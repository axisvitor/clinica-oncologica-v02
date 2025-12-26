"""
Centralized Executor Manager

This module provides a centralized management of ThreadPoolExecutors
to reduce thread pool fragmentation and improve resource utilization.

Problem:
- The codebase had 22+ ThreadPoolExecutors scattered across different modules
- Each creating 4-5 threads = 80-110 threads total
- This causes resource contention and makes lifecycle management difficult

Solution:
- Consolidate to ~8 shared executors based on workload type
- Provide lifecycle management (startup/shutdown)
- Enable proper monitoring and resource tracking

Executor Types:
1. io_executor: General I/O operations (DB, network, file)
2. cpu_executor: CPU-bound operations (computation, serialization)
3. cache_executor: Cache operations (Redis, local cache)
4. async_bridge_executor: Running async code from sync contexts
5. notification_executor: Message delivery (WhatsApp, email)
6. event_executor: Event broadcasting and WebSocket
7. validation_executor: Data validation and integrity checks
8. background_executor: Low-priority background tasks

Usage:
    from app.core.executors import get_io_executor, get_cache_executor

    # Use shared executor instead of creating new ones
    executor = get_io_executor()
    future = executor.submit(some_blocking_function)
"""

from __future__ import annotations

import atexit
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Callable, Dict, Optional, TypeVar
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ExecutorConfig:
    """Configuration for executor pool sizes."""

    # I/O bound operations (larger pool for blocking I/O)
    IO_EXECUTOR_WORKERS = 8

    # CPU bound operations (smaller pool, matches CPU cores typically)
    CPU_EXECUTOR_WORKERS = 4

    # Cache operations (moderate pool for Redis/cache ops)
    CACHE_EXECUTOR_WORKERS = 4

    # Async bridge (running async from sync contexts)
    ASYNC_BRIDGE_WORKERS = 4

    # Notification delivery
    NOTIFICATION_EXECUTOR_WORKERS = 5

    # Event broadcasting
    EVENT_EXECUTOR_WORKERS = 4

    # Validation operations
    VALIDATION_EXECUTOR_WORKERS = 4

    # Background tasks (low priority)
    BACKGROUND_EXECUTOR_WORKERS = 3


