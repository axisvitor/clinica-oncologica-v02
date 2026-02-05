"""
Cache Decorators Module

This module provides decorators for easy function caching, both sync and async,
along with context managers and utility functions for cache operations.
"""

import functools
from typing import Callable, Optional, Union, List
from datetime import timedelta
from contextlib import asynccontextmanager

from starlette.requests import Request

from app.utils.logging import get_logger
from .cache_manager import get_unified_cache_manager, CacheConfig

logger = get_logger(__name__)


def cache(
    cache_type: str = "analytics_dashboard",
    ttl: Optional[Union[int, timedelta]] = None,
    key_prefix: Optional[str] = None,
    namespace: str = "cache",
) -> Callable:
    """
    Decorator to cache function results (synchronous functions).

    Args:
        cache_type: Type of cache to use (must be registered)
        ttl: Time-to-live override
        key_prefix: Custom key prefix (defaults to function name)
        namespace: Cache namespace

    Usage:
        @cache(cache_type="user_profile", ttl=300)
        def get_user_data(user_id: int):
            return fetch_user_from_db(user_id)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get cache manager
            manager = get_unified_cache_manager()

            # Generate cache key from function name and arguments
            func_name = key_prefix or func.__name__

            # If cache_type is not registered, register it with defaults
            if cache_type not in manager._cache_configs:
                default_ttl = (
                    ttl.total_seconds() if isinstance(ttl, timedelta) else (ttl or 3600)
                )
                config = CacheConfig(
                    ttl=int(default_ttl), key_prefix=func_name, namespace=namespace
                )
                manager.register_cache_config(cache_type, config)

            # Try to get from cache
            cached_result = manager.get(cache_type, None, None, *args, **kwargs)
            if cached_result is not None:
                logger.debug(f"Cache HIT for function: {func_name}")
                return cached_result

            # Cache miss - execute function
            logger.debug(f"Cache MISS for function: {func_name}")
            result = func(*args, **kwargs)

            # Store in cache
            if result is not None:
                manager.set(cache_type, result, None, ttl, *args, **kwargs)
                logger.debug(f"Cached result for function: {func_name}")

            return result

        return wrapper

    return decorator


def async_cache(
    cache_type: str = "analytics_dashboard",
    ttl: Optional[Union[int, timedelta]] = None,
    key_prefix: Optional[str] = None,
    namespace: str = "cache",
) -> Callable:
    """
    Decorator to cache async function results.

    Args:
        cache_type: Type of cache to use (must be registered)
        ttl: Time-to-live override
        key_prefix: Custom key prefix (defaults to function name)
        namespace: Cache namespace

    Usage:
        @async_cache(cache_type="user_profile", ttl=300)
        async def get_user_data_async(user_id: int):
            return await fetch_user_from_db_async(user_id)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Get cache manager
            manager = get_unified_cache_manager()

            # Generate cache key from function name and arguments
            func_name = key_prefix or func.__name__

            # If cache_type is not registered, register it with defaults
            if cache_type not in manager._cache_configs:
                default_ttl = (
                    ttl.total_seconds() if isinstance(ttl, timedelta) else (ttl or 3600)
                )
                config = CacheConfig(
                    ttl=int(default_ttl), key_prefix=func_name, namespace=namespace
                )
                manager.register_cache_config(cache_type, config)

            # Try to get from cache
            cached_result = await manager.get_async(
                cache_type, None, None, *args, **kwargs
            )
            if cached_result is not None:
                logger.debug(f"Cache HIT for async function: {func_name}")
                return cached_result

            # Cache miss - execute function
            logger.debug(f"Cache MISS for async function: {func_name}")
            result = await func(*args, **kwargs)

            # Store in cache
            if result is not None:
                await manager.set_async(cache_type, result, None, ttl, *args, **kwargs)
                logger.debug(f"Cached result for async function: {func_name}")

            return result

        return wrapper

    return decorator


def cache_result(
    cache_type: str,
    key_generator: Callable[..., List[str]],
    ttl_override: Optional[int] = None,
):
    """
    Decorator for caching function results (backward compatibility with caching.py).

    Args:
        cache_type: Type of cache to use
        key_generator: Function to generate cache key parts from function args
        ttl_override: Override default TTL
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cache_manager = get_unified_cache_manager()

            # Generate cache key
            try:
                key_parts = key_generator(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Cache key generation failed: {e}")
                return await func(*args, **kwargs)

            # Try to get from cache
            cached_result = await cache_manager.get_async(cache_type, key_parts)
            if cached_result is not None:
                logger.debug(f"Cache hit for {cache_type}:{':'.join(key_parts)}")
                return cached_result

            # Execute function and cache result
            result = await func(*args, **kwargs)

            # Cache the result
            await cache_manager.set_async(cache_type, result, key_parts, ttl_override)
            logger.debug(f"Cached result for {cache_type}:{':'.join(key_parts)}")

            return result

        return wrapper

    return decorator


def cache_response(
    seconds: int = 300,
    *,
    ttl: Optional[int] = None,
    key_prefix: Optional[str] = None,
    cache_type: str = "analytics_dashboard",
):
    """
    Decorator for caching HTTP response data (backward compatibility with caching.py).

    Args:
        seconds: Cache TTL in seconds (default 5 minutes)
        ttl: Optional override for TTL (takes precedence over ``seconds``)
        key_prefix: Optional custom key prefix (defaults to function name)
        cache_type: Cache bucket/type registered in the unified cache manager
    """

    ttl_seconds = ttl if ttl is not None else seconds

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cache_manager = get_unified_cache_manager()

            # Generate cache key from function name and arguments
            func_name = key_prefix or func.__name__
            request_obj = None
            for arg in args:
                if isinstance(arg, Request):
                    request_obj = arg
                    break
            if request_obj is None:
                for value in kwargs.values():
                    if isinstance(value, Request):
                        request_obj = value
                        break

            if request_obj is not None:
                key_parts = [
                    func_name,
                    request_obj.url.path,
                    request_obj.url.query,
                ]
            else:
                key_parts = [
                    func_name,
                    str(hash(str(args) + str(sorted(kwargs.items())))),
                ]

            # Try to get from cache
            cached_result = await cache_manager.get_async(cache_type, key_parts)
            if cached_result is not None:
                logger.debug(f"Cache hit for response {func_name}")
                return cached_result

            # Execute function and cache result
            result = await func(*args, **kwargs)

            # Cache the result
            await cache_manager.set_async(cache_type, result, key_parts, ttl_seconds)
            logger.debug(f"Cached response for {func_name}")

            return result

        return wrapper

    return decorator


# Context managers for cache operations
@asynccontextmanager
async def cache_context():
    """
    Async context manager for cache operations.

    Usage:
        async with cache_context() as cache:
            await cache.set_async("user_profile", user_data, ["user_123"])
            data = await cache.get_async("user_profile", ["user_123"])
    """
    manager = get_unified_cache_manager()
    try:
        yield manager
    finally:
        pass


# Utility functions for cache key generation
def generate_request_cache_key(
    request, additional_parts: List[str] = None
) -> List[str]:
    """Generate cache key parts from request (backward compatibility)."""
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
    """Generate cache key parts for user-specific data (backward compatibility)."""
    parts = [user_id]

    if additional_parts:
        parts.extend(additional_parts)

    return parts


# Alias for backward compatibility
cached = cache


__all__ = [
    "cache",
    "cached",
    "async_cache",
    "cache_result",
    "cache_response",
    "cache_context",
    "generate_request_cache_key",
    "generate_user_cache_key",
]
