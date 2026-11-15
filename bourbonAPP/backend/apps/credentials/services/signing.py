"""Criptografia pura do QR (Ed25519) — sem ORM, sem estado global mutável.

Formato do QR:

    MRP1.<b64u(canonical_json(payload))>.<b64u(assinatura_ed25519_64_bytes)>

O payload assinado é minimizado (LGPD): apenas ``v``, ``k``, ``ti``, ``iat`` e
``exp`` — nunca nome/e-mail/time.
"""

import base64
import binascii
import json
import os
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from django.conf import settings

QR_PREFIX = "MRP1."
QR_VERSION = 1

_B64U_ALPHABET = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"  # pragma: allowlist secret
)
_QR_MATCHER = re.compile(r"^MRP1\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")

_REASONS = frozenset(
    {"format", "signature", "unknown_token", "revoked", "expired", "kind_mismatch"}
)


class InvalidQrError(ValueError):
    """QR inválido; ``reason`` ∈ {format, signature, unknown_token, revoked, expired, kind_mismatch}."""

    def __init__(self, reason: str):
        if reason not in _REASONS:
            raise ValueError(f"reason inválida: {reason!r}")
        super().__init__(reason)
        self.reason = reason


class Ed25519KeyMissingError(RuntimeError):
    """Chave Ed25519 (privada ou pública) não encontrada no caminho configurado."""


def b64u_encode(data: bytes) -> str:
    """Base64url sem padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64u_decode(value: str) -> bytes:
    """Base64url sem padding → bytes; rejeita caracteres fora de [A-Za-z0-9_-]."""
    if (
        not isinstance(value, str)
        or not value
        or any(char not in _B64U_ALPHABET for char in value)
    ):
        raise InvalidQrError("format")
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (binascii.Error, ValueError):
        raise InvalidQrError("format") from None


def canonical_json(payload: dict) -> bytes:
    """JSON canônico (chaves ordenadas, sem espaços) — base da assinatura."""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def load_private_key(path):
    """Carrega a chave privada Ed25519 (PEM PKCS8); levanta se faltar."""
    path = os.fspath(path)
    if not os.path.exists(path):
        raise Ed25519KeyMissingError(f"Chave privada Ed25519 não encontrada em {path}")
    with open(path, "rb") as handle:
        key = serialization.load_pem_private_key(handle.read(), password=None)
    if not isinstance(key, ed25519.Ed25519PrivateKey):
        raise TypeError(f"{path} não contém uma chave privada Ed25519")
    return key


def load_public_key(path):
    """Carrega a chave pública Ed25519 (SubjectPublicKeyInfo); levanta se faltar."""
    path = os.fspath(path)
    if not os.path.exists(path):
        raise Ed25519KeyMissingError(f"Chave pública Ed25519 não encontrada em {path}")
    with open(path, "rb") as handle:
        key = serialization.load_pem_public_key(handle.read())
    if not isinstance(key, ed25519.Ed25519PublicKey):
        raise TypeError(f"{path} não contém uma chave pública Ed25519")
    return key


def sign_payload(payload: dict, *, key=None) -> tuple[bytes, str]:
    """Assina ``payload`` e devolve (assinatura bruta de 64B, b64u sem padding)."""
    if key is None:
        key = load_private_key(settings.ED25519_PRIVATE_PATH)
    raw = key.sign(canonical_json(payload))
    return raw, b64u_encode(raw)


def build_qr_text(payload: dict, signature_b64u: str) -> str:
    """Monta o texto do QR; a assinatura entra verbatim (nunca re-assina)."""
    return f"{QR_PREFIX}{b64u_encode(canonical_json(payload))}.{signature_b64u}"


def parse_qr_text(qr_text: str) -> tuple[dict, bytes]:
    """Valida o formato e devolve (payload, assinatura bruta)."""
    if not isinstance(qr_text, str) or not _QR_MATCHER.match(qr_text):
        raise InvalidQrError("format")
    _, payload_b64, signature_b64 = qr_text.split(".")
    try:
        payload = json.loads(b64u_decode(payload_b64))
    except (InvalidQrError, ValueError):
        raise InvalidQrError("format") from None
    if not isinstance(payload, dict):
        raise InvalidQrError("format")
    signature = b64u_decode(signature_b64)
    return payload, signature


def verify_signature(payload: dict, signature: bytes, *, pub=None) -> bool:
    """True se ``signature`` for Ed25519 válida sobre o JSON canônico de ``payload``."""
    if pub is None:
        pub = load_public_key(settings.ED25519_PUBLIC_PATH)
    try:
        pub.verify(signature, canonical_json(payload))
    except (InvalidSignature, ValueError):
        return False
    return True
