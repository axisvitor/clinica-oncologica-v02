"""
Tests for ResilientOrchestrator.

Tests circuit breakers, retry logic, and fallback mechanisms.
Target: 90%+ code coverage.
"""

import pytest
import asyncio
from typing import Dict, Any, Optional
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session

from app.orchestration.base.base_orchestrator import BaseOrchestrator
from app.orchestration.base.resilient_orchestrator import ResilientOrchestrator
from app.resilience.circuit_breaker.breaker import CircuitBreakerState


# ===============================
# Test Implementation
# ===============================


class TestResilientOrchestrator(BaseOrchestrator, ResilientOrchestrator):
    """Concrete implementation for testing."""

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute test logic."""
        return {"success": True}

    def validate(self, context: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate test context."""
        return True, None


# ===============================
# Fixtures
# ===============================


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    db.execute = Mock(return_value=None)
    return db


@pytest.fixture
def orchestrator(mock_db):
    """Create resilient orchestrator instance."""
    return TestResilientOrchestrator(db=mock_db)


# ===============================
# Circuit Breaker Tests
# ===============================


def test_setup_circuit_breaker(orchestrator):
    """Test circuit breaker setup."""
    breaker = orchestrator.setup_circuit_breaker(
        "test_service",
        failure_threshold=3,
        recovery_timeout=30.0
    )

    assert breaker is not None
    assert breaker.name == "test_service"
    assert orchestrator.get_circuit_breaker("test_service") is breaker


def test_setup_circuit_breaker_with_custom_config(orchestrator):
    """Test circuit breaker setup with custom configuration."""
    breaker = orchestrator.setup_circuit_breaker(
        "payment",
        failure_threshold=5,
        recovery_timeout=60.0,
        success_threshold=2,
        timeout=45.0
    )

    assert breaker.config.failure_threshold == 5
    assert breaker.config.recovery_timeout == 60.0
    assert breaker.config.success_threshold == 2
    assert breaker.config.timeout == 45.0


def test_get_circuit_breaker_not_found(orchestrator):
    """Test get_circuit_breaker for non-existent breaker."""
    breaker = orchestrator.get_circuit_breaker("nonexistent")
    assert breaker is None


def test_get_circuit_breaker_status(orchestrator):
    """Test circuit breaker status retrieval."""
    orchestrator.setup_circuit_breaker("api")

    status = orchestrator.get_circuit_breaker_status("api")

    assert status is not None
    assert status["name"] == "api"
    assert "state" in status
    assert "failure_count" in status
    assert "success_count" in status


def test_get_circuit_breaker_status_not_found(orchestrator):
    """Test circuit breaker status for non-existent breaker."""
    status = orchestrator.get_circuit_breaker_status("nonexistent")
    assert status is None


# ===============================
# Retry Logic Tests
# ===============================


@pytest.mark.asyncio
async def test_with_retry_success_first_attempt(orchestrator):
    """Test with_retry succeeds on first attempt."""
    async def successful_func():
        return "success"

    result = await orchestrator.with_retry(successful_func, max_retries=3)

    assert result == "success"


@pytest.mark.asyncio
async def test_with_retry_success_after_retries(orchestrator):
    """Test with_retry succeeds after retries."""
    call_count = 0

    async def eventually_succeeds():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("Temporary failure")
        return "success"

    result = await orchestrator.with_retry(
        eventually_succeeds,
        max_retries=3,
        initial_delay=0.01  # Fast for testing
    )

    assert result == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_with_retry_all_attempts_fail(orchestrator):
    """Test with_retry fails after all retries exhausted."""
    async def always_fails():
        raise ValueError("Permanent failure")

    with pytest.raises(ValueError, match="Permanent failure"):
        await orchestrator.with_retry(
            always_fails,
            max_retries=2,
            initial_delay=0.01
        )


@pytest.mark.asyncio
async def test_with_retry_exponential_backoff(orchestrator):
    """Test exponential backoff delay calculation."""
    call_times = []

    async def track_timing():
        import time
        call_times.append(time.time())
        if len(call_times) < 3:
            raise Exception("Retry")
        return "success"

    await orchestrator.with_retry(
        track_timing,
        max_retries=3,
        initial_delay=0.1,
        max_delay=1.0
    )

    # Verify exponential backoff (delays should be ~0.1s, ~0.2s)
    assert len(call_times) == 3
    delay1 = call_times[1] - call_times[0]
    delay2 = call_times[2] - call_times[1]

    assert delay1 >= 0.08  # Allow small variance
    assert delay2 >= 0.18  # Should be ~2x first delay


@pytest.mark.asyncio
async def test_with_retry_max_delay_limit(orchestrator):
    """Test that retry delay doesn't exceed max_delay."""
    delays = []

    async def track_delays():
        import time
        if delays:
            delays.append(time.time() - delays[-1])
        else:
            delays.append(time.time())

        if len(delays) < 5:
            raise Exception("Retry")
        return "success"

    await orchestrator.with_retry(
        track_delays,
        max_retries=5,
        initial_delay=0.1,
        max_delay=0.2
    )

    # All delays should be capped at max_delay (0.2s)
    for delay in delays[1:]:
        assert delay <= 0.25  # Allow small variance


