"""
Synchronous executor for testing to avoid SQLite threading issues.

This module provides a synchronous executor that executes tasks immediately
in the current thread, avoiding SQLite's "objects created in a thread can only
be used in that same thread" errors during testing.
"""
from concurrent.futures import Future
from typing import Any, Callable


class SyncExecutor:
    """
    Synchronous executor that mimics ThreadPoolExecutor interface.

    Instead of using threads, this executor runs all tasks synchronously
    in the current thread. This is particularly useful for testing with
    SQLite databases which have strict thread-safety requirements.

    Usage:
        >>> executor = SyncExecutor()
        >>> future = executor.submit(lambda x: x * 2, 5)
        >>> result = future.result()
        >>> print(result)  # 10
    """

    def submit(self, fn: Callable, *args: Any, **kwargs: Any) -> Future:
        """
        Submit a function to be executed synchronously.

        Args:
            fn: The function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            A Future object with the result immediately available
        """
        future = Future()
        try:
            result = fn(*args, **kwargs)
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)
        return future

    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown the executor (no-op for synchronous executor).

        Args:
            wait: Ignored for compatibility with ThreadPoolExecutor interface
        """
        pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown(wait=True)
        return False
