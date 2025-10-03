"""
Rate Limiter Implementation

Advanced rate limiting with multiple strategies and graceful degradation.
"""

import time
import hashlib
from typing import Dict, Optional, Any, Callable, List
from dataclasses import dataclass
from enum import Enum
from flask import request, g
import logging

from .token_bucket import TokenBucket, TokenBucketConfig, TokenBucketManager

logger = logging.getLogger(__name__)


class RateLimitStrategy(Enum):
    """Rate limiting strategies"""
    PER_IP = "per_ip"
    PER_USER = "per_user"
    PER_ENDPOINT = "per_endpoint"
    GLOBAL = "global"
    CUSTOM = "custom"


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    requests_per_second: float = 10.0    # Requests per second
    burst_size: int = 50                 # Burst capacity
    strategy: RateLimitStrategy = RateLimitStrategy.PER_IP
    key_func: Optional[Callable] = None  # Custom key function
    skip_successful_requests: bool = False  # Only count failed requests
    skip_whitelisted: bool = True        # Skip whitelisted IPs/users
    whitelist: List[str] = None          # Whitelist of IPs/users

    def __post_init__(self):
        if self.whitelist is None:
            self.whitelist = []


@dataclass
class RateLimitResult:
    """Rate limit check result"""
    allowed: bool
    limit: int
    remaining: int
    reset_time: float
    retry_after: Optional[float] = None
    bucket_id: str = ""
    strategy: str = ""

    @property
    def headers(self) -> Dict[str, str]:
        """Get rate limit headers for HTTP response"""
        headers = {
            'X-RateLimit-Limit': str(self.limit),
            'X-RateLimit-Remaining': str(self.remaining),
            'X-RateLimit-Reset': str(int(self.reset_time))
        }

        if self.retry_after is not None:
            headers['Retry-After'] = str(int(self.retry_after))

        return headers


