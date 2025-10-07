"""Tests for DatabaseCircuitBreaker functionality

This test suite verifies that the circuit breaker properly:
- Tracks failures and opens the circuit after threshold
- Works correctly with both sync and async functions
- Transitions through states (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
- Properly awaits async coroutines to catch exceptions
- Resets failure counts on success
- Rejects operations when circuit is open
"""
import asyncio
import pytest
import time
from unittest.mock import Mock, AsyncMock
from sqlalchemy.exc import OperationalError

from app.utils.db_retry import DatabaseCircuitBreaker, reset_circuit_breaker


class TestDatabaseCircuitBreakerSync:
    """Test circuit breaker with synchronous functions"""

    def setup_method(self):
        """Reset circuit breaker before each test"""
        self.breaker = DatabaseCircuitBreaker(failure_threshold=3, recovery_timeout=2)

    def test_sync_success_keeps_circuit_closed(self):
        """Test that successful sync operations keep circuit closed"""
        def success_func():
            return "success"

        result = self.breaker.call(success_func)
        assert result == "success"
        assert self.breaker.state == "closed"
        assert self.breaker.failure_count == 0

    def test_sync_failure_increments_count(self):
        """Test that sync failures increment failure count"""
        def failing_func():
            raise OperationalError("DB error", None, None)

        with pytest.raises(OperationalError):
            self.breaker.call(failing_func)

        assert self.breaker.failure_count == 1
        assert self.breaker.state == "closed"
        assert self.breaker.last_failure_time is not None

    def test_sync_circuit_opens_after_threshold(self):
        """Test that circuit opens after threshold failures (sync)"""
        def failing_func():
            raise OperationalError("DB error", None, None)

        # Fail 3 times (threshold)
        for i in range(3):
            with pytest.raises(OperationalError):
                self.breaker.call(failing_func)

        assert self.breaker.state == "open"
        assert self.breaker.failure_count == 3

    def test_sync_open_circuit_rejects_operations(self):
        """Test that open circuit rejects sync operations"""
        def failing_func():
            raise OperationalError("DB error", None, None)

        # Open the circuit
        for i in range(3):
            with pytest.raises(OperationalError):
                self.breaker.call(failing_func)

        # Try another operation - should be rejected
        def any_func():
            return "should not execute"

        with pytest.raises(Exception) as exc_info:
            self.breaker.call(any_func)

        assert "Circuit breaker is OPEN" in str(exc_info.value)
        assert self.breaker.state == "open"

    def test_sync_circuit_transitions_to_half_open(self):
        """Test that circuit transitions to HALF_OPEN after timeout (sync)"""
        def failing_func():
            raise OperationalError("DB error", None, None)

        # Open the circuit
        for i in range(3):
            with pytest.raises(OperationalError):
                self.breaker.call(failing_func)

        assert self.breaker.state == "open"

        # Wait for recovery timeout
        time.sleep(2.1)

        # Next call should transition to HALF_OPEN
        with pytest.raises(OperationalError):
            self.breaker.call(failing_func)

        # Should have transitioned to HALF_OPEN before the call
        # (but failed again, so still open with increased count)
        assert self.breaker.failure_count == 4

    def test_sync_half_open_success_closes_circuit(self):
        """Test that success in HALF_OPEN closes circuit (sync)"""
        def failing_func():
            raise OperationalError("DB error", None, None)

        def success_func():
            return "recovered"

        # Open the circuit
        for i in range(3):
            with pytest.raises(OperationalError):
                self.breaker.call(failing_func)

        assert self.breaker.state == "open"

        # Wait for recovery timeout
        time.sleep(2.1)

        # Manually set to HALF_OPEN to test recovery
        self.breaker.state = "half_open"

        # Success should close the circuit
        result = self.breaker.call(success_func)
        assert result == "recovered"
        assert self.breaker.state == "closed"
        assert self.breaker.failure_count == 0


