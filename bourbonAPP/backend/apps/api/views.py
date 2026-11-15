"""Views da API REST (camada HTTP fina — sem regra de negócio aqui).

Cada view valida entrada (serializer), delega ao service de domínio e mapeia
erros de domínio para ``ApiError``. Autenticação/permissão via decorators DRF.
"""

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import check_password
from django.db import connection
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.checkin.services.checkin_service import (
    CheckinError,
    register_conformity,
    register_presence,
    resolve_qr_for_session,
    verify_qr_text,
)
from apps.core.services.audit_service import (
    ACTION_ISSUE_MEMBER,
    ACTION_ISSUE_VEHICLE,
    ACTION_STAFF_LOGIN,
    ACTION_TEAM_EXPORT,
    ACTION_TEAM_LOGIN,
    write_audit,
)
from apps.core.services.jwt_service import issue_staff_token, issue_team_token
from apps.credentials.services import qr_service, rendering
from apps.registry.models import EventSession, Member, Team, Vehicle
from apps.registry.services import portal_service

from .authentication import TeamPrincipal
from .exceptions import ApiError
from .permissions import IsStaff, IsTeam, IsTeamMember
from .throttling import throttle_scope
from .serializers import (
    CheckinRequestSerializer,
    ConformityRequestSerializer,
    StaffLoginSerializer,
    TeamLoginSerializer,
    TeamRegisterSerializer,
)

_PORTAL_ERROR_STATUS = {
    "registration_code_not_found": 404,
    "team_inactive": 409,
    "team_already_registered": 409,
    "duplicate_member": 400,
}

_PORTAL_ERROR_DETAIL = {
    "registration_code_not_found": "Código de inscrição não encontrado.",
    "team_inactive": "Equipe inativa.",
    "team_already_registered": "Equipe já registrada.",
    "duplicate_member": "E-mail ou RA já cadastrado para outro participante.",
}


@api_view(["GET"])
@permission_classes([AllowAny])
def health_view(request):
    """Healthcheck do PWA: DB + disponibilidade das chaves Ed25519."""
    from apps.credentials.services import signing

    checks = {"db": "ok", "signing": "ok"}
    try:
        connection.ensure_connection()
    except Exception:  # noqa: BLE001 — healthcheck reporta qualquer falha de sub-sistema
        checks["db"] = "error"
    try:
        signing.load_private_key(settings.ED25519_PRIVATE_PATH)
        signing.load_public_key(settings.ED25519_PUBLIC_PATH)
    except Exception:  # noqa: BLE001
        checks["signing"] = "error"
    if all(value == "ok" for value in checks.values()):
        return Response({"status": "ok", **checks})
    return Response(
        {"status": "degraded", **checks},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@throttle_scope("staff_login")
@api_view(["POST"])
@permission_classes([AllowAny])
def staff_login_view(request):
    serializer = StaffLoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = authenticate(
        username=serializer.validated_data["username"],
        password=serializer.validated_data["password"],
    )
    if user is None or not user.is_staff:
        # Equaliza o timing de resposta (mitiga enumeração de usernames de
        # staff), como o login de equipe faz no portal_service.
        check_password(serializer.validated_data["password"], portal_service.DUMMY_HASH)
        raise ApiError(401, "invalid_credentials", "Credenciais inválidas.")
    write_audit(
        ACTION_STAFF_LOGIN,
        actor_user=user,
        target_type="user",
        target_id=user.pk,
        request=request,
    )
    return Response(
        {
            "token": issue_staff_token(user),
            "token_type": "Bearer",
            "expires_in": settings.STAFF_JWT_TTL_HOURS * 3600,
            "staff": {"id": user.pk, "username": user.username},
        }
    )


@api_view(["GET"])
@permission_classes([IsStaff])
def session_list_view(request):
    queryset = EventSession.objects.all()
    status_param = request.query_params.get("status")
    if status_param:
        queryset = queryset.filter(status=status_param)
    data = [
        {
            "id": session.pk,
            "name": session.name,
            "kind": session.kind,
            "date": session.date,
            "status": session.status,
        }
        for session in queryset
    ]
    return Response(data)


@throttle_scope("register")
@api_view(["POST"])
@permission_classes([AllowAny])
def team_register_view(request):
    # Honeypot anti-bot: o formulário real do PWA nunca envia "website"
    # preenchido. Rejeita antes de validar/serializar para não gastar CPU/DB.
    if request.data.get("website"):
        raise ApiError(400, "bot_detected", "Requisição rejeitada.")
    serializer = TeamRegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        team, member_count = portal_service.register_team(
            registration_code=serializer.validated_data["registration_code"],
            password=serializer.validated_data["password"],
            members=serializer.validated_data["members"],
            vehicle=serializer.validated_data["vehicle"],
            request=request,
        )
    except portal_service.PortalError as exc:
        raise ApiError(
            _PORTAL_ERROR_STATUS[exc.code],
            exc.code,
            _PORTAL_ERROR_DETAIL[exc.code],
        ) from None
    return Response(
        {
            "detail": "equipe registrada",
            "team_id": team.pk,
            "team_name": team.name,
            "member_count": member_count,
        },
        status=status.HTTP_201_CREATED,
    )


@throttle_scope("team_login")
@api_view(["POST"])
@permission_classes([AllowAny])
def team_login_view(request):
    serializer = TeamLoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    team = portal_service.login_team(
        serializer.validated_data["registration_code"],
        serializer.validated_data["password"],
    )
    if team is None:
        raise ApiError(401, "invalid_credentials", "Credenciais inválidas.")
    write_audit(
        ACTION_TEAM_LOGIN,
        actor_team=team,
        target_type="team",
        target_id=team.pk,
        request=request,
    )
    return Response(
        {
            "token": issue_team_token(team),
            "token_type": "Bearer",
            "expires_in": settings.TEAM_JWT_TTL_HOURS * 3600,
            "team": {"id": team.pk, "name": team.name},
        }
    )


@api_view(["GET"])
@permission_classes([IsTeam])
def team_me_view(request):
    return Response(portal_service.team_payload(request.user.team))


@api_view(["GET"])
@permission_classes([IsTeam])
def team_export_view(request):
    team = request.user.team
    write_audit(
        ACTION_TEAM_EXPORT,
        actor_team=team,
        target_type="team",
        target_id=team.pk,
        request=request,
    )
    return Response(portal_service.export_team(team))


@api_view(["POST"])
@permission_classes([IsTeam])
def team_consent_revoke_view(request):
    revoked = portal_service.revoke_consent(request.user.team, request=request)
    return Response({"detail": "consentimento revogado", "revoked_qr_tokens": revoked})


@throttle_scope("credential_issue")
@api_view(["POST"])
@permission_classes([IsStaff | IsTeamMember])
def credential_issue_view(request, subject_type, pk):
    if subject_type not in ("member", "vehicle"):
        raise ApiError(404, "subject_not_found", "Sujeito não encontrado.")
    if subject_type == "member":
        subject = Member.objects.select_related("team").filter(pk=pk).first()
    else:
        subject = Vehicle.objects.select_related("team").filter(pk=pk).first()
    if subject is None:
        raise ApiError(404, "subject_not_found", "Sujeito não encontrado.")
    if subject_type == "member" and subject.consent_at is None:
        raise ApiError(
            409, "consent_required", "Consentimento do participante não registrado."
        )
    if subject.team.status != "active":
        raise ApiError(409, "team_inactive", "Equipe inativa.")

    member = subject if subject_type == "member" else None
    vehicle = subject if subject_type == "vehicle" else None
    token = qr_service.ensure_active_token(subject_type, member=member, vehicle=vehicle)
    qr_data = rendering.qr_png_data_uri(
        qr_service.qr_text_for(token), scale=settings.QR_PNG_SCALE
    )
    action = ACTION_ISSUE_MEMBER if subject_type == "member" else ACTION_ISSUE_VEHICLE
    if isinstance(request.user, TeamPrincipal):
        actor_user, actor_team = None, request.user.team
    else:
        actor_user, actor_team = request.user, None
    write_audit(
        action,
        actor_user=actor_user,
        actor_team=actor_team,
        target_type="qr_token",
        target_id=token.token_id,
        meta={"subject_id": subject.pk},
        request=request,
    )
    return Response(
        {
            "token_id": str(token.token_id),
            "subject_type": subject_type,
            "subject_id": subject.pk,
            "qr": qr_data,
            "issued_at": token.issued_at,
        }
    )


@api_view(["GET"])
@permission_classes([IsStaff | IsTeam])
def team_pdf_view(request, team_id):
    team = Team.objects.filter(pk=team_id).first()
    if team is None:
        raise ApiError(404, "team_not_found", "Equipe não encontrada.")
    if isinstance(request.user, TeamPrincipal) and request.user.team.pk != team.pk:
        raise ApiError(403, "permission_denied", "Você não tem acesso a esta equipe.")
    pdf = rendering.render_team_pdf(team)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="credenciais-team-{team_id}.pdf"'
    )
    return response


