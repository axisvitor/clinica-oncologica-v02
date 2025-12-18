"""
Async Redis Client Operations

Provides async Redis client functions and utilities.
"""

import logging
import re
from contextlib import asynccontextmanager
import redis.asyncio as redis_async

from app.config import settings

logger = logging.getLogger(__name__)


async def get_async_redis_client() -> redis_async.Redis:
    """
    Get async Redis client from manager.

    Returns:
        Async Redis client
    """
    from .utils import get_redis_manager

    manager = get_redis_manager()
    return await manager.get_async_client()


@asynccontextmanager
async def redis_transaction():
    """
    Async context manager for Redis transactions.

    Usage:
        async with redis_transaction() as pipe:
            pipe.set('key', 'value')
            pipe.incr('counter')
            results = await pipe.execute()
    """
    client = await get_async_redis_client()
    pipe = client.pipeline()
    try:
        yield pipe
    finally:
        # Pipeline cleanup is automatic
        pass


async def cleanup_redis_connections():
    """Cleanup all Redis connections (for application shutdown)."""
    from .utils import _cleanup_managers

    await _cleanup_managers()
    logger.info("All Redis connections cleaned up")


async def redis_health_check() -> dict:
    """
    Perform Redis health check.

    Returns:
        Health check results
    """

    def sanitize_redis_url(url: str) -> str:
        """Remove password from Redis URL for safe logging"""
        if not url:
            return "not_configured"
        # Replace password in redis://user:password@host:port format
        return re.sub(r"://([^:]*):([^@]*)@", r"://\1:***@", url)

    try:
        from .utils import get_redis_manager

        manager = get_redis_manager()

        # Test async client
        async_client = await manager.get_async_client()
        async_ping = await async_client.ping()

        # Test sync client
        sync_client = manager.get_sync_client()
        sync_ping = sync_client.ping()

        return {
            "status": "healthy",
            "async_ping": bool(async_ping),
            "sync_ping": bool(sync_ping),
            "redis_url": sanitize_redis_url(
                settings.REDIS_URL
            ),  # SEC-001: Sanitized URL
            "max_connections": manager.max_connections,
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "redis_url": sanitize_redis_url(
                getattr(settings, "REDIS_URL", "not_configured")
            ),  # SEC-001: Sanitized URL
        }
