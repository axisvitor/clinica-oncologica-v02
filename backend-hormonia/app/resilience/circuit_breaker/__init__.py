"""
Circuit Breaker Pattern - Consolidated Module

Single source of truth for all circuit breaker implementations:

1. **ServiceCircuitBreaker** (service_breaker.py): Async circuit breaker with
   fallback support, used by AI services, WhatsApp, database operations.
   This is the primary ``CircuitBreaker`` export.

2. **ProductionCircuitBreaker** (breaker.py): Thread-safe sync/async circuit
   breaker with monitoring metrics and ``CircuitBreakerConfig``.

3. **EnhancedCircuitBreaker** (enhanced.py): aiobreaker-backed circuit breaker
   with Prometheus metrics and Redis fallback queue. Includes
   ``CircuitBreakerManager`` for centralized management.

4. **CacheFallback** (cache_fallback.py): TTL-based cache for circuit breaker
   fallback responses.
"""

# --- Primary async circuit breaker (most callers use this) ---
from .service_breaker import (
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

# --- Production circuit breaker (thread-safe, config-based) ---
from .breaker import (
    CircuitBreaker as ProductionCircuitBreaker,
    CircuitBreakerStates,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerOpenError as ProductionCircuitBreakerOpenError,
    CircuitBreakerMetrics,
)

# --- Cache fallback ---
from .cache_fallback import CacheFallback

# --- Enhanced circuit breaker (aiobreaker + Prometheus) ---
# Lazy import to avoid requiring aiobreaker at module load time
def _lazy_enhanced():
    from .enhanced import (
        EnhancedCircuitBreaker,
        CircuitBreakerManager,
        CircuitBreakerConfig as EnhancedCircuitBreakerConfig,
        ServiceType,
        CIRCUIT_CONFIGS,
        get_circuit_breaker_manager,
        with_circuit_breaker,
    )
    return {
        "EnhancedCircuitBreaker": EnhancedCircuitBreaker,
        "CircuitBreakerManager": CircuitBreakerManager,
        "EnhancedCircuitBreakerConfig": EnhancedCircuitBreakerConfig,
        "ServiceType": ServiceType,
        "CIRCUIT_CONFIGS": CIRCUIT_CONFIGS,
        "get_circuit_breaker_manager": get_circuit_breaker_manager,
        "with_circuit_breaker": with_circuit_breaker,
    }


__all__ = [
    # Primary circuit breaker (from service_breaker)
    "CircuitBreaker",
    "CircuitState",
    "CircuitStats",
    "CircuitOpenError",
    "CircuitBreakerOpenError",
    "AIServiceCircuitBreaker",
    "get_ai_circuit_breaker",
    "circuit_breaker",
    "circuit_breaker_decorator",
    # Production circuit breaker (from breaker)
    "ProductionCircuitBreaker",
    "CircuitBreakerStates",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "ProductionCircuitBreakerOpenError",
    "CircuitBreakerMetrics",
    # Cache fallback
    "CacheFallback",
]
