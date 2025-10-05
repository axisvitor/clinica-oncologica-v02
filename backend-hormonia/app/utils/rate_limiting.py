"""
Rate limiting utilities for API endpoints.

This module provides Redis-based distributed rate limiting with automatic fallback
to in-memory storage when Redis is unavailable.

Uses the unified RedisManager (app.core.redis_unified) for all Redis connections,
ensuring consistent SSL/TLS configuration and connection pooling.

⚠️ IMPORTANT: When Redis is not available, rate limiting falls back to in-memory storage
   with the same limitations as documented in Backend/docs/RATE_LIMITING.md:
   - Counters lost on server restart
   - Not suitable for multi-instance deployments
   - No cross-service coordination

For production use, ensure Redis is configured via REDIS_URL environment variable.

See: Backend/docs/RATE_LIMITING.md for complete documentation and migration guide.
"""
import time
import asyncio
from typing import List, Optional, Tuple
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum

import redis.asyncio as redis
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer

from app.core.redis_unified import get_async_redis
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RateLimitType(str, Enum):
    """Rate limit types for different endpoint categories."""
    AUTH = "auth"
    READ = "read"
    WRITE = "write"
    WEBHOOK = "webhook"
    UPLOAD = "upload"


@dataclass
class RateLimit:
    """Rate limit configuration."""
    calls: int
    period: int  # seconds
    burst: Optional[int] = None  # burst allowance


# Rate limit configurations
RATE_LIMITS = {
    RateLimitType.AUTH: RateLimit(calls=5, period=60, burst=2),  # 5 per minute, 2 burst
    RateLimitType.READ: RateLimit(calls=100, period=60, burst=20),  # 100 per minute, 20 burst
    RateLimitType.WRITE: RateLimit(calls=50, period=60, burst=10),  # 50 per minute, 10 burst
    RateLimitType.WEBHOOK: RateLimit(calls=1000, period=60, burst=100),  # 1000 per minute, 100 burst
    RateLimitType.UPLOAD: RateLimit(calls=10, period=60, burst=3),  # 10 per minute, 3 burst
}


