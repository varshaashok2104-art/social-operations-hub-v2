from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Any
import jwt
from app.core.config import settings


def get_password_hash(password: str) -> str:
    """
    Securely hashes a password using memory-hard scrypt KDF.
    Format: scrypt$n$r$p$salt_hex$hash_hex
    """
    salt = secrets.token_bytes(16)
    n, r, p = 16384, 8, 1
    key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p)
    return f"scrypt${n}${r}${p}${salt.hex()}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain password against a stored scrypt hash using constant-time comparison.
    """
    try:
        parts = hashed_password.split("$")
        if len(parts) != 6 or parts[0] != "scrypt":
            return False
        n = int(parts[1])
        r = int(parts[2])
        p = int(parts[3])
        salt = bytes.fromhex(parts[4])
        stored_key = bytes.fromhex(parts[5])

        computed_key = hashlib.scrypt(plain_password.encode("utf-8"), salt=salt, n=n, r=r, p=p)
        return secrets.compare_digest(computed_key, stored_key)
    except Exception:
        return False


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    """
    Creates a signed JWT access token.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any] | None:
    """
    Decodes and validates a JWT access token. Returns payload dict or None if invalid/expired.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None
