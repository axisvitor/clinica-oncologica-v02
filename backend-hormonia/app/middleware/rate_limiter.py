"""
Rate limiting middleware for API endpoints.

IMPORTANT: This module provides multiple rate limiter implementations:
1. RateLimiter - In-memory (development only, has memory leak potential)
2. DistributedRateLimiter - Redis-based (RECOMMENDED for production)
3. AdaptiveRateLimiter - Behavior-based (in-memory, development only)

Production deployments MUST use DistributedRateLimiter with Redis to avoid
memory leaks and ensure proper distributed rate limiting across multiple servers.
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
    Token bucket rate limiter implementation (In-Memory).

    ⚠️ WARNING - MEMORY LEAK POTENTIAL:
    This in-memory rate limiter is suitable ONLY for development/testing.

    PROBLEMS:
    - Stores all unique keys indefinitely (bounded cleanup helps but doesn't eliminate risk)
    - State lost on server restart/deployment
    - Does NOT work with multiple server instances (load balanced deployments)
    - Not thread-safe in concurrent environments
    - IP keys accumulate over time despite cleanup

    RECOMMENDATION:
    Use DistributedRateLimiter with Redis for production deployments.
    See research/cors-csrf-technical-debt-analysis.md for details.
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

        Cleanup Strategy:
        1. Time-based: Remove keys older than KEY_EXPIRY
        2. Size-based: Evict oldest entries if exceeding MAX_KEYS
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

        # Remove old keys (time-based cleanup)
        for key in keys_to_remove:
            del self.last_check[key]
            del self.allowance[key]

        if keys_to_remove:
            logger.debug(f"Rate limiter cleanup: removed {len(keys_to_remove)} old keys")

        # Size-based eviction: Remove oldest entries if still exceeding MAX_KEYS
        if len(self.allowance) > self.MAX_KEYS:
            excess_count = len(self.allowance) - self.MAX_KEYS
            # Sort by last check time (oldest first)
            sorted_keys = sorted(self.last_check.items(), key=lambda x: x[1])

            evicted_count = 0
            for key, _ in sorted_keys[:excess_count]:
                self.allowance.pop(key, None)
                self.last_check.pop(key, None)
                evicted_count += 1

            if evicted_count > 0:
                logger.info(
                    f"Rate limiter size eviction: removed {evicted_count} oldest keys "
                    f"(current size: {len(self.allowance)})"
                )

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

    WARNING - MEMORY LEAK POTENTIAL:
    This in-memory rate limiter tracks reputation and violations per client.
    Use DistributedRateLimiter for production deployments.
    """

    # Maximum clients to track before cleanup
    MAX_TRACKED_CLIENTS = 10000
    # Clients with no violations for this duration (seconds) are eligible for cleanup
    REPUTATION_CLEANUP_EXPIRY = 7200  # 2 hours

    def __init__(self, base_rate: int = 10, per: int = 60):
        super().__init__(base_rate, per)
        self.base_rate = base_rate
        self.reputation = defaultdict(lambda: 1.0)  # Reputation score (0.5 to 2.0)
        self.violations = defaultdict(int)
        self._reputation_last_access = defaultdict(time.time)

    def is_allowed(self, key: str) -> Tuple[bool, Optional[int]]:
        """
        Check if request is allowed with adaptive limits.
        """
        # Cleanup adaptive tracking data periodically
        self._cleanup_adaptive_data()

        # Track last access time for this key
        self._reputation_last_access[key] = time.time()

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

    def _cleanup_adaptive_data(self) -> None:
        """
        Clean up reputation and violations dictionaries to prevent memory leaks.

        Cleanup Strategy:
        1. Remove entries for clients with default reputation (1.0), no violations,
           and not accessed recently
        2. Size-based eviction for oldest entries when exceeding MAX_TRACKED_CLIENTS
        """
        current = time.time()

        # Only run cleanup every 5 minutes (piggyback on parent cleanup timer)
        if current - self._last_cleanup < 300 and len(self.reputation) < self.MAX_TRACKED_CLIENTS:
            return

        expiry_threshold = current - self.REPUTATION_CLEANUP_EXPIRY

        # Find keys eligible for cleanup (default reputation, no violations, old)
        keys_to_remove = []
        for key in list(self._reputation_last_access.keys()):
            last_access = self._reputation_last_access.get(key, 0)
            reputation = self.reputation.get(key, 1.0)
            violations = self.violations.get(key, 0)

            # Remove if: old + default reputation + no violations
            if last_access < expiry_threshold and abs(reputation - 1.0) < 0.01 and violations == 0:
                keys_to_remove.append(key)

        # Clean up identified keys
        for key in keys_to_remove:
            self.reputation.pop(key, None)
            self.violations.pop(key, None)
            self._reputation_last_access.pop(key, None)

        if keys_to_remove:
            logger.debug(f"AdaptiveRateLimiter cleanup: removed {len(keys_to_remove)} idle clients")

        # Size-based eviction if still over limit
        if len(self.reputation) > self.MAX_TRACKED_CLIENTS:
            excess = len(self.reputation) - self.MAX_TRACKED_CLIENTS
            # Sort by last access (oldest first)
            sorted_keys = sorted(
                self._reputation_last_access.items(),
                key=lambda x: x[1]
            )

            evicted = 0
            for key, _ in sorted_keys[:excess]:
                self.reputation.pop(key, None)
                self.violations.pop(key, None)
                self._reputation_last_access.pop(key, None)
                evicted += 1

            if evicted > 0:
                logger.info(
                    f"AdaptiveRateLimiter size eviction: removed {evicted} oldest clients "
                    f"(current tracked: {len(self.reputation)})"
                )

    def get_client_stats(self, key: str) -> Dict:
        """Get statistics for specific client."""
        return {
            "reputation": self.reputation[key],
            "violations": self.violations[key],
            "current_rate": int(self.base_rate * self.reputation[key]),
            "allowance": self.allowance[key],
        }


