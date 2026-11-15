"""Testes do seed demo (M5): criação idempotente de equipes fictícias."""

from django.contrib.auth.hashers import check_password
from django.test import TestCase

from apps.registry.models import EventSession, Member, Team, TeamAuth, Vehicle
from scripts.seed_demo import SESSION_NAME, TEAM_PASSWORD, main


class SeedDemoTests(TestCase):
    def test_seed_creates_teams_members_vehicles(self):
        self.assertEqual(main(["--count", "3"]), 0)

        self.assertEqual(Team.objects.count(), 3)
        self.assertEqual(TeamAuth.objects.count(), 3)
        self.assertEqual(Vehicle.objects.count(), 3)
        # 3 equipes criam 3, 4 e 5 membros (3 + idx % 3).
        self.assertEqual(Member.objects.count(), 12)

        session = EventSession.objects.get(name=SESSION_NAME, kind="validation")
        self.assertEqual(session.status, "open")
        self.assertIsNotNone(session.date)

    def test_each_team_has_single_leader_and_3_to_5_members(self):
        main(["--count", "5"])

        for team in Team.objects.all():
            self.assertEqual(team.members.filter(role="leader").count(), 1)
            self.assertGreaterEqual(team.members.count(), 3)
            self.assertLessEqual(team.members.count(), 5)

    def test_auth_password_and_consent(self):
        main(["--count", "2"])

        for team in Team.objects.all():
            self.assertTrue(check_password(TEAM_PASSWORD, team.auth.password_hash))
            for member in team.members.all():
                self.assertIsNotNone(member.consent_at)
                self.assertEqual(member.consent_version, 1)

    def test_clear_is_idempotent(self):
        main(["--count", "4"])
        main(["--clear", "--count", "4"])

        self.assertEqual(Team.objects.count(), 4)
        self.assertEqual(EventSession.objects.count(), 1)

    def test_emails_and_ras_are_unique(self):
        main(["--count", "6"])

        emails = list(Member.objects.values_list("email", flat=True))
        ras = list(Member.objects.values_list("ra", flat=True))
        self.assertEqual(len(emails), len(set(emails)))
        self.assertEqual(len(ras), len(set(ras)))
