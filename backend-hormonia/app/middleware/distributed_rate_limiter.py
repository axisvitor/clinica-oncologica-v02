"""
Distributed Rate Limiter Middleware for FastAPI.

CRITICAL FIX #4: Implement distributed rate limiting to prevent throttling issues
across multiple workers.

This module provides the FastAPI middleware wrapper (RateLimitMiddleware) that
integrates the core distributed rate limiter into the request pipeline.

Core rate limiting logic (sliding window algorithm, data classes, and the
DistributedRateLimiter class) lives in app.middleware.rate_limit_core.

Features:
- Per-IP, per-user, and per-endpoint limits via tiers
- Priority lanes for authenticated users
- Automatic key expiration
- Graceful degradation if Redis unavailable

Usage:
    from app.middleware.distributed_rate_limiter import RateLimitMiddleware

    app.add_middleware(
        RateLimitMiddleware,
        redis=redis_client,
        default_limit=100,
        default_window=60,
    )
"""

import logging
import inspect
import time
from typing import Optional, Dict, Any

from redis import Redis
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse

from app.middleware.rate_limit_core import (
    RateLimitTier,
    RateLimitConfig,
    RateLimitResult,
    DistributedRateLimiter as CoreDistributedRateLimiter,
)
from app.utils.client_ip import get_client_ip, hash_sensitive_identifier, rate_limit_log_extra

logger = logging.getLogger(__name__)


class _NoopMetric:
    """No-op Prometheus-like metric for compatibility in tests."""

    def labels(self, **_kwargs):
        return self

    def inc(self, _value: float = 1.0):
        return None


# Metric handles used by existing tests.
rate_limit_hits = _NoopMetric()
rate_limit_rejections = _NoopMetric()


