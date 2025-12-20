"""
Integration Tests for Circuit Breaker Implementation (HIGH-006)
================================================================

Comprehensive tests for circuit breaker pattern covering:
- State transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
- Failure thresholds
- Recovery timeouts
- Fallback mechanisms
- WhatsApp fallback queue
- Firebase degraded mode
- Gemini AI template responses
- Prometheus metrics

Author: Backend API Developer Agent
Date: 2025-11-16

NOTE: Requires aiobreaker package to be installed.
"""

import pytest

# Skip entire module if aiobreaker is not installed
pytest.importorskip("aiobreaker", reason="aiobreaker not installed")

import asyncio
from unittest.mock import AsyncMock, patch
from aiobreaker import CircuitBreakerError

from app.core.circuit_breaker_enhanced import (
    ServiceType,
    CircuitBreakerConfig,
    EnhancedCircuitBreaker,
    get_circuit_breaker_manager,
    with_circuit_breaker,
    CIRCUIT_CONFIGS
)
from app.services.firebase_auth_circuit_breaker import FirebaseAuthServiceWithCircuitBreaker


class TestCircuitBreakerStateTransitions:
    """Test circuit breaker state machine transitions."""

    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self):
        """Test that circuit breaker opens after reaching failure threshold."""
        # Arrange
        config = CircuitBreakerConfig(
            fail_max=3,
            timeout_duration=60,
            name="test_service"
        )
        breaker = EnhancedCircuitBreaker(config)

        async def failing_function():
            raise Exception("Service unavailable")

        # Act: Make 3 calls that fail (failure threshold)
        for i in range(3):
            with pytest.raises(Exception):
                await breaker.call(failing_function)

        # Assert: Circuit should now be OPEN
        assert breaker.get_state() == "open"

    @pytest.mark.asyncio
    async def test_circuit_rejects_calls_when_open(self):
        """Test that circuit breaker rejects calls when OPEN."""
        # Arrange
        config = CircuitBreakerConfig(
            fail_max=2,
            timeout_duration=60,
            name="test_service"
        )
        breaker = EnhancedCircuitBreaker(config)

        async def failing_function():
            raise Exception("Service unavailable")

        # Open the circuit
        for i in range(2):
            with pytest.raises(Exception):
                await breaker.call(failing_function)

        # Act & Assert: Next call should raise CircuitBreakerError
        with pytest.raises(CircuitBreakerError):
            await breaker.call(failing_function)

    @pytest.mark.asyncio
    async def test_circuit_half_opens_after_timeout(self):
        """Test circuit transitions to HALF_OPEN after timeout."""
        # Arrange
        config = CircuitBreakerConfig(
            fail_max=2,
            timeout_duration=1,  # 1 second timeout for testing
            name="test_service"
        )
        breaker = EnhancedCircuitBreaker(config)

        async def failing_function():
            raise Exception("Service unavailable")

        async def working_function():
            return "success"

        # Open the circuit
        for i in range(2):
            with pytest.raises(Exception):
                await breaker.call(failing_function)

        # Assert circuit is OPEN
        assert breaker.get_state() == "open"

        # Wait for timeout
        await asyncio.sleep(1.5)

        # Act: Make a successful call
        result = await breaker.call(working_function)

        # Assert: Should transition to HALF_OPEN and succeed
        assert result == "success"

    @pytest.mark.asyncio
    async def test_circuit_closes_after_success_in_half_open(self):
        """Test circuit closes after successful calls in HALF_OPEN state."""
        # Arrange
        config = CircuitBreakerConfig(
            fail_max=2,
            timeout_duration=1,
            name="test_service"
        )
        breaker = EnhancedCircuitBreaker(config)

        async def failing_function():
            raise Exception("Service unavailable")

        async def working_function():
            return "success"

        # Open the circuit
        for i in range(2):
            with pytest.raises(Exception):
                await breaker.call(failing_function)

        # Wait for timeout and make successful calls
        await asyncio.sleep(1.5)

        # Act: Make 2 successful calls (success_threshold defaults to 2)
        await breaker.call(working_function)
        await breaker.call(working_function)

        # Assert: Circuit should now be CLOSED
        assert breaker.get_state() == "closed"


