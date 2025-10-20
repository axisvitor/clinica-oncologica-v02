"""
AI Cache Layer - Unified Caching System
========================================

Consolidates:
- ai_cache.py (base cache with TTL configs)
- ai_cache_service.py (tag-based invalidation)
- ai_redis_cache.py (metrics and warming)

Features:
- Intelligent caching with configurable TTL per operation
- Redis with memory fallback
- Pattern-based and tag-based invalidation
- Cache warming
- Performance metrics
- Cost tracking

Author: AI Architect
Date: 20 Jan 2025
Version: 2.0.0 (Consolidated)
"""

import hashlib
import json
import logging
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field, asdict

from redis.exceptions import RedisError

from app.config import get_settings
from app.core.redis_unified import get_async_redis

logger = logging.getLogger(__name__)
settings = get_settings()


class CacheOperation(Enum):
    """Types of AI operations for caching."""

    TEMPLATE_HUMANIZATION = "template_humanization"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    QUIZ_INTERPRETATION = "quiz_interpretation"
    RESPONSE_GENERATION = "response_generation"
    CONCERN_DETECTION = "concern_detection"
    INTENT_CLASSIFICATION = "intent_classification"


class CacheStrategy(Enum):
    """Cache storage strategies."""

    REDIS = "redis"  # Redis only
    MEMORY = "memory"  # Memory only
    HYBRID = "hybrid"  # Redis with memory fallback (default)
    DISABLED = "disabled"  # No caching


@dataclass
class CacheMetrics:
    """Cache performance metrics."""

    hits: int = 0
    misses: int = 0
    errors: int = 0
    invalidations: int = 0
    warming_operations: int = 0
    cost_saved_usd: float = 0.0
    last_reset: datetime = field(default_factory=datetime.utcnow)

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate percentage."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0

    @property
    def total_requests(self) -> int:
        """Total cache requests."""
        return self.hits + self.misses

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "errors": self.errors,
            "invalidations": self.invalidations,
            "warming_operations": self.warming_operations,
            "cost_saved_usd": round(self.cost_saved_usd, 2),
            "hit_rate": round(self.hit_rate, 2),
            "total_requests": self.total_requests,
            "last_reset": self.last_reset.isoformat(),
        }

    def reset(self):
        """Reset metrics."""
        self.hits = 0
        self.misses = 0
        self.errors = 0
        self.invalidations = 0
        self.warming_operations = 0
        self.cost_saved_usd = 0.0
        self.last_reset = datetime.utcnow()


