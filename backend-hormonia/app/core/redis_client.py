"""
Redis client module - Unified interface for Redis connections.

This module provides a clean, consistent interface for accessing Redis clients
throughout the application. It wraps the RedisManager to provide both sync and
async clients with proper connection pooling and error handling.

UPDATED: Now directly imports from redis_manager (2025-12-19)
- All functionality delegated to RedisManager
- Backward compatibility maintained
- Proper error handling and logging

Usage:
    from app.core.redis_client import get_redis_client, get_async_redis_client

    # Synchronous client
    redis = get_redis_client()
    redis.set("key", "value")

    # Asynchronous client
    redis = await get_async_redis_client()
    await redis.set("key", "value")
"""

from typing import Optional
import redis
import redis.asyncio as aioredis
from app.core.redis_manager import (
    get_redis_manager,
    get_sync_redis_client as _get_sync_redis_client,
    get_async_redis_client as _get_async_redis_client,
    redis_health_check,
    cleanup_redis_connections,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Log successful import for monitoring
logger.debug("Redis client module loaded - using RedisManager backend")


def get_redis_client() -> Optional[redis.Redis]:
    """
    Get synchronous Redis client for rate limiting and caching.

    Returns a connection-pooled Redis client suitable for distributed
    rate limiting, session management, and general caching.

    Returns:
        redis.Redis: Synchronous Redis client or None if unavailable

    Example:
        ```python
        redis = get_redis_client()
        if redis:
            redis.setex("rate_limit:user:123", 60, 1)
        ```
    """
    try:
        return _get_sync_redis_client()
    except Exception as e:
        logger.warning(f"Failed to get sync Redis client: {e}")
        return None


async def get_async_redis_client() -> Optional[aioredis.Redis]:
    """
    Get asynchronous Redis client for async operations.

    Returns a connection-pooled async Redis client suitable for
    use in async contexts like FastAPI endpoints.

    Returns:
        aioredis.Redis: Asynchronous Redis client or None if unavailable

    Example:
        ```python
        redis = await get_async_redis_client()
        if redis:
            await redis.setex("cache:key", 300, "value")
        ```
    """
    try:
        return await _get_async_redis_client()
    except Exception as e:
        logger.warning(f"Failed to get async Redis client: {e}")
        return None


def get_redis_manager_instance():
    """
    Get the Redis manager instance for advanced operations.

    Use this when you need direct access to the RedisManager
    for operations like creating multiple connections, health checks,
    or custom connection configurations.

    Returns:
        RedisManager: Redis manager instance

    Example:
        ```python
        manager = get_redis_manager_instance()
        stats = await manager.get_cache_stats()
        ```
    """
    return get_redis_manager()


async def check_redis_health() -> dict:
    """
    Check Redis connection health and return status.

    Performs a comprehensive health check including connectivity,
    latency, and basic operations.

    Returns:
        dict: Health check results with status and metrics

    Example:
        ```python
        health = await check_redis_health()
        if health["status"] == "healthy":
            logger.info("Redis is operational", extra={"health": health})
        ```
    """
    return await redis_health_check()


async def cleanup_redis() -> None:
    """
    Clean up Redis connections gracefully.

    Should be called during application shutdown to ensure
    all connections are properly closed.

    Example:
        ```python
        @app.on_event("shutdown")
        async def shutdown_event():
            await cleanup_redis()
        ```
    """
    await cleanup_redis_connections()


# Backward compatibility aliases
get_sync_redis = get_redis_client
get_async_redis = get_async_redis_client


__all__ = [
    "get_redis_client",
    "get_async_redis_client",
    "get_redis_manager_instance",
    "check_redis_health",
    "cleanup_redis",
    # Backward compatibility
    "get_sync_redis",
    "get_async_redis",
]