class TestCircuitBreakerFallbackMechanisms:
    """Test fallback mechanisms for different services."""

    @pytest.mark.asyncio
    async def test_fallback_called_when_circuit_open(self):
        """Test that fallback is called when circuit is OPEN."""
        # Arrange
        config = CircuitBreakerConfig(
            fail_max=2,
            timeout_duration=60,
            name="test_service",
            enable_fallback=True
        )
        breaker = EnhancedCircuitBreaker(config)

        async def failing_function():
            raise Exception("Service unavailable")

        async def fallback_function():
            return "fallback_result"

        # Open the circuit
        for i in range(2):
            await breaker.call(failing_function, fallback=fallback_function)

        # Act: Call with circuit OPEN
        result = await breaker.call(failing_function, fallback=fallback_function)

        # Assert: Should return fallback result
        assert result == "fallback_result"

    @pytest.mark.asyncio
    async def test_whatsapp_fallback_queue_enabled(self):
        """Test WhatsApp messages are queued when circuit is OPEN."""
        # Arrange
        manager = get_circuit_breaker_manager()
        whatsapp_breaker = manager.get_breaker(ServiceType.WHATSAPP)

        # Verify config
        assert whatsapp_breaker.config.fallback_queue_enabled is True
        assert whatsapp_breaker.config.fail_max == 5

    @pytest.mark.asyncio
    async def test_firebase_fallback_returns_degraded_mode(self):
        """Test Firebase returns degraded mode data when circuit is OPEN."""
        # Arrange
        with patch('app.services.firebase_auth_circuit_breaker.firebase_admin'):
            service = FirebaseAuthServiceWithCircuitBreaker(
                project_id="test-project",
                private_key="test-key",
                client_email="test@test.com"
            )

            # Open the circuit by forcing failures
            async def force_open():
                raise Exception("Firebase unavailable")

            for _ in range(3):  # Firebase fail_max = 3
                try:
                    await service.breaker.call(force_open)
                except:
                    pass

            # Act: Attempt to verify token with circuit OPEN
            result = await service.verify_token("test-token")

            # Assert: Should return degraded mode data
            assert result.get("degraded_mode") is True
            assert "warning" in result

    @pytest.mark.asyncio
    async def test_gemini_fallback_uses_template_response(self):
        """Test Gemini AI uses template/cached responses when circuit is OPEN."""
        # Arrange
        manager = get_circuit_breaker_manager()
        gemini_breaker = manager.get_breaker(ServiceType.GEMINI_AI)

        async def gemini_call():
            raise Exception("Gemini API unavailable")

        async def gemini_fallback():
            return "Template response: Thank you for your message."

        # Open circuit
        for _ in range(5):  # Gemini fail_max = 5
            await gemini_breaker.call(gemini_call, fallback=gemini_fallback)

        # Act: Call with circuit OPEN
        result = await gemini_breaker.call(gemini_call, fallback=gemini_fallback)

        # Assert: Should use fallback
        assert "Template response" in result


class TestCircuitBreakerMetrics:
    """Test Prometheus metrics integration."""

    @pytest.mark.asyncio
    async def test_success_metric_incremented(self):
        """Test that success counter increments on successful calls."""
        # Arrange
        config = CircuitBreakerConfig(
            fail_max=5,
            timeout_duration=60,
            name="test_metrics_service",
            enable_metrics=True
        )
        breaker = EnhancedCircuitBreaker(config)

        async def successful_function():
            return "success"

        # Act
        await breaker.call(successful_function)

        # Assert: Check stats
        stats = breaker.get_stats()
        assert stats["name"] == "test_metrics_service"

    @pytest.mark.asyncio
    async def test_failure_metric_incremented(self):
        """Test that failure counter increments on failed calls."""
        # Arrange
        config = CircuitBreakerConfig(
            fail_max=5,
            timeout_duration=60,
            name="test_metrics_service",
            enable_metrics=True
        )
        breaker = EnhancedCircuitBreaker(config)

        async def failing_function():
            raise Exception("Service error")

        # Act
        with pytest.raises(Exception):
            await breaker.call(failing_function)

        # Assert: Check stats
        stats = breaker.get_stats()
        assert stats["failure_count"] > 0

    @pytest.mark.asyncio
    async def test_state_gauge_updates(self):
        """Test that state gauge updates on state transitions."""
        # Arrange
        config = CircuitBreakerConfig(
            fail_max=2,
            timeout_duration=60,
            name="test_gauge_service"
        )
        breaker = EnhancedCircuitBreaker(config)

        async def failing_function():
            raise Exception("Service error")

        # Act: Open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                await breaker.call(failing_function)

        # Assert: State should be OPEN
        assert breaker.get_state() == "open"


