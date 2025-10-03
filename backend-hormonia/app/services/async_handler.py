"""
Proper async/sync bridge for FlowEngine operations.
Solves the event loop management issues in the original FlowEngine.
"""
import asyncio
import logging
import threading
from typing import Any, Callable, Coroutine, Optional, TypeVar, Union
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
import weakref

logger = logging.getLogger(__name__)

T = TypeVar('T')


class AsyncHandler:
    """
    Thread-safe handler for running async operations from sync context.

    Solves the problematic patterns:
    1. No more asyncio.new_event_loop() in sync context
    2. Proper event loop cleanup
    3. Thread-safe async operation handling
    4. Resource leak prevention
    """

    _instance: Optional['AsyncHandler'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'AsyncHandler':
        """Singleton pattern for global async handler."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize async handler with proper resource management."""
        if hasattr(self, '_initialized'):
            return

        self._executor = ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="async_handler"
        )
        self._loop = None
        self._loop_thread = None
        self._shutdown = False
        self._running_tasks = weakref.WeakSet()
        self._initialized = True

        # Start background event loop
        self._start_background_loop()

    def _start_background_loop(self):
        """Start dedicated event loop in background thread."""
        def run_loop():
            """Run event loop in dedicated thread."""
            try:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
                logger.info("Background event loop started")

                # Keep loop running until shutdown
                self._loop.run_forever()
            except Exception as e:
                logger.error(f"Error in background event loop: {e}")
            finally:
                # Cleanup
                try:
                    if self._loop and not self._loop.is_closed():
                        self._loop.close()
                    logger.info("Background event loop closed")
                except Exception as e:
                    logger.error(f"Error closing background loop: {e}")

        self._loop_thread = threading.Thread(
            target=run_loop,
            name="async_handler_loop",
            daemon=True
        )
        self._loop_thread.start()

        # Wait for loop to be ready
        timeout = 5.0
        while timeout > 0 and self._loop is None:
            threading.Event().wait(0.1)
            timeout -= 0.1

        if self._loop is None:
            raise RuntimeError("Failed to start background event loop")

    def run_async(self, coro: Coroutine[Any, Any, T], timeout: Optional[float] = None) -> T:
        """
        Run async coroutine from sync context safely.

        Args:
            coro: Coroutine to run
            timeout: Optional timeout in seconds

        Returns:
            Result of the coroutine

        Raises:
            RuntimeError: If handler is shutdown or loop unavailable
            asyncio.TimeoutError: If operation times out
        """
        if self._shutdown or self._loop is None:
            raise RuntimeError("AsyncHandler is shutdown or unavailable")

        if self._loop.is_closed():
            raise RuntimeError("Background event loop is closed")

        # Check if we're already in the event loop thread
        if threading.current_thread() == self._loop_thread:
            # We're in the event loop thread, can't block
            raise RuntimeError("Cannot run_async from within the async handler loop")

        # Submit coroutine to background loop
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)

        try:
            # Wait for result with timeout
            result = future.result(timeout=timeout)
            return result
        except Exception as e:
            # Cancel the coroutine if still running
            if not future.done():
                future.cancel()
            raise

    def run_async_safe(
        self,
        coro: Coroutine[Any, Any, T],
        timeout: Optional[float] = 30.0,
        fallback_value: Optional[T] = None
    ) -> Optional[T]:
        """
        Run async coroutine with error handling and fallback.

        Args:
            coro: Coroutine to run
            timeout: Timeout in seconds (default: 30s)
            fallback_value: Value to return if operation fails

        Returns:
            Result of coroutine or fallback value
        """
        try:
            return self.run_async(coro, timeout=timeout)
        except Exception as e:
            logger.error(f"Async operation failed safely: {e}")
            return fallback_value

    def schedule_async(self, coro: Coroutine[Any, Any, T]) -> asyncio.Future[T]:
        """
        Schedule async coroutine without waiting for result.

        Args:
            coro: Coroutine to schedule

        Returns:
            Future representing the scheduled operation
        """
        if self._shutdown or self._loop is None:
            raise RuntimeError("AsyncHandler is shutdown or unavailable")

        # Schedule on background loop
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        self._running_tasks.add(future)
        return future

    def shutdown(self, timeout: float = 10.0):
        """
        Shutdown async handler and cleanup resources.

        Args:
            timeout: Maximum time to wait for cleanup
        """
        if self._shutdown:
            return

        logger.info("Shutting down AsyncHandler...")
        self._shutdown = True

        try:
            # Stop background loop
            if self._loop and not self._loop.is_closed():
                self._loop.call_soon_threadsafe(self._loop.stop)

            # Wait for loop thread to finish
            if self._loop_thread and self._loop_thread.is_alive():
                self._loop_thread.join(timeout=timeout)

            # Shutdown executor
            self._executor.shutdown(wait=True, timeout=timeout)

            logger.info("AsyncHandler shutdown complete")

        except Exception as e:
            logger.error(f"Error during AsyncHandler shutdown: {e}")

    def __del__(self):
        """Cleanup resources on deletion."""
        if hasattr(self, '_shutdown') and not self._shutdown:
            self.shutdown(timeout=5.0)


