"""
Cache Invalidation Module

This module provides cache invalidation functionality including pattern matching,
namespace invalidation, and only the backward compatibility wrappers that still
have active callers.
"""

import re
from typing import Any, Optional, List

from app.utils.logging import get_logger
from .cache_manager import get_unified_cache_manager, CacheOperation

logger = get_logger(__name__)


class CacheInvalidator:
    """
    Cache invalidation handler with pattern matching and namespace support.
    """

    def __init__(self, cache_manager=None):
        """
        Initialize cache invalidator.

        Args:
            cache_manager: Optional cache manager instance
        """
        self.cache_manager = cache_manager or get_unified_cache_manager()

    def invalidate_pattern(self, pattern: str, namespace: Optional[str] = None) -> int:
        """
        Invalidate all cache keys matching a pattern (synchronous).

        Args:
            pattern: Key pattern (supports wildcards like "user:*")
            namespace: Optional namespace filter

        Returns:
            Number of keys deleted
        """
        if namespace:
            full_pattern = f"{namespace}:{pattern}"
        else:
            full_pattern = pattern

        deleted_count = 0

        try:
            # Delete from Redis
            keys = self.cache_manager._backend.redis_keys(full_pattern)
            if keys:
                for key in keys:
                    self.cache_manager._backend.redis_delete(key)
                    deleted_count += 1
                logger.debug(
                    f"Deleted {deleted_count} keys from Redis matching: {full_pattern}"
                )

            # Delete from local cache
            pattern_regex = re.compile(full_pattern.replace("*", ".*"))
            keys_to_remove = [
                key
                for key in self.cache_manager._backend._local_cache.keys()
                if pattern_regex.match(key)
            ]
            for key in keys_to_remove:
                del self.cache_manager._backend._local_cache[key]
                deleted_count += 1

            self.cache_manager._update_stats(CacheOperation.INVALIDATE, True)
            logger.info(
                f"Invalidated {deleted_count} cache keys matching: {full_pattern}"
            )
            return deleted_count

        except Exception as e:
            logger.error(f"Cache invalidation error for pattern {full_pattern}: {e}")
            self.cache_manager._update_stats(CacheOperation.INVALIDATE, False)
            return 0

    async def invalidate_pattern_async(
        self, pattern: str, namespace: Optional[str] = None
    ) -> int:
        """
        Invalidate all cache keys matching a pattern (asynchronous).

        Args:
            pattern: Key pattern (supports wildcards like "user:*")
            namespace: Optional namespace filter

        Returns:
            Number of keys deleted
        """
        if namespace:
            full_pattern = f"{namespace}:{pattern}"
        else:
            full_pattern = pattern

        deleted_count = 0

        try:
            # Delete from Redis
            keys = await self.cache_manager._backend.redis_keys_async(full_pattern)
            if keys:
                for key in keys:
                    await self.cache_manager._backend.redis_delete_async(key)
                    deleted_count += 1
                logger.debug(
                    f"Deleted {deleted_count} keys from Redis (Async) matching: {full_pattern}"
                )

            # Delete from local cache
            pattern_regex = re.compile(full_pattern.replace("*", ".*"))
            keys_to_remove = [
                key
                for key in self.cache_manager._backend._local_cache.keys()
                if pattern_regex.match(key)
            ]
            for key in keys_to_remove:
                del self.cache_manager._backend._local_cache[key]
                deleted_count += 1

            self.cache_manager._update_stats(CacheOperation.INVALIDATE, True)
            logger.info(
                f"Invalidated {deleted_count} cache keys (Async) matching: {full_pattern}"
            )
            return deleted_count

        except Exception as e:
            logger.error(
                f"Async cache invalidation error for pattern {full_pattern}: {e}"
            )
            self.cache_manager._update_stats(CacheOperation.INVALIDATE, False)
            return 0

    def invalidate_namespace(self, namespace: str) -> int:
        """
        Invalidate all cache keys in a namespace (synchronous).

        Args:
            namespace: Namespace to invalidate

        Returns:
            Number of keys deleted
        """
        return self.invalidate_pattern("*", namespace=namespace)

    async def invalidate_namespace_async(self, namespace: str) -> int:
        """
        Invalidate all cache keys in a namespace (asynchronous).

        Args:
            namespace: Namespace to invalidate

        Returns:
            Number of keys deleted
        """
        return await self.invalidate_pattern_async("*", namespace=namespace)

    async def clear_all_cache(self) -> bool:
        """
        Clear all cache data (Redis and local).

        Returns:
            True if successful, False otherwise
        """
        try:
            # Clear Redis cache
            redis_client = await self.cache_manager._backend.get_async_redis_client()
            if redis_client:
                try:
                    # Clear all keys with our namespaces
                    deleted_count = 0
                    for config in self.cache_manager._cache_configs.values():
                        pattern = f"{config.namespace}:{config.key_prefix}:*"
                        batch: List[Any] = []
                        async for key in redis_client.scan_iter(match=pattern):
                            batch.append(key)
                            if len(batch) >= 500:
                                for batch_key in batch:
                                    try:
                                        if hasattr(redis_client, "unlink"):
                                            deleted_count += int(
                                                (await redis_client.unlink(batch_key))
                                                or 0
                                            )
                                        else:
                                            deleted_count += int(
                                                (await redis_client.delete(batch_key))
                                                or 0
                                            )
                                    except Exception:
                                        deleted_count += int(
                                            (await redis_client.delete(batch_key)) or 0
                                        )
                                batch.clear()
                        if batch:
                            for batch_key in batch:
                                try:
                                    if hasattr(redis_client, "unlink"):
                                        deleted_count += int(
                                            (await redis_client.unlink(batch_key)) or 0
                                        )
                                    else:
                                        deleted_count += int(
                                            (await redis_client.delete(batch_key)) or 0
                                        )
                                except Exception:
                                    deleted_count += int(
                                        (await redis_client.delete(batch_key)) or 0
                                    )
                    logger.info(f"Redis cache cleared ({deleted_count} keys)")
                except Exception as e:
                    logger.warning(f"Redis cache clear failed: {e}")

            # Clear local cache
            self.cache_manager.clear_local_cache()

            return True

        except Exception as e:
            logger.error(f"Cache clear all error: {e}")
            return False


