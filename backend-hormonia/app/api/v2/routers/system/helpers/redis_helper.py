"""
Redis Helper Module.

Provides Redis client access for caching.
This is a wrapper around the auth module's _get_redis_client function.
"""

from .auth import _get_redis_client


async def get_redis_client():
    """
    Get async Redis client for caching.

    Returns:
        Optional[Redis]: Redis client instance or None if unavailable

    Note:
        This is a wrapper function that delegates to _get_redis_client
        from the auth module for consistency.
    """
    return await _get_redis_client()


__all__ = ["get_redis_client"]
