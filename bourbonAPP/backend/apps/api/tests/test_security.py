"""Testes de segurança: tokens inválidos/expirados, tipos trocados e PII em logs."""

import json
import time
import uuid
from datetime import date

import jwt as pyjwt
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from apps.core.models import AuditLog
from apps.core.services.jwt_service import issue_staff_token, issue_team_token
from apps.credentials.services import qr_service, signing
from apps.registry.models import EventSession, Team
from django.conf import settings

from .helpers import api_override_settings
from .test_portal_flow import PASSWORD, make_payload, member_payload

User = get_user_model()


@api_override_settings()
class SecurityTests(TestCase):
    def setUp(self):
        # LocMemCache persiste entre testes: zera throttling entre classes.
        cache.clear()
        self.staff = User.objects.create_user(
            username="staff.security", password="x", is_staff=True
        )
        self.session = EventSession.objects.create(
            name="Sessão Segurança",
            kind="validation",
            date=date(2026, 10, 5),
            status="open",
        )
        self.team = Team.objects.create(
            name="Equipe Segurança",
            course="Engenharia Mecânica",
            campus="Campus Centro",
            registration_code=uuid.uuid4(),
        )
        self.client.post(
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
        self.team.refresh_from_db()
        self.member = self.team.members.get(role="leader")

    def _staff_token(self, user=None):
        return issue_staff_token(user or self.staff)

    def _expired_staff_token(self):
        now = int(time.time())
        return pyjwt.encode(
            {
                "typ": "staff",
                "uid": self.staff.pk,
                "iat": now - 7200,
                "exp": now - 3600,
                "jti": str(uuid.uuid4()),
            },
            signing.load_private_key(settings.ED25519_PRIVATE_PATH),
            algorithm="EdDSA",
        )

    def _crafted_token(self, claims):
        return pyjwt.encode(
            claims,
            signing.load_private_key(settings.ED25519_PRIVATE_PATH),
            algorithm="EdDSA",
        )

    def test_tampered_token_401_invalid_token(self):
        token = self._staff_token()[:-5] + "AAAAA"
        response = self.client.get(
            "/api/v1/sessions", HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "invalid_token")

    def test_expired_token_401(self):
        response = self.client.get(
            "/api/v1/sessions",
            HTTP_AUTHORIZATION=f"Bearer {self._expired_staff_token()}",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "invalid_token")

    def test_token_without_iat_exp_401(self):
        token = self._crafted_token(
            {"typ": "staff", "uid": self.staff.pk, "jti": str(uuid.uuid4())}
        )
        response = self.client.get(
            "/api/v1/sessions", HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "invalid_token")

    def test_unsupported_typ_401(self):
        now = int(time.time())
        token = self._crafted_token(
            {
                "typ": "admin",
                "uid": self.staff.pk,
                "iat": now - 60,
                "exp": now + 3600,
                "jti": str(uuid.uuid4()),
            }
        )
        response = self.client.get(
            "/api/v1/sessions", HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "invalid_token")

    def test_inactive_staff_401(self):
        inactive = User.objects.create_user(
            username="staff.security.inactive",
            password="x",
            is_staff=True,
            is_active=False,
        )
        response = self.client.get(
            "/api/v1/sessions",
            HTTP_AUTHORIZATION=f"Bearer {self._staff_token(inactive)}",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "invalid_token")

    def test_team_token_on_staff_endpoint_403(self):
        response = self.client.get(
            "/api/v1/sessions",
            HTTP_AUTHORIZATION=f"Bearer {issue_team_token(self.team)}",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "permission_denied")

    def test_staff_token_on_team_endpoint_403(self):
        response = self.client.get(
            "/api/v1/teams/me",
            HTTP_AUTHORIZATION=f"Bearer {self._staff_token()}",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "permission_denied")

    def test_malformed_header_401_not_authenticated(self):
        response = self.client.get(
            "/api/v1/teams/me", HTTP_AUTHORIZATION="Basic dXNlcjpwYXNz"
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "not_authenticated")

    def test_audit_logs_never_contain_pii(self):
        pii_parts = [
            "Pessoa Exemplo 1",
            "pessoa1@exemplo.test",
            f"RAM3{1:05d}",
            self.team.name,
        ]
        # Fluxo completo: register, login, issue, verify, presence, conformity,
        # export e revoke — cada um grava AuditLog.
        self.client.post(
            "/api/v1/teams/login",
            {
                "registration_code": str(self.team.registration_code),
                "password": PASSWORD,
            },
            content_type="application/json",
        )
        member_qr = qr_service.qr_text_for(
            qr_service.ensure_active_token("member", member=self.member)
        )
        vehicle_qr = qr_service.qr_text_for(
            qr_service.ensure_active_token("vehicle", vehicle=self.team.vehicle)
        )
        staff_auth = {"HTTP_AUTHORIZATION": f"Bearer {self._staff_token()}"}
        self.client.post(
            f"/api/v1/credentials/issue/member/{self.member.pk}", **staff_auth
        )
        self.client.post(
            f"/api/v1/credentials/issue/vehicle/{self.team.vehicle.pk}", **staff_auth
        )
        self.client.post(
            "/api/v1/checkin/verify",
            {"session_id": self.session.pk, "qr_text": member_qr},
            content_type="application/json",
            **staff_auth,
        )
        self.client.post(
            "/api/v1/checkin/presence",
            {"session_id": self.session.pk, "qr_text": member_qr},
            content_type="application/json",
            **staff_auth,
        )
        self.client.post(
            "/api/v1/checkin/conformity",
            {
                "session_id": self.session.pk,
                "qr_text": vehicle_qr,
                "result": "pass",
                "items": {"dimensoes": True, "ratoeira": True, "materiais": True},
            },
            content_type="application/json",
            **staff_auth,
        )
        self.client.get(
            "/api/v1/teams/me/export",
            HTTP_AUTHORIZATION=f"Bearer {issue_team_token(self.team)}",
        )
        self.client.post(
            "/api/v1/teams/me/consent/revoke",
            HTTP_AUTHORIZATION=f"Bearer {issue_team_token(self.team)}",
        )

        self.assertGreaterEqual(AuditLog.objects.count(), 9)
        for log in AuditLog.objects.all():
            raw_meta = json.dumps(log.meta, ensure_ascii=False)
            raw_row = "|".join(
                [
                    str(log.action),
                    str(log.target_type or ""),
                    str(log.target_id or ""),
                    raw_meta,
                ]
            )
            for part in pii_parts:
                self.assertNotIn(part, raw_row)