class RateLimiter:
    """
    Advanced rate limiter with multiple strategies

    Features:
    - Multiple rate limiting strategies
    - Token bucket algorithm
    - Graceful degradation
    - Whitelist support
    - Custom key functions
    - Comprehensive metrics
    """

    def __init__(self,
                 config: RateLimitConfig,
                 bucket_manager: Optional[TokenBucketManager] = None,
                 name: str = "default"):
        self.config = config
        self.name = name
        self.bucket_manager = bucket_manager or TokenBucketManager()

        # Create token bucket config
        self.bucket_config = TokenBucketConfig(
            capacity=config.burst_size,
            refill_rate=config.requests_per_second,
            initial_tokens=config.burst_size
        )

        # Metrics
        self._total_requests = 0
        self._allowed_requests = 0
        self._denied_requests = 0
        self._whitelisted_requests = 0

        logger.info(
            f"Rate limiter '{name}' initialized "
            f"({config.requests_per_second}/s, burst={config.burst_size}, "
            f"strategy={config.strategy.value})"
        )

    def check_rate_limit(self,
                        key: Optional[str] = None,
                        tokens: int = 1) -> RateLimitResult:
        """
        Check if request should be rate limited

        Args:
            key: Optional custom key (uses strategy to generate if None)
            tokens: Number of tokens to consume

        Returns:
            RateLimitResult with decision and metadata
        """
        self._total_requests += 1

        # Generate bucket key
        bucket_id = key or self._generate_bucket_key()

        # Check whitelist
        if self._is_whitelisted(bucket_id):
            self._whitelisted_requests += 1
            return self._create_allowed_result(bucket_id, tokens)

        # Get or create bucket
        bucket = self.bucket_manager.get_bucket(bucket_id, self.bucket_config)

        # Try to consume tokens
        allowed = bucket.consume(tokens)

        if allowed:
            self._allowed_requests += 1
            result = self._create_allowed_result(bucket_id, tokens, bucket)
        else:
            self._denied_requests += 1
            result = self._create_denied_result(bucket_id, tokens, bucket)

        logger.debug(
            f"Rate limit check for '{bucket_id}': "
            f"{'allowed' if allowed else 'denied'} "
            f"(tokens={tokens}, strategy={self.config.strategy.value})"
        )

        return result

    def _generate_bucket_key(self) -> str:
        """Generate bucket key based on strategy"""
        if self.config.strategy == RateLimitStrategy.CUSTOM:
            if self.config.key_func:
                return self.config.key_func()
            else:
                raise ValueError("Custom strategy requires key_func")

        elif self.config.strategy == RateLimitStrategy.PER_IP:
            # Use client IP
            return self._get_client_ip()

        elif self.config.strategy == RateLimitStrategy.PER_USER:
            # Use user ID if available
            user_id = self._get_user_id()
            if user_id:
                return f"user_{user_id}"
            else:
                # Fallback to IP if no user
                return f"ip_{self._get_client_ip()}"

        elif self.config.strategy == RateLimitStrategy.PER_ENDPOINT:
            # Use endpoint + IP
            endpoint = self._get_endpoint()
            client_ip = self._get_client_ip()
            return f"endpoint_{endpoint}_{client_ip}"

        elif self.config.strategy == RateLimitStrategy.GLOBAL:
            # Global bucket
            return "global"

        else:
            raise ValueError(f"Unknown rate limit strategy: {self.config.strategy}")

    def _get_client_ip(self) -> str:
        """Get client IP address"""
        try:
            # Try to get real IP from headers (behind proxy)
            if hasattr(request, 'headers'):
                forwarded_for = request.headers.get('X-Forwarded-For')
                if forwarded_for:
                    return forwarded_for.split(',')[0].strip()

                real_ip = request.headers.get('X-Real-IP')
                if real_ip:
                    return real_ip

            # Fallback to remote address
            if hasattr(request, 'remote_addr'):
                return request.remote_addr or 'unknown'

        except Exception:
            pass

        return 'unknown'

    def _get_user_id(self) -> Optional[str]:
        """Get user ID from request context"""
        try:
            # Try to get from Flask g object
            if hasattr(g, 'current_user') and g.current_user:
                if hasattr(g.current_user, 'id'):
                    return str(g.current_user.id)
                elif hasattr(g.current_user, 'get_id'):
                    return str(g.current_user.get_id())

            # Try to get from JWT token or session
            if hasattr(g, 'user_id'):
                return str(g.user_id)

        except Exception:
            pass

        return None

    def _get_endpoint(self) -> str:
        """Get endpoint identifier"""
        try:
            if hasattr(request, 'endpoint'):
                return request.endpoint or 'unknown'

            if hasattr(request, 'path'):
                # Create hash of path to avoid long keys
                path_hash = hashlib.md5(request.path.encode()).hexdigest()[:8]
                return f"path_{path_hash}"

        except Exception:
            pass

        return 'unknown'

    def _is_whitelisted(self, bucket_id: str) -> bool:
        """Check if bucket_id is whitelisted"""
        if not self.config.skip_whitelisted or not self.config.whitelist:
            return False

        # Check against whitelist patterns
        for pattern in self.config.whitelist:
            if pattern in bucket_id or bucket_id.endswith(pattern):
                return True

        return False

    def _create_allowed_result(self,
                              bucket_id: str,
                              tokens: int,
                              bucket: Optional[TokenBucket] = None) -> RateLimitResult:
        """Create result for allowed request"""
        if bucket:
            remaining = int(bucket.peek())
            reset_time = time.time() + 60  # Approximate reset time
        else:
            # Whitelisted
            remaining = self.config.burst_size
            reset_time = time.time() + 60

        return RateLimitResult(
            allowed=True,
            limit=self.config.burst_size,
            remaining=remaining,
            reset_time=reset_time,
            bucket_id=bucket_id,
            strategy=self.config.strategy.value
        )

    def _create_denied_result(self,
                             bucket_id: str,
                             tokens: int,
                             bucket: TokenBucket) -> RateLimitResult:
        """Create result for denied request"""
        remaining = int(bucket.peek())
        retry_after = bucket.time_until_tokens(tokens)
        reset_time = time.time() + retry_after

        return RateLimitResult(
            allowed=False,
            limit=self.config.burst_size,
            remaining=remaining,
            reset_time=reset_time,
            retry_after=retry_after,
            bucket_id=bucket_id,
            strategy=self.config.strategy.value
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Get rate limiter metrics"""
        bucket_metrics = self.bucket_manager.get_all_metrics()

        success_rate = (
            self._allowed_requests / max(1, self._total_requests)
        )

        return {
            'name': self.name,
            'strategy': self.config.strategy.value,
            'requests_per_second': self.config.requests_per_second,
            'burst_size': self.config.burst_size,
            'total_requests': self._total_requests,
            'allowed_requests': self._allowed_requests,
            'denied_requests': self._denied_requests,
            'whitelisted_requests': self._whitelisted_requests,
            'success_rate': success_rate,
            'bucket_metrics': bucket_metrics
        }

    def reset_metrics(self):
        """Reset metrics"""
        self._total_requests = 0
        self._allowed_requests = 0
        self._denied_requests = 0
        self._whitelisted_requests = 0

        logger.info(f"Rate limiter '{self.name}' metrics reset")


class MultiTierRateLimiter:
    """
    Multi-tier rate limiter with different limits for different user types

    Features:
    - Multiple rate limit tiers
    - User type detection
    - Fallback limits
    - Tier-specific configurations
    """

    def __init__(self, default_tier: str = "basic"):
        self.default_tier = default_tier
        self._limiters: Dict[str, RateLimiter] = {}
        self._tier_mapping: Dict[str, str] = {}  # user_id -> tier

        logger.info(f"Multi-tier rate limiter initialized (default: {default_tier})")

    def add_tier(self, tier_name: str, config: RateLimitConfig):
        """Add rate limit tier"""
        limiter = RateLimiter(config, name=f"tier_{tier_name}")
        self._limiters[tier_name] = limiter

        logger.info(f"Added rate limit tier '{tier_name}': {config.requests_per_second}/s")

    def set_user_tier(self, user_id: str, tier: str):
        """Set tier for specific user"""
        self._tier_mapping[user_id] = tier
        logger.debug(f"Set user {user_id} to tier '{tier}'")

    def get_user_tier(self, user_id: Optional[str] = None) -> str:
        """Get tier for user"""
        if user_id and user_id in self._tier_mapping:
            return self._tier_mapping[user_id]
        return self.default_tier

    def check_rate_limit(self,
                        user_id: Optional[str] = None,
                        tokens: int = 1) -> RateLimitResult:
        """Check rate limit for user's tier"""
        tier = self.get_user_tier(user_id)

        if tier not in self._limiters:
            # Fallback to default tier
            tier = self.default_tier

        if tier not in self._limiters:
            raise ValueError(f"No rate limiter configured for tier '{tier}'")

        limiter = self._limiters[tier]
        result = limiter.check_rate_limit(tokens=tokens)

        # Add tier info to result
        result.strategy = f"tier_{tier}"

        return result

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get metrics for all tiers"""
        metrics = {
            'default_tier': self.default_tier,
            'total_tiers': len(self._limiters),
            'user_mappings': len(self._tier_mapping),
            'tiers': {}
        }

        for tier_name, limiter in self._limiters.items():
            metrics['tiers'][tier_name] = limiter.get_metrics()

        return metrics