class TestDatabaseCircuitBreakerAsync:
    """Test circuit breaker with asynchronous functions"""

    def setup_method(self):
        """Reset circuit breaker before each test"""
        self.breaker = DatabaseCircuitBreaker(failure_threshold=3, recovery_timeout=2)

    @pytest.mark.asyncio
    async def test_async_success_keeps_circuit_closed(self):
        """Test that successful async operations keep circuit closed"""
        async def success_func():
            await asyncio.sleep(0.01)
            return "async success"

        result = await self.breaker.acall(success_func)
        assert result == "async success"
        assert self.breaker.state == "closed"
        assert self.breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_async_failure_increments_count(self):
        """Test that async failures increment failure count"""
        async def failing_func():
            await asyncio.sleep(0.01)
            raise OperationalError("Async DB error", None, None)

        with pytest.raises(OperationalError):
            await self.breaker.acall(failing_func)

        assert self.breaker.failure_count == 1
        assert self.breaker.state == "closed"
        assert self.breaker.last_failure_time is not None

    @pytest.mark.asyncio
    async def test_async_circuit_opens_after_threshold(self):
        """Test that circuit opens after threshold failures (async)"""
        async def failing_func():
            await asyncio.sleep(0.01)
            raise OperationalError("Async DB error", None, None)

        # Fail 3 times (threshold)
        for i in range(3):
            with pytest.raises(OperationalError):
                await self.breaker.acall(failing_func)

        assert self.breaker.state == "open"
        assert self.breaker.failure_count == 3

    @pytest.mark.asyncio
    async def test_async_open_circuit_rejects_operations(self):
        """Test that open circuit rejects async operations"""
        async def failing_func():
            await asyncio.sleep(0.01)
            raise OperationalError("Async DB error", None, None)

        # Open the circuit
        for i in range(3):
            with pytest.raises(OperationalError):
                await self.breaker.acall(failing_func)

        # Try another operation - should be rejected
        async def any_func():
            return "should not execute"

        with pytest.raises(Exception) as exc_info:
            await self.breaker.acall(any_func)

        assert "Circuit breaker is OPEN" in str(exc_info.value)
        assert self.breaker.state == "open"

    @pytest.mark.asyncio
    async def test_async_circuit_transitions_to_half_open(self):
        """Test that circuit transitions to HALF_OPEN after timeout (async)"""
        async def failing_func():
            await asyncio.sleep(0.01)
            raise OperationalError("Async DB error", None, None)

        # Open the circuit
        for i in range(3):
            with pytest.raises(OperationalError):
                await self.breaker.acall(failing_func)

        assert self.breaker.state == "open"

        # Wait for recovery timeout
        await asyncio.sleep(2.1)

        # Next call should transition to HALF_OPEN
        with pytest.raises(OperationalError):
            await self.breaker.acall(failing_func)

        # Should have transitioned to HALF_OPEN before the call
        assert self.breaker.failure_count == 4

    @pytest.mark.asyncio
    async def test_async_half_open_success_closes_circuit(self):
        """Test that success in HALF_OPEN closes circuit (async)"""
        async def failing_func():
            await asyncio.sleep(0.01)
            raise OperationalError("Async DB error", None, None)

        async def success_func():
            await asyncio.sleep(0.01)
            return "async recovered"

        # Open the circuit
        for i in range(3):
            with pytest.raises(OperationalError):
                await self.breaker.acall(failing_func)

        assert self.breaker.state == "open"

        # Wait for recovery timeout
        await asyncio.sleep(2.1)

        # Manually set to HALF_OPEN to test recovery
        self.breaker.state = "half_open"

        # Success should close the circuit
        result = await self.breaker.acall(success_func)
        assert result == "async recovered"
        assert self.breaker.state == "closed"
        assert self.breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_async_coroutine_properly_awaited(self):
        """Test that async coroutines are properly awaited to catch exceptions"""
        call_count = 0

        async def counting_func():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            if call_count <= 3:
                raise OperationalError("Async DB error", None, None)
            return "finally succeeded"

        # First 3 calls should fail and increment failure count
        for i in range(3):
            with pytest.raises(OperationalError):
                await self.breaker.acall(counting_func)

        assert call_count == 3
        assert self.breaker.failure_count == 3
        assert self.breaker.state == "open"

        # Verify the function was actually executed (not just returned as coroutine)
        # If coroutines weren't awaited, call_count would be 0


class TestCircuitBreakerMixedOperations:
    """Test circuit breaker with mixed sync/async operations"""

    def setup_method(self):
        """Reset circuit breaker before each test"""
        self.breaker = DatabaseCircuitBreaker(failure_threshold=3, recovery_timeout=2)

    @pytest.mark.asyncio
    async def test_mixed_failures_share_state(self):
        """Test that sync and async failures share the same circuit state"""
        def sync_failing():
            raise OperationalError("Sync error", None, None)

        async def async_failing():
            await asyncio.sleep(0.01)
            raise OperationalError("Async error", None, None)

        # Mix of sync and async failures
        with pytest.raises(OperationalError):
            self.breaker.call(sync_failing)
        assert self.breaker.failure_count == 1

        with pytest.raises(OperationalError):
            await self.breaker.acall(async_failing)
        assert self.breaker.failure_count == 2

        with pytest.raises(OperationalError):
            self.breaker.call(sync_failing)
        assert self.breaker.failure_count == 3
        assert self.breaker.state == "open"

        # Both sync and async should be rejected now
        with pytest.raises(Exception) as exc_info:
            self.breaker.call(lambda: "sync")
        assert "Circuit breaker is OPEN" in str(exc_info.value)

        with pytest.raises(Exception) as exc_info:
            await self.breaker.acall(lambda: "async")
        assert "Circuit breaker is OPEN" in str(exc_info.value)


class TestResetCircuitBreaker:
    """Test the reset_circuit_breaker utility function"""

    def test_reset_clears_state(self):
        """Test that reset properly clears all circuit breaker state"""
        from app.utils.db_retry import db_circuit_breaker

        # Put circuit breaker in a failed state
        db_circuit_breaker.state = "open"
        db_circuit_breaker.failure_count = 10
        db_circuit_breaker.last_failure_time = time.time()

        # Reset
        reset_circuit_breaker()

        # Verify reset
        assert db_circuit_breaker.state == "closed"
        assert db_circuit_breaker.failure_count == 0
        assert db_circuit_breaker.last_failure_time is None
