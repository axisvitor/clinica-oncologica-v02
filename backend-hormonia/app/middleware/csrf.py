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

from fastapi import Request
from fastapi_csrf_protect import CsrfProtect
from fastapi_csrf_protect.exceptions import CsrfProtectError
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import logging
import hmac
import hashlib
import time
import base64
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Rate limiting for failed CSRF validation attempts
_csrf_validation_failures = defaultdict(list)


class CsrfSettings(BaseSettings):
    """
    CSRF protection configuration.

    Attributes:
        secret_key: Secret key for token generation (REQUIRED from env)
        cookie_name: Name of CSRF cookie (default: "fastapi-csrf-token")
        cookie_samesite: SameSite cookie policy (strict/lax/none)
        cookie_secure: Require HTTPS for cookie transmission
        cookie_httponly: Prevent JavaScript access to cookie
        cookie_path: Cookie path scope
        cookie_domain: Cookie domain scope (None = auto)
        token_header_name: HTTP header name for CSRF token
        token_expires_in: Token expiration time in seconds
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
    """
    Load CSRF settings from application configuration.

    Returns:
        CsrfSettings: Configured CSRF protection settings

    Raises:
        ValueError: If CSRF_SECRET_KEY is not configured
    """
    from app.config import settings

    # Validate secret key exists and is not a placeholder
    csrf_secret = getattr(settings, 'CSRF_SECRET_KEY', None)
    if not csrf_secret:
        raise ValueError(
            "CSRF_SECRET_KEY is required in .env for CSRF protection. "
            "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )

    # Validate secret key strength (minimum 32 bytes for HMAC-SHA256)
    if len(csrf_secret) < 32:
        raise ValueError(
            "CSRF_SECRET_KEY must be at least 32 characters for cryptographic security. "
            "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )

    # Use secure cookies only in production
    is_production = getattr(settings, 'ENVIRONMENT', 'development').lower() == 'production'
    cookie_secure = is_production or getattr(settings, 'SESSION_COOKIE_SECURE', False)

    # SECURITY FIX: Use 'strict' for maximum CSRF protection in both dev and production
    # This prevents all cross-origin cookie transmission, providing the strongest defense
    # Note: If frontend/backend are on different domains, consider using separate auth mechanism
    cookie_samesite = "strict"

    logger.info(
        f"CSRF Protection initialized: "
        f"secure={cookie_secure}, "
        f"samesite={cookie_samesite}, "
        f"httponly=True, "
        f"hmac_validation=enabled"
    )

    return CsrfSettings(
        secret_key=csrf_secret,
        cookie_secure=cookie_secure,
        cookie_samesite=cookie_samesite,
        cookie_httponly=True
    )


# Configure CSRF protection with settings loader
@CsrfProtect.load_config
def get_csrf_config():
    """
    Configuration loader for fastapi-csrf-protect.

    This function is called automatically by the library to load settings.
    """
    return get_csrf_settings()


def create_csrf_protect() -> CsrfProtect:
    """
    Factory function to create CsrfProtect instance.

    Returns:
        CsrfProtect: Configured CSRF protection instance
    """
    return CsrfProtect()


# Singleton instance for dependency injection
csrf_protect = create_csrf_protect()


def set_csrf_cookie(request: Request, response, token: str = None):
    """
    Set CSRF cookie in response.

    Helper function to set CSRF cookie with proper security headers.
    Should be called after successful login or when issuing new CSRF token.

    Args:
        request: FastAPI request object
        response: FastAPI response object to set cookie on
        token: Optional pre-generated token to use (if None, generates new one)

    Example:
        @router.post("/login")
        async def login(response: Response):
            # ... authentication logic ...
            set_csrf_cookie(request, response)
            return {"message": "logged in"}
    """
    try:
        if token is None:
            # Generate new token if none provided
            token = csrf_protect.generate_csrf(request)
            # Handle array format if returned
            if isinstance(token, (list, tuple)) and len(token) >= 2:
                token = token[1]  # Use signed token
        
        # Set the cookie with the token
        csrf_protect.set_csrf_cookie(token, response)
        logger.debug("CSRF cookie set successfully")
    except Exception as e:
        logger.error(f"Failed to set CSRF cookie: {str(e)}")
        raise


def get_csrf_token(request: Request) -> str:
    """
    Generate and return CSRF token for the current request.

    Args:
        request: FastAPI request object

    Returns:
        str: CSRF token to be included in form/request

    Example:
        @router.get("/form")
        async def get_form(request: Request):
            token = get_csrf_token(request)
            return {"csrf_token": token}
    """
    try:
        # Generate token from request context
        token = csrf_protect.generate_csrf(request)
        
        # FIX: fastapi-csrf-protect sometimes returns a tuple/list [token_id, signed_token]
        # We need the signed token (second element) for validation
        if isinstance(token, (list, tuple)) and len(token) >= 2:
            return token[1]  # Return the signed token
        elif isinstance(token, str):
            return token
        else:
            logger.error(f"Unexpected CSRF token format: {type(token)} - {token}")
            raise ValueError(f"Invalid CSRF token format: {type(token)}")
            
    except Exception as e:
        logger.error(f"Failed to generate CSRF token: {str(e)}")
        raise


def _validate_token_signature(token: str, secret_key: str, max_age: int = 3600) -> bool:
    """
    Cryptographically validate CSRF token signature using HMAC-SHA256.

    SECURITY FIX (CVE-2025-CLINIC-004): Implements proper signature validation
    to prevent token forgery attacks. Previously only checked format, now validates
    cryptographic signature and expiration.

    Token format: {timestamp}.{random_data}.{hmac_signature}

    Args:
        token: CSRF token to validate
        secret_key: Secret key for HMAC verification
        max_age: Maximum token age in seconds (default: 3600 = 1 hour)

    Returns:
        bool: True if token is valid and not expired, False otherwise

    Security features:
        - HMAC-SHA256 signature verification
        - Constant-time comparison (prevents timing attacks)
        - Token expiration validation
        - Format validation
    """
    try:
        # Parse token format: {timestamp}.{random_data}.{signature}
        parts = token.split('.')
        if len(parts) < 2:
            logger.warning(f"CSRF token format invalid: expected at least 2 parts, got {len(parts)}")
            return False

        # Extract components (signature is last part, rest is data)
        signature = parts[-1]
        data = '.'.join(parts[:-1])

        # Verify HMAC signature using constant-time comparison
        expected_signature = hmac.new(
            secret_key.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # SECURITY: Use constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(signature, expected_signature):
            logger.warning("CSRF token signature verification failed")
            return False

        # Extract and validate timestamp (first part of token)
        try:
            timestamp_str = parts[0]
            # Handle both integer timestamps and base64-encoded timestamps
            try:
                timestamp = int(timestamp_str)
            except ValueError:
                # Try decoding base64 if not a plain integer
                decoded = base64.b64decode(timestamp_str.encode()).decode()
                timestamp = int(decoded)

            # Verify token hasn't expired
            current_time = int(time.time())
            token_age = current_time - timestamp

            if token_age > max_age:
                logger.warning(f"CSRF token expired: age={token_age}s, max_age={max_age}s")
                return False

            if token_age < -60:  # Allow 60 seconds clock skew
                logger.warning(f"CSRF token from future: age={token_age}s")
                return False

        except (ValueError, IndexError) as e:
            logger.warning(f"CSRF token timestamp validation failed: {e}")
            return False

        return True

    except Exception as e:
        logger.error(f"CSRF token validation error: {e}", exc_info=True)
        return False


def _check_rate_limit(client_ip: str, max_failures: int = 10, window: int = 300) -> bool:
    """
    Rate limiting for CSRF validation failures to prevent brute force attacks.

    Args:
        client_ip: Client IP address
        max_failures: Maximum failures allowed in time window
        window: Time window in seconds (default: 300 = 5 minutes)

    Returns:
        bool: True if rate limit exceeded, False otherwise
    """
    current_time = time.time()

    # Clean old entries
    _csrf_validation_failures[client_ip] = [
        timestamp for timestamp in _csrf_validation_failures[client_ip]
        if current_time - timestamp < window
    ]

    # Check if rate limit exceeded
    failure_count = len(_csrf_validation_failures[client_ip])
    if failure_count >= max_failures:
        logger.warning(
            f"CSRF rate limit exceeded for IP {client_ip}: "
            f"{failure_count} failures in {window}s"
        )
        return True

    return False


def _record_validation_failure(client_ip: str):
    """
    Record a CSRF validation failure for rate limiting.

    Args:
        client_ip: Client IP address
    """
    _csrf_validation_failures[client_ip].append(time.time())


async def validate_csrf_token(request: Request):
    """
    Validate CSRF token from request headers with cryptographic signature verification.

    SECURITY FIX (CVE-2025-CLINIC-004): Enhanced validation with HMAC signature check,
    expiration validation, and rate limiting. Removes insecure format-only validation.

    Dependency function for route protection.
    Raises CsrfProtectError if validation fails.

    Args:
        request: FastAPI request object

    Raises:
        CsrfProtectError: If CSRF token is missing or invalid

    Example:
        @router.post("/protected", dependencies=[Depends(validate_csrf_token)])
        async def protected_route():
            return {"message": "protected"}

    Security features:
        - Primary validation via fastapi-csrf-protect library
        - Fallback validation with HMAC-SHA256 signature check
        - Token expiration validation (1 hour default)
        - Rate limiting for failed validations
        - Security event logging
    """
    client_ip = request.client.host if request.client else "unknown"

    # Check rate limit before validation
    if _check_rate_limit(client_ip):
        logger.error(
            f"CSRF validation rate limit exceeded for {client_ip}",
            extra={
                "client_ip": client_ip,
                "path": request.url.path,
                "user_agent": request.headers.get("user-agent", "unknown"),
                "security_event": "CSRF_RATE_LIMIT_EXCEEDED"
            }
        )
        raise CsrfProtectError("Too many failed CSRF validation attempts. Please try again later.")

    try:
        # Primary validation using fastapi-csrf-protect library
        await csrf_protect.validate_csrf(request)
        logger.debug(f"CSRF validation successful for {request.url.path}")
        return

    except CsrfProtectError as e:
        # SECURE FALLBACK: For cross-domain Railway deployment with proper signature validation
        csrf_header = request.headers.get("X-CSRF-Token")
        csrf_cookie = request.cookies.get("fastapi-csrf-token")

        if csrf_header and not csrf_cookie and "Missing Cookie" in str(e):
            # Cross-domain scenario: validate token signature cryptographically
            logger.debug(f"CSRF validation using secure header-only mode for {request.url.path}")

            # Get secret key for signature validation
            settings = get_csrf_settings()
            secret_key = settings.secret_key

            # SECURITY FIX: Cryptographic validation instead of format check
            if _validate_token_signature(csrf_header, secret_key, max_age=settings.token_expires_in):
                logger.info(
                    f"CSRF validation successful (secure header-only mode) for {request.url.path}",
                    extra={
                        "client_ip": client_ip,
                        "path": request.url.path,
                        "validation_mode": "header_hmac",
                        "security_event": "CSRF_VALIDATED_HEADER_HMAC"
                    }
                )
                return  # Token is cryptographically valid
            else:
                # Signature validation failed
                logger.error(
                    f"CSRF token signature validation failed for {request.url.path}",
                    extra={
                        "client_ip": client_ip,
                        "user_agent": request.headers.get("user-agent", "unknown"),
                        "path": request.url.path,
                        "security_event": "CSRF_SIGNATURE_INVALID"
                    }
                )
                _record_validation_failure(client_ip)
                raise CsrfProtectError("CSRF token signature verification failed")

        # Log validation failure with security context
        logger.warning(
            f"CSRF validation failed for {request.url.path}: {str(e)}",
            extra={
                "client_ip": client_ip,
                "user_agent": request.headers.get("user-agent", "unknown"),
                "has_csrf_header": bool(csrf_header),
                "has_csrf_cookie": bool(csrf_cookie),
                "error_type": type(e).__name__,
                "security_event": "CSRF_VALIDATION_FAILED"
            }
        )

        # Record failure for rate limiting
        _record_validation_failure(client_ip)

        # Raise original error
        raise


def is_csrf_exempt(path: str) -> bool:
    """
    Check if path is exempt from CSRF protection.

    Exempt paths (GET/HEAD/OPTIONS are always exempt):
    - /session/validate (read-only)
    - /session/active (read-only)
    - /session/stats (read-only)
    - /api/v2/csrf-token (token generation endpoint)

    Args:
        path: Request path to check

    Returns:
        bool: True if path is exempt, False otherwise
    """
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


__all__ = [
    'CsrfSettings',
    'get_csrf_settings',
    'get_csrf_config',
    'create_csrf_protect',
    'csrf_protect',
    'set_csrf_cookie',
    'get_csrf_token',
    'validate_csrf_token',
    'is_csrf_exempt',
    'CsrfProtectError'
]
