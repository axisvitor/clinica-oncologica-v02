"""
Circuit Breaker Pattern for External Service Calls.

Implements the circuit breaker pattern to prevent cascading failures
and provide fast-fail behavior for unavailable services.

States:
    CLOSED: Normal operation, requests pass through
    OPEN: Fast-fail mode, requests immediately return fallback
    HALF_OPEN: Testing recovery, limited requests allowed

Usage:
    from app.core.circuit_breaker import CircuitBreaker

    # Create circuit breaker
    redis_breaker = CircuitBreaker(
        name="Redis",
        failure_threshold=3,
        timeout=5.0,
        recovery_timeout=30.0
    )

    # Use circuit breaker
    result = await redis_breaker.call(
        func=lambda: redis_client.ping(),
        fallback=None
    )

References:
    - Martin Fowler: https://martinfowler.com/bliki/CircuitBreaker.html
    - Microsoft Patterns: https://docs.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker
"""

import asyncio
import time
from enum import Enum
from typing import Callable, TypeVar, Optional, Any, Dict
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"           # Normal operation
    OPEN = "open"              # Fast-fail mode
    HALF_OPEN = "half_open"    # Testing recovery


@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker monitoring."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    timeout_calls: int = 0
    fast_failed_calls: int = 0
    state_changes: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    current_state: CircuitState = CircuitState.CLOSED
    state_history: list = field(default_factory=list)

    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_calls == 0:
            return 100.0
        return (self.successful_calls / self.total_calls) * 100

    def failure_rate(self) -> float:
        """Calculate failure rate percentage."""
        if self.total_calls == 0:
            return 0.0
        return (self.failed_calls / self.total_calls) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "timeout_calls": self.timeout_calls,
            "fast_failed_calls": self.fast_failed_calls,
            "success_rate": round(self.success_rate(), 2),
            "failure_rate": round(self.failure_rate(), 2),
            "state_changes": self.state_changes,
            "current_state": self.current_state.value,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
        }


