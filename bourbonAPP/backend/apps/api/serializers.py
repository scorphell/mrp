"""Serializers de entrada da API (validação mínima; regra de negócio nos services)."""

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from apps.registry.models import EventSession, Member, Team, TeamAuth

from .exceptions import ApiError


def _registration_deadline():
    """Cutoff de inscrição: 24h (padrão de indústria) antes da próxima sessão.

    Usa a sessão mais próxima com data >= hoje; se não houver sessão futura
    (pré-cadastro/teste), não bloqueia. Retorna o deadline como datetime ou
    None quando o registro está aberto sem limite.
    """
    next_session = (
        EventSession.objects.filter(date__gte=timezone.localdate())
        .order_by("date")
        .first()
    )
    if next_session is None:
        return None
    session_start = timezone.make_aware(
        timezone.datetime.combine(next_session.date, timezone.datetime.min.time())
    )
    cutoff_hours = settings.REGISTRATION_CUTOFF_HOURS
    if cutoff_hours <= 0:
        return session_start
    return session_start - timezone.timedelta(hours=cutoff_hours)


class StaffLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class TeamLoginSerializer(serializers.Serializer):
    registration_code = serializers.UUIDField()
    password = serializers.CharField(write_only=True)


class MemberRegistrationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    ra = serializers.CharField(max_length=30)
    role = serializers.ChoiceField(choices=["leader", "member"])
    consent_version = serializers.IntegerField(min_value=1, max_value=32767)


class VehicleRegistrationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)


class TeamRegisterSerializer(serializers.Serializer):
    # Honeypot anti-bot: campo invisível no formulário do PWA. Bots que
    # preenchem campos ocultos enviam "website" preenchido e são rejeitados
    # em team_register_view; usuários reais enviam o campo vazio/omitido.
    website = serializers.CharField(required=False, default="", allow_blank=True)
    registration_code = serializers.UUIDField()
    password = serializers.CharField(write_only=True)
    members = MemberRegistrationSerializer(many=True)
    vehicle = VehicleRegistrationSerializer()

    def validate(self, attrs):
        team = Team.objects.filter(registration_code=attrs["registration_code"]).first()
        if team is None:
            raise ApiError(
                404,
                "registration_code_not_found",
                "Código de inscrição não encontrado.",
            )
        if team.status != "active":
            raise ApiError(409, "team_inactive", "Equipe inativa.")
        if (
            team.registered_at is not None
            or TeamAuth.objects.filter(team=team).exists()
        ):
            raise ApiError(409, "team_already_registered", "Equipe já registrada.")

        deadline = _registration_deadline()
        if deadline is not None and timezone.now() >= deadline:
            raise ApiError(
                403,
                "registration_closed",
                "Inscrições encerradas para esta edição.",
            )

        try:
            validate_password(attrs["password"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages}) from None

        members = attrs["members"]
        if not 3 <= len(members) <= 5:
            raise serializers.ValidationError(
                {"members": "A equipe deve ter entre 3 e 5 integrantes."}
            )
        if sum(1 for member in members if member["role"] == "leader") != 1:
            raise serializers.ValidationError(
                {"members": "A equipe deve ter exatamente 1 líder."}
            )

        emails = [member["email"] for member in members]
        ras = [member["ra"] for member in members]
        if Member.objects.filter(Q(email__in=emails) | Q(ra__in=ras)).exists():
            raise ApiError(
                400,
                "duplicate_member",
                "E-mail ou RA já cadastrado para outro participante.",
            )

        attrs["team"] = team
        return attrs


class CheckinRequestSerializer(serializers.Serializer):
    session_id = serializers.IntegerField()
    qr_text = serializers.CharField()


class ConformityRequestSerializer(serializers.Serializer):
    session_id = serializers.IntegerField()
    qr_text = serializers.CharField()
    result = serializers.CharField(required=False, default=None, allow_null=True)
    items = serializers.JSONField(required=False, default=None, allow_null=True)
    notes = serializers.CharField(required=False, default="", allow_blank=True)
