"""Testes de orquestração (issue/ensure/revoke/verify) com chave fictícia."""

import tempfile
import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.registry.models import Member, Team, Vehicle

from ..models import QrToken
from ..services import signing
from ..services.qr_service import (
    ensure_active_token,
    get_active_token,
    issue_token,
    qr_text_for,
    revoke_for_subject,
    revoke_token,
    verify_qr,
)

from . import make_keypair

_member_seq = 0


def make_team(name, member_count=5, with_vehicle=True):
    """Equipe fictícia criada via bulk_create (validação 3–5 fica no portal/M3)."""
    global _member_seq
    team = Team.objects.create(
        name=name, course="Engenharia Mecânica", campus="Campus Centro"
    )
    members = []
    for i in range(member_count):
        _member_seq += 1
        members.append(
            Member(
                team=team,
                name=f"{name} Membro {i + 1}",
                email=f"membro.m2.{_member_seq}@exemplo.test",
                ra=f"RAM2{_member_seq:06d}",
                role="leader" if i == 0 else "member",
            )
        )
    Member.objects.bulk_create(members)
    vehicle = (
        Vehicle.objects.create(team=team, name=f"{name} Chassi")
        if with_vehicle
        else None
    )
    return team, members, vehicle


class QrServiceTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tmp = tempfile.TemporaryDirectory()
        cls.priv_path, cls.pub_path, _ = make_keypair(Path(cls._tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()
        super().tearDownClass()

    def setUp(self):
        override = override_settings(
            ED25519_PRIVATE_PATH=str(self.priv_path),
            ED25519_PUBLIC_PATH=str(self.pub_path),
        )
        override.enable()
        self.addCleanup(override.disable)
        self.team, self.members, self.vehicle = make_team("Equipe QR")
        self.member = self.members[0]

    def test_verify_ok_returns_payload_without_pii(self):
        token = issue_token("member", member=self.member)
        payload = verify_qr(qr_text_for(token))
        self.assertEqual(payload, token.payload_json)
        self.assertNotIn("name", payload)
        self.assertNotIn("email", payload)
        for key in ("v", "k", "ti", "iat", "exp"):
            self.assertIn(key, payload)

    def test_revoked_token_rejected(self):
        token = issue_token("member", member=self.member)
        revoke_token(token)
        with self.assertRaises(signing.InvalidQrError) as ctx:
            verify_qr(qr_text_for(token))
        self.assertEqual(ctx.exception.reason, "revoked")

    def test_unknown_token_rejected(self):
        now = int(timezone.now().timestamp())
        payload = {
            "v": 1,
            "k": "m",
            "ti": str(uuid.uuid4()),
            "iat": now,
            "exp": now + 3600,
        }
        _, b64 = signing.sign_payload(payload)
        with self.assertRaises(signing.InvalidQrError) as ctx:
            verify_qr(signing.build_qr_text(payload, b64))
        self.assertEqual(ctx.exception.reason, "unknown_token")

    def test_expired_rejected_and_future_passes(self):
        now = int(timezone.now().timestamp())
        expired = {
            "v": 1,
            "k": "m",
            "ti": str(uuid.uuid4()),
            "iat": now - 7200,
            "exp": now - 3600,
        }
        _, b64_expired = signing.sign_payload(expired)
        QrToken.objects.create(
            subject_type="member",
            member=self.member,
            token_id=expired["ti"],
            payload_json=expired,
            signature=b64_expired,
            status="active",
        )
        with self.assertRaises(signing.InvalidQrError) as ctx:
            verify_qr(signing.build_qr_text(expired, b64_expired))
        self.assertEqual(ctx.exception.reason, "expired")

        future = {
            "v": 1,
            "k": "m",
            "ti": str(uuid.uuid4()),
            "iat": now,
            "exp": now + 3600,
        }
        _, b64_future = signing.sign_payload(future)
        QrToken.objects.create(
            subject_type="member",
            member=self.members[1],
            token_id=future["ti"],
            payload_json=future,
            signature=b64_future,
            status="active",
        )
        self.assertEqual(verify_qr(signing.build_qr_text(future, b64_future)), future)

    def test_member_and_vehicle_tokens_coexist_active(self):
        member_token = issue_token("member", member=self.member)
        vehicle_token = issue_token("vehicle", vehicle=self.vehicle)
        self.assertEqual(member_token.status, "active")
        self.assertEqual(vehicle_token.status, "active")
        self.assertEqual(verify_qr(qr_text_for(member_token))["k"], "m")
        self.assertEqual(verify_qr(qr_text_for(vehicle_token))["k"], "v")

    def test_issue_new_token_revokes_previous_same_subject(self):
        first = issue_token("member", member=self.member)
        second = issue_token("member", member=self.member)
        first.refresh_from_db()
        self.assertEqual(first.status, "revoked")
        self.assertIsNotNone(first.revoked_at)
        self.assertEqual(second.status, "active")
        with self.assertRaises(signing.InvalidQrError) as ctx:
            verify_qr(qr_text_for(first))
        self.assertEqual(ctx.exception.reason, "revoked")

    def test_kind_mismatch_rejected(self):
        token = issue_token("vehicle", vehicle=self.vehicle)
        payload = {**token.payload_json, "k": "m"}
        _, b64 = signing.sign_payload(payload)
        with self.assertRaises(signing.InvalidQrError) as ctx:
            verify_qr(signing.build_qr_text(payload, b64))
        self.assertEqual(ctx.exception.reason, "kind_mismatch")

    def test_qr_payload_differs_from_stored_rejected(self):
        # Defesa em profundidade: payload B assinado VALIDAMENTE pela mesma
        # chave, mas diferente do payload A gravado para o mesmo ti, é
        # rejeitado — a assinatura sozinha não basta.
        token = issue_token("member", member=self.member)
        payload_a = token.payload_json
        payload_b = {**payload_a, "iat": payload_a["iat"] + 1}
        _, b64_b = signing.sign_payload(payload_b)
        with self.assertRaises(signing.InvalidQrError) as ctx:
            verify_qr(signing.build_qr_text(payload_b, b64_b))
        self.assertEqual(ctx.exception.reason, "signature")

    def test_ensure_active_token_reuses_then_reissues(self):
        token = ensure_active_token("member", member=self.member)
        again = ensure_active_token("member", member=self.member)
        self.assertEqual(token.pk, again.pk)
        self.assertEqual(revoke_for_subject("member", member=self.member), 1)
        new_token = ensure_active_token("member", member=self.member)
        self.assertNotEqual(token.pk, new_token.pk)

    def test_ensure_active_token_reissues_when_stored_expired(self):
        now = int(timezone.now().timestamp())
        expired = {
            "v": 1,
            "k": "m",
            "ti": str(uuid.uuid4()),
            "iat": now - 7200,
            "exp": now - 3600,
        }
        _, b64 = signing.sign_payload(expired)
        stale = QrToken.objects.create(
            subject_type="member",
            member=self.member,
            token_id=expired["ti"],
            payload_json=expired,
            signature=b64,
            status="active",
        )
        fresh = ensure_active_token("member", member=self.member)
        stale.refresh_from_db()
        self.assertNotEqual(fresh.pk, stale.pk)
        self.assertEqual(stale.status, "revoked")
        self.assertIsNotNone(stale.revoked_at)
        self.assertEqual(fresh.status, "active")
        self.assertGreater(fresh.payload_json["exp"], int(timezone.now().timestamp()))

    def test_revoke_for_subject_returns_count(self):
        issue_token("member", member=self.member)
        issue_token("member", member=self.member)  # revoga o primeiro
        self.assertEqual(revoke_for_subject("member", member=self.member), 1)
        self.assertIsNone(get_active_token("member", member=self.member))

    def test_issue_token_validates_exactly_one_subject(self):
        with self.assertRaises(ValueError):
            issue_token("member")
        with self.assertRaises(ValueError):
            issue_token("member", member=self.member, vehicle=self.vehicle)
        with self.assertRaises(ValueError):
            issue_token("vehicle", member=self.member)
        with self.assertRaises(ValueError):
            issue_token("staff")

    def test_bulk_create_with_member_and_vehicle_violates_check(self):
        # bulk_create pula clean() — a garantia forte é o CheckConstraint no banco.
        with self.assertRaises(IntegrityError):
            QrToken.objects.bulk_create(
                [
                    QrToken(
                        subject_type="member",
                        member=self.member,
                        vehicle=self.vehicle,
                        token_id=uuid.uuid4(),
                        payload_json={},
                        signature="x" * 86,
                    )
                ]
            )

    def test_clean_rejects_xor_and_subject_mismatch(self):
        payload = {"v": 1}
        ok = QrToken(
            subject_type="member",
            member=self.member,
            token_id=uuid.uuid4(),
            payload_json=payload,
            signature="x" * 86,
        )
        ok.full_clean()
        both = QrToken(
            subject_type="member",
            member=self.member,
            vehicle=self.vehicle,
            token_id=uuid.uuid4(),
            payload_json=payload,
            signature="x" * 86,
        )
        with self.assertRaises(ValidationError):
            both.full_clean()
        wrong = QrToken(
            subject_type="vehicle",
            member=self.member,
            token_id=uuid.uuid4(),
            payload_json=payload,
            signature="x" * 86,
        )
        with self.assertRaises(ValidationError):
            wrong.full_clean()
