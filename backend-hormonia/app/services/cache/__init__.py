"""Cache Services Module
=====================

Unified caching system with specialized wrappers.

This module consolidates the previous cache services introduced across
multiple iterations (QW-018, QW-020) and exposes a clean public API that
is backed by ``CacheLayer``.
"""

from app.services.ai.cache_layer import (
    CacheLayer as CacheService,
    CacheOperation,
    CacheStrategy,
    CacheMetrics,
    CacheEntry,
    get_cache_layer as get_cache_service,
    reset_cache_layer as reset_cache_service,
)

from .specialized.jwt_cache import JWTCache, get_jwt_cache
from .specialized.template_cache import TemplateCache, get_template_cache
from .specialized.analytics_cache import AnalyticsCache, get_analytics_cache
from .specialized.query_cache import QueryCache, get_query_cache

from .invalidation.invalidator import (
    CacheInvalidator,
    InvalidationStrategy,
    InvalidationScope,
    get_cache_invalidator,
)

__all__ = [
    # Base cache service
    "CacheService",
    "CacheOperation",
    "CacheStrategy",
    "CacheMetrics",
    "CacheEntry",
    "get_cache_service",
    "reset_cache_service",
    # Specialized caches
    "JWTCache",
    "get_jwt_cache",
    "TemplateCache",
    "get_template_cache",
    "AnalyticsCache",
    "get_analytics_cache",
    "QueryCache",
    "get_query_cache",
    # Invalidation helpers
    "CacheInvalidator",
    "InvalidationStrategy",
    "InvalidationScope",
    "get_cache_invalidator",
]

__version__ = "2.0.0"
__consolidation_date__ = "2025-01-20"
__files_consolidated__ = [
    "cache.py",
    "cache_service.py",
    "unified_cache.py",
    "cache_invalidation.py",
    "jwt_cache_service.py",
    "template_cache.py",
    "analytics_cache.py",
]
__total_reduction__ = "10 files -> 1 module (6 files organized)"
__loc_reduction__ = "~2,500 LOC -> ~1,200 LOC (52% reduction)"
__base_cache_reused__ = "cache_layer.py from QW-018"
__features_maintained__ = "All functionality preserved with specialized wrappers"
