"""
Rate Limiting Middleware

Flask middleware for automatic rate limiting.
"""

import time
from typing import Optional, Dict, Any, List
from flask import Flask, request, jsonify, g
import logging

from .rate_limiter import RateLimiter, RateLimitConfig, RateLimitStrategy, MultiTierRateLimiter

logger = logging.getLogger(__name__)


class RateLimitMiddleware:
    """
    Flask middleware for automatic rate limiting

    Features:
    - Automatic rate limiting for all routes
    - Configurable per-route limits
    - User tier support
    - Graceful degradation
    - Comprehensive logging
    """

    def __init__(self,
                 app: Optional[Flask] = None,
                 default_config: Optional[RateLimitConfig] = None,
                 enabled: bool = True):
        self.enabled = enabled
        self.default_config = default_config or RateLimitConfig(
            requests_per_second=10.0,
            burst_size=50,
            strategy=RateLimitStrategy.PER_IP
        )

        # Route-specific configurations
        self._route_configs: Dict[str, RateLimitConfig] = {}

        # Multi-tier limiter
        self.multi_tier_limiter = MultiTierRateLimiter()

        # Global limiter
        self.global_limiter = RateLimiter(
            RateLimitConfig(
                requests_per_second=1000.0,
                burst_size=2000,
                strategy=RateLimitStrategy.GLOBAL
            ),
            name="global_middleware"
        )

        # Metrics
        self._total_requests = 0
        self._rate_limited_requests = 0
        self._bypassed_requests = 0

        if app:
            self.init_app(app)

        logger.info(f"Rate limit middleware initialized (enabled={enabled})")

    def init_app(self, app: Flask):
        """Initialize middleware with Flask app"""
        if not self.enabled:
            return

        # Register before_request handler
        app.before_request(self._before_request)

        # Store reference in app
        app.rate_limit_middleware = self

        logger.info("Rate limit middleware registered with Flask app")

    def _before_request(self):
        """Before request handler for rate limiting"""
        if not self.enabled:
            return

        self._total_requests += 1
        start_time = time.time()

        try:
            # Check if route should be bypassed
            if self._should_bypass_route():
                self._bypassed_requests += 1
                return

            # Check global rate limit first
            global_result = self.global_limiter.check_rate_limit()
            if not global_result.allowed:
                logger.warning(
                    f"Global rate limit exceeded: {request.remote_addr} "
                    f"-> {request.endpoint}"
                )
                return self._create_rate_limit_response(global_result, "Global rate limit exceeded")

            # Get route-specific configuration
            route_config = self._get_route_config()

            # Create route-specific limiter
            route_limiter = RateLimiter(route_config, name=f"route_{request.endpoint}")

            # Check route-specific rate limit
            route_result = route_limiter.check_rate_limit()

            if not route_result.allowed:
                self._rate_limited_requests += 1

                logger.info(
                    f"Rate limit exceeded: {route_result.bucket_id} "
                    f"-> {request.endpoint} "
                    f"(strategy={route_result.strategy})"
                )

                return self._create_rate_limit_response(route_result)

            # Store rate limit info for response headers
            g.rate_limit_result = route_result

            # Log successful rate limit check
            duration = (time.time() - start_time) * 1000
            logger.debug(
                f"Rate limit check passed: {route_result.bucket_id} "
                f"-> {request.endpoint} ({duration:.1f}ms)"
            )

        except Exception as e:
            logger.error(f"Rate limit middleware error: {str(e)}")
            # Don't block requests on middleware errors
            return

    def _should_bypass_route(self) -> bool:
        """Check if current route should bypass rate limiting"""
        # Bypass health checks and static files
        bypass_patterns = [
            '/health',
            '/static',
            '/favicon.ico',
            '/_debug'
        ]

        request_path = getattr(request, 'path', '')

        for pattern in bypass_patterns:
            if request_path.startswith(pattern):
                return True

        return False

    def _get_route_config(self) -> RateLimitConfig:
        """Get configuration for current route"""
        endpoint = getattr(request, 'endpoint', '')

        # Check for route-specific config
        if endpoint in self._route_configs:
            return self._route_configs[endpoint]

        # Use default config
        return self.default_config

    def _create_rate_limit_response(self,
                                   result,
                                   custom_message: Optional[str] = None):
        """Create rate limit response"""
        message = custom_message or "Rate limit exceeded"

        response_data = {
            'error': message,
            'rate_limit': {
                'limit': result.limit,
                'remaining': result.remaining,
                'reset_time': result.reset_time,
                'retry_after': result.retry_after,
                'strategy': result.strategy
            }
        }

        response = jsonify(response_data)
        response.status_code = 429

        # Add rate limit headers
        for header, value in result.headers.items():
            response.headers[header] = value

        return response

    def configure_route(self, endpoint: str, config: RateLimitConfig):
        """Configure rate limiting for specific route"""
        self._route_configs[endpoint] = config
        logger.info(f"Configured rate limit for route '{endpoint}': {config.requests_per_second}/s")

    def configure_user_tier(self, user_id: str, tier: str):
        """Configure user tier for multi-tier rate limiting"""
        self.multi_tier_limiter.set_user_tier(user_id, tier)
        logger.info(f"Set user {user_id} to tier '{tier}'")

    def add_tier(self, tier_name: str, config: RateLimitConfig):
        """Add rate limit tier"""
        self.multi_tier_limiter.add_tier(tier_name, config)
        logger.info(f"Added rate limit tier '{tier_name}'")

    def get_metrics(self) -> Dict[str, Any]:
        """Get middleware metrics"""
        rate_limited_rate = (
            self._rate_limited_requests / max(1, self._total_requests)
        )

        bypass_rate = (
            self._bypassed_requests / max(1, self._total_requests)
        )

        return {
            'enabled': self.enabled,
            'total_requests': self._total_requests,
            'rate_limited_requests': self._rate_limited_requests,
            'bypassed_requests': self._bypassed_requests,
            'rate_limited_rate': rate_limited_rate,
            'bypass_rate': bypass_rate,
            'route_configs': len(self._route_configs),
            'global_limiter': self.global_limiter.get_metrics(),
            'multi_tier_limiter': self.multi_tier_limiter.get_all_metrics()
        }

    def reset_metrics(self):
        """Reset all metrics"""
        self._total_requests = 0
        self._rate_limited_requests = 0
        self._bypassed_requests = 0

        self.global_limiter.reset_metrics()

        logger.info("Rate limit middleware metrics reset")

    def enable(self):
        """Enable rate limiting"""
        self.enabled = True
        logger.info("Rate limiting enabled")

    def disable(self):
        """Disable rate limiting"""
        self.enabled = False
        logger.info("Rate limiting disabled")


