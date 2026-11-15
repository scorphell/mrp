"""Portal de equipes: registro, login, payload e rotas LGPD (export/revoke)."""

from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.checkin.models import CheckIn
from apps.core.services.audit_service import (
    ACTION_CONSENT_REVOKE,
    ACTION_TEAM_REGISTER,
    write_audit,
)
from apps.credentials.models import QrToken
from apps.credentials.services import qr_service

from ..models import Member, Team, TeamAuth, Vehicle

# Hash PBKDF2 fixo (senha dummy) p/ equalizar o timing de login quando o código
# de inscrição não existe ou a equipe ainda não tem credencial (mitiga envio
# de consultas de existência por diferença de tempo de resposta).
DUMMY_HASH = (
    "pbkdf2_sha256$1000000$m3dummy$z1zDsW6VytG+PpDY5JzTzkq6lX2ilHvrgGV4S7hOfuY="
)


class PortalError(ValueError):
    """Erro de domínio do portal; ``code`` é mapeado para HTTP na camada API."""

    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail or code
        super().__init__(self.detail)


@transaction.atomic
def register_team(registration_code, password, members, vehicle, request=None):
    """Registra a equipe: referência→senha→membros→veículo→auditoria.

    Espera ``members`` (list[dict]) e ``vehicle`` (dict) já validados pelo
    serializer da camada API; aqui são persistidos com ``consent_at`` e
    ``registered_at`` sempre definidos server-side.
    """
    team = (
        Team.objects.select_for_update()
        .filter(registration_code=registration_code)
        .first()
    )
    if team is None:
        raise PortalError("registration_code_not_found")
    if team.status != "active":
        raise PortalError("team_inactive")
    if team.registered_at is not None or TeamAuth.objects.filter(team=team).exists():
        raise PortalError("team_already_registered")

    now = timezone.now()
    try:
        TeamAuth.objects.create(team=team, password_hash=make_password(password))
        Member.objects.bulk_create(
            [
                Member(
                    team=team,
                    name=item["name"],
                    email=item["email"],
                    ra=item["ra"],
                    role=item["role"],
                    consent_at=now,
                    consent_version=item["consent_version"],
                )
                for item in members
            ]
        )
        Vehicle.objects.create(team=team, name=vehicle["name"])
        team.registered_at = now
        team.save(update_fields=["registered_at", "updated_at"])
    except IntegrityError:
        raise PortalError(
            "duplicate_member",
            "E-mail ou RA já cadastrado para outro participante.",
        ) from None

    write_audit(
        ACTION_TEAM_REGISTER,
        actor_team=team,
        target_type="team",
        target_id=team.pk,
        meta={"member_count": len(members)},
        request=request,
    )
    return team, len(members)


def login_team(registration_code, password):
    """Valida credenciais do portal; devolve a equipe ou None (401 genérico)."""
    team = Team.objects.filter(registration_code=registration_code).first()
    auth = getattr(team, "auth", None) if team is not None else None

    if auth is None:
        check_password(password, DUMMY_HASH)
        return None
    if team.status != "active":
        check_password(password, auth.password_hash)
        return None
    if not check_password(password, auth.password_hash):
        return None
    return team


def team_payload(team):
    """Dados da própria equipe (portal): inclui e-mail/RA (auto-serviço)."""
    members = [
        {
            "id": member.pk,
            "name": member.name,
            "email": member.email,
            "ra": member.ra,
            "role": member.role,
            "consent_at": member.consent_at,
            "consent_version": member.consent_version,
        }
        for member in team.members.all().order_by("role", "name")
    ]
    vehicle = getattr(team, "vehicle", None)
    return {
        "team": {
            "id": team.pk,
            "name": team.name,
            "course": team.course,
            "campus": team.campus,
            "status": team.status,
            "registered_at": team.registered_at,
            "members": members,
            "vehicle": ({"id": vehicle.pk, "name": vehicle.name} if vehicle else None),
        }
    }


def export_team(team):
    """Exportação LGPD (Art. 18, II): dados do titular + check-ins + QRs.

    Não exporta AuditLog (logs raspados não são restituíveis por design).
    """
    vehicle = getattr(team, "vehicle", None)
    members = team.members.all().order_by("role", "name")
    checkins = CheckIn.objects.filter(
        Q(member__team=team) | Q(vehicle__team=team)
    ).order_by("last_seen_at")
    qr_tokens = QrToken.objects.filter(
        Q(member__team=team) | Q(vehicle__team=team)
    ).order_by("issued_at")

    return {
        "exported_at": timezone.now(),
        "team": {
            "id": team.pk,
            "name": team.name,
            "course": team.course,
            "campus": team.campus,
            "status": team.status,
            "registered_at": team.registered_at,
        },
        "members": [
            {
                "id": member.pk,
                "name": member.name,
                "email": member.email,
                "ra": member.ra,
                "role": member.role,
                "consent_at": member.consent_at,
                "consent_version": member.consent_version,
                "created_at": member.created_at,
            }
            for member in members
        ],
        "vehicle": (
            {
                "id": vehicle.pk,
                "name": vehicle.name,
                "conformity_status": vehicle.conformity_status,
            }
            if vehicle
            else None
        ),
        "checkins": [
            {
                "session_id": checkin.session_id,
                "subject_type": checkin.subject_type,
                "subject_id": checkin.member_id or checkin.vehicle_id,
                "last_seen_at": checkin.last_seen_at,
                "uuid": checkin.uuid,
            }
            for checkin in checkins
        ],
        "qr_tokens": [
            {
                "subject_type": token.subject_type,
                "subject_id": token.member_id or token.vehicle_id,
                "token_id": token.token_id,
                "status": token.status,
                "issued_at": token.issued_at,
                "revoked_at": token.revoked_at,
            }
            for token in qr_tokens
        ],
    }


@transaction.atomic
def revoke_consent(team, request=None):
    """Revoga o consentimento: anonimiza membros, revoga QRs e inativa o time.

    Idempotente: a 2ª chamada não encontra tokens ativos e devolve 0.
    """
    revoked = 0
    for member in team.members.all():
        member.name = "[apagado]"
        member.email = f"apagado.{member.pk}@mousetrap.local"
        member.ra = f"APAGADO-{member.pk}"
        member.consent_at = None
        member.consent_version = None
        member.save(
            update_fields=[
                "name",
                "email",
                "ra",
                "consent_at",
                "consent_version",
                "updated_at",
            ]
        )
        revoked += qr_service.revoke_for_subject("member", member=member)
    vehicle = getattr(team, "vehicle", None)
    if vehicle is not None:
        revoked += qr_service.revoke_for_subject("vehicle", vehicle=vehicle)

    team.status = "inactive"
    team.save(update_fields=["status", "updated_at"])

    write_audit(
        ACTION_CONSENT_REVOKE,
        actor_team=team,
        target_type="team",
        target_id=team.pk,
        meta={"revoked_tokens": revoked},
        request=request,
    )
    return revoked
