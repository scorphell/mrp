"""Testes do fluxo do portal: register, login e teams/me (D.1–D.3)."""

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.core.services.jwt_service import decode_token, issue_staff_token
from apps.registry.models import EventSession, Team, TeamAuth, Vehicle

from .helpers import api_override_settings

PASSWORD = "SenhaForte-123!"  # pragma: allowlist secret


def member_payload(index, role="member"):
    return {
        "name": f"Pessoa Exemplo {index}",
        "email": f"pessoa{index}@exemplo.test",
        "ra": f"RAM3{index:05d}",
        "role": role,
        "consent_version": 1,
    }


def make_payload(team, *, password=PASSWORD, members=None, vehicle="Chassi X1"):
    return {
        "registration_code": str(team.registration_code),
        "password": password,
        "members": members
        or [
            member_payload(1, role="leader"),
            member_payload(2),
            member_payload(3),
        ],
        "vehicle": {"name": vehicle},
    }


@api_override_settings()
class PortalFlowTests(TestCase):
    def setUp(self):
        # LocMemCache persiste entre testes: zera throttling entre classes.
        cache.clear()
        self.team = Team.objects.create(
            name="Equipe Portal",
            course="Engenharia Mecânica",
            campus="Campus Centro",
            registration_code=uuid.uuid4(),
            status="active",
        )

    def _register(self, **overrides):
        payload = make_payload(self.team)
        payload.update(overrides)
        return self.client.post(
            "/api/v1/teams/register", payload, content_type="application/json"
        )

    def test_register_success_201(self):
        response = self._register()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["detail"], "equipe registrada")
        self.assertEqual(body["team_id"], self.team.pk)
        self.assertEqual(body["team_name"], self.team.name)
        self.assertEqual(body["member_count"], 3)

        self.team.refresh_from_db()
        self.assertIsNotNone(self.team.registered_at)
        auth = TeamAuth.objects.get(team=self.team)
        self.assertTrue(auth.password_hash.startswith("pbkdf2_sha256$"))
        members = list(self.team.members.all())
        self.assertEqual(len(members), 3)
        for member in members:
            self.assertIsNotNone(member.consent_at)  # consent_at é server-side
            self.assertEqual(member.consent_version, 1)
        self.assertTrue(
            Vehicle.objects.filter(team=self.team, name="Chassi X1").exists()
        )

    def test_register_unknown_code_404(self):
        self._register(registration_code=str(uuid.uuid4()))
        response = self._register(registration_code=str(uuid.uuid4()))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "registration_code_not_found")

    def test_re_register_409(self):
        self._register()
        response = self._register()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "team_already_registered")

    def test_register_two_members_400(self):
        payload = make_payload(self.team)
        payload["members"] = payload["members"][:2]
        response = self.client.post(
            "/api/v1/teams/register", payload, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("members", response.json()["fields"])

    def test_register_two_leaders_400(self):
        payload = make_payload(self.team)
        payload["members"][1]["role"] = "leader"
        response = self.client.post(
            "/api/v1/teams/register", payload, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("members", response.json()["fields"])

    def test_register_missing_consent_version_400(self):
        payload = make_payload(self.team)
        del payload["members"][0]["consent_version"]
        response = self.client.post(
            "/api/v1/teams/register", payload, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_register_honeypot_filled_400(self):
        """Bots que preenchem o honeypot 'website' são rejeitados sem efeito."""
        response = self._register(website="https://spam.example")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "bot_detected")
        self.team.refresh_from_db()
        self.assertIsNone(self.team.registered_at)
        self.assertFalse(TeamAuth.objects.filter(team=self.team).exists())

    @override_settings(REGISTRATION_CUTOFF_HOURS=24)
    def test_register_blocked_after_cutoff_403(self):
        """Sessão hoje + cutoff 24h = inscrição fechada (padrão de indústria)."""
        EventSession.objects.create(
            name="Cutoff Hoje",
            kind="final",
            date=timezone.localdate(),
            status="planned",
        )
        response = self._register()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "registration_closed")
        self.team.refresh_from_db()
        self.assertIsNone(self.team.registered_at)

    @override_settings(REGISTRATION_CUTOFF_HOURS=24)
    def test_register_open_far_before_session_201(self):
        """Sessão em 10 dias + cutoff 24h = janela aberta."""
        EventSession.objects.create(
            name="Cutoff Futuro",
            kind="final",
            date=timezone.localdate() + timedelta(days=10),
            status="planned",
        )
        response = self._register()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["detail"], "equipe registrada")

    @override_settings(REGISTRATION_CUTOFF_HOURS=0)
    def test_register_cutoff_zero_allows_until_session_date(self):
        """CUTOFF=0 = inscrições valem até a meia-noite do dia da sessão."""
        EventSession.objects.create(
            name="Cutoff Zero",
            kind="final",
            date=timezone.localdate() + timedelta(days=7),
            status="planned",
        )
        response = self._register()
        self.assertEqual(response.status_code, 201)

    @override_settings(REGISTRATION_CUTOFF_HOURS=24)
    def test_register_without_future_session_allows_201(self):
        """Sem sessão futura (pré-cadastro/teste) o registro não bloqueia."""
        response = self._register()
        self.assertEqual(response.status_code, 201)

    def test_register_weak_password_400(self):
        response = self._register(password="12345678")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json()["fields"])

    def test_register_duplicate_email_400(self):
        payload = make_payload(self.team)
        payload["members"][1]["email"] = payload["members"][0]["email"]
        response = self.client.post(
            "/api/v1/teams/register", payload, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "duplicate_member")

    def test_register_duplicate_ra_400(self):
        payload = make_payload(self.team)
        payload["members"][2]["ra"] = payload["members"][0]["ra"]
        response = self.client.post(
            "/api/v1/teams/register", payload, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "duplicate_member")

    def test_login_200_and_token_decodes_as_team(self):
        self._register()
        response = self.client.post(
            "/api/v1/teams/login",
            {
                "registration_code": str(self.team.registration_code),
                "password": PASSWORD,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["token_type"], "Bearer")
        self.assertEqual(body["expires_in"], 43200)
        self.assertEqual(body["team"]["id"], self.team.pk)
        claims = decode_token(body["token"])
        self.assertEqual(claims["typ"], "team")
        self.assertEqual(claims["tid"], self.team.pk)

    def test_login_wrong_password_and_unknown_code_same_body_401(self):
        self._register()
        wrong = self.client.post(
            "/api/v1/teams/login",
            {
                "registration_code": str(self.team.registration_code),
                "password": "errada-123",  # pragma: allowlist secret
            },
            content_type="application/json",
        )
        unknown = self.client.post(
            "/api/v1/teams/login",
            {"registration_code": str(uuid.uuid4()), "password": "errada-123"},
            content_type="application/json",
        )
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(wrong.json(), unknown.json())
        self.assertEqual(wrong.json()["code"], "invalid_credentials")

    def test_login_inactive_team_401(self):
        self._register()
        self.team.status = "inactive"
        self.team.save(update_fields=["status"])
        response = self.client.post(
            "/api/v1/teams/login",
            {
                "registration_code": str(self.team.registration_code),
                "password": PASSWORD,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "invalid_credentials")

    def test_teams_me_with_bearer_200(self):
        self._register()
        token = self._team_token()
        response = self.client.get(
            "/api/v1/teams/me", HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()["team"]
        self.assertEqual(body["id"], self.team.pk)
        self.assertEqual(body["name"], self.team.name)
        self.assertIsNotNone(body["registered_at"])
        self.assertEqual(len(body["members"]), 3)
        member = body["members"][0]
        self.assertIn("email", member)
        self.assertIn("ra", member)
        self.assertEqual(body["vehicle"]["name"], "Chassi X1")

    def test_teams_me_without_token_401(self):
        response = self.client.get("/api/v1/teams/me")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "not_authenticated")

    def test_teams_me_with_staff_token_403(self):
        user = get_user_model().objects.create_user(
            username="staff.portal", password="x", is_staff=True
        )
        token = issue_staff_token(user)
        response = self.client.get(
            "/api/v1/teams/me", HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "permission_denied")

    def _team_token(self):
        from apps.core.services.jwt_service import issue_team_token

        return issue_team_token(self.team)
