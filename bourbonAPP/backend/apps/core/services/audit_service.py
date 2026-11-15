"""Trilha de auditoria (LGPD): escrita de AuditLog com IP hasheado.

Nenhuma função aqui aceita (nem escreve) dados pessoais em ``meta``. O IP do
requisitante vira SHA-256 com salt via ``hash_ip`` — a combinação
UUID+nome/e-mail nunca aparece em linha alguma de log.
"""

import hashlib

from django.conf import settings

from ..models import AuditLog

ACTION_STAFF_LOGIN = "auth.login_staff"
ACTION_TEAM_LOGIN = "auth.login_team"
ACTION_TEAM_REGISTER = "team.register"
ACTION_TEAM_EXPORT = "team.export"
ACTION_CONSENT_REVOKE = "team.consent_revoke"
ACTION_ISSUE_MEMBER = "credentials.issue_member"
ACTION_ISSUE_VEHICLE = "credentials.issue_vehicle"
ACTION_VERIFY_OK = "checkin.verify_ok"
ACTION_VERIFY_FAIL = "checkin.verify_fail"
ACTION_PRESENCE = "checkin.presence"
ACTION_CONFORMITY = "checkin.conformity"


def request_ip(request):
    """IP efetivo do requisitante: X-Forwarded-For (1ª parte) ou REMOTE_ADDR."""
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def hash_ip(request):
    """SHA-256 (ip + salt) ou None quando não há request/IP."""
    ip = request_ip(request)
    if not ip:
        return None
    return hashlib.sha256(f"{ip}|{settings.IP_HASH_SALT}".encode("utf-8")).hexdigest()


def write_audit(
    action,
    *,
    actor_user=None,
    actor_team=None,
    target_type=None,
    target_id=None,
    meta=None,
    request=None,
):
    """Registra uma linha de auditoria (sem PII em ``meta``)."""
    return AuditLog.objects.create(
        actor=actor_user,
        actor_team=actor_team,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        meta=meta or {},
        ip_hash=hash_ip(request),
    )
