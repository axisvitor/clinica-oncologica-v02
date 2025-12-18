"""
Unified cache layer for AI services.

Package version of cache_layer so that `app.services.ai.cache_layer`
is importable both as a module (legacy `.py`) or as a package.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Iterable, Optional, Set

from app.infrastructure.cache import (
    CacheConfig,
    UnifiedCacheManager,
    get_unified_cache_manager,
)

logger = logging.getLogger(__name__)


class CacheStrategy(str, Enum):
    """Storage strategy for the cache layer."""

    MEMORY = "memory"
    REDIS = "redis"
    HYBRID = "hybrid"


class CacheOperation(str, Enum):
    """Supported AI cache operations."""

    TEMPLATE_HUMANIZATION = "template_humanization"
    RESPONSE_GENERATION = "response_generation"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    CONCERN_DETECTION = "concern_detection"
    INTENT_CLASSIFICATION = "intent_classification"
    QUIZ_INTERPRETATION = "quiz_interpretation"


@dataclass
class CacheEntry:
    """Metadata for cached entries."""

    cache_key: str
    raw_key: str
    operation: CacheOperation
    ttl: int
    value: Any = None
    tags: Set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def is_expired(self) -> bool:
        if self.ttl <= 0:
            return False
        return datetime.utcnow() >= self.created_at + timedelta(seconds=self.ttl)


@dataclass
class CacheMetrics:
    """Lightweight metrics for observability."""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    invalidations: int = 0
    last_reset: datetime = field(default_factory=datetime.utcnow)

    def record_hit(self) -> None:
        self.hits += 1

    def record_miss(self) -> None:
        self.misses += 1

    def record_set(self) -> None:
        self.sets += 1

    def record_delete(self, invalidation: bool = False) -> None:
        self.deletes += 1
        if invalidation:
            self.invalidations += 1

    def reset(self) -> None:
        self.hits = self.misses = self.sets = self.deletes = self.invalidations = 0
        self.last_reset = datetime.utcnow()

    def as_dict(self) -> Dict[str, Any]:
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100.0) if total_requests else 0.0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "total_requests": total_requests,
            "hit_rate_percent": round(hit_rate, 2),
            "sets": self.sets,
            "deletes": self.deletes,
            "invalidations": self.invalidations,
            "last_reset": self.last_reset.isoformat(),
        }


class CacheLayer:
    """
    Async cache layer with Redis + in-memory fallback.
    """

    _OPERATION_TTLS: Dict[CacheOperation, int] = {
        CacheOperation.TEMPLATE_HUMANIZATION: 3600,
        CacheOperation.RESPONSE_GENERATION: 3600,
        CacheOperation.SENTIMENT_ANALYSIS: 900,
        CacheOperation.CONCERN_DETECTION: 900,
        CacheOperation.INTENT_CLASSIFICATION: 900,
        CacheOperation.QUIZ_INTERPRETATION: 600,
    }

    def __init__(
        self,
        strategy: CacheStrategy = CacheStrategy.HYBRID,
        default_ttl: int = 900,
        redis_client: Any = None,
    ):
        self.strategy = strategy
        self.default_ttl = default_ttl
        self.redis_client = redis_client

        self.metrics = CacheMetrics()
        self._entries: Dict[str, CacheEntry] = {}
        self._tag_index: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()
        self._initialized = False
        self._cache_manager: Optional[UnifiedCacheManager] = None
        self._operation_cache_types: Dict[CacheOperation, str] = {}
        self._local_cache_enabled = self.strategy != CacheStrategy.REDIS

    @property
    def initialized(self) -> bool:
        return self._initialized

    async def initialize(self) -> None:
        if self._initialized:
            return

        if self.strategy != CacheStrategy.MEMORY:
            self._cache_manager = get_unified_cache_manager(
                redis_client=self.redis_client,
                enable_stats=True,
                enable_local_fallback=self.strategy != CacheStrategy.REDIS,
            )

        for operation in CacheOperation:
            cache_type = self._cache_type_name(operation)
            self._operation_cache_types[operation] = cache_type

            if self._cache_manager:
                ttl = self._get_ttl(operation)
                config = CacheConfig(
                    ttl=ttl,
                    key_prefix=f"ai:{operation.value}",
                    namespace="ai",
                    enable_local_fallback=self.strategy != CacheStrategy.REDIS,
                )
                self._cache_manager.register_cache_config(cache_type, config)

        self._initialized = True
        logger.info("CacheLayer initialized (strategy=%s)", self.strategy.value)

    async def close(self) -> None:
        async with self._lock:
            self._entries.clear()
            self._tag_index.clear()
            self._initialized = False
        logger.debug("CacheLayer closed")

    async def get(
        self, key: str, operation: CacheOperation, default: Any = None
    ) -> Any:
        await self._ensure_initialized()
        cache_key = self._build_cache_key(operation, key)

        entry = await self._get_local_entry(cache_key)
        if entry and entry.value is not None:
            self.metrics.record_hit()
            return entry.value

        value = None
        if self._cache_manager:
            cache_type = self._operation_cache_types[operation]
            value = await self._cache_manager.get_async(
                cache_type,
                key_parts=[key],
                default=default,
            )
            if value is not None and self._local_cache_enabled:
                await self._store_local(
                    cache_key,
                    operation,
                    key,
                    value,
                    ttl=self._get_ttl(operation),
                    tags=entry.tags if entry else None,
                )

        if value is not None:
            self.metrics.record_hit()
            return value

        self.metrics.record_miss()
        return default

    async def set(
        self,
        key: str,
        value: Any,
        operation: CacheOperation,
        ttl: Optional[int] = None,
        tags: Optional[Iterable[str]] = None,
    ) -> bool:
        await self._ensure_initialized()
        ttl_seconds = ttl if ttl is not None else self._get_ttl(operation)
        cache_key = self._build_cache_key(operation, key)

        if self._cache_manager:
            cache_type = self._operation_cache_types[operation]
            await self._cache_manager.set_async(
                cache_type,
                value,
                key_parts=[key],
                ttl_override=ttl_seconds,
            )

        await self._store_local(
            cache_key,
            operation,
            key,
            value if self._local_cache_enabled else None,
            ttl=ttl_seconds,
            tags=tags,
        )
        self.metrics.record_set()
        return True

    async def delete(self, key: str, operation: CacheOperation) -> bool:
        await self._ensure_initialized()
        cache_key = self._build_cache_key(operation, key)
        entry = await self._pop_entry(cache_key)

        if self._cache_manager:
            cache_type = self._operation_cache_types[operation]
            await self._cache_manager.delete_async(cache_type, key_parts=[key])

        if entry:
            self.metrics.record_delete()
            return True
        return False

    async def invalidate_by_tag(self, tag: str) -> int:
        await self._ensure_initialized()
        async with self._lock:
            keys = list(self._tag_index.get(tag, set()))

        deleted = 0
        for cache_key in keys:
            entry = await self._pop_entry(cache_key)
            if entry:
                if self._cache_manager:
                    cache_type = self._operation_cache_types[entry.operation]
                    await self._cache_manager.delete_async(
                        cache_type,
                        key_parts=[entry.raw_key],
                    )
                deleted += 1
                self.metrics.record_delete(invalidation=True)

        return deleted

    async def invalidate_patient_cache(self, patient_id: str) -> int:
        return await self.invalidate_by_tag(f"patient:{patient_id}")

    async def get_stats(self) -> Dict[str, Any]:
        await self._ensure_initialized()
        stats = {
            "strategy": self.strategy.value,
            "local_cache_entries": len(self._entries),
            "metrics": self.metrics.as_dict(),
        }
        if self._cache_manager:
            stats["backend"] = self._cache_manager.get_stats()
        return stats

    def reset_metrics(self) -> None:
        self.metrics.reset()
        if self._cache_manager:
            self._cache_manager.reset_stats()

    # ------------------------------------------------------------------ #
    async def _ensure_initialized(self) -> None:
        if not self._initialized:
            await self.initialize()

    async def _get_local_entry(self, cache_key: str) -> Optional[CacheEntry]:
        entry = self._entries.get(cache_key)
        if entry and entry.is_expired():
            await self._pop_entry(cache_key)
            entry = None
        return entry

    async def _store_local(
        self,
        cache_key: str,
        operation: CacheOperation,
        raw_key: str,
        value: Any,
        ttl: int,
        tags: Optional[Iterable[str]] = None,
    ) -> None:
        entry = CacheEntry(
            cache_key=cache_key,
            raw_key=raw_key,
            operation=operation,
            ttl=ttl,
            value=value,
            tags=set(tags or []),
        )
        async with self._lock:
            self._entries[cache_key] = entry
            for tag in entry.tags:
                self._tag_index.setdefault(tag, set()).add(cache_key)

    async def _pop_entry(self, cache_key: str) -> Optional[CacheEntry]:
        async with self._lock:
            entry = self._entries.pop(cache_key, None)
            if entry:
                for tag in entry.tags:
                    tag_set = self._tag_index.get(tag)
                    if tag_set:
                        tag_set.discard(cache_key)
                        if not tag_set:
                            self._tag_index.pop(tag, None)
            return entry

    def _cache_type_name(self, operation: CacheOperation) -> str:
        return f"ai_{operation.value}"

    def _get_ttl(self, operation: CacheOperation) -> int:
        return self._OPERATION_TTLS.get(operation, self.default_ttl)

    def _build_cache_key(self, operation: CacheOperation, key: str) -> str:
        return f"{operation.value}:{key}"


_cache_layer_instance: Optional[CacheLayer] = None
_cache_layer_lock = asyncio.Lock()


async def get_cache_layer() -> CacheLayer:
    global _cache_layer_instance
    if _cache_layer_instance and _cache_layer_instance.initialized:
        return _cache_layer_instance

    async with _cache_layer_lock:
        if _cache_layer_instance is None:
            _cache_layer_instance = CacheLayer()

        if not _cache_layer_instance.initialized:
            await _cache_layer_instance.initialize()

        return _cache_layer_instance


def reset_cache_layer() -> None:
    global _cache_layer_instance
    instance = _cache_layer_instance
    _cache_layer_instance = None

    if not instance:
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(instance.close())
    else:
        loop.create_task(instance.close())


__all__ = [
    "CacheLayer",
    "CacheOperation",
    "CacheStrategy",
    "CacheMetrics",
    "CacheEntry",
    "get_cache_layer",
    "reset_cache_layer",
]
