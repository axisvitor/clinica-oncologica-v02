"""
Tests for saga compensation (rollback) scenarios.

QW-002: Tests for atomic saga compensation with proper error propagation.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4

from app.orchestration.saga_orchestrator import (
    SagaOrchestrator,
    SagaCompensationError
)
from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.models.enums import SagaStatus
from app.models.patient import Patient, FlowState
from app.models.message import Message, MessageStatus


class TestSagaCompensationStepWithRetry:
    """Test compensation step retry logic."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = MagicMock()
        db.query = MagicMock(return_value=MagicMock())
        db.add = MagicMock()
        db.commit = MagicMock()
        db.delete = MagicMock()
        return db

    @pytest.fixture
    def mock_saga(self):
        """Create mock saga object."""
        saga = MagicMock(spec=PatientOnboardingSaga)
        saga.id = uuid4()
        saga.patient_id = uuid4()
        saga.doctor_id = uuid4()
        saga.current_step = 4
        saga.status = SagaStatus.COMPENSATING
        saga.execution_log = []
        saga.add_log_entry = MagicMock()
        return saga

    @pytest.fixture
    def orchestrator(self, mock_db):
        """Create orchestrator with mocked dependencies."""
        with patch('app.orchestration.saga_orchestrator.get_redis_client'):
            with patch('app.orchestration.saga_orchestrator.PatientRepository'):
                with patch('app.orchestration.saga_orchestrator.PatientFlowService'):
                    with patch('app.orchestration.saga_orchestrator.UnifiedWhatsAppService'):
                        with patch('app.orchestration.saga_orchestrator.MessageService'):
                            orch = SagaOrchestrator(mock_db)
                            orch.redis = AsyncMock()
                            return orch

    @pytest.mark.asyncio
    async def test_compensation_step_succeeds_first_try(self, orchestrator, mock_saga):
        """Test compensation succeeds on first attempt."""
        compensation_errors = []
        compensate_fn = AsyncMock()

        await orchestrator._compensate_step_with_retry(
            saga=mock_saga,
            step_num=3,
            step_name="test_compensation",
            compensate_fn=compensate_fn,
            compensation_errors=compensation_errors,
            max_retries=3
        )

        compensate_fn.assert_called_once_with(mock_saga)
        mock_saga.add_log_entry.assert_called_once_with(3, "test_compensation", "compensated")
        assert len(compensation_errors) == 0

    @pytest.mark.asyncio
    async def test_compensation_step_succeeds_after_retry(self, orchestrator, mock_saga):
        """Test compensation succeeds after initial failures."""
        compensation_errors = []
        # Fail twice, succeed on third
        compensate_fn = AsyncMock(side_effect=[
            Exception("Transient error 1"),
            Exception("Transient error 2"),
            None  # Success
        ])

        await orchestrator._compensate_step_with_retry(
            saga=mock_saga,
            step_num=3,
            step_name="test_compensation",
            compensate_fn=compensate_fn,
            compensation_errors=compensation_errors,
            max_retries=3
        )

        assert compensate_fn.call_count == 3
        mock_saga.add_log_entry.assert_called_with(3, "test_compensation", "compensated")
        assert len(compensation_errors) == 0

    @pytest.mark.asyncio
    async def test_compensation_step_fails_after_max_retries(self, orchestrator, mock_saga):
        """Test compensation failure after exhausting retries."""
        compensation_errors = []
        error = Exception("Persistent failure")
        compensate_fn = AsyncMock(side_effect=error)

        await orchestrator._compensate_step_with_retry(
            saga=mock_saga,
            step_num=3,
            step_name="test_compensation",
            compensate_fn=compensate_fn,
            compensation_errors=compensation_errors,
            max_retries=3
        )

        assert compensate_fn.call_count == 3
        mock_saga.add_log_entry.assert_called_with(
            3, "test_compensation", "compensation_failed", "Persistent failure"
        )
        assert len(compensation_errors) == 1
        assert compensation_errors[0][0] == 3
        assert str(compensation_errors[0][1]) == "Persistent failure"


