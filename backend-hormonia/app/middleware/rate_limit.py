"""
Rate limiting middleware module.

This module provides a simplified RateLimitMiddleware class that wraps
the existing rate limiting functionality for compatibility with test imports.
"""

import time
from typing import Dict, Tuple, Optional
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send
import logging

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple rate limiting middleware for testing compatibility.

    This is a simplified version that provides basic rate limiting
    functionality compatible with the test suite expectations.
    """

    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 60,
        window_seconds: int = 60
    ):
        """
        Initialize rate limiting middleware.

        Args:
            app: ASGI application
            requests_per_minute: Maximum requests per minute per IP
            window_seconds: Time window in seconds for rate limiting
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self.request_store: Dict[str, list] = {}

    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        client_ip = self._get_client_ip(request)

        # Clean up old requests
        self._cleanup_old_requests(client_ip)

        # Check rate limit
        if not self._is_request_allowed(client_ip):
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {self.requests_per_minute} requests per minute.",
                headers={"Retry-After": "60"}
            )

        # Record this request
        self._record_request(client_ip)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        remaining = max(0, self.requests_per_minute - len(self.request_store.get(client_ip, [])))
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + self.window_seconds))

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to client address
        return request.client.host if request.client else "unknown"

    def _cleanup_old_requests(self, ip: str) -> None:
        """Remove requests older than the time window."""
        if ip not in self.request_store:
            return

        current_time = time.time()
        cutoff_time = current_time - self.window_seconds

        self.request_store[ip] = [
            req_time for req_time in self.request_store[ip]
            if req_time > cutoff_time
        ]

        # Remove empty entries
        if not self.request_store[ip]:
            del self.request_store[ip]

    def _is_request_allowed(self, ip: str) -> bool:
        """Check if request is within rate limit."""
        if ip not in self.request_store:
            return True

        return len(self.request_store[ip]) < self.requests_per_minute

    def _record_request(self, ip: str) -> None:
        """Record current request timestamp."""
        if ip not in self.request_store:
            self.request_store[ip] = []

        self.request_store[ip].append(time.time())


# Alias for compatibility with enhanced middleware
RateLimitMiddleware.__doc__ = """
Rate limiting middleware with configurable limits per IP address.

Features:
- Configurable requests per minute limit
- IP-based rate limiting with forwarded header support
- Automatic cleanup of expired request records
- Standard rate limit headers in responses
- 429 status code with Retry-After header when limit exceeded

Compatible with test suites expecting basic rate limiting functionality.
"""