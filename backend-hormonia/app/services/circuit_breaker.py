"""
Circuit Breaker Service - COMPATIBILITY SHIM.

All circuit breaker classes have been consolidated into
``app.resilience.circuit_breaker``.  This module re-exports the public
API so that existing ``from app.services.circuit_breaker import ...``
statements continue to work without modification.
"""

from app.resilience.circuit_breaker.service_breaker import (  # noqa: F401
    CircuitBreaker,
    CircuitState,
    CircuitStats,
    CircuitOpenError,
    CircuitBreakerOpenError,
    AIServiceCircuitBreaker,
    get_ai_circuit_breaker,
    circuit_breaker,
    circuit_breaker_decorator,
)

__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "CircuitStats",
    "CircuitOpenError",
    "CircuitBreakerOpenError",
    "AIServiceCircuitBreaker",
    "get_ai_circuit_breaker",
    "circuit_breaker",
    "circuit_breaker_decorator",
]
