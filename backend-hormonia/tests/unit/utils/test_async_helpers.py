"""
Comprehensive unit tests for app.utils.async_helpers module.
Tests async/sync boundary helpers and utilities.
"""
import pytest
import asyncio
import concurrent.futures
from unittest.mock import Mock, patch, MagicMock
import threading
import time
from app.utils.async_helpers import (
    run_async_in_sync,
    run_async_in_thread,
    async_to_sync,
    AsyncContextManager,
    run_async_safe
)


class TestRunAsyncInSync:
    """Test the run_async_in_sync function."""

    def test_run_async_in_sync_success(self):
        """Test running async coroutine successfully in sync context."""
        async def simple_async_func():
            await asyncio.sleep(0.1)
            return "success"

        result = run_async_in_sync(simple_async_func())
        assert result == "success"

    def test_run_async_in_sync_with_timeout(self):
        """Test timeout functionality."""
        async def slow_async_func():
            await asyncio.sleep(2)
            return "should timeout"

        with pytest.raises(TimeoutError, match="Operation timed out after 1 seconds"):
            run_async_in_sync(slow_async_func(), timeout=1)

    def test_run_async_in_sync_with_exception(self):
        """Test exception handling in async function."""
        async def failing_async_func():
            await asyncio.sleep(0.1)
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            run_async_in_sync(failing_async_func())

    def test_run_async_in_sync_with_arguments(self):
        """Test async function with arguments."""
        async def async_func_with_args(x, y, multiplier=1):
            await asyncio.sleep(0.1)
            return (x + y) * multiplier

        result = run_async_in_sync(async_func_with_args(5, 3, multiplier=2))
        assert result == 16

    def test_run_async_in_sync_custom_timeout(self):
        """Test with custom timeout value."""
        async def medium_async_func():
            await asyncio.sleep(1.5)
            return "completed"

        result = run_async_in_sync(medium_async_func(), timeout=2)
        assert result == "completed"

    @patch('asyncio.get_running_loop')
    def test_run_async_in_sync_already_in_async_context(self, mock_get_loop):
        """Test behavior when already in async context."""
        mock_get_loop.return_value = MagicMock()

        async def simple_func():
            return "test"

        with pytest.raises(RuntimeError, match="Cannot run async function in sync context"):
            run_async_in_sync(simple_func())

    def test_run_async_in_sync_immediate_return(self):
        """Test async function that returns immediately."""
        async def immediate_func():
            return "immediate"

        result = run_async_in_sync(immediate_func())
        assert result == "immediate"

    def test_run_async_in_sync_none_return(self):
        """Test async function that returns None."""
        async def none_func():
            await asyncio.sleep(0.1)
            return None

        result = run_async_in_sync(none_func())
        assert result is None

    def test_run_async_in_sync_complex_return(self):
        """Test async function returning complex data types."""
        async def complex_func():
            await asyncio.sleep(0.1)
            return {
                "list": [1, 2, 3],
                "dict": {"nested": "value"},
                "tuple": (4, 5, 6)
            }

        result = run_async_in_sync(complex_func())
        assert result["list"] == [1, 2, 3]
        assert result["dict"]["nested"] == "value"
        assert result["tuple"] == (4, 5, 6)

    @patch('asyncio.new_event_loop')
    def test_run_async_in_sync_loop_cleanup(self, mock_new_loop):
        """Test that event loop is properly cleaned up."""
        mock_loop = MagicMock()
        mock_new_loop.return_value = mock_loop
        mock_loop.run_until_complete.return_value = "result"

        async def test_func():
            return "test"

        with patch('asyncio.set_event_loop') as mock_set_loop:
            result = run_async_in_sync(test_func())

        assert result == "result"
        mock_loop.close.assert_called_once()
        # Should be called twice: once to set the loop, once to clear it
        assert mock_set_loop.call_count == 2
        mock_set_loop.assert_any_call(mock_loop)
        mock_set_loop.assert_any_call(None)

    def test_run_async_in_sync_asyncio_timeout_error(self):
        """Test handling of asyncio.TimeoutError specifically."""
        async def timeout_func():
            await asyncio.sleep(2)

        # Mock asyncio.wait_for to raise TimeoutError
        with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError):
            with pytest.raises(TimeoutError, match="Operation timed out after 1 seconds"):
                run_async_in_sync(timeout_func(), timeout=1)


