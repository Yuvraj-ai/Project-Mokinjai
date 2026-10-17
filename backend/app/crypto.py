"""Fernet encryption for provider secrets. Adapted from Looky's vision key helpers."""

from cryptography.fernet import Fernet

from app.config import get_settings


def encrypt_api_key(plaintext: str) -> bytes:
    return Fernet(_encryption_key()).encrypt(plaintext.encode())


def decrypt_api_key(ciphertext: bytes) -> str:
    return Fernet(_encryption_key()).decrypt(ciphertext).decode()


def _encryption_key() -> bytes:
    key = get_settings().LLM_ENCRYPTION_KEY
    if not key:
        raise RuntimeError("LLM_ENCRYPTION_KEY is not set")
    return key.encode()
