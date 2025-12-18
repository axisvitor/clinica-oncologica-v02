"""
Async/Sync boundary helpers for Celery tasks and other sync contexts.
"""

import asyncio
import concurrent.futures
import threading
from typing import Any, Callable, Coroutine, TypeVar
from functools import wraps
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Thread-local storage for event loop caching
_thread_local_loop = threading.local()


def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """
    Get or create a thread-local event loop for reuse.

    This avoids the overhead of creating a new event loop for each
    async call in Celery workers, providing ~2-5ms savings per call.
    """
    if not hasattr(_thread_local_loop, "loop") or _thread_local_loop.loop.is_closed():
        _thread_local_loop.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_thread_local_loop.loop)
    return _thread_local_loop.loop


def run_async(coro: Coroutine[Any, Any, T], timeout: int = 60) -> T:
    """
    Run async coroutine using a cached thread-local event loop.

    This is the RECOMMENDED way to call async functions from Celery tasks.
    It's more efficient than asyncio.run() for repeated calls as it reuses
    the same event loop within a worker thread.

    Performance improvement: ~2-5ms per call vs asyncio.run()

    Args:
        coro: The coroutine to run
        timeout: Timeout in seconds (default 60)

    Returns:
        The result of the coroutine

    Raises:
        TimeoutError: If the coroutine doesn't complete within timeout
        Exception: Any exception raised by the coroutine

    Usage:
        from app.utils.async_helpers import run_async

        # In Celery task
        result = run_async(some_async_function())
    """
    try:
        loop = get_or_create_event_loop()
        return loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))
    except asyncio.TimeoutError:
        logger.error(f"Async operation timed out after {timeout} seconds")
        raise TimeoutError(f"Operation timed out after {timeout} seconds")
    except Exception as e:
        logger.error(f"Error in run_async: {e}")
        raise


def run_async_in_sync(coro: Coroutine[Any, Any, T], timeout: int = 60) -> T:
    """
    Run an async coroutine in a synchronous context safely.

    This is designed for use in Celery tasks and other sync contexts
    where we need to call async functions.

    Args:
        coro: The coroutine to run
        timeout: Timeout in seconds

    Returns:
        The result of the coroutine

    Raises:
        TimeoutError: If the coroutine doesn't complete within timeout
        Exception: Any exception raised by the coroutine
    """
    try:
        # Check if there's already an event loop running
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No event loop running, we can create one
        loop = None

    if loop is not None:
        # We're already in an async context, this shouldn't happen in Celery
        # but handle it gracefully
        raise RuntimeError(
            "Cannot run async function in sync context: already in async context. "
            "Use 'await' directly instead."
        )

    # Create a new event loop for this thread
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)

    try:
        # Run the coroutine with timeout
        return new_loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))
    except asyncio.TimeoutError:
        logger.error(f"Async operation timed out after {timeout} seconds")
        raise TimeoutError(f"Operation timed out after {timeout} seconds")
    except Exception as e:
        logger.error(f"Error running async operation: {e}")
        raise
    finally:
        # Clean up the event loop
        new_loop.close()
        asyncio.set_event_loop(None)


def run_async_in_thread(coro: Coroutine[Any, Any, T], timeout: int = 60) -> T:
    """
    Run an async coroutine in a separate thread with its own event loop.

    This is safer for long-running operations in Celery tasks as it
    completely isolates the async operation.

    Args:
        coro: The coroutine to run
        timeout: Timeout in seconds

    Returns:
        The result of the coroutine

    Raises:
        TimeoutError: If the coroutine doesn't complete within timeout
        Exception: Any exception raised by the coroutine
    """

    def run_in_thread():
        """Function to run in thread with new event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_in_thread)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            logger.error(f"Async operation timed out after {timeout} seconds")
            raise TimeoutError(f"Operation timed out after {timeout} seconds")
        except Exception as e:
            logger.error(f"Error running async operation in thread: {e}")
            raise


def async_to_sync(timeout: int = 60):
    """
    Decorator to convert async functions to sync for use in Celery tasks.

    Usage:
        @async_to_sync(timeout=120)
        async def my_async_function():
            await some_async_operation()

        # Can now be called from sync context
        result = my_async_function()
    """

    def decorator(
        async_func: Callable[..., Coroutine[Any, Any, T]],
    ) -> Callable[..., T]:
        @wraps(async_func)
        def sync_wrapper(*args, **kwargs) -> T:
            coro = async_func(*args, **kwargs)
            return run_async_in_thread(coro, timeout=timeout)

        # Preserve the original async function as an attribute
        sync_wrapper.async_func = async_func
        return sync_wrapper

    return decorator


class AsyncContextManager:
    """
    Context manager for running async operations in sync contexts.

    Usage:
        with AsyncContextManager() as async_runner:
            result = async_runner.run(some_async_function())
    """

    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self.loop = None
        self.thread_executor = None

    def __enter__(self):
        """Enter the context and set up event loop."""
        self.thread_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources."""
        if self.thread_executor:
            self.thread_executor.shutdown(wait=True)
        return False

    def run(self, coro: Coroutine[Any, Any, T]) -> T:
        """Run an async coroutine."""
        if not self.thread_executor:
            raise RuntimeError("AsyncContextManager not entered")

        def run_coro():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

        future = self.thread_executor.submit(run_coro)
        return future.result(timeout=self.timeout)


# Helper functions for common operations


def run_async_safe(coro: Coroutine[Any, Any, T], timeout: int = 60) -> T:
    """
    Safely run an async coroutine from any context.

    Automatically detects if we're in sync or async context and
    handles appropriately.
    """
    try:
        # Check if we're in async context
        asyncio.get_running_loop()
        # We're in async context, create a task
        return asyncio.create_task(coro)
    except RuntimeError:
        # We're in sync context, use thread executor
        return run_async_in_thread(coro, timeout=timeout)
