"""
Unified Cache Infrastructure Module

This module provides a comprehensive caching solution with:
- Redis backend with local fallback
- Sync and async operations
- Cache decorators for easy function caching
- Pattern-based cache invalidation
- Statistics and monitoring
- Backward compatibility with legacy cache modules

Public API exports all commonly used cache utilities.
"""

# Core cache manager and configuration
from .cache_manager import (
    UnifiedCacheManager,
    UnifiedCache,
    CacheManager,
    CacheConfig,
    CacheStats,
    CacheOperation,
    DEFAULT_CACHE_CONFIGS,
    get_unified_cache_manager,
)

# Redis backend
from .redis_backend import RedisBackend, SerializationMethod

# Cache decorators and utilities
from .cache_decorators import (
    cache,
    cached,
    async_cache,
    cache_result,
    cache_response,
    cache_context,
    generate_request_cache_key,
    generate_user_cache_key,
)

# Cache invalidation
from .invalidation import (
    CacheInvalidator,
    cache_user_data,
    get_cached_user_data,
    invalidate_user_cache,
    cache_user_data_async,
    get_cached_user_data_async,
    invalidate_user_cache_async,
    cache_patient_data,
    get_cached_patient_data,
    invalidate_patient_cache,
    cache_patient_data_async,
    get_cached_patient_data_async,
    invalidate_patient_cache_async,
    invalidate_cache,
    get_cache_manager,
)

__all__ = [
    # Core cache manager
    "UnifiedCacheManager",
    "UnifiedCache",
    "CacheManager",
    "CacheConfig",
    "CacheStats",
    "CacheOperation",
    "DEFAULT_CACHE_CONFIGS",
    "get_unified_cache_manager",
    # Redis backend
    "RedisBackend",
    "SerializationMethod",
    # Decorators
    "cache",
    "cached",
    "async_cache",
    "cache_result",
    "cache_response",
    "cache_context",
    # Invalidation
    "CacheInvalidator",
    "invalidate_cache",
    # User cache operations (backward compatibility)
    "cache_user_data",
    "get_cached_user_data",
    "invalidate_user_cache",
    "cache_user_data_async",
    "get_cached_user_data_async",
    "invalidate_user_cache_async",
    # Patient cache operations (backward compatibility)
    "cache_patient_data",
    "get_cached_patient_data",
    "invalidate_patient_cache",
    "cache_patient_data_async",
    "get_cached_patient_data_async",
    "invalidate_patient_cache_async",
    # Utilities
    "generate_request_cache_key",
    "generate_user_cache_key",
    "get_cache_manager",
]
