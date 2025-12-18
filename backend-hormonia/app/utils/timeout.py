"""
Timeout utilities for external API calls and async operations.
"""

import asyncio
import functools
from typing import TypeVar, Callable
from app.exceptions.external_service import ExternalServiceError

T = TypeVar("T")


def with_timeout(timeout_seconds: int = 30):
    """
    Decorator to add timeout to async functions.

    Args:
        timeout_seconds: Maximum time to wait for function completion

    Raises:
        ExternalServiceError: When function times out
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs), timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                func_name = func.__name__
                raise ExternalServiceError(
                    f"Operation {func_name} timed out after {timeout_seconds} seconds",
                    is_recoverable=True,
                    retry_after=60,
                )

        return wrapper

    return decorator


async def run_with_timeout(
    coro: Callable[..., T], timeout: int = 30, *args, **kwargs
) -> T:
    """
    Run a coroutine with timeout.

    Args:
        coro: Coroutine to run
        timeout: Timeout in seconds
        *args: Positional arguments for coroutine
        **kwargs: Keyword arguments for coroutine

    Returns:
        Result of the coroutine

    Raises:
        ExternalServiceError: When coroutine times out
    """
    try:
        return await asyncio.wait_for(
            coro(*args, **kwargs) if callable(coro) else coro, timeout=timeout
        )
    except asyncio.TimeoutError:
        raise ExternalServiceError(
            f"Operation timed out after {timeout} seconds",
            is_recoverable=True,
            retry_after=60,
        )
