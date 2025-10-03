"""Rate limiting middleware for public and private endpoints."""
import time
from typing import Dict, Optional, Tuple
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Base rate limiter class."""

    def __init__(self):
        self.requests: Dict[str, list] = {}

    def _clean_old_requests(self, ip: str, window_seconds: int):
        """Remove old requests outside the time window."""
        if ip in self.requests:
            current_time = time.time()
            self.requests[ip] = [
                req_time for req_time in self.requests[ip]
                if current_time - req_time < window_seconds
            ]

    def is_allowed(self, ip: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
        """Check if request is allowed."""
        current_time = time.time()
        self._clean_old_requests(ip, window_seconds)

        if ip not in self.requests:
            self.requests[ip] = []

        request_count = len(self.requests[ip])

        if request_count >= limit:
            return False, request_count

        self.requests[ip].append(current_time)
        return True, request_count + 1


class PublicEndpointRateLimiter:
    """Rate limiter for public endpoints (quiz, webhooks)."""

    def __init__(self, requests_per_minute: int = 10, requests_per_hour: int = 50, burst_limit: int = 5):
        self.limiter = RateLimiter()
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_limit = burst_limit
        # Different limits for different endpoints
        self.limits = {
            "/api/v1/monthly-quiz-public": (requests_per_minute, 60),  # Per minute limit
            "/api/v1/webhook": (100, 60),  # 100 requests per minute
            "default": (30, 60)  # 30 requests per minute for other public endpoints
        }
        # Also track hourly limits
        self.hourly_limiter = RateLimiter()
        self.hourly_limits = {
            "/api/v1/monthly-quiz-public": (requests_per_hour, 3600),  # Per hour limit
            "/api/v1/webhook": (500, 3600),  # 500 requests per hour
            "default": (200, 3600)  # 200 requests per hour
        }

    async def __call__(self, request: Request, call_next):
        """Middleware to enforce rate limiting on public endpoints."""
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        # Find matching limit configuration
        minute_config = None
        hourly_config = None

        for endpoint_prefix, config in self.limits.items():
            if endpoint_prefix != "default" and path.startswith(endpoint_prefix):
                minute_config = config
                break

        for endpoint_prefix, config in self.hourly_limits.items():
            if endpoint_prefix != "default" and path.startswith(endpoint_prefix):
                hourly_config = config
                break

        if not minute_config:
            minute_config = self.limits["default"]
        if not hourly_config:
            hourly_config = self.hourly_limits["default"]

        minute_limit, minute_window = minute_config
        hourly_limit, hourly_window = hourly_config

        # Check minute rate limit
        minute_allowed, minute_count = self.limiter.is_allowed(client_ip, minute_limit, minute_window)

        if not minute_allowed:
            logger.warning(f"Minute rate limit exceeded for IP {client_ip} on {path}: {minute_count} requests in {minute_window}s")
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Maximum {minute_limit} requests per minute."
            )

        # Check hourly rate limit
        hourly_allowed, hourly_count = self.hourly_limiter.is_allowed(client_ip, hourly_limit, hourly_window)

        if not hourly_allowed:
            logger.warning(f"Hourly rate limit exceeded for IP {client_ip} on {path}: {hourly_count} requests in {hourly_window}s")
            raise HTTPException(
                status_code=429,
                detail=f"Hourly rate limit exceeded. Maximum {hourly_limit} requests per hour."
            )

        # Add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(minute_limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, minute_limit - minute_count))
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + minute_window))
        response.headers["X-RateLimit-Hourly-Limit"] = str(hourly_limit)
        response.headers["X-RateLimit-Hourly-Remaining"] = str(max(0, hourly_limit - hourly_count))

        return response

    async def check_rate_limit(self, request: Request) -> None:
        """
        Check rate limits for a request without middleware overhead.
        Raises HTTPException(429) if limit exceeded.

        Args:
            request: The incoming request

        Raises:
            HTTPException: If rate limit is exceeded
        """
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        # Find matching limit configuration
        minute_config = None
        hourly_config = None

        for endpoint_prefix, config in self.limits.items():
            if endpoint_prefix != "default" and path.startswith(endpoint_prefix):
                minute_config = config
                break

        for endpoint_prefix, config in self.hourly_limits.items():
            if endpoint_prefix != "default" and path.startswith(endpoint_prefix):
                hourly_config = config
                break

        if not minute_config:
            minute_config = self.limits["default"]
        if not hourly_config:
            hourly_config = self.hourly_limits["default"]

        minute_limit, minute_window = minute_config
        hourly_limit, hourly_window = hourly_config

        # Check minute rate limit
        minute_allowed, minute_count = self.limiter.is_allowed(client_ip, minute_limit, minute_window)

        if not minute_allowed:
            logger.warning(f"Minute rate limit exceeded for IP {client_ip} on {path}: {minute_count} requests in {minute_window}s")
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Maximum {minute_limit} requests per minute."
            )

        # Check hourly rate limit
        hourly_allowed, hourly_count = self.hourly_limiter.is_allowed(client_ip, hourly_limit, hourly_window)

        if not hourly_allowed:
            logger.warning(f"Hourly rate limit exceeded for IP {client_ip} on {path}: {hourly_count} requests in {hourly_window}s")
            raise HTTPException(
                status_code=429,
                detail=f"Hourly rate limit exceeded. Maximum {hourly_limit} requests per hour."
            )


class EnhancedRateLimitMiddleware(BaseHTTPMiddleware):
    """Enhanced rate limiting middleware for all endpoints."""

    def __init__(self, app, default_limit: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.limiter = RateLimiter()
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self.public_limiter = PublicEndpointRateLimiter()

    async def dispatch(self, request: Request, call_next):
        """Dispatch request with rate limiting."""
        path = request.url.path

        # Public endpoints use their own limiter
        if path.startswith("/api/v1/monthly-quiz-public") or path.startswith("/api/v1/webhook"):
            return await self.public_limiter(request, call_next)

        # Private endpoints use general limiter
        client_ip = request.client.host if request.client else "unknown"

        allowed, count = self.limiter.is_allowed(
            client_ip,
            self.default_limit,
            self.window_seconds
        )

        if not allowed:
            logger.warning(f"Rate limit exceeded for IP {client_ip}: {count} requests")
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Maximum {self.default_limit} requests per {self.window_seconds} seconds."
            )

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.default_limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, self.default_limit - count))
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + self.window_seconds))

        return response