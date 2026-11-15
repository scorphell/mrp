"""Suíte de testes de apps.credentials — chaves sempre fictícias em tmp_path."""

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


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
