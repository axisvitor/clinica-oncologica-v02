"""
Core security helpers for token generation/validation.

This lightweight module replaces the legacy auth helpers used by tests and
admin contracts. It focuses on password reset token creation so that the
API contracts can generate realistic JWT tokens during integration tests.
"""

from datetime import timedelta
from typing import Optional
from uuid import uuid4

import jwt  # PyJWT - replaces python-jose to fix CVE-2024-23342

from app.config import settings
from app.utils.security import verify_password as _verify_password_util
from app.utils.timezone import now_sao_paulo

# Default expiration for password reset tokens (24 hours)
PASSWORD_RESET_TOKEN_EXPIRE_HOURS = 24
PASSWORD_RESET_TOKEN_TYPE = "password_reset"
PASSWORD_RESET_TOKEN_ISSUER = "backend-hormonia"
PASSWORD_RESET_TOKEN_AUDIENCE = "password-reset"


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
        secret_key: Optional secret key (defaults to settings.SECURITY_SECRET_KEY).
        algorithm: JWT algorithm (defaults to HS256).

    Returns:
        Encoded JWT string.
    """
    now = now_sao_paulo()
    expire = now_sao_paulo() + (
        expires_delta or timedelta(hours=PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
    )
    payload = {
        "sub": email,
        "exp": expire,
        "iat": now,
        "nbf": now,
        "type": PASSWORD_RESET_TOKEN_TYPE,
        "iss": PASSWORD_RESET_TOKEN_ISSUER,
        "aud": PASSWORD_RESET_TOKEN_AUDIENCE,
        "jti": str(uuid4()),
    }
    return jwt.encode(
        payload, secret_key or settings.SECURITY_SECRET_KEY, algorithm=algorithm
    )


def verify_password_reset_token(
    token: str,
    *,
    secret_key: Optional[str] = None,
    algorithms: Optional[list[str]] = None,
) -> str:
    """
    Validate password reset token and return embedded email.
    """
    try:
        payload = jwt.decode(
            token,
            secret_key or settings.SECURITY_SECRET_KEY,
            algorithms=algorithms or ["HS256"],
            audience=PASSWORD_RESET_TOKEN_AUDIENCE,
            issuer=PASSWORD_RESET_TOKEN_ISSUER,
        )
        if payload.get("type") != PASSWORD_RESET_TOKEN_TYPE:
            raise ValueError("Invalid token type")
        email = payload.get("sub")
        if not email:
            raise ValueError("Missing subject")
        return email
    except jwt.exceptions.PyJWTError as exc:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        ) from exc


__all__ = [
    "create_password_reset_token",
    "verify_password_reset_token",
    "verify_password",
    "PASSWORD_RESET_TOKEN_EXPIRE_HOURS",
]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Proxy to existing password verification helper for backwards compatibility."""
    return _verify_password_util(plain_password, hashed_password)