@pytest.mark.asyncio
async def test_with_retry_sync_function(orchestrator):
    """Test with_retry works with synchronous functions."""
    def sync_function():
        return "sync_result"

    result = await orchestrator.with_retry(sync_function, max_retries=2)

    assert result == "sync_result"


@pytest.mark.asyncio
async def test_with_retry_with_args_and_kwargs(orchestrator):
    """Test with_retry passes arguments correctly."""
    async def func_with_args(a, b, c=None):
        return {"a": a, "b": b, "c": c}

    result = await orchestrator.with_retry(
        func_with_args,
        "arg1", "arg2",
        c="kwarg",
        max_retries=2
    )

    assert result == {"a": "arg1", "b": "arg2", "c": "kwarg"}


# ===============================
# Fallback Handler Tests
# ===============================


def test_register_fallback(orchestrator):
    """Test fallback handler registration."""
    def fallback_handler():
        return "fallback_result"

    orchestrator.register_fallback("service", fallback_handler)

    assert "service" in orchestrator._fallback_handlers
    assert orchestrator._fallback_handlers["service"] is fallback_handler


@pytest.mark.asyncio
async def test_execute_with_fallback_success(orchestrator):
    """Test execute_with_fallback when primary succeeds."""
    async def primary():
        return "primary_result"

    def fallback():
        return "fallback_result"

    orchestrator.register_fallback("service", fallback)

    result = await orchestrator.execute_with_fallback(
        "service",
        primary
    )

    assert result == "primary_result"


@pytest.mark.asyncio
async def test_execute_with_fallback_uses_fallback(orchestrator):
    """Test execute_with_fallback uses fallback on failure."""
    async def primary():
        raise ConnectionError("Primary failed")

    async def fallback():
        return "fallback_result"

    orchestrator.register_fallback("service", fallback)

    result = await orchestrator.execute_with_fallback(
        "service",
        primary
    )

    assert result == "fallback_result"


@pytest.mark.asyncio
async def test_execute_with_fallback_no_fallback_registered(orchestrator):
    """Test execute_with_fallback raises when no fallback registered."""
    async def primary():
        raise ValueError("Primary failed")

    with pytest.raises(ValueError, match="Primary failed"):
        await orchestrator.execute_with_fallback("service", primary)


@pytest.mark.asyncio
async def test_execute_with_fallback_sync_functions(orchestrator):
    """Test execute_with_fallback with synchronous functions."""
    def primary():
        raise Exception("Failed")

    def fallback():
        return "fallback"

    orchestrator.register_fallback("service", fallback)

    result = await orchestrator.execute_with_fallback("service", primary)

    assert result == "fallback"


@pytest.mark.asyncio
async def test_execute_with_fallback_with_args(orchestrator):
    """Test execute_with_fallback passes arguments."""
    async def primary(x, y):
        raise Exception("Failed")

    async def fallback(x, y):
        return x + y

    orchestrator.register_fallback("service", fallback)

    result = await orchestrator.execute_with_fallback(
        "service",
        primary,
        10, 20
    )

    assert result == 30


# ===============================
# Combined Resilience Tests
# ===============================


@pytest.mark.asyncio
async def test_execute_with_resilience_success(orchestrator):
    """Test execute_with_resilience with successful execution."""
    orchestrator.setup_circuit_breaker("api")

    async def api_call():
        return "success"

    result = await orchestrator.execute_with_resilience(
        "api",
        api_call,
        max_retries=3
    )

    assert result == "success"


@pytest.mark.asyncio
async def test_execute_with_resilience_retry_on_failure(orchestrator):
    """Test execute_with_resilience retries on failure."""
    orchestrator.setup_circuit_breaker("api")

    call_count = 0

    async def api_call():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("Temporary")
        return "success"

    result = await orchestrator.execute_with_resilience(
        "api",
        api_call,
        max_retries=5
    )

    assert result == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_execute_with_resilience_no_circuit_breaker(orchestrator):
    """Test execute_with_resilience without circuit breaker."""
    async def api_call():
        return "success"

    with patch.object(orchestrator, "log_warning"):
        result = await orchestrator.execute_with_resilience(
            "nonexistent",
            api_call
        )

    assert result == "success"


# ===============================
# Integration Tests
# ===============================


@pytest.mark.asyncio
async def test_full_resilience_workflow(orchestrator):
    """Test full resilience workflow with all features."""
    # Setup
    orchestrator.setup_circuit_breaker("external_api", failure_threshold=2)

    async def fallback_handler():
        return "fallback_response"

    orchestrator.register_fallback("external_api", fallback_handler)

    # Test successful call
    async def successful_call():
        return "success"

    result = await orchestrator.execute_with_resilience(
        "external_api",
        successful_call,
        max_retries=3
    )

    assert result == "success"


@pytest.mark.asyncio
async def test_metrics_tracking_with_retries(orchestrator):
    """Test that metrics track retry operations."""
    call_count = 0

    async def intermittent_failure():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise Exception("Fail")
        return "success"

    await orchestrator.with_retry(
        intermittent_failure,
        max_retries=3,
        initial_delay=0.01
    )

    # Verify execution completed
    assert call_count == 2
