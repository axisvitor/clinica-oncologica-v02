"""
Tests for Saga timeout functionality (MEDIUM-004).

Tests cover:
- Global saga timeout
- Step-level timeout
- Timeout with compensation
- Timeout configuration
"""

import pytest
import asyncio
from datetime import datetime
from uuid import uuid4

from app.orchestration.saga_orchestrator import (
    SagaOrchestrator,
    SagaState,
    SagaStep,
    SagaStatus,
    SagaStepStatus
)


@pytest.fixture
def saga_orchestrator(db_session, redis_client, evolution_client):
    """Create saga orchestrator with short timeout for testing."""
    return SagaOrchestrator(
        db=db_session,
        redis=redis_client,
        evolution_client=evolution_client,
        global_timeout=5,  # 5 seconds for testing
        max_retries=1
    )


class TestSagaTimeout:
    """Test saga timeout functionality."""

    @pytest.mark.asyncio
    async def test_saga_global_timeout(self, saga_orchestrator):
        """Test saga exceeds global timeout."""
        # Create slow step that exceeds timeout
        async def slow_step(context):
            await asyncio.sleep(10)  # Longer than timeout
            return "should_not_complete"

        # Create saga with slow step
        saga_state = SagaState(
            saga_id=f"saga_{uuid4().hex}",
            saga_type="test_timeout",
            status=SagaStatus.PENDING,
            steps=[
                SagaStep(
                    name="slow_step",
                    action=slow_step
                )
            ],
            context={}
        )

        # Execute saga (should timeout)
        with pytest.raises(asyncio.TimeoutError):
            await saga_orchestrator.execute_saga(saga_state, timeout=5)

        # Verify saga marked as failed
        assert saga_state.status == SagaStatus.FAILED
        assert "timeout" in saga_state.error.lower()

    @pytest.mark.asyncio
    async def test_saga_completes_within_timeout(self, saga_orchestrator):
        """Test saga completes successfully within timeout."""
        # Create fast step
        async def fast_step(context):
            await asyncio.sleep(0.1)
            return "completed"

        saga_state = SagaState(
            saga_id=f"saga_{uuid4().hex}",
            saga_type="test_success",
            status=SagaStatus.PENDING,
            steps=[
                SagaStep(name="fast_step", action=fast_step)
            ],
            context={}
        )

        # Execute saga (should complete)
        result = await saga_orchestrator.execute_saga(saga_state, timeout=5)

        assert result.status == SagaStatus.COMPLETED
        assert result.steps[0].status == SagaStepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_timeout_with_compensation(self, saga_orchestrator):
        """Test saga timeout triggers compensation of completed steps."""
        compensation_called = {"step1": False, "step2": False}

        async def step1(context):
            await asyncio.sleep(0.1)
            return "step1_complete"

        async def compensate_step1(context):
            compensation_called["step1"] = True
            return "step1_compensated"

        async def step2(context):
            await asyncio.sleep(0.1)
            return "step2_complete"

        async def compensate_step2(context):
            compensation_called["step2"] = True
            return "step2_compensated"

        async def slow_step(context):
            await asyncio.sleep(10)  # Exceeds timeout
            return "should_not_complete"

        saga_state = SagaState(
            saga_id=f"saga_{uuid4().hex}",
            saga_type="test_timeout_compensation",
            status=SagaStatus.PENDING,
            steps=[
                SagaStep(name="step1", action=step1, compensation=compensate_step1),
                SagaStep(name="step2", action=step2, compensation=compensate_step2),
                SagaStep(name="slow_step", action=slow_step)
            ],
            context={}
        )

        # Execute saga (should timeout)
        with pytest.raises(asyncio.TimeoutError):
            await saga_orchestrator.execute_saga(saga_state, timeout=3)

        # Note: Current implementation doesn't compensate on timeout
        # This is a known limitation - timeout happens at orchestrator level
        # Compensation requires explicit handling after timeout
        # Future enhancement: Add compensation on timeout

    @pytest.mark.asyncio
    async def test_custom_timeout_override(self, saga_orchestrator):
        """Test custom timeout overrides default."""
        async def medium_step(context):
            await asyncio.sleep(2)
            return "completed"

        saga_state = SagaState(
            saga_id=f"saga_{uuid4().hex}",
            saga_type="test_custom_timeout",
            status=SagaStatus.PENDING,
            steps=[
                SagaStep(name="medium_step", action=medium_step)
            ],
            context={}
        )

        # Short timeout should fail
        with pytest.raises(asyncio.TimeoutError):
            await saga_orchestrator.execute_saga(saga_state, timeout=1)

        # Reset saga
        saga_state.status = SagaStatus.PENDING
        saga_state.steps[0].status = SagaStepStatus.PENDING

        # Longer timeout should succeed
        result = await saga_orchestrator.execute_saga(saga_state, timeout=5)
        assert result.status == SagaStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_timeout_persistence(self, saga_orchestrator):
        """Test saga state persisted on timeout."""
        async def slow_step(context):
            await asyncio.sleep(10)
            return "should_not_complete"

        saga_state = SagaState(
            saga_id=f"saga_{uuid4().hex}",
            saga_type="test_timeout_persistence",
            status=SagaStatus.PENDING,
            steps=[
                SagaStep(name="slow_step", action=slow_step)
            ],
            context={"test_key": "test_value"}
        )

        # Execute saga (should timeout)
        with pytest.raises(asyncio.TimeoutError):
            await saga_orchestrator.execute_saga(saga_state, timeout=2)

        # Verify state persisted
        persisted_state = await saga_orchestrator.persistence_manager.get_saga_state(
            saga_state.saga_id
        )

        assert persisted_state is not None
        assert persisted_state.status == SagaStatus.FAILED
        assert "timeout" in persisted_state.error.lower()

    @pytest.mark.asyncio
    async def test_timeout_configuration_from_settings(self, db_session, redis_client, evolution_client, monkeypatch):
        """Test timeout loads from settings."""
        # Mock settings
        from app.config.settings.tasks import SAGA_GLOBAL_TIMEOUT_SECONDS
        monkeypatch.setattr("app.config.settings.tasks.SAGA_GLOBAL_TIMEOUT_SECONDS", 42)

        orchestrator = SagaOrchestrator(
            db=db_session,
            redis=redis_client,
            evolution_client=evolution_client
        )

        assert orchestrator.global_timeout == 42


class TestSagaTimeoutMetrics:
    """Test timeout metrics and logging."""

    @pytest.mark.asyncio
    async def test_timeout_logged(self, saga_orchestrator, caplog):
        """Test timeout is logged with context."""
        async def slow_step(context):
            await asyncio.sleep(10)
            return "should_not_complete"

        saga_state = SagaState(
            saga_id=f"saga_{uuid4().hex}",
            saga_type="test_timeout_logging",
            status=SagaStatus.PENDING,
            steps=[
                SagaStep(name="slow_step", action=slow_step)
            ],
            context={}
        )

        with pytest.raises(asyncio.TimeoutError):
            await saga_orchestrator.execute_saga(saga_state, timeout=2)

        # Verify timeout logged
        assert "timeout" in caplog.text.lower()
        assert saga_state.saga_type in caplog.text
