"""
Application Performance Monitoring (APM) System.

Tracks response times, throughput, error rates, and Apdex scores.
"""

import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
from contextlib import asynccontextmanager
import statistics
import logging
from datetime import datetime, timedelta, timezone
import threading
import redis.asyncio as redis

logger = logging.getLogger(__name__)


@dataclass
class RequestMetrics:
    """Metrics for a single request."""

    endpoint: str
    method: str
    status_code: int
    response_time: float
    timestamp: datetime
    user_id: Optional[str] = None
    error_type: Optional[str] = None
    db_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0


@dataclass
class EndpointStats:
    """Statistics for an endpoint."""

    total_requests: int = 0
    error_count: int = 0
    response_times: deque = field(default_factory=lambda: deque(maxlen=1000))
    status_codes: Dict[int, int] = field(default_factory=lambda: defaultdict(int))
    hourly_requests: deque = field(default_factory=lambda: deque(maxlen=24))
    last_hour_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class APMCollector:
    """Application Performance Monitoring collector."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.endpoint_stats: Dict[str, EndpointStats] = defaultdict(EndpointStats)
        self.global_stats = EndpointStats()
        self.apdex_threshold = 0.5  # 500ms
        self.apdex_toleration = 2.0  # 2 seconds
        self._lock = threading.Lock()

    async def record_request(self, metrics: RequestMetrics) -> None:
        """Record metrics for a request."""
        endpoint_key = f"{metrics.method} {metrics.endpoint}"

        with self._lock:
            # Update endpoint stats
            stats = self.endpoint_stats[endpoint_key]
            stats.total_requests += 1
            stats.response_times.append(metrics.response_time)
            stats.status_codes[metrics.status_code] += 1

            if metrics.status_code >= 400:
                stats.error_count += 1

            # Update hourly counts
            current_hour = metrics.timestamp.replace(minute=0, second=0, microsecond=0)
            if current_hour != stats.last_hour_start:
                stats.hourly_requests.append(0)
                stats.last_hour_start = current_hour

            if stats.hourly_requests:
                stats.hourly_requests[-1] += 1
            else:
                stats.hourly_requests.append(1)

            # Update global stats
            self.global_stats.total_requests += 1
            self.global_stats.response_times.append(metrics.response_time)
            self.global_stats.status_codes[metrics.status_code] += 1

            if metrics.status_code >= 400:
                self.global_stats.error_count += 1

        # Store in Redis for real-time dashboard
        if self.redis_client:
            try:
                await self._store_metrics_redis(endpoint_key, metrics)
            except Exception as e:
                logger.error(f"Failed to store metrics in Redis: {e}")

    async def _store_metrics_redis(
        self, endpoint_key: str, metrics: RequestMetrics
    ) -> None:
        """Store metrics in Redis for real-time access."""
        timestamp = int(metrics.timestamp.timestamp())

        # Store individual metric
        metric_data = {
            "endpoint": endpoint_key,
            "status_code": metrics.status_code,
            "response_time": metrics.response_time,
            "timestamp": timestamp,
            "error_type": metrics.error_type or "",
            "db_queries": metrics.db_queries,
            "cache_hits": metrics.cache_hits,
            "cache_misses": metrics.cache_misses,
        }

        await self.redis_client.lpush("apm:requests", str(metric_data))

        # Keep only last 10000 requests
        await self.redis_client.ltrim("apm:requests", 0, 9999)

        # Update endpoint counters
        await self.redis_client.hincrby(
            f"apm:endpoint:{endpoint_key}", "total_requests", 1
        )
        await self.redis_client.hincrby(
            f"apm:endpoint:{endpoint_key}", f"status_{metrics.status_code}", 1
        )

        if metrics.status_code >= 400:
            await self.redis_client.hincrby(
                f"apm:endpoint:{endpoint_key}", "error_count", 1
            )

        # Set expiration for endpoint stats (24 hours)
        await self.redis_client.expire(f"apm:endpoint:{endpoint_key}", 86400)

    def get_endpoint_stats(self, endpoint: str) -> Dict[str, Any]:
        """Get statistics for a specific endpoint."""
        stats = self.endpoint_stats.get(endpoint, EndpointStats())

        if not stats.response_times:
            return {
                "endpoint": endpoint,
                "total_requests": 0,
                "error_rate": 0.0,
                "avg_response_time": 0.0,
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "apdex_score": 1.0,
                "requests_per_hour": 0.0,
            }

        response_times = list(stats.response_times)

        return {
            "endpoint": endpoint,
            "total_requests": stats.total_requests,
            "error_rate": (stats.error_count / stats.total_requests) * 100,
            "avg_response_time": statistics.mean(response_times),
            "p50": self._percentile(response_times, 50),
            "p95": self._percentile(response_times, 95),
            "p99": self._percentile(response_times, 99),
            "apdex_score": self._calculate_apdex(response_times),
            "requests_per_hour": sum(stats.hourly_requests)
            if stats.hourly_requests
            else 0,
            "status_codes": dict(stats.status_codes),
        }

    def get_global_stats(self) -> Dict[str, Any]:
        """Get global application statistics."""
        if not self.global_stats.response_times:
            return {
                "total_requests": 0,
                "error_rate": 0.0,
                "avg_response_time": 0.0,
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "apdex_score": 1.0,
                "throughput_rpm": 0.0,
                "status_codes": {},
            }

        response_times = list(self.global_stats.response_times)

        # Calculate throughput (requests per minute)
        now = datetime.now(timezone.utc)
        minute_ago = now - timedelta(minutes=1)
        recent_requests = sum(
            1
            for rt in self.global_stats.response_times
            if (
                now
                - timedelta(
                    seconds=len(self.global_stats.response_times)
                    - list(self.global_stats.response_times).index(rt)
                )
            )
            >= minute_ago
        )

        return {
            "total_requests": self.global_stats.total_requests,
            "error_rate": (
                self.global_stats.error_count / self.global_stats.total_requests
            )
            * 100,
            "avg_response_time": statistics.mean(response_times),
            "p50": self._percentile(response_times, 50),
            "p95": self._percentile(response_times, 95),
            "p99": self._percentile(response_times, 99),
            "apdex_score": self._calculate_apdex(response_times),
            "throughput_rpm": recent_requests,
            "status_codes": dict(self.global_stats.status_codes),
        }

    def get_all_endpoints_stats(self) -> List[Dict[str, Any]]:
        """Get statistics for all endpoints."""
        return [
            self.get_endpoint_stats(endpoint) for endpoint in self.endpoint_stats.keys()
        ]

    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0

        sorted_data = sorted(data)
        index = (percentile / 100) * len(sorted_data)

        if index.is_integer():
            return sorted_data[int(index) - 1]
        else:
            lower = sorted_data[int(index)]
            upper = (
                sorted_data[int(index) + 1]
                if int(index) + 1 < len(sorted_data)
                else lower
            )
            return lower + (upper - lower) * (index - int(index))

    def _calculate_apdex(self, response_times: List[float]) -> float:
        """Calculate Apdex score."""
        if not response_times:
            return 1.0

        satisfied = sum(1 for rt in response_times if rt <= self.apdex_threshold)
        tolerating = sum(
            1
            for rt in response_times
            if self.apdex_threshold < rt <= self.apdex_toleration
        )

        total = len(response_times)
        return (satisfied + (0.5 * tolerating)) / total

    def reset_stats(self) -> None:
        """Reset all statistics."""
        with self._lock:
            self.endpoint_stats.clear()
            self.global_stats = EndpointStats()


@asynccontextmanager
async def track_request(
    apm_collector: APMCollector,
    endpoint: str,
    method: str,
    user_id: Optional[str] = None,
):
    """Context manager to track request metrics."""
    start_time = time.time()
    db_queries = 0
    cache_hits = 0
    cache_misses = 0
    error_type = None

    try:
        yield {
            "add_db_query": lambda: setattr(
                locals(), "db_queries", locals().get("db_queries", 0) + 1
            ),
            "add_cache_hit": lambda: setattr(
                locals(), "cache_hits", locals().get("cache_hits", 0) + 1
            ),
            "add_cache_miss": lambda: setattr(
                locals(), "cache_misses", locals().get("cache_misses", 0) + 1
            ),
            "set_error": lambda error: setattr(locals(), "error_type", str(error)),
        }
        status_code = 200
    except Exception as e:
        status_code = 500
        error_type = type(e).__name__
        raise
    finally:
        end_time = time.time()
        response_time = end_time - start_time

        metrics = RequestMetrics(
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time=response_time,
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            error_type=error_type,
            db_queries=db_queries,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
        )

        await apm_collector.record_request(metrics)


class APMMiddleware:
    """FastAPI middleware for automatic APM tracking."""

    def __init__(self, apm_collector: APMCollector):
        self.apm_collector = apm_collector

    async def __call__(self, request, call_next):
        """Process request with APM tracking."""
        start_time = time.time()

        # Get user ID if available
        user_id = getattr(request.state, "user_id", None)

        # Track request
        response = await call_next(request)

        # Calculate metrics
        end_time = time.time()
        response_time = end_time - start_time

        metrics = RequestMetrics(
            endpoint=request.url.path,
            method=request.method,
            status_code=response.status_code,
            response_time=response_time,
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
        )

        await self.apm_collector.record_request(metrics)

        # Add performance headers
        response.headers["X-Response-Time"] = f"{response_time:.3f}"

        return response
