"""
Redis-based caching utilities for performance optimization.
"""

import json
import pickle
import hashlib
from typing import Any, List, Optional, Callable
from datetime import datetime, timedelta, timezone
from functools import wraps
from dataclasses import dataclass

import redis.asyncio as redis
from fastapi import Request

from app.utils.logging import get_logger
from app.core.redis_unified import get_async_redis

logger = get_logger(__name__)


@dataclass
class CacheConfig:
    """Cache configuration for different data types."""

    ttl: int  # Time to live in seconds
    key_prefix: str
    serialize_method: str = "json"  # json, pickle
    compress: bool = False


# Cache configurations for different data types
CACHE_CONFIGS = {
    "patient_list": CacheConfig(ttl=300, key_prefix="patients:list"),  # 5 minutes
    "patient_detail": CacheConfig(ttl=600, key_prefix="patients:detail"),  # 10 minutes
    "user_profile": CacheConfig(ttl=1800, key_prefix="users:profile"),  # 30 minutes
    "quiz_templates": CacheConfig(ttl=3600, key_prefix="quiz:templates"),  # 1 hour
    "flow_templates": CacheConfig(ttl=3600, key_prefix="flow:templates"),  # 1 hour
    "analytics_dashboard": CacheConfig(
        ttl=300, key_prefix="analytics:dashboard"
    ),  # 5 minutes
    "system_metrics": CacheConfig(ttl=60, key_prefix="system:metrics"),  # 1 minute
    "message_stats": CacheConfig(ttl=300, key_prefix="messages:stats"),  # 5 minutes
    "report_data": CacheConfig(ttl=1800, key_prefix="reports:data"),  # 30 minutes
}


