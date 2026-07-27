from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.logging_setup import get_logger

logger = get_logger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}:{h.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, hsh = stored_hash.split(":", 1)
        h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
        return h.hex() == hsh
    except (ValueError, AttributeError):
        return False


def create_access_token(subject: str) -> str:
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is not configured")

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expire_minutes
    )
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, object]:
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is not configured")
    try:
        return pyjwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except pyjwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


def verify_token(token: str) -> dict[str, object]:
    """Verify and decode a JWT token, raising PyJWTError on failure.

    Unlike decode_access_token(), this does NOT raise HTTPException,
    allowing callers (like WebSocket handlers) to handle errors directly.
    This is the appropriate choice for WebSocket auth where we can't use
    HTTP status codes.

    Args:
        token: JWT token string to verify

    Returns:
        Decoded token payload as dictionary

    Raises:
        RuntimeError: If JWT_SECRET is not configured
        jwt.ExpiredSignatureError: If token has expired
        jwt.PyJWTError: If token is invalid
    """
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is not configured")

    return pyjwt.decode(
        token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )
    payload = decode_access_token(credentials.credentials)
    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return subject


def authenticate_admin(username: str, password: str) -> bool:
    if username != settings.admin_username:
        return False
    if not settings.admin_password_hash:
        logger.warning("admin_password_hash not configured")
        return False
    return verify_password(password, settings.admin_password_hash)