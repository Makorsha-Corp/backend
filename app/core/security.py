"""
Security utilities for authentication and authorization
"""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from jose import JWTError, jwt
import bcrypt
from app.core.config import settings


# Length (in url-safe base64 characters) of the raw refresh token returned to
# clients. 64 bytes of entropy ≈ 86 characters; ample for a non-JWT credential.
REFRESH_TOKEN_BYTES = 64


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token

    Args:
        data: Data to encode in the token
        expires_delta: Optional expiration time delta

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password using bcrypt directly

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password

    Returns:
        True if password matches, False otherwise
    """
    if not hashed_password:
        return False

    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > 72:
        raise ValueError("Password exceeds bcrypt's 72-byte limit")

    hashed_bytes = hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
    try:
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt directly (bypasses passlib's bug detection)

    Args:
        password: Plain text password

    Returns:
        Hashed password

    Note:
        Bcrypt has a 72-byte limit. Passwords longer than 72 bytes
        will be truncated. Consider validating password length in
        your schemas to prevent this.
    """
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        raise ValueError("Password exceeds bcrypt's 72-byte limit")

    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')


def create_refresh_token() -> Tuple[str, str]:
    """Generate a refresh token pair (raw value, sha256 hex digest).

    The raw token is the credential returned to the client and is never
    persisted server-side. The hash is what gets stored in `refresh_tokens`
    and used for lookups.

    Returns:
        Tuple of (raw_token, token_hash). Always send the raw value to the
        client; always persist the hash.
    """
    raw = secrets.token_urlsafe(REFRESH_TOKEN_BYTES)
    token_hash = hash_refresh_token(raw)
    return raw, token_hash


def hash_refresh_token(raw: str) -> str:
    """Compute the sha256 hex digest used to look up a refresh token row.

    Uses a plain sha256 (not bcrypt) because:
    - The input has high entropy (`secrets.token_urlsafe(64)`), so we don't
      need a slow hash to defend against brute-force.
    - We need to look it up cheaply on every refresh; bcrypt would force a
      table scan.
    """
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify JWT token

    Args:
        token: JWT token to decode

    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
