"""
Tests for Redis-backed Circuit Breaker.

These tests verify:
- State persistence in Redis
- Cross-worker consistency
- State transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
- Fallback behavior
- Graceful degradation to in-memory when Redis unavailable
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch
import json

from app.core.redis_circuit_breaker import (
    RedisCircuitBreaker,
    CircuitState,
    CircuitOpenError,
    create_redis_circuit_breaker,
)


class TestRedisCircuitBreakerBasics:
    """Test basic circuit breaker functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock(return_value=True)
        return redis

    @pytest.fixture
    def breaker(self):
        """Create a circuit breaker with in-memory fallback."""
        breaker = RedisCircuitBreaker(
            name="test_breaker",
            failure_threshold=3,
            recovery_timeout=30,
            success_threshold=2,
        )
        breaker._fallback_to_memory = True  # Force in-memory mode for tests
        return breaker

    @pytest.mark.asyncio
    async def test_initial_state_is_closed(self, breaker):
        """Circuit breaker should start in CLOSED state."""
        state = await breaker.get_state_async()
        assert state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_successful_call(self, breaker):
        """Successful calls should be recorded."""
        async def success_func():
            return "success"

        result = await breaker.call(success_func)
        assert result == "success"

        stats = await breaker.get_stats_async()
        assert stats["total_requests"] == 1
        assert stats["successful_requests"] == 1
        assert stats["failed_requests"] == 0

    @pytest.mark.asyncio
    async def test_failed_call_increments_failure_count(self, breaker):
        """Failed calls should increment failure count."""
        async def fail_func():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            await breaker.call(fail_func)

        stats = await breaker.get_stats_async()
        assert stats["consecutive_failures"] == 1

    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self, breaker):
        """Circuit should open after failure threshold is reached."""
        async def fail_func():
            raise ValueError("test error")

        # Trigger 3 failures (threshold)
        for _ in range(3):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        state = await breaker.get_state_async()
        assert state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_fallback_used_when_circuit_open(self, breaker):
        """Fallback should be used when circuit is open."""
        async def fail_func():
            raise ValueError("test error")

        async def fallback():
            return "fallback_result"

        # Open the circuit
        for _ in range(3):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        # Next call should use fallback
        result = await breaker.call(fail_func, fallback=fallback)
        assert result == "fallback_result"

    @pytest.mark.asyncio
    async def test_circuit_open_error_without_fallback(self, breaker):
        """CircuitOpenError should be raised when circuit is open and no fallback."""
        async def fail_func():
            raise ValueError("test error")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        # Next call should raise CircuitOpenError
        with pytest.raises(CircuitOpenError):
            await breaker.call(fail_func)


class TestRedisCircuitBreakerRecovery:
    """Test circuit breaker recovery behavior."""

    @pytest.fixture
    def breaker(self):
        """Create a circuit breaker with short recovery timeout."""
        breaker = RedisCircuitBreaker(
            name="test_recovery",
            failure_threshold=2,
            recovery_timeout=1,  # 1 second for fast tests
            success_threshold=2,
        )
        breaker._fallback_to_memory = True
        return breaker

    @pytest.mark.asyncio
    async def test_half_open_after_recovery_timeout(self, breaker):
        """Circuit should transition to HALF_OPEN after recovery timeout."""
        async def fail_func():
            raise ValueError("test error")

        async def success_func():
            return "success"

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        state = await breaker.get_state_async()
        assert state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # Next call should transition to HALF_OPEN and succeed
        result = await breaker.call(success_func)
        assert result == "success"

        state = await breaker.get_state_async()
        # After 1 success, still half-open (need 2 for success_threshold)
        assert state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_circuit_closes_after_success_threshold(self, breaker):
        """Circuit should close after success threshold is met in HALF_OPEN."""
        async def fail_func():
            raise ValueError("test error")

        async def success_func():
            return "success"

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # Make 2 successful calls (success_threshold)
        await breaker.call(success_func)
        await breaker.call(success_func)

        state = await breaker.get_state_async()
        assert state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_reopens_on_half_open_failure(self, breaker):
        """Circuit should reopen if call fails in HALF_OPEN state."""
        async def fail_func():
            raise ValueError("test error")

        async def success_func():
            return "success"

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # First call transitions to HALF_OPEN and succeeds
        await breaker.call(success_func)

        # Second call fails - should reopen
        with pytest.raises(ValueError):
            await breaker.call(fail_func)

        state = await breaker.get_state_async()
        assert state == CircuitState.OPEN