class RateLimiter:
    """Redis-based distributed rate limiter with sliding window."""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self._local_cache: dict[str, deque] = defaultdict(deque)
        self._cache_lock = asyncio.Lock()
    
    async def _get_redis_client(self) -> Optional[redis.Redis]:
        """Get Redis client if available via unified RedisManager."""
        if self.redis_client:
            return self.redis_client

        try:
            # Use unified RedisManager - handles SSL/TLS configuration automatically
            client = await get_async_redis()
            await client.ping()
            return client
        except Exception as e:
            logger.warning(f"Redis not available for rate limiting: {e}")
            return None
    
    async def is_allowed(
        self,
        key: str,
        rate_limit: RateLimit,
        current_time: Optional[float] = None
    ) -> Tuple[bool, dict[str, int]]:
        """
        Check if request is allowed under rate limit.
        
        Returns:
            Tuple of (is_allowed, headers_dict)
        """
        if current_time is None:
            current_time = time.time()
        
        redis_client = await self._get_redis_client()
        
        if redis_client:
            return await self._check_redis_rate_limit(
                redis_client, key, rate_limit, current_time
            )
        else:
            return await self._check_local_rate_limit(
                key, rate_limit, current_time
            )
    
    async def _check_redis_rate_limit(
        self,
        redis_client: redis.Redis,
        key: str,
        rate_limit: RateLimit,
        current_time: float
    ) -> Tuple[bool, dict[str, int]]:
        """Check rate limit using Redis sliding window."""
        window_start = current_time - rate_limit.period
        
        try:
            # Use Redis pipeline for atomic operations
            pipe = redis_client.pipeline()
            
            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(current_time): current_time})
            
            # Set expiration
            pipe.expire(key, rate_limit.period + 1)
            
            results = await pipe.execute()
            current_count = results[1]
            
            # Check if limit exceeded
            is_allowed = current_count < rate_limit.calls
            
            # Calculate headers
            remaining = max(0, rate_limit.calls - current_count - 1)
            reset_time = int(current_time + rate_limit.period)
            
            headers = {
                "X-RateLimit-Limit": rate_limit.calls,
                "X-RateLimit-Remaining": remaining,
                "X-RateLimit-Reset": reset_time,
                "X-RateLimit-Window": rate_limit.period
            }
            
            if not is_allowed:
                # Remove the request we just added since it's not allowed
                await redis_client.zrem(key, str(current_time))
                
                logger.warning(
                    f"Rate limit exceeded for key: {key}",
                    extra={
                        'event_type': 'rate_limit_exceeded',
                        'key': key,
                        'current_count': current_count,
                        'limit': rate_limit.calls,
                        'period': rate_limit.period
                    }
                )
            
            return is_allowed, headers
            
        except Exception as e:
            logger.error(f"Redis rate limiting error: {e}")
            # Fallback to local rate limiting
            return await self._check_local_rate_limit(key, rate_limit, current_time)
    
    async def _check_local_rate_limit(
        self,
        key: str,
        rate_limit: RateLimit,
        current_time: float
    ) -> Tuple[bool, dict[str, int]]:
        """Check rate limit using local memory (fallback)."""
        async with self._cache_lock:
            window_start = current_time - rate_limit.period
            
            # Clean old entries
            while (self._local_cache[key] and 
                   self._local_cache[key][0] < window_start):
                self._local_cache[key].popleft()
            
            current_count = len(self._local_cache[key])
            is_allowed = current_count < rate_limit.calls
            
            if is_allowed:
                self._local_cache[key].append(current_time)
            
            # Calculate headers
            remaining = max(0, rate_limit.calls - current_count - (1 if is_allowed else 0))
            reset_time = int(current_time + rate_limit.period)
            
            headers = {
                "X-RateLimit-Limit": rate_limit.calls,
                "X-RateLimit-Remaining": remaining,
                "X-RateLimit-Reset": reset_time,
                "X-RateLimit-Window": rate_limit.period
            }
            
            if not is_allowed:
                logger.warning(
                    f"Rate limit exceeded for key: {key} (local cache)",
                    extra={
                        'event_type': 'rate_limit_exceeded',
                        'key': key,
                        'current_count': current_count,
                        'limit': rate_limit.calls,
                        'period': rate_limit.period
                    }
                )
            
            return is_allowed, headers


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def get_client_identifier(request: Request) -> str:
    """Extract client identifier for rate limiting."""
    # Try to get user ID from request state (if authenticated)
    user_id = getattr(request.state, 'user_id', None)
    if user_id:
        return f"user:{user_id}"
    
    # Fall back to IP address
    client_ip = request.headers.get('X-Forwarded-For')
    if client_ip:
        client_ip = client_ip.split(',')[0].strip()
    else:
        client_ip = request.headers.get('X-Real-IP')
        if not client_ip:
            client_ip = request.client.host if request.client else 'unknown'
    
    return f"ip:{client_ip}"


async def check_rate_limit(
    request: Request,
    rate_limit_type: RateLimitType
) -> dict[str, int]:
    """
    Check rate limit for request.
    
    Raises HTTPException if rate limit exceeded.
    Returns headers to be added to response.
    """
    rate_limit = RATE_LIMITS[rate_limit_type]
    client_id = get_client_identifier(request)
    key = f"rate_limit:{rate_limit_type.value}:{client_id}"
    
    rate_limiter = get_rate_limiter()
    is_allowed, headers = await rate_limiter.is_allowed(key, rate_limit)
    
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"Rate limit exceeded for {rate_limit_type.value} operations",
                "retry_after": headers["X-RateLimit-Reset"] - int(time.time())
            },
            headers=headers
        )
    
    return headers


def rate_limit(rate_limit_type: RateLimitType):
    """Decorator for applying rate limits to endpoints."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Find request object in arguments
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if request is None:
                # Try to find in kwargs
                request = kwargs.get('request')
            
            if request is None:
                logger.warning("Rate limit decorator: Request object not found")
                return await func(*args, **kwargs)
            
            # Check rate limit
            headers = await check_rate_limit(request, rate_limit_type)
            
            # Call original function
            response = await func(*args, **kwargs)
            
            # Add rate limit headers to response
            if hasattr(response, 'headers'):
                for key, value in headers.items():
                    response.headers[key] = str(value)
            
            return response
        
        return wrapper
    return decorator