"""
Retry Logic with Exponential Backoff
Implements retry patterns for resilient service calls.
"""

import asyncio
import logging
from functools import wraps
from typing import Callable, TypeVar, Optional, Any, Tuple, Type
import random
from dataclasses import dataclass

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryConfig:
    """Configuration for retry behavior"""

    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BASE_DELAY = 1.0
    DEFAULT_MAX_DELAY = 60.0
    DEFAULT_EXPONENTIAL_BASE = 2.0
    DEFAULT_JITTER = True


class RetryExhaustedError(Exception):
    """Raised when all retry attempts have been exhausted"""

    pass


async def retry_with_backoff(
    max_retries: int = RetryConfig.DEFAULT_MAX_RETRIES,
    base_delay: float = RetryConfig.DEFAULT_BASE_DELAY,
    max_delay: float = RetryConfig.DEFAULT_MAX_DELAY,
    exponential_base: float = RetryConfig.DEFAULT_EXPONENTIAL_BASE,
    jitter: bool = RetryConfig.DEFAULT_JITTER,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None,
):
    """
    Decorator for retrying async functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds between retries
        max_delay: Maximum delay in seconds (caps exponential growth)
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to delays
        exceptions: Tuple of exception types to catch and retry
        on_retry: Callback function called on each retry attempt

    Example:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        async def call_api():
            return await api.request()
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)

                except exceptions as e:
                    last_exception = e

                    if attempt >= max_retries:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} retries: {e}",
                            extra={
                                "function": func.__name__,
                                "attempts": attempt + 1,
                                "error": str(e),
                            },
                        )
                        raise RetryExhaustedError(
                            f"Failed after {max_retries} retries: {e}"
                        ) from e

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base**attempt), max_delay)

                    # Add jitter if enabled
                    if jitter:
                        delay = delay * (0.5 + random.random())

                    # Call retry callback if provided
                    if on_retry:
                        try:
                            await on_retry(
                                e, attempt + 1
                            ) if asyncio.iscoroutinefunction(on_retry) else on_retry(
                                e, attempt + 1
                            )
                        except Exception as callback_error:
                            logger.warning(
                                f"on_retry callback failed: {callback_error}"
                            )

                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{max_retries} failed, "
                        f"retrying in {delay:.2f}s: {e}",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "delay": delay,
                            "error": str(e),
                        },
                    )

                    await asyncio.sleep(delay)

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


class RetryStrategy:
    """
    Advanced retry strategy with configurable policies.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        """
        Initialize retry strategy.

        Args:
            max_retries: Maximum number of retries
            base_delay: Base delay between retries
            max_delay: Maximum delay between retries
            exponential_base: Base for exponential calculation
            jitter: Whether to add jitter
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.stats = {
            "total_attempts": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "total_delay": 0.0,
        }

    async def execute(
        self,
        func: Callable[..., T],
        *args,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
        **kwargs,
    ) -> T:
        """
        Execute function with retry logic.

        Args:
            func: Function to execute
            *args: Function arguments
            exceptions: Exceptions to catch
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            RetryExhaustedError: If all retries are exhausted
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):
            self.stats["total_attempts"] += 1

            try:
                result = await func(*args, **kwargs)
                if attempt > 0:
                    self.stats["successful_retries"] += 1
                return result

            except exceptions as e:
                last_exception = e

                if attempt >= self.max_retries:
                    self.stats["failed_retries"] += 1
                    raise RetryExhaustedError(
                        f"Failed after {self.max_retries} retries: {e}"
                    ) from e

                delay = self._calculate_delay(attempt)
                self.stats["total_delay"] += delay

                logger.warning(
                    f"Retry attempt {attempt + 1}/{self.max_retries} "
                    f"after {delay:.2f}s delay"
                )

                await asyncio.sleep(delay)

        if last_exception:
            raise last_exception

    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for next retry attempt.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        delay = min(self.base_delay * (self.exponential_base**attempt), self.max_delay)

        if self.jitter:
            # Add jitter: randomize between 50% and 100% of calculated delay
            delay = delay * (0.5 + random.random() * 0.5)

        return delay

    def get_stats(self) -> dict:
        """
        Get retry statistics.

        Returns:
            Dictionary with retry stats
        """
        return {
            **self.stats,
            "average_delay": (
                self.stats["total_delay"] / max(self.stats["successful_retries"], 1)
            )
            if self.stats["successful_retries"] > 0
            else 0.0,
        }

    def reset_stats(self):
        """Reset retry statistics."""
        self.stats = {
            "total_attempts": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "total_delay": 0.0,
        }


