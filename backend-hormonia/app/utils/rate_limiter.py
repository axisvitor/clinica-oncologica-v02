"""
Rate limiting utility for authentication endpoints.

Implements Redis-based rate limiting to prevent brute force attacks
and abuse of authentication endpoints.
"""
from typing import Callable
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


def get_client_ip(request: Request) -> str:
    """
    Get client IP address from request.

    Considers X-Forwarded-For header for proxy/load balancer scenarios.
    Falls back to direct client IP if no proxy headers are present.

    Args:
        request: FastAPI Request object

    Returns:
        Client IP address as string
    """
    # Check X-Forwarded-For header (standard proxy header)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # X-Forwarded-For can contain multiple IPs (client, proxy1, proxy2, ...)
        # We want the first one (original client)
        return forwarded.split(",")[0].strip()

    # Check X-Real-IP header (alternative proxy header)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fallback to direct client host
    if request.client:
        return request.client.host

    # Last resort fallback
    return "unknown"


# Determine storage backend based on Redis availability
def _get_storage_uri() -> str:
    """
    Get storage URI for rate limiter.

    Uses Redis if configured, falls back to in-memory storage.
    Raises RuntimeError if in production without Redis.

    Returns:
        Storage URI string for slowapi

    Raises:
        RuntimeError: If in production environment without Redis configured
    """
    # Check if Redis is properly configured
    has_redis = settings.REDIS_URL and settings.REDIS_URL != "rediss://localhost:6379"

    if has_redis:
        logger.info("Using Redis for rate limiting")
        return settings.REDIS_URL

    # Production safety check
    is_production = getattr(settings, 'ENVIRONMENT', '').lower() in ('production', 'prod')
    if is_production:
        raise RuntimeError(
            "Redis is required for rate limiting in production environment. "
            "In-memory storage is not suitable for multi-worker deployments. "
            "Please configure REDIS_URL environment variable."
        )

    logger.warning("Redis not configured, using in-memory rate limiting (not suitable for production)")
    return "memory://"


# Initialize rate limiter
limiter = Limiter(
    key_func=get_client_ip,
    default_limits=["100/minute"],  # Global default: 100 requests per minute
    storage_uri=_get_storage_uri(),
    strategy="fixed-window"  # Fixed time window strategy
)


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Custom handler for rate limit exceeded errors.

    Returns standardized JSON error response with retry information.

    Args:
        request: FastAPI Request that triggered the rate limit
        exc: RateLimitExceeded exception

    Returns:
        JSONResponse with error details and retry information
    """
    client_ip = get_client_ip(request)
    logger.warning(
        f"Rate limit exceeded for IP {client_ip} on {request.method} {request.url.path}",
        extra={
            "client_ip": client_ip,
            "path": str(request.url.path),
            "method": request.method
        }
    )

    return JSONResponse(
        status_code=429,
        content={
            "error": "too_many_requests",
            "message": "Muitas tentativas. Tente novamente mais tarde.",
            "retry_after": exc.detail,
            "limit": str(exc.detail) if exc.detail else "unknown"
        }
    )


# Rate limit configurations for different endpoint types
RATE_LIMITS = {
    "login": "5/minute",              # 5 login attempts per minute per IP
    "password_reset": "3/hour",       # 3 password reset requests per hour
    "password_change": "3/hour",      # 3 password change attempts per hour
    "token_refresh": "20/minute",     # 20 token refreshes per minute
    "registration": "3/hour",         # 3 registration attempts per hour
    "email_verification": "5/hour",   # 5 email verification requests per hour
    "avatar_upload": "10/hour",       # 10 avatar uploads per hour
    "profile_update": "20/hour"       # 20 profile updates per hour
}


def get_rate_limit(limit_type: str) -> str:
    """
    Get rate limit string for a specific endpoint type.

    Args:
        limit_type: Type of endpoint (e.g., 'login', 'password_reset')

    Returns:
        Rate limit string (e.g., '5/minute')
    """
    return RATE_LIMITS.get(limit_type, "100/minute")
