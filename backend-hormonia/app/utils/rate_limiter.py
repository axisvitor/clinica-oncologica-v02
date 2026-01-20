"""
Rate limiting utility with Redis backend for production security.

SECURITY FIX: P0-01 (CVSS 9.1 - CRITICAL)
Re-enabled rate limiting to prevent DoS attacks, brute force attempts,
and API abuse.

SECURITY FIX: HIGH-001 - Webhook DDoS/Spam Protection
Added multi-layer rate limiting for webhook endpoints with global and per-phone limits.

Features:
- Redis-backed distributed rate limiting
- Multi-layer rate limiting (global + per-identifier)
- Configurable limits per endpoint type
- Rate limit headers in responses
- Automatic cleanup and token bucket algorithm
- Environment-based configuration
- Per-phone number tracking for webhook spam prevention
"""

import os
import sys
import time
from typing import Callable
from functools import wraps
from pathlib import Path

# Load .env file explicitly before any os.getenv calls
from dotenv import load_dotenv

env_file = Path(__file__).parent.parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)

from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.utils.logging import get_logger

logger = get_logger(__name__)

def _is_test_environment() -> bool:
    return bool(
        "pytest" in sys.modules
        or os.getenv("PYTEST_CURRENT_TEST")
        or os.getenv("TESTING") == "1"
        or os.getenv("APP_ENVIRONMENT", "").lower() in ("test", "testing")
    )

def get_redis_url() -> str:
    """
    Get Redis URL from environment variables with fallback.
    Supports SSL via REDIS_ENABLE_SSL environment variable.

    Returns:
        str: Redis connection URL (with rediss:// if SSL enabled)
    """
    redis_url = os.getenv("REDIS_URL")

    if not redis_url:
        # Construct from individual environment variables
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = os.getenv("REDIS_PORT", "6379")
        redis_db = os.getenv("REDIS_DB", "0")
        redis_password = os.getenv("REDIS_PASSWORD", "")

        if redis_password:
            redis_url = (
                f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
            )
        else:
            redis_url = f"redis://{redis_host}:{redis_port}/{redis_db}"

    # Convert to SSL URL if REDIS_ENABLE_SSL is true
    enable_ssl = os.getenv("REDIS_ENABLE_SSL", "false").lower() == "true"
    if enable_ssl and redis_url.startswith("redis://"):
        redis_url = "rediss://" + redis_url[8:]

    return redis_url


def get_rate_limit_storage_uri() -> str:
    """
    Get storage URI for rate limiting with test-friendly fallback.

    Priority:
    1) RATE_LIMIT_REDIS_URL / RATE_LIMIT_STORAGE_URI (explicit override)
    2) In-memory for test env unless USE_TEST_REDIS is set
    3) Standard Redis URL
    """
    override_url = os.getenv("RATE_LIMIT_REDIS_URL") or os.getenv("RATE_LIMIT_STORAGE_URI")
    if override_url:
        return override_url

    app_env = os.getenv("APP_ENVIRONMENT", "").lower()
    use_test_redis = os.getenv("USE_TEST_REDIS", "").lower() in ("1", "true", "yes")
    if app_env in ("test", "testing") and not use_test_redis:
        return "memory://"

    return get_redis_url()


# Create the real rate limiter instance with Redis backend
# SECURITY: This replaces the disabled NoOpLimiter
# NOTE: headers_enabled=False because slowapi tries to inject headers via
# kwargs.get("response") which is None when endpoint returns Pydantic model.
# This causes "parameter `response` must be an instance of Response" error.
_rate_limit_enabled = not _is_test_environment()
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=get_rate_limit_storage_uri(),
    default_limits=["60/minute"],  # Global default: 60 requests per minute
    enabled=_rate_limit_enabled,
    headers_enabled=False,  # Disabled: endpoints return Pydantic models, not Response
    swallow_errors=False,  # Raise errors on rate limit exceeded
)

# Specialized limiter for authentication endpoints (stricter limits)
auth_limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=get_rate_limit_storage_uri(),
    default_limits=["10/minute"],  # Auth endpoints: 10 requests per minute
    enabled=_rate_limit_enabled,
    headers_enabled=False,  # Disabled: endpoints return Pydantic models, not Response
    swallow_errors=False,
)

logger.info(
    "✅ Rate limiting ENABLED with Redis backend"
    if _rate_limit_enabled
    else "ℹ️  Rate limiting DISABLED in test environment"
)
if _rate_limit_enabled:
    logger.info("   Global limit: 60 requests/minute")
    logger.info("   Auth limit: 10 requests/minute")
