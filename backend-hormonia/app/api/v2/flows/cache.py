"""
Shared cache helper for flow API routers.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable


async def get_cached_or_compute(
    cache_key: str,
    compute_fn: Callable[[], Awaitable[Any]],
    redis_cache: Any,
    ttl: int,
) -> Any:
    """
    Resolve value from cache or compute and cache it.
    """
    cached = await redis_cache.get(cache_key)
    if cached is not None:
        return cached

    result = await compute_fn()
    await redis_cache.set(cache_key, result, ttl=ttl)
    return result

