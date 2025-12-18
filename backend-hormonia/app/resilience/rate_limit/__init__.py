"""
Rate Limiting Implementation (FIX #12)

Implements production-ready rate limiting with:
- Token bucket algorithm
- Per-user rate limiting
- API endpoint throttling
- Graceful degradation
"""

from .token_bucket import TokenBucket, TokenBucketConfig
from .rate_limiter import (
    RateLimiter,
    RateLimitConfig,
    RateLimitResult,
    RateLimitStrategy,
    RateLimitContext,
)

__all__ = [
    "TokenBucket",
    "TokenBucketConfig",
    "RateLimiter",
    "RateLimitConfig",
    "RateLimitResult",
    "RateLimitStrategy",
    "RateLimitContext",
]


def _missing_flask_feature(feature: str):
    def _raiser(*_args, **_kwargs):
        raise RuntimeError(
            f"{feature} requires Flask. Install Flask or use the FastAPI integration instead."
        )

    return _raiser


try:  # Optional Flask decorators
    from .decorators import rate_limit, api_rate_limit  # type: ignore
except Exception:  # pragma: no cover - Flask may be absent
    rate_limit = _missing_flask_feature("rate_limit decorator")
    api_rate_limit = _missing_flask_feature("api_rate_limit decorator")

__all__.extend(["rate_limit", "api_rate_limit"])

try:  # Optional Flask middleware
    from .middleware import RateLimitMiddleware  # type: ignore
except Exception:  # pragma: no cover - Flask may be absent

    class RateLimitMiddleware:  # type: ignore
        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                "RateLimitMiddleware requires Flask. Install Flask to use it."
            )


__all__.append("RateLimitMiddleware")
