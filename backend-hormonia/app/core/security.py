"""
Core security helpers for token generation/validation.

This lightweight module replaces the legacy auth helpers used by tests and
admin contracts. It focuses on password reset token creation so that the
API contracts can generate realistic JWT tokens during integration tests.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Optional
from uuid import uuid4

import jwt  # PyJWT - replaces python-jose to fix CVE-2024-23342

from app.config import settings
from app.utils.security import verify_password as _verify_password_util
from app.utils.timezone import now_sao_paulo

# Default expiration for password reset tokens
PASSWORD_RESET_TOKEN_EXPIRE_HOURS = getattr(settings, "AUTH_RESET_TOKEN_EXPIRE_HOURS", 24)
PASSWORD_RESET_TOKEN_TYPE = "password_reset"
PASSWORD_RESET_TOKEN_ISSUER = "backend-hormonia"
PASSWORD_RESET_TOKEN_AUDIENCE = "password-reset"


@dataclass(frozen=True, slots=True)
class PasswordResetTokenClaims:
    """Minimal validated password-reset claims needed by reset services."""

    sub: str
    jti: str
    exp: int


def _invalid_reset_token_error() -> Exception:
    from fastapi import HTTPException, status

    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired reset token",
    )


def _decode_password_reset_payload(
    token: str,
    *,
    secret_key: Optional[str] = None,
    algorithms: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Decode and validate shared password-reset JWT envelope claims."""
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
        if not isinstance(email, str) or not email.strip():
            raise ValueError("Missing subject")
        return payload
    except (jwt.exceptions.PyJWTError, ValueError) as exc:
        raise _invalid_reset_token_error() from exc


def _require_password_reset_claims(payload: dict[str, Any]) -> PasswordResetTokenClaims:
    """Extract reset-token replay claims without returning raw token material."""
    jti = payload.get("jti")
    if not isinstance(jti, str) or not jti.strip():
        raise _invalid_reset_token_error()

    try:
        exp = int(payload.get("exp"))
    except (TypeError, ValueError) as exc:
        raise _invalid_reset_token_error() from exc

    return PasswordResetTokenClaims(
        sub=payload["sub"].strip().lower(),
        jti=jti.strip(),
        exp=exp,
    )


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


def verify_password_reset_token_claims(
    token: str,
    *,
    secret_key: Optional[str] = None,
    algorithms: Optional[list[str]] = None,
) -> PasswordResetTokenClaims:
    """
    Validate password reset token and return replay-control claims.

    The returned data intentionally excludes the raw token and any reset URL.
    """
    payload = _decode_password_reset_payload(
        token,
        secret_key=secret_key,
        algorithms=algorithms,
    )
    return _require_password_reset_claims(payload)


def verify_password_reset_token(
    token: str,
    *,
    secret_key: Optional[str] = None,
    algorithms: Optional[list[str]] = None,
) -> str:
    """
    Validate password reset token and return embedded email.
    """
    payload = _decode_password_reset_payload(
        token,
        secret_key=secret_key,
        algorithms=algorithms,
    )
    return payload["sub"]


__all__ = [
    "create_password_reset_token",
    "verify_password_reset_token",
    "verify_password_reset_token_claims",
    "verify_password",
    "PasswordResetTokenClaims",
    "PASSWORD_RESET_TOKEN_EXPIRE_HOURS",
]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Proxy to existing password verification helper for backwards compatibility."""
    return _verify_password_util(plain_password, hashed_password)
