"""
Core security helpers for token generation/validation.

This lightweight module replaces the legacy auth helpers used by tests and
admin contracts. It focuses on password reset token creation so that the
API contracts can generate realistic JWT tokens during integration tests.
"""

from datetime import datetime, timedelta
from typing import Optional

from jose import jwt

from app.config import settings

# Default expiration for password reset tokens (24 hours)
PASSWORD_RESET_TOKEN_EXPIRE_HOURS = 24


def create_password_reset_token(
    email: str,
    expires_delta: Optional[timedelta] = None,
    *,
    secret_key: Optional[str] = None,
    algorithm: str = "HS256",
) -> str:
    """
    Generate a signed JWT used for password reset flows.

    Args:
        email: User email to embed in the token.
        expires_delta: Optional custom expiration window.
        secret_key: Optional secret key (defaults to settings.SECRET_KEY).
        algorithm: JWT algorithm (defaults to HS256).

    Returns:
        Encoded JWT string.
    """
    expire = datetime.utcnow() + (
        expires_delta or timedelta(hours=PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
    )
    payload = {"sub": email, "exp": expire}
    return jwt.encode(payload, secret_key or settings.SECRET_KEY, algorithm=algorithm)


__all__ = ["create_password_reset_token", "PASSWORD_RESET_TOKEN_EXPIRE_HOURS"]
