"""
Rate Limiter Implementation

Advanced rate limiting with multiple strategies and graceful degradation.
"""

import time
import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Mapping, Optional

try:  # Optional Flask dependency
    from flask import request as flask_request, g as flask_g  # type: ignore
except ImportError:  # pragma: no cover - Flask not installed
    flask_request = None
    flask_g = SimpleNamespace()

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

    requests_per_second: float = 10.0  # Requests per second
    burst_size: int = 50  # Burst capacity
    strategy: RateLimitStrategy = RateLimitStrategy.PER_IP
    key_func: Optional[Callable] = None  # Custom key function
    skip_successful_requests: bool = False  # Only count failed requests
    skip_whitelisted: bool = True  # Skip whitelisted IPs/users
    whitelist: List[str] = None  # Whitelist of IPs/users

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
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(int(self.reset_time)),
        }

        if self.retry_after is not None:
            headers["Retry-After"] = str(int(self.retry_after))

        return headers


@dataclass
class RateLimitContext:
    """Framework-agnostic request data for rate limiting decisions."""

    client_ip: str = "unknown"
    user_id: Optional[str] = None
    endpoint: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


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

    def __init__(
        self,
        config: RateLimitConfig,
        bucket_manager: Optional[TokenBucketManager] = None,
        name: str = "default",
    ):
        self.config = config
        self.name = name
        self.bucket_manager = bucket_manager or TokenBucketManager()

        # Create token bucket config
        self.bucket_config = TokenBucketConfig(
            capacity=config.burst_size,
            refill_rate=config.requests_per_second,
            initial_tokens=config.burst_size,
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

    def check_rate_limit(
        self,
        key: Optional[str] = None,
        tokens: int = 1,
        context: Optional["RateLimitContext"] = None,
    ) -> RateLimitResult:
        """
        Check if request should be rate limited

        Args:
            key: Optional custom key (uses strategy to generate if None)
            tokens: Number of tokens to consume
            context: Optional request metadata used to derive rate limit keys

        Returns:
            RateLimitResult with decision and metadata
        """
        self._total_requests += 1

        # Generate bucket key
        bucket_id = key or self._generate_bucket_key(context=context)

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

    def _generate_bucket_key(self, context: Optional["RateLimitContext"] = None) -> str:
        """Generate bucket key based on strategy"""
        if self.config.strategy == RateLimitStrategy.CUSTOM:
            if self.config.key_func:
                try:
                    return self.config.key_func(context)
                except TypeError:
                    return self.config.key_func()
            raise ValueError("Custom strategy requires key_func")

        elif self.config.strategy == RateLimitStrategy.PER_IP:
            # Use client IP
            return f"ip_{self._get_client_ip(context)}"

        elif self.config.strategy == RateLimitStrategy.PER_USER:
            # Use user ID if available
            user_id = self._get_user_id(context)
            if user_id:
                return f"user_{user_id}"
            else:
                # Fallback to IP if no user
                return f"ip_{self._get_client_ip(context)}"

        elif self.config.strategy == RateLimitStrategy.PER_ENDPOINT:
            # Use endpoint + IP
            endpoint = self._get_endpoint(context)
            client_ip = self._get_client_ip(context)
            return f"endpoint_{endpoint}_{client_ip}"

        elif self.config.strategy == RateLimitStrategy.GLOBAL:
            # Global bucket
            return "global"

        else:
            raise ValueError(f"Unknown rate limit strategy: {self.config.strategy}")

    @staticmethod
    def _extract_from_context(
        context: Optional["RateLimitContext"], *keys: str
    ) -> Optional[Any]:
        """Safely extract attribute from multiple context styles."""
        if context is None:
            return None

        sources = [context]

        if isinstance(context, RateLimitContext):
            sources.append(context.metadata)

        extra_source = None
        if isinstance(context, Mapping):
            extra_source = context.get("extra")
        elif hasattr(context, "extra"):
            extra_source = getattr(context, "extra")

        if isinstance(extra_source, Mapping):
            sources.append(extra_source)

        for source in sources:
            for key in keys:
                value = None
                if isinstance(source, Mapping):
                    value = source.get(key)
                if value is None and hasattr(source, key):
                    value = getattr(source, key)
                if value is not None:
                    return value

        return None

    def _resolve_request_object(
        self, context: Optional["RateLimitContext"]
    ) -> Optional[Any]:
        """Return the best available request object."""
        request_obj = self._extract_from_context(context, "request")
        if request_obj is not None:
            return request_obj
        return flask_request

    def _resolve_headers(self, context: Optional["RateLimitContext"]) -> Optional[Any]:
        """Return headers from context or request if available."""
        headers = self._extract_from_context(context, "headers")
        if headers is not None:
            return headers

        request_obj = self._resolve_request_object(context)
        if request_obj and hasattr(request_obj, "headers"):
            return getattr(request_obj, "headers")

        return None

    @staticmethod
    def _get_header_value(headers: Optional[Any], key: str) -> Optional[str]:
        """Case-insensitive header access."""
        if headers is None:
            return None

        getter = getattr(headers, "get", None)
        if callable(getter):
            value = getter(key)
            if value is None:
                value = getter(key.lower())
            return value

        if isinstance(headers, Mapping):
            return headers.get(key) or headers.get(key.lower())

        return None

    @staticmethod
    def _hash_path(path: str) -> str:
        """Hashes path to create compact bucket identifiers."""
        path_hash = hashlib.md5(path.encode()).hexdigest()[:8]
        return f"path_{path_hash}"

    @staticmethod
    def _format_endpoint(endpoint: Any) -> str:
        """Return a string identifier for the endpoint."""
        if isinstance(endpoint, str):
            return endpoint

        if callable(endpoint):
            return getattr(endpoint, "__name__", str(endpoint))

        return str(endpoint)

    def _get_client_ip(self, context: Optional["RateLimitContext"] = None) -> str:
        """Get client IP address"""
        ip = self._extract_from_context(context, "client_ip", "ip", "remote_addr")
        if ip:
            ip_str = str(ip)
            if ip_str.lower() != "unknown":
                return ip_str

        headers = self._resolve_headers(context)
        forwarded_for = self._get_header_value(headers, "X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = self._get_header_value(headers, "X-Real-IP")
        if real_ip:
            return real_ip

        request_obj = self._resolve_request_object(context)
        if request_obj:
            client = getattr(request_obj, "client", None)
            if client:
                host = getattr(client, "host", None)
                if host:
                    return host

            if hasattr(request_obj, "remote_addr"):
                remote_addr = getattr(request_obj, "remote_addr")
                if remote_addr:
                    return remote_addr

        return "unknown"

    def _get_user_id(
        self, context: Optional["RateLimitContext"] = None
    ) -> Optional[str]:
        """Get user ID from request context"""
        user_id = self._extract_from_context(context, "user_id")
        if user_id:
            return str(user_id)

        user_obj = self._extract_from_context(context, "user")
        state = self._extract_from_context(context, "state")

        candidates = [user_obj]
        if state is not None:
            candidates.append(getattr(state, "user", None))
            state_user_id = getattr(state, "user_id", None)
            if state_user_id:
                return str(state_user_id)

        for candidate in candidates:
            if candidate is None:
                continue

            candidate_id = getattr(candidate, "id", None)
            if candidate_id is not None:
                return str(candidate_id)

            get_id = getattr(candidate, "get_id", None)
            if callable(get_id):
                user_value = get_id()
                if user_value:
                    return str(user_value)

        flask_user = getattr(flask_g, "current_user", None)
        if flask_user:
            flask_id = getattr(flask_user, "id", None)
            if flask_id is not None:
                return str(flask_id)

            flask_get_id = getattr(flask_user, "get_id", None)
            if callable(flask_get_id):
                user_value = flask_get_id()
                if user_value:
                    return str(user_value)

        flask_user_id = getattr(flask_g, "user_id", None)
        if flask_user_id is not None:
            return str(flask_user_id)

        return None

    def _get_endpoint(self, context: Optional["RateLimitContext"] = None) -> str:
        """Get endpoint identifier"""
        endpoint = self._extract_from_context(context, "endpoint")
        if endpoint:
            return self._format_endpoint(endpoint)

        path = self._extract_from_context(context, "path")
        if path:
            return self._hash_path(str(path))

        request_obj = self._resolve_request_object(context)
        if request_obj:
            endpoint_attr = getattr(request_obj, "endpoint", None)
            if endpoint_attr:
                return self._format_endpoint(endpoint_attr)

            scope = getattr(request_obj, "scope", None)
            if isinstance(scope, Mapping):
                scope_endpoint = scope.get("endpoint")
                if scope_endpoint:
                    return self._format_endpoint(scope_endpoint)

            request_path = getattr(request_obj, "path", None)
            if request_path:
                return self._hash_path(str(request_path))

            url = getattr(request_obj, "url", None)
            if url:
                try:
                    return self._hash_path(str(url.path))
                except Exception as e:
                    logger.warning(f"Failed to hash URL path: {e}", exc_info=True)

        return "unknown"

    def _is_whitelisted(self, bucket_id: str) -> bool:
        """Check if bucket_id is whitelisted"""
        if not self.config.skip_whitelisted or not self.config.whitelist:
            return False

        # Check against whitelist patterns
        for pattern in self.config.whitelist:
            if pattern in bucket_id or bucket_id.endswith(pattern):
                return True

        return False

    def _create_allowed_result(
        self, bucket_id: str, tokens: int, bucket: Optional[TokenBucket] = None
    ) -> RateLimitResult:
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
            strategy=self.config.strategy.value,
        )

    def _create_denied_result(
        self, bucket_id: str, tokens: int, bucket: TokenBucket
    ) -> RateLimitResult:
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
            strategy=self.config.strategy.value,
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Get rate limiter metrics"""
        bucket_metrics = self.bucket_manager.get_all_metrics()

        success_rate = self._allowed_requests / max(1, self._total_requests)

        return {
            "name": self.name,
            "strategy": self.config.strategy.value,
            "requests_per_second": self.config.requests_per_second,
            "burst_size": self.config.burst_size,
            "total_requests": self._total_requests,
            "allowed_requests": self._allowed_requests,
            "denied_requests": self._denied_requests,
            "whitelisted_requests": self._whitelisted_requests,
            "success_rate": success_rate,
            "bucket_metrics": bucket_metrics,
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

        logger.info(
            f"Added rate limit tier '{tier_name}': {config.requests_per_second}/s"
        )

    def set_user_tier(self, user_id: str, tier: str):
        """Set tier for specific user"""
        self._tier_mapping[user_id] = tier
        logger.debug(f"Set user {user_id} to tier '{tier}'")

    def get_user_tier(self, user_id: Optional[str] = None) -> str:
        """Get tier for user"""
        if user_id and user_id in self._tier_mapping:
            return self._tier_mapping[user_id]
        return self.default_tier

    def check_rate_limit(
        self, user_id: Optional[str] = None, tokens: int = 1
    ) -> RateLimitResult:
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
            "default_tier": self.default_tier,
            "total_tiers": len(self._limiters),
            "user_mappings": len(self._tier_mapping),
            "tiers": {},
        }

        for tier_name, limiter in self._limiters.items():
            metrics["tiers"][tier_name] = limiter.get_metrics()

        return metrics