class TestSagaCompensateMessage:
    """Test message compensation step."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = MagicMock()
        return db

    @pytest.fixture
    def mock_saga(self):
        """Create mock saga object."""
        saga = MagicMock(spec=PatientOnboardingSaga)
        saga.id = uuid4()
        saga.patient_id = uuid4()
        return saga

    @pytest.fixture
    def orchestrator(self, mock_db):
        """Create orchestrator with mocked dependencies."""
        with patch('app.orchestration.saga_orchestrator.get_redis_client'):
            with patch('app.orchestration.saga_orchestrator.PatientRepository'):
                with patch('app.orchestration.saga_orchestrator.PatientFlowService'):
                    with patch('app.orchestration.saga_orchestrator.UnifiedWhatsAppService'):
                        with patch('app.orchestration.saga_orchestrator.MessageService'):
                            return SagaOrchestrator(mock_db)

    @pytest.mark.asyncio
    async def test_compensate_message_marks_as_cancelled(self, orchestrator, mock_saga, mock_db):
        """Test message compensation marks messages as cancelled."""
        # Create mock messages
        message1 = MagicMock(spec=Message)
        message1.message_metadata = {"saga_id": str(mock_saga.id)}
        message2 = MagicMock(spec=Message)
        message2.message_metadata = {"saga_id": str(mock_saga.id)}

        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = [message1, message2]
        mock_db.query.return_value = mock_query

        await orchestrator._compensate_message(mock_saga)

        assert message1.status == MessageStatus.CANCELLED
        assert message2.status == MessageStatus.CANCELLED
        assert "cancelled_by" in message1.message_metadata
        assert message1.message_metadata["cancelled_by"] == "saga_compensation"

    @pytest.mark.asyncio
    async def test_compensate_message_handles_no_messages(self, orchestrator, mock_saga, mock_db):
        """Test message compensation handles case with no messages."""
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        # Should not raise
        await orchestrator._compensate_message(mock_saga)


class TestSagaCompensateFlow:
    """Test flow compensation step."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = MagicMock()
        return db

    @pytest.fixture
    def mock_saga(self):
        """Create mock saga object."""
        saga = MagicMock(spec=PatientOnboardingSaga)
        saga.id = uuid4()
        saga.patient_id = uuid4()
        return saga

    @pytest.fixture
    def orchestrator(self, mock_db):
        """Create orchestrator with mocked dependencies."""
        with patch('app.orchestration.saga_orchestrator.get_redis_client'):
            with patch('app.orchestration.saga_orchestrator.PatientRepository'):
                with patch('app.orchestration.saga_orchestrator.PatientFlowService'):
                    with patch('app.orchestration.saga_orchestrator.UnifiedWhatsAppService'):
                        with patch('app.orchestration.saga_orchestrator.MessageService'):
                            return SagaOrchestrator(mock_db)

    @pytest.mark.asyncio
    async def test_compensate_flow_deletes_flow_states(self, orchestrator, mock_saga, mock_db):
        """Test flow compensation deletes flow states."""
        flow_state1 = MagicMock(spec=FlowState)
        flow_state2 = MagicMock(spec=FlowState)

        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = [flow_state1, flow_state2]
        mock_db.query.return_value = mock_query

        await orchestrator._compensate_flow(mock_saga)

        assert mock_db.delete.call_count == 2
        mock_db.delete.assert_any_call(flow_state1)
        mock_db.delete.assert_any_call(flow_state2)

    @pytest.mark.asyncio
    async def test_compensate_flow_handles_no_patient_id(self, orchestrator, mock_db):
        """Test flow compensation handles missing patient_id."""
        saga = MagicMock(spec=PatientOnboardingSaga)
        saga.id = uuid4()
        saga.patient_id = None

        # Should not raise and not query
        await orchestrator._compensate_flow(saga)
        mock_db.query.assert_not_called()


