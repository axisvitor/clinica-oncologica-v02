"""
Performance metrics middleware for request tracking and monitoring.

Tracks request/response times, query counts, memory usage, and cache performance
in Prometheus-compatible format for observability.
"""

import time
from typing import Callable, Dict, Any, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import uuid
import psutil
from collections import defaultdict
from datetime import datetime

from app.utils.structured_logger import (
    StructuredLogger,
    set_correlation_id,
    set_request_id,
    set_user_id,
    set_request_path,
    clear_context,
)

logger = StructuredLogger(__name__)


class MetricsCollector:
    """
    Thread-safe metrics collector for application performance tracking.
    """

    def __init__(self):
        """Initialize metrics storage."""
        self.request_count = 0
        self.request_duration_sum = 0.0
        self.request_duration_count = 0
        self.status_codes: Dict[int, int] = defaultdict(int)
        self.endpoint_metrics: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "total_duration_ms": 0.0,
                "min_duration_ms": float("inf"),
                "max_duration_ms": 0.0,
                "error_count": 0,
            }
        )
        self.query_count = 0
        self.cache_hits = 0
        self.cache_misses = 0

    def record_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: float,
        query_count: int = 0,
    ):
        """
        Record request metrics.

        Args:
            endpoint: API endpoint path
            method: HTTP method
            status_code: Response status code
            duration_ms: Request duration in milliseconds
            query_count: Number of database queries
        """
        self.request_count += 1
        self.request_duration_sum += duration_ms
        self.request_duration_count += 1
        self.status_codes[status_code] += 1
        self.query_count += query_count

        # Track per-endpoint metrics
        key = f"{method}:{endpoint}"
        metrics = self.endpoint_metrics[key]
        metrics["count"] += 1
        metrics["total_duration_ms"] += duration_ms
        metrics["min_duration_ms"] = min(metrics["min_duration_ms"], duration_ms)
        metrics["max_duration_ms"] = max(metrics["max_duration_ms"], duration_ms)

        if status_code >= 400:
            metrics["error_count"] += 1

    def record_cache_operation(self, hit: bool):
        """
        Record cache hit or miss.

        Args:
            hit: True if cache hit, False if miss
        """
        if hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics snapshot.

        Returns:
            dict: Current metrics in Prometheus-compatible format
        """
        avg_duration = (
            self.request_duration_sum / self.request_duration_count
            if self.request_duration_count > 0
            else 0.0
        )

        cache_total = self.cache_hits + self.cache_misses
        cache_hit_rate = (
            (self.cache_hits / cache_total * 100) if cache_total > 0 else 0.0
        )

        # Process memory info
        process = psutil.Process()
        memory_info = process.memory_info()

        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "requests": {
                "total": self.request_count,
                "avg_duration_ms": round(avg_duration, 2),
                "by_status": dict(self.status_codes),
            },
            "endpoints": {
                key: {
                    "count": metrics["count"],
                    "avg_duration_ms": round(
                        metrics["total_duration_ms"] / metrics["count"], 2
                    )
                    if metrics["count"] > 0
                    else 0.0,
                    "min_duration_ms": round(metrics["min_duration_ms"], 2)
                    if metrics["min_duration_ms"] != float("inf")
                    else 0.0,
                    "max_duration_ms": round(metrics["max_duration_ms"], 2),
                    "error_count": metrics["error_count"],
                    "error_rate": round(
                        (metrics["error_count"] / metrics["count"] * 100), 2
                    )
                    if metrics["count"] > 0
                    else 0.0,
                }
                for key, metrics in self.endpoint_metrics.items()
            },
            "database": {
                "total_queries": self.query_count,
                "avg_queries_per_request": round(
                    self.query_count / self.request_count, 2
                )
                if self.request_count > 0
                else 0.0,
            },
            "cache": {
                "hits": self.cache_hits,
                "misses": self.cache_misses,
                "total": cache_total,
                "hit_rate_percent": round(cache_hit_rate, 2),
            },
            "memory": {
                "rss_mb": round(memory_info.rss / 1024 / 1024, 2),
                "vms_mb": round(memory_info.vms / 1024 / 1024, 2),
            },
        }

    def reset(self):
        """Reset all metrics."""
        self.request_count = 0
        self.request_duration_sum = 0.0
        self.request_duration_count = 0
        self.status_codes.clear()
        self.endpoint_metrics.clear()
        self.query_count = 0
        self.cache_hits = 0
        self.cache_misses = 0


# Global metrics collector
metrics_collector = MetricsCollector()


class PerformanceMetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track request performance metrics and context.
    """

    def __init__(self, app: ASGIApp):
        """
        Initialize middleware.

        Args:
            app: ASGI application
        """
        super().__init__(app)
        self.process = psutil.Process()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and track metrics.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response with metrics headers
        """
        # Set up request context
        request_id_value = str(uuid.uuid4())
        correlation_id_value = request.headers.get(
            "X-Correlation-ID", str(uuid.uuid4())
        )

        set_request_id(request_id_value)
        set_correlation_id(correlation_id_value)
        set_request_path(request.url.path)

        # Extract user ID if available (from auth middleware)
        user_id_value = getattr(request.state, "user_id", None)
        if user_id_value:
            set_user_id(user_id_value)

        # Track memory before request
        memory_before = self.process.memory_info().rss

        # Track request timing
        start_time = time.perf_counter()

        # Initialize query counter on request state
        request.state.query_count = 0

        try:
            # Process request
            response = await call_next(request)

            # Calculate metrics
            duration_ms = (time.perf_counter() - start_time) * 1000
            memory_after = self.process.memory_info().rss
            memory_delta_mb = (memory_after - memory_before) / 1024 / 1024

            # Get query count from request state
            query_count = getattr(request.state, "query_count", 0)

            # Record metrics
            metrics_collector.record_request(
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                duration_ms=duration_ms,
                query_count=query_count,
            )

            # Log request
            logger.log_api_call(
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                duration_ms=duration_ms,
                query_count=query_count,
                memory_delta_mb=round(memory_delta_mb, 2),
                user_id=user_id_value,
            )

            # Add metrics headers to response
            response.headers["X-Request-ID"] = request_id_value
            response.headers["X-Correlation-ID"] = correlation_id_value
            response.headers["X-Response-Time-Ms"] = str(round(duration_ms, 2))
            response.headers["X-Query-Count"] = str(query_count)

            return response

        except Exception as e:
            # Calculate metrics for failed request
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Record error metrics
            metrics_collector.record_request(
                endpoint=request.url.path,
                method=request.method,
                status_code=500,
                duration_ms=duration_ms,
                query_count=getattr(request.state, "query_count", 0),
            )

            # Log error
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                exc_info=e,
                duration_ms=duration_ms,
                error=str(e),
            )

            raise

        finally:
            # Clear context
            clear_context()


def get_metrics() -> Dict[str, Any]:
    """
    Get current performance metrics.

    Returns:
        dict: Performance metrics snapshot
    """
    return metrics_collector.get_metrics()


def reset_metrics():
    """Reset performance metrics."""
    metrics_collector.reset()


def record_cache_hit():
    """Record cache hit."""
    metrics_collector.record_cache_operation(hit=True)


def record_cache_miss():
    """Record cache miss."""
    metrics_collector.record_cache_operation(hit=False)


def increment_query_count(request: Optional[Request] = None, count: int = 1):
    """
    Increment query count for current request.

    Args:
        request: Current request (optional)
        count: Number of queries to add
    """
    if request and hasattr(request.state, "query_count"):
        request.state.query_count += count