_storage_uri = get_rate_limit_storage_uri()
logger.info(
    f"   Rate limit storage: {_storage_uri.split('@')[-1] if '@' in _storage_uri else _storage_uri}"
)


def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """
    Custom exception handler for rate limit exceeded errors.

    Args:
        request: FastAPI request object
        exc: RateLimitExceeded exception

    Returns:
        JSONResponse: Error response with rate limit information
    """
    # Extract rate limit information from the exception
    retry_after = getattr(exc, "retry_after", 60)

    logger.warning(
        f"Rate limit exceeded for {get_remote_address(request)}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "client_ip": get_remote_address(request),
            "retry_after": retry_after,
        },
    )

    return JSONResponse(
        status_code=429,
        content={
            "error": "Too Many Requests",
            "message": "Rate limit exceeded. Please try again later.",
            "retry_after": retry_after,
            "detail": str(exc),
        },
        headers={
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": str(getattr(exc, "limit", 60)),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(retry_after),
        },
    )


def get_rate_limit(limit_type: str) -> str:
    """
    Get rate limit string for a specific endpoint type.

    Args:
        limit_type: Type of endpoint (auth, api, admin, public, webhook)

    Returns:
        str: Rate limit string in format "count/period"
    """
    limits = {
        "auth": "10/minute",  # Strict for login/auth
        "api": "60/minute",  # Normal API endpoints
        "admin": "100/minute",  # Higher for admin operations
        "public": "30/minute",  # Conservative for public endpoints
        "webhook": "300/minute",  # High for webhooks
        "webhook_global": "1000/minute",  # Global webhook limit
        "webhook_per_phone": "100/minute",  # Per-phone webhook limit
    }

    return limits.get(limit_type, "60/minute")


# ============================================================================
# AI SERVICE RATE LIMITING
# ============================================================================


async def check_ai_rate_limit(
    service_name: str = "gemini",
    max_requests: int = 60,
    window_seconds: int = 60,
) -> tuple[bool, int]:
    """
    Check rate limit for AI service calls.

    Args:
        service_name: Name of the AI service (gemini, openai, etc.)
        max_requests: Maximum requests allowed in window (default: 60 RPM)
        window_seconds: Time window in seconds (default: 60)

    Returns:
        tuple: (allowed: bool, retry_after: int)
    """
    key = f"rate_limit:ai:{service_name}"
    return await check_rate_limit_redis(key, max_requests, window_seconds)


class AIRateLimitExceeded(Exception):
    """Raised when AI rate limit is exceeded."""

    def __init__(self, retry_after: int = 60, service: str = "gemini"):
        self.retry_after = retry_after
        self.service = service
        super().__init__(
            f"AI rate limit exceeded for {service}. Retry after {retry_after}s."
        )


# ============================================================================
# MULTI-LAYER RATE LIMITING (HIGH-001 FIX)
# ============================================================================


async def get_redis_client():
    """
    Get Redis client for manual rate limiting.

    Returns:
        Redis client or None if unavailable
    """
    try:
        import redis.asyncio as redis

        redis_url = get_rate_limit_storage_uri()
        if redis_url.startswith("memory://"):
            return None
        client = redis.from_url(redis_url, decode_responses=True)
        return client
    except Exception as e:
        logger.warning(f"Redis client unavailable for rate limiting: {e}")
        return None


async def check_rate_limit_redis(
    key: str, max_requests: int, window_seconds: int, redis_client=None
) -> tuple[bool, int]:
    """
    Check rate limit using Redis sliding window.

    Args:
        key: Redis key for rate limit tracking
        max_requests: Maximum requests allowed in window
        window_seconds: Time window in seconds
        redis_client: Redis client (optional, will create if not provided)

    Returns:
        tuple: (allowed: bool, retry_after: int)
    """
    if not redis_client:
        redis_client = await get_redis_client()
        if not redis_client:
            # Fail open if Redis unavailable
            logger.warning("Rate limiting unavailable - Redis not connected")
            return True, 0

    try:
        current_time = int(time.time())
        window_start = current_time - window_seconds

        # Use Redis sorted set for sliding window
        pipe = redis_client.pipeline()

        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)

        # Add current request
        pipe.zadd(key, {str(current_time): current_time})

        # Count requests in window
        pipe.zcard(key)

        # Set expiration
        pipe.expire(key, window_seconds)

        results = await pipe.execute()
        request_count = results[2]

        if request_count > max_requests:
            retry_after = window_seconds
            logger.warning(
                f"Rate limit exceeded for {key}: {request_count}/{max_requests} requests",
                extra={
                    "rate_limit_key": key,
                    "request_count": request_count,
                    "max_requests": max_requests,
                    "window_seconds": window_seconds,
                },
            )
            return False, retry_after

        return True, 0

    except Exception as e:
        logger.error(f"Error checking rate limit: {e}", exc_info=True)
        # Fail open on error
        return True, 0


