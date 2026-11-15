import uuid
from datetime import date

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase

from apps.registry.models import EventSession, Member, Team, Vehicle

from .models import CheckIn, ConformityCheck

User = get_user_model()


class CheckInConstraintTests(TransactionTestCase):
    def setUp(self):
        self.session = EventSession.objects.create(
            name="Sessão Validação 2026",
            kind="validation",
            date=date(2026, 10, 5),
        )
        self.team = Team.objects.create(
            name="Equipe Checkin", course="Engenharia Mecânica", campus="Campus Centro"
        )
        self.members = Member.objects.bulk_create(
            [
                Member(
                    team=self.team,
                    name=f"Membro Checkin {i}",
                    email=f"checkin.{i}@exemplo.test",
                    ra=f"RACHECKIN{i:04d}",
                    role="member" if i else "leader",
                )
                for i in range(3)
            ]
        )
        self.member = self.members[0]
        self.vehicle = Vehicle.objects.create(team=self.team, name="Chassi Checkin")
        self.staff = User.objects.create_user(username="staff.checkin", password="x")

    def _checkin(self, **kwargs):
        defaults = {
            "session": self.session,
            "subject_type": "member",
            "member": self.member,
            "staff": self.staff,
        }
        defaults.update(kwargs)
        return CheckIn.objects.create(**defaults)

    def test_duplicate_member_checkin_same_session_raises(self):
        self._checkin()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._checkin()

    def test_same_member_in_distinct_sessions_passes(self):
        other_session = EventSession.objects.create(
            name="Sessão Final 2026", kind="final", date=date(2026, 11, 15)
        )
        self._checkin()
        self._checkin(session=other_session)
        self.assertEqual(CheckIn.objects.count(), 2)

    def test_member_and_vehicle_in_same_session_passes(self):
        self._checkin()
        self._checkin(
            subject_type="vehicle",
            member=None,
            vehicle=self.vehicle,
        )
        self.assertEqual(CheckIn.objects.count(), 2)

    def test_uuid_is_auto_generated(self):
        checkin = self._checkin()
        self.assertIsInstance(checkin.uuid, uuid.UUID)

    def test_duplicate_uuid_raises(self):
        first = self._checkin()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._checkin(uuid=first.uuid)


class ConformityCheckTests(TestCase):
    def setUp(self):
        self.session = EventSession.objects.create(
            name="Sessão Validação 2026",
            kind="validation",
            date=date(2026, 10, 5),
        )
        self.team = Team.objects.create(
            name="Equipe Conformidade",
            course="Engenharia Mecânica",
            campus="Campus Centro",
        )
        self.vehicle = Vehicle.objects.create(team=self.team, name="Chassi B")
        self.staff = User.objects.create_user(username="staff.fiscal", password="x")

    def test_pass_with_items(self):
        checked = ConformityCheck.objects.create(
            vehicle=self.vehicle,
            session=self.session,
            staff=self.staff,
            result="pass",
            items={"dimensoes": True, "materiais": True},
        )
        self.assertEqual(checked.result, "pass")
        self.assertEqual(checked.items["dimensoes"], True)
        self.assertIsNotNone(checked.checked_at)

    def test_fail_with_notes(self):
        checked = ConformityCheck.objects.create(
            vehicle=self.vehicle,
            session=self.session,
            staff=self.staff,
            result="fail",
            items={"dimensoes": False},
            notes="Dimensão do chassi excede 60x30x30 cm.",
        )
        self.assertEqual(checked.result, "fail")
        self.assertEqual(checked.notes, "Dimensão do chassi excede 60x30x30 cm.")
