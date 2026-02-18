"""
Resilience Patterns Module

Implements production-ready resilience patterns:
- Circuit Breaker (FIX #9)
- Retry with Exponential Backoff (FIX #10)
- Health Checks (FIX #11)
- Rate Limiting (FIX #12)
"""

from .circuit_breaker import CircuitBreaker, CircuitBreakerStates, CircuitState
from .retry import RetryManager, ExponentialBackoff
from .health import HealthChecker, HealthStatus
from .rate_limit import TokenBucket, RateLimiter


def _missing_flask_feature(feature: str):
    def _raiser(*_args, **_kwargs):
        raise RuntimeError(
            f"{feature} requires Flask. Install Flask or switch to the FastAPI metrics integration."
        )

    return _raiser


try:  # Optional Flask metrics dashboard
    from .metrics import ResilienceMetrics  # type: ignore
except Exception:  # pragma: no cover - Flask may be absent
    ResilienceMetrics = _missing_flask_feature("ResilienceMetrics")  # type: ignore

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerStates",
    "CircuitState",
    "RetryManager",
    "ExponentialBackoff",
    "HealthChecker",
    "HealthStatus",
    "TokenBucket",
    "RateLimiter",
    "ResilienceMetrics",
]