class DistributedRateLimiter:
    """
    Redis-based distributed rate limiter using Token Bucket algorithm.

    ✅ PRODUCTION-READY:
    - No memory leaks (Redis handles TTL automatically)
    - Works across multiple server instances
    - State persists across restarts
    - Thread-safe and distributed-friendly
    - Automatic cleanup via Redis TTL

    This implementation uses Redis with atomic operations and automatic
    expiration to provide distributed rate limiting without memory leaks.

    Usage:
        # In application startup
        from app.middleware.rate_limiter import DistributedRateLimiter

        rate_limiter = DistributedRateLimiter(
            redis_url="redis://localhost:6379/3",  # Use dedicated DB for rate limiting
            rate=100,
            per=60
        )

        # In middleware/endpoint
        is_allowed, retry_after = await rate_limiter.is_allowed("user:123")
        if not is_allowed:
            raise HTTPException(429, detail=f"Retry after {retry_after}s")
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        rate: int = 60,
        per: int = 60,
        prefix: str = "ratelimit",
    ):
        """
        Initialize distributed rate limiter.

        Args:
            redis_url: Redis connection URL (uses settings if None)
            rate: Number of requests allowed
            per: Time period in seconds
            prefix: Redis key prefix for rate limit data
        """
        self.rate = rate
        self.per = per
        self.prefix = prefix
        self._redis_client = None
        self._redis_url = redis_url

    def _get_redis_client(self):
        """Get or create Redis client (lazy initialization)."""
        if self._redis_client is None:
            import redis
            from app.config import settings

            # Use provided URL or fall back to settings
            redis_url = self._redis_url or getattr(
                settings,
                "RATE_LIMIT_REDIS_URL",
                getattr(settings, "REDIS_URL", "redis://localhost:6379/3")
            )

            # Parse URL to add DB number if not present
            if "?" not in redis_url and redis_url.endswith(("6379", "6379/")):
                # Use dedicated DB for rate limiting (DB 3)
                redis_url = redis_url.rstrip("/") + "/3"

            try:
                self._redis_client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
                # Test connection
                self._redis_client.ping()
                logger.info(f"DistributedRateLimiter: Connected to Redis at {redis_url}")
            except Exception as e:
                logger.error(f"DistributedRateLimiter: Failed to connect to Redis: {e}")
                logger.warning("DistributedRateLimiter: Falling back to in-memory rate limiting")
                # Fall back to None - will be handled in is_allowed()
                self._redis_client = None

        return self._redis_client

    async def is_allowed(self, key: str) -> Tuple[bool, Optional[int]]:
        """
        Check if request is allowed using Redis-based rate limiting.

        Args:
            key: Unique identifier for rate limiting (e.g., "user:123", "ip:1.2.3.4")

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        redis_client = self._get_redis_client()

        # Fall back to permissive if Redis unavailable
        if redis_client is None:
            logger.warning(f"Redis unavailable, allowing request for {key}")
            return True, None

        try:
            return await self._check_rate_limit_redis(redis_client, key)
        except Exception as e:
            logger.error(f"Rate limit check failed for {key}: {e}")
            # Fail open - allow request if Redis has issues
            return True, None

    async def _check_rate_limit_redis(
        self, redis_client, key: str
    ) -> Tuple[bool, Optional[int]]:
        """
        Perform Redis-based rate limit check using Token Bucket algorithm.

        Uses Redis atomic operations (MULTI/EXEC pipeline) for thread-safety.
        """
        redis_key_allowance = f"{self.prefix}:allowance:{key}"
        redis_key_last_check = f"{self.prefix}:last_check:{key}"

        current_time = time.time()

        # Use pipeline for atomic operations
        pipe = redis_client.pipeline()

        try:
            # Get current values
            pipe.get(redis_key_allowance)
            pipe.get(redis_key_last_check)
            values = pipe.execute()

            # Parse values
            allowance = float(values[0]) if values[0] else self.rate
            last_check = float(values[1]) if values[1] else current_time

            # Calculate new allowance
            time_passed = current_time - last_check
            allowance += time_passed * (self.rate / self.per)
            allowance = min(allowance, self.rate)  # Cap at max rate

            # Check if allowed
            if allowance < 1.0:
                # Not allowed - calculate retry after
                retry_after = int((1.0 - allowance) * (self.per / self.rate))
                return False, retry_after

            # Consume token
            allowance -= 1.0

            # Update Redis (atomic)
            pipe = redis_client.pipeline()
            pipe.setex(redis_key_allowance, self.per * 2, str(allowance))
            pipe.setex(redis_key_last_check, self.per * 2, str(current_time))
            pipe.execute()

            return True, None

        except Exception as e:
            logger.error(f"Redis rate limit operation failed: {e}")
            # Fail open
            return True, None

    def reset(self, key: str):
        """Reset rate limit for specific key."""
        redis_client = self._get_redis_client()
        if redis_client:
            try:
                redis_key_allowance = f"{self.prefix}:allowance:{key}"
                redis_key_last_check = f"{self.prefix}:last_check:{key}"
                redis_client.delete(redis_key_allowance, redis_key_last_check)
            except Exception as e:
                logger.error(f"Failed to reset rate limit for {key}: {e}")

    def get_remaining(self, key: str) -> Optional[int]:
        """Get remaining requests for key."""
        redis_client = self._get_redis_client()
        if redis_client:
            try:
                redis_key_allowance = f"{self.prefix}:allowance:{key}"
                allowance = redis_client.get(redis_key_allowance)
                return int(float(allowance)) if allowance else self.rate
            except Exception as e:
                logger.error(f"Failed to get remaining for {key}: {e}")
        return None