def create_rate_limit_middleware(app: Flask,
                                default_requests_per_second: float = 10.0,
                                default_burst_size: int = 50,
                                enabled: bool = True) -> RateLimitMiddleware:
    """
    Create and configure rate limit middleware

    Args:
        app: Flask application
        default_requests_per_second: Default request rate
        default_burst_size: Default burst size
        enabled: Whether rate limiting is enabled

    Returns:
        Configured RateLimitMiddleware instance
    """
    default_config = RateLimitConfig(
        requests_per_second=default_requests_per_second,
        burst_size=default_burst_size,
        strategy=RateLimitStrategy.PER_IP
    )

    middleware = RateLimitMiddleware(
        app=app,
        default_config=default_config,
        enabled=enabled
    )

    # Configure common API tiers
    middleware.add_tier('basic', RateLimitConfig(
        requests_per_second=5.0,
        burst_size=20,
        strategy=RateLimitStrategy.PER_USER
    ))

    middleware.add_tier('premium', RateLimitConfig(
        requests_per_second=20.0,
        burst_size=100,
        strategy=RateLimitStrategy.PER_USER
    ))

    middleware.add_tier('enterprise', RateLimitConfig(
        requests_per_second=100.0,
        burst_size=500,
        strategy=RateLimitStrategy.PER_USER
    ))

    logger.info("Rate limit middleware created and configured")
    return middleware