"""JWT stateless Ed25519 (PyJWT) para autenticação de staff e equipes.

Usa a MESMA chave Ed25519 do QR (via ``apps.credentials.services.signing``):
zero biblioteca extra, e os mesmos pares de chave servem prod e LAN.

Claims:
    team  -> {"typ": "team",  "tid": <Team.pk>, "iat", "exp", "jti"}
    staff -> {"typ": "staff", "uid": <User.pk>, "iat", "exp", "jti"}

``jti`` é um UUID4 por emissão. TTL por settings STAFF/JWT_TTL_HOURS
(default 12h).
"""

import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.utils import timezone

from apps.credentials.services import signing

_JWT_CODES = frozenset({"invalid", "expired", "unsupported_type"})


class JwtError(ValueError):
    """Erro de JWT; ``code`` ∈ {invalid, expired, unsupported_type}."""

    def __init__(self, code: str):
        if code not in _JWT_CODES:
            raise ValueError(f"code inválida: {code!r}")
        super().__init__(code)
        self.code = code


def _encode(claims: dict, ttl_hours: int) -> str:
    now = timezone.now()
    payload = {
        **claims,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=ttl_hours)).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    key = signing.load_private_key(settings.ED25519_PRIVATE_PATH)
    return jwt.encode(payload, key, algorithm="EdDSA")


def issue_team_token(team) -> str:
    """JWT de equipe (12h): identifica o time dono nas rotas do portal."""
    return _encode({"typ": "team", "tid": team.pk}, settings.TEAM_JWT_TTL_HOURS)


def issue_staff_token(user) -> str:
    """JWT de staff (12h): identifica o usuário Django (is_staff)."""
    return _encode({"typ": "staff", "uid": user.pk}, settings.STAFF_JWT_TTL_HOURS)


def decode_token(token: str) -> dict:
    """Valida assinatura/exp/iat e devolve as claims (typ ∈ {team, staff})."""
    try:
        payload = jwt.decode(
            token,
            signing.load_public_key(settings.ED25519_PUBLIC_PATH),
            algorithms=["EdDSA"],
            options={"require": ["exp", "iat"]},
        )
    except jwt.ExpiredSignatureError:
        raise JwtError("expired") from None
    except jwt.MissingRequiredClaimError:
        raise JwtError("invalid") from None
    except jwt.InvalidTokenError:
        raise JwtError("invalid") from None
    if payload.get("typ") not in ("team", "staff"):
        raise JwtError("unsupported_type")
    return payload
