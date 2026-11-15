"""Testes das constraints do modelo QrToken (transaction, sem chaves reais)."""

import uuid

from django.db import IntegrityError, transaction
from django.test import TransactionTestCase
from django.utils import timezone

from apps.registry.models import Member, Team, Vehicle

from ..models import QrToken


def make_team(name):
    team = Team.objects.create(
        name=name, course="Engenharia Mecânica", campus="Campus Centro"
    )
    members = Member.objects.bulk_create(
        [
            Member(
                team=team,
                name=f"{name} M{i + 1}",
                email=f"{name.lower()}.m{i}@exemplo.test",
                ra=f"RAMODEL{i:05d}",
                role="leader" if i == 0 else "member",
            )
            for i in range(3)
        ]
    )
    return team, members


class QrTokenConstraintTests(TransactionTestCase):
    def setUp(self):
        self.team, self.members = make_team("Equipe Model")
        self.member = self.members[0]
        self.vehicle = Vehicle.objects.create(team=self.team, name="Chassi Model")

    def _token(
        self, *, member=None, vehicle=None, subject_type="member", status="active"
    ):
        return QrToken.objects.create(
            subject_type=subject_type,
            member=member,
            vehicle=vehicle,
            token_id=uuid.uuid4(),
            payload_json={"v": 1, "k": subject_type[0]},
            signature="A" * 86,
            status=status,
            issued_at=timezone.now(),
        )

    def test_second_active_same_subject_via_bulk_create_raises(self):
        self._token(member=self.member)
        with self.assertRaises(IntegrityError), transaction.atomic():
            QrToken.objects.bulk_create(
                [
                    QrToken(
                        subject_type="member",
                        member=self.member,
                        token_id=uuid.uuid4(),
                        payload_json={"v": 1, "k": "m"},
                        signature="B" * 86,
                        status="active",
                    )
                ]
            )

    def test_active_plus_revoked_same_subject_passes(self):
        first = self._token(member=self.member)
        first.status = "revoked"
        first.revoked_at = timezone.now()
        first.save(update_fields=["status", "revoked_at"])
        self._token(member=self.member)
        self.assertEqual(QrToken.objects.filter(member=self.member).count(), 2)

    def test_member_and_vehicle_active_same_team_passes(self):
        self._token(member=self.member)
        self._token(subject_type="vehicle", vehicle=self.vehicle)
        self.assertEqual(QrToken.objects.count(), 2)

    def test_multiple_subjects_active_passes(self):
        for member in self.members:
            self._token(member=member)
        self._token(subject_type="vehicle", vehicle=self.vehicle)
        self.assertEqual(QrToken.objects.filter(status="active").count(), 4)

    def test_str_has_no_pii(self):
        token = self._token(member=self.member)
        rendered = str(token)
        self.assertNotIn(self.member.name, rendered)
        self.assertNotIn(self.member.email, rendered)
        self.assertNotIn(self.team.name, rendered)
