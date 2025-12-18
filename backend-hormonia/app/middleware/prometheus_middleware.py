"""
Prometheus metrics middleware for FastAPI.

Automatically tracks HTTP request metrics.
"""

import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.monitoring.metrics import (
    http_request_duration_seconds,
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to track HTTP request metrics."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Track request metrics."""
        method = request.method
        path = request.url.path

        # Skip metrics endpoint
        if path == "/metrics":
            return await call_next(request)

        start_time = time.time()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            # Track failed requests
            status_code = 500
            duration = time.time() - start_time
            http_request_duration_seconds.labels(
                method=method, endpoint=path, status_code=str(status_code)
            ).observe(duration)
            raise
        else:
            # Track successful requests
            duration = time.time() - start_time
            http_request_duration_seconds.labels(
                method=method, endpoint=path, status_code=str(status_code)
            ).observe(duration)

            return response
