"""Core utilities and managers."""

from .event_loop_manager import (
    EventLoopManager,
    async_to_sync,
    AsyncFlowEngineBase,
    ManagedAsyncService,
    get_event_loop_manager,
    cleanup_all_loops,
)

# NOTE: redis_circuit_breaker is NOT imported here to avoid circular imports.
# Import directly from app.core.redis_circuit_breaker when needed:
#   from app.core.redis_circuit_breaker import RedisCircuitBreaker, CircuitState

__all__ = [
    "EventLoopManager",
    "async_to_sync",
    "AsyncFlowEngineBase",
    "ManagedAsyncService",
    "get_event_loop_manager",
    "cleanup_all_loops",
]
