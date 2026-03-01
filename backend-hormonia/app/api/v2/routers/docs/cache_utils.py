"""
Cache utilities for documentation endpoints.
Provides Redis-based caching with configurable TTL.
"""

import json
import hashlib
import logging
from typing import Optional, Dict

from app.core.redis_manager import get_async_redis_client as get_async_redis

logger = logging.getLogger(__name__)

# Cache TTL configuration (in seconds)
CACHE_TTL_API_DOCS = 86400  # 24 hours
CACHE_TTL_GUIDES = 43200  # 12 hours
CACHE_TTL_EXAMPLES = 21600  # 6 hours
CACHE_TTL_SEARCH = 3600  # 1 hour


def get_cache_key(prefix: str, **params) -> str:
    """
    Generate cache key from prefix and parameters.

    Args:
        prefix: Cache key prefix (e.g., "endpoints", "guides")
        **params: Query parameters to include in cache key

    Returns:
        Hashed cache key string
    """
    param_str = json.dumps(params, sort_keys=True, default=str)
    # Use SHA-256 instead of MD5 for better collision resistance
    param_hash = hashlib.sha256(param_str.encode()).hexdigest()[:32]
    return f"docs:v2:{prefix}:{param_hash}"


async def get_cached_result(cache_key: str) -> Optional[Dict]:
    """
    Get cached result from Redis.

    Args:
        cache_key: Cache key to retrieve

    Returns:
        Cached data as dict, or None if not found/error
    """
    try:
        redis_client = await get_async_redis()
        if redis_client is None:
            return None
        cached = await redis_client.get(cache_key)
        if cached:
            logger.debug(f"Cache HIT: {cache_key}")
            return json.loads(cached)
        return None
    except Exception as e:
        logger.warning(f"Cache read failed: {e}")
        return None


async def set_cached_result(cache_key: str, data: Dict, ttl: int) -> None:
    """
    Set cached result in Redis.

    Args:
        cache_key: Cache key to set
        data: Data to cache (must be JSON serializable)
        ttl: Time to live in seconds
    """
    try:
        redis_client = await get_async_redis()
        if redis_client is None:
            return
        await redis_client.setex(cache_key, ttl, json.dumps(data, default=str))
        logger.debug(f"Cache SET: {cache_key} (TTL: {ttl}s)")
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")
