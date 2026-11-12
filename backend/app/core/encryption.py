"""Credential encryption at rest using Fernet."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _derive_fernet_key(raw: str) -> bytes:
    """Derive a valid Fernet key from an arbitrary secret string."""
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def get_fernet() -> Fernet:
    return Fernet(_derive_fernet_key(settings.encryption_key))


def encrypt_value(plaintext: str) -> str:
    if not plaintext:
        return ""
    return get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_value(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt credential — encryption key may have changed") from exc


def mask_secret(value: str, visible: int = 4) -> str:
    """Return a masked representation safe for API responses."""
    if not value:
        return ""
    if len(value) <= visible:
        return "*" * len(value)
    return f"{'*' * (len(value) - visible)}{value[-visible:]}"