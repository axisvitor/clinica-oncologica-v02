"""
Redis Manager Package - Unified Redis Client Management

Provides both async and sync Redis interfaces with automatic compatibility detection.
Manages connection pooling, error handling, and proper resource cleanup.

- RedisManager: Core manager class
- FirebaseRedisCache: 3-layer caching system for Firebase authentication
- get_redis_manager: Get or create global Redis manager instance
- get_cache_redis_manager: Get Redis manager for cache operations
- get_broker_redis_manager: Get Redis manager for Celery broker operations
- get_async_redis_client: Get async Redis client
- get_sync_redis_client: Get sync Redis client
- get_compatible_redis_client: Get Redis client with automatic compatibility
- redis_transaction: Async context manager for Redis transactions
- cleanup_redis_connections: Cleanup all Redis connections
- redis_health_check: Perform Redis health check
- get_redis_connection_kwargs: Get kwargs for redis.from_url with SSL support
"""

from typing import Dict, Any

from .manager import RedisManager
from .firebase_cache import FirebaseRedisCache
from .async_client import (
    get_async_redis_client,
    redis_transaction,
    cleanup_redis_connections,
    redis_health_check,
)
from .sync_client import get_sync_redis_client, get_compatible_redis_client
from .utils import (
    get_redis_manager,
    get_cache_redis_manager,
    get_broker_redis_manager,
    build_redis_url_for_db,
)
from app.config import settings


def get_redis_connection_kwargs(
    decode_responses: bool = True,
    socket_timeout: float = 5.0,
    socket_connect_timeout: float = 3.0,
    mode: str = "async",
    **extra_kwargs,
) -> Dict[str, Any]:
    """
    Get connection kwargs for redis.from_url() with proper SSL configuration.

    Use this when you need to create a Redis connection directly via from_url().

    Args:
        decode_responses: Whether to decode responses to strings
        socket_timeout: Socket timeout in seconds
        socket_connect_timeout: Connection timeout in seconds
        mode: "async" (default) or "sync" - affects SSL configuration
        **extra_kwargs: Additional kwargs to pass to from_url()

    Returns:
        Dict of kwargs to pass to redis.from_url()

    Example:
        from app.core.redis_manager import get_redis_connection_kwargs, get_redis_url_with_ssl
        import redis.asyncio as redis

        url = get_redis_url_with_ssl()
        kwargs = get_redis_connection_kwargs(mode="async")
        client = redis.from_url(url, **kwargs)
    """
    kwargs = {
        "decode_responses": decode_responses,
        "socket_timeout": socket_timeout,
        "socket_connect_timeout": socket_connect_timeout,
        **extra_kwargs,
    }

    if not getattr(settings, "REDIS_ENABLE_SSL", False):
        return kwargs

    ssl_cert_reqs = getattr(settings, "REDIS_SSL_CERT_REQS", "required").lower()

    # Use ssl_cert_reqs parameter (works universally with from_url() in redis-py 5.x and 6.x)
    kwargs["ssl_cert_reqs"] = ssl_cert_reqs

    return kwargs


def get_redis_url_with_ssl() -> str:
    """
    Get Redis URL with proper scheme based on SSL settings.

    Returns:
        Redis URL (rediss:// if SSL enabled, redis:// otherwise)
    """
    redis_url = settings.REDIS_URL

    if getattr(settings, "REDIS_ENABLE_SSL", False):
        if redis_url.startswith("redis://"):
            return "rediss://" + redis_url[8:]
    else:
        if redis_url.startswith("rediss://"):
            return "redis://" + redis_url[9:]

    return redis_url


__all__ = [
    # Classes
    "RedisManager",
    "FirebaseRedisCache",
    # Manager functions
    "get_redis_manager",
    "get_cache_redis_manager",
    "get_broker_redis_manager",
    "build_redis_url_for_db",
    # Client functions
    "get_async_redis_client",
    "get_sync_redis_client",
    "get_compatible_redis_client",
    # Utilities
    "redis_transaction",
    "cleanup_redis_connections",
    "redis_health_check",
    # SSL helpers
    "get_redis_connection_kwargs",
    "get_redis_url_with_ssl",
]
