"""
Cache Monitoring Middleware - Track cache hit/miss rates per endpoint

Sprint 1 (P1-1): Monitor cache performance across all API endpoints.

Features:
- Track cache hit/miss rates per endpoint
- Log slow cache operations (>10ms)
- Add cache metrics to response headers (X-Cache-Status: HIT/MISS)
- Integration with existing metrics middleware
"""

import logging
import time
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from fastapi import FastAPI

from app.utils.query_cache import get_query_cache

logger = logging.getLogger(__name__)


class CacheMonitoringMiddleware(BaseHTTPMiddleware):
    """
    Middleware to monitor cache performance per endpoint.

    Adds X-Cache-* headers to responses for debugging and monitoring.
    """

    def __init__(self, app: FastAPI):
        super().__init__(app)
        self.cache = get_query_cache()

        # Per-endpoint statistics
        self.endpoint_stats = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with cache monitoring.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/route handler

        Returns:
            HTTP response with cache headers
        """
        # Capture cache stats before request
        stats_before = self.cache.get_stats().copy()

        # Record request start time
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate request duration
        duration_ms = (time.time() - start_time) * 1000

        # Capture cache stats after request
        stats_after = self.cache.get_stats()

        # Calculate cache operations during this request
        cache_hits = stats_after['hits'] - stats_before['hits']
        cache_misses = stats_after['misses'] - stats_before['misses']

        # Determine cache status
        if cache_hits > 0 and cache_misses == 0:
            cache_status = 'HIT'
        elif cache_misses > 0 and cache_hits == 0:
            cache_status = 'MISS'
        elif cache_hits > 0 and cache_misses > 0:
            cache_status = 'PARTIAL'
        else:
            cache_status = 'NONE'

        # Add cache headers to response
        response.headers['X-Cache-Status'] = cache_status
        response.headers['X-Cache-Hits'] = str(cache_hits)
        response.headers['X-Cache-Misses'] = str(cache_misses)

        # Add performance header if request was slow
        if duration_ms > 1000:  # Log slow requests (>1s)
            response.headers['X-Response-Time-Ms'] = f"{duration_ms:.2f}"
            logger.warning(
                f"Slow request: {request.method} {request.url.path} "
                f"({duration_ms:.2f}ms, cache: {cache_status})"
            )

        # Update per-endpoint statistics
        endpoint = f"{request.method} {request.url.path}"
        if endpoint not in self.endpoint_stats:
            self.endpoint_stats[endpoint] = {
                'hits': 0,
                'misses': 0,
                'total_requests': 0,
                'total_duration_ms': 0.0
            }

        self.endpoint_stats[endpoint]['hits'] += cache_hits
        self.endpoint_stats[endpoint]['misses'] += cache_misses
        self.endpoint_stats[endpoint]['total_requests'] += 1
        self.endpoint_stats[endpoint]['total_duration_ms'] += duration_ms

        # Log slow cache operations (>10ms average)
        avg_cache_time = stats_after.get('avg_get_time_ms', 0)
        if avg_cache_time > 10:
            logger.warning(
                f"Slow cache operation detected: {avg_cache_time:.2f}ms average "
                f"(endpoint: {endpoint})"
            )

        return response

    def get_endpoint_statistics(self) -> dict:
        """
        Get cache statistics grouped by endpoint.

        Returns:
            Dictionary mapping endpoint -> statistics
        """
        stats = {}

        for endpoint, data in self.endpoint_stats.items():
            total_cache_ops = data['hits'] + data['misses']
            hit_rate = (data['hits'] / total_cache_ops * 100) if total_cache_ops > 0 else 0

            avg_duration = (
                data['total_duration_ms'] / data['total_requests']
                if data['total_requests'] > 0 else 0
            )

            stats[endpoint] = {
                'hits': data['hits'],
                'misses': data['misses'],
                'total_requests': data['total_requests'],
                'hit_rate_percent': round(hit_rate, 2),
                'avg_response_time_ms': round(avg_duration, 2)
            }

        return stats

    def reset_endpoint_statistics(self):
        """Reset per-endpoint statistics."""
        self.endpoint_stats = {}
        logger.info("Cache endpoint statistics reset")


# Middleware factory function
def setup_cache_monitoring(app: FastAPI) -> CacheMonitoringMiddleware:
    """
    Setup cache monitoring middleware for FastAPI app.

    Args:
        app: FastAPI application instance

    Returns:
        CacheMonitoringMiddleware instance
    """
    middleware = CacheMonitoringMiddleware(app)
    app.add_middleware(CacheMonitoringMiddleware)

    logger.info("✅ Cache monitoring middleware enabled")
    return middleware
