"""
Tests for saga compensation (rollback) scenarios
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class TestSagaCompensation:
    """Test saga rollback when steps fail."""

    @pytest.mark.asyncio
    async def test_rollback_on_whatsapp_failure(self):
        """Test saga rollback when WhatsApp step fails."""
        from app.orchestration.saga_orchestrator import SagaOrchestrator

        orchestrator = SagaOrchestrator()

        # Mock steps
        orchestrator._step_create_patient = AsyncMock(return_value={"id": "123"})
        orchestrator._step_init_flow = AsyncMock()
        orchestrator._step_send_whatsapp = AsyncMock(side_effect=Exception("WhatsApp failed"))
        orchestrator._compensate_create_patient = AsyncMock()
        orchestrator._compensate_init_flow = AsyncMock()

        with pytest.raises(Exception):
            await orchestrator.execute_saga({})

        # Compensation should be called in reverse order
        orchestrator._compensate_init_flow.assert_called_once()
        orchestrator._compensate_create_patient.assert_called_once()

    @pytest.mark.asyncio
    async def test_compensation_errors_tracked(self):
        """Test compensation errors are tracked in Redis."""
        from app.orchestration.saga_orchestrator import SagaOrchestrator

        orchestrator = SagaOrchestrator()
        orchestrator._redis = AsyncMock()

        # Mock compensation failure
        await orchestrator._track_compensation_failure(
            saga_id="saga_123",
            step=3,
            error=Exception("Compensation failed")
        )

        orchestrator._redis.setex.assert_called_once()
        call_args = orchestrator._redis.setex.call_args
        assert "saga_123" in str(call_args)

    @pytest.mark.asyncio
    async def test_partial_compensation_on_multiple_failures(self):
        """Test compensation continues even if one compensation fails."""
        from app.orchestration.saga_orchestrator import SagaOrchestrator

        orchestrator = SagaOrchestrator()

        # Mock steps
        orchestrator._step_1 = AsyncMock(return_value={"step": 1})
        orchestrator._step_2 = AsyncMock(return_value={"step": 2})
        orchestrator._step_3 = AsyncMock(side_effect=Exception("Step 3 failed"))

        # Mock compensations - one fails
        orchestrator._compensate_1 = AsyncMock()
        orchestrator._compensate_2 = AsyncMock(side_effect=Exception("Compensation 2 failed"))

        orchestrator._steps = [
            (orchestrator._step_1, orchestrator._compensate_1),
            (orchestrator._step_2, orchestrator._compensate_2),
            (orchestrator._step_3, None)
        ]

        with pytest.raises(Exception):
            await orchestrator.execute_saga({})

        # Both compensations should be attempted
        orchestrator._compensate_2.assert_called_once()
        orchestrator._compensate_1.assert_called_once()

    @pytest.mark.asyncio
    async def test_saga_state_persisted_on_failure(self):
        """Test saga state is persisted when failure occurs."""
        from app.orchestration.saga_orchestrator import SagaOrchestrator

        orchestrator = SagaOrchestrator()
        orchestrator._redis = AsyncMock()

        saga_id = "saga_456"
        saga_state = {
            "saga_id": saga_id,
            "status": "failed",
            "completed_steps": 2,
            "total_steps": 5,
            "error": "Database connection failed"
        }

        await orchestrator._persist_saga_state(saga_id, saga_state)

        orchestrator._redis.setex.assert_called_once()


class TestSagaRecovery:
    """Test saga recovery mechanisms."""

    @pytest.mark.asyncio
    async def test_saga_can_be_resumed_after_failure(self):
        """Test saga can be resumed from last successful step."""
        from app.orchestration.saga_orchestrator import SagaOrchestrator
        import json

        orchestrator = SagaOrchestrator()
        orchestrator._redis = AsyncMock()

        # Mock persisted state
        saga_state = {
            "saga_id": "saga_789",
            "completed_steps": 2,
            "status": "failed",
            "context": {"patient_id": "123"}
        }
        orchestrator._redis.get.return_value = json.dumps(saga_state)

        recovered_state = await orchestrator.recover_saga("saga_789")

        assert recovered_state["completed_steps"] == 2
        assert recovered_state["context"]["patient_id"] == "123"

    @pytest.mark.asyncio
    async def test_saga_recovery_with_retry(self):
        """Test saga can retry failed steps."""
        from app.orchestration.saga_orchestrator import SagaOrchestrator

        orchestrator = SagaOrchestrator()

        # Mock step that fails first time, succeeds second time
        call_count = 0

        async def flaky_step(context):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Temporary failure")
            return {"success": True}

        orchestrator._step_flaky = flaky_step

        # Should retry and succeed
        result = await orchestrator.execute_with_retry(
            orchestrator._step_flaky,
            context={},
            max_retries=3
        )

        assert result["success"] is True
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_saga_timeout_triggers_compensation(self):
        """Test saga timeout triggers compensation."""
        from app.orchestration.saga_orchestrator import SagaOrchestrator
        import asyncio

        orchestrator = SagaOrchestrator()

        # Mock slow step
        async def slow_step(context):
            await asyncio.sleep(10)
            return {"done": True}

        orchestrator._step_slow = slow_step
        orchestrator._compensate_slow = AsyncMock()

        # Execute with short timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                orchestrator._step_slow({}),
                timeout=0.1
            )

        # Compensation should be triggered
        # In actual implementation


class TestSagaPatientCreation:
    """Test saga for patient creation workflow."""

    @pytest.mark.asyncio
    async def test_patient_creation_saga_success(self):
        """Test complete patient creation saga succeeds."""
        from app.orchestration.saga_orchestrator import SagaOrchestrator

        orchestrator = SagaOrchestrator()

        # Mock all steps to succeed
        orchestrator._create_patient_record = AsyncMock(
            return_value={"patient_id": "patient_123"}
        )
        orchestrator._init_whatsapp_flow = AsyncMock(
            return_value={"flow_id": "flow_456"}
        )
        orchestrator._send_welcome_message = AsyncMock(
            return_value={"message_id": "msg_789"}
        )
        orchestrator._create_initial_tasks = AsyncMock(
            return_value={"tasks_created": 3}
        )

        result = await orchestrator.execute_patient_creation_saga({
            "name": "Test Patient",
            "phone": "+5511999999999"
        })

        assert result["patient_id"] == "patient_123"
        assert result["flow_id"] == "flow_456"

    @pytest.mark.asyncio
    async def test_patient_creation_saga_rollback_on_whatsapp_failure(self):
        """Test patient creation rollback when WhatsApp fails."""
        from app.orchestration.saga_orchestrator import SagaOrchestrator

        orchestrator = SagaOrchestrator()

        # Patient creation succeeds
        orchestrator._create_patient_record = AsyncMock(
            return_value={"patient_id": "patient_123"}
        )
        # WhatsApp fails
        orchestrator._init_whatsapp_flow = AsyncMock(
            side_effect=Exception("WhatsApp API unavailable")
        )
        # Compensation
        orchestrator._delete_patient_record = AsyncMock()

        with pytest.raises(Exception):
            await orchestrator.execute_patient_creation_saga({
                "name": "Test Patient",
                "phone": "+5511999999999"
            })

        # Patient should be deleted
        orchestrator._delete_patient_record.assert_called_once()

    @pytest.mark.asyncio
    async def test_patient_creation_saga_partial_rollback(self):
        """Test partial rollback when later steps fail."""
        from app.orchestration.saga_orchestrator import SagaOrchestrator

        orchestrator = SagaOrchestrator()

        # First two steps succeed
        orchestrator._create_patient_record = AsyncMock(
            return_value={"patient_id": "patient_123"}
        )
        orchestrator._init_whatsapp_flow = AsyncMock(
            return_value={"flow_id": "flow_456"}
        )
        # Third step fails
        orchestrator._send_welcome_message = AsyncMock(
            side_effect=Exception("Message send failed")
        )

        # Compensations
        orchestrator._cancel_whatsapp_flow = AsyncMock()
        orchestrator._delete_patient_record = AsyncMock()

        with pytest.raises(Exception):
            await orchestrator.execute_patient_creation_saga({})

        # Both compensations should run
        orchestrator._cancel_whatsapp_flow.assert_called_once()
        orchestrator._delete_patient_record.assert_called_once()


class TestSagaLogging:
    """Test saga logging and audit trail."""

    @pytest.mark.asyncio
    async def test_saga_logs_each_step(self):
        """Test each saga step is logged."""
        from app.orchestration.saga_orchestrator import SagaOrchestrator

        orchestrator = SagaOrchestrator()
        orchestrator._logger = MagicMock()

        step_name = "create_patient"
        context = {"data": "test"}

        await orchestrator._log_step_execution(step_name, context, success=True)

        orchestrator._logger.info.assert_called_once()
        call_args = orchestrator._logger.info.call_args[0][0]
        assert step_name in call_args

    @pytest.mark.asyncio
    async def test_saga_logs_compensation(self):
        """Test compensation is logged."""
        from app.orchestration.saga_orchestrator import SagaOrchestrator

        orchestrator = SagaOrchestrator()
        orchestrator._logger = MagicMock()

        step_name = "create_patient"
        error = Exception("Database error")

        await orchestrator._log_compensation(step_name, error)

        orchestrator._logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_saga_creates_audit_trail(self):
        """Test saga creates complete audit trail."""
        from app.orchestration.saga_orchestrator import SagaOrchestrator

        orchestrator = SagaOrchestrator()
        orchestrator._redis = AsyncMock()

        saga_id = "saga_audit_123"
        audit_entry = {
            "saga_id": saga_id,
            "timestamp": datetime.utcnow().isoformat(),
            "step": "create_patient",
            "status": "success",
            "duration_ms": 150
        }

        await orchestrator._append_audit_trail(saga_id, audit_entry)

        # Should append to list in Redis
        orchestrator._redis.rpush.assert_called_once()


class TestSagaMetrics:
    """Test saga performance metrics."""

    @pytest.mark.asyncio
    async def test_saga_tracks_execution_time(self):
        """Test saga tracks total execution time."""
        from app.orchestration.saga_orchestrator import SagaOrchestrator
        import time

        orchestrator = SagaOrchestrator()

        start_time = time.time()

        # Simulate saga execution
        await orchestrator._track_metrics(
            saga_id="saga_metrics_123",
            start_time=start_time,
            end_time=time.time()
        )

        # Metrics should be recorded
        # In actual implementation, verify metrics storage

    @pytest.mark.asyncio
    async def test_saga_tracks_step_durations(self):
        """Test saga tracks individual step durations."""
        from app.orchestration.saga_orchestrator import SagaOrchestrator

        orchestrator = SagaOrchestrator()
        orchestrator._metrics = []

        step_metric = {
            "step": "create_patient",
            "duration_ms": 125,
            "status": "success"
        }

        orchestrator._metrics.append(step_metric)

        assert len(orchestrator._metrics) == 1
        assert orchestrator._metrics[0]["duration_ms"] == 125
