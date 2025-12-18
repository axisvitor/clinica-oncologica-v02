"""
Admin endpoint caching utilities for Hormonia Backend.

Provides efficient caching for admin dashboard data and user management.
"""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from functools import wraps

from fastapi import Request
import structlog

from app.core.redis_unified import get_async_redis

logger = structlog.get_logger(__name__)


class AdminCacheManager:
    """
    Cache manager for admin endpoints with intelligent invalidation.
    """

    def __init__(self):
        self.default_ttl = 300  # 5 minutes
        self.cache_prefix = "admin_cache"
        self.stats = {"hits": 0, "misses": 0, "invalidations": 0}

    def _generate_cache_key(self, key_parts: List[str]) -> str:
        """Generate consistent cache key from parts."""
        key_string = ":".join(str(part) for part in key_parts)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()[:12]
        return f"{self.cache_prefix}:{key_hash}:{key_string}"

    def _generate_request_key(
        self, request: Request, additional_parts: List[str] = None
    ) -> str:
        """Generate cache key from request parameters."""
        key_parts = [
            request.method,
            request.url.path,
            str(sorted(request.query_params.items())),
        ]

        if additional_parts:
            key_parts.extend(additional_parts)

        return self._generate_cache_key(key_parts)

    async def get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached response if available."""
        try:
            redis_client = await get_async_redis()
            cached_data = await redis_client.get(cache_key)

            if cached_data:
                self.stats["hits"] += 1
                data = json.loads(cached_data.decode())

                # Check if cache is still valid
                if "expires_at" in data:
                    expires_at = datetime.fromisoformat(data["expires_at"])
                    if datetime.utcnow() > expires_at:
                        await redis_client.delete(cache_key)
                        self.stats["misses"] += 1
                        return None

                logger.debug(f"Cache hit for key: {cache_key}")
                return data.get("response")

            self.stats["misses"] += 1
            return None

        except Exception as e:
            logger.error(f"Error getting cached response: {e}")
            self.stats["misses"] += 1
            return None

    async def set_cached_response(
        self, cache_key: str, response_data: Dict[str, Any], ttl: Optional[int] = None
    ) -> bool:
        """Cache response data with TTL."""
        try:
            redis_client = await get_async_redis()
            ttl = ttl or self.default_ttl

            cache_data = {
                "response": response_data,
                "cached_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(seconds=ttl)).isoformat(),
            }

            await redis_client.setex(
                cache_key, ttl, json.dumps(cache_data, default=str)
            )

            logger.debug(f"Cached response for key: {cache_key}, TTL: {ttl}s")
            return True

        except Exception as e:
            logger.error(f"Error caching response: {e}")
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all cache keys matching pattern."""
        try:
            redis_client = await get_async_redis()
            keys = await redis_client.keys(f"{self.cache_prefix}:*{pattern}*")

            if keys:
                deleted = await redis_client.delete(*keys)
                self.stats["invalidations"] += deleted
                logger.info(
                    f"Invalidated {deleted} cache entries matching pattern: {pattern}"
                )
                return deleted

            return 0

        except Exception as e:
            logger.error(f"Error invalidating cache pattern {pattern}: {e}")
            return 0

    async def invalidate_user_cache(self, user_id: str) -> None:
        """Invalidate cache entries related to a specific user."""
        patterns = [f"user:{user_id}", "users", "stats", "activity"]

        for pattern in patterns:
            await self.invalidate_pattern(pattern)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / max(total_requests, 1)) * 100

        return {
            **self.stats,
            "total_requests": total_requests,
            "hit_rate_percentage": round(hit_rate, 2),
        }


# Global cache manager instance
admin_cache = AdminCacheManager()


def cache_admin_response(
    ttl: int = 300,
    cache_key_fn: Optional[Callable] = None,
    invalidate_on: Optional[List[str]] = None,
):
    """
    Decorator for caching admin endpoint responses.

    Args:
        ttl: Time to live in seconds
        cache_key_fn: Custom function to generate cache key
        invalidate_on: List of events that should invalidate this cache
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if not request:
                # If no request found, execute without caching
                return await func(*args, **kwargs)

            # Generate cache key
            if cache_key_fn:
                cache_key = cache_key_fn(request, *args, **kwargs)
            else:
                cache_key = admin_cache._generate_request_key(request, [func.__name__])

            # Try to get cached response
            cached_response = await admin_cache.get_cached_response(cache_key)
            if cached_response is not None:
                return cached_response

            # Execute function and cache result
            response = await func(*args, **kwargs)

            # Cache the response if it's successful
            if hasattr(response, "status_code"):
                if response.status_code == 200:
                    await admin_cache.set_cached_response(
                        cache_key, response.__dict__, ttl
                    )
            else:
                # For direct dict/object responses
                await admin_cache.set_cached_response(cache_key, response, ttl)

            return response

        return wrapper

    return decorator


def invalidate_admin_cache(pattern: str):
    """Helper function to invalidate admin cache by pattern."""
    import asyncio

    async def _invalidate():
        await admin_cache.invalidate_pattern(pattern)

    # Run in background if called from non-async context
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_invalidate())
        else:
            asyncio.run(_invalidate())
    except RuntimeError:
        asyncio.run(_invalidate())


# Cache key generators for common patterns
def user_list_cache_key(request: Request, *args, **kwargs) -> str:
    """Generate cache key for user list endpoint."""
    page = request.query_params.get("page", "1")
    size = request.query_params.get("size", "20")
    filters = [
        request.query_params.get("role", ""),
        request.query_params.get("is_active", ""),
        request.query_params.get("search", ""),
    ]

    return admin_cache._generate_cache_key(["user_list", page, size, *filters])


def user_stats_cache_key(request: Request, *args, **kwargs) -> str:
    """Generate cache key for user statistics."""
    return admin_cache._generate_cache_key(["user_stats"])


def user_activity_cache_key(request: Request, *args, **kwargs) -> str:
    """Generate cache key for user activity."""
    user_id = kwargs.get("user_id", "")
    page = request.query_params.get("page", "1")
    size = request.query_params.get("size", "20")
    action = request.query_params.get("action", "")

    return admin_cache._generate_cache_key(
        ["user_activity", str(user_id), page, size, action]
    )


def get_admin_cache() -> AdminCacheManager:
    """Get the global admin cache manager instance."""
    return admin_cache