class CircuitBreaker:
    """
    Circuit breaker for external service calls.

    Prevents cascading failures by fast-failing when a service is unavailable.

    States:
        - CLOSED: Normal operation, all requests pass through
        - OPEN: Service is down, immediately return fallback
        - HALF_OPEN: Testing recovery, allow limited requests

    Example:
        breaker = CircuitBreaker(
            name="External API",
            failure_threshold=5,
            timeout=10.0,
            recovery_timeout=60.0
        )

        result = await breaker.call(
            func=lambda: api_client.fetch_data(),
            fallback={"status": "unavailable"}
        )
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        timeout: float = 10.0,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Circuit breaker name for logging
            failure_threshold: Number of failures to open circuit
            timeout: Request timeout in seconds
            recovery_timeout: Time to wait before testing recovery (seconds)
            half_open_max_calls: Max calls allowed in HALF_OPEN state
            logger: Optional logger instance
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.logger = logger or logging.getLogger(__name__)

        # State management
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.half_open_calls = 0
        self.last_failure_time = 0.0
        self.last_state_change = time.time()

        # Metrics
        self.metrics = CircuitBreakerMetrics(current_state=self.state)

        # Thread safety
        self._lock = asyncio.Lock()

        self.logger.info(
            f"Circuit breaker '{name}' initialized: "
            f"threshold={failure_threshold}, timeout={timeout}s, "
            f"recovery={recovery_timeout}s"
        )

    async def call(
        self,
        func: Callable[[], T],
        fallback: Optional[T] = None,
        exception_types: tuple = (Exception,)
    ) -> T:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Async function to execute
            fallback: Value to return on failure/fast-fail
            exception_types: Tuple of exceptions to catch

        Returns:
            Result from function or fallback value

        Example:
            result = await breaker.call(
                func=lambda: api_client.fetch(),
                fallback={"error": "service_unavailable"}
            )
        """
        async with self._lock:
            self.metrics.total_calls += 1

            # Check circuit state
            if not await self._should_attempt():
                self.metrics.fast_failed_calls += 1
                self.logger.warning(
                    f"Circuit '{self.name}' is OPEN - fast failing"
                )
                return fallback

            # Attempt call
            try:
                result = await asyncio.wait_for(func(), timeout=self.timeout)
                await self._on_success()
                return result

            except asyncio.TimeoutError:
                self.metrics.timeout_calls += 1
                self.logger.error(
                    f"Circuit '{self.name}' timeout after {self.timeout}s"
                )
                await self._on_failure(
                    TimeoutError(f"Request timeout after {self.timeout}s")
                )
                return fallback

            except exception_types as e:
                self.logger.error(
                    f"Circuit '{self.name}' error: {type(e).__name__}: {e}"
                )
                await self._on_failure(e)
                return fallback

    async def _should_attempt(self) -> bool:
        """
        Determine if request should be attempted.

        Returns:
            True if request should proceed, False for fast-fail
        """
        # CLOSED state: always attempt
        if self.state == CircuitState.CLOSED:
            return True

        # OPEN state: check recovery timeout
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                await self._transition_to_half_open()
                return True
            return False

        # HALF_OPEN state: allow limited calls
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls < self.half_open_max_calls:
                self.half_open_calls += 1
                return True
            return False

        return False

    async def _on_success(self):
        """Handle successful call."""
        self.metrics.successful_calls += 1
        self.metrics.last_success_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # Successful call in HALF_OPEN -> transition to CLOSED
            await self._transition_to_closed()

        # Reset failure count on success
        self.failure_count = 0

    async def _on_failure(self, error: Exception):
        """Handle failed call."""
        self.metrics.failed_calls += 1
        self.metrics.last_failure_time = time.time()
        self.last_failure_time = time.time()
        self.failure_count += 1

        if self.state == CircuitState.HALF_OPEN:
            # Failed call in HALF_OPEN -> reopen circuit
            await self._transition_to_open()

        elif self.state == CircuitState.CLOSED:
            # Check if threshold reached
            if self.failure_count >= self.failure_threshold:
                await self._transition_to_open()

    async def _transition_to_closed(self):
        """Transition to CLOSED state."""
        if self.state != CircuitState.CLOSED:
            self.logger.info(
                f"Circuit '{self.name}' transitioning to CLOSED "
                f"(from {self.state.value})"
            )
            self._change_state(CircuitState.CLOSED)
            self.failure_count = 0
            self.half_open_calls = 0

    async def _transition_to_open(self):
        """Transition to OPEN state."""
        if self.state != CircuitState.OPEN:
            self.logger.error(
                f"Circuit '{self.name}' transitioning to OPEN "
                f"(from {self.state.value}) after {self.failure_count} failures"
            )
            self._change_state(CircuitState.OPEN)
            self.half_open_calls = 0

    async def _transition_to_half_open(self):
        """Transition to HALF_OPEN state."""
        if self.state != CircuitState.HALF_OPEN:
            self.logger.info(
                f"Circuit '{self.name}' transitioning to HALF_OPEN "
                f"(from {self.state.value}) - testing recovery"
            )
            self._change_state(CircuitState.HALF_OPEN)
            self.half_open_calls = 0

    def _change_state(self, new_state: CircuitState):
        """Change circuit state and record metrics."""
        old_state = self.state
        self.state = new_state
        self.last_state_change = time.time()
        self.metrics.state_changes += 1
        self.metrics.current_state = new_state

        # Record state change in history
        self.metrics.state_history.append({
            "from": old_state.value,
            "to": new_state.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "failure_count": self.failure_count
        })

        # Keep only last 10 state changes
        if len(self.metrics.state_history) > 10:
            self.metrics.state_history = self.metrics.state_history[-10:]

    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        return self.state

    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics."""
        return {
            "name": self.name,
            "config": {
                "failure_threshold": self.failure_threshold,
                "timeout": self.timeout,
                "recovery_timeout": self.recovery_timeout,
            },
            **self.metrics.to_dict()
        }

    def reset(self):
        """Manually reset circuit breaker to CLOSED state."""
        self.logger.info(f"Circuit '{self.name}' manually reset")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.half_open_calls = 0
        self.last_failure_time = 0.0

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(name='{self.name}', state={self.state.value}, "
            f"failures={self.failure_count}/{self.failure_threshold})"
        )


class CircuitBreakerRegistry:
    """
    Global registry for circuit breakers.

    Allows centralized management and monitoring of all circuit breakers.

    Usage:
        registry = get_circuit_breaker_registry()

        # Register breakers
        registry.register("redis", redis_breaker)
        registry.register("firebase", firebase_breaker)

        # Get metrics
        all_metrics = registry.get_all_metrics()

        # Reset all
        registry.reset_all()
    """

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    async def register(self, name: str, breaker: CircuitBreaker):
        """Register a circuit breaker."""
        async with self._lock:
            self._breakers[name] = breaker
            logger.info(f"Registered circuit breaker: {name}")

    async def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        return self._breakers.get(name)

    async def get_all_metrics(self) -> Dict[str, Any]:
        """Get metrics for all registered circuit breakers."""
        async with self._lock:
            return {
                name: breaker.get_metrics()
                for name, breaker in self._breakers.items()
            }

    async def reset_all(self):
        """Reset all circuit breakers."""
        async with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()
            logger.info("All circuit breakers reset")

    def list_breakers(self) -> list:
        """List all registered circuit breaker names."""
        return list(self._breakers.keys())


# Global registry instance
_registry: Optional[CircuitBreakerRegistry] = None


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get global circuit breaker registry."""
    global _registry
    if _registry is None:
        _registry = CircuitBreakerRegistry()
    return _registry


__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "CircuitBreakerMetrics",
    "CircuitBreakerRegistry",
    "get_circuit_breaker_registry",
]
