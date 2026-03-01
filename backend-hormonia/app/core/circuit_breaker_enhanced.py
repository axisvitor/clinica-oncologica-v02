"""
Enhanced Circuit Breaker Module - COMPATIBILITY SHIM.

All circuit breaker classes have been consolidated into
``app.resilience.circuit_breaker``.  This module re-exports the public
API so that existing ``from app.core.circuit_breaker_enhanced import ...``
statements continue to work without modification.
"""

from app.resilience.circuit_breaker.enhanced import (  # noqa: F401
    ServiceType,
    CircuitBreakerConfig,
    EnhancedCircuitBreaker,
    CircuitBreakerManager,
    get_circuit_breaker_manager,
    with_circuit_breaker,
    CIRCUIT_CONFIGS,
)

__all__ = [
    "ServiceType",
    "CircuitBreakerConfig",
    "EnhancedCircuitBreaker",
    "CircuitBreakerManager",
    "get_circuit_breaker_manager",
    "with_circuit_breaker",
    "CIRCUIT_CONFIGS",
]
