"""
CSRF Protection Middleware - Simplified Implementation

Stateless Double Submit Cookie pattern using HMAC-SHA256.
Native Python implementation with no external dependencies.

Token generation/validation logic lives in csrf_tokens.py.
This module contains the middleware, cookie handling, and path exemptions.

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
import logging
from fastapi import Request
from fastapi.responses import Response, JSONResponse
from starlette.types import ASGIApp, Scope, Receive, Send

from app.middleware.csrf_tokens import (
    CSRFSettings,
    build_csrf_settings,
    generate_csrf_token as _generate_csrf_token_impl,
    validate_csrf_token as _validate_csrf_token_impl,
    _get_secret_key,
    _is_production,
    TOKEN_EXPIRY,
    COOKIE_NAME,
    COOKIE_PATH,
    COOKIE_SAMESITE,
)
from typing import Optional

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
    "/api/v2/auth/logout",
    "/api/v2/auth/password/reset-request",
    "/api/v2/auth/password/reset-confirm",
    "/webhooks/",
    "/api/v2/webhooks/",  # WhatsApp/Evolution webhooks
    "/api/public/",
    "/api/v2/quiz-extensions/monthly/public",
    "/api/v2/auth/firebase/verify",  # Exempt: Use ID token in body (safe from CSRF)
    "/api/v2/messages",  # Exempt: Protected by session auth (get_current_user_from_session)
    "/api/v2/enhanced-messages",  # Exempt: Protected by session auth (enhanced messaging API)
    "/api/v2/flows",  # Exempt: Protected by session auth (flow management)
})

# Safe HTTP methods (no state changes)
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


# ============================================================================
# Public API
# ============================================================================

def get_csrf_settings() -> CSRFSettings:
    """
    Get CSRF settings from application configuration.

    Thin wrapper that resolves helpers from this module's namespace
    so that ``@patch("app.middleware.csrf._is_production")`` works in tests.
    See ``csrf_tokens.get_csrf_settings`` for full documentation.
    """
    return build_csrf_settings(
        secret_key_resolver=_get_secret_key,
        production_resolver=_is_production,
    )


def generate_csrf_token(secret_key: Optional[str] = None) -> str:
    """
    Generate a cryptographically signed CSRF token.

    Thin wrapper that resolves the secret key from this module's namespace
    so that ``@patch("app.middleware.csrf._get_secret_key")`` works in tests.
    See ``csrf_tokens.generate_csrf_token`` for full documentation.
    """
    if secret_key is None:
        secret_key = _get_secret_key()
    return _generate_csrf_token_impl(secret_key=secret_key)


def validate_csrf_token(token: str, secret_key: Optional[str] = None) -> bool:
    """
    Validate a CSRF token's format, signature, and expiration.

    Thin wrapper that resolves the secret key from this module's namespace
    so that ``@patch("app.middleware.csrf._get_secret_key")`` works in tests.
    See ``csrf_tokens.validate_csrf_token`` for full documentation.
    """
    if secret_key is None:
        secret_key = _get_secret_key()
    return _validate_csrf_token_impl(token, secret_key=secret_key)


def get_csrf_token() -> str:
    """Generate a new CSRF token."""
    return generate_csrf_token()


def set_csrf_cookie(response: Response, token: str) -> str:
    """
    Set CSRF token as an HTTP-only cookie with security flags.

    Implements Double Submit Cookie pattern by setting the token
    in a secure cookie that will be sent automatically by the browser.

    Cookie Security Flags:
        - httponly: True (prevents JavaScript access, XSS mitigation)
        - secure: True in production (HTTPS only)
        - samesite: "strict" (prevents CSRF from external sites)
        - path: "/" (available across entire domain)
        - max_age: TOKEN_EXPIRY (automatic expiration)

    Args:
        response: FastAPI Response object to set cookie on
        token: CSRF token string to store in cookie

    Returns:
        str: The token that was set (for convenience)

    Security Note:
        The same token must be sent in the X-CSRF-Token header
        for validation (Double Submit Cookie pattern).

    Example:
        >>> token = get_csrf_token()
        >>> set_csrf_cookie(response, token)
        >>> return {"csrf_token": token}
    """
    csrf_settings = get_csrf_settings()

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=TOKEN_EXPIRY,
        path="/",
        secure=csrf_settings.cookie_secure,
        httponly=True,
        samesite=csrf_settings.cookie_samesite,
    )

    logger.debug(f"CSRF cookie set: secure={csrf_settings.cookie_secure}, httponly=True, samesite={csrf_settings.cookie_samesite}")

    return token


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


def _has_auth_header(request: Request) -> bool:
    """
    Allow token-authenticated requests to bypass CSRF checks.

    CSRF protection is intended for cookie-auth flows. If a request includes
    an Authorization or X-API-Key header, we treat it as token-authenticated
    and skip CSRF validation.

    NOTE: X-Session-ID was removed from this check because custom headers
    can be set by attackers in cross-origin requests. If session auth relies
    on cookies, the X-Session-ID header alone should not bypass CSRF.
    """
    return bool(
        request.headers.get("Authorization")
        or request.headers.get("X-API-Key")
    )


# ============================================================================
# Middleware
# ============================================================================

class CSRFMiddleware:
    """
    CSRF protection middleware using Double Submit Cookie pattern.

    Security Model:
        1. Client requests CSRF token from /api/v2/auth/csrf-token
        2. Server generates signed token and sets it in httpOnly cookie
        3. Client includes same token in X-CSRF-Token header for state-changing requests
        4. Middleware validates both header and cookie tokens match

    Validation Steps:
        1. Check if path/method is exempt (safe methods, public endpoints)
        2. Verify X-CSRF-Token header is present
        3. Validate header token signature and expiration
        4. Verify CSRF cookie is present
        5. Validate cookie token signature and expiration
        6. Ensure header token matches cookie token (constant-time comparison)

    Protection Against:
        - CSRF attacks from malicious websites
        - Token tampering (HMAC signature)
        - Token replay attacks (expiration)
        - Timing attacks (constant-time comparison)

    Compatible Headers:
        - X-CSRF-Token (primary)
        - X-CSRFToken (alternative)
        - X-XSRF-Token (Angular compatibility)
    """

    def __init__(self, app: ASGIApp):
        self.app = app
        logger.info("CSRF middleware initialized with Double Submit Cookie pattern")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        Process request and validate CSRF token if required.

        Args:
            scope: ASGI scope
            receive: ASGI receive callable
            send: ASGI send callable
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)

        # Skip exempt paths/methods
        if is_csrf_exempt(request.url.path, request.method):
            logger.debug(f"CSRF exempt: {request.method} {request.url.path}")
            await self.app(scope, receive, send)
            return

        # Skip CSRF for token-authenticated requests
        if _has_auth_header(request):
            logger.debug(f"CSRF bypassed for auth header: {request.method} {request.url.path}")
            await self.app(scope, receive, send)
            return

        # Extract client information for logging
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")[:100]  # Truncate for security

        # Get token from header (support multiple header names for compatibility)
        header_token = (
            request.headers.get("X-CSRF-Token") or
            request.headers.get("X-CSRFToken") or
            request.headers.get("X-XSRF-Token")
        )

        if not header_token:
            logger.warning(
                f"CSRF token missing in header: {request.method} {request.url.path} "
                f"from {client_ip} ({user_agent})"
            )
            response = JSONResponse(
                status_code=403,
                content={
                    "error": "csrf_token_missing",
                    "message": "CSRF token required in X-CSRF-Token header"
                }
            )
            await response(scope, receive, send)
            return

        # Validate header token format and signature
        if not validate_csrf_token(header_token):
            logger.warning(
                f"CSRF token invalid in header: {request.method} {request.url.path} "
                f"from {client_ip} (token_length={len(header_token)})"
            )
            response = JSONResponse(
                status_code=403,
                content={
                    "error": "csrf_token_invalid",
                    "message": "CSRF token invalid or expired"
                }
            )
            await response(scope, receive, send)
            return

        # Get cookie token
        cookie_token = request.cookies.get(COOKIE_NAME)

        if not cookie_token:
            logger.warning(
                f"CSRF cookie missing: {request.method} {request.url.path} "
                f"from {client_ip}"
            )
            response = JSONResponse(
                status_code=403,
                content={
                    "error": "csrf_cookie_missing",
                    "message": "CSRF cookie required"
                }
            )
            await response(scope, receive, send)
            return

        # Validate cookie token format and signature
        if not validate_csrf_token(cookie_token):
            logger.warning(
                f"CSRF cookie invalid: {request.method} {request.url.path} "
                f"from {client_ip}"
            )
            response = JSONResponse(
                status_code=403,
                content={
                    "error": "csrf_cookie_invalid",
                    "message": "CSRF cookie invalid or expired"
                }
            )
            await response(scope, receive, send)
            return

        # Double Submit: header must match cookie (constant-time comparison)
        if not hmac.compare_digest(header_token, cookie_token):
            logger.warning(
                f"CSRF mismatch: {request.method} {request.url.path} "
                f"from {client_ip} - header and cookie tokens do not match"
            )
            response = JSONResponse(
                status_code=403,
                content={
                    "error": "csrf_mismatch",
                    "message": "CSRF token mismatch between header and cookie"
                }
            )
            await response(scope, receive, send)
            return

        # CSRF validation passed
        logger.debug(f"CSRF validation passed: {request.method} {request.url.path}")
        await self.app(scope, receive, send)


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "CSRFMiddleware",
    "CSRFSettings",
    "get_csrf_token",
    "get_csrf_settings",
    "set_csrf_cookie",
    "validate_csrf_token",
    "generate_csrf_token",
    "is_csrf_exempt",
    "EXEMPT_PATHS",
    "SAFE_METHODS",
    "TOKEN_EXPIRY",
    "COOKIE_NAME",
    "COOKIE_PATH",
    "COOKIE_SAMESITE",
]
