"""
Core Distributed Rate Limiter with Sliding Window Algorithm.

This module contains the core rate limiting logic extracted from
distributed_rate_limiter.py:

- RateLimitTier: Enum of rate limit tiers aligned with system roles
- RateLimitConfig: Configuration dataclass for endpoint rate limits
- RateLimitResult: Result dataclass from rate limit checks
- DistributedRateLimiter: Redis-based sliding window rate limiter

The sliding window algorithm stores request timestamps in Redis sorted sets,
providing accurate distributed rate limiting across multiple workers.

See distributed_rate_limiter.py for the FastAPI middleware wrapper
(RateLimitMiddleware) that uses these components.
"""

import time
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from redis import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local window_start = tonumber(ARGV[1])
local current_time = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local window = tonumber(ARGV[4])
redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, current_time, tostring(current_time))
    redis.call('EXPIRE', key, window + 60)
    return {1, count + 1}
end
return {0, count}
"""


class RateLimitTier(str, Enum):
    """Rate limit tiers - aligned with actual system roles."""

    PUBLIC = "public"  # Unauthenticated requests (quiz publico, health checks)
    AUTHENTICATED = "authenticated"  # Generic authenticated users
    DOCTOR = "doctor"  # Medicos autenticados
    PREMIUM = "premium"  # Premium tier users
    ADMIN = "admin"  # Administradores do sistema


@dataclass
class RateLimitConfig:
    """Rate limit configuration for an endpoint."""

    requests: int  # Number of requests allowed
    window: int  # Time window in seconds
    tier: RateLimitTier  # User tier
    burst_multiplier: float = 1.5  # Burst allowance (e.g., 1.5x = 50% burst)

    @property
    def burst_limit(self) -> int:
        """Maximum burst limit."""
        return int(self.requests * self.burst_multiplier)


@dataclass
class RateLimitResult:
    """Result of rate limit check."""

    allowed: bool  # Whether request is allowed
    limit: int  # Rate limit
    remaining: int  # Remaining requests
    reset_at: datetime  # When limit resets
    retry_after: Optional[int] = None  # Seconds to wait before retry


class DistributedRateLimiter:
    """
    Distributed rate limiter using Redis with sliding window algorithm.

    The sliding window algorithm:
    1. Store each request timestamp in a sorted set
    2. Remove timestamps older than the window
    3. Count remaining timestamps
    4. Allow if count < limit

    Redis keys:
    - ratelimit:sliding:{key}:{window} -> sorted set of timestamps
    - ratelimit:block:{key} -> blocked until timestamp (for penalties)

    Advantages over fixed window:
    - More accurate (no burst at window boundaries)
    - Better user experience (smoother limiting)
    - Distributed across workers
    """

    def __init__(
        self,
        redis: Redis,
        prefix: str = "ratelimit",
        enable_blocking: bool = True,
        block_duration: int = 300,  # 5 minutes
        fail_open: bool = True,  # Allow requests if Redis fails
    ):
        """
        Initialize distributed rate limiter.

        Args:
            redis: Redis client instance
            prefix: Key prefix for Redis keys
            enable_blocking: Enable temporary blocking for abuse
            block_duration: Duration to block abusive clients (seconds)
            fail_open: Allow requests if Redis is unavailable (fail open vs fail closed)
        """
        self.redis = redis
        self.prefix = prefix
        self.enable_blocking = enable_blocking
        self.block_duration = block_duration
        self.fail_open = fail_open
        self._sliding_window_script = redis.register_script(_SLIDING_WINDOW_LUA)

    def _get_key(self, identifier: str, window: int) -> str:
        """
        Get Redis key for rate limit.

        Args:
            identifier: Unique identifier (IP, user ID, etc.)
            window: Time window in seconds

        Returns:
            Redis key
        """
        return f"{self.prefix}:sliding:{identifier}:{window}"

    def _get_block_key(self, identifier: str) -> str:
        """
        Get Redis key for blocking.

        Args:
            identifier: Unique identifier

        Returns:
            Block key
        """
        return f"{self.prefix}:block:{identifier}"

    async def check_rate_limit(
        self,
        identifier: str,
        limit: int,
        window: int,
        increment: bool = True,
    ) -> RateLimitResult:
        """
        Check if request is within rate limit using sliding window.

        Args:
            identifier: Unique identifier (IP, user ID, etc.)
            limit: Maximum requests allowed
            window: Time window in seconds
            increment: Whether to increment counter (False for checking only)

        Returns:
            RateLimitResult with allow status and metadata
        """
        try:
            # Check if client is blocked
            if self.enable_blocking:
                block_key = self._get_block_key(identifier)
                block_until = self.redis.get(block_key)

                if block_until:
                    block_until_ts = int(block_until)
                    current_ts = int(time.time())

                    if current_ts < block_until_ts:
                        retry_after = block_until_ts - current_ts
                        logger.warning(
                            f"Client {identifier} is blocked for {retry_after}s"
                        )
                        return RateLimitResult(
                            allowed=False,
                            limit=limit,
                            remaining=0,
                            reset_at=datetime.fromtimestamp(block_until_ts),
                            retry_after=retry_after,
                        )

            # Sliding window algorithm
            key = self._get_key(identifier, window)
            current_time = time.time()
            window_start = current_time - window

            if increment:
                # Atomic path: Lua script executes check-and-increment as a single
                # operation on the Redis server, eliminating the race condition
                # between ZCARD and ZADD that existed in the pipeline implementation.
                result = self._sliding_window_script(
                    keys=[key],
                    args=[window_start, current_time, limit, window]
                )
                allowed = int(result[0]) == 1
                current_count = int(result[1])
            else:
                # Read-only path: no ZADD needed, pipeline is safe (no race condition
                # because we are not mutating state)
                pipe = self.redis.pipeline()
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zcard(key)
                results = pipe.execute()
                current_count = results[1]
                allowed = current_count < limit

            remaining = max(0, limit - current_count)
            reset_at = datetime.fromtimestamp(current_time + window)

            # Log if approaching limit
            if current_count >= limit * 0.9:
                logger.warning(
                    f"Rate limit approaching for {identifier}: "
                    f"{current_count}/{limit} in {window}s window"
                )

            # Check for abuse (significantly over limit)
            if self.enable_blocking and current_count > limit * 2:
                self._block_client(identifier, duration=self.block_duration)
                logger.error(
                    f"Blocking abusive client {identifier}: "
                    f"{current_count} requests (limit: {limit})"
                )

            return RateLimitResult(
                allowed=allowed,
                limit=limit,
                remaining=remaining,
                reset_at=reset_at,
                retry_after=window if not allowed else None,
            )

        except RedisError as e:
            logger.error(f"Redis error in rate limiter: {e}", exc_info=True)

            # Fail open or closed based on configuration
            if self.fail_open:
                logger.warning(
                    f"Rate limiter failing open due to Redis error for {identifier}"
                )
                return RateLimitResult(
                    allowed=True,
                    limit=limit,
                    remaining=limit,
                    reset_at=datetime.now() + timedelta(seconds=window),
                )
            else:
                logger.error(
                    f"Rate limiter failing closed due to Redis error for {identifier}"
                )
                return RateLimitResult(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    reset_at=datetime.now() + timedelta(seconds=window),
                    retry_after=60,
                )

        except Exception as e:
            logger.error(f"Unexpected error in rate limiter: {e}", exc_info=True)

            # Fail open for unexpected errors
            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=limit,
                reset_at=datetime.now() + timedelta(seconds=window),
            )

    def _block_client(self, identifier: str, duration: int) -> None:
        """
        Temporarily block a client for abuse.

        Args:
            identifier: Client identifier
            duration: Block duration in seconds
        """
        try:
            block_key = self._get_block_key(identifier)
            block_until = int(time.time()) + duration
            self.redis.setex(block_key, duration, str(block_until))
            logger.warning(f"Blocked {identifier} for {duration}s")
        except RedisError as e:
            logger.error(f"Failed to block client: {e}")

    async def reset_limit(self, identifier: str, window: int) -> bool:
        """
        Reset rate limit for an identifier (admin action).

        Args:
            identifier: Client identifier
            window: Window to reset

        Returns:
            True if successful
        """
        try:
            key = self._get_key(identifier, window)
            self.redis.delete(key)
            logger.info(f"Reset rate limit for {identifier} (window: {window}s)")
            return True
        except RedisError as e:
            logger.error(f"Failed to reset rate limit: {e}")
            return False

    async def unblock_client(self, identifier: str) -> bool:
        """
        Unblock a client (admin action).

        Args:
            identifier: Client identifier

        Returns:
            True if successful
        """
        try:
            block_key = self._get_block_key(identifier)
            self.redis.delete(block_key)
            logger.info(f"Unblocked {identifier}")
            return True
        except RedisError as e:
            logger.error(f"Failed to unblock client: {e}")
            return False

    async def get_stats(self, identifier: str, window: int) -> Dict[str, Any]:
        """
        Get rate limit statistics for an identifier.

        Args:
            identifier: Client identifier
            window: Time window

        Returns:
            Dictionary with stats
        """
        try:
            key = self._get_key(identifier, window)
            current_time = time.time()
            window_start = current_time - window

            # Get all timestamps in current window
            timestamps = self.redis.zrangebyscore(key, window_start, current_time)

            return {
                "identifier": identifier,
                "window": window,
                "current_count": len(timestamps),
                "timestamps": [float(ts) for ts in timestamps],
                "window_start": window_start,
                "window_end": current_time,
            }
        except RedisError as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}


# Export public API
__all__ = [
    "RateLimitTier",
    "RateLimitConfig",
    "RateLimitResult",
    "DistributedRateLimiter",
]
