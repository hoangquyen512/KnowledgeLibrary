from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _fernet_from_material(raw: str) -> Fernet:
    """Accept a Fernet key or any passphrase (derived via SHA-256)."""
    try:
        return Fernet(raw.encode("utf-8"))
    except Exception:
        digest = hashlib.sha256(raw.encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(digest))


def get_fernet() -> Fernet:
    key = settings.app_encryption_key
    if key:
        return _fernet_from_material(key)
    if settings.is_production:
        raise RuntimeError("APP_ENCRYPTION_KEY is required in production")
    ephemeral = os.environ.get("_DEV_EPHEMERAL_ENC_KEY")
    if not ephemeral:
        ephemeral = Fernet.generate_key().decode("utf-8")
        os.environ["_DEV_EPHEMERAL_ENC_KEY"] = ephemeral
    return Fernet(ephemeral.encode("utf-8"))


def encrypt_secret(plaintext: str) -> bytes:
    return get_fernet().encrypt(plaintext.encode("utf-8"))


def decrypt_secret(token: bytes) -> str:
    try:
        return get_fernet().decrypt(token).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt secret") from exc


def mask_secret(secret: str, visible: int = 4) -> str:
    if len(secret) <= visible:
        return "•" * max(len(secret), 1)
    return "•" * max(8, len(secret) - visible) + secret[-visible:]
