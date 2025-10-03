"""
Rate Limiting Decorators

Convenient decorators for applying rate limits to Flask routes.
"""

import functools
from typing import Optional, Callable, List
from flask import jsonify

from .rate_limiter import RateLimiter, RateLimitConfig, RateLimitStrategy


def rate_limit(requests_per_second: float = 10.0,
               burst_size: int = 50,
               strategy: RateLimitStrategy = RateLimitStrategy.PER_IP,
               key_func: Optional[Callable] = None,
               whitelist: Optional[List[str]] = None,
               error_message: str = "Rate limit exceeded",
               error_code: int = 429):
    """
    Rate limit decorator for Flask routes

    Args:
        requests_per_second: Requests per second limit
        burst_size: Burst capacity
        strategy: Rate limiting strategy
        key_func: Custom key function
        whitelist: List of whitelisted IPs/users
        error_message: Error message for rate limited requests
        error_code: HTTP status code for rate limited requests
    """
    def decorator(func: Callable) -> Callable:
        # Create rate limiter configuration
        config = RateLimitConfig(
            requests_per_second=requests_per_second,
            burst_size=burst_size,
            strategy=strategy,
            key_func=key_func,
            whitelist=whitelist or []
        )

        # Create rate limiter
        limiter = RateLimiter(config, name=func.__name__)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Check rate limit
            result = limiter.check_rate_limit()

            if not result.allowed:
                # Return rate limit error
                response_data = {
                    'error': error_message,
                    'rate_limit': {
                        'limit': result.limit,
                        'remaining': result.remaining,
                        'reset_time': result.reset_time,
                        'retry_after': result.retry_after
                    }
                }

                response = jsonify(response_data)
                response.status_code = error_code

                # Add rate limit headers
                for header, value in result.headers.items():
                    response.headers[header] = value

                return response

            # Add rate limit headers to successful response
            response = func(*args, **kwargs)

            # Add headers if response has headers attribute
            if hasattr(response, 'headers'):
                for header, value in result.headers.items():
                    response.headers[header] = value

            return response

        # Attach rate limiter for metrics access
        wrapper._rate_limiter = limiter

        return wrapper

    return decorator


def api_rate_limit(tier: str = "basic",
                  error_message: str = "API rate limit exceeded",
                  error_code: int = 429):
    """
    API-specific rate limit decorator with predefined tiers

    Args:
        tier: Rate limit tier (basic, premium, enterprise)
        error_message: Error message for rate limited requests
        error_code: HTTP status code for rate limited requests
    """
    # Predefined tier configurations
    tier_configs = {
        'basic': RateLimitConfig(
            requests_per_second=5.0,
            burst_size=20,
            strategy=RateLimitStrategy.PER_USER
        ),
        'premium': RateLimitConfig(
            requests_per_second=20.0,
            burst_size=100,
            strategy=RateLimitStrategy.PER_USER
        ),
        'enterprise': RateLimitConfig(
            requests_per_second=100.0,
            burst_size=500,
            strategy=RateLimitStrategy.PER_USER
        )
    }

    if tier not in tier_configs:
        raise ValueError(f"Unknown rate limit tier: {tier}")

    config = tier_configs[tier]

    return rate_limit(
        requests_per_second=config.requests_per_second,
        burst_size=config.burst_size,
        strategy=config.strategy,
        error_message=f"{error_message} (tier: {tier})",
        error_code=error_code
    )


def user_rate_limit(requests_per_second: float = 10.0,
                   burst_size: int = 50,
                   error_message: str = "User rate limit exceeded",
                   error_code: int = 429):
    """
    User-specific rate limit decorator

    Args:
        requests_per_second: Requests per second limit
        burst_size: Burst capacity
        error_message: Error message for rate limited requests
        error_code: HTTP status code for rate limited requests
    """
    return rate_limit(
        requests_per_second=requests_per_second,
        burst_size=burst_size,
        strategy=RateLimitStrategy.PER_USER,
        error_message=error_message,
        error_code=error_code
    )


def endpoint_rate_limit(requests_per_second: float = 20.0,
                       burst_size: int = 100,
                       error_message: str = "Endpoint rate limit exceeded",
                       error_code: int = 429):
    """
    Endpoint-specific rate limit decorator

    Args:
        requests_per_second: Requests per second limit
        burst_size: Burst capacity
        error_message: Error message for rate limited requests
        error_code: HTTP status code for rate limited requests
    """
    return rate_limit(
        requests_per_second=requests_per_second,
        burst_size=burst_size,
        strategy=RateLimitStrategy.PER_ENDPOINT,
        error_message=error_message,
        error_code=error_code
    )


def global_rate_limit(requests_per_second: float = 1000.0,
                     burst_size: int = 2000,
                     error_message: str = "Global rate limit exceeded",
                     error_code: int = 503):
    """
    Global rate limit decorator (for system protection)

    Args:
        requests_per_second: Requests per second limit
        burst_size: Burst capacity
        error_message: Error message for rate limited requests
        error_code: HTTP status code for rate limited requests
    """
    return rate_limit(
        requests_per_second=requests_per_second,
        burst_size=burst_size,
        strategy=RateLimitStrategy.GLOBAL,
        error_message=error_message,
        error_code=error_code
    )


def get_rate_limit_metrics(func: Callable) -> Optional[dict]:
    """
    Get rate limit metrics from a decorated function

    Args:
        func: Function decorated with rate limit decorator

    Returns:
        Dictionary with rate limit metrics or None if not decorated
    """
    rate_limiter = getattr(func, '_rate_limiter', None)
    if rate_limiter:
        return rate_limiter.get_metrics()
    return None


def reset_rate_limit_metrics(func: Callable) -> bool:
    """
    Reset rate limit metrics for a decorated function

    Args:
        func: Function decorated with rate limit decorator

    Returns:
        True if metrics were reset, False if function not decorated
    """
    rate_limiter = getattr(func, '_rate_limiter', None)
    if rate_limiter:
        rate_limiter.reset_metrics()
        return True
    return False