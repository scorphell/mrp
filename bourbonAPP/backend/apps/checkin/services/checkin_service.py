"""Serviços de check-in: verify (só auditoria), presença idempotente e conformidade."""

import uuid

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.services.audit_service import (
    ACTION_CONFORMITY,
    ACTION_PRESENCE,
    ACTION_VERIFY_FAIL,
    ACTION_VERIFY_OK,
    write_audit,
)
from apps.credentials.services import qr_service, signing
from apps.registry.models import EventSession

from ..models import CheckIn, ConformityCheck

# reason do InvalidQrError -> (HTTP status, código de resposta).
_QR_ERROR_MAP = {
    "format": (400, "qr_format"),
    "signature": (400, "qr_signature"),
    "kind_mismatch": (400, "qr_kind_mismatch"),
    "unknown_token": (404, "qr_unknown_token"),
    "revoked": (410, "qr_revoked"),
    "expired": (410, "qr_expired"),
}


class CheckinError(ValueError):
    """Erro de domínio do check-in; (status, code, detail) viram HTTP na API."""

    def __init__(self, status: int, code: str, detail: str):
        self.status = status
        self.code = code
        self.detail = detail
        super().__init__(detail)


def _open_session(session_id):
    try:
        return EventSession.objects.get(pk=session_id)
    except EventSession.DoesNotExist:
        raise CheckinError(404, "session_not_found", "Sessão não encontrada.") from None


def _verify_qr_or_raise(qr_text):
    try:
        return qr_service.verify_qr(qr_text)
    except signing.InvalidQrError as exc:
        status, code = _QR_ERROR_MAP[exc.reason]
        raise CheckinError(status, code, "QR inválido ou não reconhecido.") from None


def resolve_qr_for_session(qr_text, session_id):
    """Valida sessão aberta + QR e devolve (session, subject_type, subject, token).

    Usado pelo verify e pelo presence para aplicar exatamente as mesmas
    validações (sessão existente/aberta, QR assinado/válido, consentimento).
    """
    session = _open_session(session_id)
    if session.status != "open":
        raise CheckinError(409, "session_closed", "Sessão fechada.")
    payload = _verify_qr_or_raise(qr_text)
    subject_type, subject, token = qr_service.resolve_subject(payload)
    if subject_type == "member" and subject.consent_at is None:
        raise CheckinError(410, "consent_revoked", "Consentimento revogado.")
    return session, subject_type, subject, token


def verify_qr_text(qr_text, session_id, request) -> dict:
    """Confere o QR para o app leitor; NÃO grava check-in, só audit (verify_ok/fail).

    Retorna o payload de resposta com nome/time (sem e-mail/RA) para a
    conferência visual do fiscal.
    """
    try:
        session, subject_type, subject, token = resolve_qr_for_session(
            qr_text, session_id
        )
    except CheckinError as exc:
        if not exc.code.startswith("session_"):
            write_audit(
                ACTION_VERIFY_FAIL,
                actor_user=request.user,
                target_type=None,
                meta={"session_id": session_id, "reason": exc.code},
                request=request,
            )
        raise

    write_audit(
        ACTION_VERIFY_OK,
        actor_user=request.user,
        target_type="qr_token",
        target_id=token.token_id,
        meta={
            "session_id": session.pk,
            "subject_type": subject_type,
            "subject_id": subject.pk,
            "token_id": str(token.token_id),
        },
        request=request,
    )

    payload = {
        "valid": True,
        "subject_type": subject_type,
        "subject_id": subject.pk,
        "token_id": str(token.token_id),
    }
    if subject_type == "member":
        payload["member"] = {
            "name": subject.name,
            "team": subject.team.name,
            "role": subject.role,
        }
    else:
        payload["member"] = None
        payload["vehicle"] = {
            "name": subject.name,
            "team": subject.team.name,
            "conformity_status": subject.conformity_status,
        }
    return payload


def register_presence(session, subject_type, subject, staff, request):
    """Registra presença idempotente (um CheckIn por sujeito por sessão).

    Re-leitura atualiza ``last_seen_at`` mas NÃO sobrescreve staff nem uuid.
    """
    member = subject if subject_type == "member" else None
    vehicle = subject if subject_type == "vehicle" else None
    try:
        with transaction.atomic():
            checkin, created = CheckIn.objects.get_or_create(
                session=session,
                subject_type=subject_type,
                member=member,
                vehicle=vehicle,
                defaults={"staff": staff, "uuid": uuid.uuid4()},
            )
    except IntegrityError:
        # Corrida: outra requisição criou a linha primeiro.
        checkin = CheckIn.objects.get(
            session=session,
            subject_type=subject_type,
            member=member,
            vehicle=vehicle,
        )
        created = False
    if not created:
        checkin.save(update_fields=["last_seen_at"])

    write_audit(
        ACTION_PRESENCE,
        actor_user=staff,
        target_type="checkin",
        target_id=checkin.pk,
        meta={
            "session_id": session.pk,
            "duplicate": not created,
            "checkin_uuid": str(checkin.uuid),
        },
        request=request,
    )
    return checkin, created


@transaction.atomic
def register_conformity(*, qr_text, session_id, result, items, notes, staff, request):
    """Checklist manual de conformidade (QR do veículo) + status denormalizado.

    Cada scan gera uma nova linha de ConformityCheck; ``Vehicle.conformity_status``
    reflete o último resultado (pass/fail).
    """
    session = _open_session(session_id)
    if session.status != "open":
        raise CheckinError(409, "session_closed", "Sessão fechada.")
    payload = _verify_qr_or_raise(qr_text)
    subject_type, subject, _ = qr_service.resolve_subject(payload)
    if subject_type != "vehicle":
        raise CheckinError(
            400, "expected_vehicle_qr", "O QR informado não é de um veículo."
        )
    if result not in ("pass", "fail"):
        raise CheckinError(400, "invalid_result", "result deve ser 'pass' ou 'fail'.")
    if not isinstance(items, dict):
        raise CheckinError(
            400, "invalid_items", "items deve ser um objeto de checklist."
        )
    forbidden = sorted(set(items) - settings.CONFORMITY_ITEMS_WHITELIST)
    if forbidden:
        raise CheckinError(
            400,
            "invalid_items",
            f"Campos fora da whitelist: {', '.join(forbidden)}",
        )
    if result == "pass" and not items:
        raise CheckinError(
            400,
            "invalid_items",
            "items deve registrar ao menos 1 item do checklist para result='pass'.",
        )

    check = ConformityCheck.objects.create(
        vehicle=subject,
        session=session,
        staff=staff,
        result=result,
        items=items,
        notes=notes or "",
    )
    subject.conformity_status = result
    subject.conformity_checked_at = timezone.now()
    subject.save(
        update_fields=["conformity_status", "conformity_checked_at", "updated_at"]
    )

    write_audit(
        ACTION_CONFORMITY,
        actor_user=staff,
        target_type="vehicle",
        target_id=subject.pk,
        meta={"session_id": session.pk, "result": result},
        request=request,
    )
    return check
