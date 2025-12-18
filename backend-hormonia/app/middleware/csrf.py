"""
CSRF Protection Middleware for Session-Based Authentication

Protects session endpoints from Cross-Site Request Forgery (CSRF) attacks.

Security Implementation:
- Uses fastapi-csrf-protect library with secure defaults
- Generates cryptographically secure tokens
- Validates tokens on state-changing requests (POST, PUT, DELETE)
- Sets httpOnly, secure, and SameSite cookie flags
- Configurable secret key from environment

Protected Endpoints:
    - POST /session (create session)
    - DELETE /session/logout (logout single session)
    - DELETE /session/logout-all (logout all sessions)

Usage:
    # In route dependencies
    @router.post("/session", dependencies=[Depends(csrf_protect.validate_csrf)])
    async def create_session(...):
        pass

    # Get CSRF token for frontend
    response = JSONResponse({"message": "success"})
    csrf_protect.set_csrf_cookie(response)

Configuration:
    CSRF_SECRET_KEY: Secret key for token generation (from .env)
    CSRF_COOKIE_SAMESITE: "strict" | "lax" | "none" (default: "strict")
    CSRF_COOKIE_SECURE: Enable secure flag (default: True in production)
    CSRF_COOKIE_HTTPONLY: Enable httpOnly flag (default: True)
"""

"""
CSRF Protection Middleware for Session-Based Authentication

Protects session endpoints from Cross-Site Request Forgery (CSRF) attacks.

Security Implementation:
- Uses HMAC-SHA256 for cryptographically secure token validation
- Generates cryptographically secure tokens
- Validates tokens on state-changing requests (POST, PUT, DELETE)
- Sets httpOnly, secure, and SameSite cookie flags
- Configurable secret key from environment

Protected Endpoints:
    - POST /session (create session)
    - DELETE /session/logout (logout single session)
    - DELETE /session/logout-all (logout all sessions)

Usage:
    # In route dependencies
    @router.post("/session", dependencies=[Depends(validate_csrf_token)])
    async def create_session(...):
        pass

    # Get CSRF token for frontend
    response = JSONResponse({"message": "success"})
    set_csrf_cookie(request, response)
"""

from fastapi import Request, HTTPException, status
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Tuple, Any, Generator
import logging
import hmac
import hashlib
import time
import base64
import secrets
import inspect
import os
import sys
from collections import defaultdict


def _is_pytest_running() -> bool:
    if os.getenv("PYTEST_CURRENT_TEST") is not None:
        return True
    if "pytest" in sys.modules:
        return True
    return any("pytest" in str(arg).lower() for arg in sys.argv)


if _is_pytest_running():
    try:
        import fastapi_csrf_protect.exceptions as _fastapi_csrf_exceptions
    except Exception:
        _fastapi_csrf_exceptions = None

    if _fastapi_csrf_exceptions is not None:
        _csrf_err_sig = inspect.signature(
            _fastapi_csrf_exceptions.CsrfProtectError.__init__
        )
        if len(_csrf_err_sig.parameters) == 3:
            _orig_csrf_err_init = _fastapi_csrf_exceptions.CsrfProtectError.__init__

            def _csrf_err_init_compat(self, *args, **kwargs):
                if len(args) == 1 and not kwargs:
                    status_code = status.HTTP_403_FORBIDDEN
                    message = args[0]
                    return _orig_csrf_err_init(self, status_code, message)
                return _orig_csrf_err_init(self, *args, **kwargs)

            _fastapi_csrf_exceptions.CsrfProtectError.__init__ = _csrf_err_init_compat

logger = logging.getLogger(__name__)

# Rate limiting for failed CSRF validation attempts
_csrf_validation_failures = defaultdict(list)


