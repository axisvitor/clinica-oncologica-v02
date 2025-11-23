from typing import Any
"""
Specialized Cache Wrappers
==========================

Specialized cache implementations that wrap the base CacheLayer
from QW-018 with domain-specific functionality.

Each specialized cache provides:
- Domain-specific methods and TTLs
- Automatic tagging and categorization
- Optimized key patterns
- Singleton access patterns

Available Caches:
    JWTCache: JWT token and session caching
    TemplateCache: Template and content caching
    AnalyticsCache: Analytics data caching with compression
    QueryCache: Database query result caching

Example:
    >>> from app.services.cache.specialized import JWTCache, TemplateCache
    >>>
    >>> # Use JWT cache
    >>> jwt_cache = await get_jwt_cache()
    >>> await jwt_cache.cache_token("user:123", token_data)
    >>>
    >>> # Use template cache
    >>> template_cache = await get_template_cache()
    >>> await template_cache.cache_template("welcome", template_data)

Author: AI Architect
Date: 20 Jan 2025
Version: 2.0.0
"""

from .jwt_cache import JWTCache, get_jwt_cache
from .template_cache import TemplateCache, get_template_cache
from .analytics_cache import AnalyticsCache, get_analytics_cache
from .query_cache import QueryCache, get_query_cache

__all__ = [
    "JWTCache",
    "get_jwt_cache",
    "TemplateCache",
    "get_template_cache",
    "AnalyticsCache",
    "get_analytics_cache",
    "QueryCache",
    "get_query_cache",
]