class TestRunAsyncInThread:
    """Test the run_async_in_thread function."""

    def test_run_async_in_thread_success(self):
        """Test running async coroutine in thread successfully."""
        async def simple_async_func():
            await asyncio.sleep(0.1)
            return "thread_success"

        result = run_async_in_thread(simple_async_func())
        assert result == "thread_success"

    def test_run_async_in_thread_timeout(self):
        """Test timeout in thread execution."""
        async def slow_func():
            await asyncio.sleep(2)
            return "should timeout"

        with pytest.raises(TimeoutError, match="Operation timed out after 1 seconds"):
            run_async_in_thread(slow_func(), timeout=1)

    def test_run_async_in_thread_exception(self):
        """Test exception handling in thread execution."""
        async def failing_func():
            await asyncio.sleep(0.1)
            raise RuntimeError("Thread error")

        with pytest.raises(RuntimeError, match="Thread error"):
            run_async_in_thread(failing_func())

    def test_run_async_in_thread_with_args(self):
        """Test async function with arguments in thread."""
        async def async_add(a, b, factor=1):
            await asyncio.sleep(0.1)
            return (a + b) * factor

        result = run_async_in_thread(async_add(10, 20, factor=2))
        assert result == 60

    def test_run_async_in_thread_isolation(self):
        """Test that thread execution is properly isolated."""
        results = []

        async def async_func(value):
            await asyncio.sleep(0.1)
            results.append(value)
            return value

        # Run multiple async functions in threads concurrently
        import threading
        threads = []

        def run_in_thread(val):
            run_async_in_thread(async_func(val))

        for i in range(3):
            thread = threading.Thread(target=run_in_thread, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(results) == 3
        assert set(results) == {0, 1, 2}

    @patch('concurrent.futures.ThreadPoolExecutor')
    def test_run_async_in_thread_executor_management(self, mock_executor_class):
        """Test proper thread pool executor management."""
        mock_executor = MagicMock()
        mock_future = MagicMock()
        mock_future.result.return_value = "executor_result"
        mock_executor.submit.return_value = mock_future
        mock_executor.__enter__.return_value = mock_executor
        mock_executor.__exit__.return_value = None
        mock_executor_class.return_value = mock_executor

        async def test_func():
            return "test"

        result = run_async_in_thread(test_func())

        assert result == "executor_result"
        mock_executor_class.assert_called_once_with(max_workers=1)
        mock_executor.submit.assert_called_once()
        mock_future.result.assert_called_once_with(timeout=60)

    def test_run_async_in_thread_concurrent_futures_timeout(self):
        """Test handling of concurrent.futures.TimeoutError."""
        async def timeout_func():
            await asyncio.sleep(0.1)

        with patch('concurrent.futures.ThreadPoolExecutor') as mock_executor_class:
            mock_executor = MagicMock()
            mock_future = MagicMock()
            mock_future.result.side_effect = concurrent.futures.TimeoutError()
            mock_executor.submit.return_value = mock_future
            mock_executor.__enter__.return_value = mock_executor
            mock_executor_class.return_value = mock_executor

            with pytest.raises(TimeoutError, match="Operation timed out after 60 seconds"):
                run_async_in_thread(timeout_func())


class TestAsyncToSyncDecorator:
    """Test the async_to_sync decorator."""

    def test_async_to_sync_basic_functionality(self):
        """Test basic decorator functionality."""
        @async_to_sync(timeout=30)
        async def decorated_func():
            await asyncio.sleep(0.1)
            return "decorated_result"

        result = decorated_func()
        assert result == "decorated_result"

    def test_async_to_sync_with_arguments(self):
        """Test decorator with function arguments."""
        @async_to_sync(timeout=30)
        async def decorated_func_with_args(x, y, operation="add"):
            await asyncio.sleep(0.1)
            if operation == "add":
                return x + y
            elif operation == "multiply":
                return x * y
            return 0

        result1 = decorated_func_with_args(5, 3)
        assert result1 == 8

        result2 = decorated_func_with_args(5, 3, operation="multiply")
        assert result2 == 15

    def test_async_to_sync_preserves_metadata(self):
        """Test that decorator preserves function metadata."""
        @async_to_sync(timeout=30)
        async def documented_func():
            """This function has documentation."""
            return "result"

        assert documented_func.__name__ == "documented_func"
        assert "This function has documentation" in documented_func.__doc__

    def test_async_to_sync_preserves_async_func(self):
        """Test that decorator preserves original async function."""
        @async_to_sync(timeout=30)
        async def original_func():
            await asyncio.sleep(0.1)
            return "original"

        assert hasattr(original_func, 'async_func')
        assert asyncio.iscoroutinefunction(original_func.async_func)

    def test_async_to_sync_timeout(self):
        """Test decorator timeout functionality."""
        @async_to_sync(timeout=1)
        async def slow_decorated_func():
            await asyncio.sleep(2)
            return "should timeout"

        with pytest.raises(TimeoutError):
            slow_decorated_func()

    def test_async_to_sync_exception_handling(self):
        """Test decorator exception handling."""
        @async_to_sync(timeout=30)
        async def failing_decorated_func():
            await asyncio.sleep(0.1)
            raise ValueError("Decorator error")

        with pytest.raises(ValueError, match="Decorator error"):
            failing_decorated_func()

    def test_async_to_sync_default_timeout(self):
        """Test decorator with default timeout."""
        @async_to_sync()  # Should use default timeout of 60
        async def default_timeout_func():
            await asyncio.sleep(0.1)
            return "default_timeout"

        result = default_timeout_func()
        assert result == "default_timeout"

    def test_async_to_sync_multiple_calls(self):
        """Test decorator works with multiple calls."""
        call_count = 0

        @async_to_sync(timeout=30)
        async def multi_call_func():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)
            return f"call_{call_count}"

        result1 = multi_call_func()
        assert result1 == "call_1"

        result2 = multi_call_func()
        assert result2 == "call_2"

        assert call_count == 2


