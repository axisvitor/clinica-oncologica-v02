"""
CSRF Protection Middleware - Unified Stateless Implementation

Native Python implementation using standard library (hmac, secrets, hashlib).
Fast, secure, and fully auditable without external dependencies.

Security Implementation:
- HMAC-SHA256 for cryptographically secure token validation
- HEXADECIMAL encoding (not Base64) for better readability and auditability
- NO in-memory rate limiting (prevents memory leaks)
- httpOnly, secure, and SameSite cookie flags
- Constant-time comparison to prevent timing attacks
- Double Submit Cookie pattern for stateless CSRF protection

Architecture:
- Pure Python standard library (hmac, secrets, hashlib, time)
- No external dependencies beyond FastAPI
- Zero memory overhead (no caching dictionaries)
- Stateless token validation

Protected Endpoints:
All state-changing operations (POST, PUT, DELETE, PATCH) except exempt paths.

Usage:
    # Add middleware to application
    from app.middleware.csrf import CSRFMiddleware
    app.add_middleware(CSRFMiddleware)

    # Get CSRF token in route
    from app.middleware.csrf import get_csrf_token, set_csrf_cookie

    @router.get("/csrf-token")
    async def get_token(request: Request, response: Response):
        token = get_csrf_token(request)
        set_csrf_cookie(request, response, token)
        return {"csrf_token": token}

    # Validate CSRF in protected route (automatic via middleware)
    @router.post("/protected")
    async def protected_endpoint(request: Request):
        # CSRF validation happens automatically in middleware
        return {"message": "Success"}

Configuration:
    SECURITY_CSRF_SECRET_KEY: Secret key for token generation (from .env)
    SESSION_COOKIE_SAMESITE: "strict" | "lax" | "none" (default: "strict")
    SESSION_ENABLE_COOKIE_SECURE: Enable secure flag (default: True in production)
    SESSION_ENABLE_COOKIE_HTTPONLY: Enable httpOnly flag (default: True)
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Any
import logging
import hmac
import hashlib
import time
import secrets

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

class CsrfSettings(BaseSettings):
    """
    CSRF protection configuration.

    All settings loaded from environment variables with sensible defaults.
    """

    secret_key: str = Field(
        ...,
        description="Secret key for CSRF token generation (from SECURITY_CSRF_SECRET_KEY env var)",
    )
    cookie_name: str = Field(
        default="fastapi-csrf-token", description="Name of the CSRF cookie"
    )
    cookie_samesite: str = Field(
        default="strict",
        description="SameSite cookie policy: strict (recommended), lax, or none",
    )
    cookie_secure: bool = Field(
        default=True,
        description="Require HTTPS for cookie transmission (must be True in production)",
    )
    cookie_httponly: bool = Field(
        default=True, description="Prevent JavaScript access to CSRF cookie"
    )
    cookie_path: str = Field(default="/", description="Cookie path scope")
    cookie_domain: Optional[str] = Field(
        default=None,
        description="Cookie domain scope (None = auto-detect from request)",
    )
    token_header_name: str = Field(
        default="X-CSRF-Token",
        description="HTTP header name for CSRF token in requests",
    )
    token_expires_in: int = Field(
        default=3600,
        description="CSRF token expiration time in seconds (1 hour default)",
    )

    model_config = SettingsConfigDict(extra="ignore")


# ============================================================================
# Helper Functions for Safe Value Extraction
# ============================================================================

def _extract_secret_str(value: Any) -> Optional[str]:
    """Safely extract secret string from Pydantic SecretStr or plain string."""
    if value is None:
        return None
    if hasattr(value, "get_secret_value"):
        try:
            value = value.get_secret_value()
        except Exception:
            return None
    if isinstance(value, str):
        if value.strip():
            return value
    return None


def get_csrf_settings() -> CsrfSettings:
    """
    Load CSRF settings from application configuration.

    Validates that secret key exists and has sufficient length.

    Returns:
        CsrfSettings: Validated CSRF configuration

    Raises:
        ValueError: If secret key is missing or too short
    """
    from app.config import settings

    # Validate secret key exists
    csrf_secret = _extract_secret_str(
        getattr(settings, "SECURITY_CSRF_SECRET_KEY", None)
    )
    if csrf_secret is None:
        csrf_secret = _extract_secret_str(getattr(settings, "CSRF_SECRET_KEY", None))

    if not csrf_secret:
        raise ValueError(
            "CSRF secret key is required. Set SECURITY_CSRF_SECRET_KEY environment variable.\n"
            "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )

    if len(csrf_secret) < 32:
        raise ValueError(
            f"CSRF secret key must be at least 32 characters (got {len(csrf_secret)}).\n"
            "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )

    # Use secure cookies only in production
    environment = getattr(
        settings, "APP_ENVIRONMENT", getattr(settings, "ENVIRONMENT", "development")
    )
    is_production = str(environment).lower() == "production"
    cookie_secure = is_production or bool(
        getattr(
            settings,
            "SESSION_ENABLE_COOKIE_SECURE",
            getattr(settings, "SESSION_COOKIE_SECURE", False),
        )
    )

    # SECURITY: Use 'strict' for maximum CSRF protection
    cookie_samesite = "strict"

    return CsrfSettings(
        secret_key=csrf_secret,
        cookie_secure=cookie_secure,
        cookie_samesite=cookie_samesite,
        cookie_httponly=True,
    )


# ============================================================================
# Exception Classes
# ============================================================================

class CsrfProtectError(HTTPException):
    """
    CSRF validation error exception.

    FastAPI HTTPException for CSRF validation failures.
    """
    def __init__(self, detail: str = "CSRF validation failed"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


# ============================================================================
# Exempt Paths Configuration (TUPLE for performance)
# ============================================================================

# SECURITY FIX: Exempt paths as FROZENSET for O(1) lookup performance
# Using frozenset instead of tuple for constant-time membership testing
EXEMPT_PATHS = frozenset({
    # Health and documentation
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    # CSRF token endpoint (GET only)
    "/csrf-token",
    "/api/v2/auth/csrf-token",
    # Public endpoints
    "/webhooks/",
    "/api/public/",
    # Session validation (GET only)
    "/session/validate",
    "/session/active",
    "/session/stats",
    # Public quiz endpoints (token-based, no session auth)
    "/api/v2/quiz-extensions/monthly/public",
    "/api/v2/monthly-quiz-public/monthly/public",
    "/api/v2/monthly-quiz/monthly/public",
})


def is_csrf_exempt(path: str, method: str) -> bool:
    """
    Check if path and method combination is exempt from CSRF protection.

    SECURITY FIX: Optimized with frozenset for O(1) lookups instead of O(n) tuple iteration.

    Exempt conditions:
    1. Safe HTTP methods (GET, HEAD, OPTIONS) - read-only operations
    2. Paths in EXEMPT_PATHS frozenset
    3. Static file paths

    Args:
        path: Request path to check
        method: HTTP method (GET, POST, etc.)

    Returns:
        True if path/method is exempt from CSRF protection
    """
    # SECURITY FIX: Use frozenset for O(1) safe method checking
    # Safe HTTP methods are always exempt (CSRF only needed for state changes)
    SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
    if method in SAFE_METHODS:
        return True

    # SECURITY FIX: O(1) exact path lookup in frozenset before O(n) prefix check
    # Check exact path match first (most common case)
    if path in EXEMPT_PATHS:
        return True

    # Check if path starts with any exempt path prefix
    if any(path.startswith(exempt) for exempt in EXEMPT_PATHS):
        return True

    # Static files are exempt
    if path.startswith("/static/") or path.startswith("/uploads/"):
        return True

    return False


# ============================================================================
# Token Generation and Validation (Native Python - HEXADECIMAL)
# ============================================================================

def _generate_token_signature(data: str, secret_key: str) -> str:
    """
    Generate HMAC-SHA256 signature for data.

    Uses native Python hmac module for cryptographic security.

    Args:
        data: Data to sign
        secret_key: Secret key for HMAC

    Returns:
        Hexadecimal signature string
    """
    return hmac.new(
        secret_key.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def generate_csrf_token(secret_key: Optional[str] = None) -> str:
    """
    Generate a new signed CSRF token in HEXADECIMAL format.

    Token Format: {timestamp}.{random_data}.{hmac_signature}

    SECURITY FIX: Using hexadecimal encoding instead of Base64 for:
    - More readable and auditable in logs
    - No URL-safe encoding concerns (no padding issues)
    - Cleaner regex validation (^[0-9a-f.]+$)
    - Better compatibility with different systems
    - Prevents potential base64 decoding vulnerabilities

    Args:
        secret_key: Optional secret key (uses settings if not provided)

    Returns:
        Hexadecimal-encoded CSRF token string

    Example:
        "1734695123.a1b2c3d4e5f6.9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b"
    """
    if secret_key is None:
        secret_key = get_csrf_settings().secret_key

    # Timestamp for expiration checking
    timestamp = str(int(time.time()))

    # SECURITY FIX: 32 bytes of cryptographically secure random data (64 hex chars)
    # Using secrets.token_hex() for hex encoding instead of base64
    # 32 bytes provides 256 bits of entropy
    random_data = secrets.token_hex(32)

    # Combine timestamp and random data
    data = f"{timestamp}.{random_data}"

    # Sign with HMAC-SHA256 (cryptographically secure)
    signature = _generate_token_signature(data, secret_key)

    # Return in format: timestamp.random.signature (all hexadecimal)
    token = f"{data}.{signature}"

    logger.debug(
        "Generated CSRF token",
        extra={
            "timestamp": timestamp,
            "random_length": len(random_data),
            "signature_length": len(signature),
            "total_length": len(token),
        }
    )

    return token


def _validate_token_signature(token: str, secret_key: str, max_age: int = 3600) -> bool:
    """
    Validate CSRF token format, expiration, and signature.

    SECURITY FIX: Uses constant-time comparison to prevent timing attacks.

    Performs validation in this order:
    1. Format validation (must have 3 parts: timestamp.random.signature)
    2. Signature validation (constant-time HMAC comparison)
    3. Expiration validation (within max_age seconds)

    Args:
        token: CSRF token to validate (hexadecimal format)
        secret_key: Secret key for HMAC validation
        max_age: Maximum token age in seconds (default: 1 hour)

    Returns:
        True if token is valid, False otherwise

    Security Notes:
    - SECURITY FIX: Uses hmac.compare_digest() for constant-time comparison
    - Prevents timing attacks by avoiding early returns on signature mismatch
    - Validates signature before expiration to prevent timing leaks
    - Allows 60 seconds of clock skew for distributed systems
    """
    try:
        # Parse token format: timestamp.random.signature
        parts = token.split(".")
        if len(parts) != 3:
            logger.warning(
                "CSRF token has invalid format",
                extra={"parts_count": len(parts)}
            )
            return False

        timestamp_str, random_data, signature = parts

        # Reconstruct data for signature validation
        data = f"{timestamp_str}.{random_data}"

        # Calculate expected signature using HMAC-SHA256
        expected_signature = _generate_token_signature(data, secret_key)

        # SECURITY FIX: Constant-time comparison using hmac.compare_digest()
        # This prevents timing attacks by ensuring comparison takes same time
        # regardless of where strings differ
        if not hmac.compare_digest(signature, expected_signature):
            logger.warning("CSRF token signature mismatch")
            return False

        # Validate expiration (only after signature check to prevent timing leaks)
        timestamp = int(timestamp_str)
        current_time = int(time.time())
        token_age = current_time - timestamp

        # Allow 60 seconds of clock skew for distributed systems
        if token_age > max_age or token_age < -60:
            logger.warning(
                "CSRF token expired",
                extra={
                    "token_age": token_age,
                    "max_age": max_age,
                    "timestamp": timestamp,
                    "current_time": current_time,
                }
            )
            return False

        logger.debug(
            "CSRF token validated successfully",
            extra={"token_age": token_age}
        )
        return True

    except (ValueError, IndexError) as e:
        logger.warning(
            "CSRF token validation error",
            extra={"error": str(e)}
        )
        return False


# ============================================================================
# Public API Functions
# ============================================================================

def set_csrf_cookie(request: Request, response: Response, token: str = None) -> str:
    """
    Set CSRF cookie in response with proper security flags.

    This function RETURNS the token value, allowing callers to include
    it in the response body for easier frontend integration.

    Args:
        request: FastAPI request object
        response: FastAPI response object
        token: Optional pre-generated token (generates new if not provided)

    Returns:
        The CSRF token that was set in the cookie

    Example:
        from fastapi import Response
        from fastapi.responses import JSONResponse

        response = JSONResponse({"message": "success"})
        token = set_csrf_cookie(request, response)
        response.body = json.dumps({"message": "success", "csrf_token": token}).encode()
        return response
    """
    try:
        settings = get_csrf_settings()

        # Generate new token if not provided
        if token is None:
            token = generate_csrf_token(settings.secret_key)

        # Set cookie with security flags
        response.set_cookie(
            key=settings.cookie_name,
            value=token,
            max_age=settings.token_expires_in,
            path=settings.cookie_path,
            domain=settings.cookie_domain,
            secure=settings.cookie_secure,
            httponly=settings.cookie_httponly,
            samesite=settings.cookie_samesite,
        )

        logger.debug(
            "CSRF cookie set successfully",
            extra={
                "cookie_name": settings.cookie_name,
                "secure": settings.cookie_secure,
                "httponly": settings.cookie_httponly,
                "samesite": settings.cookie_samesite,
            }
        )

        return token

    except Exception as e:
        logger.error(f"Failed to set CSRF cookie: {str(e)}")
        raise


def get_csrf_token(request: Request) -> str:
    """
    Generate and return CSRF token for the current request.

    Args:
        request: FastAPI request object

    Returns:
        New CSRF token string
    """
    settings = get_csrf_settings()
    return generate_csrf_token(settings.secret_key)


def validate_csrf_token(request: Request) -> None:
    """
    Validate CSRF token from headers and cookies (Double Submit Cookie pattern).

    Validation Steps:
    1. Extract token from header (X-CSRF-Token, X-CSRFToken, X-XSRF-Token)
    2. Validate token signature and expiration
    3. Extract token from cookie
    4. Validate cookie signature and expiration
    5. Verify header and cookie tokens match (Double Submit Cookie pattern)

    Args:
        request: FastAPI request object

    Raises:
        CsrfProtectError: If validation fails at any step

    Security Notes:
    - Implements Double Submit Cookie pattern for stateless CSRF protection
    - Uses constant-time comparison to prevent timing attacks
    - No in-memory structures (prevents memory leaks)
    """
    settings = get_csrf_settings()
    client_ip = request.client.host if getattr(request, "client", None) else "unknown"
    request_path = str(request.url.path) if hasattr(request, "url") else "unknown"

    # Step 1: Get token from header
    csrf_header = None
    for header_name in [settings.token_header_name, "X-CSRFToken", "X-XSRF-Token"]:
        csrf_header = request.headers.get(header_name)
        if csrf_header:
            break

    if not csrf_header:
        logger.warning(
            f"CSRF token missing in headers for {request_path}",
            extra={"client_ip": client_ip}
        )
        raise CsrfProtectError("Missing CSRF token in headers")

    # Step 2: Validate header token signature and expiration
    if not _validate_token_signature(csrf_header, settings.secret_key, settings.token_expires_in):
        logger.warning(
            f"CSRF token invalid signature or expired for {request_path}",
            extra={"client_ip": client_ip}
        )
        raise CsrfProtectError("Invalid CSRF token")

    # Step 3: Get token from cookie (Double Submit Cookie Check)
    csrf_cookie = request.cookies.get(settings.cookie_name)
    if not csrf_cookie:
        # Try fallback cookie name
        csrf_cookie = request.cookies.get("csrf_token")

    if not csrf_cookie:
        logger.warning(
            f"CSRF cookie missing for {request_path}",
            extra={"client_ip": client_ip}
        )
        raise CsrfProtectError("Missing CSRF cookie")

    # Step 4: Validate cookie signature
    if not _validate_token_signature(csrf_cookie, settings.secret_key, settings.token_expires_in):
        logger.warning(
            f"CSRF cookie has invalid signature or is expired for {request_path}",
            extra={"client_ip": client_ip}
        )
        raise CsrfProtectError("Invalid CSRF cookie")

    # Step 5: Verify header and cookie tokens match (Double Submit Cookie pattern)
    # SECURITY FIX: Use constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(csrf_header, csrf_cookie):
        logger.warning(
            f"CSRF header and cookie mismatch for {request_path}",
            extra={"client_ip": client_ip}
        )
        raise CsrfProtectError("CSRF token mismatch")

    logger.debug(
        f"CSRF validation successful for {request_path}",
        extra={"client_ip": client_ip}
    )


# ============================================================================
# CSRF Middleware
# ============================================================================

class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection middleware using Double Submit Cookie pattern.

    Automatically validates CSRF tokens for state-changing requests
    (POST, PUT, DELETE, PATCH) unless the path is in the exempt list.

    The middleware:
    1. Checks if the request needs CSRF protection
    2. Validates the CSRF token using the double submit cookie pattern
    3. Returns 403 Forbidden if validation fails
    4. Allows the request to proceed if validation passes

    Usage:
        from app.middleware.csrf import CSRFMiddleware
        app.add_middleware(CSRFMiddleware)
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        logger.info("CSRF middleware initialized")

    async def dispatch(self, request: Request, call_next):
        """
        Process request with CSRF validation.

        Args:
            request: The incoming request
            call_next: Next middleware in chain

        Returns:
            Response from the application or 403 if CSRF validation fails
        """
        # Check if CSRF protection is needed
        if is_csrf_exempt(request.url.path, request.method):
            # Skip CSRF validation for exempt paths/methods
            return await call_next(request)

        # Validate CSRF token
        try:
            validate_csrf_token(request)
        except CsrfProtectError as e:
            # Return 403 Forbidden if validation fails
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=403,
                content={
                    "error": "csrf_validation_failed",
                    "message": str(e.detail),
                    "timestamp": time.time(),
                }
            )

        # CSRF validation passed - proceed with request
        return await call_next(request)


# ============================================================================
# Public Exports
# ============================================================================

__all__ = [
    "CSRFMiddleware",
    "CsrfSettings",
    "get_csrf_settings",
    "set_csrf_cookie",
    "get_csrf_token",
    "validate_csrf_token",
    "is_csrf_exempt",
    "CsrfProtectError",
    "EXEMPT_PATHS",
]