class ExecutorManager:
    """
    Centralized manager for all thread pool executors.

    This singleton class manages the lifecycle of all shared executors,
    providing proper initialization and shutdown handling.

    Thread Safety:
        All operations are thread-safe using locks.

    Lifecycle:
        - Executors are created lazily on first access
        - Shutdown is handled via atexit registration
        - Can be manually shutdown via shutdown_all()

    Usage:
        manager = ExecutorManager.get_instance()
        executor = manager.get_io_executor()
    """

    _instance: Optional["ExecutorManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "ExecutorManager":
        """Singleton pattern for executor manager."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize executor manager."""
        if hasattr(self, "_initialized") and self._initialized:
            return

        self._executors: Dict[str, ThreadPoolExecutor] = {}
        self._executor_lock = threading.Lock()
        self._shutdown = False
        self._initialized = True

        # Register cleanup on interpreter shutdown
        atexit.register(self._cleanup)

        logger.info("ExecutorManager initialized")

    @classmethod
    def get_instance(cls) -> "ExecutorManager":
        """Get singleton instance of ExecutorManager."""
        return cls()

    def _create_executor(
        self,
        name: str,
        max_workers: int,
        thread_name_prefix: str,
    ) -> ThreadPoolExecutor:
        """
        Create a new executor with the given configuration.

        Args:
            name: Unique name for the executor
            max_workers: Maximum number of worker threads
            thread_name_prefix: Prefix for thread names

        Returns:
            Configured ThreadPoolExecutor
        """
        executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix,
        )
        logger.info(
            f"Created executor: {name} (workers={max_workers}, prefix={thread_name_prefix})"
        )
        return executor

    def _get_or_create(
        self,
        name: str,
        max_workers: int,
        thread_name_prefix: str,
    ) -> ThreadPoolExecutor:
        """
        Get existing executor or create new one.

        Thread-safe lazy initialization of executors.

        Args:
            name: Executor name
            max_workers: Worker count
            thread_name_prefix: Thread prefix

        Returns:
            ThreadPoolExecutor instance

        Raises:
            RuntimeError: If manager has been shutdown
        """
        if self._shutdown:
            raise RuntimeError("ExecutorManager has been shutdown")

        with self._executor_lock:
            if name not in self._executors:
                self._executors[name] = self._create_executor(
                    name, max_workers, thread_name_prefix
                )
            return self._executors[name]

    # =========================================================================
    # Public Executor Accessors
    # =========================================================================

    def get_io_executor(self) -> ThreadPoolExecutor:
        """
        Get executor for general I/O operations.

        Use for:
        - Database operations
        - File I/O
        - Network calls
        - Any blocking I/O
        """
        return self._get_or_create(
            "io",
            ExecutorConfig.IO_EXECUTOR_WORKERS,
            "io_pool",
        )

    def get_cpu_executor(self) -> ThreadPoolExecutor:
        """
        Get executor for CPU-bound operations.

        Use for:
        - Computation-heavy tasks
        - Serialization/deserialization
        - Data transformation
        """
        return self._get_or_create(
            "cpu",
            ExecutorConfig.CPU_EXECUTOR_WORKERS,
            "cpu_pool",
        )

    def get_cache_executor(self) -> ThreadPoolExecutor:
        """
        Get executor for cache operations.

        Use for:
        - Redis operations
        - Cache invalidation
        - Cache warming
        """
        return self._get_or_create(
            "cache",
            ExecutorConfig.CACHE_EXECUTOR_WORKERS,
            "cache_pool",
        )

    def get_async_bridge_executor(self) -> ThreadPoolExecutor:
        """
        Get executor for async-to-sync bridging.

        Use for:
        - Running async coroutines from sync contexts
        - Event loop management in worker threads
        """
        return self._get_or_create(
            "async_bridge",
            ExecutorConfig.ASYNC_BRIDGE_WORKERS,
            "async_bridge",
        )

    def get_notification_executor(self) -> ThreadPoolExecutor:
        """
        Get executor for notification delivery.

        Use for:
        - WhatsApp message sending
        - Email delivery
        - Push notifications
        """
        return self._get_or_create(
            "notification",
            ExecutorConfig.NOTIFICATION_EXECUTOR_WORKERS,
            "notification",
        )

    def get_event_executor(self) -> ThreadPoolExecutor:
        """
        Get executor for event processing.

        Use for:
        - Event broadcasting
        - WebSocket event handling
        - Async event handlers
        """
        return self._get_or_create(
            "event",
            ExecutorConfig.EVENT_EXECUTOR_WORKERS,
            "event_pool",
        )

    def get_validation_executor(self) -> ThreadPoolExecutor:
        """
        Get executor for validation operations.

        Use for:
        - Data validation
        - Integrity checks
        - Format verification
        """
        return self._get_or_create(
            "validation",
            ExecutorConfig.VALIDATION_EXECUTOR_WORKERS,
            "validation",
        )

    def get_background_executor(self) -> ThreadPoolExecutor:
        """
        Get executor for background tasks.

        Use for:
        - Low-priority operations
        - Cleanup tasks
        - Non-urgent processing
        """
        return self._get_or_create(
            "background",
            ExecutorConfig.BACKGROUND_EXECUTOR_WORKERS,
            "background",
        )

    # =========================================================================
    # Lifecycle Management
    # =========================================================================

    def shutdown_all(self, wait: bool = True, timeout: Optional[float] = 30.0) -> None:
        """
        Shutdown all executors gracefully.

        Args:
            wait: Whether to wait for pending tasks to complete
            timeout: Maximum time to wait for shutdown (per executor)
        """
        if self._shutdown:
            logger.warning("ExecutorManager already shutdown")
            return

        self._shutdown = True
        logger.info("Shutting down all executors...")

        with self._executor_lock:
            for name, executor in self._executors.items():
                try:
                    logger.debug(f"Shutting down executor: {name}")
                    executor.shutdown(wait=wait)
                    logger.info(f"Executor shutdown complete: {name}")
                except Exception as e:
                    logger.error(f"Error shutting down executor {name}: {e}")

            self._executors.clear()

        logger.info("All executors shutdown complete")

    def _cleanup(self) -> None:
        """Cleanup handler for atexit."""
        try:
            self.shutdown_all(wait=True, timeout=10.0)
        except Exception as e:
            logger.error(f"Error during executor cleanup: {e}")

    # =========================================================================
    # Monitoring & Stats
    # =========================================================================

    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all executors.

        Returns:
            Dictionary mapping executor names to their stats
        """
        stats = {}

        with self._executor_lock:
            for name, executor in self._executors.items():
                try:
                    stats[name] = {
                        "max_workers": executor._max_workers,
                        "shutdown": executor._shutdown,
                        "thread_name_prefix": executor._thread_name_prefix,
                    }
                except Exception as e:
                    stats[name] = {"error": str(e)}

        return stats

    def get_active_executor_count(self) -> int:
        """Get count of active executors."""
        with self._executor_lock:
            return len(self._executors)

    def get_total_thread_count(self) -> int:
        """Get total thread count across all executors."""
        total = 0
        with self._executor_lock:
            for executor in self._executors.values():
                total += executor._max_workers
        return total


# =============================================================================
# Module-level Convenience Functions
# =============================================================================

def get_executor_manager() -> ExecutorManager:
    """Get the singleton ExecutorManager instance."""
    return ExecutorManager.get_instance()


def get_io_executor() -> ThreadPoolExecutor:
    """Get the shared I/O executor."""
    return get_executor_manager().get_io_executor()


def get_cpu_executor() -> ThreadPoolExecutor:
    """Get the shared CPU executor."""
    return get_executor_manager().get_cpu_executor()


def get_cache_executor() -> ThreadPoolExecutor:
    """Get the shared cache executor."""
    return get_executor_manager().get_cache_executor()


def get_async_bridge_executor() -> ThreadPoolExecutor:
    """Get the shared async bridge executor."""
    return get_executor_manager().get_async_bridge_executor()


def get_notification_executor() -> ThreadPoolExecutor:
    """Get the shared notification executor."""
    return get_executor_manager().get_notification_executor()


def get_event_executor() -> ThreadPoolExecutor:
    """Get the shared event executor."""
    return get_executor_manager().get_event_executor()


def get_validation_executor() -> ThreadPoolExecutor:
    """Get the shared validation executor."""
    return get_executor_manager().get_validation_executor()


def get_background_executor() -> ThreadPoolExecutor:
    """Get the shared background executor."""
    return get_executor_manager().get_background_executor()


def shutdown_executors(wait: bool = True) -> None:
    """Shutdown all shared executors."""
    get_executor_manager().shutdown_all(wait=wait)


def get_executor_stats() -> Dict[str, Dict[str, Any]]:
    """Get statistics for all shared executors."""
    return get_executor_manager().get_stats()


# =============================================================================
# Decorators for Executor Usage
# =============================================================================

def run_in_io_executor(func: Callable[..., T]) -> Callable[..., Future[T]]:
    """
    Decorator to run a function in the I/O executor.

    Usage:
        @run_in_io_executor
        def blocking_io_operation():
            # This runs in the I/O thread pool
            return result

        future = blocking_io_operation()
        result = future.result()
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Future[T]:
        executor = get_io_executor()
        return executor.submit(func, *args, **kwargs)
    return wrapper


def run_in_cache_executor(func: Callable[..., T]) -> Callable[..., Future[T]]:
    """
    Decorator to run a function in the cache executor.

    Usage:
        @run_in_cache_executor
        def cache_operation():
            # This runs in the cache thread pool
            return result
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Future[T]:
        executor = get_cache_executor()
        return executor.submit(func, *args, **kwargs)
    return wrapper


def run_in_background(func: Callable[..., T]) -> Callable[..., Future[T]]:
    """
    Decorator to run a function in the background executor.

    Usage:
        @run_in_background
        def low_priority_task():
            # This runs in the background thread pool
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Future[T]:
        executor = get_background_executor()
        return executor.submit(func, *args, **kwargs)
    return wrapper


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Manager class
    "ExecutorManager",
    "ExecutorConfig",

    # Get manager instance
    "get_executor_manager",

    # Executor accessors
    "get_io_executor",
    "get_cpu_executor",
    "get_cache_executor",
    "get_async_bridge_executor",
    "get_notification_executor",
    "get_event_executor",
    "get_validation_executor",
    "get_background_executor",

    # Lifecycle
    "shutdown_executors",
    "get_executor_stats",

    # Decorators
    "run_in_io_executor",
    "run_in_cache_executor",
    "run_in_background",
]