def multi_layer_rate_limit(
    global_limit: int = 1000,
    global_window: int = 60,
    identifier_limit: int = 100,
    identifier_window: int = 60,
    identifier_key: str = "phone",
):
    """
    Decorator for multi-layer rate limiting (global + per-identifier).

    HIGH-001 FIX: Prevents DDoS/spam attacks on webhook endpoints.

    Args:
        global_limit: Global requests per window (default: 1000/minute)
        global_window: Global window in seconds (default: 60)
        identifier_limit: Per-identifier requests per window (default: 100/minute)
        identifier_window: Per-identifier window in seconds (default: 60)
        identifier_key: Request field to use as identifier (default: "phone")

    Example:
        @router.post("/webhooks/whatsapp")
        @multi_layer_rate_limit(
            global_limit=1000,
            identifier_limit=100,
            identifier_key="phone"
        )
        async def webhook(request: Request):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request:
                request = kwargs.get("request")

            if not request:
                logger.warning("Rate limit decorator: Request object not found")
                return await func(*args, **kwargs)

            redis_client = await get_redis_client()

            # Layer 1: Global rate limit (all requests)
            global_key = "rate_limit:webhook:global"
            allowed, retry_after = await check_rate_limit_redis(
                global_key, global_limit, global_window, redis_client
            )

            if not allowed:
                logger.warning(
                    "Global webhook rate limit exceeded",
                    extra={
                        "limit": global_limit,
                        "window": global_window,
                        "path": request.url.path,
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Too Many Requests",
                        "message": f"Global rate limit exceeded: {global_limit} requests per {global_window}s",
                        "retry_after": retry_after,
                        "scope": "global",
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(global_limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(time.time()) + retry_after),
                        "X-RateLimit-Scope": "global",
                    },
                )

            # Layer 2: Per-identifier rate limit (e.g., per phone number)
            identifier_value = None

            try:
                # Try to extract identifier from request body
                body = await request.json()

                # Support nested identifier paths (e.g., "data.phone")
                if "." in identifier_key:
                    keys = identifier_key.split(".")
                    value = body
                    for key in keys:
                        value = value.get(key, {})
                    identifier_value = value if isinstance(value, str) else None
                else:
                    identifier_value = body.get(identifier_key)

                # Also check common webhook patterns
                if not identifier_value:
                    # Try data.key pattern (Evolution API format)
                    data = body.get("data", {})
                    identifier_value = data.get("key", {}).get("remoteJid")

                    # Try phone extraction from remoteJid
                    if identifier_value and "@" in identifier_value:
                        identifier_value = identifier_value.split("@")[0]

            except Exception as e:
                logger.debug(f"Could not extract identifier from request: {e}")

            if identifier_value:
                # Sanitize identifier (keep only alphanumeric)
                identifier_value = "".join(
                    c for c in str(identifier_value) if c.isalnum()
                )

                identifier_rate_key = f"rate_limit:webhook:phone:{identifier_value}"
                allowed, retry_after = await check_rate_limit_redis(
                    identifier_rate_key,
                    identifier_limit,
                    identifier_window,
                    redis_client,
                )

                if not allowed:
                    logger.warning(
                        f"Per-phone webhook rate limit exceeded for {identifier_value}",
                        extra={
                            "identifier": identifier_value,
                            "limit": identifier_limit,
                            "window": identifier_window,
                            "path": request.url.path,
                        },
                    )
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail={
                            "error": "Too Many Requests",
                            "message": f"Rate limit exceeded for this phone number: {identifier_limit} requests per {identifier_window}s",
                            "retry_after": retry_after,
                            "scope": "phone",
                        },
                        headers={
                            "Retry-After": str(retry_after),
                            "X-RateLimit-Limit": str(identifier_limit),
                            "X-RateLimit-Remaining": "0",
                            "X-RateLimit-Reset": str(int(time.time()) + retry_after),
                            "X-RateLimit-Scope": "phone",
                        },
                    )

            # Close Redis connection
            if redis_client:
                try:
                    await redis_client.aclose()  # Redis 5.x uses aclose() for async
                except Exception:
                    pass  # Ignore close errors (connection may already be closed)

            # All rate limits passed - execute the function
            return await func(*args, **kwargs)

        return wrapper

    return decorator
