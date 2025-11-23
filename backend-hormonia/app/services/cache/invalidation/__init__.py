from typing import Any
"""
Cache Invalidation Module
=========================

Centralized cache invalidation system with smart strategies.
Coordinates invalidation across all specialized caches.

Features:
- Smart invalidation strategies (immediate, lazy, cascade)
- Cross-cache coordination
- Entity-aware invalidation
- Bulk operations
- Invalidation tracking and analytics

Example:
    >>> from app.services.cache.invalidation import get_cache_invalidator
    >>>
    >>> invalidator = get_cache_invalidator()
    >>>
    >>> # Invalidate specific entity
    >>> await invalidator.invalidate_entity("patient", patient_id)
    >>>
    >>> # Invalidate on entity update
    >>> await invalidator.invalidate_on_update("patient", patient_id)
    >>>
    >>> # Invalidate user session (logout)
    >>> await invalidator.invalidate_user(user_id, logout=True)

Author: Backend Team
Date: 2025-01-20
Version: 1.0.0
"""

from .invalidator import (
    CacheInvalidator,
    InvalidationStrategy,
    InvalidationScope,
    get_cache_invalidator,
)

__all__ = [
    "CacheInvalidator",
    "InvalidationStrategy",
    "InvalidationScope",
    "get_cache_invalidator",
]
