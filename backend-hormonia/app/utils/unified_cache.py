"""
Unified Cache Utility Service - DEPRECATED

⚠️ DEPRECATION NOTICE:
This module has been refactored and moved to app.infrastructure.cache.

Please update your imports:
    OLD: from app.utils.unified_cache import UnifiedCacheManager
    NEW: from app.infrastructure.cache import UnifiedCacheManager

This wrapper is maintained for backward compatibility only and may be removed in a future version.
"""

import warnings

# Issue deprecation warning
warnings.warn(
    "app.utils.unified_cache is deprecated and will be removed in a future version. "
    "Please use app.infrastructure.cache instead. "
    "Update your imports: from app.infrastructure.cache import UnifiedCacheManager",
    DeprecationWarning,
    stacklevel=2
)

# Re-export all public APIs from the new location for backward compatibility
from app.infrastructure.cache import (
    # Core classes
    UnifiedCacheManager,
    UnifiedCache,
    CacheManager,
    CacheConfig,
    CacheStats,
    CacheOperation,
    SerializationMethod,
    DEFAULT_CACHE_CONFIGS,

    # Main factory
    get_unified_cache_manager,

    # Decorators
    cache,
    cached,
    async_cache,
    cache_result,
    cache_response,
    cache_context,

    # Invalidation
    CacheInvalidator,
    invalidate_cache,

    # User cache operations
    cache_user_data,
    get_cached_user_data,
    invalidate_user_cache,
    cache_user_data_async,
    get_cached_user_data_async,
    invalidate_user_cache_async,

    # Patient cache operations
    cache_patient_data,
    get_cached_patient_data,
    invalidate_patient_cache,
    cache_patient_data_async,
    get_cached_patient_data_async,
    invalidate_patient_cache_async,

    # Utilities
    generate_request_cache_key,
    generate_user_cache_key,
    get_cache_manager,

    # Backend
    RedisBackend
)

__all__ = [
    "UnifiedCacheManager",
    "UnifiedCache",
    "CacheManager",
    "CacheConfig",
    "CacheStats",
    "SerializationMethod",
    "CacheOperation",
    "get_unified_cache_manager",
    "cache",
    "cached",
    "async_cache",
    "cache_context",
    "cache_user_data",
    "get_cached_user_data",
    "invalidate_user_cache",
    "cache_user_data_async",
    "get_cached_user_data_async",
    "invalidate_user_cache_async",
    "cache_patient_data",
    "get_cached_patient_data",
    "invalidate_patient_cache",
    "cache_patient_data_async",
    "get_cached_patient_data_async",
    "invalidate_patient_cache_async",
    "get_cache_manager",
    "cache_result",
    "cache_response",
    "generate_request_cache_key",
    "generate_user_cache_key",
    "invalidate_cache",
    "CacheInvalidator",
    "RedisBackend",
    "DEFAULT_CACHE_CONFIGS"
]
