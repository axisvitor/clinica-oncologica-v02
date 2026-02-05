"""
Cache Manager Module - Main Cache Orchestrator

This module provides the central cache management class with CRUD operations,
statistics tracking, and cache configuration management.
"""

import hashlib
import asyncio
from typing import Any, Callable, Optional, Union, List, Dict
from datetime import timedelta, datetime, timezone
from dataclasses import dataclass, field
from enum import Enum

from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from app.utils.logging import get_logger
from app.core.executors import get_cache_executor
from .redis_backend import RedisBackend, SerializationMethod

logger = get_logger(__name__)


class CacheOperation(str, Enum):
    """Cache operation types for monitoring."""

    GET = "get"
    SET = "set"
    DELETE = "delete"
    INVALIDATE = "invalidate"
    CLEAR = "clear"


@dataclass
class CacheConfig:
    """Configuration for different cache types."""

    ttl: int  # Time to live in seconds
    key_prefix: str
    serialize_method: SerializationMethod = SerializationMethod.JSON
    compress: bool = False
    namespace: str = "cache"
    enable_local_fallback: bool = True
    max_key_length: int = 200


@dataclass
class CacheStats:
    """Cache statistics tracking."""

    hits: int = 0
    misses: int = 0
    errors: int = 0
    sets: int = 0
    deletes: int = 0
    invalidations: int = 0
    last_reset: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_requests(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        return (
            (self.hits / self.total_requests * 100) if self.total_requests > 0 else 0.0
        )

    def reset(self):
        """Reset all statistics."""
        self.hits = 0
        self.misses = 0
        self.errors = 0
        self.sets = 0
        self.deletes = 0
        self.invalidations = 0
        self.last_reset = datetime.now(timezone.utc)


# Default cache configurations for different data types
DEFAULT_CACHE_CONFIGS = {
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
    "ai_responses": CacheConfig(ttl=7200, key_prefix="ai:responses"),  # 2 hours
    "template_cache": CacheConfig(ttl=3600, key_prefix="templates:cache"),  # 1 hour
    "session_data": CacheConfig(ttl=1800, key_prefix="sessions:data"),  # 30 minutes
    "http_cache": CacheConfig(
        ttl=300,
        key_prefix="responses",
        namespace="http",
    ),
}


class UnifiedCacheManager:
    """
    Unified cache manager that provides both sync and async operations
    with Redis backend and local fallback support.
    """

    def __init__(
        self,
        redis_client: Optional[Union[Redis, AsyncRedis]] = None,
        enable_stats: bool = True,
        enable_local_fallback: bool = True,
    ):
        """
        Initialize unified cache manager.

        Args:
            redis_client: Optional Redis client instance
            enable_stats: Whether to track cache statistics
            enable_local_fallback: Whether to use local cache as fallback
        """
        self.enable_stats = enable_stats
        self._stats = CacheStats() if enable_stats else None
        self._cache_configs = DEFAULT_CACHE_CONFIGS.copy()
        # Use centralized executor from app.core.executors
        self._executor = get_cache_executor()
        self._backend = RedisBackend(
            redis_client=redis_client, enable_local_fallback=enable_local_fallback
        )

    def register_cache_config(self, cache_type: str, config: CacheConfig):
        """Register a new cache configuration."""
        self._cache_configs[cache_type] = config

    def get_cache_config(self, cache_type: str) -> Optional[CacheConfig]:
        """Get cache configuration for a given type."""
        return self._cache_configs.get(cache_type)

    def _generate_cache_key(
        self,
        config: CacheConfig,
        key_parts: Optional[List[str]] = None,
        *args,
        **kwargs,
    ) -> str:
        """
        Generate a unique cache key from configuration and arguments.

        Args:
            config: Cache configuration
            key_parts: Optional list of key parts
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Unique cache key string
        """
        # Start with namespace and prefix
        key_components = [config.namespace, config.key_prefix]

        # Add provided key parts
        if key_parts:
            key_components.extend([str(part) for part in key_parts])

        # Add function arguments
        if args:
            key_components.extend([str(arg) for arg in args])

        if kwargs:
            # Sort kwargs for consistent key generation
            sorted_kwargs = sorted(kwargs.items())
            key_components.extend([f"{k}={v}" for k, v in sorted_kwargs])

        # Join parts and hash if too long
        cache_key = ":".join(key_components)

        # Hash long keys to avoid Redis key length limits
        if len(cache_key) > config.max_key_length:
            hash_suffix = hashlib.md5(cache_key.encode()).hexdigest()
            cache_key = f"{config.namespace}:{config.key_prefix}:hash:{hash_suffix}"

        return cache_key

    def _update_stats(self, operation: CacheOperation, success: bool = True):
        """Update cache statistics."""
        if not self._stats:
            return

        if operation == CacheOperation.GET:
            if success:
                self._stats.hits += 1
            else:
                self._stats.misses += 1
        elif operation == CacheOperation.SET:
            if success:
                self._stats.sets += 1
            else:
                self._stats.errors += 1
        elif operation == CacheOperation.DELETE:
            if success:
                self._stats.deletes += 1
            else:
                self._stats.errors += 1
        elif operation == CacheOperation.INVALIDATE:
            if success:
                self._stats.invalidations += 1
            else:
                self._stats.errors += 1

    # ------------------------------------------------------------------
    # Cache invalidation helpers (compatibility with legacy interfaces)
    # ------------------------------------------------------------------

    def invalidate_pattern(self, pattern: str, namespace: Optional[str] = None) -> int:
        """
        Invalidate cache entries that match a pattern.

        This keeps backward compatibility with the old cache API.
        """
        try:
            from .invalidation import (
                CacheInvalidator,
            )  # Local import to avoid circular dependency

            invalidator = CacheInvalidator(cache_manager=self)
            return invalidator.invalidate_pattern(pattern, namespace=namespace)
        except Exception as exc:
            logger.error(
                "UnifiedCacheManager.invalidate_pattern failed",
                exc_info=True,
                extra={"pattern": pattern, "namespace": namespace, "error": str(exc)},
            )
            return 0

    async def invalidate_pattern_async(
        self, pattern: str, namespace: Optional[str] = None
    ) -> int:
        """Async variant of invalidate_pattern."""
        try:
            from .invalidation import CacheInvalidator

            invalidator = CacheInvalidator(cache_manager=self)
            return await invalidator.invalidate_pattern_async(
                pattern, namespace=namespace
            )
        except Exception as exc:
            logger.error(
                "UnifiedCacheManager.invalidate_pattern_async failed",
                exc_info=True,
                extra={"pattern": pattern, "namespace": namespace, "error": str(exc)},
            )
            return 0

    def get(
        self,
        cache_type: str,
        key_parts: Optional[List[str]] = None,
        default: Any = None,
        *args,
        **kwargs,
    ) -> Any:
        """
        Get value from cache (synchronous).

        Args:
            cache_type: Type of cache (must be in registered configs)
            key_parts: List of key components
            default: Default value if not found
            *args: Additional arguments for key generation
            **kwargs: Additional keyword arguments for key generation

        Returns:
            Cached value or default
        """
        config = self._cache_configs.get(cache_type)
        if not config:
            logger.warning(f"Unknown cache type: {cache_type}")
            self._update_stats(CacheOperation.GET, False)
            return default

        cache_key = self._generate_cache_key(config, key_parts, *args, **kwargs)

        try:
            # Try Redis first
            cached_data = self._backend.redis_get(cache_key)
            if cached_data is not None:
                result = self._backend.deserialize_from_cache(
                    cached_data, config.serialize_method
                )
                self._update_stats(CacheOperation.GET, True)
                logger.debug(f"Cache HIT (Redis) for key: {cache_key}")
                return result

            # Fallback to local cache
            local_result = self._backend.get_from_local_cache(cache_key)
            if local_result is not None:
                self._update_stats(CacheOperation.GET, True)
                logger.debug(f"Cache HIT (Local) for key: {cache_key}")
                return local_result

            # Cache miss
            self._update_stats(CacheOperation.GET, False)
            logger.debug(f"Cache MISS for key: {cache_key}")
            return default

        except Exception as e:
            logger.error(f"Cache GET error for key {cache_key}: {e}")
            self._update_stats(CacheOperation.GET, False)
            return default

    async def get_async(
        self,
        cache_type: str,
        key_parts: Optional[List[str]] = None,
        default: Any = None,
        *args,
        **kwargs,
    ) -> Any:
        """
        Get value from cache (asynchronous).

        Args:
            cache_type: Type of cache (must be in registered configs)
            key_parts: List of key components
            default: Default value if not found
            *args: Additional arguments for key generation
            **kwargs: Additional keyword arguments for key generation

        Returns:
            Cached value or default
        """
        config = self._cache_configs.get(cache_type)
        if not config:
            logger.warning(f"Unknown cache type: {cache_type}")
            self._update_stats(CacheOperation.GET, False)
            return default

        cache_key = self._generate_cache_key(config, key_parts, *args, **kwargs)

        try:
            # Try Redis first
            cached_data = await self._backend.redis_get_async(cache_key)
            if cached_data is not None:
                result = self._backend.deserialize_from_cache(
                    cached_data, config.serialize_method
                )
                self._update_stats(CacheOperation.GET, True)
                logger.debug(f"Cache HIT (Redis Async) for key: {cache_key}")
                return result

            # Fallback to local cache
            local_result = self._backend.get_from_local_cache(cache_key)
            if local_result is not None:
                self._update_stats(CacheOperation.GET, True)
                logger.debug(f"Cache HIT (Local Async) for key: {cache_key}")
                return local_result

            # Cache miss
            self._update_stats(CacheOperation.GET, False)
            logger.debug(f"Cache MISS (Async) for key: {cache_key}")
            return default

        except Exception as e:
            logger.error(f"Async cache GET error for key {cache_key}: {e}")
            self._update_stats(CacheOperation.GET, False)
            return default

    def set(
        self,
        cache_type: str,
        value: Any,
        key_parts: Optional[List[str]] = None,
        ttl_override: Optional[Union[int, timedelta]] = None,
        *args,
        **kwargs,
    ) -> bool:
        """
        Set value in cache (synchronous).

        Args:
            cache_type: Type of cache (must be in registered configs)
            value: Value to cache
            key_parts: List of key components
            ttl_override: Override default TTL
            *args: Additional arguments for key generation
            **kwargs: Additional keyword arguments for key generation

        Returns:
            True if successful, False otherwise
        """
        config = self._cache_configs.get(cache_type)
        if not config:
            logger.warning(f"Unknown cache type: {cache_type}")
            self._update_stats(CacheOperation.SET, False)
            return False

        cache_key = self._generate_cache_key(config, key_parts, *args, **kwargs)

        # Calculate TTL
        if ttl_override is not None:
            ttl = (
                ttl_override.total_seconds()
                if isinstance(ttl_override, timedelta)
                else ttl_override
            )
        else:
            ttl = config.ttl

        try:
            # Serialize the data
            serialized_data = self._backend.serialize_for_cache(
                value, config.serialize_method
            )

            # Try Redis first
            self._backend.redis_set(cache_key, serialized_data, int(ttl))

            # Also set in local cache as fallback
            self._backend.set_in_local_cache(cache_key, value, int(ttl))

            self._update_stats(CacheOperation.SET, True)
            return True

        except Exception as e:
            logger.error(f"Cache SET error for key {cache_key}: {e}")
            self._update_stats(CacheOperation.SET, False)
            return False

    async def set_async(
        self,
        cache_type: str,
        value: Any,
        key_parts: Optional[List[str]] = None,
        ttl_override: Optional[Union[int, timedelta]] = None,
        *args,
        **kwargs,
    ) -> bool:
        """
        Set value in cache (asynchronous).

        Args:
            cache_type: Type of cache (must be in registered configs)
            value: Value to cache
            key_parts: List of key components
            ttl_override: Override default TTL
            *args: Additional arguments for key generation
            **kwargs: Additional keyword arguments for key generation

        Returns:
            True if successful, False otherwise
        """
        config = self._cache_configs.get(cache_type)
        if not config:
            logger.warning(f"Unknown cache type: {cache_type}")
            self._update_stats(CacheOperation.SET, False)
            return False

        cache_key = self._generate_cache_key(config, key_parts, *args, **kwargs)

        # Calculate TTL
        if ttl_override is not None:
            ttl = (
                ttl_override.total_seconds()
                if isinstance(ttl_override, timedelta)
                else ttl_override
            )
        else:
            ttl = config.ttl

        try:
            # Serialize the data
            serialized_data = self._backend.serialize_for_cache(
                value, config.serialize_method
            )

            # Try Redis first
            await self._backend.redis_set_async(cache_key, serialized_data, int(ttl))

            # Also set in local cache as fallback
            self._backend.set_in_local_cache(cache_key, value, int(ttl))

            self._update_stats(CacheOperation.SET, True)
            return True

        except Exception as e:
            logger.error(f"Async cache SET error for key {cache_key}: {e}")
            self._update_stats(CacheOperation.SET, False)
            return False

    def delete(
        self, cache_type: str, key_parts: Optional[List[str]] = None, *args, **kwargs
    ) -> bool:
        """
        Delete value from cache (synchronous).

        Args:
            cache_type: Type of cache
            key_parts: List of key components
            *args: Additional arguments for key generation
            **kwargs: Additional keyword arguments for key generation

        Returns:
            True if deleted, False otherwise
        """
        config = self._cache_configs.get(cache_type)
        if not config:
            self._update_stats(CacheOperation.DELETE, False)
            return False

        cache_key = self._generate_cache_key(config, key_parts, *args, **kwargs)

        try:
            # Delete from Redis
            self._backend.redis_delete(cache_key)

            # Remove from local cache
            self._backend.remove_from_local_cache(cache_key)

            self._update_stats(CacheOperation.DELETE, True)
            return True

        except Exception as e:
            logger.error(f"Cache DELETE error for key {cache_key}: {e}")
            self._update_stats(CacheOperation.DELETE, False)
            return False

    async def delete_async(
        self, cache_type: str, key_parts: Optional[List[str]] = None, *args, **kwargs
    ) -> bool:
        """
        Delete value from cache (asynchronous).

        Args:
            cache_type: Type of cache
            key_parts: List of key components
            *args: Additional arguments for key generation
            **kwargs: Additional keyword arguments for key generation

        Returns:
            True if deleted, False otherwise
        """
        config = self._cache_configs.get(cache_type)
        if not config:
            self._update_stats(CacheOperation.DELETE, False)
            return False

        cache_key = self._generate_cache_key(config, key_parts, *args, **kwargs)

        try:
            # Delete from Redis
            await self._backend.redis_delete_async(cache_key)

            # Remove from local cache
            self._backend.remove_from_local_cache(cache_key)

            self._update_stats(CacheOperation.DELETE, True)
            return True

        except Exception as e:
            logger.error(f"Async cache DELETE error for key {cache_key}: {e}")
            self._update_stats(CacheOperation.DELETE, False)
            return False

    def exists(
        self, cache_type: str, key_parts: Optional[List[str]] = None, *args, **kwargs
    ) -> bool:
        """
        Check if key exists in cache (synchronous).

        Args:
            cache_type: Type of cache
            key_parts: List of key components
            *args: Additional arguments for key generation
            **kwargs: Additional keyword arguments for key generation

        Returns:
            True if key exists, False otherwise
        """
        config = self._cache_configs.get(cache_type)
        if not config:
            return False

        cache_key = self._generate_cache_key(config, key_parts, *args, **kwargs)

        try:
            # Check Redis first
            if self._backend.redis_exists(cache_key):
                return True

            # Check local cache
            return self._backend.get_from_local_cache(cache_key) is not None

        except Exception as e:
            logger.error(f"Cache EXISTS error for {cache_key}: {e}")
            return False

    async def exists_async(
        self, cache_type: str, key_parts: Optional[List[str]] = None, *args, **kwargs
    ) -> bool:
        """
        Check if key exists in cache (asynchronous).

        Args:
            cache_type: Type of cache
            key_parts: List of key components
            *args: Additional arguments for key generation
            **kwargs: Additional keyword arguments for key generation

        Returns:
            True if key exists, False otherwise
        """
        config = self._cache_configs.get(cache_type)
        if not config:
            return False

        cache_key = self._generate_cache_key(config, key_parts, *args, **kwargs)

        try:
            # Check Redis first
            if await self._backend.redis_exists_async(cache_key):
                return True

            # Check local cache
            return self._backend.get_from_local_cache(cache_key) is not None

        except Exception as e:
            logger.error(f"Async cache EXISTS error for {cache_key}: {e}")
            return False

    def get_ttl(
        self, cache_type: str, key_parts: Optional[List[str]] = None, *args, **kwargs
    ) -> Optional[int]:
        """
        Get remaining TTL for a cache key (synchronous).

        Args:
            cache_type: Type of cache
            key_parts: List of key components
            *args: Additional arguments for key generation
            **kwargs: Additional keyword arguments for key generation

        Returns:
            Remaining TTL in seconds, None if key doesn't exist or no TTL
        """
        config = self._cache_configs.get(cache_type)
        if not config:
            return None

        cache_key = self._generate_cache_key(config, key_parts, *args, **kwargs)

        try:
            # Check Redis first
            ttl = self._backend.redis_ttl(cache_key)
            if ttl is not None:
                return ttl

            # Check local cache
            if cache_key in self._backend._local_cache:
                cache_entry = self._backend._local_cache[cache_key]
                remaining = (
                    cache_entry["expires_at"] - datetime.now(timezone.utc)
                ).total_seconds()
                return int(remaining) if remaining > 0 else None

            return None

        except Exception as e:
            logger.error(f"Cache TTL error for {cache_key}: {e}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary containing cache statistics
        """
        if not self._stats:
            return {"stats_disabled": True}

        return {
            "hits": self._stats.hits,
            "misses": self._stats.misses,
            "errors": self._stats.errors,
            "sets": self._stats.sets,
            "deletes": self._stats.deletes,
            "invalidations": self._stats.invalidations,
            "total_requests": self._stats.total_requests,
            "hit_rate_percent": round(self._stats.hit_rate, 2),
            "local_cache_size": self._backend.get_local_cache_size(),
            "last_reset": self._stats.last_reset.isoformat(),
            "registered_cache_types": list(self._cache_configs.keys()),
        }

    def reset_stats(self):
        """Reset cache statistics."""
        if self._stats:
            self._stats.reset()

    def clear_local_cache(self):
        """Clear local cache."""
        self._backend.clear_local_cache()

    def warmup_cache(
        self, cache_type: str, data_loader: Callable, key_parts_list: List[List[str]]
    ):
        """
        Warm up cache with preloaded data (synchronous).

        Args:
            cache_type: Type of cache
            data_loader: Function to load data
            key_parts_list: List of key parts for cache entries
        """
        logger.info(
            f"Starting cache warmup for {cache_type} with {len(key_parts_list)} entries"
        )

        for key_parts in key_parts_list:
            try:
                data = data_loader(*key_parts)
                if data is not None:
                    self.set(cache_type, data, key_parts)
                    logger.debug(
                        f"Warmed up cache for {cache_type}:{':'.join(key_parts)}"
                    )
            except Exception as e:
                logger.warning(
                    f"Cache warmup failed for {cache_type}:{':'.join(key_parts)}: {e}"
                )

        logger.info(f"Cache warmup completed for {cache_type}")

    async def warmup_cache_async(
        self, cache_type: str, data_loader: Callable, key_parts_list: List[List[str]]
    ):
        """
        Warm up cache with preloaded data (asynchronous).

        Args:
            cache_type: Type of cache
            data_loader: Async function to load data
            key_parts_list: List of key parts for cache entries
        """
        logger.info(
            f"Starting async cache warmup for {cache_type} with {len(key_parts_list)} entries"
        )

        tasks = []
        for key_parts in key_parts_list:

            async def _warmup_entry(kp=key_parts):
                try:
                    data = await data_loader(*kp)
                    if data is not None:
                        await self.set_async(cache_type, data, kp)
                        logger.debug(
                            f"Warmed up cache (async) for {cache_type}:{':'.join(kp)}"
                        )
                except Exception as e:
                    logger.warning(
                        f"Async cache warmup failed for {cache_type}:{':'.join(kp)}: {e}"
                    )

            tasks.append(_warmup_entry())

        # Execute warmup tasks concurrently
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info(f"Async cache warmup completed for {cache_type}")


# Global cache manager instance
_unified_cache_manager: Optional[UnifiedCacheManager] = None


def get_unified_cache_manager(
    redis_client: Optional[Union[Redis, AsyncRedis]] = None,
    enable_stats: bool = True,
    enable_local_fallback: bool = True,
) -> UnifiedCacheManager:
    """
    Get global unified cache manager singleton.

    Args:
        redis_client: Optional Redis client instance
        enable_stats: Whether to track cache statistics
        enable_local_fallback: Whether to use local cache as fallback

    Returns:
        UnifiedCacheManager instance
    """
    global _unified_cache_manager
    if _unified_cache_manager is None:
        _unified_cache_manager = UnifiedCacheManager(
            redis_client=redis_client,
            enable_stats=enable_stats,
            enable_local_fallback=enable_local_fallback,
        )
    return _unified_cache_manager


# Alias for backward compatibility
UnifiedCache = UnifiedCacheManager
CacheManager = UnifiedCacheManager


__all__ = [
    "UnifiedCacheManager",
    "UnifiedCache",
    "CacheManager",
    "CacheConfig",
    "CacheStats",
    "CacheOperation",
    "DEFAULT_CACHE_CONFIGS",
    "get_unified_cache_manager",
]
