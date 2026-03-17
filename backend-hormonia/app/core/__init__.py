"""Core utilities and managers."""

# NOTE: redis_circuit_breaker is NOT imported here to avoid circular imports.
# Import directly from app.core.redis_circuit_breaker when needed:
#   from app.core.redis_circuit_breaker import RedisCircuitBreaker, CircuitState
