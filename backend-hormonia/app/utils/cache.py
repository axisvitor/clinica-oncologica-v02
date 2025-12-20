"""
Distributed caching utilities using Redis for the Hormonia Oncology System.
Provides decorators and helper functions for caching with TTL support.
"""

import json
import logging
import functools
from typing import Any, Callable, Optional, Union, Dict
from datetime import timedelta, datetime, timezone
from uuid import UUID
from decimal import Decimal
import hashlib

from app.core.redis_unified import get_sync_redis, get_async_redis

logger = logging.getLogger(__name__)


def _json_serializer(obj: Any) -> Any:
    """JSON serializer for complex objects."""
    if isinstance(obj, (datetime, UUID)):
        return str(obj)
    elif isinstance(obj, Decimal):
        return float(obj)
    elif hasattr(obj, "__dict__"):
        # For SQLAlchemy models or complex objects
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    else:
        return str(obj)


def _serialize_for_cache(obj: Any) -> str:
    """Serialize complex objects for caching."""
    try:
        if hasattr(obj, "__dict__"):
            # For SQLAlchemy models or complex objects
            data = {}
            for key, value in obj.__dict__.items():
                if not key.startswith("_") and not callable(value):
                    data[key] = value
            return json.dumps(data, default=_json_serializer)
        else:
            return json.dumps(obj, default=_json_serializer)
    except (TypeError, ValueError):
        return str(obj)


def _deserialize_from_cache(data: str) -> Any:
    """Deserialize data from cache with fallback."""
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return data


def _generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Generate a unique cache key from function arguments.

    Args:
        prefix: Cache key prefix
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Unique cache key string
    """
    # Create a string representation of all arguments
    key_parts = [prefix]

    if args:
        key_parts.extend([str(arg) for arg in args])

    if kwargs:
        # Sort kwargs for consistent key generation
        sorted_kwargs = sorted(kwargs.items())
        key_parts.extend([f"{k}={v}" for k, v in sorted_kwargs])

    # Join parts and hash if too long
    cache_key = ":".join(key_parts)

    # Hash long keys to avoid Redis key length limits
    if len(cache_key) > 200:
        hash_suffix = hashlib.md5(cache_key.encode()).hexdigest()
        cache_key = f"{prefix}:hash:{hash_suffix}"

    return cache_key


def cache(
    ttl: Union[int, timedelta] = 3600,
    key_prefix: Optional[str] = None,
    namespace: str = "cache",
) -> Callable:
    """
    Decorator to cache function results in Redis with automatic TTL.

    Args:
        ttl: Time-to-live in seconds (int) or timedelta object
        key_prefix: Custom key prefix (defaults to function name)
        namespace: Cache namespace for organization

    Usage:
        @cache(ttl=300)
        def get_user_data(user_id: int):
            return fetch_user_from_db(user_id)

        @cache(ttl=timedelta(hours=1), key_prefix="patient")
        def get_patient_info(patient_id: str):
            return fetch_patient_data(patient_id)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Calculate TTL in seconds
            ttl_seconds = ttl.total_seconds() if isinstance(ttl, timedelta) else ttl

            # Generate cache key
            prefix = key_prefix or func.__name__
            full_prefix = f"{namespace}:{prefix}"
            cache_key = _generate_cache_key(full_prefix, *args, **kwargs)

            # Try to get from cache
            redis_client = get_sync_redis()

            try:
                cached_value = redis_client.get(cache_key)
                if cached_value is not None:
                    logger.debug(f"Cache HIT for key: {cache_key}")
                    return _deserialize_from_cache(cached_value)
            except Exception as e:
                logger.warning(f"Cache GET failed for {cache_key}: {e}")

            # Cache miss - execute function
            logger.debug(f"Cache MISS for key: {cache_key}")
            result = func(*args, **kwargs)

            # Store in cache
            try:
                # Use enhanced serialization for complex objects
                if isinstance(result, str):
                    serialized_result = result
                elif hasattr(result, "__dict__"):  # SQLAlchemy model or complex object
                    serialized_result = _serialize_for_cache(result)
                else:
                    serialized_result = json.dumps(result, default=_json_serializer)
                redis_client.set(cache_key, serialized_result, ex=int(ttl_seconds))
                logger.debug(
                    f"Cached result for key: {cache_key} (TTL: {ttl_seconds}s)"
                )
            except Exception as e:
                logger.warning(f"Cache SET failed for {cache_key}: {e}")

            return result

        return wrapper

    return decorator