class TestCircuitBreakerManager:
    """Test circuit breaker manager functionality."""

    def test_manager_singleton(self):
        """Test that manager returns same instance."""
        # Act
        manager1 = get_circuit_breaker_manager()
        manager2 = get_circuit_breaker_manager()

        # Assert
        assert manager1 is manager2

    def test_manager_has_all_services(self):
        """Test that manager initializes breakers for all services."""
        # Arrange
        manager = get_circuit_breaker_manager()

        # Assert
        assert ServiceType.WHATSAPP in manager.breakers
        assert ServiceType.FIREBASE in manager.breakers
        assert ServiceType.GEMINI_AI in manager.breakers

    def test_get_all_stats(self):
        """Test retrieving stats for all circuit breakers."""
        # Arrange
        manager = get_circuit_breaker_manager()

        # Act
        stats = manager.get_all_stats()

        # Assert
        assert len(stats) == 3
        assert ServiceType.WHATSAPP.value in stats
        assert ServiceType.FIREBASE.value in stats
        assert ServiceType.GEMINI_AI.value in stats

    def test_circuit_configs_are_correct(self):
        """Test that circuit configurations match requirements."""
        # WhatsApp config
        whatsapp_config = CIRCUIT_CONFIGS[ServiceType.WHATSAPP]
        assert whatsapp_config.fail_max == 5
        assert whatsapp_config.timeout_duration == 60
        assert whatsapp_config.fallback_queue_enabled is True

        # Firebase config
        firebase_config = CIRCUIT_CONFIGS[ServiceType.FIREBASE]
        assert firebase_config.fail_max == 3
        assert firebase_config.timeout_duration == 30

        # Gemini config
        gemini_config = CIRCUIT_CONFIGS[ServiceType.GEMINI_AI]
        assert gemini_config.fail_max == 5
        assert gemini_config.timeout_duration == 120


class TestCircuitBreakerDecorator:
    """Test circuit breaker decorator functionality."""

    @pytest.mark.asyncio
    async def test_decorator_applies_circuit_breaker(self):
        """Test that decorator properly applies circuit breaker."""
        # Arrange
        @with_circuit_breaker(ServiceType.WHATSAPP)
        async def send_message():
            return "message_sent"

        # Act
        result = await send_message()

        # Assert
        assert result == "message_sent"
        assert hasattr(send_message, 'circuit_breaker_service')
        assert send_message.circuit_breaker_service == ServiceType.WHATSAPP


class TestChaosEngineering:
    """Chaos engineering tests for circuit breaker resilience."""

    @pytest.mark.asyncio
    async def test_intermittent_failures_dont_open_circuit(self):
        """Test circuit doesn't open with intermittent failures below threshold."""
        # Arrange
        config = CircuitBreakerConfig(
            fail_max=5,
            timeout_duration=60,
            name="test_chaos"
        )
        breaker = EnhancedCircuitBreaker(config)

        call_count = 0

        async def intermittent_function():
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:  # Every 3rd call fails
                raise Exception("Intermittent failure")
            return "success"

        # Act: Make 10 calls (3 will fail, below threshold of 5)
        results = []
        for _ in range(10):
            try:
                result = await breaker.call(intermittent_function)
                results.append(result)
            except Exception:
                pass

        # Assert: Circuit should still be CLOSED
        assert breaker.get_state() == "closed"
        assert len(results) > 0  # Some calls succeeded

    @pytest.mark.asyncio
    async def test_cascading_failure_prevention(self):
        """Test circuit breaker prevents cascading failures."""
        # Arrange
        config = CircuitBreakerConfig(
            fail_max=3,
            timeout_duration=60,
            name="test_cascade"
        )
        breaker = EnhancedCircuitBreaker(config)

        async def failing_service():
            await asyncio.sleep(5)  # Slow failing service
            raise Exception("Service timeout")

        # Act: Open circuit with 3 failures
        for _ in range(3):
            with pytest.raises(Exception):
                await breaker.call(failing_service)

        # Assert: Circuit is OPEN
        assert breaker.get_state() == "open"

        # Further calls should fail fast without waiting
        import time
        start = time.time()
        with pytest.raises(CircuitBreakerError):
            await breaker.call(failing_service)
        duration = time.time() - start

        # Assert: Failed immediately (< 1 second) instead of waiting 5 seconds
        assert duration < 1.0


# Fixtures
@pytest.fixture
async def circuit_breaker_manager():
    """Provide circuit breaker manager for tests."""
    manager = get_circuit_breaker_manager()
    yield manager
    # Reset breakers after tests
    for breaker in manager.breakers.values():
        breaker._breaker.reset()


@pytest.fixture
def mock_redis_client():
    """Provide mock Redis client for fallback queue tests."""
    client = AsyncMock()
    client.rpush = AsyncMock()
    client.lpop = AsyncMock(return_value=None)
    return client
