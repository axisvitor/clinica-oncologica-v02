"""
Cache service module - provides CacheService class for dependency injection.
Wraps UnifiedCacheService for backward compatibility.
"""

from app.services.unified_cache import UnifiedCacheService

# Alias for backward compatibility
CacheService = UnifiedCacheService

__all__ = ["CacheService"]
