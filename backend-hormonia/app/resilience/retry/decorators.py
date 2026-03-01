"""
Retry Decorators

Convenient decorators for applying retry logic to functions.
"""

import functools
from typing import Callable, Optional, Type, Tuple

from .retry_manager import RetryManager, RetryConfig
from .backoff import BackoffConfig, BackoffStrategy

RETRY_ARG_NAMES = (
    "max_attempts",
    "backoff_strategy",
    "base_delay",
    "max_delay",
    "multiplier",
    "jitter",
    "exceptions",
    "stop_exceptions",
    "timeout",
    "enable_dead_letter",
    "retry_condition",
    "name",
)


def _merge_retry_args(args: tuple, kwargs: dict) -> dict:
    """Accept positional decorator args while normalizing to keyword arguments."""
    merged_kwargs = dict(kwargs)
    for index, value in enumerate(args):
        if index >= len(RETRY_ARG_NAMES):
            raise TypeError("Too many positional arguments for retry decorator")
        key = RETRY_ARG_NAMES[index]
        merged_kwargs.setdefault(key, value)
    return merged_kwargs


def _build_retry_manager(
    *,
    manager_name: str,
    max_attempts: int,
    backoff_strategy: BackoffStrategy,
    base_delay: float,
    max_delay: float,
    multiplier: float,
    jitter: bool,
    exceptions: Tuple[Type[Exception], ...],
    stop_exceptions: Tuple[Type[Exception], ...],
    timeout: Optional[float],
    enable_dead_letter: bool,
    retry_condition: Optional[Callable],
) -> RetryManager:
    """Construct a RetryManager with shared decorator configuration."""
    backoff_config = BackoffConfig(
        base_delay=base_delay,
        max_delay=max_delay,
        multiplier=multiplier,
        jitter=jitter,
        strategy=backoff_strategy,
    )

    retry_config = RetryConfig(
        max_attempts=max_attempts,
        backoff_config=backoff_config,
        retryable_exceptions=exceptions,
        stop_exceptions=stop_exceptions,
        timeout=timeout,
        enable_dead_letter=enable_dead_letter,
        retry_condition=retry_condition,
    )
    return RetryManager(retry_config, name=manager_name)


def _make_retry_decorator(
    *,
    use_async: bool,
    max_attempts: int = 3,
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    multiplier: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    stop_exceptions: Tuple[Type[Exception], ...] = (),
    timeout: Optional[float] = None,
    enable_dead_letter: bool = False,
    retry_condition: Optional[Callable] = None,
    name: Optional[str] = None,
):
    """Create a retry decorator for sync or async callables."""

    def decorator(func: Callable) -> Callable:
        retry_manager = _build_retry_manager(
            manager_name=name or func.__name__,
            max_attempts=max_attempts,
            backoff_strategy=backoff_strategy,
            base_delay=base_delay,
            max_delay=max_delay,
            multiplier=multiplier,
            jitter=jitter,
            exceptions=exceptions,
            stop_exceptions=stop_exceptions,
            timeout=timeout,
            enable_dead_letter=enable_dead_letter,
            retry_condition=retry_condition,
        )

        if use_async:

            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                return await retry_manager.aexecute(func, *args, **kwargs)

        else:

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return retry_manager.execute(func, *args, **kwargs)

        # Attach retry manager for metrics access
        wrapper._retry_manager = retry_manager
        return wrapper

    return decorator


def retry(*args, **kwargs):
    """
    Retry decorator for synchronous functions

    Args:
        max_attempts: Maximum number of retry attempts
        backoff_strategy: Backoff strategy (exponential, linear, fixed, fibonacci)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        multiplier: Exponential multiplier
        jitter: Add random jitter to delays
        exceptions: Tuple of exceptions that trigger retries
        stop_exceptions: Tuple of exceptions that stop retries immediately
        timeout: Operation timeout in seconds
        enable_dead_letter: Enable dead letter queue for persistent failures
        retry_condition: Custom function to determine if retry should happen
        name: Name for the retry manager (defaults to function name)
    """

    merged_kwargs = _merge_retry_args(args, kwargs)
    return _make_retry_decorator(use_async=False, **merged_kwargs)


def async_retry(*args, **kwargs):
    """
    Retry decorator for asynchronous functions

    Args:
        max_attempts: Maximum number of retry attempts
        backoff_strategy: Backoff strategy (exponential, linear, fixed, fibonacci)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        multiplier: Exponential multiplier
        jitter: Add random jitter to delays
        exceptions: Tuple of exceptions that trigger retries
        stop_exceptions: Tuple of exceptions that stop retries immediately
        timeout: Operation timeout in seconds
        enable_dead_letter: Enable dead letter queue for persistent failures
        retry_condition: Custom function to determine if retry should happen
        name: Name for the retry manager (defaults to function name)
    """

    merged_kwargs = _merge_retry_args(args, kwargs)
    return _make_retry_decorator(use_async=True, **merged_kwargs)


def database_retry(
    max_attempts: int = 5, base_delay: float = 0.5, max_delay: float = 30.0
):
    """
    Specialized retry decorator for database operations
    """
    from psycopg import OperationalError as PsycopgOperationalError
    from psycopg.errors import (
        IntegrityError as PsycopgIntegrityError,
        ProgrammingError as PsycopgProgrammingError,
    )
    from sqlalchemy.exc import OperationalError, DisconnectionError

    return retry(
        max_attempts=max_attempts,
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        base_delay=base_delay,
        max_delay=max_delay,
        exceptions=(
            OperationalError,
            DisconnectionError,
            PsycopgOperationalError,
            ConnectionError,
        ),
        stop_exceptions=(PsycopgIntegrityError, PsycopgProgrammingError),
        name="database_retry",
    )


def api_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    timeout: float = 30.0,
):
    """
    Specialized retry decorator for API calls
    """
    retryable_exceptions: Tuple[Type[Exception], ...]
    stop_exceptions: Tuple[Type[Exception], ...]

    try:
        import aiohttp

        retryable_exceptions = (
            aiohttp.ClientError,
            aiohttp.ClientConnectionError,
            aiohttp.ServerTimeoutError,
            ConnectionError,
            TimeoutError,
        )
        # Client response errors (typically 4xx) should not be retried.
        stop_exceptions = (aiohttp.ClientResponseError,)
    except Exception:
        from urllib.error import HTTPError, URLError

        retryable_exceptions = (
            URLError,
            ConnectionError,
            TimeoutError,
        )
        stop_exceptions = (HTTPError,)

    return retry(
        max_attempts=max_attempts,
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        base_delay=base_delay,
        max_delay=max_delay,
        timeout=timeout,
        exceptions=retryable_exceptions,
        stop_exceptions=stop_exceptions,
        name="api_retry",
    )


def get_retry_metrics(func: Callable) -> Optional[dict]:
    """
    Get retry metrics from a decorated function

    Args:
        func: Function decorated with @retry or @async_retry

    Returns:
        Dictionary with retry metrics or None if not decorated
    """
    retry_manager = getattr(func, "_retry_manager", None)
    if retry_manager:
        return retry_manager.get_metrics()
    return None


def reset_retry_metrics(func: Callable) -> bool:
    """
    Reset retry metrics for a decorated function

    Args:
        func: Function decorated with @retry or @async_retry

    Returns:
        True if metrics were reset, False if function not decorated
    """
    retry_manager = getattr(func, "_retry_manager", None)
    if retry_manager:
        retry_manager.reset_metrics()
        return True
    return False
