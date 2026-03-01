"""
Async/Sync boundary helpers for Celery tasks and other sync contexts.
"""

import asyncio
import concurrent.futures
import atexit
import threading
import time
from typing import Any, Callable, Coroutine, Dict, TypeVar
from functools import wraps
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Thread-local storage for event loop caching
_thread_local_loop = threading.local()
_event_loop_registry: Dict[int, asyncio.AbstractEventLoop] = {}
_event_loop_registry_lock = threading.Lock()

# Rotate idle loops to avoid keeping stale loops forever.
_THREAD_LOCAL_LOOP_MAX_IDLE_SECONDS = 30 * 60


def _register_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Register the current thread event loop in thread-local and registry."""
    thread_id = threading.get_ident()
    _thread_local_loop.loop = loop
    _thread_local_loop.last_used = time.monotonic()
    _thread_local_loop.thread_id = thread_id
    with _event_loop_registry_lock:
        _event_loop_registry[thread_id] = loop


def _touch_thread_local_loop() -> None:
    """Refresh current thread loop last-used timestamp."""
    if hasattr(_thread_local_loop, "loop"):
        _thread_local_loop.last_used = time.monotonic()


def _close_event_loop(loop: asyncio.AbstractEventLoop) -> bool:
    """Safely close a non-running event loop and release resources."""
    if loop.is_closed():
        return False

    if loop.is_running():
        logger.debug("Skipping cleanup of running event loop")
        return False

    try:
        pending = asyncio.all_tasks(loop)
    except Exception:
        pending = set()

    for task in pending:
        task.cancel()

    if pending:
        try:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            logger.debug("Ignoring error while draining pending loop tasks", exc_info=True)

    try:
        loop.run_until_complete(loop.shutdown_asyncgens())
    except Exception:
        logger.debug("Ignoring asyncgens shutdown error during loop cleanup", exc_info=True)

    if hasattr(loop, "shutdown_default_executor"):
        try:
            loop.run_until_complete(loop.shutdown_default_executor())
        except Exception:
            logger.debug(
                "Ignoring default executor shutdown error during loop cleanup",
                exc_info=True,
            )

    loop.close()
    return True


def cleanup_event_loop() -> bool:
    """
    Cleanup and detach current thread-local event loop.

    Returns:
        True when a loop was closed by this call.
    """
    loop = getattr(_thread_local_loop, "loop", None)
    thread_id = getattr(_thread_local_loop, "thread_id", threading.get_ident())
    was_closed = False

    if loop is not None:
        was_closed = _close_event_loop(loop)

    with _event_loop_registry_lock:
        _event_loop_registry.pop(thread_id, None)

    for attr in ("loop", "last_used", "thread_id"):
        if hasattr(_thread_local_loop, attr):
            delattr(_thread_local_loop, attr)

    try:
        asyncio.set_event_loop(None)
    except Exception:
        # Not all environments allow detaching event loop from current thread.
        pass

    return was_closed


def cleanup_stale_event_loop(
    max_idle_seconds: int = _THREAD_LOCAL_LOOP_MAX_IDLE_SECONDS,
) -> bool:
    """
    Cleanup the current thread loop when idle for too long.

    Returns:
        True when cleanup happened.
    """
    loop = getattr(_thread_local_loop, "loop", None)
    if loop is None:
        return False

    if loop.is_closed():
        cleanup_event_loop()
        return True

    last_used = getattr(_thread_local_loop, "last_used", None)
    if not isinstance(last_used, (int, float)):
        _touch_thread_local_loop()
        return False

    if max_idle_seconds >= 0 and (time.monotonic() - last_used) >= max_idle_seconds:
        cleanup_event_loop()
        return True

    return False


def cleanup_all_event_loops() -> int:
    """
    Best-effort cleanup for all registered thread-local loops.

    Returns:
        Number of loops closed.
    """
    closed_count = 0
    current_thread_id = threading.get_ident()

    with _event_loop_registry_lock:
        thread_ids = list(_event_loop_registry.keys())

    for thread_id in thread_ids:
        if thread_id == current_thread_id:
            if cleanup_event_loop():
                closed_count += 1
            continue

        with _event_loop_registry_lock:
            loop = _event_loop_registry.pop(thread_id, None)

        if loop is not None and _close_event_loop(loop):
            closed_count += 1

    return closed_count


@atexit.register
def _cleanup_event_loops_on_process_exit() -> None:
    """Close cached event loops during process shutdown."""
    cleanup_all_event_loops()


def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """
    Get or create a thread-local event loop for reuse.

    This avoids the overhead of creating a new event loop for each
    async call in Celery workers, providing ~2-5ms savings per call.
    """
    cleanup_stale_event_loop()

    loop = getattr(_thread_local_loop, "loop", None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _register_event_loop(loop)
        return loop

    asyncio.set_event_loop(loop)
    _touch_thread_local_loop()
    return loop


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
    loop = None
    try:
        loop = get_or_create_event_loop()
        result = loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))
        _touch_thread_local_loop()
        return result
    except asyncio.TimeoutError:
        logger.error(f"Async operation timed out after {timeout} seconds")
        raise TimeoutError(f"Operation timed out after {timeout} seconds")
    except RuntimeError as e:
        # Recover from stale/closed loop references without changing call API.
        if loop is not None and "closed" in str(e).lower():
            cleanup_event_loop()
            fresh_loop = get_or_create_event_loop()
            result = fresh_loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))
            _touch_thread_local_loop()
            return result
        logger.error(f"Error in run_async: {e}")
        raise
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
            asyncio.set_event_loop(None)

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
                asyncio.set_event_loop(None)

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
