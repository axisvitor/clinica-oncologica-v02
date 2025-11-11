"""
Retry Decorators

Convenient decorators for applying retry logic to functions.
"""

import asyncio
import functools
from typing import Any, Callable, Optional, Type, Union, Tuple

from .retry_manager import RetryManager, RetryConfig
from .backoff import BackoffConfig, BackoffStrategy, create_exponential_backoff
from .dead_letter import DeadLetterQueue


def retry(max_attempts: int = 3,
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
          name: Optional[str] = None):
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
    def decorator(func: Callable) -> Callable:
        # Create retry configuration
        backoff_config = BackoffConfig(
            base_delay=base_delay,
            max_delay=max_delay,
            multiplier=multiplier,
            jitter=jitter,
            strategy=backoff_strategy
        )

        retry_config = RetryConfig(
            max_attempts=max_attempts,
            backoff_config=backoff_config,
            retryable_exceptions=exceptions,
            stop_exceptions=stop_exceptions,
            timeout=timeout,
            enable_dead_letter=enable_dead_letter,
            retry_condition=retry_condition
        )

        # Create retry manager
        manager_name = name or func.__name__
        retry_manager = RetryManager(retry_config, name=manager_name)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return retry_manager.execute(func, *args, **kwargs)

        # Attach retry manager for metrics access
        wrapper._retry_manager = retry_manager

        return wrapper

    return decorator


def async_retry(max_attempts: int = 3,
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
                name: Optional[str] = None):
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
    def decorator(func: Callable) -> Callable:
        # Create retry configuration
        backoff_config = BackoffConfig(
            base_delay=base_delay,
            max_delay=max_delay,
            multiplier=multiplier,
            jitter=jitter,
            strategy=backoff_strategy
        )

        retry_config = RetryConfig(
            max_attempts=max_attempts,
            backoff_config=backoff_config,
            retryable_exceptions=exceptions,
            stop_exceptions=stop_exceptions,
            timeout=timeout,
            enable_dead_letter=enable_dead_letter,
            retry_condition=retry_condition
        )

        # Create retry manager
        manager_name = name or func.__name__
        retry_manager = RetryManager(retry_config, name=manager_name)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_manager.aexecute(func, *args, **kwargs)

        # Attach retry manager for metrics access
        wrapper._retry_manager = retry_manager

        return wrapper

    return decorator


def database_retry(max_attempts: int = 5,
                  base_delay: float = 0.5,
                  max_delay: float = 30.0):
    """
    Specialized retry decorator for database operations
    """
    from psycopg import OperationalError as PsycopgOperationalError
    from psycopg.errors import IntegrityError as PsycopgIntegrityError, ProgrammingError as PsycopgProgrammingError
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
            ConnectionError
        ),
        stop_exceptions=(
            PsycopgIntegrityError,
            PsycopgProgrammingError
        ),
        name="database_retry"
    )


def api_retry(max_attempts: int = 3,
              base_delay: float = 1.0,
              max_delay: float = 60.0,
              timeout: float = 30.0):
    """
    Specialized retry decorator for API calls
    """
    import requests

    return retry(
        max_attempts=max_attempts,
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        base_delay=base_delay,
        max_delay=max_delay,
        timeout=timeout,
        exceptions=(
            requests.RequestException,
            requests.Timeout,
            requests.ConnectionError,
            ConnectionError,
            TimeoutError
        ),
        stop_exceptions=(
            requests.HTTPError,  # 4xx client errors shouldn't retry
        ),
        name="api_retry"
    )


def get_retry_metrics(func: Callable) -> Optional[dict]:
    """
    Get retry metrics from a decorated function

    Args:
        func: Function decorated with @retry or @async_retry

    Returns:
        Dictionary with retry metrics or None if not decorated
    """
    retry_manager = getattr(func, '_retry_manager', None)
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
    retry_manager = getattr(func, '_retry_manager', None)
    if retry_manager:
        retry_manager.reset_metrics()
        return True
    return False