@dataclass
class CacheEntry:
    """Cache entry with metadata."""

    key: str
    value: Any
    operation: CacheOperation
    created_at: datetime
    expires_at: datetime
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    tags: Set[str] = field(default_factory=set)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "key": self.key,
            "value": self.value,
            "operation": self.operation.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat()
            if self.last_accessed
            else None,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        """Create from dictionary."""
        return cls(
            key=data["key"],
            value=data["value"],
            operation=CacheOperation(data["operation"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            access_count=data.get("access_count", 0),
            last_accessed=datetime.fromisoformat(data["last_accessed"])
            if data.get("last_accessed")
            else None,
            tags=set(data.get("tags", [])),
        )


class CacheLayer:
    """
    Unified cache layer for AI operations.

    Consolidates multiple cache implementations into a single,
    robust caching system with intelligent strategies.

    Features:
    - Configurable TTL per operation type
    - Redis with memory fallback
    - Pattern-based invalidation
    - Tag-based invalidation
    - Cache warming
    - Performance metrics
    - Cost tracking

    Example:
        >>> cache = CacheLayer()
        >>> await cache.initialize()
        >>> await cache.set("key", {"result": "data"}, CacheOperation.SENTIMENT_ANALYSIS)
        >>> result = await cache.get("key", CacheOperation.SENTIMENT_ANALYSIS)
    """

    # TTL configurations in seconds
    TTL_CONFIG = {
        CacheOperation.TEMPLATE_HUMANIZATION: 86400,  # 24 hours
        CacheOperation.SENTIMENT_ANALYSIS: 3600,  # 1 hour
        CacheOperation.QUIZ_INTERPRETATION: 7200,  # 2 hours
        CacheOperation.RESPONSE_GENERATION: 1800,  # 30 minutes
        CacheOperation.CONCERN_DETECTION: 3600,  # 1 hour
        CacheOperation.INTENT_CLASSIFICATION: 7200,  # 2 hours
    }

    # Cost estimates per operation (USD)
    COST_PER_OPERATION = {
        CacheOperation.TEMPLATE_HUMANIZATION: 0.002,
        CacheOperation.SENTIMENT_ANALYSIS: 0.001,
        CacheOperation.QUIZ_INTERPRETATION: 0.003,
        CacheOperation.RESPONSE_GENERATION: 0.002,
        CacheOperation.CONCERN_DETECTION: 0.001,
        CacheOperation.INTENT_CLASSIFICATION: 0.001,
    }

    # Cache key prefix
    KEY_PREFIX = "ai:cache:v2"

    def __init__(self, strategy: CacheStrategy = CacheStrategy.HYBRID):
        """
        Initialize cache layer.

        Args:
            strategy: Cache storage strategy (default: HYBRID)
        """
        self.strategy = strategy
        self.redis = None
        self.memory_cache: Dict[str, CacheEntry] = {}
        self.metrics = CacheMetrics()
        self._initialized = False

        logger.info(f"CacheLayer initialized with strategy: {strategy.value}")

    async def initialize(self):
        """Initialize cache connections."""
        if self._initialized:
            return

        if self.strategy in (CacheStrategy.REDIS, CacheStrategy.HYBRID):
            try:
                self.redis = await get_async_redis()
                await self.redis.ping()
                logger.info(f"CacheLayer: Redis connection established")
            except Exception as e:
                logger.warning(f"CacheLayer: Redis connection failed: {e}")
                if self.strategy == CacheStrategy.REDIS:
                    # Fallback to memory if Redis-only failed
                    self.strategy = CacheStrategy.MEMORY
                    logger.info("CacheLayer: Falling back to memory strategy")

        self._initialized = True
        logger.info("CacheLayer initialized successfully")

    async def get(self, key: str, operation: CacheOperation) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key (will be prefixed internally)
            operation: Operation type

        Returns:
            Cached value or None if not found/expired
        """
        if self.strategy == CacheStrategy.DISABLED:
            return None

        full_key = self._build_key(key, operation)

        try:
            # Try Redis first
            if self.redis and self.strategy in (
                CacheStrategy.REDIS,
                CacheStrategy.HYBRID,
            ):
                value = await self._get_from_redis(full_key)
                if value is not None:
                    self.metrics.hits += 1
                    self._track_cost_saved(operation)
                    logger.debug(f"Cache HIT (Redis): {operation.value}:{key[:20]}...")
                    return value

            # Try memory cache
            if self.strategy in (CacheStrategy.MEMORY, CacheStrategy.HYBRID):
                entry = self.memory_cache.get(full_key)
                if entry and entry.expires_at > datetime.utcnow():
                    # Update access metadata
                    entry.access_count += 1
                    entry.last_accessed = datetime.utcnow()

                    self.metrics.hits += 1
                    self._track_cost_saved(operation)
                    logger.debug(f"Cache HIT (Memory): {operation.value}:{key[:20]}...")
                    return entry.value
                elif entry:
                    # Expired entry
                    del self.memory_cache[full_key]

            # Cache miss
            self.metrics.misses += 1
            logger.debug(f"Cache MISS: {operation.value}:{key[:20]}...")
            return None

        except Exception as e:
            logger.error(f"Cache get error: {e}")
            self.metrics.errors += 1
            return None

    async def set(
        self,
        key: str,
        value: Any,
        operation: CacheOperation,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ):
        """
        Set value in cache.

        Args:
            key: Cache key (will be prefixed internally)
            value: Value to cache
            operation: Operation type
            ttl: Custom TTL in seconds (optional, uses default if not provided)
            tags: Tags for tag-based invalidation (optional)
        """
        if self.strategy == CacheStrategy.DISABLED:
            return

        full_key = self._build_key(key, operation)
        ttl = ttl or self.TTL_CONFIG.get(operation, 3600)

        try:
            # Store in Redis
            if self.redis and self.strategy in (
                CacheStrategy.REDIS,
                CacheStrategy.HYBRID,
            ):
                await self._set_in_redis(full_key, value, ttl)

                # Store tags if provided
                if tags:
                    for tag in tags:
                        tag_key = f"{self.KEY_PREFIX}:tag:{tag}"
                        await self.redis.sadd(tag_key, full_key)
                        await self.redis.expire(tag_key, ttl)

                logger.debug(
                    f"Cache SET (Redis): {operation.value}:{key[:20]}... (TTL: {ttl}s)"
                )

            # Store in memory
            if self.strategy in (CacheStrategy.MEMORY, CacheStrategy.HYBRID):
                now = datetime.utcnow()
                entry = CacheEntry(
                    key=full_key,
                    value=value,
                    operation=operation,
                    created_at=now,
                    expires_at=now + timedelta(seconds=ttl),
                    tags=set(tags) if tags else set(),
                )
                self.memory_cache[full_key] = entry
                logger.debug(
                    f"Cache SET (Memory): {operation.value}:{key[:20]}... (TTL: {ttl}s)"
                )

        except Exception as e:
            logger.error(f"Cache set error: {e}")
            self.metrics.errors += 1

    async def invalidate(self, pattern: str):
        """
        Invalidate cache keys matching pattern.

        Args:
            pattern: Key pattern to invalidate (supports wildcards)

        Example:
            >>> await cache.invalidate("patient:123:*")
        """
        try:
            count = 0

            # Invalidate in Redis
            if self.redis and self.strategy in (
                CacheStrategy.REDIS,
                CacheStrategy.HYBRID,
            ):
                search_pattern = f"{self.KEY_PREFIX}:{pattern}"
                keys = []
                async for key in self.redis.scan_iter(match=search_pattern):
                    keys.append(key)

                if keys:
                    await self.redis.delete(*keys)
                    count += len(keys)

            # Invalidate in memory
            if self.strategy in (CacheStrategy.MEMORY, CacheStrategy.HYBRID):
                keys_to_delete = [
                    k
                    for k in self.memory_cache.keys()
                    if self._matches_pattern(k, pattern)
                ]
                for k in keys_to_delete:
                    del self.memory_cache[k]
                    count += 1

            self.metrics.invalidations += count
            logger.info(f"Invalidated {count} cache keys matching pattern: {pattern}")

        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")
            self.metrics.errors += 1

    async def invalidate_by_tag(self, tag: str):
        """
        Invalidate all cache entries with given tag.

        Args:
            tag: Tag to invalidate

        Example:
            >>> await cache.invalidate_by_tag("patient:123")
        """
        try:
            count = 0

            # Invalidate in Redis
            if self.redis and self.strategy in (
                CacheStrategy.REDIS,
                CacheStrategy.HYBRID,
            ):
                tag_key = f"{self.KEY_PREFIX}:tag:{tag}"
                keys = await self.redis.smembers(tag_key)

                if keys:
                    await self.redis.delete(*keys)
                    await self.redis.delete(tag_key)
                    count += len(keys)

            # Invalidate in memory
            if self.strategy in (CacheStrategy.MEMORY, CacheStrategy.HYBRID):
                keys_to_delete = [
                    k for k, entry in self.memory_cache.items() if tag in entry.tags
                ]
                for k in keys_to_delete:
                    del self.memory_cache[k]
                    count += 1

            self.metrics.invalidations += count
            logger.info(f"Invalidated {count} cache keys with tag: {tag}")

        except Exception as e:
            logger.error(f"Tag invalidation error: {e}")
            self.metrics.errors += 1

    async def warm_cache(
        self,
        keys_and_operations: List[tuple[str, CacheOperation]],
        value_generator: callable,
    ):
        """
        Warm cache with pre-computed values.

        Args:
            keys_and_operations: List of (key, operation) tuples to warm
            value_generator: Async function to generate values (key, operation) -> value

        Example:
            >>> async def gen(key, op):
            ...     return await compute_value(key)
            >>> await cache.warm_cache([("key1", CacheOperation.SENTIMENT), ...], gen)
        """
        try:
            for key, operation in keys_and_operations:
                value = await value_generator(key, operation)
                await self.set(key, value, operation)

            self.metrics.warming_operations += len(keys_and_operations)
            logger.info(f"Warmed {len(keys_and_operations)} cache keys")

        except Exception as e:
            logger.error(f"Cache warming error: {e}")
            self.metrics.errors += 1

    async def clear_all(self):
        """Clear all cache entries (use with caution!)."""
        try:
            # Clear Redis
            if self.redis and self.strategy in (
                CacheStrategy.REDIS,
                CacheStrategy.HYBRID,
            ):
                keys = []
                async for key in self.redis.scan_iter(match=f"{self.KEY_PREFIX}:*"):
                    keys.append(key)

                if keys:
                    await self.redis.delete(*keys)
                    logger.info(f"Cleared {len(keys)} keys from Redis")

            # Clear memory
            if self.strategy in (CacheStrategy.MEMORY, CacheStrategy.HYBRID):
                count = len(self.memory_cache)
                self.memory_cache.clear()
                logger.info(f"Cleared {count} keys from memory")

        except Exception as e:
            logger.error(f"Cache clear error: {e}")

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = self.metrics.to_dict()
        stats["strategy"] = self.strategy.value
        stats["memory_entries"] = len(self.memory_cache)

        # Add Redis stats if available
        if self.redis and self.strategy in (CacheStrategy.REDIS, CacheStrategy.HYBRID):
            try:
                info = await self.redis.info("stats")
                stats["redis_hits"] = info.get("keyspace_hits", 0)
                stats["redis_misses"] = info.get("keyspace_misses", 0)
            except:
                pass

        return stats

    def reset_metrics(self):
        """Reset performance metrics."""
        self.metrics.reset()
        logger.info("Cache metrics reset")

    # Private methods

    def _build_key(self, key: str, operation: CacheOperation) -> str:
        """Build full cache key with prefix."""
        # Hash long keys to prevent Redis key size issues
        if len(key) > 100:
            key_hash = hashlib.md5(key.encode()).hexdigest()
            key = f"{key[:50]}:{key_hash}"

        return f"{self.KEY_PREFIX}:{operation.value}:{key}"

    async def _get_from_redis(self, key: str) -> Optional[Any]:
        """Get value from Redis."""
        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for key {key}: {e}")
        except Exception as e:
            logger.error(f"Redis get error: {e}")
        return None

    async def _set_in_redis(self, key: str, value: Any, ttl: int):
        """Set value in Redis."""
        try:
            serialized = json.dumps(value, default=str)
            await self.redis.setex(key, ttl, serialized)
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            raise

    def _matches_pattern(self, key: str, pattern: str) -> bool:
        """Check if key matches pattern (simple wildcard support)."""
        import fnmatch

        return fnmatch.fnmatch(key, f"{self.KEY_PREFIX}:{pattern}")

    def _track_cost_saved(self, operation: CacheOperation):
        """Track cost saved by cache hit."""
        cost = self.COST_PER_OPERATION.get(operation, 0.001)
        self.metrics.cost_saved_usd += cost


# Singleton instance
_cache_layer: Optional[CacheLayer] = None


async def get_cache_layer() -> CacheLayer:
    """
    Get or create singleton CacheLayer instance.

    Returns:
        Initialized CacheLayer instance
    """
    global _cache_layer

    if _cache_layer is None:
        _cache_layer = CacheLayer()
        await _cache_layer.initialize()

    return _cache_layer


async def reset_cache_layer():
    """Reset singleton instance (for testing)."""
    global _cache_layer
    _cache_layer = None
