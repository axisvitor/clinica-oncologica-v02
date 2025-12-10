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
from typing import Optional, Union, Tuple
import logging
import hmac
import hashlib
import time
import base64
import secrets
from collections import defaultdict

logger = logging.getLogger(__name__)

# Rate limiting for failed CSRF validation attempts
_csrf_validation_failures = defaultdict(list)


class CsrfSettings(BaseSettings):
    """
    CSRF protection configuration.
    """
    secret_key: str = Field(
        ...,
        description="Secret key for CSRF token generation (from CSRF_SECRET_KEY env var)"
    )
    cookie_name: str = Field(
        default="fastapi-csrf-token",
        description="Name of the CSRF cookie"
    )
    cookie_samesite: str = Field(
        default="strict",
        description="SameSite cookie policy: strict (recommended), lax, or none"
    )
    cookie_secure: bool = Field(
        default=True,
        description="Require HTTPS for cookie transmission (must be True in production)"
    )
    cookie_httponly: bool = Field(
        default=True,
        description="Prevent JavaScript access to CSRF cookie"
    )
    cookie_path: str = Field(
        default="/",
        description="Cookie path scope"
    )
    cookie_domain: Optional[str] = Field(
        default=None,
        description="Cookie domain scope (None = auto-detect from request)"
    )
    token_header_name: str = Field(
        default="X-CSRF-Token",
        description="HTTP header name for CSRF token in requests"
    )
    token_expires_in: int = Field(
        default=3600,
        description="CSRF token expiration time in seconds (1 hour default)"
    )

    model_config = SettingsConfigDict(extra="ignore")


def get_csrf_settings() -> CsrfSettings:
    """Load CSRF settings from application configuration."""
    from app.config import settings

    # Validate secret key exists
    csrf_secret = getattr(settings, 'CSRF_SECRET_KEY', None)
    if not csrf_secret:
        # Fallback for development if not set, but warn
        logger.warning("CSRF_SECRET_KEY not set. Using temporary random key.")
        csrf_secret = secrets.token_urlsafe(32)

    # Use secure cookies only in production
    is_production = getattr(settings, 'ENVIRONMENT', 'development').lower() == 'production'
    cookie_secure = is_production or getattr(settings, 'SESSION_COOKIE_SECURE', False)
    
    # SECURITY FIX: Use 'strict' for maximum CSRF protection
    cookie_samesite = "strict"

    return CsrfSettings(
        secret_key=csrf_secret,
        cookie_secure=cookie_secure,
        cookie_samesite=cookie_samesite,
        cookie_httponly=True
    )


