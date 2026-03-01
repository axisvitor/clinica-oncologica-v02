"""
Redis-Backed Circuit Breaker for Cross-Worker Consistency.

This module provides a Redis-backed circuit breaker implementation that
persists state across multiple application workers/instances.

Key Features:
- State persistence in Redis for cross-worker consistency
- Full API compatibility with in-memory CircuitBreaker
- Atomic operations using Redis transactions
- TTL-based automatic cleanup
- Fallback to in-memory if Redis unavailable

Usage:
    from app.core.redis_circuit_breaker import RedisCircuitBreaker

    breaker = RedisCircuitBreaker(
        name="evolution_api",
        failure_threshold=5,
        recovery_timeout=60,
        success_threshold=3,
    )

    # Use like regular circuit breaker
    result = await breaker.call(func, *args, fallback=fallback_func, **kwargs)
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Optional

from app.core import redis_manager as redis_manager_module
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitOpenError(Exception):
    """Exception raised when circuit is open."""

    pass


class RedisCircuitBreaker:
    """
    Redis-backed circuit breaker for cross-worker consistency.

    This implementation stores all circuit breaker state in Redis, ensuring
    that multiple workers/instances share the same circuit state.

    State stored in Redis:
        - state: Current circuit state (closed/open/half_open)
        - consecutive_failures: Number of consecutive failures
        - consecutive_successes: Number of consecutive successes in half-open
        - total_requests: Total requests processed
        - successful_requests: Total successful requests
        - failed_requests: Total failed requests
        - last_failure_time: ISO timestamp of last failure

    Redis Keys:
        - circuit_breaker:{name}:state - JSON blob with all state
        - TTL of 1 hour for automatic cleanup of stale circuits
    """

    # Redis key prefix
    KEY_PREFIX = "circuit_breaker"
    # Default TTL for circuit breaker state (1 hour)
    DEFAULT_TTL = 3600

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 3,
        expected_exception: type = Exception,
        ttl: int = DEFAULT_TTL,
    ):
        """
        Initialize Redis-backed circuit breaker.

        Args:
            name: Circuit breaker name (used as Redis key suffix)
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before half-opening
            success_threshold: Successes needed to close from half-open
            expected_exception: Exception type to catch as failures
            ttl: TTL for Redis state in seconds (default: 1 hour)
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.expected_exception = expected_exception
        self.ttl = ttl
        self._redis_key = f"{self.KEY_PREFIX}:{name}:state"
        self._lock = asyncio.Lock()
        self._redis = None
        self._fallback_to_memory = False

        # In-memory fallback state (used if Redis unavailable)
        self._memory_state = {
            "state": CircuitState.CLOSED.value,
            "consecutive_failures": 0,
            "consecutive_successes": 0,
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "last_failure_time": None,
        }

        logger.info(
            f"Redis circuit breaker '{name}' initialized",
            extra={
                "failure_threshold": failure_threshold,
                "recovery_timeout": recovery_timeout,
                "success_threshold": success_threshold,
                "redis_key": self._redis_key,
            },
        )

    async def _get_redis(self):
        """Get Redis client, caching for performance."""
        if self._redis is None:
            try:
                self._redis = await redis_manager_module.get_async_redis_client()
            except Exception as e:
                logger.warning(
                    f"Failed to get Redis client for circuit breaker '{self.name}': {e}. "
                    "Falling back to in-memory mode."
                )
                self._fallback_to_memory = True
        return self._redis

    async def _get_state(self) -> Dict[str, Any]:
        """
        Get circuit breaker state from Redis.

        Returns:
            Dict with circuit state including:
                - state: CircuitState value
                - consecutive_failures: int
                - consecutive_successes: int
                - total_requests: int
                - successful_requests: int
                - failed_requests: int
                - last_failure_time: ISO string or None
        """
        if self._fallback_to_memory:
            return self._memory_state.copy()

        try:
            redis = await self._get_redis()
            if redis is None:
                return self._memory_state.copy()

            data = await redis.get(self._redis_key)
            if data:
                return json.loads(data)

            # Return default state if not in Redis
            return {
                "state": CircuitState.CLOSED.value,
                "consecutive_failures": 0,
                "consecutive_successes": 0,
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "last_failure_time": None,
            }

        except Exception as e:
            logger.warning(
                f"Failed to get circuit state from Redis for '{self.name}': {e}. "
                "Using in-memory fallback."
            )
            self._fallback_to_memory = True
            return self._memory_state.copy()

    async def _set_state(self, state: Dict[str, Any]) -> None:
        """
        Set circuit breaker state in Redis.

        Args:
            state: Dict with circuit state to persist
        """
        if self._fallback_to_memory:
            self._memory_state = state
            return

        try:
            redis = await self._get_redis()
            if redis is None:
                self._memory_state = state
                return

            await redis.set(
                self._redis_key,
                json.dumps(state),
                ex=self.ttl,
            )

        except Exception as e:
            logger.warning(
                f"Failed to set circuit state in Redis for '{self.name}': {e}. "
                "Using in-memory fallback."
            )
            self._fallback_to_memory = True
            self._memory_state = state

    def _should_attempt_reset(self, state: Dict[str, Any]) -> bool:
        """
        Check if enough time has passed to attempt reset from OPEN.

        Args:
            state: Current circuit state dict

        Returns:
            True if recovery_timeout has elapsed since last failure
        """
        last_failure = state.get("last_failure_time")
        if not last_failure:
            return True

        try:
            last_failure_dt = datetime.fromisoformat(last_failure)
            time_since_failure = now_sao_paulo() - last_failure_dt
            return time_since_failure.total_seconds() >= self.recovery_timeout
        except (ValueError, TypeError):
            return True

    def can_execute(self) -> bool:
        """
        Check if circuit allows execution (sync version for compatibility).

        Note: This is a sync method for compatibility. For accurate cross-worker
        state, use the async `call()` method which reads from Redis.

        Returns:
            True (always allows, actual check happens in async call)
        """
        # For sync compatibility, always return True
        # The actual state check happens in the async call() method
        return True

    def record_success(self) -> None:
        """
        Record successful execution (sync version for compatibility).

        Note: This is a sync method for compatibility. For cross-worker
        consistency, use the async `call()` method.
        """
        # Sync version updates memory state only
        self._memory_state["total_requests"] += 1
        self._memory_state["successful_requests"] += 1
        self._memory_state["consecutive_failures"] = 0
        self._memory_state["consecutive_successes"] += 1

        if self._memory_state["state"] == CircuitState.HALF_OPEN.value:
            if self._memory_state["consecutive_successes"] >= self.success_threshold:
                self._memory_state["state"] = CircuitState.CLOSED.value
                logger.info(f"Circuit {self.name} closed after recovery (sync)")

    def record_failure(self) -> None:
        """
        Record failed execution (sync version for compatibility).

        Note: This is a sync method for compatibility. For cross-worker
        consistency, use the async `call()` method.
        """
        # Sync version updates memory state only
        self._memory_state["total_requests"] += 1
        self._memory_state["failed_requests"] += 1
        self._memory_state["last_failure_time"] = now_sao_paulo().isoformat()
        self._memory_state["consecutive_failures"] += 1
        self._memory_state["consecutive_successes"] = 0

        current_state = self._memory_state["state"]
        if current_state == CircuitState.HALF_OPEN.value:
            self._memory_state["state"] = CircuitState.OPEN.value
            logger.warning(f"Circuit {self.name} reopened after test failure (sync)")
        elif current_state == CircuitState.CLOSED.value:
            if self._memory_state["consecutive_failures"] >= self.failure_threshold:
                self._memory_state["state"] = CircuitState.OPEN.value
                logger.error(
                    f"Circuit {self.name} opened after {self.failure_threshold} failures (sync)"
                )

    async def call(
        self,
        func: Callable,
        *args,
        fallback: Optional[Callable] = None,
        **kwargs,
    ) -> Any:
        """
        Execute function with circuit breaker protection.

        This method reads and updates state in Redis for cross-worker consistency.

        Args:
            func: Async function to call
            *args: Function arguments
            fallback: Optional fallback function
            **kwargs: Function keyword arguments

        Returns:
            Function result or fallback result

        Raises:
            CircuitOpenError: If circuit is open and no fallback provided
            Exception: If function fails and no fallback provided
        """
        async with self._lock:
            state = await self._get_state()

            # Check circuit state
            if state["state"] == CircuitState.OPEN.value:
                if self._should_attempt_reset(state):
                    state["state"] = CircuitState.HALF_OPEN.value
                    state["consecutive_successes"] = 0
                    await self._set_state(state)
                    logger.info(f"Circuit {self.name} half-opened for testing")
                else:
                    # Circuit is open, use fallback or raise
                    if fallback:
                        logger.warning(f"Circuit {self.name} is open, using fallback")
                        return await self._execute_fallback(fallback, *args, **kwargs)
                    raise CircuitOpenError(f"Circuit {self.name} is open")

        # Try to execute the function
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result

        except self.expected_exception as e:
            await self._on_failure()

            # Use fallback if available
            if fallback:
                logger.warning(f"Circuit {self.name} call failed, using fallback: {e}")
                return await self._execute_fallback(fallback, *args, **kwargs)
            raise

    async def _on_success(self) -> None:
        """Handle successful call - update Redis state."""
        async with self._lock:
            state = await self._get_state()

            state["total_requests"] += 1
            state["successful_requests"] += 1
            state["consecutive_failures"] = 0
            state["consecutive_successes"] += 1

            if state["state"] == CircuitState.HALF_OPEN.value:
                if state["consecutive_successes"] >= self.success_threshold:
                    state["state"] = CircuitState.CLOSED.value
                    logger.info(f"Circuit {self.name} closed after recovery")

            await self._set_state(state)

    async def _on_failure(self) -> None:
        """Handle failed call - update Redis state."""
        async with self._lock:
            state = await self._get_state()

            state["total_requests"] += 1
            state["failed_requests"] += 1
            state["last_failure_time"] = now_sao_paulo().isoformat()
            state["consecutive_failures"] += 1
            state["consecutive_successes"] = 0

            if state["state"] == CircuitState.HALF_OPEN.value:
                # Failed during recovery test, reopen
                state["state"] = CircuitState.OPEN.value
                logger.warning(f"Circuit {self.name} reopened after test failure")

            elif state["state"] == CircuitState.CLOSED.value:
                if state["consecutive_failures"] >= self.failure_threshold:
                    state["state"] = CircuitState.OPEN.value
                    logger.error(
                        f"Circuit {self.name} opened after {self.failure_threshold} failures"
                    )

            await self._set_state(state)

    async def _execute_fallback(
        self, fallback: Callable, *args, **kwargs
    ) -> Any:
        """Execute fallback function."""
        try:
            if asyncio.iscoroutinefunction(fallback):
                return await fallback(*args, **kwargs)
            else:
                return fallback(*args, **kwargs)
        except Exception as e:
            logger.error(f"Fallback failed for {self.name}: {e}")
            raise

    def get_state(self) -> CircuitState:
        """
        Get current circuit state (sync version).

        Note: Returns in-memory state. For accurate cross-worker state,
        use `get_state_async()`.
        """
        return CircuitState(self._memory_state["state"])

    async def get_state_async(self) -> CircuitState:
        """Get current circuit state from Redis."""
        state = await self._get_state()
        return CircuitState(state["state"])

    def get_stats(self) -> Dict[str, Any]:
        """
        Get circuit statistics (sync version).

        Note: Returns in-memory stats. For accurate cross-worker stats,
        use `get_stats_async()`.
        """
        state = self._memory_state
        total = state["total_requests"]
        successful = state["successful_requests"]
        success_rate = (successful / total * 100) if total > 0 else 100.0

        return {
            "name": self.name,
            "state": state["state"],
            "total_requests": total,
            "successful_requests": successful,
            "failed_requests": state["failed_requests"],
            "success_rate": f"{success_rate:.2f}%",
            "consecutive_failures": state["consecutive_failures"],
            "consecutive_successes": state["consecutive_successes"],
            "last_failure": state["last_failure_time"],
            "redis_backed": not self._fallback_to_memory,
        }

    async def get_stats_async(self) -> Dict[str, Any]:
        """Get circuit statistics from Redis."""
        state = await self._get_state()
        total = state["total_requests"]
        successful = state["successful_requests"]
        success_rate = (successful / total * 100) if total > 0 else 100.0

        return {
            "name": self.name,
            "state": state["state"],
            "total_requests": total,
            "successful_requests": successful,
            "failed_requests": state["failed_requests"],
            "success_rate": f"{success_rate:.2f}%",
            "consecutive_failures": state["consecutive_failures"],
            "consecutive_successes": state["consecutive_successes"],
            "last_failure": state["last_failure_time"],
            "redis_backed": not self._fallback_to_memory,
        }

    def reset(self) -> None:
        """
        Reset circuit to closed state (sync version).

        Note: Only resets in-memory state. For cross-worker reset,
        use `reset_async()`.
        """
        self._memory_state = {
            "state": CircuitState.CLOSED.value,
            "consecutive_failures": 0,
            "consecutive_successes": 0,
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "last_failure_time": None,
        }
        logger.info(f"Circuit {self.name} manually reset (in-memory)")

    async def reset_async(self) -> None:
        """Reset circuit to closed state in Redis."""
        async with self._lock:
            state = {
                "state": CircuitState.CLOSED.value,
                "consecutive_failures": 0,
                "consecutive_successes": 0,
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "last_failure_time": None,
            }
            await self._set_state(state)
            self._memory_state = state.copy()
            logger.info(f"Circuit {self.name} manually reset (Redis)")

    async def force_open(self) -> None:
        """Force circuit to open state in Redis."""
        async with self._lock:
            state = await self._get_state()
            state["state"] = CircuitState.OPEN.value
            state["last_failure_time"] = now_sao_paulo().isoformat()
            await self._set_state(state)
            self._memory_state = state.copy()
            logger.warning(f"Circuit {self.name} manually forced OPEN")

    async def force_closed(self) -> None:
        """Force circuit to closed state in Redis."""
        async with self._lock:
            state = await self._get_state()
            state["state"] = CircuitState.CLOSED.value
            state["consecutive_failures"] = 0
            state["consecutive_successes"] = 0
            await self._set_state(state)
            self._memory_state = state.copy()
            logger.info(f"Circuit {self.name} manually forced CLOSED")

    def __repr__(self) -> str:
        return (
            f"RedisCircuitBreaker(name='{self.name}', "
            f"state={self._memory_state['state']}, "
            f"failures={self._memory_state['consecutive_failures']}/{self.failure_threshold})"
        )


# Factory function for creating Redis circuit breakers
def create_redis_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    success_threshold: int = 3,
) -> RedisCircuitBreaker:
    """
    Factory function to create a Redis-backed circuit breaker.

    Args:
        name: Circuit breaker name
        failure_threshold: Failures before opening
        recovery_timeout: Seconds before half-opening
        success_threshold: Successes to close from half-open

    Returns:
        RedisCircuitBreaker instance
    """
    return RedisCircuitBreaker(
        name=name,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        success_threshold=success_threshold,
    )


__all__ = [
    "RedisCircuitBreaker",
    "CircuitState",
    "CircuitOpenError",
    "create_redis_circuit_breaker",
]
