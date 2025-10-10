"""
Comprehensive unit tests for app.utils.timeout module.
Tests timeout decorators and async operation timeout handling.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from app.utils.timeout import with_timeout, run_with_timeout
from app.exceptions.external_service import ExternalServiceError


class TestWithTimeoutDecorator:
    """Test the with_timeout decorator."""

    @pytest.mark.asyncio
    async def test_with_timeout_success(self):
        """Test decorator with function that completes within timeout."""
        @with_timeout(timeout_seconds=5)
        async def fast_function():
            await asyncio.sleep(0.1)  # Complete quickly
            return "success"

        result = await fast_function()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_with_timeout_timeout_exceeded(self):
        """Test decorator with function that exceeds timeout."""
        @with_timeout(timeout_seconds=1)
        async def slow_function():
            await asyncio.sleep(2)  # Takes longer than timeout
            return "should not reach here"

        with pytest.raises(ExternalServiceError) as exc_info:
            await slow_function()

        assert "timed out after 1 seconds" in str(exc_info.value)
        assert exc_info.value.is_recoverable is True
        assert exc_info.value.retry_after == 60

    @pytest.mark.asyncio
    async def test_with_timeout_custom_timeout(self):
        """Test decorator with custom timeout value."""
        @with_timeout(timeout_seconds=2)
        async def medium_function():
            await asyncio.sleep(1.5)  # Within timeout
            return "completed"

        result = await medium_function()
        assert result == "completed"

    @pytest.mark.asyncio
    async def test_with_timeout_zero_timeout(self):
        """Test decorator with very short timeout."""
        @with_timeout(timeout_seconds=0.1)
        async def function_that_times_out():
            await asyncio.sleep(0.5)
            return "should not complete"

        with pytest.raises(ExternalServiceError) as exc_info:
            await function_that_times_out()

        assert "timed out after 0.1 seconds" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_with_timeout_function_raises_exception(self):
        """Test decorator when wrapped function raises exception."""
        @with_timeout(timeout_seconds=5)
        async def function_that_raises():
            await asyncio.sleep(0.1)
            raise ValueError("Original error")

        with pytest.raises(ValueError, match="Original error"):
            await function_that_raises()

    @pytest.mark.asyncio
    async def test_with_timeout_preserves_function_metadata(self):
        """Test decorator preserves original function metadata."""
        @with_timeout(timeout_seconds=5)
        async def documented_function():
            """This function has documentation."""
            return "result"

        assert documented_function.__name__ == "documented_function"
        assert "This function has documentation" in documented_function.__doc__

    @pytest.mark.asyncio
    async def test_with_timeout_with_function_arguments(self):
        """Test decorator with function that takes arguments."""
        @with_timeout(timeout_seconds=5)
        async def function_with_args(x, y, multiplier=1):
            await asyncio.sleep(0.1)
            return (x + y) * multiplier

        result = await function_with_args(5, 3, multiplier=2)
        assert result == 16

    @pytest.mark.asyncio
    async def test_with_timeout_default_timeout(self):
        """Test decorator with default timeout value."""
        @with_timeout()  # Uses default 30 seconds
        async def default_timeout_function():
            await asyncio.sleep(0.1)
            return "success"

        result = await default_timeout_function()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_with_timeout_exception_details(self):
        """Test timeout exception contains correct details."""
        function_name = "test_function"

        @with_timeout(timeout_seconds=1)
        async def test_function():
            await asyncio.sleep(2)
            return "timeout"

        with pytest.raises(ExternalServiceError) as exc_info:
            await test_function()

        error = exc_info.value
        assert function_name in str(error)
        assert "1 seconds" in str(error)
        assert error.is_recoverable is True
        assert error.retry_after == 60

    @pytest.mark.asyncio
    async def test_with_timeout_multiple_calls(self):
        """Test decorator works correctly with multiple calls."""
        @with_timeout(timeout_seconds=2)
        async def reusable_function(delay):
            await asyncio.sleep(delay)
            return f"completed after {delay}s"

        # First call succeeds
        result1 = await reusable_function(0.5)
        assert result1 == "completed after 0.5s"

        # Second call also succeeds
        result2 = await reusable_function(1.0)
        assert result2 == "completed after 1.0s"

        # Third call times out
        with pytest.raises(ExternalServiceError):
            await reusable_function(3.0)


class TestRunWithTimeout:
    """Test the run_with_timeout function."""

    @pytest.mark.asyncio
    async def test_run_with_timeout_success(self):
        """Test running coroutine that completes within timeout."""
        async def fast_coroutine():
            await asyncio.sleep(0.1)
            return "success"

        result = await run_with_timeout(fast_coroutine, timeout=5)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_run_with_timeout_with_args(self):
        """Test running coroutine with arguments."""
        async def coroutine_with_args(x, y):
            await asyncio.sleep(0.1)
            return x * y

        result = await run_with_timeout(coroutine_with_args, 30, 5, 7)
        assert result == 35

    @pytest.mark.asyncio
    async def test_run_with_timeout_with_kwargs(self):
        """Test running coroutine with keyword arguments."""
        async def coroutine_with_kwargs(base, multiplier=1, offset=0):
            await asyncio.sleep(0.1)
            return base * multiplier + offset

        result = await run_with_timeout(
            coroutine_with_kwargs, 30, 10, multiplier=3, offset=5
        )
        assert result == 35

    @pytest.mark.asyncio
    async def test_run_with_timeout_timeout_exceeded(self):
        """Test running coroutine that exceeds timeout."""
        async def slow_coroutine():
            await asyncio.sleep(2)
            return "should not complete"

        with pytest.raises(ExternalServiceError) as exc_info:
            await run_with_timeout(slow_coroutine, timeout=1)

        assert "timed out after 1 seconds" in str(exc_info.value)
        assert exc_info.value.is_recoverable is True
        assert exc_info.value.retry_after == 60

    @pytest.mark.asyncio
    async def test_run_with_timeout_default_timeout(self):
        """Test running coroutine with default timeout."""
        async def quick_coroutine():
            await asyncio.sleep(0.1)
            return "completed"

        result = await run_with_timeout(quick_coroutine)  # Uses default 30s timeout
        assert result == "completed"

    @pytest.mark.asyncio
    async def test_run_with_timeout_coroutine_raises_exception(self):
        """Test running coroutine that raises an exception."""
        async def failing_coroutine():
            await asyncio.sleep(0.1)
            raise RuntimeError("Coroutine failed")

        with pytest.raises(RuntimeError, match="Coroutine failed"):
            await run_with_timeout(failing_coroutine, timeout=5)

    @pytest.mark.asyncio
    async def test_run_with_timeout_already_awaitable(self):
        """Test running with an already created coroutine object."""
        async def test_coroutine():
            await asyncio.sleep(0.1)
            return "from coroutine object"

        # Create coroutine object
        coro = test_coroutine()

        result = await run_with_timeout(coro, timeout=5)
        assert result == "from coroutine object"

    @pytest.mark.asyncio
    async def test_run_with_timeout_zero_timeout(self):
        """Test running with very short timeout."""
        async def any_coroutine():
            await asyncio.sleep(0.5)
            return "should timeout"

        with pytest.raises(ExternalServiceError) as exc_info:
            await run_with_timeout(any_coroutine, timeout=0.1)

        assert "timed out after 0.1 seconds" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_run_with_timeout_mixed_args_kwargs(self):
        """Test running coroutine with mixed positional and keyword arguments."""
        async def complex_coroutine(a, b, c=None, d=None):
            await asyncio.sleep(0.1)
            return f"a={a}, b={b}, c={c}, d={d}"

        result = await run_with_timeout(
            complex_coroutine, 30, "first", "second", c="third", d="fourth"
        )
        assert result == "a=first, b=second, c=third, d=fourth"

    @pytest.mark.asyncio
    async def test_run_with_timeout_callable_vs_coroutine(self):
        """Test behavior difference between callable and coroutine object."""
        async def test_coroutine(value):
            await asyncio.sleep(0.1)
            return value

        # Test with callable (function)
        result1 = await run_with_timeout(test_coroutine, 30, "from callable")
        assert result1 == "from callable"

        # Test with coroutine object
        coro_obj = test_coroutine("from coroutine")
        result2 = await run_with_timeout(coro_obj, 30)
        assert result2 == "from coroutine"


class TestTimeoutErrorHandling:
    """Test timeout error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_timeout_error_message_format(self):
        """Test timeout error message format."""
        @with_timeout(timeout_seconds=1)
        async def timeout_function():
            await asyncio.sleep(2)

        with pytest.raises(ExternalServiceError) as exc_info:
            await timeout_function()

        error_message = str(exc_info.value)
        assert "timeout_function" in error_message
        assert "timed out after 1 seconds" in error_message

    @pytest.mark.asyncio
    async def test_timeout_error_properties(self):
        """Test timeout error has correct properties."""
        async def timeout_coroutine():
            await asyncio.sleep(2)

        with pytest.raises(ExternalServiceError) as exc_info:
            await run_with_timeout(timeout_coroutine, timeout=1)

        error = exc_info.value
        assert error.is_recoverable is True
        assert error.retry_after == 60
        assert "timed out after 1 seconds" in str(error)

    @pytest.mark.asyncio
    async def test_nested_timeouts(self):
        """Test behavior with nested timeout decorators."""
        @with_timeout(timeout_seconds=3)  # Outer timeout
        async def outer_function():
            @with_timeout(timeout_seconds=1)  # Inner timeout (shorter)
            async def inner_function():
                await asyncio.sleep(2)  # Exceeds inner timeout
                return "should not reach"

            return await inner_function()

        # Should raise timeout from inner function (1 second)
        with pytest.raises(ExternalServiceError) as exc_info:
            await outer_function()

        assert "timed out after 1 seconds" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_timeout_with_cancellation(self):
        """Test timeout behavior when task is cancelled."""
        @with_timeout(timeout_seconds=2)
        async def cancellable_function():
            try:
                await asyncio.sleep(5)
                return "completed"
            except asyncio.CancelledError:
                # Should not catch this, let it propagate
                raise

        task = asyncio.create_task(cancellable_function())
        await asyncio.sleep(0.1)  # Let it start
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_timeout_precision(self):
        """Test timeout precision for quick operations."""
        start_time = asyncio.get_event_loop().time()

        @with_timeout(timeout_seconds=0.5)
        async def precise_timeout_function():
            await asyncio.sleep(0.6)  # Slightly over timeout
            return "should timeout"

        with pytest.raises(ExternalServiceError):
            await precise_timeout_function()

        end_time = asyncio.get_event_loop().time()
        elapsed = end_time - start_time

        # Should complete close to timeout value (allow some variance)
        assert 0.4 <= elapsed <= 0.8

    @pytest.mark.asyncio
    async def test_concurrent_timeouts(self):
        """Test multiple concurrent timeout operations."""
        @with_timeout(timeout_seconds=1)
        async def concurrent_function(delay, name):
            await asyncio.sleep(delay)
            return f"completed {name}"

        # Start multiple concurrent operations
        tasks = [
            concurrent_function(0.3, "fast"),
            concurrent_function(0.6, "medium"),
            concurrent_function(1.5, "slow"),  # This should timeout
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # First two should succeed
        assert results[0] == "completed fast"
        assert results[1] == "completed medium"

        # Third should timeout
        assert isinstance(results[2], ExternalServiceError)
        assert "timed out" in str(results[2])


class TestTimeoutUtilityEdgeCases:
    """Test edge cases and unusual scenarios."""

    @pytest.mark.asyncio
    async def test_timeout_with_instant_return(self):
        """Test timeout with function that returns immediately."""
        @with_timeout(timeout_seconds=1)
        async def instant_function():
            return "immediate"

        result = await instant_function()
        assert result == "immediate"

    @pytest.mark.asyncio
    async def test_timeout_with_none_return(self):
        """Test timeout with function that returns None."""
        @with_timeout(timeout_seconds=1)
        async def none_returning_function():
            await asyncio.sleep(0.1)
            return None

        result = await none_returning_function()
        assert result is None

    @pytest.mark.asyncio
    async def test_timeout_with_complex_return_types(self):
        """Test timeout with function returning complex types."""
        @with_timeout(timeout_seconds=1)
        async def complex_return_function():
            await asyncio.sleep(0.1)
            return {
                "list": [1, 2, 3],
                "dict": {"nested": "value"},
                "tuple": (4, 5, 6)
            }

        result = await complex_return_function()
        assert result["list"] == [1, 2, 3]
        assert result["dict"]["nested"] == "value"
        assert result["tuple"] == (4, 5, 6)

    @pytest.mark.asyncio
    async def test_run_with_timeout_no_args(self):
        """Test run_with_timeout with coroutine that takes no arguments."""
        async def no_args_coroutine():
            await asyncio.sleep(0.1)
            return "no args"

        result = await run_with_timeout(no_args_coroutine, 30)
        assert result == "no args"

    @pytest.mark.asyncio
    async def test_timeout_function_name_extraction(self):
        """Test timeout error includes correct function name."""
        async def specifically_named_function():
            await asyncio.sleep(2)

        @with_timeout(timeout_seconds=1)
        async def wrapper():
            return await specifically_named_function()

        with pytest.raises(ExternalServiceError) as exc_info:
            await wrapper()

        # Should include the wrapper function name, not the inner function
        assert "wrapper" in str(exc_info.value)