class CacheManager:
    """
    Manager class for advanced caching operations with Redis.
    Provides explicit cache control and invalidation methods.
    """

    def __init__(self, redis_client=None):
        """
        Initialize cache manager.

        Args:
            redis_client: Optional Redis client instance (uses singleton if not provided)
        """
        self.redis = redis_client or get_sync_redis()
        self.namespace = "cache"

    def get(self, key: str, namespace: Optional[str] = None) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key
            namespace: Optional namespace (defaults to instance namespace)

        Returns:
            Cached value or None if not found
        """
        full_key = f"{namespace or self.namespace}:{key}"

        try:
            value = self.redis.get(full_key)
            if value is not None:
                return _deserialize_from_cache(value)
            return None
        except Exception as e:
            logger.error(f"Cache GET error for {full_key}: {e}")
            return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: Union[int, timedelta] = 3600,
        namespace: Optional[str] = None,
    ) -> bool:
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (int) or timedelta
            namespace: Optional namespace (defaults to instance namespace)

        Returns:
            True if successful, False otherwise
        """
        full_key = f"{namespace or self.namespace}:{key}"
        ttl_seconds = ttl.total_seconds() if isinstance(ttl, timedelta) else ttl

        try:
            # Use enhanced serialization for complex objects
            if isinstance(value, str):
                serialized_value = value
            elif hasattr(value, "__dict__"):  # SQLAlchemy model or complex object
                serialized_value = _serialize_for_cache(value)
            else:
                serialized_value = json.dumps(value, default=_json_serializer)

            return self.redis.set(full_key, serialized_value, ex=int(ttl_seconds))
        except Exception as e:
            logger.error(f"Cache SET error for {full_key}: {e}")
            return False

    def delete(self, key: str, namespace: Optional[str] = None) -> bool:
        """
        Delete value from cache.

        Args:
            key: Cache key
            namespace: Optional namespace (defaults to instance namespace)

        Returns:
            True if deleted, False otherwise
        """
        full_key = f"{namespace or self.namespace}:{key}"

        try:
            return self.redis.delete(full_key)
        except Exception as e:
            logger.error(f"Cache DELETE error for {full_key}: {e}")
            return False

    def invalidate_pattern(self, pattern: str, namespace: Optional[str] = None) -> int:
        """
        Invalidate all cache keys matching a pattern.

        Args:
            pattern: Key pattern (supports wildcards like "user:*")
            namespace: Optional namespace (defaults to instance namespace)

        Returns:
            Number of keys deleted
        """
        full_pattern = f"{namespace or self.namespace}:{pattern}"

        try:
            keys = self.redis.keys(full_pattern)
            if not keys:
                return 0

            deleted = 0
            for key in keys:
                if self.redis.delete(key):
                    deleted += 1

            logger.info(f"Invalidated {deleted} cache keys matching: {full_pattern}")
            return deleted
        except Exception as e:
            logger.error(f"Cache invalidation error for pattern {full_pattern}: {e}")
            return 0

    def invalidate_namespace(self, namespace: str) -> int:
        """
        Invalidate all cache keys in a namespace.

        Args:
            namespace: Namespace to invalidate

        Returns:
            Number of keys deleted
        """
        return self.invalidate_pattern("*", namespace=namespace)

    def exists(self, key: str, namespace: Optional[str] = None) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key
            namespace: Optional namespace (defaults to instance namespace)

        Returns:
            True if key exists, False otherwise
        """
        full_key = f"{namespace or self.namespace}:{key}"

        try:
            return self.redis.exists(full_key)
        except Exception as e:
            logger.error(f"Cache EXISTS error for {full_key}: {e}")
            return False

    def get_ttl(self, key: str, namespace: Optional[str] = None) -> Optional[int]:
        """
        Get remaining TTL for a cache key.

        Args:
            key: Cache key
            namespace: Optional namespace (defaults to instance namespace)

        Returns:
            Remaining TTL in seconds, None if key doesn't exist or no TTL
        """
        full_key = f"{namespace or self.namespace}:{key}"

        try:
            ttl = self.redis.ttl(full_key)
            return ttl if ttl > 0 else None
        except Exception as e:
            logger.error(f"Cache TTL error for {full_key}: {e}")
            return None


# Global cache manager instance
_cache_manager = None


def get_cache_manager() -> CacheManager:
    """
    Get global cache manager singleton.

    Returns:
        CacheManager instance
    """
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


# Enhanced async-aware cache manager for better Redis integration
class AsyncCacheManager:
    """Async-aware cache manager with Redis."""

    def __init__(self):
        self.namespace = "cache"

    async def get(self, key: str, namespace: Optional[str] = None) -> Optional[Any]:
        """Get value from cache (async)."""
        full_key = f"{namespace or self.namespace}:{key}"
        try:
            redis_client = await get_async_redis()
            value = await redis_client.get(full_key)
            return _deserialize_from_cache(value) if value else None
        except Exception as e:
            logger.error(f"Async cache GET error for {full_key}: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Union[int, timedelta] = 3600,
        namespace: Optional[str] = None,
    ) -> bool:
        """Set value in cache with TTL (async)."""
        full_key = f"{namespace or self.namespace}:{key}"
        ttl_seconds = ttl.total_seconds() if isinstance(ttl, timedelta) else ttl
        try:
            redis_client = await get_async_redis()
            serialized_value = (
                _serialize_for_cache(value) if not isinstance(value, str) else value
            )
            return await redis_client.set(
                full_key, serialized_value, ex=int(ttl_seconds)
            )
        except Exception as e:
            logger.error(f"Async cache SET error for {full_key}: {e}")
            return False

    async def delete(self, key: str, namespace: Optional[str] = None) -> bool:
        """Delete value from cache (async)."""
        full_key = f"{namespace or self.namespace}:{key}"
        try:
            redis_client = await get_async_redis()
            return await redis_client.delete(full_key)
        except Exception as e:
            logger.error(f"Async cache DELETE error for {full_key}: {e}")
            return False


# Global async cache manager
_async_cache_manager = None


def get_async_cache_manager() -> AsyncCacheManager:
    """Get global async cache manager singleton."""
    global _async_cache_manager
    if _async_cache_manager is None:
        _async_cache_manager = AsyncCacheManager()
    return _async_cache_manager


# Convenience functions for common caching patterns (sync versions for compatibility)


def cache_user_data(user_id: str, data: Any, ttl: int = 1800) -> bool:
    """Cache user data with 30-minute default TTL (sync version)"""
    manager = get_cache_manager()
    return manager.set(f"user:{user_id}", data, ttl=ttl, namespace="users")


def get_cached_user_data(user_id: str) -> Optional[Any]:
    """Get cached user data (sync version)"""
    manager = get_cache_manager()
    return manager.get(f"user:{user_id}", namespace="users")


def invalidate_user_cache(user_id: str) -> bool:
    """Invalidate specific user cache (sync version)"""
    manager = get_cache_manager()
    return manager.delete(f"user:{user_id}", namespace="users")


# Async versions of convenience functions
async def cache_user_data_async(user_id: str, data: Any, ttl: int = 1800) -> bool:
    """Cache user data with 30-minute default TTL (async version)"""
    manager = get_async_cache_manager()
    return await manager.set(f"user:{user_id}", data, ttl=ttl, namespace="users")


async def get_cached_user_data_async(user_id: str) -> Optional[Any]:
    """Get cached user data (async version)"""
    manager = get_async_cache_manager()
    return await manager.get(f"user:{user_id}", namespace="users")


async def invalidate_user_cache_async(user_id: str) -> bool:
    """Invalidate specific user cache (async version)"""
    manager = get_async_cache_manager()
    return await manager.delete(f"user:{user_id}", namespace="users")


def cache_patient_data(patient_id: str, data: Any, ttl: int = 3600) -> bool:
    """Cache patient data with 1-hour default TTL (sync version)"""
    manager = get_cache_manager()
    return manager.set(f"patient:{patient_id}", data, ttl=ttl, namespace="patients")


def get_cached_patient_data(patient_id: str) -> Optional[Any]:
    """Get cached patient data (sync version)"""
    manager = get_cache_manager()
    return manager.get(f"patient:{patient_id}", namespace="patients")


def invalidate_patient_cache(patient_id: str) -> bool:
    """Invalidate specific patient cache (sync version)"""
    manager = get_cache_manager()
    return manager.delete(f"patient:{patient_id}", namespace="patients")


# Async versions for patient data
async def cache_patient_data_async(patient_id: str, data: Any, ttl: int = 3600) -> bool:
    """Cache patient data with 1-hour default TTL (async version)"""
    manager = get_async_cache_manager()
    return await manager.set(
        f"patient:{patient_id}", data, ttl=ttl, namespace="patients"
    )


async def get_cached_patient_data_async(patient_id: str) -> Optional[Any]:
    """Get cached patient data (async version)"""
    manager = get_async_cache_manager()
    return await manager.get(f"patient:{patient_id}", namespace="patients")


async def invalidate_patient_cache_async(patient_id: str) -> bool:
    """Invalidate specific patient cache (async version)"""
    manager = get_async_cache_manager()
    return await manager.delete(f"patient:{patient_id}", namespace="patients")


# Context manager for async cache operations
class AsyncCacheContext:
    """Async context manager for Redis cache operations."""

    def __init__(self):
        self.manager = get_async_cache_manager()

    async def __aenter__(self) -> AsyncCacheManager:
        return self.manager

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def async_cache() -> AsyncCacheContext:
    """Create async cache context manager.

    Usage:
        async with async_cache() as cache:
            await cache.set("key", "value")
            value = await cache.get("key")
    """
    return AsyncCacheContext()


# Redis connection management for system initialization
def get_redis_client():
    """Get Redis client for system operations."""
    return get_sync_redis()


def reset_redis_connections() -> bool:
    """
    Reset Redis connection pools for system restart.

    This function clears connection pools and forces
    new connections to be established.

    Returns:
        True if reset successful, False otherwise
    """
    try:
        global _cache_manager, _async_cache_manager

        # Clear global cache managers to force new connections
        _cache_manager = None
        _async_cache_manager = None

        # Reset the Redis connection pools in the unified module
        from app.core.redis_unified import reset_redis_pools

        reset_redis_pools()

        logger.info("✅ Redis connections reset successfully")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to reset Redis connections: {e}")
        return False


def test_redis_connectivity() -> Dict[str, Any]:
    """
    Test Redis connectivity with comprehensive checks.

    Returns:
        Dictionary with connectivity test results
    """
    test_results = {
        "status": "unknown",
        "tests": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        redis_client = get_redis_client()

        # Test 1: Basic ping
        start_time = datetime.now(timezone.utc)
        ping_result = redis_client.ping()
        ping_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        test_results["tests"]["ping"] = {
            "status": "success" if ping_result else "failed",
            "response_time_ms": ping_time,
        }

        # Test 2: Set/Get operation
        test_key = "connectivity_test"
        test_value = "test_value_123"

        start_time = datetime.now(timezone.utc)
        redis_client.set(test_key, test_value, ex=60)  # 60 second expiry
        retrieved_value = redis_client.get(test_key)
        operation_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        test_results["tests"]["set_get"] = {
            "status": "success" if retrieved_value.decode() == test_value else "failed",
            "response_time_ms": operation_time,
        }

        # Clean up test key
        redis_client.delete(test_key)

        # Test 3: Get Redis info
        redis_info = redis_client.info()
        test_results["tests"]["info"] = {
            "status": "success",
            "redis_version": redis_info.get("redis_version"),
            "memory_used": redis_info.get("used_memory_human"),
            "connected_clients": redis_info.get("connected_clients"),
        }

        # Overall status
        all_tests_passed = all(
            test.get("status") == "success" for test in test_results["tests"].values()
        )
        test_results["status"] = "healthy" if all_tests_passed else "unhealthy"

    except Exception as e:
        test_results["status"] = "unhealthy"
        test_results["error"] = str(e)
        logger.error(f"Redis connectivity test failed: {e}")

    return test_results
