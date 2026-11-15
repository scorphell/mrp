"""Helpers compartilhados da suíte de testes da API (M3)."""

import tempfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.test import override_settings


def make_keypair(directory) -> tuple[Path, Path, Ed25519PrivateKey]:
    """Gera um par Ed25519 fictício em ``directory`` (priv, pub, key)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    private_path = directory / "test_ed25519_private.pem"
    public_path = directory / "test_ed25519_public.pem"
    private_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return private_path, public_path, key


# Par de chaves fictício da suíte: criado uma vez por processo.
_PRIVATE_PATH, _PUBLIC_PATH, _KEY = make_keypair(tempfile.mkdtemp(prefix="api-tests-"))


def api_override_settings(**extra):
    """override_settings padrão da suíte: chaves fictícias + salt de teste."""
    defaults = {
        "ED25519_PRIVATE_PATH": _PRIVATE_PATH,
        "ED25519_PUBLIC_PATH": _PUBLIC_PATH,
        "IP_HASH_SALT": "test-salt",
    }
    defaults.update(extra)
    return override_settings(**defaults)
