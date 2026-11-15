#!/usr/bin/env python3
"""Seed de dados demo (M5): 30 equipes fictícias + sessão de validação.

Uso:
    python scripts/seed_demo.py [--clear] [--count N]

Também executável pelo shell do Django:
    python manage.py shell -c "from scripts.seed_demo import main; main()"

Gera somente dados fictícios: nomes brasileiros comuns com inicial de
sobrenome, e-mails @mousetrap.local e RAs derivados — nunca dados reais.
"""

import argparse
import os
import re
import sys
import unicodedata
from pathlib import Path

import django
from django.apps import apps as django_apps
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils import timezone

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
if not django_apps.ready:
    django.setup()

from apps.checkin.models import CheckIn, ConformityCheck  # noqa: E402
from apps.registry.models import EventSession, Member, Team, TeamAuth, Vehicle  # noqa: E402

SESSION_NAME = "Validação Final"
SESSION_KIND = "validation"
TEAM_PASSWORD = "mousetrap2026"  # pragma: allowlist secret
CAMPUS = "Campus Central"
COURSES = ["Engenharia", "Ciência da Computação", "Design"]
FIRST_NAMES = [
    "Ana",
    "Bruno",
    "Camila",
    "Carlos",
    "Davi",
    "Eduarda",
    "Felipe",
    "Gabriela",
    "Heitor",
    "Isabela",
    "João",
    "Júlia",
    "Kaio",
    "Larissa",
    "Lucas",
    "Maria",
    "Matheus",
    "Nicolas",
    "Paula",
    "Pedro",
    "Rafael",
    "Sofia",
    "Thiago",
    "Valentina",
    "Vitor",
    "Yasmin",
]


def _slugify(name: str) -> str:
    """Normaliza um nome para ASCII minúsculo com separador de ponto."""
    ascii_text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", ".", ascii_text.lower()).strip(".")


def _clear_data() -> None:
    """Remove dados demo anteriores na ordem de dependência de FK."""
    ConformityCheck.objects.all().delete()
    CheckIn.objects.all().delete()
    Team.objects.all().delete()  # cascata: TeamAuth, Member, Vehicle, QrToken
    EventSession.objects.all().delete()


def _seed_session() -> EventSession:
    """Sessão 'Validação Final' do dia de hoje, aberta (idempotente)."""
    today = timezone.localdate()
    session, created = EventSession.objects.get_or_create(
        name=SESSION_NAME,
        kind=SESSION_KIND,
        date=today,
        defaults={"status": "open"},
    )
    if not created and session.status != "open":
        session.status = "open"
        session.save(update_fields=["status", "updated_at"])
    return session


def _seed_team(team_idx: int):
    """Cria uma equipe fictícia: time + auth + 3–5 membros + chassi."""
    number = team_idx + 1
    now = timezone.now()
    team = Team.objects.create(
        name=f"Rato {number:03d}",
        course=COURSES[team_idx % len(COURSES)],
        campus=CAMPUS,
        registered_at=now,
    )
    TeamAuth.objects.create(team=team, password_hash=make_password(TEAM_PASSWORD))

    member_count = 3 + (team_idx % 3)  # 3–5 membros, determinístico
    members = []
    for k in range(member_count):
        member_idx = k + 1
        initial = chr(65 + (team_idx + k) % 26)
        name = f"{FIRST_NAMES[(team_idx + k) % len(FIRST_NAMES)]} {initial}."
        members.append(
            Member(
                team=team,
                name=name,
                email=f"{_slugify(name)}.{number:02d}@mousetrap.local",
                ra=f"{number:02d}{member_idx:02d}",
                role="leader" if member_idx == 1 else "member",
                consent_at=now,
                consent_version=1,
            )
        )
    # bulk_create de propósito: a validação 3–5/leader do Member.save() só faz
    # sentido para salvamentos individuais (mesmo padrão do portal).
    Member.objects.bulk_create(members)

    vehicle = Vehicle.objects.create(team=team, name=f"Chassi Rato {number:03d}")
    return team, members, vehicle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="seed_demo",
        description="Seed de dados demo (M5): equipes, membros, veículos e sessão.",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="apaga dados demo anteriores antes de popular",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=30,
        help="número de equipes a criar (default: 30)",
    )
    args = parser.parse_args(argv if argv is not None else [])
    if args.count < 1:
        parser.error("--count precisa ser >= 1")

    with transaction.atomic():
        if args.clear:
            _clear_data()
        session = _seed_session()
        teams = []
        for idx in range(args.count):
            team, _, _ = _seed_team(idx)
            teams.append(team)

    member_total = Member.objects.filter(team__in=teams).count()
    print(
        f"Seed concluído: {len(teams)} equipes, {member_total} membros, "
        f"{Vehicle.objects.filter(team__in=teams).count()} veículos."
    )
    print(
        f"Sessão: {session.name} "
        f"({session.kind}, {session.status}, {session.date.isoformat()})"
    )
    print(f"Senha das equipes: {TEAM_PASSWORD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
