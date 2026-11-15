"""Testes do healthcheck público (D.11)."""

from django.test import TestCase

from .helpers import _PUBLIC_PATH, api_override_settings


@api_override_settings()
class HealthTests(TestCase):
    def test_health_ok(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "db": "ok", "signing": "ok"})

    def test_health_degraded_when_public_key_missing(self):
        with api_override_settings(
            ED25519_PUBLIC_PATH=_PUBLIC_PATH.with_name("missing.pem")
        ):
            response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertEqual(body["status"], "degraded")
        self.assertEqual(body["db"], "ok")
        self.assertEqual(body["signing"], "error")
