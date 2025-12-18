"""
Template Cache Wrapper
======================

Lightweight in-memory cache for template content (email, WhatsApp, etc.).
Primarily used by tests and the cache invalidator to verify namespace-based
invalidations without requiring Redis.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

from app.services.ai.cache_layer import CacheLayer, CacheStrategy

_template_cache_singleton: Optional["TemplateCache"] = None


class TemplateCache:
    """Simple async template cache with namespace invalidation."""

    def __init__(self, cache_layer: Optional[CacheLayer] = None):
        self.cache_layer = cache_layer
        self._lock = asyncio.Lock()
        # category -> name -> entry
        self._store: Dict[str, Dict[str, Dict[str, Any]]] = {}

    async def cache_template(
        self,
        category: str,
        name: str,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        """Cache template content under a category/name combo."""
        expires_at = time.monotonic() + ttl if ttl else None
        async with self._lock:
            category_bucket = self._store.setdefault(category, {})
            category_bucket[name] = {
                "value": content,
                "metadata": metadata or {},
                "expires_at": expires_at,
            }
        return True

    async def get_template(self, category: str, name: str) -> Optional[Any]:
        """Retrieve cached template if present and not expired."""
        async with self._lock:
            entry = self._store.get(category, {}).get(name)
            if not entry:
                return None
            expires_at = entry.get("expires_at")
            if expires_at and expires_at <= time.monotonic():
                self._store[category].pop(name, None)
                if not self._store[category]:
                    self._store.pop(category, None)
                return None
            return entry["value"]

    async def invalidate_category(self, category: str) -> int:
        """Invalidate all templates for a category."""
        async with self._lock:
            bucket = self._store.pop(category, {})
            deleted = len(bucket)
        return deleted

    async def clear_all(self) -> int:
        """Remove every cached template."""
        async with self._lock:
            deleted = sum(len(bucket) for bucket in self._store.values())
            self._store.clear()
        return deleted

    async def get_stats(self) -> Dict[str, Any]:
        """Return simple stats for observability/debugging."""
        async with self._lock:
            total = sum(len(bucket) for bucket in self._store.values())
            categories = list(self._store.keys())
        strategy = (
            self.cache_layer.strategy.value
            if self.cache_layer and isinstance(self.cache_layer.strategy, CacheStrategy)
            else "memory"
        )
        return {
            "strategy": strategy,
            "total_templates": total,
            "categories": categories,
        }


def get_template_cache() -> TemplateCache:
    """Return singleton template cache instance."""
    global _template_cache_singleton
    if _template_cache_singleton is None:
        _template_cache_singleton = TemplateCache()
    return _template_cache_singleton


__all__ = ["TemplateCache", "get_template_cache"]
