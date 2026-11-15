#!/usr/bin/env python3
"""Gera o par de chaves Ed25519 do QR/JWT em backend/secrets/.

Idempotente: NÃO sobrescreve a chave privada se ela já existir (use --force).
Standalone: depende apenas do pacote ``cryptography``, sem Django.

Saída:
    secrets/ed25519_private.pem  — PEM PKCS8 ("BEGIN PRIVATE KEY"), chmod 600  # pragma: allowlist secret
    secrets/ed25519_public.pem   — SubjectPublicKeyInfo, chmod 644
"""

import argparse
import base64
import hashlib
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

PRIVATE_NAME = "ed25519_private.pem"
PUBLIC_NAME = "ed25519_public.pem"
SECRETS_DIR = Path(__file__).resolve().parent.parent / "secrets"


def _write(path: Path, data: bytes, mode: int) -> None:
    path.write_bytes(data)
    os.chmod(path, mode)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="substitui o par existente mesmo se a chave privada já existir",
    )
    args = parser.parse_args()

    private_path = SECRETS_DIR / PRIVATE_NAME
    public_path = SECRETS_DIR / PUBLIC_NAME

    if private_path.exists() and not args.force:
        print(f"Chave privada já existe em {private_path}; nada a fazer (use --force).")
        return 0

    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    _write(
        private_path,
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        0o600,
    )
    _write(
        public_path,
        key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ),
        0o644,
    )
    raw_public = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    fingerprint = base64.b64encode(hashlib.sha256(raw_public).digest()).decode("ascii")
    print(f"Par Ed25519 gerado em {SECRETS_DIR}")
    print(f"Fingerprint (SHA-256 da raw public key, base64): {fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
