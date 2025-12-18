"""
Async Context Manager for Safe Task Creation

Provides safe asyncio task creation that works in both web contexts (FastAPI)
and worker contexts (Celery), with proper event loop management.

Key Features:
- Automatic event loop detection and creation
- Safe task creation for web and worker environments
- Fallback mechanisms for sync-only environments
- Task monitoring and cleanup
- Memory leak prevention
"""

import asyncio
import logging
import threading
from typing import Coroutine, Optional, Any, Dict, Set
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
import functools

logger = logging.getLogger(__name__)


class AsyncTaskTracker:
    """Tracks async tasks to prevent memory leaks and orphaned tasks."""

    def __init__(self):
        self._tasks: Set[asyncio.Task] = set()
        self._task_metadata: Dict[asyncio.Task, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def track_task(
        self, task: asyncio.Task, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Track a task for monitoring and cleanup."""
        with self._lock:
            self._tasks.add(task)
            if metadata:
                self._task_metadata[task] = metadata

            # Clean up completed tasks
            task.add_done_callback(self._task_completed)

    def _task_completed(self, task: asyncio.Task) -> None:
        """Called when a task completes."""
        with self._lock:
            self._tasks.discard(task)
            self._task_metadata.pop(task, None)

    def get_active_tasks(self) -> Dict[str, Any]:
        """Get information about active tasks."""
        with self._lock:
            return {
                "active_count": len(self._tasks),
                "tasks": [
                    {
                        "task_id": id(task),
                        "done": task.done(),
                        "cancelled": task.cancelled(),
                        "metadata": self._task_metadata.get(task, {}),
                    }
                    for task in self._tasks
                ],
            }

    async def cleanup_all(self) -> None:
        """Cancel all tracked tasks."""
        with self._lock:
            tasks = list(self._tasks)

        for task in tasks:
            if not task.done():
                task.cancel()

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(f"Cleaned up {len(tasks)} async tasks")


# Global task tracker instance
task_tracker = AsyncTaskTracker()


class EventLoopContext:
    """Manages event loop context for different execution environments."""

    def __init__(self):
        self._thread_loops: Dict[threading.Thread, asyncio.AbstractEventLoop] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="async_context"
        )

    def get_or_create_event_loop(self) -> asyncio.AbstractEventLoop:
        """
        Get existing event loop or create new one safely.

        Returns:
            asyncio.AbstractEventLoop: Event loop for current context
        """
        try:
            # Try to get existing loop
            loop = asyncio.get_running_loop()
            logger.debug("Using existing event loop")
            return loop
        except RuntimeError:
            # No running loop, need to create one
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    raise RuntimeError("Event loop is closed")
                logger.debug("Using existing event loop (not running)")
                return loop
            except RuntimeError:
                # Create new event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                logger.info("Created new event loop for thread")
                return loop

    def is_event_loop_running(self) -> bool:
        """Check if an event loop is currently running."""
        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            return False

    def is_main_thread(self) -> bool:
        """Check if we're in the main thread."""
        return threading.current_thread() is threading.main_thread()

    def cleanup(self) -> None:
        """Cleanup resources."""
        self._executor.shutdown(wait=True)
        logger.info("EventLoopContext cleanup completed")


# Global event loop context
event_loop_context = EventLoopContext()


def safe_create_task(
    coro: Coroutine,
    name: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    fallback_sync: bool = False,
) -> Optional[asyncio.Task]:
    """
    Safely create an asyncio task with proper event loop context.

    Args:
        coro: Coroutine to run as task
        name: Optional task name for debugging
        context: Optional context metadata
        fallback_sync: If True, run synchronously if no event loop available

    Returns:
        asyncio.Task if successful, None if failed
    """
    try:
        # Try to get running loop first
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(coro, name=name)
            logger.debug(f"Created task '{name}' in running loop")
        except RuntimeError:
            # No running loop, handle based on environment
            if fallback_sync:
                # Run synchronously as fallback
                logger.warning(
                    f"No event loop available, running task '{name}' synchronously"
                )
                try:
                    asyncio.run(coro)
                    return None  # Can't return task for sync execution
                except Exception as e:
                    logger.error(f"Sync execution failed for task '{name}': {e}")
                    return None
            else:
                # Create loop and task
                loop = event_loop_context.get_or_create_event_loop()
                task = loop.create_task(coro, name=name)
                logger.debug(f"Created task '{name}' in new loop")

        # Track the task
        metadata = {
            "name": name,
            "created_at": asyncio.get_event_loop().time(),
            "context": context or {},
        }
        task_tracker.track_task(task, metadata)

        return task

    except Exception as e:
        logger.error(f"Failed to create task '{name}': {e}")
        return None


def safe_run_coroutine(
    coro: Coroutine, timeout: Optional[float] = None, fallback_sync: bool = True
) -> Any:
    """
    Safely run a coroutine in the appropriate context.

    Args:
        coro: Coroutine to run
        timeout: Optional timeout in seconds
        fallback_sync: Run synchronously if no async context available

    Returns:
        Coroutine result
    """
    try:
        # Check if we're already in an async context
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context, can't use asyncio.run()
            task = loop.create_task(coro)
            if timeout:
                return asyncio.wait_for(task, timeout=timeout)
            return task
        except RuntimeError:
            # No running loop, safe to use asyncio.run()
            try:
                if timeout:

                    async def timed_coro():
                        return await asyncio.wait_for(coro, timeout=timeout)

                    return asyncio.run(timed_coro())
                else:
                    return asyncio.run(coro)
            except asyncio.TimeoutError:
                logger.error(f"Coroutine execution timed out after {timeout} seconds")
                raise
            except Exception as e:
                logger.error(f"Failed to run coroutine with asyncio.run: {e}")
                # If asyncio.run fails, we need to handle this gracefully
                if fallback_sync:
                    logger.warning(
                        "asyncio.run failed, attempting synchronous fallback"
                    )
                    raise RuntimeError(
                        "Async execution failed and sync fallback not implemented"
                    )
                raise

    except Exception as e:
        logger.error(f"Failed to run coroutine: {e}")
        if fallback_sync:
            logger.warning("Attempting synchronous fallback")
            # This is a last resort and may not work for all coroutines
            raise RuntimeError(
                "Async execution failed and sync fallback not implemented"
            )
        raise


@asynccontextmanager
async def async_context():
    """
    Async context manager for safe async operations.

    Usage:
        async with async_context():
            task = safe_create_task(my_coroutine())
            await task
    """
    loop = event_loop_context.get_or_create_event_loop()
    try:
        yield loop
    finally:
        # Cleanup any remaining tasks
        await task_tracker.cleanup_all()


class CeleryAsyncMixin:
    """
    Mixin for Celery tasks that need async capabilities.

    Usage:
        from celery import Task

        class AsyncTask(CeleryAsyncMixin, Task):
            def run(self, *args, **kwargs):
                return self.run_async(self.async_run(*args, **kwargs))

            async def async_run(self, *args, **kwargs):
                # Your async code here
                pass
    """

    def run_async(self, coro: Coroutine, timeout: Optional[float] = None) -> Any:
        """Run a coroutine in Celery task context."""
        try:
            # Check if we're already in an async context
            try:
                asyncio.get_running_loop()
                # We're in an async context, can't use run_until_complete
                logger.error("Cannot use run_async from within an async context")
                raise RuntimeError(
                    "run_async called from async context - use await instead"
                )
            except RuntimeError:
                # No running loop, safe to proceed
                pass

            # Ensure we have an event loop
            loop = event_loop_context.get_or_create_event_loop()

            # Always use run_until_complete since we verified no running loop
            if timeout:

                async def timed_coro():
                    return await asyncio.wait_for(coro, timeout=timeout)

                return loop.run_until_complete(timed_coro())
            else:
                return loop.run_until_complete(coro)

        except Exception as e:
            logger.error(f"Celery async execution failed: {e}")
            raise


def ensure_async_context(func):
    """
    Decorator to ensure function runs in proper async context.

    Usage:
        @ensure_async_context
        async def my_async_function():
            # This will have proper event loop context
            task = asyncio.create_task(some_coroutine())
            return await task
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        async with async_context():
            return await func(*args, **kwargs)

    return wrapper


def celery_async_task(func):
    """
    Decorator for Celery tasks that use async operations.

    Usage:
        @celery_app.task(bind=True)
        @celery_async_task
        def my_task(self, *args, **kwargs):
            # This can now safely use asyncio.create_task()
            task = safe_create_task(my_coroutine())
            return asyncio.run(some_async_operation())
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Ensure proper event loop context for Celery
        try:
            loop = event_loop_context.get_or_create_event_loop()

            if asyncio.iscoroutinefunction(func):
                # Function is async
                return loop.run_until_complete(func(*args, **kwargs))
            else:
                # Function is sync but may use async operations
                return func(*args, **kwargs)

        except Exception as e:
            logger.error(f"Celery async task failed: {e}")
            raise

    return wrapper


# Health check functions
async def async_health_check() -> Dict[str, Any]:
    """Health check for async context manager."""
    try:
        # Test event loop creation
        event_loop_context.get_or_create_event_loop()

        # Test task creation
        async def test_task():
            return "test_completed"

        task = safe_create_task(test_task(), name="health_check")
        if task:
            result = await task
            success = result == "test_completed"
        else:
            success = False

        # Get task tracker status
        task_status = task_tracker.get_active_tasks()

        return {
            "status": "healthy" if success else "unhealthy",
            "event_loop_running": event_loop_context.is_event_loop_running(),
            "main_thread": event_loop_context.is_main_thread(),
            "task_tracker": task_status,
            "test_task_success": success,
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "event_loop_running": False,
            "task_tracker": {"active_count": 0, "tasks": []},
        }


def sync_health_check() -> Dict[str, Any]:
    """Synchronous health check for environments without async support."""
    try:
        # Basic checks that don't require async
        task_status = task_tracker.get_active_tasks()

        return {
            "status": "healthy",
            "event_loop_running": event_loop_context.is_event_loop_running(),
            "main_thread": event_loop_context.is_main_thread(),
            "task_tracker": task_status,
            "async_support": True,
        }

    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "async_support": False}


# Cleanup function for graceful shutdown
def cleanup_async_context() -> None:
    """Cleanup async context manager resources."""
    try:
        # Run cleanup in sync context
        if event_loop_context.is_event_loop_running():
            loop = asyncio.get_event_loop()
            loop.run_until_complete(task_tracker.cleanup_all())

        event_loop_context.cleanup()
        logger.info("Async context cleanup completed")

    except Exception as e:
        logger.error(f"Async context cleanup failed: {e}")


# Register cleanup with atexit
import atexit

atexit.register(cleanup_async_context)
