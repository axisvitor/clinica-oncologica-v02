"""
Circuit Breaker Pattern Implementation (FIX #9)

Implements circuit breaker for external APIs with:
- CLOSED, OPEN, HALF_OPEN states
- Configurable thresholds and timeouts
- Fallback mechanisms
- Metrics collection
"""

from .breaker import CircuitBreaker, CircuitBreakerStates, CircuitBreakerConfig
from .cache_fallback import CacheFallback

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerStates",
    "CircuitBreakerConfig",
    "CacheFallback",
]
