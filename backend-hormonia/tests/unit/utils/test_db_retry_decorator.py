"""Tests for with_db_retry decorator with circuit breaker integration

This test suite verifies the complete retry mechanism including:
- Retry logic with exponential backoff
- Circuit breaker integration
- Both sync and async function support
- Session rollback on failures
"""
import asyncio
import pytest
import time
from unittest.mock import Mock, MagicMock
from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy.orm import Session

from app.utils.db_retry import with_db_retry, reset_circuit_breaker, db_circuit_breaker


class TestDbRetryDecoratorSync:
    """Test retry decorator with synchronous functions"""

    def setup_method(self):
        """Reset circuit breaker before each test"""
        reset_circuit_breaker()

    def test_sync_successful_operation_no_retry(self):
        """Test that successful sync operations don't retry"""
        call_count = 0

        @with_db_retry(max_retries=3)
        def successful_operation():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_operation()
        assert result == "success"
        assert call_count == 1
        assert db_circuit_breaker.state == "closed"
        assert db_circuit_breaker.failure_count == 0

    def test_sync_transient_failure_then_success(self):
        """Test that sync operation retries on transient failure then succeeds"""
        call_count = 0

        @with_db_retry(max_retries=3, base_delay=0.01)
        def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OperationalError("Transient error", None, None)
            return "recovered"

        result = flaky_operation()
        assert result == "recovered"
        assert call_count == 3
        # Circuit should be closed since we eventually succeeded
        assert db_circuit_breaker.state == "closed"

    def test_sync_all_retries_fail_opens_circuit(self):
        """Test that sync failures exceeding retries open the circuit"""
        @with_db_retry(max_retries=2, base_delay=0.01)
        def always_fails():
            raise OperationalError("Persistent error", None, None)

        with pytest.raises(OperationalError):
            always_fails()

        # Should have attempted 3 times (initial + 2 retries)
        assert db_circuit_breaker.failure_count == 3
        assert db_circuit_breaker.state == "open"

    def test_sync_integrity_error_no_retry(self):
        """Test that sync IntegrityErrors are not retried"""
        call_count = 0

        @with_db_retry(max_retries=3)
        def integrity_violation():
            nonlocal call_count
            call_count += 1
            raise IntegrityError("Unique constraint", None, None)

        with pytest.raises(IntegrityError):
            integrity_violation()

        # Should only be called once (no retries)
        assert call_count == 1

    def test_sync_session_rollback_on_error(self):
        """Test that sync operations rollback session on error"""
        mock_session = Mock(spec=Session)

        @with_db_retry(max_retries=2, base_delay=0.01)
        def failing_with_session(db: Session):
            raise OperationalError("DB error", None, None)

        with pytest.raises(OperationalError):
            failing_with_session(db=mock_session)

        # Session should have been rolled back (3 times: initial + 2 retries)
        assert mock_session.rollback.call_count == 3