# Backward compatibility helpers with active callers (user cache operations)
def cache_user_data(user_id: str, data: Any, ttl: int = 1800) -> bool:
    """Cache user data with 30-minute default TTL (backward compatibility)."""
    manager = get_unified_cache_manager()
    return manager.set("user_profile", data, [user_id], ttl)


def get_cached_user_data(user_id: str) -> Optional[Any]:
    """Get cached user data (backward compatibility)."""
    manager = get_unified_cache_manager()
    return manager.get("user_profile", [user_id])


def invalidate_user_cache(user_id: str) -> bool:
    """Invalidate specific user cache (backward compatibility)."""
    manager = get_unified_cache_manager()
    return manager.delete("user_profile", [user_id])


async def invalidate_user_cache_async(user_id: str) -> bool:
    """Invalidate specific user cache (async backward compatibility)."""
    manager = get_unified_cache_manager()
    return await manager.delete_async("user_profile", [user_id])


# Backward compatibility helpers with active callers (patient cache operations)
def cache_patient_data(patient_id: str, data: Any, ttl: int = 3600) -> bool:
    """Cache patient data with 1-hour default TTL (backward compatibility)."""
    manager = get_unified_cache_manager()
    return manager.set("patient_detail", data, [patient_id], ttl)


def get_cached_patient_data(patient_id: str) -> Optional[Any]:
    """Get cached patient data (backward compatibility)."""
    manager = get_unified_cache_manager()
    return manager.get("patient_detail", [patient_id])


def invalidate_patient_cache(patient_id: str) -> bool:
    """Invalidate specific patient cache (backward compatibility)."""
    manager = get_unified_cache_manager()
    return manager.delete("patient_detail", [patient_id])


def invalidate_cache(cache_type: str, key_parts: Optional[List[str]] = None) -> bool:
    """
    Invalidate a specific cache entry (backward compatibility).

    Legacy callers often pass a single cache key string and ignore return values.
    This helper must never raise for those callers.
    """
    try:
        cache_manager = get_unified_cache_manager()
        return cache_manager.delete(cache_type, key_parts)
    except Exception as e:
        logger.debug("invalidate_cache best-effort fallback for %s failed: %s", cache_type, e)
        return False


__all__ = [
    "CacheInvalidator",
    "cache_user_data",
    "get_cached_user_data",
    "invalidate_user_cache",
    "invalidate_user_cache_async",
    "cache_patient_data",
    "get_cached_patient_data",
    "invalidate_patient_cache",
    "invalidate_cache",
]
