"""
Rate limiting middleware for API endpoints.
"""
import time
import logging
from typing import Dict, Optional, Tuple
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter implementation.
    """
    
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
    
    def is_allowed(self, key: str) -> Tuple[bool, Optional[int]]:
        """
        Check if request is allowed.
        
        Args:
            key: Unique identifier for rate limiting (e.g., IP address, user ID)
            
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
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
        "default": (60, 60)  # 60 requests per minute default
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
                    "retry_after": retry_after
                },
                headers={"Retry-After": str(retry_after)}
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limiter.rate)
        response.headers["X-RateLimit-Remaining"] = str(int(limiter.allowance[client_id]))
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
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        
        return f"ip:{client_ip}"
    
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
            "allowance": self.allowance[key]
        }