class TestAsyncContextManager:
    """Test the AsyncContextManager class."""

    def test_async_context_manager_basic(self):
        """Test basic context manager functionality."""
        async def simple_func():
            await asyncio.sleep(0.1)
            return "context_result"

        with AsyncContextManager() as async_runner:
            result = async_runner.run(simple_func())

        assert result == "context_result"

    def test_async_context_manager_with_timeout(self):
        """Test context manager with custom timeout."""
        async def quick_func():
            await asyncio.sleep(0.1)
            return "quick_result"

        with AsyncContextManager(timeout=30) as async_runner:
            result = async_runner.run(quick_func())

        assert result == "quick_result"

    def test_async_context_manager_timeout_exceeded(self):
        """Test context manager timeout."""
        async def slow_func():
            await asyncio.sleep(2)
            return "should timeout"

        with AsyncContextManager(timeout=1) as async_runner:
            with pytest.raises(concurrent.futures.TimeoutError):
                async_runner.run(slow_func())

    def test_async_context_manager_exception(self):
        """Test context manager exception handling."""
        async def failing_func():
            await asyncio.sleep(0.1)
            raise RuntimeError("Context error")

        with AsyncContextManager() as async_runner:
            with pytest.raises(RuntimeError, match="Context error"):
                async_runner.run(failing_func())

    def test_async_context_manager_multiple_runs(self):
        """Test multiple runs within same context."""
        async def func_with_value(value):
            await asyncio.sleep(0.1)
            return value * 2

        with AsyncContextManager() as async_runner:
            result1 = async_runner.run(func_with_value(5))
            result2 = async_runner.run(func_with_value(10))

        assert result1 == 10
        assert result2 == 20

    def test_async_context_manager_run_without_enter(self):
        """Test running without entering context."""
        async def test_func():
            return "test"

        manager = AsyncContextManager()
        with pytest.raises(RuntimeError, match="AsyncContextManager not entered"):
            manager.run(test_func())

    def test_async_context_manager_resource_cleanup(self):
        """Test proper resource cleanup."""
        manager = AsyncContextManager()

        # Enter context
        result = manager.__enter__()
        assert result is manager
        assert manager.thread_executor is not None

        # Exit context
        exit_result = manager.__exit__(None, None, None)
        assert exit_result is False  # Don't suppress exceptions

    @patch('concurrent.futures.ThreadPoolExecutor')
    def test_async_context_manager_executor_shutdown(self, mock_executor_class):
        """Test executor shutdown on context exit."""
        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        with AsyncContextManager():
            pass

        mock_executor.shutdown.assert_called_once_with(wait=True)


class TestRunAsyncSafe:
    """Test the run_async_safe function."""

    def test_run_async_safe_in_sync_context(self):
        """Test run_async_safe in synchronous context."""
        async def simple_func():
            await asyncio.sleep(0.1)
            return "sync_context_result"

        result = run_async_safe(simple_func())
        assert result == "sync_context_result"

    @patch('asyncio.get_running_loop')
    def test_run_async_safe_in_async_context(self, mock_get_loop):
        """Test run_async_safe in asynchronous context."""
        mock_loop = MagicMock()
        mock_get_loop.return_value = mock_loop

        async def test_func():
            return "async_context"

        with patch('asyncio.create_task') as mock_create_task:
            mock_task = MagicMock()
            mock_create_task.return_value = mock_task

            result = run_async_safe(test_func())

            mock_create_task.assert_called_once()
            assert result == mock_task

    def test_run_async_safe_with_timeout(self):
        """Test run_async_safe with custom timeout."""
        async def func_with_delay():
            await asyncio.sleep(0.5)
            return "timeout_test"

        result = run_async_safe(func_with_delay(), timeout=2)
        assert result == "timeout_test"

    def test_run_async_safe_timeout_exceeded(self):
        """Test run_async_safe timeout in sync context."""
        async def slow_func():
            await asyncio.sleep(2)
            return "should timeout"

        with pytest.raises(TimeoutError):
            run_async_safe(slow_func(), timeout=1)

    def test_run_async_safe_exception_handling(self):
        """Test run_async_safe exception handling in sync context."""
        async def failing_func():
            await asyncio.sleep(0.1)
            raise ValueError("Safe run error")

        with pytest.raises(ValueError, match="Safe run error"):
            run_async_safe(failing_func())

    @patch('asyncio.get_running_loop', side_effect=RuntimeError("No loop"))
    def test_run_async_safe_fallback_to_thread(self, mock_get_loop):
        """Test that run_async_safe falls back to thread execution."""
        async def fallback_func():
            await asyncio.sleep(0.1)
            return "fallback_result"

        with patch('app.utils.async_helpers.run_async_in_thread') as mock_run_in_thread:
            mock_run_in_thread.return_value = "mocked_result"

            result = run_async_safe(fallback_func(), timeout=30)

            mock_run_in_thread.assert_called_once()
            assert result == "mocked_result"


