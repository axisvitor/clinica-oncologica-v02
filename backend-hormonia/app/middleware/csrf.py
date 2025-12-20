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

# Token configuration defaults
TOKEN_EXPIRY = 3600  # 1 hour
COOKIE_NAME = "csrf_token"
COOKIE_PATH = "/"
COOKIE_SAMESITE = "strict"


class CSRFSettings:
    """CSRF configuration settings."""

    def __init__(
        self,
        secret_key: str,
        cookie_name: str = COOKIE_NAME,
        token_expires_in: int = TOKEN_EXPIRY,
        cookie_path: str = COOKIE_PATH,
        cookie_domain: Optional[str] = None,
        cookie_secure: bool = False,
        cookie_httponly: bool = True,
        cookie_samesite: str = COOKIE_SAMESITE,
    ):
        self.secret_key = secret_key
        self.cookie_name = cookie_name
        self.token_expires_in = token_expires_in
        self.cookie_path = cookie_path
        self.cookie_domain = cookie_domain
        self.cookie_secure = cookie_secure
        self.cookie_httponly = cookie_httponly
        self.cookie_samesite = cookie_samesite


def get_csrf_settings() -> CSRFSettings:
    """
    Get CSRF settings from application configuration.

    Returns CSRFSettings with values from environment or defaults.
    """
    secret_key = _get_secret_key()

    return CSRFSettings(
        secret_key=secret_key,
        cookie_name=COOKIE_NAME,
        token_expires_in=TOKEN_EXPIRY,
        cookie_path=COOKIE_PATH,
        cookie_domain=None,
        cookie_secure=_is_production(),
        cookie_httponly=True,
        cookie_samesite=COOKIE_SAMESITE,
    )


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
    Generate a cryptographically signed CSRF token with high entropy.

    Token Format: {timestamp}.{random_hex}.{hmac_signature}

    Components:
        - timestamp: Current Unix timestamp (replay attack prevention)
        - random_hex: 64 hexadecimal characters (256 bits entropy)
        - hmac_signature: HMAC-SHA256 signature (prevents tampering)

    Security Properties:
        - 256-bit random entropy (cryptographically secure)
        - HMAC-SHA256 signature for integrity
        - Timestamp for expiration enforcement
        - Hexadecimal encoding (URL-safe, auditable)

    Args:
        secret_key: Optional HMAC secret key (uses configured key if None)

    Returns:
        str: Signed CSRF token in hexadecimal format

    Raises:
        ValueError: If secret key is invalid or too short

    Example:
        >>> token = generate_csrf_token()
        >>> # Returns: "1734695123.a1b2c3d4e5f6...signature"
    """
    if secret_key is None:
        secret_key = _get_secret_key()

    # Validate secret key strength
    if not secret_key or len(secret_key) < 32:
        raise ValueError(
            "CSRF secret key must be at least 32 characters. "
            "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )

    timestamp = str(int(time.time()))
    # Use 32 bytes (256 bits) of cryptographically secure random data
    random_data = secrets.token_hex(32)
    payload = f"{timestamp}.{random_data}"

    # Generate HMAC-SHA256 signature for integrity protection
    signature = hmac.new(
        secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    token = f"{payload}.{signature}"

    # Log token generation for security monitoring (without exposing the token)
    logger.debug(f"CSRF token generated: length={len(token)}, timestamp={timestamp}")

    return token


def validate_csrf_token(token: str, secret_key: Optional[str] = None) -> bool:
    """
    Validate a CSRF token's format, signature, and expiration.

    Uses constant-time comparison to prevent timing attacks.
    Handles edge cases including None tokens, non-ASCII characters,
    and invalid formats.

    Args:
        token: CSRF token string to validate (format: timestamp.random.signature)
        secret_key: Optional secret key for HMAC validation

    Returns:
        bool: True if token is valid, False otherwise

    Security considerations:
        - Uses hmac.compare_digest for constant-time comparison
        - Validates token format before processing
        - Checks timestamp for expiration and clock skew
        - Handles None and invalid inputs gracefully
    """
    # Handle None and empty tokens
    if token is None or not isinstance(token, str) or not token.strip():
        logger.debug("CSRF validation failed: token is None or empty")
        return False

    if secret_key is None:
        secret_key = _get_secret_key()

    try:
        parts = token.split(".")
        if len(parts) != 3:
            logger.debug(f"CSRF validation failed: invalid token format (expected 3 parts, got {len(parts)})")
            return False

        timestamp_str, random_data, signature = parts

        # Verify signature (constant-time)
        # Convert to ASCII-safe encoding to prevent non-ASCII comparison errors
        payload = f"{timestamp_str}.{random_data}"
        expected = hmac.new(
            secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        # Ensure both strings are ASCII-safe before comparison
        try:
            signature_bytes = signature.encode('ascii')
            expected_bytes = expected.encode('ascii')
        except UnicodeEncodeError:
            logger.debug("CSRF validation failed: non-ASCII characters in token")
            return False

        if not hmac.compare_digest(signature_bytes, expected_bytes):
            logger.debug("CSRF validation failed: signature mismatch")
            return False

        # Check expiration
        timestamp = int(timestamp_str)
        current_time = int(time.time())
        age = current_time - timestamp

        # Token is expired if older than TOKEN_EXPIRY
        if age > TOKEN_EXPIRY:
            logger.debug(f"CSRF validation failed: token expired (age: {age}s, max: {TOKEN_EXPIRY}s)")
            return False

        # Token is invalid if timestamp is too far in the future (60s clock skew allowed)
        if age < -60:
            logger.debug(f"CSRF validation failed: token timestamp too far in future (age: {age}s)")
            return False

        return True

    except (ValueError, IndexError, UnicodeDecodeError, AttributeError) as e:
        logger.debug(f"CSRF validation failed: {type(e).__name__}: {str(e)}")
        return False


# ============================================================================
# Public API
# ============================================================================

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
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=TOKEN_EXPIRY,
        path="/",
        secure=_is_production(),
        httponly=True,
        samesite="strict",
    )

    logger.debug(f"CSRF cookie set: secure={_is_production()}, httponly=True, samesite=strict")

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


# ============================================================================
# Middleware
# ============================================================================

class CSRFMiddleware(BaseHTTPMiddleware):
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
        super().__init__(app)
        logger.info("CSRF middleware initialized with Double Submit Cookie pattern")

    async def dispatch(self, request: Request, call_next):
        """
        Process request and validate CSRF token if required.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware in chain

        Returns:
            Response from application or 403 error if CSRF validation fails
        """
        # Skip exempt paths/methods
        if is_csrf_exempt(request.url.path, request.method):
            logger.debug(f"CSRF exempt: {request.method} {request.url.path}")
            return await call_next(request)

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
            return JSONResponse(
                status_code=403,
                content={
                    "error": "csrf_token_missing",
                    "message": "CSRF token required in X-CSRF-Token header"
                }
            )

        # Validate header token format and signature
        if not validate_csrf_token(header_token):
            logger.warning(
                f"CSRF token invalid in header: {request.method} {request.url.path} "
                f"from {client_ip} (token_length={len(header_token)})"
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": "csrf_token_invalid",
                    "message": "CSRF token invalid or expired"
                }
            )

        # Get cookie token
        cookie_token = request.cookies.get(COOKIE_NAME)

        if not cookie_token:
            logger.warning(
                f"CSRF cookie missing: {request.method} {request.url.path} "
                f"from {client_ip}"
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": "csrf_cookie_missing",
                    "message": "CSRF cookie required"
                }
            )

        # Validate cookie token format and signature
        if not validate_csrf_token(cookie_token):
            logger.warning(
                f"CSRF cookie invalid: {request.method} {request.url.path} "
                f"from {client_ip}"
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": "csrf_cookie_invalid",
                    "message": "CSRF cookie invalid or expired"
                }
            )

        # Double Submit: header must match cookie (constant-time comparison)
        if not hmac.compare_digest(header_token, cookie_token):
            logger.warning(
                f"CSRF mismatch: {request.method} {request.url.path} "
                f"from {client_ip} - header and cookie tokens do not match"
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": "csrf_mismatch",
                    "message": "CSRF token mismatch between header and cookie"
                }
            )

        # CSRF validation passed
        logger.debug(f"CSRF validation passed: {request.method} {request.url.path}")
        return await call_next(request)


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
]
