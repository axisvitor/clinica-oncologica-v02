"""
Rate limiting middleware for API endpoints.
"""

import time
import logging
from typing import Dict, Optional, Tuple
from collections import defaultdict

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter implementation.

    NOTE: This in-memory rate limiter has a memory leak potential
    as it stores all unique keys indefinitely. Use DistributedRateLimiter
    with Redis for production deployments.
    """

    # Maximum number of tracked keys before cleanup
    MAX_KEYS = 10000
    # Keys older than this (seconds) are eligible for cleanup
    KEY_EXPIRY = 3600  # 1 hour

    def __init__(self, rate: int = 10, per: int = 60):
        """
        Initialize rate limiter.

        Args:
            rate: Number of requests allowed
            per: Time period in seconds
        """
        self.rate = rate
        self.per = per
        self.allowance = defaultdict(lambda: rate)
        self.last_check = defaultdict(time.time)
        self._last_cleanup = time.time()

    def _cleanup_old_keys(self) -> None:
        """
        Remove old keys to prevent memory leak.
        Called periodically when checking rate limits.
        """
        current = time.time()
        # Only cleanup every 5 minutes or when we have too many keys
        if current - self._last_cleanup < 300 and len(self.last_check) < self.MAX_KEYS:
            return

        self._last_cleanup = current
        expiry_threshold = current - self.KEY_EXPIRY

        # Find keys to remove (older than expiry threshold)
        keys_to_remove = [
            key for key, last_time in self.last_check.items()
            if last_time < expiry_threshold
        ]

        # Remove old keys
        for key in keys_to_remove:
            del self.last_check[key]
            del self.allowance[key]

        if keys_to_remove:
            logger.debug(f"Rate limiter cleanup: removed {len(keys_to_remove)} old keys")

    def is_allowed(self, key: str) -> Tuple[bool, Optional[int]]:
        """
        Check if request is allowed.

        Args:
            key: Unique identifier for rate limiting (e.g., IP address, user ID)

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        # Periodic cleanup to prevent memory leak
        self._cleanup_old_keys()

        current = time.time()
        time_passed = current - self.last_check[key]
        self.last_check[key] = current

        # Replenish tokens based on time passed
        self.allowance[key] += time_passed * (self.rate / self.per)

        # Cap at maximum rate
        if self.allowance[key] > self.rate:
            self.allowance[key] = self.rate

        # Check if request is allowed
        if self.allowance[key] < 1.0:
            # Calculate retry after
            retry_after = int((1.0 - self.allowance[key]) * (self.per / self.rate))
            return False, retry_after

        # Consume one token
        self.allowance[key] -= 1.0
        return True, None

    def reset(self, key: str):
        """Reset rate limit for specific key."""
        self.allowance[key] = self.rate
        self.last_check[key] = time.time()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware for FastAPI.
    """

    # Different rate limits for different endpoints
    RATE_LIMITS = {
        "/api/auth/login": (5, 60),  # 5 requests per minute
        "/api/auth/register": (3, 60),  # 3 requests per minute
        "/api/messages/send": (30, 60),  # 30 messages per minute
        "/api/patients": (100, 60),  # 100 requests per minute
        "/ws": (10, 60),  # 10 WebSocket connections per minute
        "default": (60, 60),  # 60 requests per minute default
    }

    def __init__(self, app):
        super().__init__(app)
        self.limiters = {}

        # Initialize rate limiters for each endpoint
        for endpoint, (rate, per) in self.RATE_LIMITS.items():
            self.limiters[endpoint] = RateLimiter(rate, per)

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Apply rate limiting to requests.
        """
        # Skip rate limiting for health check and docs
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        # Get client identifier (IP address or authenticated user)
        client_id = self._get_client_id(request)

        # Get appropriate rate limiter
        limiter = self._get_limiter_for_path(request.url.path)

        # Check rate limit
        is_allowed, retry_after = limiter.is_allowed(client_id)

        if not is_allowed:
            logger.warning(f"Rate limit exceeded for {client_id} on {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limiter.rate)
        response.headers["X-RateLimit-Remaining"] = str(
            int(limiter.allowance[client_id])
        )
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + limiter.per))

        return response

    def _get_client_id(self, request: Request) -> str:
        """
        Get unique client identifier from request.

        Priority:
        1. Authenticated user ID (from JWT)
        2. API key
        3. IP address
        """
        # Try to get authenticated user from request state
        if hasattr(request.state, "user") and request.state.user:
            return f"user:{request.state.user.id}"

        # Try to get API key from headers
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"api:{api_key}"

        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"

        # Check for proxy headers
        # SECURITY: Only trust X-Forwarded-For if we're behind a trusted proxy
        # Railway/Heroku/AWS add this header - we trust the first IP in the chain
        # when running behind known load balancers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Get the leftmost IP (original client)
            forwarded_ip = forwarded_for.split(",")[0].strip()
            # Basic validation: ensure it looks like an IP address
            if self._is_valid_ip(forwarded_ip):
                client_ip = forwarded_ip
            else:
                logger.warning(f"Invalid X-Forwarded-For IP format: {forwarded_ip}")

        return f"ip:{client_ip}"

    def _is_valid_ip(self, ip: str) -> bool:
        """
        Basic IP address format validation.
        Returns True if the string looks like a valid IPv4 or IPv6 address.
        """
        import re
        # IPv4 pattern
        ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        # IPv6 pattern (simplified)
        ipv6_pattern = r'^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$'

        if re.match(ipv4_pattern, ip):
            # Validate each octet is 0-255
            try:
                octets = [int(x) for x in ip.split('.')]
                return all(0 <= o <= 255 for o in octets)
            except ValueError:
                return False
        elif re.match(ipv6_pattern, ip):
            return True
        return False

    def _get_limiter_for_path(self, path: str) -> RateLimiter:
        """
        Get appropriate rate limiter for request path.
        """
        # Check for exact match
        if path in self.limiters:
            return self.limiters[path]

        # Check for prefix match
        for endpoint in self.limiters:
            if endpoint != "default" and path.startswith(endpoint):
                return self.limiters[endpoint]

        # Return default limiter
        return self.limiters["default"]


class AdaptiveRateLimiter(RateLimiter):
    """
    Adaptive rate limiter that adjusts limits based on client behavior.
    """

    def __init__(self, base_rate: int = 10, per: int = 60):
        super().__init__(base_rate, per)
        self.base_rate = base_rate
        self.reputation = defaultdict(lambda: 1.0)  # Reputation score (0.5 to 2.0)
        self.violations = defaultdict(int)

    def is_allowed(self, key: str) -> Tuple[bool, Optional[int]]:
        """
        Check if request is allowed with adaptive limits.
        """
        # Adjust rate based on reputation
        adjusted_rate = self.base_rate * self.reputation[key]
        self.rate = max(1, int(adjusted_rate))

        is_allowed, retry_after = super().is_allowed(key)

        if not is_allowed:
            # Record violation
            self.violations[key] += 1

            # Decrease reputation for repeated violations
            if self.violations[key] > 3:
                self.reputation[key] = max(0.5, self.reputation[key] - 0.1)
        else:
            # Slowly restore reputation for good behavior
            if self.violations[key] > 0:
                self.violations[key] = max(0, self.violations[key] - 1)
            self.reputation[key] = min(2.0, self.reputation[key] + 0.01)

        return is_allowed, retry_after

    def get_client_stats(self, key: str) -> Dict:
        """Get statistics for specific client."""
        return {
            "reputation": self.reputation[key],
            "violations": self.violations[key],
            "current_rate": int(self.base_rate * self.reputation[key]),
            "allowance": self.allowance[key],
        }
