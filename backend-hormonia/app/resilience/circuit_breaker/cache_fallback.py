"""
Cache Fallback for Circuit Breaker

Provides cached responses when circuit breaker is open.
"""

import json
import time
import hashlib
from typing import Any, Optional, Dict, Callable
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with TTL"""

    value: Any
    timestamp: float
    ttl: float
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        return time.time() > self.timestamp + self.ttl

    @property
    def age(self) -> float:
        """Get age of cache entry in seconds"""
        return time.time() - self.timestamp


class CacheFallback:
    """
    Cache fallback mechanism for circuit breaker

    Features:
    - TTL-based cache entries
    - Automatic cleanup of expired entries
    - Hit/miss metrics
    - Configurable cache size
    """

    def __init__(
        self,
        default_ttl: float = 300.0,  # 5 minutes
        max_size: int = 1000,
        cleanup_interval: float = 60.0,
    ):
        self.default_ttl = default_ttl
        self.max_size = max_size
        self.cleanup_interval = cleanup_interval

        self._cache: Dict[str, CacheEntry] = {}
        self._last_cleanup = time.time()

        # Metrics
        self._hits = 0
        self._misses = 0
        self._evictions = 0

        logger.info(
            f"Cache fallback initialized (ttl={default_ttl}s, max_size={max_size})"
        )

    def get_cache_key(self, func: Callable, *args, **kwargs) -> str:
        """Generate cache key from function and arguments"""
        # Create a stable hash from function name and arguments
        func_name = getattr(func, "__name__", str(func))

        # Serialize arguments for hashing
        try:
            args_str = json.dumps(args, sort_keys=True, default=str)
            kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)
        except (TypeError, ValueError):
            # Fallback for non-serializable objects
            args_str = str(args)
            kwargs_str = str(kwargs)

        content = f"{func_name}:{args_str}:{kwargs_str}"
        return hashlib.md5(content.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
        self._cleanup_if_needed()

        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            logger.debug(f"Cache miss for key: {key[:8]}...")
            return None

        if entry.is_expired:
            del self._cache[key]
            self._misses += 1
            logger.debug(f"Cache expired for key: {key[:8]}... (age={entry.age:.1f}s)")
            return None

        entry.hit_count += 1
        self._hits += 1
        logger.debug(f"Cache hit for key: {key[:8]}... (age={entry.age:.1f}s)")
        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set cached value"""
        if ttl is None:
            ttl = self.default_ttl

        # Evict oldest entries if cache is full
        if len(self._cache) >= self.max_size:
            self._evict_oldest()

        self._cache[key] = CacheEntry(value=value, timestamp=time.time(), ttl=ttl)

        logger.debug(f"Cached value for key: {key[:8]}... (ttl={ttl}s)")

    def cache_result(self, func: Callable, result: Any, *args, **kwargs) -> None:
        """Cache function result"""
        key = self.get_cache_key(func, *args, **kwargs)
        self.set(key, result)

    def get_cached_result(self, func: Callable, *args, **kwargs) -> Optional[Any]:
        """Get cached function result"""
        key = self.get_cache_key(func, *args, **kwargs)
        return self.get(key)

    def _cleanup_if_needed(self):
        """Cleanup expired entries if needed"""
        current_time = time.time()
        if current_time - self._last_cleanup < self.cleanup_interval:
            return

        expired_keys = []
        for key, entry in self._cache.items():
            if entry.is_expired:
                expired_keys.append(key)

        for key in expired_keys:
            del self._cache[key]

        self._last_cleanup = current_time

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    def _evict_oldest(self):
        """Evict oldest cache entry"""
        if not self._cache:
            return

        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].timestamp)
        del self._cache[oldest_key]
        self._evictions += 1

        logger.debug(f"Evicted oldest cache entry: {oldest_key[:8]}...")

    def clear(self):
        """Clear all cache entries"""
        self._cache.clear()
        logger.info("Cache cleared")

    def get_metrics(self) -> Dict:
        """Get cache metrics"""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

        return {
            "total_entries": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "evictions": self._evictions,
            "default_ttl": self.default_ttl,
        }

    def get_cache_info(self) -> Dict:
        """Get detailed cache information"""
        time.time()
        entries_info = []

        for key, entry in self._cache.items():
            entries_info.append(
                {
                    "key": key[:16] + "..." if len(key) > 16 else key,
                    "age": entry.age,
                    "ttl": entry.ttl,
                    "hit_count": entry.hit_count,
                    "is_expired": entry.is_expired,
                }
            )

        # Sort by age (newest first)
        entries_info.sort(key=lambda x: x["age"])

        return {
            "metrics": self.get_metrics(),
            "entries": entries_info[:10],  # Show only first 10 entries
        }


class CachedCircuitBreakerMixin:
    """
    Mixin to add cache fallback to circuit breaker
    """

    def __init__(self, *args, cache_fallback: Optional[CacheFallback] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache_fallback = cache_fallback or CacheFallback()

    def call_with_cache(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with cache fallback"""
        try:
            # Try normal execution with circuit breaker
            result = self.call(func, *args, **kwargs)

            # Cache successful result
            self.cache_fallback.cache_result(func, result, *args, **kwargs)
            return result

        except Exception as e:
            # Check for cached result as fallback
            cached_result = self.cache_fallback.get_cached_result(func, *args, **kwargs)

            if cached_result is not None:
                logger.info(
                    f"Using cached fallback for {func.__name__} "
                    f"due to {type(e).__name__}: {str(e)}"
                )
                return cached_result

            # No cache available, re-raise exception
            raise

    async def acall_with_cache(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with cache fallback"""
        try:
            # Try normal execution with circuit breaker
            result = await self.acall(func, *args, **kwargs)

            # Cache successful result
            self.cache_fallback.cache_result(func, result, *args, **kwargs)
            return result

        except Exception as e:
            # Check for cached result as fallback
            cached_result = self.cache_fallback.get_cached_result(func, *args, **kwargs)

            if cached_result is not None:
                logger.info(
                    f"Using cached fallback for {func.__name__} "
                    f"due to {type(e).__name__}: {str(e)}"
                )
                return cached_result

            # No cache available, re-raise exception
            raise