# Global async handler instance
_async_handler: Optional[AsyncHandler] = None
_handler_lock = threading.Lock()


def get_async_handler() -> AsyncHandler:
    """Get global async handler instance (thread-safe)."""
    global _async_handler
    if _async_handler is None:
        with _handler_lock:
            if _async_handler is None:
                _async_handler = AsyncHandler()
    return _async_handler


# Decorator for sync functions that need to run async code
def run_async_safe(timeout: Optional[float] = 30.0, fallback=None):
    """
    Decorator to safely run async code from sync functions.

    Usage:
        @run_async_safe(timeout=10.0, fallback="default_value")
        async def my_async_operation():
            return await some_async_call()

        # Can be called from sync context
        result = my_async_operation()
    """
    def decorator(async_func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., T]:
        @wraps(async_func)
        def wrapper(*args, **kwargs) -> T:
            handler = get_async_handler()
            coro = async_func(*args, **kwargs)
            return handler.run_async_safe(coro, timeout=timeout, fallback_value=fallback)
        return wrapper
    return decorator


# Context manager for safe async operations
class AsyncContext:
    """
    Context manager for safe async operations in sync code.

    Usage:
        async def my_operation():
            return "result"

        with AsyncContext() as handler:
            result = handler.run(my_operation())
    """

    def __init__(self, timeout: Optional[float] = 30.0):
        """Initialize context with timeout."""
        self.timeout = timeout
        self.handler = None

    def __enter__(self) -> 'AsyncContextRunner':
        """Enter context and return runner."""
        self.handler = get_async_handler()
        return AsyncContextRunner(self.handler, self.timeout)

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context (cleanup handled by global handler)."""
        pass


class AsyncContextRunner:
    """Runner for async operations within AsyncContext."""

    def __init__(self, handler: AsyncHandler, timeout: Optional[float]):
        """Initialize runner."""
        self.handler = handler
        self.timeout = timeout

    def run(self, coro: Coroutine[Any, Any, T]) -> T:
        """Run coroutine with configured timeout."""
        return self.handler.run_async(coro, timeout=self.timeout)

    def run_safe(self, coro: Coroutine[Any, Any, T], fallback=None) -> Optional[T]:
        """Run coroutine safely with fallback."""
        return self.handler.run_async_safe(coro, timeout=self.timeout, fallback_value=fallback)

    def schedule(self, coro: Coroutine[Any, Any, T]) -> asyncio.Future[T]:
        """Schedule coroutine without waiting."""
        return self.handler.schedule_async(coro)


# Cleanup function for application shutdown
def shutdown_async_handler(timeout: float = 10.0):
    """Shutdown global async handler."""
    global _async_handler
    if _async_handler:
        _async_handler.shutdown(timeout=timeout)
        _async_handler = None