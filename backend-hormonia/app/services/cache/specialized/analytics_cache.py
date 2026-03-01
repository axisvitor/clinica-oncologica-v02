"""
Specialized cache wrapper for analytics data.

This lightweight implementation is purposely in-memory to keep the baseline
tests fast. When a ``CacheLayer`` instance is provided we retain a reference
so the caller can inspect its strategy/metrics, but the wrapper maintains its
own namespace maps for metrics, counters, reports, dashboards and aggregations.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional, Tuple

_analytics_cache_singleton: Optional["AnalyticsCache"] = None


def _normalize_filters(
    filters: Optional[Dict[str, Any]],
) -> Optional[Tuple[Tuple[str, Any], ...]]:
    if not filters:
        return None
    return tuple(sorted(filters.items()))


class AnalyticsCache:
    """In-memory analytics cache with optional TTL support."""

    def __init__(self, cache_layer: Optional[Any] = None):
        self.cache_layer = cache_layer
        self._lock = asyncio.Lock()
        self._metrics: Dict[Tuple[str, Optional[str]], Dict[str, Any]] = {}
        self._counters: Dict[Tuple[str, Optional[str]], int] = {}
        self._reports: Dict[
            Tuple[str, Optional[Tuple[Tuple[str, Any], ...]]], Dict[str, Any]
        ] = {}
        self._dashboards: Dict[Tuple[str, Optional[str]], Dict[str, Any]] = {}
        self._aggregations: Dict[
            Tuple[str, str, Optional[Tuple[Tuple[str, Any], ...]], Optional[str]],
            Dict[str, Any],
        ] = {}

    # ------------------------------------------------------------------ #
    async def set_metric(
        self,
        name: str,
        data: Dict[str, Any],
        scope: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        await self._set_entry(self._metrics, (name, scope), data, ttl)
        return True

    async def get_metric(
        self, name: str, scope: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        return await self._get_entry(self._metrics, (name, scope))

    async def increment_counter(
        self, name: str, scope: Optional[str] = None, increment: int = 1
    ) -> int:
        key = (name, scope)
        async with self._lock:
            value = self._counters.get(key, 0) + increment
            self._counters[key] = value
            return value

    async def get_counter(self, name: str, scope: Optional[str] = None) -> int:
        async with self._lock:
            return self._counters.get((name, scope), 0)

    # ------------------------------------------------------------------ #
    async def set_report(
        self,
        name: str,
        data: Dict[str, Any],
        filters: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        key = (name, _normalize_filters(filters))
        await self._set_entry(self._reports, key, data, ttl)
        return True

    async def get_report(
        self, name: str, filters: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        key = (name, _normalize_filters(filters))
        return await self._get_entry(self._reports, key)

    async def invalidate_report(
        self, name: str, filters: Optional[Dict[str, Any]] = None
    ) -> bool:
        key = (name, _normalize_filters(filters))
        return await self._delete_entry(self._reports, key)

    # ------------------------------------------------------------------ #
    async def set_dashboard(
        self,
        name: str,
        data: Dict[str, Any],
        user_id: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        await self._set_entry(self._dashboards, (name, user_id), data, ttl)
        return True

    async def get_dashboard(
        self, name: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        return await self._get_entry(self._dashboards, (name, user_id))

    async def invalidate_dashboard(
        self, name: str, user_id: Optional[str] = None
    ) -> bool:
        return await self._delete_entry(self._dashboards, (name, user_id))

    async def invalidate_all_dashboards(self) -> int:
        return await self._clear_namespace(self._dashboards)

    # ------------------------------------------------------------------ #
    async def set_aggregation(
        self,
        namespace: str,
        metric: str,
        data: Dict[str, Any],
        filters: Optional[Dict[str, Any]] = None,
        period: Optional[str] = None,
        group_by: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        key = (namespace, metric, _normalize_filters(filters), period, group_by)
        await self._set_entry(self._aggregations, key, data, ttl)
        return True

    async def get_aggregation(
        self,
        namespace: str,
        metric: str,
        filters: Optional[Dict[str, Any]] = None,
        period: Optional[str] = None,
        group_by: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        key = (namespace, metric, _normalize_filters(filters), period, group_by)
        return await self._get_entry(self._aggregations, key)

    async def invalidate_aggregations(self, namespace: str) -> int:
        async with self._lock:
            keys = [key for key in self._aggregations if key[0] == namespace]
        deleted = 0
        for key in keys:
            if await self._delete_entry(self._aggregations, key):
                deleted += 1
        return deleted

    # ------------------------------------------------------------------ #
    async def invalidate_all_metrics(self) -> int:
        return await self._clear_namespace(self._metrics)

    async def invalidate_all_reports(self) -> int:
        return await self._clear_namespace(self._reports)

    async def clear_all(self) -> int:
        total = 0
        total += await self._clear_namespace(self._metrics)
        total += await self._clear_namespace(self._reports)
        total += await self._clear_namespace(self._dashboards)
        total += await self._clear_namespace(self._aggregations)
        async with self._lock:
            count = len(self._counters)
            self._counters.clear()
            total += count
        return total

    async def get_cache_stats(self) -> Dict[str, Any]:
        strategy_obj = getattr(self.cache_layer, "strategy", None)
        strategy = getattr(strategy_obj, "value", strategy_obj) or "memory"
        async with self._lock:
            namespaces = {
                "metrics": len(self._metrics),
                "reports": len(self._reports),
                "dashboards": len(self._dashboards),
                "counters": len(self._counters),
                "aggregations": len(self._aggregations),
            }
        return {"strategy": strategy, "namespaces": namespaces}

    # ------------------------------------------------------------------ #
    async def _set_entry(
        self, store: Dict[Any, Dict[str, Any]], key: Any, value: Any, ttl: Optional[int]
    ) -> None:
        expires_at = time.monotonic() + ttl if ttl else None
        async with self._lock:
            store[key] = {"value": value, "expires_at": expires_at}

    async def _get_entry(
        self, store: Dict[Any, Dict[str, Any]], key: Any
    ) -> Optional[Any]:
        async with self._lock:
            entry = store.get(key)
            if not entry:
                return None
            expires_at = entry.get("expires_at")
            if expires_at and expires_at <= time.monotonic():
                store.pop(key, None)
                return None
            return entry["value"]

    async def _delete_entry(self, store: Dict[Any, Dict[str, Any]], key: Any) -> bool:
        async with self._lock:
            return store.pop(key, None) is not None

    async def _clear_namespace(self, store: Dict[Any, Dict[str, Any]]) -> int:
        async with self._lock:
            count = len(store)
            store.clear()
            return count


def get_analytics_cache() -> AnalyticsCache:
    """Return singleton analytics cache instance."""
    global _analytics_cache_singleton
    if _analytics_cache_singleton is None:
        _analytics_cache_singleton = AnalyticsCache()
    return _analytics_cache_singleton


__all__ = ["AnalyticsCache", "get_analytics_cache"]