class CacheManager:
    """Redis-based cache manager with automatic serialization and compression."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self._local_cache: dict[str, dict[str, Any]] = {}
        self._cache_stats = {"hits": 0, "misses": 0, "errors": 0}

    async def _get_redis_client(self) -> Optional[redis.Redis]:
        """Get Redis client if available using unified RedisManager."""
        if self.redis_client:
            return self.redis_client

        try:
            # Use unified RedisManager - SSL/TLS configured automatically
            client = await get_async_redis()
            await client.ping()
            return client
        except Exception as e:
            logger.warning(f"Redis not available for caching: {e}")
            return None

    def _generate_cache_key(self, config: CacheConfig, key_parts: List[str]) -> str:
        """Generate cache key from configuration and key parts."""
        key_string = ":".join(str(part) for part in key_parts)
        # Hash long keys to avoid Redis key length limits
        if len(key_string) > 200:
            key_hash = hashlib.md5(key_string.encode()).hexdigest()
            return f"{config.key_prefix}:{key_hash}"
        return f"{config.key_prefix}:{key_string}"

    def _serialize_data(self, data: Any, method: str) -> bytes:
        """Serialize data based on method."""
        if method == "json":
            return json.dumps(data, default=str).encode()
        elif method == "pickle":
            return pickle.dumps(data)
        else:
            raise ValueError(f"Unknown serialization method: {method}")

    def _deserialize_data(self, data: bytes, method: str) -> Any:
        """Deserialize data based on method."""
        if method == "json":
            return json.loads(data.decode())
        elif method == "pickle":
            return pickle.loads(data)
        else:
            raise ValueError(f"Unknown serialization method: {method}")

    async def get(
        self, cache_type: str, key_parts: List[str], default: Any = None
    ) -> Any:
        """
        Get value from cache.

        Args:
            cache_type: Type of cache (must be in CACHE_CONFIGS)
            key_parts: List of key components
            default: Default value if not found

        Returns:
            Cached value or default
        """
        if cache_type not in CACHE_CONFIGS:
            logger.warning(f"Unknown cache type: {cache_type}")
            return default

        config = CACHE_CONFIGS[cache_type]
        cache_key = self._generate_cache_key(config, key_parts)

        try:
            redis_client = await self._get_redis_client()

            if redis_client:
                # Try Redis first
                cached_data = await redis_client.get(cache_key)
                if cached_data:
                    self._cache_stats["hits"] += 1
                    return self._deserialize_data(cached_data, config.serialize_method)

            # Fallback to local cache
            if cache_key in self._local_cache:
                cache_entry = self._local_cache[cache_key]
                if datetime.now(timezone.utc) < cache_entry["expires_at"]:
                    self._cache_stats["hits"] += 1
                    return cache_entry["data"]
                else:
                    # Expired, remove from local cache
                    del self._local_cache[cache_key]

            self._cache_stats["misses"] += 1
            return default

        except Exception as e:
            logger.error(f"Cache get error for key {cache_key}: {e}")
            self._cache_stats["errors"] += 1
            return default

    async def set(
        self,
        cache_type: str,
        key_parts: List[str],
        value: Any,
        ttl_override: Optional[int] = None,
    ) -> bool:
        """
        Set value in cache.

        Args:
            cache_type: Type of cache (must be in CACHE_CONFIGS)
            key_parts: List of key components
            value: Value to cache
            ttl_override: Override default TTL

        Returns:
            True if successful, False otherwise
        """
        if cache_type not in CACHE_CONFIGS:
            logger.warning(f"Unknown cache type: {cache_type}")
            return False

        config = CACHE_CONFIGS[cache_type]
        cache_key = self._generate_cache_key(config, key_parts)
        ttl = ttl_override or config.ttl

        try:
            serialized_data = self._serialize_data(value, config.serialize_method)

            redis_client = await self._get_redis_client()

            if redis_client:
                # Set in Redis
                await redis_client.setex(cache_key, ttl, serialized_data)

            # Also set in local cache as fallback
            self._local_cache[cache_key] = {
                "data": value,
                "expires_at": datetime.now(timezone.utc) + timedelta(seconds=ttl),
            }

            return True

        except Exception as e:
            logger.error(f"Cache set error for key {cache_key}: {e}")
            self._cache_stats["errors"] += 1
            return False

    async def delete(self, cache_type: str, key_parts: List[str]) -> bool:
        """Delete value from cache."""
        if cache_type not in CACHE_CONFIGS:
            return False

        config = CACHE_CONFIGS[cache_type]
        cache_key = self._generate_cache_key(config, key_parts)

        try:
            redis_client = await self._get_redis_client()

            if redis_client:
                await redis_client.delete(cache_key)

            # Remove from local cache
            self._local_cache.pop(cache_key, None)

            return True

        except Exception as e:
            logger.error(f"Cache delete error for key {cache_key}: {e}")
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a pattern."""
        try:
            redis_client = await self._get_redis_client()

            if redis_client:
                keys = await redis_client.keys(pattern)
                if keys:
                    await redis_client.delete(*keys)
                    return len(keys)

            # For local cache, remove matching keys
            keys_to_remove = [key for key in self._local_cache.keys() if pattern in key]
            for key in keys_to_remove:
                del self._local_cache[key]

            return len(keys_to_remove)

        except Exception as e:
            logger.error(f"Cache invalidate pattern error for {pattern}: {e}")
            return 0

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._cache_stats["hits"] + self._cache_stats["misses"]
        hit_rate = (
            (self._cache_stats["hits"] / total_requests * 100)
            if total_requests > 0
            else 0
        )

        return {
            "hits": self._cache_stats["hits"],
            "misses": self._cache_stats["misses"],
            "errors": self._cache_stats["errors"],
            "hit_rate_percent": round(hit_rate, 2),
            "local_cache_size": len(self._local_cache),
        }

    async def clear_all(self) -> bool:
        """Clear all cache data."""
        try:
            redis_client = await self._get_redis_client()

            if redis_client:
                # Clear all keys with our prefixes
                for config in CACHE_CONFIGS.values():
                    pattern = f"{config.key_prefix}:*"
                    keys = await redis_client.keys(pattern)
                    if keys:
                        await redis_client.delete(*keys)

            # Clear local cache
            self._local_cache.clear()

            return True

        except Exception as e:
            logger.error(f"Cache clear all error: {e}")
            return False


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def cache_result(
    cache_type: str,
    key_generator: Callable[..., List[str]],
    ttl_override: Optional[int] = None,
):
    """
    Decorator for caching function results.

    Args:
        cache_type: Type of cache to use
        key_generator: Function to generate cache key parts from function args
        ttl_override: Override default TTL
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_manager = get_cache_manager()

            # Generate cache key
            try:
                key_parts = key_generator(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Cache key generation failed: {e}")
                return await func(*args, **kwargs)

            # Try to get from cache
            cached_result = await cache_manager.get(cache_type, key_parts)
            if cached_result is not None:
                logger.debug(f"Cache hit for {cache_type}:{':'.join(key_parts)}")
                return cached_result

            # Execute function and cache result
            result = await func(*args, **kwargs)

            # Cache the result
            await cache_manager.set(cache_type, key_parts, result, ttl_override)
            logger.debug(f"Cached result for {cache_type}:{':'.join(key_parts)}")

            return result

        return wrapper

    return decorator


def invalidate_cache(cache_type: str, key_parts: List[str]):
    """Invalidate specific cache entry."""

    async def _invalidate():
        cache_manager = get_cache_manager()
        await cache_manager.delete(cache_type, key_parts)

    return _invalidate


def generate_request_cache_key(
    request: Request, additional_parts: List[str] = None
) -> List[str]:
    """Generate cache key parts from request."""
    parts = [
        request.method,
        request.url.path,
        str(sorted(request.query_params.items())),
    ]

    if additional_parts:
        parts.extend(additional_parts)

    return parts


def generate_user_cache_key(
    user_id: str, additional_parts: List[str] = None
) -> List[str]:
    """Generate cache key parts for user-specific data."""
    parts = [user_id]

    if additional_parts:
        parts.extend(additional_parts)

    return parts


def cache_response(seconds: int = 300):
    """
    Decorator for caching HTTP response data.

    Args:
        seconds: Cache TTL in seconds (default 5 minutes)
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_manager = get_cache_manager()

            # Generate cache key from function name and arguments
            func_name = func.__name__
            # Use string representation of args/kwargs for cache key
            key_parts = [func_name, str(hash(str(args) + str(sorted(kwargs.items()))))]

            # Try to get from cache
            cached_result = await cache_manager.get("analytics_dashboard", key_parts)
            if cached_result is not None:
                logger.debug(f"Cache hit for response {func_name}")
                return cached_result

            # Execute function and cache result
            result = await func(*args, **kwargs)

            # Cache the result
            await cache_manager.set("analytics_dashboard", key_parts, result, seconds)
            logger.debug(f"Cached response for {func_name}")

            return result

        return wrapper

    return decorator