@throttle_scope("verify")
@api_view(["POST"])
@permission_classes([IsStaff])
def checkin_verify_view(request):
    serializer = CheckinRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        payload = verify_qr_text(
            serializer.validated_data["qr_text"],
            serializer.validated_data["session_id"],
            request,
        )
    except CheckinError as exc:
        raise ApiError(exc.status, exc.code, exc.detail) from None
    return Response(payload)


@throttle_scope("presence")
@api_view(["POST"])
@permission_classes([IsStaff])
def checkin_presence_view(request):
    serializer = CheckinRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        session, subject_type, subject, _ = resolve_qr_for_session(
            serializer.validated_data["qr_text"],
            serializer.validated_data["session_id"],
        )
    except CheckinError as exc:
        raise ApiError(exc.status, exc.code, exc.detail) from None
    checkin, created = register_presence(
        session, subject_type, subject, request.user, request
    )
    return Response(
        {
            "checkin_id": checkin.pk,
            "duplicate": not created,
            "subject_type": subject_type,
            "subject_id": subject.pk,
            "uuid": checkin.uuid,
            "last_seen_at": checkin.last_seen_at,
        }
    )


@throttle_scope("conformity")
@api_view(["POST"])
@permission_classes([IsStaff])
def checkin_conformity_view(request):
    serializer = ConformityRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        check = register_conformity(
            qr_text=serializer.validated_data["qr_text"],
            session_id=serializer.validated_data["session_id"],
            result=serializer.validated_data["result"],
            items=serializer.validated_data["items"],
            notes=serializer.validated_data["notes"],
            staff=request.user,
            request=request,
        )
    except CheckinError as exc:
        raise ApiError(exc.status, exc.code, exc.detail) from None
    return Response(
        {
            "check_id": check.pk,
            "vehicle_id": check.vehicle_id,
            "result": check.result,
            "conformity_status": check.vehicle.conformity_status,
            "checked_at": check.checked_at,
        },
        status=status.HTTP_201_CREATED,
    )