@dataclass(frozen=True)
class _RetryStrategyPreset:
    """Immutable preset that creates a fresh strategy per access."""

    max_retries: int
    base_delay: float
    max_delay: float
    exponential_base: float
    jitter: bool

    def build(self) -> RetryStrategy:
        return RetryStrategy(
            max_retries=self.max_retries,
            base_delay=self.base_delay,
            max_delay=self.max_delay,
            exponential_base=self.exponential_base,
            jitter=self.jitter,
        )


class _RetryStrategyPresetDescriptor:
    """Descriptor returning a new strategy instance on each attribute access."""

    def __init__(self, preset: _RetryStrategyPreset):
        self._preset = preset

    def __get__(self, instance, owner) -> RetryStrategy:
        _ = instance, owner
        return self._preset.build()


# Predefined retry strategies for common use cases
class RetryStrategies:
    """Predefined retry strategies"""

    # Fast retry for quick operations
    FAST = _RetryStrategyPresetDescriptor(
        _RetryStrategyPreset(
            max_retries=3,
            base_delay=0.5,
            max_delay=5.0,
            exponential_base=2.0,
            jitter=True,
        )
    )

    # Standard retry for most operations
    STANDARD = _RetryStrategyPresetDescriptor(
        _RetryStrategyPreset(
            max_retries=3,
            base_delay=1.0,
            max_delay=30.0,
            exponential_base=2.0,
            jitter=True,
        )
    )

    # Slow retry for rate-limited APIs
    SLOW = _RetryStrategyPresetDescriptor(
        _RetryStrategyPreset(
            max_retries=5,
            base_delay=2.0,
            max_delay=60.0,
            exponential_base=2.0,
            jitter=True,
        )
    )

    # Aggressive retry for critical operations
    AGGRESSIVE = _RetryStrategyPresetDescriptor(
        _RetryStrategyPreset(
            max_retries=7,
            base_delay=0.5,
            max_delay=30.0,
            exponential_base=1.5,
            jitter=True,
        )
    )

    # Conservative retry for expensive operations
    CONSERVATIVE = _RetryStrategyPresetDescriptor(
        _RetryStrategyPreset(
            max_retries=2,
            base_delay=5.0,
            max_delay=60.0,
            exponential_base=2.0,
            jitter=False,
        )
    )


async def retry_async(
    func: Callable[..., T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    *args,
    **kwargs,
) -> T:
    """
    Simple retry function for one-off async calls.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retries
        base_delay: Base delay between retries
        exceptions: Exceptions to catch
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Function result

    Example:
        result = await retry_async(
            api.get_data,
            max_retries=3,
            base_delay=1.0,
            user_id=123
        )
    """
    strategy = RetryStrategy(max_retries=max_retries, base_delay=base_delay)
    return await strategy.execute(func, *args, exceptions=exceptions, **kwargs)


class CircuitBreakerRetry:
    """
    Combines circuit breaker with retry logic for maximum resilience.
    """

    def __init__(
        self,
        circuit_breaker: Any,  # CircuitBreaker instance
        retry_strategy: Optional[RetryStrategy] = None,
    ):
        """
        Initialize circuit breaker with retry.

        Args:
            circuit_breaker: CircuitBreaker instance
            retry_strategy: Retry strategy to use
        """
        self.circuit_breaker = circuit_breaker
        self.retry_strategy = retry_strategy or RetryStrategies.STANDARD

    async def execute(
        self,
        func: Callable[..., T],
        *args,
        fallback: Optional[Callable] = None,
        **kwargs,
    ) -> T:
        """
        Execute function with both circuit breaker and retry logic.

        Args:
            func: Function to execute
            *args: Function arguments
            fallback: Fallback function
            **kwargs: Function keyword arguments

        Returns:
            Function result or fallback result
        """

        async def wrapped_call():
            return await self.circuit_breaker.call(
                func, *args, fallback=fallback, **kwargs
            )

        return await self.retry_strategy.execute(wrapped_call)


# Convenience function to combine circuit breaker and retry
def with_retry_and_circuit_breaker(
    circuit_breaker: Any, retry_strategy: Optional[RetryStrategy] = None
):
    """
    Decorator that combines circuit breaker with retry logic.

    Args:
        circuit_breaker: CircuitBreaker instance
        retry_strategy: Retry strategy to use

    Example:
        @with_retry_and_circuit_breaker(evolution_breaker, RetryStrategies.STANDARD)
        async def send_message(phone, message):
            return await api.send(phone, message)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        combined = CircuitBreakerRetry(
            circuit_breaker, retry_strategy or RetryStrategies.STANDARD
        )

        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await combined.execute(func, *args, **kwargs)

        return wrapper

    return decorator
