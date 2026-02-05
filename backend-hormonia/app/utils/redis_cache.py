"""
Compatibility helpers for legacy Redis cache access.
"""

from typing import Any

from app.core.redis_unified import get_async_redis, get_sync_redis


async def get_async_redis_client() -> Any:
    """Return the async Redis client (legacy name)."""
    return await get_async_redis()


def get_sync_redis_client() -> Any:
    """Return the sync Redis client (legacy name)."""
    return get_sync_redis()
