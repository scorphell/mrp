"""Testes de throttling (429 throttled) para verify e team_login."""

import uuid
from datetime import date

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.settings import api_settings
from rest_framework.throttling import ScopedRateThrottle

from apps.core.services.jwt_service import issue_staff_token
from apps.credentials.services import qr_service
from apps.registry.models import EventSession, Team

from .helpers import api_override_settings
from .test_portal_flow import PASSWORD, make_payload, member_payload

User = get_user_model()

# Limites reduzidos para o teste (2/min). Formato: {scope: rate}.
THROTTLED_RATES = {"verify": "2/minute", "team_login": "2/minute"}


@api_override_settings()
class ThrottlingTests(TestCase):
    """ScopedRateThrottle.THROTTLE_RATES é capturado no import do módulo DRF;
    override_settings/REST_FRAMEWORK não o altera. Mutamos o dict no lugar."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        rates = api_settings.DEFAULT_THROTTLE_RATES
        if ScopedRateThrottle.THROTTLE_RATES is not rates:
            raise AssertionError(
                "THROTTLE_RATES do ScopedRateThrottle deveria ser o mesmo dict"
            )
        cls._rates_backup = dict(rates)
        rates.update(THROTTLED_RATES)

    @classmethod
    def tearDownClass(cls):
        rates = api_settings.DEFAULT_THROTTLE_RATES
        rates.clear()
        rates.update(cls._rates_backup)
        super().tearDownClass()

    def setUp(self):
        # LocMemCache persiste entre testes no mesmo processo; zera o contador.
        cache.clear()
        self.staff = User.objects.create_user(
            username="staff.throttle", password="x", is_staff=True
        )
        self.session = EventSession.objects.create(
            name="Sessão Throttle",
            kind="validation",
            date=date(2026, 10, 5),
            status="open",
        )
        self.team = Team.objects.create(
            name="Equipe Throttle",
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
        member = self.team.members.get(role="leader")
        self.qr = qr_service.qr_text_for(
            qr_service.ensure_active_token("member", member=member)
        )

    def test_third_verify_call_429(self):
        auth = {"HTTP_AUTHORIZATION": f"Bearer {issue_staff_token(self.staff)}"}
        body = {"session_id": self.session.pk, "qr_text": self.qr}

        first = self.client.post(
            "/api/v1/checkin/verify", body, content_type="application/json", **auth
        )
        second = self.client.post(
            "/api/v1/checkin/verify", body, content_type="application/json", **auth
        )
        third = self.client.post(
            "/api/v1/checkin/verify", body, content_type="application/json", **auth
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(third.status_code, 429)
        self.assertEqual(third.json()["code"], "throttled")

    def test_third_team_login_429(self):
        login = {
            "registration_code": str(self.team.registration_code),
            "password": PASSWORD,
        }
        self.client.post("/api/v1/teams/login", login, content_type="application/json")
        self.client.post("/api/v1/teams/login", login, content_type="application/json")
        third = self.client.post(
            "/api/v1/teams/login", login, content_type="application/json"
        )
        self.assertEqual(third.status_code, 429)
        self.assertEqual(third.json()["code"], "throttled")
