import os
import base64
import logging

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config.settings import settings

logger = logging.getLogger(__name__)


def _get_aesgcm() -> AESGCM:
    key = settings.ENCRYPTION_KEY.get_secret_value().strip()

    logger.info("ENCRYPTION_KEY length=%s", len(key))

    if not key:
        raise ValueError("ENCRYPTION_KEY is not configured")

    try:
        key_bytes = base64.b64decode(key)
    except Exception as exc:
        raise ValueError(
            "ENCRYPTION_KEY must be a Base64 encoded AES-256 key"
        ) from exc

    if len(key_bytes) != 32:
        raise ValueError(
            "ENCRYPTION_KEY must decode to exactly 32 bytes for AES-256"
        )

    return AESGCM(key_bytes)


def encrypt_email(email: str) -> str:
    if not email:
        raise ValueError("Email cannot be empty")

    aesgcm = _get_aesgcm()

    nonce = os.urandom(12)  # Recommended size for GCM
    ciphertext = aesgcm.encrypt(
        nonce,
        email.encode("utf-8"),
        None
    )

    encrypted = base64.urlsafe_b64encode(
        nonce + ciphertext
    ).decode("utf-8")

    return encrypted


def decrypt_email(encrypted_email: str) -> str:
    if not encrypted_email:
        raise ValueError("Encrypted email cannot be empty")

    try:
        data = base64.urlsafe_b64decode(
            encrypted_email.encode("utf-8")
        )

        nonce = data[:12]
        ciphertext = data[12:]

        aesgcm = _get_aesgcm()

        plaintext = aesgcm.decrypt(
            nonce,
            ciphertext,
            None
        )

        return plaintext.decode("utf-8")

    except Exception as exc:
        raise ValueError(
            "Invalid encrypted email or encryption key"
        ) from exc