class TestAsyncHelpersEdgeCases:
    """Test edge cases and error scenarios."""

    def test_coroutine_cleanup_on_exception(self):
        """Test proper coroutine cleanup when exceptions occur."""
        async def exception_func():
            await asyncio.sleep(0.1)
            raise RuntimeError("Cleanup test")

        # Test with run_async_in_sync
        with pytest.raises(RuntimeError):
            run_async_in_sync(exception_func())

        # Test with run_async_in_thread
        with pytest.raises(RuntimeError):
            run_async_in_thread(exception_func())

    def test_zero_timeout(self):
        """Test behavior with zero timeout."""
        async def any_func():
            await asyncio.sleep(0.1)
            return "should timeout immediately"

        with pytest.raises(TimeoutError):
            run_async_in_sync(any_func(), timeout=0)

        with pytest.raises(TimeoutError):
            run_async_in_thread(any_func(), timeout=0)

    def test_very_long_timeout(self):
        """Test behavior with very long timeout."""
        async def quick_func():
            return "quick"

        result1 = run_async_in_sync(quick_func(), timeout=3600)
        assert result1 == "quick"

        result2 = run_async_in_thread(quick_func(), timeout=3600)
        assert result2 == "quick"

    def test_concurrent_operations(self):
        """Test multiple concurrent async operations."""
        results = []

        async def concurrent_func(value):
            await asyncio.sleep(0.1)
            results.append(value)
            return value

        # Run multiple operations concurrently using threads
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(run_async_in_thread, concurrent_func(i))
                for i in range(3)
            ]

            completed_results = [future.result() for future in futures]

        assert len(results) == 3
        assert set(results) == {0, 1, 2}
        assert set(completed_results) == {0, 1, 2}

    def test_nested_async_calls(self):
        """Test nested async function calls."""
        async def inner_async(value):
            await asyncio.sleep(0.1)
            return value * 2

        async def outer_async(value):
            inner_result = await inner_async(value)
            await asyncio.sleep(0.1)
            return inner_result + 1

        result = run_async_in_sync(outer_async(5))
        assert result == 11  # (5 * 2) + 1

    def test_memory_usage_with_large_returns(self):
        """Test memory handling with large return values."""
        async def large_data_func():
            await asyncio.sleep(0.1)
            return list(range(10000))  # Large list

        result = run_async_in_sync(large_data_func())
        assert len(result) == 10000
        assert result[0] == 0
        assert result[-1] == 9999

    def test_exception_preservation(self):
        """Test that exception details are preserved."""
        async def detailed_exception_func():
            await asyncio.sleep(0.1)
            raise ValueError("Detailed error with traceback")

        try:
            run_async_in_sync(detailed_exception_func())
            assert False, "Should have raised exception"
        except ValueError as e:
            assert str(e) == "Detailed error with traceback"
            assert e.__class__ == ValueError

    def test_async_generator_handling(self):
        """Test behavior with async generators (should not work directly)."""
        async def async_gen():
            for i in range(3):
                yield i
                await asyncio.sleep(0.1)

        # Async generators return async generator objects, not coroutines
        # This should fail gracefully
        try:
            # This will fail because async_gen() returns an async generator, not a coroutine
            result = run_async_in_sync(async_gen())
            assert False, "Should have failed with async generator"
        except Exception:
            # Expected to fail - async generators need different handling
            pass

    @patch('logging.getLogger')
    def test_logging_on_errors(self, mock_get_logger):
        """Test that errors are properly logged."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        async def logging_test_func():
            await asyncio.sleep(2)
            return "timeout"

        with pytest.raises(TimeoutError):
            run_async_in_sync(logging_test_func(), timeout=1)

        # Verify error was logged
        mock_logger.error.assert_called()
        error_calls = mock_logger.error.call_args_list
        assert any("timed out after 1 seconds" in str(call) for call in error_calls)