class TestDbRetryDecoratorAsync:
    """Test retry decorator with asynchronous functions"""

    def setup_method(self):
        """Reset circuit breaker before each test"""
        reset_circuit_breaker()

    @pytest.mark.asyncio
    async def test_async_successful_operation_no_retry(self):
        """Test that successful async operations don't retry"""
        call_count = 0

        @with_db_retry(max_retries=3)
        async def successful_operation():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return "async success"

        result = await successful_operation()
        assert result == "async success"
        assert call_count == 1
        assert db_circuit_breaker.state == "closed"
        assert db_circuit_breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_async_transient_failure_then_success(self):
        """Test that async operation retries on transient failure then succeeds"""
        call_count = 0

        @with_db_retry(max_retries=3, base_delay=0.01)
        async def flaky_operation():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            if call_count < 3:
                raise OperationalError("Async transient error", None, None)
            return "async recovered"

        result = await flaky_operation()
        assert result == "async recovered"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_async_all_retries_fail_opens_circuit(self):
        """Test that async failures exceeding retries open the circuit"""
        call_count = 0

        @with_db_retry(max_retries=2, base_delay=0.01)
        async def always_fails():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            raise OperationalError("Async persistent error", None, None)

        with pytest.raises(OperationalError):
            await always_fails()

        # Should have attempted 3 times (initial + 2 retries)
        assert call_count == 3
        assert db_circuit_breaker.failure_count == 3
        assert db_circuit_breaker.state == "open"

    @pytest.mark.asyncio
    async def test_async_integrity_error_no_retry(self):
        """Test that async IntegrityErrors are not retried"""
        call_count = 0

        @with_db_retry(max_retries=3)
        async def integrity_violation():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            raise IntegrityError("Async unique constraint", None, None)

        with pytest.raises(IntegrityError):
            integrity_violation()

        # Should only be called once (no retries)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_session_rollback_on_error(self):
        """Test that async operations rollback session on error"""
        mock_session = Mock(spec=Session)

        @with_db_retry(max_retries=2, base_delay=0.01)
        async def failing_with_session(db: Session):
            await asyncio.sleep(0.01)
            raise OperationalError("Async DB error", None, None)

        with pytest.raises(OperationalError):
            await failing_with_session(db=mock_session)

        # Session should have been rolled back (3 times: initial + 2 retries)
        assert mock_session.rollback.call_count == 3


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration with retry decorator"""

    def setup_method(self):
        """Reset circuit breaker before each test"""
        reset_circuit_breaker()

    @pytest.mark.asyncio
    async def test_open_circuit_prevents_retry_attempts(self):
        """Test that open circuit prevents retry attempts"""
        # Manually open the circuit
        db_circuit_breaker.state = "open"
        db_circuit_breaker.failure_count = 5
        db_circuit_breaker.last_failure_time = time.time()

        call_count = 0

        @with_db_retry(max_retries=3)
        async def should_be_rejected():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return "should not execute"

        with pytest.raises(Exception) as exc_info:
            await should_be_rejected()

        assert "Circuit breaker is OPEN" in str(exc_info.value)
        # Function should not be called when circuit is open
        assert call_count == 0

    @pytest.mark.asyncio
    async def test_circuit_opens_during_retries(self):
        """Test that circuit can open during retry attempts"""
        # Set a low threshold
        db_circuit_breaker.failure_threshold = 2

        @with_db_retry(max_retries=5, base_delay=0.01)
        async def always_fails():
            await asyncio.sleep(0.01)
            raise OperationalError("Error", None, None)

        with pytest.raises(OperationalError):
            await always_fails()

        # Circuit should be open after threshold failures
        assert db_circuit_breaker.state == "open"
        assert db_circuit_breaker.failure_count >= 2

    @pytest.mark.asyncio
    async def test_circuit_recovery_allows_operations(self):
        """Test that circuit recovery allows operations to proceed"""
        # Set short recovery timeout
        db_circuit_breaker.recovery_timeout = 1

        # Open the circuit
        db_circuit_breaker.state = "open"
        db_circuit_breaker.failure_count = 5
        db_circuit_breaker.last_failure_time = time.time() - 2  # 2 seconds ago

        @with_db_retry(max_retries=1)
        async def should_succeed():
            await asyncio.sleep(0.01)
            return "recovered"

        # Circuit should transition to HALF_OPEN and allow the operation
        result = await should_succeed()
        assert result == "recovered"
        assert db_circuit_breaker.state == "closed"


class TestExponentialBackoff:
    """Test exponential backoff behavior"""

    def setup_method(self):
        """Reset circuit breaker before each test"""
        reset_circuit_breaker()

    @pytest.mark.asyncio
    async def test_async_delays_increase_exponentially(self):
        """Test that async retry delays increase exponentially"""
        call_times = []

        @with_db_retry(max_retries=3, base_delay=0.1, exponential_base=2.0, jitter=False)
        async def timed_failures():
            call_times.append(time.time())
            await asyncio.sleep(0.01)
            if len(call_times) < 4:
                raise OperationalError("Error", None, None)
            return "done"

        result = await timed_failures()
        assert result == "done"
        assert len(call_times) == 4

        # Check delays are approximately exponential (0.1, 0.2, 0.4)
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        delay3 = call_times[3] - call_times[2]

        assert 0.08 < delay1 < 0.15  # ~0.1s with some tolerance
        assert 0.18 < delay2 < 0.25  # ~0.2s
        assert 0.38 < delay3 < 0.45  # ~0.4s


class TestDecoratorFunctionTypeDetection:
    """Test that decorator correctly detects sync vs async functions"""

    def setup_method(self):
        """Reset circuit breaker before each test"""
        reset_circuit_breaker()

    def test_sync_function_returns_sync_wrapper(self):
        """Test that decorating sync function returns sync wrapper"""
        @with_db_retry()
        def sync_func():
            return "sync"

        result = sync_func()
        assert result == "sync"
        # Should not be a coroutine
        assert not asyncio.iscoroutine(result)

    @pytest.mark.asyncio
    async def test_async_function_returns_async_wrapper(self):
        """Test that decorating async function returns async wrapper"""
        @with_db_retry()
        async def async_func():
            await asyncio.sleep(0.01)
            return "async"

        # Calling should return a coroutine
        coro = async_func()
        assert asyncio.iscoroutine(coro)

        result = await coro
        assert result == "async"
