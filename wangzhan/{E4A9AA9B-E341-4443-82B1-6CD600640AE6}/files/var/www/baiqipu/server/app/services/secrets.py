from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


def _build_fernet() -> Fernet:
    settings = get_settings()
    seed = str(settings.SHOPEE_TOKEN_ENCRYPTION_KEY or settings.SECRET_KEY or "").strip()
    if not seed:
        raise ValueError("SECRET_KEY or SHOPEE_TOKEN_ENCRYPTION_KEY must be configured")
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_text(value: str | None) -> str | None:
    plaintext = str(value or "").strip()
    if not plaintext:
        return None
    return _build_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_text(value: str | None) -> str | None:
    ciphertext = str(value or "").strip()
    if not ciphertext:
        return None
    if not ciphertext.startswith("gAAAA"):
        return ciphertext
    try:
        return _build_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Stored token could not be decrypted") from exc