class TestSagaCompensatePatient:
    """Test patient compensation step."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = MagicMock()
        return db

    @pytest.fixture
    def mock_saga(self):
        """Create mock saga object."""
        saga = MagicMock(spec=PatientOnboardingSaga)
        saga.id = uuid4()
        saga.patient_id = uuid4()
        return saga

    @pytest.fixture
    def orchestrator(self, mock_db):
        """Create orchestrator with mocked dependencies."""
        with patch('app.orchestration.saga_orchestrator.get_redis_client'):
            with patch('app.orchestration.saga_orchestrator.PatientRepository') as MockRepo:
                with patch('app.orchestration.saga_orchestrator.PatientFlowService'):
                    with patch('app.orchestration.saga_orchestrator.UnifiedWhatsAppService'):
                        with patch('app.orchestration.saga_orchestrator.MessageService'):
                            orch = SagaOrchestrator(mock_db)
                            orch.patient_repo = MagicMock()
                            return orch

    @pytest.mark.asyncio
    async def test_compensate_patient_deletes_patient(self, orchestrator, mock_saga, mock_db):
        """Test patient compensation deletes patient record."""
        patient = MagicMock(spec=Patient)
        orchestrator.patient_repo.get_by_id.return_value = patient

        await orchestrator._compensate_patient(mock_saga)

        orchestrator.patient_repo.get_by_id.assert_called_once_with(mock_saga.patient_id)
        mock_db.delete.assert_called_once_with(patient)

    @pytest.mark.asyncio
    async def test_compensate_patient_handles_already_deleted(self, orchestrator, mock_saga, mock_db):
        """Test patient compensation handles already deleted patient."""
        orchestrator.patient_repo.get_by_id.return_value = None

        # Should not raise
        await orchestrator._compensate_patient(mock_saga)
        mock_db.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_compensate_patient_handles_no_patient_id(self, orchestrator, mock_db):
        """Test patient compensation handles missing patient_id."""
        saga = MagicMock(spec=PatientOnboardingSaga)
        saga.id = uuid4()
        saga.patient_id = None

        await orchestrator._compensate_patient(saga)
        orchestrator.patient_repo.get_by_id.assert_not_called()


class TestSagaCompensationInternal:
    """Test full internal compensation flow."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = MagicMock()
        db.commit = MagicMock()
        return db

    @pytest.fixture
    def mock_saga(self):
        """Create mock saga object."""
        saga = MagicMock(spec=PatientOnboardingSaga)
        saga.id = uuid4()
        saga.patient_id = uuid4()
        saga.doctor_id = uuid4()
        saga.current_step = 4
        saga.status = SagaStatus.FAILED
        saga.execution_log = []
        saga.add_log_entry = MagicMock()
        return saga

    @pytest.fixture
    def orchestrator(self, mock_db):
        """Create orchestrator with mocked dependencies."""
        with patch('app.orchestration.saga_orchestrator.get_redis_client'):
            with patch('app.orchestration.saga_orchestrator.PatientRepository') as MockRepo:
                with patch('app.orchestration.saga_orchestrator.PatientFlowService'):
                    with patch('app.orchestration.saga_orchestrator.UnifiedWhatsAppService'):
                        with patch('app.orchestration.saga_orchestrator.MessageService'):
                            orch = SagaOrchestrator(mock_db)
                            orch.patient_repo = MagicMock()
                            return orch

    @pytest.mark.asyncio
    async def test_compensate_saga_internal_all_steps_succeed(self, orchestrator, mock_saga, mock_db):
        """Test compensation succeeds for all steps."""
        # Mock all compensation methods
        orchestrator._compensate_message = AsyncMock()
        orchestrator._compensate_flow = AsyncMock()
        orchestrator._compensate_patient = AsyncMock()
        orchestrator._compensate_step_with_retry = AsyncMock()

        await orchestrator._compensate_saga_internal(mock_saga)

        # Should call compensation for steps 4, 3, 1 (step 2 is skipped)
        assert orchestrator._compensate_step_with_retry.call_count == 3
        mock_db.commit.assert_called_once()
        assert mock_saga.status == SagaStatus.FAILED

    @pytest.mark.asyncio
    async def test_compensate_saga_internal_raises_on_failure(self, orchestrator, mock_saga, mock_db):
        """Test compensation raises SagaCompensationError on failure."""
        error = Exception("Compensation failed")

        async def mock_compensate_with_retry(saga, step_num, step_name, compensate_fn, compensation_errors, max_retries=3):
            compensation_errors.append((step_num, error))

        orchestrator._compensate_step_with_retry = mock_compensate_with_retry
        orchestrator._track_compensation_failure = AsyncMock()

        with pytest.raises(SagaCompensationError) as exc_info:
            await orchestrator._compensate_saga_internal(mock_saga)

        assert mock_saga.id in str(exc_info.value.saga_id)


class TestSagaCompensationError:
    """Test SagaCompensationError exception."""

    def test_saga_compensation_error_attributes(self):
        """Test SagaCompensationError has correct attributes."""
        original = ValueError("Original error")
        saga_id = uuid4()

        error = SagaCompensationError(
            message="Compensation failed",
            original_error=original,
            saga_id=saga_id
        )

        assert error.message == "Compensation failed"
        assert error.original_error == original
        assert error.saga_id == saga_id
        assert str(error) == "Compensation failed"