# Exception for CSRF errors (backward compatibility wrapper)
class CsrfProtectError(HTTPException):
    def __init__(self, detail: str = "CSRF validation failed"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _generate_token_signature(data: str, secret_key: str) -> str:
    """Generate HMAC-SHA256 signature for data."""
    return hmac.new(
        secret_key.encode('utf-8'),
        data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def generate_csrf_token(secret_key: str) -> str:
    """
    Generate a new signed CSRF token.
    Format: {timestamp}.{random_data}.{hmac_signature}
    """
    timestamp = str(int(time.time()))
    random_data = secrets.token_hex(16)
    data = f"{timestamp}.{random_data}"
    signature = _generate_token_signature(data, secret_key)
    return f"{data}.{signature}"


def set_csrf_cookie(request: Request, response, token: str = None):
    """
    Set CSRF cookie in response with proper security flags.
    """
    try:
        settings = get_csrf_settings()
        
        if token is None:
            token = generate_csrf_token(settings.secret_key)
            
        response.set_cookie(
            key=settings.cookie_name,
            value=token,
            max_age=settings.token_expires_in,
            path=settings.cookie_path,
            domain=settings.cookie_domain,
            secure=settings.cookie_secure,
            httponly=settings.cookie_httponly,
            samesite=settings.cookie_samesite
        )
        logger.debug("CSRF cookie set successfully")
    except Exception as e:
        logger.error(f"Failed to set CSRF cookie: {str(e)}")
        raise


def get_csrf_token(request: Request) -> str:
    """Generate and return CSRF token for the current request."""
    settings = get_csrf_settings()
    return generate_csrf_token(settings.secret_key)


def _validate_token_signature(token: str, secret_key: str, max_age: int = 3600) -> bool:
    """
    Validate CSRF token format, expiration and signature.
    """
    try:
        parts = token.split('.')
        if len(parts) < 3:
            return False

        signature = parts[-1]
        data = '.'.join(parts[:-1])
        
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


def _check_rate_limit(client_ip: str, max_failures: int = 10, window: int = 300) -> bool:
    """Rate limitation for failed validations."""
    current_time = time.time()
    # Clean old entries
    _csrf_validation_failures[client_ip] = [
        t for t in _csrf_validation_failures[client_ip]
        if current_time - t < window
    ]
    
    if len(_csrf_validation_failures[client_ip]) >= max_failures:
        logger.warning(f"CSRF rate limit exceeded for IP {client_ip}")
        return True
    return False


async def validate_csrf_token(request: Request):
    """
    Validate CSRF token from headers (Double Submit Cookie pattern).
    Raises CsrfProtectError if validation fails.
    """
    settings = get_csrf_settings()
    client_ip = request.client.host if request.client else "unknown"

    if _check_rate_limit(client_ip):
         raise CsrfProtectError("Too many failed CSRF validation attempts.")

    # Get token from header
    csrf_header = request.headers.get(settings.token_header_name)
    if not csrf_header:
        # Check alternative headers
        for h in ["X-CSRFToken", "X-XSRF-Token"]:
            csrf_header = request.headers.get(h)
            if csrf_header:
                break
    
    if not csrf_header:
        logger.warning(f"CSRF token missing in headers for {request.url.path}")
        _csrf_validation_failures[client_ip].append(time.time())
        raise CsrfProtectError("Missing CSRF token in headers")

    # Validate signature of header token
    if not _validate_token_signature(csrf_header, settings.secret_key, settings.token_expires_in):
        logger.warning(f"CSRF token invalid signature or expired for {request.url.path}")
        _csrf_validation_failures[client_ip].append(time.time())
        raise CsrfProtectError("Invalid CSRF token")

    # Double Submit Cookie Check
    # Verify that the CSRF cookie exists and matches the header token
    # This enforces the Double Submit Cookie pattern for CSRF protection

    csrf_cookie = request.cookies.get(settings.cookie_name)
    if not csrf_cookie:
        logger.warning(f"CSRF cookie missing for {request.url.path}")
        _csrf_validation_failures[client_ip].append(time.time())
        raise CsrfProtectError("Missing CSRF cookie")

    # Validate cookie signature
    if not _validate_token_signature(csrf_cookie, settings.secret_key, settings.token_expires_in):
        logger.warning(f"CSRF cookie has invalid signature or is expired for {request.url.path}")
        _csrf_validation_failures[client_ip].append(time.time())
        raise CsrfProtectError("Invalid CSRF cookie")

    # Verify header and cookie tokens match (Double Submit Cookie pattern)
    if not hmac.compare_digest(csrf_header, csrf_cookie):
        logger.warning(f"CSRF header and cookie mismatch for {request.url.path}")
        _csrf_validation_failures[client_ip].append(time.time())
        raise CsrfProtectError("CSRF token mismatch")

    logger.debug(f"CSRF validation successful for {request.url.path}")


def is_csrf_exempt(path: str) -> bool:
    """Check if path is exempt from CSRF protection."""
    exempt_paths = [
        "/session/validate",
        "/session/active",
        "/session/stats",
        "/api/v2/csrf-token",
        "/docs",
        "/redoc", 
        "/openapi.json"
    ]
    return any(path.startswith(exempt) for exempt in exempt_paths)

# Backward compatibility (dummy object for load_config decorator if used elsewhere)
class MockCsrfProtect:
    def load_config(self, f):
        return f

csrf_protect = MockCsrfProtect()

__all__ = [
    'CsrfSettings',
    'get_csrf_settings',
    'set_csrf_cookie',
    'get_csrf_token',
    'validate_csrf_token',
    'is_csrf_exempt',
    'CsrfProtectError',
    'csrf_protect'
]
