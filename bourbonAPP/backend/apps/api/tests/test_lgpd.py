"""Testes LGPD: export (D.4) e revogação de consentimento (D.5)."""

import uuid
from datetime import date

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from apps.checkin.models import CheckIn
from apps.core.services.jwt_service import issue_staff_token, issue_team_token
from apps.credentials.models import QrToken
from apps.credentials.services import qr_service
from apps.registry.models import EventSession, Team

from .helpers import api_override_settings
from .test_portal_flow import PASSWORD, make_payload, member_payload

User = get_user_model()


@api_override_settings()
class LgpdTests(TestCase):
    def setUp(self):
        # LocMemCache persiste entre testes: zera throttling entre classes.
        cache.clear()
        self.staff = User.objects.create_user(
            username="staff.lgpd", password="x", is_staff=True
        )
        self.session = EventSession.objects.create(
            name="Sessão Validação",
            kind="validation",
            date=date(2026, 10, 5),
            status="open",
        )
        self.team = Team.objects.create(
            name="Equipe LGPD",
            course="Engenharia Mecânica",
            campus="Campus Centro",
            registration_code=uuid.uuid4(),
        )
        response = self.client.post(
            "/api/v1/teams/register",
            make_payload(
                self.team,
                members=[
                    member_payload(1, role="leader"),
                    member_payload(2),
                    member_payload(3),
                ],
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.team.refresh_from_db()
        self.member = self.team.members.get(role="leader")
        self.vehicle = self.team.vehicle

        # Emite credenciais (member + vehicle) e registra uma presença.
        self.member_qr = qr_service.qr_text_for(
            qr_service.ensure_active_token("member", member=self.member)
        )
        self.vehicle_qr = qr_service.qr_text_for(
            qr_service.ensure_active_token("vehicle", vehicle=self.vehicle)
        )
        self.client.post(
            "/api/v1/checkin/presence",
            {"session_id": self.session.pk, "qr_text": self.member_qr},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {issue_staff_token(self.staff)}",
        )

    def _team_token(self):
        return issue_team_token(self.team)

    def _me_export(self):
        return self.client.get(
            "/api/v1/teams/me/export", HTTP_AUTHORIZATION=f"Bearer {self._team_token()}"
        )

    def _revoke(self):
        return self.client.post(
            "/api/v1/teams/me/consent/revoke",
            HTTP_AUTHORIZATION=f"Bearer {self._team_token()}",
        )

    def test_export_200_contains_data_without_auditlog(self):
        response = self._me_export()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("exported_at", body)
        self.assertEqual(body["team"]["id"], self.team.pk)
        self.assertEqual(len(body["members"]), 3)
        member = body["members"][0]
        self.assertIn("created_at", member)
        self.assertEqual(body["vehicle"]["id"], self.vehicle.pk)
        self.assertEqual(len(body["checkins"]), 1)
        self.assertEqual(body["checkins"][0]["session_id"], self.session.pk)
        self.assertEqual(len(body["qr_tokens"]), 2)
        self.assertNotIn("audit_logs", body)
        self.assertNotIn("AuditLog", body)

    def test_revoke_consent_200_and_idempotent(self):
        first = self._revoke()
        self.assertEqual(first.status_code, 200)
        self.assertGreater(first.json()["revoked_qr_tokens"], 0)

        second = self._revoke()
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["revoked_qr_tokens"], 0)

    def test_after_revoke_anonymization_and_status(self):
        self._revoke()
        for member in self.team.members.all():
            self.assertEqual(member.name, "[apagado]")
            self.assertTrue(member.email.startswith("apagado."))
            self.assertTrue(member.ra.startswith("APAGADO-"))
            self.assertIsNone(member.consent_at)
            self.assertIsNone(member.consent_version)
        self.team.refresh_from_db()
        self.assertEqual(self.team.status, "inactive")
        self.assertFalse(
            QrToken.objects.filter(member__team=self.team, status="active").exists()
        )
        self.assertFalse(
            QrToken.objects.filter(vehicle__team=self.team, status="active").exists()
        )

    def test_login_after_revoke_401(self):
        self._revoke()
        response = self.client.post(
            "/api/v1/teams/login",
            {
                "registration_code": str(self.team.registration_code),
                "password": PASSWORD,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_verify_old_qr_after_revoke_410(self):
        self._revoke()
        response = self.client.post(
            "/api/v1/checkin/verify",
            {"session_id": self.session.pk, "qr_text": self.member_qr},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {issue_staff_token(self.staff)}",
        )
        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.json()["code"], "qr_revoked")

    def test_issue_after_revoke_409(self):
        self._revoke()
        response = self.client.post(
            f"/api/v1/credentials/issue/member/{self.member.pk}",
            HTTP_AUTHORIZATION=f"Bearer {issue_staff_token(self.staff)}",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "consent_required")

    def test_checkin_row_kept_for_referential_integrity(self):
        self._revoke()
        self.assertEqual(CheckIn.objects.filter(member=self.member).count(), 1)
