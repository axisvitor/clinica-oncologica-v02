"""
Resilient orchestrator mixin providing circuit breakers and retry logic.

This module consolidates duplicate resilience patterns (circuit breakers,
exponential backoff retry, fallback handlers) found across multiple orchestrators.

Provides:
- Circuit breaker management for external services
- Exponential backoff retry with configurable delays
- Fallback handler registration and execution
- Failure tracking and recovery patterns
"""

import asyncio
import logging
from typing import Callable, Optional, Any, Dict, Tuple

from app.resilience.circuit_breaker.breaker import CircuitBreaker, CircuitBreakerConfig


logger = logging.getLogger(__name__)


class ResilientOrchestrator:
    """
    Mixin providing resilience patterns (circuit breakers, retries, fallbacks).

    This mixin must be used with BaseOrchestrator to access logging and
    database functionality. It consolidates retry logic from SagaOrchestrator
    and circuit breaker patterns from FlowOrchestrator.

    Must be used with BaseOrchestrator:
        >>> class MyOrchestrator(BaseOrchestrator, ResilientOrchestrator):
        ...     def __init__(self, db):
        ...         super().__init__(db)
        ...         self.setup_circuit_breaker("external_service")

    Provides:
    1. Circuit breaker setup and management
    2. Retry logic with exponential backoff
    3. Fallback handler registration and execution
    4. Failure tracking and recovery

    Example:
        >>> # Setup circuit breaker
        >>> orchestrator.setup_circuit_breaker(
        ...     "whatsapp",
        ...     failure_threshold=5,
        ...     recovery_timeout=60.0
        ... )
        >>>
        >>> # Execute with retry
        >>> result = await orchestrator.with_retry(
        ...     external_api_call,
        ...     arg1, arg2,
        ...     max_retries=3
        ... )
        >>>
        >>> # Execute with fallback
        >>> orchestrator.register_fallback("api", fallback_function)
        >>> result = await orchestrator.execute_with_fallback(
        ...     "api",
        ...     risky_operation,
        ...     *args
        ... )

    Attributes:
        _circuit_breakers (Dict[str, CircuitBreaker]): Circuit breakers by name
        _fallback_handlers (Dict[str, Callable]): Fallback handlers by service
        retry_initial_delay (int): Initial retry delay in seconds
        retry_max_delay (int): Maximum retry delay in seconds
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize resilience features.

        Must call super().__init__() to initialize BaseOrchestrator.
        """
        super().__init__(*args, **kwargs)
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._fallback_handlers: Dict[str, Callable] = {}
        self.retry_initial_delay = 1  # seconds
        self.retry_max_delay = 30  # seconds

    # ===============================
    # Circuit Breaker Management
    # ===============================

    def setup_circuit_breaker(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 3,
        timeout: float = 30.0,
        expected_exception: Tuple = (Exception,),
    ) -> CircuitBreaker:
        """
        Setup circuit breaker for external service.

        Args:
            name: Circuit breaker name (unique identifier)
            failure_threshold: Failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
            success_threshold: Successes needed to close circuit
            timeout: Request timeout in seconds
            expected_exception: Tuple of exceptions to handle

        Returns:
            Configured CircuitBreaker instance

        Example:
            >>> breaker = orchestrator.setup_circuit_breaker(
            ...     "payment_api",
            ...     failure_threshold=3,
            ...     recovery_timeout=30.0
            ... )
        """
        config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            success_threshold=success_threshold,
            timeout=timeout,
            expected_exception=expected_exception,
        )

        breaker = CircuitBreaker(name=name, config=config)
        self._circuit_breakers[name] = breaker

        self.log_info(
            f"Circuit breaker '{name}' configured",
            extra={
                "circuit_breaker": name,
                "failure_threshold": failure_threshold,
                "recovery_timeout": recovery_timeout,
            },
        )

        return breaker

    def get_circuit_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """
        Get circuit breaker by name.

        Args:
            name: Circuit breaker name

        Returns:
            CircuitBreaker instance or None if not found
        """
        return self._circuit_breakers.get(name)

    def get_circuit_breaker_status(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get circuit breaker status and metrics.

        Args:
            name: Circuit breaker name

        Returns:
            Status dictionary or None if breaker not found
        """
        breaker = self._circuit_breakers.get(name)
        if not breaker:
            return None

        return {
            "name": name,
            "state": breaker.state.value,
            "failure_count": breaker.failure_count,
            "success_count": breaker.success_count,
            "last_failure_time": (
                breaker.last_failure_time.isoformat()
                if breaker.last_failure_time
                else None
            ),
        }

    # ===============================
    # Retry Logic with Exponential Backoff
    # ===============================

    async def with_retry(
        self,
        func: Callable,
        *args,
        max_retries: int = 3,
        initial_delay: Optional[float] = None,
        max_delay: Optional[float] = None,
        **kwargs,
    ) -> Any:
        """
        Execute function with exponential backoff retry.

        Implements retry pattern from SagaOrchestrator with configurable
        delays and automatic backoff calculation.

        Args:
            func: Function to execute (sync or async)
            *args: Function arguments
            max_retries: Maximum retry attempts (default: 3)
            initial_delay: Initial retry delay in seconds (default: 1)
            max_delay: Maximum retry delay in seconds (default: 30)
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Last exception if all retries fail

        Example:
            >>> # Retry async function
            >>> result = await orchestrator.with_retry(
            ...     async_api_call,
            ...     "param1",
            ...     max_retries=5,
            ...     initial_delay=2
            ... )
            >>>
            >>> # Retry sync function
            >>> result = await orchestrator.with_retry(
            ...     sync_database_query,
            ...     query_params,
            ...     max_retries=3
            ... )
        """
        delay = initial_delay or self.retry_initial_delay
        max_delay_value = max_delay or self.retry_max_delay
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                # Execute function (handle both sync and async)
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                # Log success on retry
                if attempt > 0:
                    self.log_info(
                        f"Retry succeeded on attempt {attempt + 1}",
                        extra={"attempt": attempt + 1, "function": func.__name__},
                    )

                return result

            except Exception as e:
                last_exception = e

                if attempt < max_retries:
                    self.log_warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed, retrying in {delay}s",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": max_retries + 1,
                            "delay": delay,
                            "function": func.__name__,
                            "error": str(e),
                        },
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, max_delay_value)  # Exponential backoff
                else:
                    self.log_error(
                        f"All {max_retries + 1} attempts failed",
                        e,
                        extra={
                            "function": func.__name__,
                            "total_attempts": max_retries + 1,
                        },
                    )

        # All retries exhausted
        raise last_exception

    # ===============================
    # Fallback Handler Management
    # ===============================

    def register_fallback(self, service_name: str, fallback: Callable):
        """
        Register fallback handler for service failure.

        Args:
            service_name: Service identifier
            fallback: Fallback function (sync or async)

        Example:
            >>> def fallback_payment(amount, user_id):
            ...     # Fallback logic (e.g., queue for later)
            ...     return {"queued": True, "amount": amount}
            >>>
            >>> orchestrator.register_fallback("payment", fallback_payment)
        """
        self._fallback_handlers[service_name] = fallback
        self.log_info(
            f"Fallback registered for '{service_name}'",
            extra={"service": service_name, "fallback": fallback.__name__},
        )

    async def execute_with_fallback(
        self, service_name: str, func: Callable, *args, **kwargs
    ) -> Any:
        """
        Execute function with fallback on failure.

        Args:
            service_name: Service identifier for fallback lookup
            func: Primary function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Result from primary function or fallback

        Raises:
            Exception if both primary and fallback fail

        Example:
            >>> result = await orchestrator.execute_with_fallback(
            ...     "payment_api",
            ...     process_payment,
            ...     amount=100,
            ...     user_id=123
            ... )
        """
        try:
            # Execute primary function
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        except Exception as e:
            fallback = self._fallback_handlers.get(service_name)

            if fallback:
                self.log_warning(
                    f"Service '{service_name}' failed, using fallback",
                    extra={
                        "service": service_name,
                        "error": str(e),
                        "fallback": fallback.__name__,
                    },
                )

                # Execute fallback
                if asyncio.iscoroutinefunction(fallback):
                    return await fallback(*args, **kwargs)
                else:
                    return fallback(*args, **kwargs)

            # No fallback available
            self.log_error(
                f"Service '{service_name}' failed with no fallback",
                e,
                extra={"service": service_name},
            )
            raise

    # ===============================
    # Combined Circuit Breaker + Retry
    # ===============================

    async def execute_with_resilience(
        self,
        circuit_breaker_name: str,
        func: Callable,
        *args,
        max_retries: int = 3,
        **kwargs,
    ) -> Any:
        """
        Execute function with both circuit breaker and retry logic.

        Combines circuit breaker protection with exponential backoff retry
        for maximum resilience.

        Args:
            circuit_breaker_name: Circuit breaker to use
            func: Function to execute
            *args: Function arguments
            max_retries: Maximum retry attempts
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Exception if all retries fail or circuit is open

        Example:
            >>> result = await orchestrator.execute_with_resilience(
            ...     "external_api",
            ...     api_call,
            ...     endpoint="/users",
            ...     max_retries=5
            ... )
        """
        breaker = self.get_circuit_breaker(circuit_breaker_name)

        if not breaker:
            self.log_warning(
                f"Circuit breaker '{circuit_breaker_name}' not found, executing without protection"
            )
            return await self.with_retry(func, *args, max_retries=max_retries, **kwargs)

        # Execute with circuit breaker protection
        async def protected_func():
            async with breaker:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

        # Add retry on top of circuit breaker
        return await self.with_retry(protected_func, max_retries=max_retries)
