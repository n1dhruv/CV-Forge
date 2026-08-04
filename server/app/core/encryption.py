from cryptography.fernet import Fernet

from app.core.config import get_settings


def _fernet() -> Fernet:
    key = get_settings().encryption_key.get_secret_value()
    return Fernet(key.encode())


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
