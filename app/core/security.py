"""
Security utilities for authentication and authorization
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
import bcrypt
from app.core.config import settings


# Password hashing context
# Use passlib for verification (handles different hash formats)
# Use bcrypt directly for hashing to avoid passlib's bug detection issues
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
    # Use bcrypt directly to avoid passlib's initialization bug detection issues
    # Convert password to bytes and truncate if necessary
    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    # Convert hashed_password back to bytes if it's a string
    if isinstance(hashed_password, str):
        hashed_password_bytes = hashed_password.encode('utf-8')
    else:
        hashed_password_bytes = hashed_password
    
    # Use bcrypt to verify
    try:
        return bcrypt.checkpw(password_bytes, hashed_password_bytes)
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
    # Convert to bytes and truncate to 72 bytes if necessary
    # Bcrypt requires bytes, not strings, and has a 72-byte limit
    password_bytes = password.encode('utf-8')
    
    if len(password_bytes) > 72:
        # Truncate to exactly 72 bytes
        password_bytes = password_bytes[:72]
    
    # Use bcrypt directly to avoid passlib's initialization bug detection issues
    # Generate salt and hash
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    
    # Return as string (bcrypt returns bytes)
    return hashed.decode('utf-8')


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
        print(f"DEBUG [decode_token]: Successfully decoded token. Payload: {payload}")
        return payload
    except JWTError as e:
        print(f"DEBUG [decode_token]: JWT decode error: {type(e).__name__}: {e}")
        print(f"DEBUG [decode_token]: Token (first 50 chars): {token[:50]}...")
        print(f"DEBUG [decode_token]: Using SECRET_KEY: {settings.SECRET_KEY[:20]}...")
        print(f"DEBUG [decode_token]: Using ALGORITHM: {settings.ALGORITHM}")
        return None