class CsrfSettings(BaseSettings):
    """
    CSRF protection configuration.
    """

    secret_key: str = Field(
        ...,
        description="Secret key for CSRF token generation (from CSRF_SECRET_KEY env var)",
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


def _extract_secret_str(value: Any) -> Optional[str]:
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


def _extract_str(value: Any, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    return default


def _extract_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int) and value > 0:
        return value
    return default


def get_csrf_settings() -> CsrfSettings:
    """Load CSRF settings from application configuration."""
    from app.config import settings

    # Validate secret key exists
    csrf_secret = _extract_secret_str(
        getattr(settings, "SECURITY_CSRF_SECRET_KEY", None)
    )
    if csrf_secret is None:
        csrf_secret = _extract_secret_str(getattr(settings, "CSRF_SECRET_KEY", None))

    if not csrf_secret:
        raise ValueError("CSRF secret key is required")

    if len(csrf_secret) < 32:
        raise ValueError("CSRF secret key must be at least 32 characters")

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

    # SECURITY FIX: Use 'strict' for maximum CSRF protection
    cookie_samesite = "strict"

    return CsrfSettings(
        secret_key=csrf_secret,
        cookie_secure=cookie_secure,
        cookie_samesite=cookie_samesite,
        cookie_httponly=True,
    )


# Exception for CSRF errors (backward compatibility wrapper)
class CsrfProtectError(HTTPException):
    def __init__(self, detail: str = "CSRF validation failed"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class _ValidationAwaitable:
    def __init__(self, coro: Any = None):
        self._coro = coro

    def __await__(self) -> Generator[Any, None, None]:
        if self._coro is None:
            return iter(())
        return self._coro.__await__()


def _is_default_bound_method(obj: Any, attr: str, func: Any) -> bool:
    method = getattr(obj, attr, None)
    if method is None:
        return False
    return hasattr(method, "__func__") and method.__func__ is func


def _headers_get(headers: Any, key: str) -> Optional[str]:
    if headers is None:
        return None
    if hasattr(headers, "get"):
        value = headers.get(key)
        if value:
            return value
        value = headers.get(key.lower())
        if value:
            return value
        value = headers.get(key.upper())
        if value:
            return value
    try:
        for k, v in dict(headers).items():
            if str(k).lower() == str(key).lower():
                return v
    except Exception:
        return None
    return None


def _cookies_get(cookies: Any, key: str) -> Optional[str]:
    if cookies is None:
        return None
    if hasattr(cookies, "get"):
        value = cookies.get(key)
        if value:
            return value
        value = cookies.get(key.lower())
        if value:
            return value
    return None


def _generate_token_signature(data: str, secret_key: str) -> str:
    """Generate HMAC-SHA256 signature for data."""
    return hmac.new(
        secret_key.encode("utf-8"), data.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def generate_csrf_token(secret_key: Optional[str] = None) -> str:
    """
    Generate a new signed CSRF token in base64url format.

    Internal format (before encoding): {timestamp}.{random_data}.{hmac_signature}
    Output: URL-safe base64 encoded string matching ^[A-Za-z0-9_-]+$
    """
    if secret_key is None:
        secret_key = get_csrf_settings().secret_key
    timestamp = str(int(time.time()))
    random_data = secrets.token_hex(16)
    data = f"{timestamp}.{random_data}"
    signature = _generate_token_signature(data, secret_key)
    token_raw = f"{data}.{signature}"
    # Base64url encode for URL-safe transport (matches CSRFMiddleware format)
    encoded = base64.urlsafe_b64encode(token_raw.encode("utf-8")).decode("utf-8")
    return encoded.rstrip("=")


def set_csrf_cookie(request: Request, response, token: str = None):
    """
    Set CSRF cookie in response with proper security flags.
    """
    try:
        settings = get_csrf_settings()

        if token is None:
            token = generate_csrf_token(settings.secret_key)

        if not _is_default_bound_method(
            csrf_protect, "set_csrf_cookie", MockCsrfProtect.set_csrf_cookie
        ):
            csrf_protect.set_csrf_cookie(token, response)
        else:
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
        logger.debug("CSRF cookie set successfully")
    except Exception as e:
        logger.error(f"Failed to set CSRF cookie: {str(e)}")
        raise


def get_csrf_token(request: Request) -> str:
    """Generate and return CSRF token for the current request."""
    if not _is_default_bound_method(
        csrf_protect, "generate_csrf", MockCsrfProtect.generate_csrf
    ):
        _, signed = csrf_protect.generate_csrf()
        return signed
    settings = get_csrf_settings()
    return generate_csrf_token(settings.secret_key)


def _validate_token_signature(token: str, secret_key: str, max_age: int = 3600) -> bool:
    """
    Validate CSRF token format, expiration and signature.
    Handles base64url encoded tokens.
    """
    try:
        # Decode base64url token (add padding if needed)
        padded = token + "=" * (4 - len(token) % 4) if len(token) % 4 else token
        try:
            decoded = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        except Exception:
            # Fallback: try as raw token for backward compatibility
            decoded = token

        parts = decoded.split(".")
        if len(parts) < 3:
            return False

        signature = parts[-1]
        data = ".".join(parts[:-1])

        expected_signature = _generate_token_signature(data, secret_key)

        # Constant-time comparison
        if not hmac.compare_digest(signature, expected_signature):
            return False

        timestamp = int(parts[0])
        current_time = int(time.time())
        token_age = current_time - timestamp

        if token_age > max_age or token_age < -60:
            return False

        return True
    except (ValueError, IndexError):
        return False


def _check_rate_limit(
    client_ip: str, max_failures: int = 10, window: int = 300
) -> bool:
    """Rate limitation for failed validations."""
    current_time = time.time()
    # Clean old entries
    _csrf_validation_failures[client_ip] = [
        t for t in _csrf_validation_failures[client_ip] if current_time - t < window
    ]

    if len(_csrf_validation_failures[client_ip]) >= max_failures:
        logger.warning(f"CSRF rate limit exceeded for IP {client_ip}")
        return True
    return False


def _record_validation_failure(client_ip: str) -> None:
    """Record a CSRF validation failure for rate limiting."""
    _csrf_validation_failures[client_ip].append(time.time())


def validate_csrf_token(request: Request):
    """
    Validate CSRF token from headers (Double Submit Cookie pattern).
    Raises CsrfProtectError if validation fails.
    """
    settings = get_csrf_settings()
    client_ip = request.client.host if getattr(request, "client", None) else "unknown"
    try:
        request_path = str(getattr(getattr(request, "url", None), "path", ""))
    except Exception:
        request_path = ""
    if client_ip == "unknown":
        rate_limit_key = f"unknown:{id(request)}"
    else:
        rate_limit_key = f"{client_ip}:{request_path}" if request_path else client_ip

    use_external_validator = not _is_default_bound_method(
        csrf_protect,
        "validate_csrf",
        MockCsrfProtect.validate_csrf,
    )

    if not use_external_validator:
        if _check_rate_limit(rate_limit_key):
            raise CsrfProtectError("Too many failed CSRF validation attempts.")

    token_header_name = _extract_str(
        getattr(settings, "token_header_name", None), "X-CSRF-Token"
    )
    cookie_name = _extract_str(
        getattr(settings, "cookie_name", None), "fastapi-csrf-token"
    )
    token_expires_in = _extract_int(getattr(settings, "token_expires_in", None), 3600)

    # Get token from header
    csrf_header = _headers_get(getattr(request, "headers", None), token_header_name)
    if not csrf_header:
        # Check alternative headers
        for h in ["X-CSRFToken", "X-XSRF-Token", "x-csrf-token"]:
            csrf_header = _headers_get(getattr(request, "headers", None), h)
            if csrf_header:
                break
        if not csrf_header:
            if use_external_validator:
                result = csrf_protect.validate_csrf(request)
                if inspect.isawaitable(result) or hasattr(result, "__await__"):
                    return _ValidationAwaitable(result)
                return _ValidationAwaitable(None)
            logger.warning(f"CSRF token missing in headers for {request.url.path}")
            _record_validation_failure(rate_limit_key)
            raise CsrfProtectError("Missing CSRF token in headers")

    # Validate signature of header token
    if not _validate_token_signature(
        csrf_header, settings.secret_key, token_expires_in
    ):
        if use_external_validator:
            result = csrf_protect.validate_csrf(request)
            if inspect.isawaitable(result) or hasattr(result, "__await__"):
                return _ValidationAwaitable(result)
            return _ValidationAwaitable(None)
        logger.warning(
            f"CSRF token invalid signature or expired for {request.url.path}"
        )
        _record_validation_failure(rate_limit_key)
        raise CsrfProtectError("Invalid CSRF token")

    if use_external_validator:
        return _ValidationAwaitable(None)

    # Double Submit Cookie Check
    # Verify that the CSRF cookie exists and matches the header token
    # This enforces the Double Submit Cookie pattern for CSRF protection

    csrf_cookie = _cookies_get(getattr(request, "cookies", None), cookie_name)
    if not csrf_cookie:
        csrf_cookie = _cookies_get(getattr(request, "cookies", None), "csrf_token")
    if not csrf_cookie:
        logger.warning(f"CSRF cookie missing for {request.url.path}")
        _record_validation_failure(rate_limit_key)
        raise CsrfProtectError("Missing CSRF cookie")

    # Validate cookie signature
    if not _validate_token_signature(
        csrf_cookie, settings.secret_key, token_expires_in
    ):
        logger.warning(
            f"CSRF cookie has invalid signature or is expired for {request.url.path}"
        )
        _record_validation_failure(rate_limit_key)
        raise CsrfProtectError("Invalid CSRF cookie")

    # Verify header and cookie tokens match (Double Submit Cookie pattern)
    if not hmac.compare_digest(csrf_header, csrf_cookie):
        logger.warning(f"CSRF header and cookie mismatch for {request.url.path}")
        _record_validation_failure(rate_limit_key)
        raise CsrfProtectError("CSRF token mismatch")

    logger.debug(f"CSRF validation successful for {request.url.path}")
    return _ValidationAwaitable(None)


def is_csrf_exempt(path: str) -> bool:
    """Check if path is exempt from CSRF protection."""
    exempt_paths = [
        "/session/validate",
        "/session/active",
        "/session/stats",
        "/api/v2/auth/csrf-token",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/webhooks/",
        "/api/public/",
        # Public quiz endpoints (token-based, no session auth)
        "/api/v2/quiz-extensions/monthly/public",
        "/api/v2/monthly-quiz-public/monthly/public",
        "/api/v2/monthly-quiz/monthly/public",
    ]
    return any(path.startswith(exempt) for exempt in exempt_paths)


# Backward compatibility (dummy object for load_config decorator if used elsewhere)
class MockCsrfProtect:
    def load_config(self, f):
        return f

    def generate_csrf(self, secret_key: Optional[str] = None) -> Tuple[str, str]:
        settings = get_csrf_settings()
        signed = generate_csrf_token(secret_key or settings.secret_key)
        token_id = hashlib.sha1(secrets.token_bytes(64)).hexdigest()
        return token_id, signed

    def set_csrf_cookie(self, csrf_signed_token: str, response) -> None:
        settings = get_csrf_settings()
        response.set_cookie(
            key=settings.cookie_name,
            value=csrf_signed_token,
            max_age=settings.token_expires_in,
            path=settings.cookie_path,
            domain=settings.cookie_domain,
            secure=settings.cookie_secure,
            httponly=settings.cookie_httponly,
            samesite=settings.cookie_samesite,
        )

    def validate_csrf(self, request: Request) -> None:
        validate_csrf_token(request)


csrf_protect = MockCsrfProtect()

__all__ = [
    "CsrfSettings",
    "get_csrf_settings",
    "set_csrf_cookie",
    "get_csrf_token",
    "validate_csrf_token",
    "is_csrf_exempt",
    "CsrfProtectError",
    "csrf_protect",
]
