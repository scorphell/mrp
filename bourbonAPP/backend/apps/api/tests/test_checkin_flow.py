"""Testes do fluxo de check-in: issue, verify, presence, conformity e PDF (D.6–D.10)."""

import time
import uuid
from datetime import date

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from apps.checkin.models import ConformityCheck
from apps.core.services.jwt_service import issue_staff_token, issue_team_token
from apps.credentials.services import qr_service, signing
from apps.registry.models import EventSession, Team

from .helpers import _KEY, api_override_settings
from .test_portal_flow import make_payload, member_payload

User = get_user_model()


def make_qr_text(payload, key=_KEY):
    """Monta o texto de um QR assinado com uma chave (fictícia ou não)."""
    _, signature = signing.sign_payload(payload, key=key)
    return signing.build_qr_text(payload, signature)


@api_override_settings()
class CheckinFlowTests(TestCase):
    def setUp(self):
        # LocMemCache persiste entre testes: zera throttling entre classes.
        cache.clear()
        self.staff = User.objects.create_user(
            username="staff.checkin", password="x", is_staff=True
        )
        self.session = EventSession.objects.create(
            name="Sessão Validação",
            kind="validation",
            date=date(2026, 10, 5),
            status="open",
        )
        self.team = self._register_team("Equipe Checkin Flow")
        self.member = self.team.members.get(role="leader")
        self.vehicle = self.team.vehicle

    # ---------- fixtures ----------

    def _register_team(self, name, base=1):
        team = Team.objects.create(
            name=name,
            course="Engenharia Mecânica",
            campus="Campus Centro",
            registration_code=uuid.uuid4(),
        )
        payload = make_payload(
            team,
            members=[
                member_payload(base, role="leader"),
                member_payload(base + 1),
                member_payload(base + 2),
            ],
        )
        response = self.client.post(
            "/api/v1/teams/register", payload, content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        return Team.objects.get(pk=team.pk)

    def _staff_token(self):
        return issue_staff_token(self.staff)

    def _team_token(self, team=None):
        return issue_team_token(team or self.team)

    def _auth(self, token=None):
        return {"HTTP_AUTHORIZATION": f"Bearer {token or self._staff_token()}"}

    def _member_qr(self, member=None):
        member = member or self.member
        token = qr_service.ensure_active_token("member", member=member)
        return qr_service.qr_text_for(token)

    def _vehicle_qr(self, vehicle=None):
        vehicle = vehicle or self.vehicle
        token = qr_service.ensure_active_token("vehicle", vehicle=vehicle)
        return qr_service.qr_text_for(token)

    def _issue(self, subject_type, pk, token=None):
        return self.client.post(
            f"/api/v1/credentials/issue/{subject_type}/{pk}",
            HTTP_AUTHORIZATION=f"Bearer {token or self._staff_token()}",
        )

    def _verify(self, qr_text, session=None, token=None):
        return self.client.post(
            "/api/v1/checkin/verify",
            {"session_id": (session or self.session).pk, "qr_text": qr_text},
            content_type="application/json",
            **self._auth(token),
        )

    def _presence(self, qr_text, session=None, token=None):
        return self.client.post(
            "/api/v1/checkin/presence",
            {"session_id": (session or self.session).pk, "qr_text": qr_text},
            content_type="application/json",
            **self._auth(token),
        )

    def _conformity(self, qr_text, **extra):
        body = {
            "session_id": self.session.pk,
            "qr_text": qr_text,
            "result": "pass",
            "items": {"dimensoes": True, "ratoeira": True, "materiais": True},
            "notes": "",
        }
        body.update(extra)
        return self.client.post(
            "/api/v1/checkin/conformity",
            body,
            content_type="application/json",
            **self._auth(),
        )

    # ---------- credentials ----------

    def test_issue_member_staff_200(self):
        response = self._issue("member", self.member.pk)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["subject_type"], "member")
        self.assertEqual(body["subject_id"], self.member.pk)
        self.assertTrue(body["qr"].startswith("data:image/png;base64,"))
        self.assertIsNotNone(body["issued_at"])
        self.assertNotIn("name", body)
        self.assertNotIn("email", body)

    def test_issue_vehicle_staff_200(self):
        response = self._issue("vehicle", self.vehicle.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["subject_type"], "vehicle")
        self.assertTrue(response.json()["qr"].startswith("data:image/png;base64,"))

    def test_issue_own_team_200(self):
        response = self._issue("member", self.member.pk, token=self._team_token())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["subject_type"], "member")

    def test_issue_other_team_403(self):
        other = self._register_team("Equipe Outra", base=10)
        token = self._team_token(other)
        response = self._issue("member", self.member.pk, token=token)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "permission_denied")

    def test_issue_member_without_consent_409(self):
        self.team.members.update(consent_at=None, consent_version=None)
        response = self._issue("member", self.member.pk)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "consent_required")

    def test_issue_unknown_subject_404(self):
        response = self._issue("member", 999999)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "subject_not_found")

    # ---------- verify ----------

    def test_verify_valid_member_200(self):
        response = self._verify(self._member_qr())
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["valid"])
        self.assertEqual(body["subject_type"], "member")
        self.assertEqual(body["subject_id"], self.member.pk)
        self.assertEqual(body["member"]["name"], self.member.name)
        self.assertEqual(body["member"]["team"], self.team.name)
        self.assertEqual(body["member"]["role"], self.member.role)
        self.assertNotIn("email", body["member"])
        self.assertNotIn("ra", body["member"])

    def test_verify_valid_vehicle_200(self):
        response = self._verify(self._vehicle_qr())
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["subject_type"], "vehicle")
        self.assertIsNone(body["member"])
        self.assertEqual(body["vehicle"]["name"], self.vehicle.name)
        self.assertEqual(body["vehicle"]["team"], self.team.name)
        self.assertIsNone(body["vehicle"]["conformity_status"])

    def test_verify_tampered_signature_400(self):
        token = qr_service.ensure_active_token("member", member=self.member)
        other_key = __import__(
            "cryptography.hazmat.primitives.asymmetric.ed25519",
            fromlist=["Ed25519PrivateKey"],
        ).Ed25519PrivateKey.generate()
        _, forged = signing.sign_payload(token.payload_json, key=other_key)
        tampered = signing.build_qr_text(token.payload_json, forged)
        response = self._verify(tampered)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "qr_signature")

    def test_verify_revoked_410(self):
        qr = self._member_qr()
        qr_service.revoke_for_subject("member", member=self.member)
        response = self._verify(qr)
        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.json()["code"], "qr_revoked")

    def test_verify_expired_410(self):
        token = qr_service.ensure_active_token("member", member=self.member)
        payload = dict(token.payload_json)
        payload["exp"] = int(time.time()) - 1000
        response = self._verify(make_qr_text(payload))
        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.json()["code"], "qr_expired")

    def test_verify_unknown_token_404(self):
        now = int(time.time())
        payload = {
            "v": 1,
            "k": "m",
            "ti": str(uuid.uuid4()),
            "iat": now,
            "exp": now + 3600,
        }
        response = self._verify(make_qr_text(payload))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "qr_unknown_token")

    def test_verify_closed_session_409(self):
        self.session.status = "closed"
        self.session.save(update_fields=["status"])
        response = self._verify(self._member_qr())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "session_closed")

    def test_verify_without_auth_401(self):
        response = self.client.post(
            "/api/v1/checkin/verify",
            {"session_id": self.session.pk, "qr_text": "x"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "not_authenticated")

    def test_verify_non_staff_403(self):
        member_user = User.objects.create_user(username="nao.staff", password="x")
        response = self.client.post(
            "/api/v1/checkin/verify",
            {"session_id": self.session.pk, "qr_text": "x"},
            content_type="application/json",
            **self._auth(issue_staff_token(member_user)),
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "permission_denied")

    # ---------- presence ----------

    def test_presence_twice_is_idempotent(self):
        qr = self._member_qr()
        first = self._presence(qr)
        self.assertEqual(first.status_code, 200)
        first_body = first.json()
        self.assertFalse(first_body["duplicate"])
        self.assertIsNotNone(first_body["checkin_id"])
        self.assertEqual(first_body["subject_type"], "member")
        self.assertEqual(first_body["subject_id"], self.member.pk)

        second = self._presence(qr)
        self.assertEqual(second.status_code, 200)
        second_body = second.json()
        self.assertTrue(second_body["duplicate"])
        self.assertEqual(second_body["checkin_id"], first_body["checkin_id"])
        self.assertEqual(second_body["uuid"], first_body["uuid"])

    def test_presence_without_auth_401(self):
        response = self.client.post(
            "/api/v1/checkin/presence",
            {"session_id": self.session.pk, "qr_text": "x"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_presence_non_staff_403(self):
        member_user = User.objects.create_user(username="nao.staff2", password="x")
        response = self.client.post(
            "/api/v1/checkin/presence",
            {"session_id": self.session.pk, "qr_text": "x"},
            content_type="application/json",
            **self._auth(issue_staff_token(member_user)),
        )
        self.assertEqual(response.status_code, 403)

    # ---------- conformity ----------

    def test_conformity_vehicle_201(self):
        response = self._conformity(self._vehicle_qr())
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["vehicle_id"], self.vehicle.pk)
        self.assertEqual(body["result"], "pass")
        self.assertEqual(body["conformity_status"], "pass")
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.conformity_status, "pass")
        self.assertIsNotNone(self.vehicle.conformity_checked_at)

    def test_conformity_member_qr_400(self):
        response = self._conformity(self._member_qr())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "expected_vehicle_qr")

    def test_conformity_items_outside_whitelist_400(self):
        response = self._conformity(
            self._vehicle_qr(), items={"dimensoes": True, "motor": True}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_items")
        self.assertIn("motor", response.json()["detail"])

    def test_conformity_second_check_flips_status(self):
        self._conformity(self._vehicle_qr())
        response = self._conformity(
            self._vehicle_qr(),
            result="fail",
            items={"dimensoes": False, "ratoeira": True, "materiais": True},
            notes="Dimensão acima de 60x30x30 cm.",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["result"], "fail")
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.conformity_status, "fail")
        self.assertEqual(
            ConformityCheck.objects.filter(vehicle=self.vehicle).count(), 2
        )

    # ---------- PDF ----------

    def test_team_pdf_staff_200(self):
        response = self.client.get(
            f"/api/v1/credentials/team/{self.team.pk}/pdf", **self._auth()
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(
            f"credenciais-team-{self.team.pk}.pdf", response["Content-Disposition"]
        )

    def test_team_pdf_team_own_200(self):
        """"Equipe autenticada baixa o PDF da própria equipe (portal)."""
        response = self.client.get(
            f"/api/v1/credentials/team/{self.team.pk}/pdf",
            **self._auth(self._team_token()),
        )
        self.assertEqual(response.status_code, 200)

    def test_team_pdf_team_other_403(self):
        """Equipe autenticada NÃO baixa o PDF de outra equipe."""
        other = self._register_team("Equipe Outra Base", base=10)
        response = self.client.get(
            f"/api/v1/credentials/team/{other.pk}/pdf",
            **self._auth(self._team_token()),
        )
        self.assertEqual(response.status_code, 403)

    def test_team_pdf_unknown_team_404(self):
        response = self.client.get(
            "/api/v1/credentials/team/999999/pdf", **self._auth()
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "team_not_found")
