"""
Query Cache Wrapper
===================

Stores entity snapshots, paginated lists, aggregations, and search results in
memory so tests and cache invalidation logic can run without Redis.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional, Tuple, List
from uuid import UUID

from app.services.ai.cache_layer import CacheLayer, CacheStrategy

_query_cache_singleton: Optional["QueryCache"] = None


def _normalize_filters(filters: Optional[Dict[str, Any]]) -> Optional[Tuple[Tuple[str, Any], ...]]:
    if not filters:
        return None
    return tuple(sorted(filters.items()))


def _normalize_relations(relations: Optional[List[str]]) -> Optional[Tuple[str, ...]]:
    if not relations:
        return None
    return tuple(sorted(relations))


def _normalize_sorting(sorting: Optional[Dict[str, Any]]) -> Optional[Tuple[Tuple[str, Any], ...]]:
    if not sorting:
        return None
    return tuple(sorted(sorting.items()))


class QueryCache:
    """Async in-memory query cache with entity/list/search helpers."""

    def __init__(self, cache_layer: Optional[CacheLayer] = None):
        self.cache_layer = cache_layer
        self._lock = asyncio.Lock()
        self._entities: Dict[Tuple[str, str, Optional[Tuple[str, ...]]], Dict[str, Any]] = {}
        self._lists: Dict[Tuple[str, Optional[Tuple[Tuple[str, Any], ...]], Optional[Tuple[Tuple[str, Any], ...]], Optional[int], Optional[int]], Dict[str, Any]] = {}
        self._aggregations: Dict[Tuple[str, str, Optional[Tuple[Tuple[str, Any], ...]], Optional[str]], Dict[str, Any]] = {}
        self._searches: Dict[Tuple[str, str, Optional[Tuple[Tuple[str, Any], ...]]], Dict[str, Any]] = {}

    # ------------------------------------------------------------------ #
    async def set_entity(
        self,
        entity_type: str,
        entity_id: UUID,
        data: Dict[str, Any],
        *,
        include_relations: Optional[List[str]] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        key = (entity_type, str(entity_id), _normalize_relations(include_relations))
        await self._set_entry(self._entities, key, {"value": data}, ttl)
        return True

    async def get_entity(
        self,
        entity_type: str,
        entity_id: UUID,
        *,
        include_relations: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        key = (entity_type, str(entity_id), _normalize_relations(include_relations))
        entry = await self._get_entry(self._entities, key)
        return entry.get("value") if entry else None

    async def invalidate_entity(self, entity_type: str, entity_id: UUID) -> int:
        entity_key = str(entity_id)
        async with self._lock:
            keys = [
                key for key in self._entities if key[0] == entity_type and key[1] == entity_key
            ]
        deleted = 0
        for key in keys:
            if await self._delete_entry(self._entities, key):
                deleted += 1
        return deleted

    # ------------------------------------------------------------------ #
    async def set_list(
        self,
        entity_type: str,
        items: List[Dict[str, Any]],
        total: int,
        *,
        filters: Optional[Dict[str, Any]] = None,
        sorting: Optional[Dict[str, Any]] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        key = (
            entity_type,
            _normalize_filters(filters),
            _normalize_sorting(sorting),
            page,
            page_size,
        )
        await self._set_entry(self._lists, key, {"items": items, "total": total}, ttl)
        return True

    async def get_list(
        self,
        entity_type: str,
        *,
        filters: Optional[Dict[str, Any]] = None,
        sorting: Optional[Dict[str, Any]] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> Optional[Tuple[List[Dict[str, Any]], int]]:
        key = (
            entity_type,
            _normalize_filters(filters),
            _normalize_sorting(sorting),
            page,
            page_size,
        )
        entry = await self._get_entry(self._lists, key)
        if not entry:
            return None
        return entry["items"], entry["total"]

    async def invalidate_lists(self, entity_type: str) -> int:
        async with self._lock:
            keys = [key for key in self._lists if key[0] == entity_type]
        deleted = 0
        for key in keys:
            if await self._delete_entry(self._lists, key):
                deleted += 1
        return deleted

    # ------------------------------------------------------------------ #
    async def set_aggregation(
        self,
        entity_type: str,
        metric: str,
        data: Dict[str, Any],
        *,
        filters: Optional[Dict[str, Any]] = None,
        group_by: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        key = (entity_type, metric, _normalize_filters(filters), group_by)
        await self._set_entry(self._aggregations, key, data, ttl)
        return True

    async def get_aggregation(
        self,
        entity_type: str,
        metric: str,
        *,
        filters: Optional[Dict[str, Any]] = None,
        group_by: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        key = (entity_type, metric, _normalize_filters(filters), group_by)
        return await self._get_entry(self._aggregations, key)

    async def invalidate_aggregations(self, entity_type: str) -> int:
        async with self._lock:
            keys = [key for key in self._aggregations if key[0] == entity_type]
        deleted = 0
        for key in keys:
            if await self._delete_entry(self._aggregations, key):
                deleted += 1
        return deleted

    # ------------------------------------------------------------------ #
    async def set_search(
        self,
        entity_type: str,
        term: str,
        items: List[Dict[str, Any]],
        total: int,
        *,
        filters: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        key = (entity_type, term.lower(), _normalize_filters(filters))
        await self._set_entry(self._searches, key, {"items": items, "total": total}, ttl)
        return True

    async def get_search(
        self,
        entity_type: str,
        term: str,
        *,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Optional[Tuple[List[Dict[str, Any]], int]]:
        key = (entity_type, term.lower(), _normalize_filters(filters))
        entry = await self._get_entry(self._searches, key)
        if not entry:
            return None
        return entry["items"], entry["total"]

    async def invalidate_searches(self, entity_type: str) -> int:
        async with self._lock:
            keys = [key for key in self._searches if key[0] == entity_type]
        deleted = 0
        for key in keys:
            if await self._delete_entry(self._searches, key):
                deleted += 1
        return deleted

    # ------------------------------------------------------------------ #
    async def invalidate_entity_related(
        self, entity_type: str, entity_id: Optional[UUID] = None
    ) -> Dict[str, int]:
        """Invalidate all cached data related to an entity or entity type."""
        stats = {"entities": 0, "lists": 0, "aggregations": 0, "searches": 0}

        if entity_id is not None:
            stats["entities"] = await self.invalidate_entity(entity_type, entity_id)

        stats["lists"] = await self.invalidate_lists(entity_type)
        stats["aggregations"] = await self.invalidate_aggregations(entity_type)
        stats["searches"] = await self.invalidate_searches(entity_type)
        stats["total"] = sum(stats.values())
        return stats

    # ------------------------------------------------------------------ #
    async def clear_all(self) -> int:
        """Remove everything from the cache."""
        async with self._lock:
            total = (
                len(self._entities)
                + len(self._lists)
                + len(self._aggregations)
                + len(self._searches)
            )
            self._entities.clear()
            self._lists.clear()
            self._aggregations.clear()
            self._searches.clear()
        return total

    # ------------------------------------------------------------------ #
    async def _set_entry(
        self, store: Dict[Any, Dict[str, Any]], key: Any, value: Dict[str, Any], ttl: Optional[int]
    ) -> None:
        expires_at = time.monotonic() + ttl if ttl else None
        async with self._lock:
            store[key] = {"expires_at": expires_at, **value}

    async def _get_entry(self, store: Dict[Any, Dict[str, Any]], key: Any) -> Optional[Dict[str, Any]]:
        async with self._lock:
            entry = store.get(key)
            if not entry:
                return None
            expires_at = entry.get("expires_at")
            if expires_at and expires_at <= time.monotonic():
                store.pop(key, None)
                return None
            return entry

    async def _delete_entry(self, store: Dict[Any, Dict[str, Any]], key: Any) -> bool:
        async with self._lock:
            return store.pop(key, None) is not None


def get_query_cache() -> QueryCache:
    """Return singleton query cache instance."""
    global _query_cache_singleton
    if _query_cache_singleton is None:
        _query_cache_singleton = QueryCache()
    return _query_cache_singleton


__all__ = ["QueryCache", "get_query_cache"]