class TestTrackCompensationFailure:
    """Test compensation failure tracking."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def orchestrator(self, mock_db):
        """Create orchestrator with mocked dependencies."""
        with patch('app.orchestration.saga_orchestrator.get_redis_client'):
            with patch('app.orchestration.saga_orchestrator.PatientRepository'):
                with patch('app.orchestration.saga_orchestrator.PatientFlowService'):
                    with patch('app.orchestration.saga_orchestrator.UnifiedWhatsAppService'):
                        with patch('app.orchestration.saga_orchestrator.MessageService'):
                            orch = SagaOrchestrator(mock_db)
                            orch.redis = MagicMock()
                            orch.redis.setex = MagicMock()
                            return orch

    @pytest.mark.asyncio
    async def test_track_compensation_failure_stores_in_redis(self, orchestrator):
        """Test compensation failure is stored in Redis."""
        saga_id = uuid4()
        error = Exception("Test error")

        await orchestrator._track_compensation_failure(saga_id, 3, error)

        orchestrator.redis.setex.assert_called_once()
        call_args = orchestrator.redis.setex.call_args
        key = call_args[0][0]
        ttl = call_args[0][1]
        data = json.loads(call_args[0][2])

        assert f"saga:compensation_failure:{saga_id}" == key
        assert ttl == 86400 * 7  # 7 days
        assert data["saga_id"] == str(saga_id)
        assert data["step"] == 3
        assert data["error"] == "Test error"
        assert data["error_type"] == "Exception"

    @pytest.mark.asyncio
    async def test_track_compensation_failure_handles_redis_error(self, orchestrator):
        """Test tracking handles Redis errors gracefully."""
        saga_id = uuid4()
        orchestrator.redis.setex.side_effect = Exception("Redis connection error")

        # Should not raise
        await orchestrator._track_compensation_failure(saga_id, 3, Exception("Test"))


class TestGetSagaStatus:
    """Test get_saga_status method."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def orchestrator(self, mock_db):
        """Create orchestrator with mocked dependencies."""
        with patch('app.orchestration.saga_orchestrator.get_redis_client'):
            with patch('app.orchestration.saga_orchestrator.PatientRepository'):
                with patch('app.orchestration.saga_orchestrator.PatientFlowService'):
                    with patch('app.orchestration.saga_orchestrator.UnifiedWhatsAppService'):
                        with patch('app.orchestration.saga_orchestrator.MessageService'):
                            return SagaOrchestrator(mock_db)

    @pytest.mark.asyncio
    async def test_get_saga_status_returns_status(self, orchestrator, mock_db):
        """Test get_saga_status returns correct status."""
        saga_id = uuid4()
        saga = MagicMock(spec=PatientOnboardingSaga)
        saga.id = saga_id
        saga.status = SagaStatus.COMPLETED
        saga.current_step = 4
        saga.patient_id = uuid4()
        saga.doctor_id = uuid4()
        saga.started_at = datetime.utcnow()
        saga.completed_at = datetime.utcnow()
        saga.failed_at = None
        saga.error_message = None
        saga.error_type = None
        saga.execution_log = []

        mock_db.query.return_value.filter.return_value.first.return_value = saga

        result = await orchestrator.get_saga_status(saga_id)

        assert result["id"] == str(saga_id)
        assert result["status"] == SagaStatus.COMPLETED.value
        assert result["current_step"] == 4

    @pytest.mark.asyncio
    async def test_get_saga_status_returns_none_when_not_found(self, orchestrator, mock_db):
        """Test get_saga_status returns None when saga not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = await orchestrator.get_saga_status(uuid4())

        assert result is None


class TestListFailedSagas:
    """Test list_failed_sagas method."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def orchestrator(self, mock_db):
        """Create orchestrator with mocked dependencies."""
        with patch('app.orchestration.saga_orchestrator.get_redis_client'):
            with patch('app.orchestration.saga_orchestrator.PatientRepository'):
                with patch('app.orchestration.saga_orchestrator.PatientFlowService'):
                    with patch('app.orchestration.saga_orchestrator.UnifiedWhatsAppService'):
                        with patch('app.orchestration.saga_orchestrator.MessageService'):
                            return SagaOrchestrator(mock_db)

    @pytest.mark.asyncio
    async def test_list_failed_sagas_returns_list(self, orchestrator, mock_db):
        """Test list_failed_sagas returns list of failed sagas."""
        saga1 = MagicMock(spec=PatientOnboardingSaga)
        saga1.id = uuid4()
        saga1.doctor_id = uuid4()
        saga1.current_step = 2
        saga1.error_message = "Error 1"
        saga1.error_type = "Exception"
        saga1.failed_at = datetime.utcnow()
        saga1.retry_count = 1

        saga2 = MagicMock(spec=PatientOnboardingSaga)
        saga2.id = uuid4()
        saga2.doctor_id = uuid4()
        saga2.current_step = 3
        saga2.error_message = "Error 2"
        saga2.error_type = "ValueError"
        saga2.failed_at = datetime.utcnow()
        saga2.retry_count = 0

        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [saga1, saga2]

        result = await orchestrator.list_failed_sagas()

        assert len(result) == 2
        assert result[0]["id"] == str(saga1.id)
        assert result[1]["error_type"] == "ValueError"

    @pytest.mark.asyncio
    async def test_list_failed_sagas_filters_by_doctor(self, orchestrator, mock_db):
        """Test list_failed_sagas filters by doctor_id."""
        doctor_id = uuid4()

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        await orchestrator.list_failed_sagas(doctor_id=doctor_id, limit=10)

        # Verify filter was called twice (once for status, once for doctor_id)
        assert mock_query.filter.call_count == 2