class TestRedisCircuitBreakerRedisPersistence:
    """Test Redis persistence functionality."""

    @pytest.mark.asyncio
    async def test_state_stored_in_redis(self):
        """State should be stored in Redis."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)

        breaker = RedisCircuitBreaker(name="redis_test")

        with patch(
            "app.core.redis_manager.get_async_redis_client",
            return_value=mock_redis,
        ):
            async def success_func():
                return "success"

            await breaker.call(success_func)

            # Verify Redis set was called
            mock_redis.set.assert_called()
            call_args = mock_redis.set.call_args
            assert "circuit_breaker:redis_test:state" in call_args[0]

    @pytest.mark.asyncio
    async def test_state_retrieved_from_redis(self):
        """State should be retrieved from Redis."""
        stored_state = {
            "state": "open",
            "consecutive_failures": 5,
            "consecutive_successes": 0,
            "total_requests": 10,
            "successful_requests": 5,
            "failed_requests": 5,
            "last_failure_time": None,
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(stored_state))
        mock_redis.set = AsyncMock(return_value=True)

        breaker = RedisCircuitBreaker(name="redis_test")

        with patch(
            "app.core.redis_manager.get_async_redis_client",
            return_value=mock_redis,
        ):
            state = await breaker.get_state_async()
            assert state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_fallback_to_memory_on_redis_error(self):
        """Should fall back to in-memory when Redis fails."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Redis connection failed"))

        breaker = RedisCircuitBreaker(name="fallback_test")

        with patch(
            "app.core.redis_manager.get_async_redis_client",
            return_value=mock_redis,
        ):
            # Should not raise, should use fallback
            async def success_func():
                return "success"

            result = await breaker.call(success_func)
            assert result == "success"
            assert breaker._fallback_to_memory is True


class TestRedisCircuitBreakerReset:
    """Test circuit breaker reset functionality."""

    @pytest.fixture
    def breaker(self):
        """Create a circuit breaker."""
        breaker = RedisCircuitBreaker(name="reset_test", failure_threshold=2)
        breaker._fallback_to_memory = True
        return breaker

    @pytest.mark.asyncio
    async def test_reset_clears_state(self, breaker):
        """Reset should clear all state."""
        async def fail_func():
            raise ValueError("test error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        assert (await breaker.get_state_async()) == CircuitState.OPEN

        # Reset
        await breaker.reset_async()

        state = await breaker.get_state_async()
        assert state == CircuitState.CLOSED

        stats = await breaker.get_stats_async()
        assert stats["total_requests"] == 0
        assert stats["consecutive_failures"] == 0

    @pytest.mark.asyncio
    async def test_force_open(self, breaker):
        """Force open should set circuit to OPEN state."""
        assert (await breaker.get_state_async()) == CircuitState.CLOSED

        await breaker.force_open()

        assert (await breaker.get_state_async()) == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_force_closed(self, breaker):
        """Force closed should set circuit to CLOSED state."""
        async def fail_func():
            raise ValueError("test error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        assert (await breaker.get_state_async()) == CircuitState.OPEN

        await breaker.force_closed()

        assert (await breaker.get_state_async()) == CircuitState.CLOSED


class TestFactoryFunction:
    """Test factory function."""

    def test_create_redis_circuit_breaker(self):
        """Factory function should create a RedisCircuitBreaker."""
        breaker = create_redis_circuit_breaker(
            name="factory_test",
            failure_threshold=10,
            recovery_timeout=120,
            success_threshold=5,
        )

        assert isinstance(breaker, RedisCircuitBreaker)
        assert breaker.name == "factory_test"
        assert breaker.failure_threshold == 10
        assert breaker.recovery_timeout == 120
        assert breaker.success_threshold == 5
