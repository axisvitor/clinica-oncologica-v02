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

import hashlib
import hmac
import logging
import re
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

# Paths exempt from CSRF protection.
#
# Keep this set intentionally narrow: browser/session-backed mutating APIs must
# prove a double-submit CSRF token before route dependencies, DB writes, queues,
# or provider calls.  Provider webhooks and intentionally public tokenized APIs
# stay exempt because they are protected by non-cookie ingress controls.
EXACT_EXEMPT_PATHS = frozenset({
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/csrf-token",
    "/api/v2/auth/csrf-token",
})

PREFIX_EXEMPT_PATHS = frozenset({
    "/health/",
    "/webhooks/",
    "/api/v2/webhooks/",  # WhatsApp/Evolution webhooks; HMAC/idempotency covered separately.
    "/api/public/",
    "/api/v2/quiz-extensions/monthly/public",  # Tokenized public quiz flow, not cookie/session auth.
    "/static/",
    "/uploads/",
})

EXEMPT_PATHS = EXACT_EXEMPT_PATHS | PREFIX_EXEMPT_PATHS

# Authorization/X-API-Key may bypass CSRF only for endpoints that are truly
# token-authenticated and not cookie/session backed.  Keep empty until a route
# has an explicit non-cookie auth contract; webhooks/public APIs are already
# exempt above by path and verified by their own ingress controls.
TOKEN_AUTH_BYPASS_PATH_PREFIXES = frozenset()

# Safe HTTP methods (no state changes)
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


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


def _matches_prefix(path: str, prefix: str) -> bool:
    """Return True when ``path`` is inside an exempt prefix boundary."""
    if prefix.endswith("/"):
        return path.startswith(prefix)
    return path == prefix or path.startswith(f"{prefix}/")


def is_csrf_exempt(path: str, method: str) -> bool:
    """Check if request is exempt from CSRF protection."""
    if method in SAFE_METHODS:
        return True

    if path in EXACT_EXEMPT_PATHS:
        return True

    return any(_matches_prefix(path, exempt) for exempt in PREFIX_EXEMPT_PATHS)


def _path_allows_token_auth_bypass(path: str) -> bool:
    """Return True only for explicit non-cookie token-auth ingress paths."""
    return any(
        _matches_prefix(path, exempt)
        for exempt in TOKEN_AUTH_BYPASS_PATH_PREFIXES
    )


def _has_auth_header(request: Request) -> bool:
    """
    Allow CSRF bypass only for explicitly token-authenticated paths.

    CSRF protection is intended for cookie-auth flows, but a generic
    Authorization/X-API-Key bypass is unsafe because browser/session endpoints
    in this app intentionally reject legacy bearer/X-Session transports and
    resolve staff auth from cookies only.  A request header alone must not skip
    CSRF for session-backed state changes.
    """
    if not _path_allows_token_auth_bypass(request.url.path):
        return False

    return bool(
        request.headers.get("Authorization")
        or request.headers.get("X-API-Key")
    )


def _stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _safe_request_identifier(value: object) -> Optional[str]:
    if value is None:
        return None

    request_id = str(value)
    if _SAFE_REQUEST_ID.fullmatch(request_id):
        return request_id

    return f"hashed-{_stable_hash(request_id)}"


def _get_request_id(request: Request) -> Optional[str]:
    """Best-effort PHI-safe request correlation identifier."""
    request_id = _safe_request_identifier(getattr(request.state, "request_id", None))
    if request_id:
        return request_id

    monitoring_state = getattr(request.state, "monitoring", None)
    if isinstance(monitoring_state, dict):
        request_id = _safe_request_identifier(monitoring_state.get("request_id"))
        if request_id:
            return request_id

    return _safe_request_identifier(request.headers.get("X-Request-ID"))


def _client_identity_hash(request: Request) -> Optional[str]:
    if not request.client or not request.client.host:
        return None
    return _stable_hash(request.client.host)


def _log_csrf_denial(request: Request, *, reason: str) -> Optional[str]:
    """Emit PHI-safe structured diagnostics for a denied CSRF request."""
    request_id = _get_request_id(request)
    logger.warning(
        "CSRF validation denied",
        extra={
            "event_type": "csrf_denied",
            "reason": reason,
            "method": request.method,
            "path": request.url.path,
            "request_id": request_id,
            "client_identity_hash": _client_identity_hash(request),
        },
    )
    return request_id


def _csrf_denied_response(
    request: Request,
    *,
    reason: str,
    error: str,
    message: str,
) -> JSONResponse:
    request_id = _log_csrf_denial(request, reason=reason)
    content = {
        "error": error,
        "message": message,
    }
    if request_id:
        content["request_id"] = request_id
    return JSONResponse(status_code=403, content=content)


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

        # Get token from header (support multiple header names for compatibility)
        header_token = (
            request.headers.get("X-CSRF-Token") or
            request.headers.get("X-CSRFToken") or
            request.headers.get("X-XSRF-Token")
        )

        if not header_token:
            response = _csrf_denied_response(
                request,
                reason="missing_header",
                error="csrf_token_missing",
                message="CSRF token required in X-CSRF-Token header",
            )
            await response(scope, receive, send)
            return

        # Validate header token format and signature
        if not validate_csrf_token(header_token):
            response = _csrf_denied_response(
                request,
                reason="invalid_header",
                error="csrf_token_invalid",
                message="CSRF token invalid or expired",
            )
            await response(scope, receive, send)
            return

        # Get cookie token
        cookie_token = request.cookies.get(COOKIE_NAME)

        if not cookie_token:
            response = _csrf_denied_response(
                request,
                reason="missing_cookie",
                error="csrf_cookie_missing",
                message="CSRF cookie required",
            )
            await response(scope, receive, send)
            return

        # Validate cookie token format and signature
        if not validate_csrf_token(cookie_token):
            response = _csrf_denied_response(
                request,
                reason="invalid_cookie",
                error="csrf_cookie_invalid",
                message="CSRF cookie invalid or expired",
            )
            await response(scope, receive, send)
            return

        # Double Submit: header must match cookie (constant-time comparison)
        if not hmac.compare_digest(header_token, cookie_token):
            response = _csrf_denied_response(
                request,
                reason="mismatch",
                error="csrf_mismatch",
                message="CSRF token mismatch between header and cookie",
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
    "EXACT_EXEMPT_PATHS",
    "PREFIX_EXEMPT_PATHS",
    "TOKEN_AUTH_BYPASS_PATH_PREFIXES",
    "SAFE_METHODS",
    "TOKEN_EXPIRY",
    "COOKIE_NAME",
    "COOKIE_PATH",
    "COOKIE_SAMESITE",
]
