import uuid

from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
from django.test import TestCase, TransactionTestCase

from .models import Member, Team


def make_team(name="Equipe Teste"):
    return Team.objects.create(
        name=name, course="Engenharia Mecânica", campus="Campus Centro"
    )


def bulk_members(team, count, start=0, role="member"):
    """Cria membros via bulk_create de propósito: a validação 3–5/leader do
    ``Member.save()`` só faz sentido para salvamentos individuais."""
    return Member.objects.bulk_create(
        [
            Member(
                team=team,
                name=f"Membro {chr(65 + ((start + i) % 26))}{start + i}",
                email=f"membro.{start + i}@exemplo.test",
                ra=f"RA{start + i:06d}",
                role=role,
            )
            for i in range(count)
        ]
    )


class TeamSizeValidationTests(TestCase):
    def test_team_with_3_members_passes(self):
        team = make_team("Equipe Tres")
        bulk_members(team, 2)
        member = Member(
            team=team,
            name="Membro Terceiro",
            email="terceiro@exemplo.test",
            ra="RA000003",
        )
        member.save()
        self.assertEqual(team.members.count(), 3)
        self.assertIsNotNone(member.pk)

    def test_team_with_5_members_passes(self):
        team = make_team("Equipe Cinco")
        bulk_members(team, 4)
        member = Member(
            team=team, name="Membro Quinto", email="quinto@exemplo.test", ra="RA000005"
        )
        member.save()
        self.assertEqual(team.members.count(), 5)
        self.assertIsNotNone(member.pk)

    def test_team_with_2_members_rejected(self):
        team = make_team("Equipe Dois")
        bulk_members(team, 1)
        member = Member(
            team=team,
            name="Membro Segundo",
            email="segundo@exemplo.test",
            ra="RA000002",
        )
        with self.assertRaises(ValidationError):
            member.save()
        self.assertEqual(team.members.count(), 1)

    def test_team_with_6_members_rejected(self):
        team = make_team("Equipe Seis")
        bulk_members(team, 5)
        member = Member(
            team=team, name="Membro Sexto", email="sexto@exemplo.test", ra="RA000006"
        )
        with self.assertRaises(ValidationError):
            member.save()
        self.assertEqual(team.members.count(), 5)


class LeaderValidationTests(TestCase):
    def test_second_leader_via_save_rejected(self):
        team = make_team("Equipe Lider")
        bulk_members(team, 2, start=1)
        bulk_members(team, 1, start=0, role="leader")
        second_leader = Member(
            team=team,
            name="Membro Lider2",
            email="lider2@exemplo.test",
            ra="RA000050",
            role="leader",
        )
        with self.assertRaises(ValidationError):
            second_leader.save()
        self.assertEqual(team.members.filter(role="leader").count(), 1)


class LeaderConstraintTests(TransactionTestCase):
    def test_second_leader_via_bulk_create_raises_integrity_error(self):
        team = make_team("Equipe Constraint")
        bulk_members(team, 2, start=1)
        bulk_members(team, 1, start=0, role="leader")
        with self.assertRaises(IntegrityError), transaction.atomic():
            bulk_members(team, 1, start=30, role="leader")


class UniqueFieldTests(TransactionTestCase):
    def test_duplicate_team_name_raises_integrity_error(self):
        make_team("Equipe Unica")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Team.objects.create(
                name="Equipe Unica", course="Engenharia", campus="Campus 2"
            )

    def test_duplicate_email_raises_integrity_error(self):
        team_a = make_team("Equipe A")
        team_b = make_team("Equipe B")
        bulk_members(team_a, 1, start=10)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Member.objects.bulk_create(
                [
                    Member(
                        team=team_b,
                        name="Membro Duplicado",
                        email="membro.10@exemplo.test",
                        ra="RA999990",
                    )
                ]
            )

    def test_duplicate_ra_raises_integrity_error(self):
        team_a = make_team("Equipe C")
        team_b = make_team("Equipe D")
        bulk_members(team_a, 1, start=20)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Member.objects.bulk_create(
                [
                    Member(
                        team=team_b,
                        name="Membro Duplicado",
                        email="membro.21@exemplo.test",
                        ra="RA000020",
                    )
                ]
            )


class RegistrationCodeTests(TransactionTestCase):
    def test_registration_code_auto_generated_and_unique(self):
        first = make_team("Equipe Codigo 1")
        second = make_team("Equipe Codigo 2")
        self.assertIsInstance(first.registration_code, uuid.UUID)
        self.assertIsInstance(second.registration_code, uuid.UUID)
        self.assertNotEqual(first.registration_code, second.registration_code)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Team.objects.bulk_create(
                [
                    Team(
                        name="Equipe Codigo Duplicado",
                        course="Engenharia",
                        campus="Campus 3",
                        registration_code=first.registration_code,
                    )
                ]
            )
