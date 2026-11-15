"""Orquestração de tokens de QR: emissão, revogação e verificação (DB + crypto)."""

import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import QrToken
from . import signing

# subject_type do banco -> chave ``k`` do payload do QR.
SUBJECT_KEYS = {"member": "m", "vehicle": "v"}


def _validate_subject(subject_type, *, member=None, vehicle=None):
    """Garante exatamente 1 sujeito coerente com o tipo."""
    if subject_type not in SUBJECT_KEYS:
        raise ValueError(f"subject_type inválido: {subject_type!r}")
    if subject_type == "member":
        if member is None or vehicle is not None:
            raise ValueError("member exige exatamente 1 Member e nenhum Vehicle")
    else:
        if vehicle is None or member is not None:
            raise ValueError("vehicle exige exatamente 1 Vehicle e nenhum Member")
    return member, vehicle


def _active_qs(subject_type, *, member=None, vehicle=None):
    member, vehicle = _validate_subject(subject_type, member=member, vehicle=vehicle)
    return QrToken.objects.filter(
        subject_type=subject_type, member=member, vehicle=vehicle, status="active"
    )


def get_active_token(subject_type, *, member=None, vehicle=None):
    """Retorna o token ativo do sujeito, ou None."""
    return _active_qs(subject_type, member=member, vehicle=vehicle).first()


@transaction.atomic
def issue_token(subject_type, *, member=None, vehicle=None) -> QrToken:
    """Emite um novo token ativo; revoga o anterior do mesmo sujeito na mesma transação."""
    member, vehicle = _validate_subject(subject_type, member=member, vehicle=vehicle)
    _active_qs(subject_type, member=member, vehicle=vehicle).update(
        status="revoked", revoked_at=timezone.now()
    )
    now = timezone.now()
    payload = {
        "v": signing.QR_VERSION,
        "k": SUBJECT_KEYS[subject_type],
        "ti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.QR_TOKEN_TTL_DAYS)).timestamp()),
    }
    _, signature_b64u = signing.sign_payload(payload)
    return QrToken.objects.create(
        subject_type=subject_type,
        member=member,
        vehicle=vehicle,
        token_id=uuid.UUID(payload["ti"]),
        payload_json=payload,
        signature=signature_b64u,
        status="active",
        issued_at=now,
    )


def ensure_active_token(subject_type, *, member=None, vehicle=None) -> QrToken:
    """Devolve o token ativo e não expirado do sujeito, reemitindo se necessário.

    Um token ativo com ``exp`` no passado é reemitido via ``issue_token``
    (transação atômica: revoga o expirado e cria o novo). Na corrida de duas
    emissões concorrentes a constraint ``uniq_qr_active_per_subject`` faz a
    perdedora falhar; o IntegrityError é absorvido e a vencedora é devolvida.
    """
    token = get_active_token(subject_type, member=member, vehicle=vehicle)
    if token is None:
        try:
            return issue_token(subject_type, member=member, vehicle=vehicle)
        except IntegrityError:
            return get_active_token(subject_type, member=member, vehicle=vehicle)
    exp = token.payload_json.get("exp")
    if not isinstance(exp, int) or exp <= int(timezone.now().timestamp()):
        token = issue_token(subject_type, member=member, vehicle=vehicle)
    return token


def revoke_token(token: QrToken) -> QrToken:
    """Revoga um token individual (idempotente)."""
    if token.status == "active":
        token.status = "revoked"
        token.revoked_at = timezone.now()
        token.save(update_fields=["status", "revoked_at"])
    return token


def revoke_for_subject(subject_type, *, member=None, vehicle=None) -> int:
    """Revoga todos os ativos do sujeito; retorna quantos foram revogados."""
    return _active_qs(subject_type, member=member, vehicle=vehicle).update(
        status="revoked", revoked_at=timezone.now()
    )


def qr_text_for(token: QrToken) -> str:
    """Monta o texto do QR com a assinatura gravada VERBATIM (nunca re-assina)."""
    return signing.build_qr_text(token.payload_json, token.signature)


def verify_qr(qr_text: str) -> dict:
    """Valida assinatura/ti/status/exp e devolve o payload do QR (sem PII)."""
    payload, signature = signing.parse_qr_text(qr_text)
    if not signing.verify_signature(payload, signature):
        raise signing.InvalidQrError("signature")
    ti = payload.get("ti")
    if not isinstance(ti, str):
        raise signing.InvalidQrError("unknown_token")
    try:
        token = QrToken.objects.get(token_id=ti)
    except (QrToken.DoesNotExist, ValidationError):
        raise signing.InvalidQrError("unknown_token") from None
    if payload.get("k") != SUBJECT_KEYS[token.subject_type]:
        raise signing.InvalidQrError("kind_mismatch")
    if token.status != "active":
        raise signing.InvalidQrError("revoked")
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp <= int(timezone.now().timestamp()):
        raise signing.InvalidQrError("expired")
    if payload != token.payload_json:
        # Defesa em profundidade: assinatura válida, mas o payload difere do
        # que foi gravado para este token_id (integridade do registro).
        raise signing.InvalidQrError("signature")
    return payload


def resolve_subject(payload: dict) -> tuple[str, object, QrToken]:
    """Resolve o sujeito do payload: (subject_type, Member|Vehicle, QrToken).

    Lê o QrToken pelo ``ti`` (com select_related do time) e devolve a FK
    correspondente — nome/time só são resolvidos server-side (staff).
    """
    ti = payload.get("ti")
    if not isinstance(ti, str):
        raise signing.InvalidQrError("unknown_token")
    try:
        token = QrToken.objects.select_related("member__team", "vehicle__team").get(
            token_id=ti
        )
    except (QrToken.DoesNotExist, ValidationError):
        raise signing.InvalidQrError("unknown_token") from None
    subject = token.member if token.subject_type == "member" else token.vehicle
    if subject is None:
        raise signing.InvalidQrError("unknown_token")
    return token.subject_type, subject, token
