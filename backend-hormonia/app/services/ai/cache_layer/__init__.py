"""
Unified cache layer for AI services.

Package version of cache_layer so that `app.services.ai.cache_layer`
is importable both as a module (legacy `.py`) or as a package.

Security Fix: Added bounded cache with LRU eviction to prevent memory exhaustion.
"""

from __future__ import annotations

# Standard library imports
import asyncio
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Iterable, Optional, Set

# Local application imports
from app.infrastructure.cache import (
    CacheConfig,
    UnifiedCacheManager,
    get_unified_cache_manager,
)

# Maximum entries in local cache to prevent memory exhaustion
MAX_LOCAL_CACHE_SIZE = 10000

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
        return datetime.now(timezone.utc) >= self.created_at + timedelta(seconds=self.ttl)


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
        self.last_reset = datetime.now(timezone.utc)

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

    Security Fix: Uses bounded LRU cache to prevent memory exhaustion.
    Maximum entries: MAX_LOCAL_CACHE_SIZE (default: 10000)
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
        max_local_entries: int = MAX_LOCAL_CACHE_SIZE,
    ):
        self.strategy = strategy
        self.default_ttl = default_ttl
        self.redis_client = redis_client
        self.max_local_entries = max_local_entries

        self.metrics = CacheMetrics()
        # FIX: Use OrderedDict for LRU eviction support
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()
        self._tag_index: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()
        self._initialized = False
        self._cache_manager: Optional[UnifiedCacheManager] = None
        self._operation_cache_types: Dict[CacheOperation, str] = {}
        self._local_cache_enabled = self.strategy != CacheStrategy.REDIS
        self._eviction_count = 0

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
            "max_local_entries": self.max_local_entries,
            "eviction_count": self._eviction_count,
            "cache_utilization": len(self._entries) / self.max_local_entries if self.max_local_entries > 0 else 0,
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
        elif entry:
            # FIX: Move accessed entry to end for LRU tracking
            async with self._lock:
                self._entries.move_to_end(cache_key)
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
            # FIX: LRU eviction - remove oldest entries if at capacity
            while len(self._entries) >= self.max_local_entries:
                oldest_key, oldest_entry = self._entries.popitem(last=False)
                # Clean up tag index for evicted entry
                for tag in oldest_entry.tags:
                    tag_set = self._tag_index.get(tag)
                    if tag_set:
                        tag_set.discard(oldest_key)
                        if not tag_set:
                            self._tag_index.pop(tag, None)
                self._eviction_count += 1
                logger.debug(f"LRU evicted cache entry: {oldest_key}")

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


async def reset_cache_layer_async() -> None:
    """
    Reset cache layer instance with proper async cleanup.

    FIX: Properly awaits the close operation instead of creating orphaned tasks.
    """
    global _cache_layer_instance

    async with _cache_layer_lock:
        instance = _cache_layer_instance
        _cache_layer_instance = None

        if instance:
            try:
                await instance.close()
                logger.debug("Cache layer reset and closed successfully")
            except Exception as e:
                logger.warning(f"Error closing cache layer during reset: {e}")


def reset_cache_layer() -> None:
    """
    Reset cache layer instance (sync wrapper for backward compatibility).

    FIX: Uses proper async cleanup when running loop is available.
    """
    global _cache_layer_instance
    instance = _cache_layer_instance
    _cache_layer_instance = None

    if not instance:
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop - safe to use asyncio.run
        asyncio.run(instance.close())
    else:
        # FIX: Schedule cleanup as a proper awaited coroutine
        # Use asyncio.ensure_future with a wrapper that handles errors
        async def _safe_close():
            try:
                await instance.close()
            except Exception as e:
                logger.warning(f"Error during cache layer cleanup: {e}")

        asyncio.ensure_future(_safe_close())


__all__ = [
    "CacheLayer",
    "CacheOperation",
    "CacheStrategy",
    "CacheMetrics",
    "CacheEntry",
    "get_cache_layer",
    "reset_cache_layer",
    "reset_cache_layer_async",
    "MAX_LOCAL_CACHE_SIZE",
]