class DistributedRateLimiter(CoreDistributedRateLimiter):
    """
    Wrapper around core DistributedRateLimiter.

    Supports constructor parameters used across the codebase:
    - DistributedRateLimiter(redis, ...)
    - DistributedRateLimiter(redis_client=..., max_requests=..., window_seconds=...)
    """

    def __init__(
        self,
        redis: Optional[Redis] = None,
        *,
        redis_client: Optional[Redis] = None,
        max_requests: int = 80,
        window_seconds: int = 60,
        **kwargs: Any,
    ):
        redis_backend = redis_client or redis
        if redis_backend is None:
            raise ValueError("A Redis client instance is required")

        kwargs.setdefault("fail_open", False)
        super().__init__(redis=redis_backend, **kwargs)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._key_prefix = "rate_limit"

    @staticmethod
    def _is_urgent_priority(priority: Any) -> bool:
        if priority is None:
            return False
        priority_name = str(getattr(priority, "name", priority)).upper()
        return priority_name in {"URGENT", "CRITICAL", "HIGH"}

    async def _maybe_await(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    async def acquire(self, priority: Any = None, identifier: str = "global") -> bool:
        """
        Acquire one token using a sliding-window counter.

        Reserve 20% of capacity for urgent/critical priorities.
        """
        try:
            key = f"{self._key_prefix}:{identifier}:{self.window_seconds}"
            current_time = time.time()
            window_start = current_time - self.window_seconds

            pipeline = self.redis.pipeline()
            pipeline.zremrangebyscore(key, 0, window_start)
            pipeline.zcard(key)
            pipeline.zadd(key, {str(current_time): current_time})
            pipeline.expire(key, self.window_seconds)
            result = await self._maybe_await(pipeline.execute())

            current_count = 0
            if isinstance(result, (list, tuple)) and len(result) > 1:
                current_count = int(result[1] or 0)

            is_urgent = self._is_urgent_priority(priority)
            reserved_capacity = int(self.max_requests * 0.20)
            effective_limit = (
                self.max_requests
                if is_urgent
                else max(1, self.max_requests - reserved_capacity)
            )

            if current_count < effective_limit:
                rate_limit_hits.inc()
                return True

            # At boundary (max-1) allow one optimistic pass to
            # avoid false negatives under concurrent workers.
            if not is_urgent and current_count == self.max_requests - 1:
                rate_limit_hits.inc()
                return True

            rate_limit_rejections.inc()
            return False
        except Exception as exc:
            if self.fail_open:
                logger.warning(
                    "acquire() Redis failure; allowing request (fail-open): %s", exc
                )
                rate_limit_hits.inc()
                return True

            logger.warning(
                "acquire() Redis failure; denying request (fail-closed): %s", exc,
                extra={"event_type": "rate_limit_denied", "reason": "redis_error", "scope": "acquire"},
            )
            rate_limit_rejections.inc()
            return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for distributed rate limiting.

    Usage:
        app.add_middleware(
            RateLimitMiddleware,
            redis=redis_client,
            default_limit=100,
            default_window=60,
        )
    """

    def __init__(
        self,
        app,
        redis: Redis,
        default_limit: int = 100,
        default_window: int = 60,
        tier_configs: Optional[Dict[RateLimitTier, RateLimitConfig]] = None,
        exempt_paths: Optional[list[str]] = None,
        whitelist_ips: Optional[list[str]] = None,
    ):
        """
        Initialize rate limit middleware.

        Args:
            app: FastAPI application
            redis: Redis client
            default_limit: Default request limit
            default_window: Default time window (seconds)
            tier_configs: Rate limit configs per tier
            exempt_paths: Paths exempt from rate limiting
            whitelist_ips: IPs exempt from rate limiting
        """
        super().__init__(app)
        self.rate_limiter = DistributedRateLimiter(redis)
        self.default_limit = default_limit
        self.default_window = default_window

        # Default tier configurations
        self.tier_configs = tier_configs or {
            RateLimitTier.PUBLIC: RateLimitConfig(
                requests=200,
                window=60,
                tier=RateLimitTier.PUBLIC,  # Quiz publico, health checks
            ),
            RateLimitTier.DOCTOR: RateLimitConfig(
                requests=1000,
                window=60,
                tier=RateLimitTier.DOCTOR,  # Medicos - operacoes clinicas
            ),
            RateLimitTier.ADMIN: RateLimitConfig(
                requests=10000,
                window=60,
                tier=RateLimitTier.ADMIN,  # Administradores - sem limitacao pratica
            ),
        }

        self.exempt_paths = exempt_paths or [
            "/health",
            "/metrics",
            "/docs",
            "/openapi.json",
            "/ws/connect",  # WebSocket connections
        ]
        self.whitelist_ips = set(
            whitelist_ips
            or [
                "127.0.0.1",
                "::1",
            ]
        )

    def _get_client_identifier(self, request: Request) -> str:
        """
        Get unique identifier for client.

        Args:
            request: FastAPI request

        Returns:
            Client identifier (IP or user ID)
        """
        # Try to get user ID if authenticated
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"user:{user_id}"

        # Fallback to IP address resolved through the shared trusted-proxy boundary.
        ip = get_client_ip(request)

        return f"ip:{ip}"

    def _get_rate_limit_tier(self, request: Request) -> RateLimitTier:
        """
        Determine rate limit tier for request.

        Args:
            request: FastAPI request

        Returns:
            Rate limit tier
        """
        # First check if user is in request.state (set by auth middleware)
        user = getattr(request.state, "user", None)
        if user:
            user_role = getattr(user, "role", None)
            if user_role == "admin":
                return RateLimitTier.ADMIN
            elif user_role == "premium":
                return RateLimitTier.PREMIUM
            else:
                return RateLimitTier.AUTHENTICATED

        # SECURITY FIX: Do NOT trust unverified JWT tokens for tier determination
        # JWT signature MUST be verified before trusting any claims
        # Admin tier should ONLY be granted via properly authenticated request.state.user
        # Removed: Unverified JWT decode that allowed rate limit bypass via forged tokens
        #
        # If authentication middleware has not set request.state.user, default to PUBLIC tier
        # This ensures rate limiting cannot be bypassed with forged JWTs

        return RateLimitTier.PUBLIC

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Middleware dispatch function.

        Args:
            request: Incoming request
            call_next: Next middleware/endpoint

        Returns:
            Response
        """
        # Skip rate limiting for OPTIONS preflight requests (CORS)
        # This ensures CORS middleware can handle preflights properly
        if request.method == "OPTIONS":
            return await call_next(request)

        # Check if path is exempt
        if any(request.url.path.startswith(path) for path in self.exempt_paths):
            return await call_next(request)

        # Check if resolved client IP is whitelisted (only explicit local/dev peers).
        # When behind a trusted proxy, this uses the forwarded client identity so a
        # localhost proxy does not exempt every external caller.
        client_ip = get_client_ip(request)
        if client_ip in self.whitelist_ips:
            return await call_next(request)

        # SECURITY FIX: Removed admin bypass backdoor
        # Previously allowed any request with "admin" in Authorization header to bypass rate limiting
        # This was a critical security vulnerability - attackers could bypass all rate limits

        # Get client identifier and tier
        identifier = self._get_client_identifier(request)
        tier = self._get_rate_limit_tier(request)
        config = self.tier_configs.get(tier)

        # Debug logging for admin detection
        if tier == RateLimitTier.ADMIN:
            logger.info(
                "Admin tier detected for rate limiting",
                extra={
                    "event_type": "rate_limit_tier",
                    "scope": "middleware",
                    "client_identity_hash": hash_sensitive_identifier(identifier, prefix="client"),
                    "route": request.url.path,
                },
            )
        # SECURITY FIX: Removed unsafe admin string detection
        # Admin tier must be determined by proper authentication via request.state.user

        if not config:
            config = RateLimitConfig(
                requests=self.default_limit,
                window=self.default_window,
                tier=tier,
            )

        # Check rate limit
        result = await self.rate_limiter.check_rate_limit(
            identifier=identifier,
            limit=config.requests,
            window=config.window,
            increment=True,
        )

        # Add rate limit headers
        response = None
        if result.allowed:
            response = await call_next(request)
        else:
            denial_reason = result.reason or "limit_exceeded"
            logger.warning(
                "Distributed rate limit denied",
                extra=rate_limit_log_extra(
                    request,
                    reason=denial_reason,
                    scope="middleware",
                    limit=result.limit,
                    window_seconds=config.window,
                    retry_after=result.retry_after,
                ),
            )
            response = JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Try again in {result.retry_after} seconds.",
                    "limit": result.limit,
                    "retry_after": result.retry_after,
                },
            )

        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(int(result.reset_at.timestamp()))

        if result.retry_after:
            response.headers["Retry-After"] = str(result.retry_after)

        return response


# Re-export all public names from this module.
__all__ = [
    "DistributedRateLimiter",
    "RateLimitMiddleware",
    "RateLimitTier",
    "RateLimitConfig",
    "RateLimitResult",
]
