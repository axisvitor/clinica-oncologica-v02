"""
Circuit Breaker Pattern - COMPATIBILITY SHIM.

All circuit breaker classes have been consolidated into
``app.resilience.circuit_breaker``.  This module re-exports the public
API so that existing ``from app.core.circuit_breaker import ...``
statements continue to work without modification.
"""

from app.resilience.circuit_breaker.service_breaker import (  # noqa: F401
    CircuitBreaker,
    CircuitState,
    CircuitOpenError,
    CircuitBreakerOpenError,
)

# CircuitBreakerMetrics re-exported from the production breaker
from app.resilience.circuit_breaker.breaker import (  # noqa: F401
    CircuitBreakerMetrics,
)

__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "CircuitBreakerMetrics",
    "CircuitOpenError",
    "CircuitBreakerOpenError",
]
