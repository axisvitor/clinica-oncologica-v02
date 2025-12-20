"""
CSRF Protection Middleware - Simplified Implementation

Stateless Double Submit Cookie pattern using HMAC-SHA256.
Native Python implementation with no external dependencies.

Security:
- HMAC-SHA256 for token signing
- Hexadecimal encoding (auditable, no padding issues)
- Constant-time comparison (prevents timing attacks)
- httpOnly, Secure, SameSite cookie flags

Usage:
    from app.middleware.csrf import CSRFMiddleware, get_csrf_token, set_csrf_cookie

    # Add middleware
    app.add_middleware(CSRFMiddleware)

    # Token endpoint
    @router.get("/csrf-token")
    def csrf_token(request: Request, response: Response):
        token = get_csrf_token()
        set_csrf_cookie(response, token)
        return {"csrf_token": token}
"""

import hmac
import hashlib
import secrets
import time
import logging
from typing import Optional
from fastapi import Request
from fastapi.responses import Response, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

# Paths exempt from CSRF protection
EXEMPT_PATHS = frozenset({
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/csrf-token",
    "/api/v2/auth/csrf-token",
    "/api/v2/auth/login",
    "/api/v2/auth/register",
    "/api/v2/auth/refresh",
    "/webhooks/",
    "/api/public/",
    "/api/v2/quiz-extensions/monthly/public",
    "/api/v2/monthly-quiz-public",
})

# Safe HTTP methods (no state changes)
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Token configuration
TOKEN_EXPIRY = 3600  # 1 hour
COOKIE_NAME = "csrf_token"


def _get_secret_key() -> str:
    """Get CSRF secret key from settings."""
    from app.config import settings

    secret = getattr(settings, "SECURITY_CSRF_SECRET_KEY", None)
    if secret and hasattr(secret, "get_secret_value"):
        secret = secret.get_secret_value()

    if not secret or len(str(secret)) < 32:
        raise ValueError(
            "SECURITY_CSRF_SECRET_KEY must be at least 32 characters. "
            "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )

    return str(secret)


def _is_production() -> bool:
    """Check if running in production."""
    from app.config import settings
    return str(getattr(settings, "APP_ENVIRONMENT", "development")).lower() == "production"


# ============================================================================
# Token Generation and Validation
# ============================================================================

def generate_csrf_token(secret_key: Optional[str] = None) -> str:
    """
    Generate a signed CSRF token.

    Format: {timestamp}.{random_hex}.{hmac_signature}
    """
    if secret_key is None:
        secret_key = _get_secret_key()

    timestamp = str(int(time.time()))
    random_data = secrets.token_hex(32)
    payload = f"{timestamp}.{random_data}"

    signature = hmac.new(
        secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return f"{payload}.{signature}"


def validate_csrf_token(token: str, secret_key: Optional[str] = None) -> bool:
    """
    Validate a CSRF token's format, signature, and expiration.

    Uses constant-time comparison to prevent timing attacks.
    """
    if secret_key is None:
        secret_key = _get_secret_key()

    try:
        parts = token.split(".")
        if len(parts) != 3:
            return False

        timestamp_str, random_data, signature = parts

        # Verify signature (constant-time)
        payload = f"{timestamp_str}.{random_data}"
        expected = hmac.new(
            secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected):
            return False

        # Check expiration
        timestamp = int(timestamp_str)
        age = int(time.time()) - timestamp

        if age > TOKEN_EXPIRY or age < -60:  # 60s clock skew allowed
            return False

        return True

    except (ValueError, IndexError):
        return False


# ============================================================================
# Public API
# ============================================================================

def get_csrf_token() -> str:
    """Generate a new CSRF token."""
    return generate_csrf_token()


def set_csrf_cookie(response: Response, token: str) -> None:
    """Set CSRF token as a cookie."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=TOKEN_EXPIRY,
        path="/",
        secure=_is_production(),
        httponly=True,
        samesite="strict",
    )


def is_csrf_exempt(path: str, method: str) -> bool:
    """Check if request is exempt from CSRF protection."""
    if method in SAFE_METHODS:
        return True

    if path in EXEMPT_PATHS:
        return True

    for exempt in EXEMPT_PATHS:
        if path.startswith(exempt):
            return True

    if path.startswith("/static/") or path.startswith("/uploads/"):
        return True

    return False


# ============================================================================
# Middleware
# ============================================================================

class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection middleware using Double Submit Cookie pattern.

    Validates that:
    1. X-CSRF-Token header is present
    2. Token signature is valid
    3. Token is not expired
    4. Header token matches cookie token
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        logger.info("CSRF middleware initialized")

    async def dispatch(self, request: Request, call_next):
        # Skip exempt paths/methods
        if is_csrf_exempt(request.url.path, request.method):
            return await call_next(request)

        # Get token from header
        header_token = (
            request.headers.get("X-CSRF-Token") or
            request.headers.get("X-CSRFToken") or
            request.headers.get("X-XSRF-Token")
        )

        if not header_token:
            logger.warning(f"CSRF token missing: {request.method} {request.url.path}")
            return JSONResponse(
                status_code=403,
                content={"error": "csrf_token_missing", "message": "CSRF token required"}
            )

        # Validate header token
        if not validate_csrf_token(header_token):
            logger.warning(f"CSRF token invalid: {request.method} {request.url.path}")
            return JSONResponse(
                status_code=403,
                content={"error": "csrf_token_invalid", "message": "CSRF token invalid or expired"}
            )

        # Get cookie token
        cookie_token = request.cookies.get(COOKIE_NAME)

        if not cookie_token:
            logger.warning(f"CSRF cookie missing: {request.method} {request.url.path}")
            return JSONResponse(
                status_code=403,
                content={"error": "csrf_cookie_missing", "message": "CSRF cookie required"}
            )

        # Validate cookie token
        if not validate_csrf_token(cookie_token):
            logger.warning(f"CSRF cookie invalid: {request.method} {request.url.path}")
            return JSONResponse(
                status_code=403,
                content={"error": "csrf_cookie_invalid", "message": "CSRF cookie invalid or expired"}
            )

        # Double Submit: header must match cookie
        if not hmac.compare_digest(header_token, cookie_token):
            logger.warning(f"CSRF mismatch: {request.method} {request.url.path}")
            return JSONResponse(
                status_code=403,
                content={"error": "csrf_mismatch", "message": "CSRF token mismatch"}
            )

        return await call_next(request)


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "CSRFMiddleware",
    "get_csrf_token",
    "set_csrf_cookie",
    "validate_csrf_token",
    "is_csrf_exempt",
    "EXEMPT_PATHS",
]
