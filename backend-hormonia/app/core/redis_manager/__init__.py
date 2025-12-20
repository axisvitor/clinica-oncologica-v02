"""
Redis Manager Package - Unified Redis Client Management

Provides both async and sync Redis interfaces with automatic compatibility detection.
Manages connection pooling, error handling, and proper resource cleanup.

Main exports:
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
- create_redis_ssl_context: Create SSL context for Redis connections
- get_redis_connection_kwargs: Get kwargs for redis.from_url with SSL support
"""

import ssl
from typing import Dict, Any, Optional

from .manager import RedisManager, REDIS_CA_CERT_PATH
from .firebase_cache import FirebaseRedisCache
from .async_client import (
    get_async_redis_client,
    redis_transaction,
    cleanup_redis_connections,
    redis_health_check,
)
from .sync_client import get_sync_redis_client, get_compatible_redis_client
from .utils import get_redis_manager, get_cache_redis_manager, get_broker_redis_manager
from app.config import settings


def create_redis_ssl_context() -> Optional[ssl.SSLContext]:
    """
    Create SSL context for Redis connections.

    Respects REDIS_SSL_CERT_REQS and REDIS_ENABLE_SSL settings.

    Returns:
        SSLContext if SSL is enabled, None otherwise
    """
    if not getattr(settings, "REDIS_ENABLE_SSL", False):
        return None

    ssl_cert_reqs = getattr(settings, "REDIS_SSL_CERT_REQS", "required").lower()

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

    if ssl_cert_reqs == "none":
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    else:
        if REDIS_CA_CERT_PATH.exists():
            ssl_context.load_verify_locations(cafile=str(REDIS_CA_CERT_PATH))
        else:
            ssl_context.load_default_certs()
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED

    return ssl_context


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

    # Import version detection from manager
    from .manager import REDIS_6_OR_HIGHER

    if REDIS_6_OR_HIGHER:
        # redis-py 6.x: use ssl_context parameter for both sync and async
        ssl_context = create_redis_ssl_context()
        if ssl_context:
            kwargs["ssl_context"] = ssl_context
    else:
        # redis-py 5.x: use ssl_cert_reqs parameter
        if ssl_cert_reqs == "none":
            kwargs["ssl_cert_reqs"] = "none"
        else:
            kwargs["ssl_cert_reqs"] = "required"
            if REDIS_CA_CERT_PATH.exists():
                kwargs["ssl_ca_certs"] = str(REDIS_CA_CERT_PATH)

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
    # Client functions
    "get_async_redis_client",
    "get_sync_redis_client",
    "get_compatible_redis_client",
    # Utilities
    "redis_transaction",
    "cleanup_redis_connections",
    "redis_health_check",
    # SSL helpers
    "create_redis_ssl_context",
    "get_redis_connection_kwargs",
    "get_redis_url_with_ssl",
    "REDIS_CA_CERT_PATH",
]
