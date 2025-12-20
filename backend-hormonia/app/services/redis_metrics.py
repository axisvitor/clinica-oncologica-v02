"""
Redis Cache Metrics - Global Hit Rate Tracking

Provides centralized cache metrics collection for all Redis caches in the system.
"""

import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json

logger = logging.getLogger(__name__)


@dataclass
class CacheMetrics:
    """Cache performance metrics"""

    cache_name: str
    hits: int = 0
    misses: int = 0
    errors: int = 0
    total_requests: int = 0
    hit_rate: float = 0.0
    last_updated: str = ""

    def calculate_hit_rate(self):
        """Calculate current hit rate"""
        if self.total_requests > 0:
            self.hit_rate = round((self.hits / self.total_requests) * 100, 2)
        else:
            self.hit_rate = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class RedisMetricsCollector:
    """
    Centralized Redis cache metrics collector

    Tracks hit/miss rates for all caches in the system.
    """

    def __init__(self):
        self._metrics: Dict[str, CacheMetrics] = {}
        self._start_time = time.time()

    def record_hit(self, cache_name: str):
        """
        Record a cache hit

        Args:
            cache_name: Name of the cache (e.g., 'jwt', 'template', 'ai_response')
        """
        if cache_name not in self._metrics:
            self._metrics[cache_name] = CacheMetrics(cache_name=cache_name)

        metrics = self._metrics[cache_name]
        metrics.hits += 1
        metrics.total_requests += 1
        metrics.calculate_hit_rate()
        metrics.last_updated = datetime.now(timezone.utc).isoformat()

    def record_miss(self, cache_name: str):
        """
        Record a cache miss

        Args:
            cache_name: Name of the cache
        """
        if cache_name not in self._metrics:
            self._metrics[cache_name] = CacheMetrics(cache_name=cache_name)

        metrics = self._metrics[cache_name]
        metrics.misses += 1
        metrics.total_requests += 1
        metrics.calculate_hit_rate()
        metrics.last_updated = datetime.now(timezone.utc).isoformat()

    def record_error(self, cache_name: str):
        """
        Record a cache error

        Args:
            cache_name: Name of the cache
        """
        if cache_name not in self._metrics:
            self._metrics[cache_name] = CacheMetrics(cache_name=cache_name)

        metrics = self._metrics[cache_name]
        metrics.errors += 1
        metrics.last_updated = datetime.now(timezone.utc).isoformat()

    def get_metrics(self, cache_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get metrics for specific cache or all caches

        Args:
            cache_name: Optional cache name to filter by

        Returns:
            Metrics dictionary
        """
        if cache_name:
            metrics = self._metrics.get(cache_name)
            return metrics.to_dict() if metrics else {}

        return {name: metrics.to_dict() for name, metrics in self._metrics.items()}

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of all cache metrics

        Returns:
            Summary dictionary with aggregated stats
        """
        total_hits = sum(m.hits for m in self._metrics.values())
        total_misses = sum(m.misses for m in self._metrics.values())
        total_errors = sum(m.errors for m in self._metrics.values())
        total_requests = sum(m.total_requests for m in self._metrics.values())

        overall_hit_rate = 0.0
        if total_requests > 0:
            overall_hit_rate = round((total_hits / total_requests) * 100, 2)

        uptime_seconds = int(time.time() - self._start_time)

        return {
            "summary": {
                "total_hits": total_hits,
                "total_misses": total_misses,
                "total_errors": total_errors,
                "total_requests": total_requests,
                "overall_hit_rate": overall_hit_rate,
                "uptime_seconds": uptime_seconds,
                "cache_count": len(self._metrics),
            },
            "caches": self.get_metrics(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def reset_metrics(self, cache_name: Optional[str] = None):
        """
        Reset metrics for specific cache or all caches

        Args:
            cache_name: Optional cache name to reset
        """
        if cache_name:
            if cache_name in self._metrics:
                self._metrics[cache_name] = CacheMetrics(cache_name=cache_name)
                logger.info(f"Reset metrics for cache: {cache_name}")
        else:
            self._metrics.clear()
            self._start_time = time.time()
            logger.info("Reset all cache metrics")

    def export_prometheus(self) -> str:
        """
        Export metrics in Prometheus format

        Returns:
            Prometheus-formatted metrics string
        """
        lines = [
            "# HELP redis_cache_hits_total Total number of cache hits",
            "# TYPE redis_cache_hits_total counter",
        ]

        for name, metrics in self._metrics.items():
            lines.append(f'redis_cache_hits_total{{cache="{name}"}} {metrics.hits}')

        lines.extend(
            [
                "# HELP redis_cache_misses_total Total number of cache misses",
                "# TYPE redis_cache_misses_total counter",
            ]
        )

        for name, metrics in self._metrics.items():
            lines.append(f'redis_cache_misses_total{{cache="{name}"}} {metrics.misses}')

        lines.extend(
            [
                "# HELP redis_cache_errors_total Total number of cache errors",
                "# TYPE redis_cache_errors_total counter",
            ]
        )

        for name, metrics in self._metrics.items():
            lines.append(f'redis_cache_errors_total{{cache="{name}"}} {metrics.errors}')

        lines.extend(
            [
                "# HELP redis_cache_hit_rate_percent Current cache hit rate percentage",
                "# TYPE redis_cache_hit_rate_percent gauge",
            ]
        )

        for name, metrics in self._metrics.items():
            lines.append(
                f'redis_cache_hit_rate_percent{{cache="{name}"}} {metrics.hit_rate}'
            )

        return "\n".join(lines) + "\n"

    def log_metrics(self, level: str = "INFO"):
        """
        Log current metrics

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR)
        """
        summary = self.get_summary()

        log_method = getattr(logger, level.lower(), logger.info)
        log_method(
            f"Redis Cache Metrics Summary: {json.dumps(summary['summary'], indent=2)}"
        )

        for cache_name, metrics in summary["caches"].items():
            log_method(f"  Cache '{cache_name}': {json.dumps(metrics, indent=4)}")


# Global metrics collector instance
_metrics_collector: Optional[RedisMetricsCollector] = None


def get_metrics_collector() -> RedisMetricsCollector:
    """
    Get or create global metrics collector instance

    Returns:
        RedisMetricsCollector instance
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = RedisMetricsCollector()
    return _metrics_collector


def record_cache_hit(cache_name: str):
    """Convenience function to record cache hit"""
    get_metrics_collector().record_hit(cache_name)


def record_cache_miss(cache_name: str):
    """Convenience function to record cache miss"""
    get_metrics_collector().record_miss(cache_name)


def record_cache_error(cache_name: str):
    """Convenience function to record cache error"""
    get_metrics_collector().record_error(cache_name)


def get_cache_metrics(cache_name: Optional[str] = None) -> Dict[str, Any]:
    """Convenience function to get metrics"""
    return get_metrics_collector().get_metrics(cache_name)


def get_cache_summary() -> Dict[str, Any]:
    """Convenience function to get summary"""
    return get_metrics_collector().get_summary()


# Decorator for automatic metrics tracking
def track_cache_metrics(cache_name: str):
    """
    Decorator to automatically track cache hit/miss/error

    Usage:
        @track_cache_metrics('jwt')
        def get_from_cache(key):
            # Returns value or None
            pass
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)

                if result is not None:
                    record_cache_hit(cache_name)
                else:
                    record_cache_miss(cache_name)

                return result

            except Exception:
                record_cache_error(cache_name)
                raise

        return wrapper

    return decorator


def async_track_cache_metrics(cache_name: str):
    """
    Async decorator to automatically track cache hit/miss/error

    Usage:
        @async_track_cache_metrics('template')
        async def get_from_cache(key):
            # Returns value or None
            pass
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)

                if result is not None:
                    record_cache_hit(cache_name)
                else:
                    record_cache_miss(cache_name)

                return result

            except Exception:
                record_cache_error(cache_name)
                raise

        return wrapper

    return decorator
