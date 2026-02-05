"""
Tests for CompletionService - Patient onboarding completion logic.

This test suite validates the CompletionService functionality including:
- Partial onboarding completion
- Patient data updates
- Flow state initialization
- Error handling and rollback
- Notification integration

File: backend-hormonia/tests/domain/patient/onboarding/test_completion_service.py
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime

from app.domain.patient.onboarding.completion_service import CompletionService
from app.models.patient import Patient, FlowState
from app.schemas.patient import PatientCreate
from app.models.flow import PatientFlowState


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    db.rollback = Mock()
    db.query = Mock()
    return db


@pytest.fixture
def mock_flow_service():
    """Mock PatientFlowService."""
    service = Mock()
    service.initialize_default_flow = AsyncMock()
    return service


@pytest.fixture
def mock_notification_service():
    """Mock NotificationService."""
    service = Mock()
    service.publish_patient_created_event = AsyncMock(return_value=True)
    service.send_welcome_if_needed = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_executor():
    """Mock ThreadPoolExecutor."""
    executor = Mock()
    executor.shutdown = Mock()
    return executor


@pytest.fixture
def completion_service(
    mock_db, mock_flow_service, mock_notification_service, sync_executor
):
    """Create CompletionService with mocked dependencies."""
    return CompletionService(
        db=mock_db,
        flow_service=mock_flow_service,
        notification_service=mock_notification_service,
        executor=sync_executor,
    )


@pytest.fixture
def sample_patient():
    """Create a sample patient object."""
    patient = Patient(
        id=uuid4(),
        name="João Silva",
        phone="+5511999999999",
        email="joao@example.com",
        cpf="12345678909",
        birth_date=datetime(1990, 1, 1).date(),
        treatment_type="Oncologia",
        doctor_id=uuid4(),
        flow_state=FlowState.ONBOARDING,
        patient_data={},
    )
    return patient


@pytest.fixture
def partial_patient():
    """Create a partial patient (missing some data)."""
    patient = Patient(
        id=uuid4(),
        name=None,  # Missing
        phone="+5511999999999",
        email=None,  # Missing
        cpf="12345678909",
        birth_date=None,  # Missing
        treatment_type=None,  # Missing
        doctor_id=uuid4(),
        flow_state=FlowState.ONBOARDING,
        patient_data={},
    )
    return patient


@pytest.fixture
def patient_data():
    """Create sample PatientCreate data."""
    return PatientCreate(
        name="João Silva",
        phone="+5511999999999",
        email="joao@example.com",
        cpf="12345678909",
        birth_date=datetime(1990, 1, 1).date(),
        treatment_type="Oncologia",
        metadata={
            "system": {"source": "web"},
            "custom_fields": {"campaign": "summer2025"},
        },
    )


# =============================================================================
# Test Class 1: Initialization
# =============================================================================


class TestCompletionServiceInitialization:
    """Test CompletionService initialization."""

    def test_init_with_all_dependencies(
        self, mock_db, mock_flow_service, mock_notification_service, mock_executor
    ):
        """
        GIVEN: All required dependencies
        WHEN: CompletionService is initialized
        THEN: All dependencies are set correctly
        """
        service = CompletionService(
            db=mock_db,
            flow_service=mock_flow_service,
            notification_service=mock_notification_service,
            executor=mock_executor,
        )

        assert service.db == mock_db
        assert service.flow_service == mock_flow_service
        assert service.notification_service == mock_notification_service
        assert service._executor == mock_executor

    @patch("app.domain.patient.onboarding.completion_service.get_io_executor")
    def test_init_creates_default_executor(
        self, mock_get_io_executor, mock_db, mock_flow_service, mock_notification_service
    ):
        """
        GIVEN: No executor provided
        WHEN: CompletionService is initialized
        THEN: A default ThreadPoolExecutor is created
        """
        mock_executor = Mock()
        mock_get_io_executor.return_value = mock_executor

        service = CompletionService(
            db=mock_db,
            flow_service=mock_flow_service,
            notification_service=mock_notification_service,
        )

        mock_get_io_executor.assert_called_once_with()
        assert service._executor == mock_executor


# =============================================================================
# Test Class 2: Complete Partial Onboarding
# =============================================================================


class TestCompletePartialOnboarding:
    """Test complete_partial_onboarding method."""

    @pytest.mark.asyncio
    async def test_complete_partial_onboarding_success(
        self,
        completion_service,
        partial_patient,
        patient_data,
        mock_db,
        mock_flow_service,
        mock_notification_service,
    ):
        """
        GIVEN: Partial patient and complete patient data
        WHEN: complete_partial_onboarding is called
        THEN: Patient is updated, notifications sent, flow initialized
        """
        current_user = Mock()
        current_user.id = uuid4()

        # Mock asyncio executor
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_event_loop = AsyncMock()
            mock_loop.return_value = mock_event_loop
            mock_event_loop.run_in_executor = AsyncMock(
                side_effect=lambda executor, func: func() if callable(func) else None
            )

            # Mock cache manager
            with patch(
                "app.domain.patient.onboarding.completion_service.get_cache_manager"
            ) as mock_cache:
                mock_cache_manager = Mock()
                mock_cache_manager.invalidate_pattern = Mock()
                mock_cache.return_value = mock_cache_manager

                # Mock flow query to return None (no existing flow)
                mock_db.query.return_value.filter.return_value.first.return_value = (
                    None
                )

                # Execute
                result = await completion_service.complete_partial_onboarding(
                    partial_patient, patient_data, current_user
                )

                # Assert
                assert result == partial_patient
                assert partial_patient.name == "João Silva"
                assert partial_patient.email == "joao@example.com"
                assert partial_patient.birth_date == datetime(1990, 1, 1).date()  # DB returns date, not datetime
                assert partial_patient.treatment_type == "Oncologia"

                # Verify notifications
                mock_notification_service.publish_patient_created_event.assert_called_once()
                mock_notification_service.send_welcome_if_needed.assert_called_once()

                # Verify flow initialization
                mock_flow_service.initialize_default_flow.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_partial_onboarding_preserves_existing_data(
        self,
        completion_service,
        sample_patient,
        patient_data,
        mock_notification_service,
        mock_db,
    ):
        """
        GIVEN: Patient with existing data
        WHEN: complete_partial_onboarding is called with new data
        THEN: Existing data is preserved (not overwritten)
        """
        # Store original values
        original_name = sample_patient.name
        original_email = sample_patient.email

        # Mock asyncio executor
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_event_loop = AsyncMock()
            mock_loop.return_value = mock_event_loop
            mock_event_loop.run_in_executor = AsyncMock(
                side_effect=lambda executor, func: func() if callable(func) else None
            )

            # Mock cache manager
            with patch(
                "app.domain.patient.onboarding.completion_service.get_cache_manager"
            ) as mock_cache:
                mock_cache.return_value = Mock()

                # Mock flow query
                mock_db.query.return_value.filter.return_value.first.return_value = (
                    Mock()
                )  # Existing flow

                # Execute with different data (should be preserved)
                new_data = PatientCreate(
                    name="Different Name",
                    phone=sample_patient.phone,
                    email="different@example.com",
                    cpf=sample_patient.cpf,
                )
                result = await completion_service.complete_partial_onboarding(
                    sample_patient, new_data, None
                )

                # Assert original data preserved
                assert result.name == original_name
                assert result.email == original_email

    @pytest.mark.asyncio
    async def test_complete_partial_onboarding_handles_commit_error(
        self, completion_service, partial_patient, patient_data, mock_db
    ):
        """
        GIVEN: Database commit fails
        WHEN: complete_partial_onboarding is called
        THEN: Exception is raised and rollback is called
        """
        # Mock asyncio executor to raise exception on commit
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_event_loop = AsyncMock()
            mock_loop.return_value = mock_event_loop

            def executor_side_effect(executor, func):
                if func == mock_db.commit:
                    raise Exception("Database commit failed")
                return func() if callable(func) else None

            mock_event_loop.run_in_executor = AsyncMock(side_effect=executor_side_effect)

            # Execute and expect exception
            with pytest.raises(Exception, match="Database commit failed"):
                await completion_service.complete_partial_onboarding(
                    partial_patient, patient_data, None
                )

    @pytest.mark.asyncio
    async def test_complete_partial_onboarding_continues_on_notification_failure(
        self,
        completion_service,
        partial_patient,
        patient_data,
        mock_notification_service,
        mock_db,
    ):
        """
        GIVEN: Notification service fails
        WHEN: complete_partial_onboarding is called
        THEN: Process continues and returns patient (failure is logged)
        """
        # Mock notification failure
        mock_notification_service.publish_patient_created_event.side_effect = Exception(
            "WebSocket error"
        )

        # Mock asyncio executor
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_event_loop = AsyncMock()
            mock_loop.return_value = mock_event_loop
            mock_event_loop.run_in_executor = AsyncMock(
                side_effect=lambda executor, func: func() if callable(func) else None
            )

            # Mock cache manager
            with patch(
                "app.domain.patient.onboarding.completion_service.get_cache_manager"
            ) as mock_cache:
                mock_cache.return_value = Mock()

                # Mock flow query
                mock_db.query.return_value.filter.return_value.first.return_value = (
                    Mock()
                )

                # Execute - should NOT raise exception
                result = await completion_service.complete_partial_onboarding(
                    partial_patient, patient_data, None
                )

                # Assert patient returned despite notification failure
                assert result == partial_patient


# =============================================================================
# Test Class 3: Update Patient Data
# =============================================================================


class TestUpdatePatientData:
    """Test _update_patient_data method."""

    @pytest.mark.asyncio
    async def test_updates_empty_fields_only(
        self, completion_service, partial_patient, patient_data
    ):
        """
        GIVEN: Partial patient with some empty fields
        WHEN: _update_patient_data is called
        THEN: Only empty fields are updated
        """
        await completion_service._update_patient_data(partial_patient, patient_data)

        assert partial_patient.name == "João Silva"
        assert partial_patient.email == "joao@example.com"
        assert partial_patient.birth_date == datetime(1990, 1, 1).date()  # DB returns date
        assert partial_patient.treatment_type == "Oncologia"

    @pytest.mark.asyncio
    async def test_preserves_existing_fields(
        self, completion_service, sample_patient, patient_data
    ):
        """
        GIVEN: Patient with existing data
        WHEN: _update_patient_data is called
        THEN: Existing fields are NOT overwritten
        """
        original_name = sample_patient.name
        original_email = sample_patient.email

        await completion_service._update_patient_data(sample_patient, patient_data)

        assert sample_patient.name == original_name
        assert sample_patient.email == original_email

    @pytest.mark.asyncio
    async def test_updates_metadata(self, completion_service, partial_patient):
        """
        GIVEN: Patient data with metadata
        WHEN: _update_patient_data is called
        THEN: Metadata is merged into patient_data
        """
        patient_data = PatientCreate(
            phone=partial_patient.phone,
            name="João Silva",
            metadata={
                "system": {"source": "web"},
                "custom_fields": {"campaign": "summer2025"},
            },
        )

        await completion_service._update_patient_data(partial_patient, patient_data)

        assert partial_patient.patient_data["system"]["source"] == "web"
        assert partial_patient.patient_data["custom_fields"]["campaign"] == "summer2025"

    @pytest.mark.asyncio
    async def test_creates_patient_data_if_none(
        self, completion_service, partial_patient
    ):
        """
        GIVEN: Patient with no patient_data (None)
        WHEN: _update_patient_data is called with metadata
        THEN: patient_data is created and metadata added
        """
        partial_patient.patient_data = None
        patient_data = PatientCreate(
            phone=partial_patient.phone,
            name="João Silva",
            metadata={"custom_fields": {"key": "value"}}
        )

        await completion_service._update_patient_data(partial_patient, patient_data)

        assert partial_patient.patient_data is not None
        assert partial_patient.patient_data["custom_fields"]["key"] == "value"


# =============================================================================
# Test Class 4: Initialize Flow State
# =============================================================================


class TestInitializeFlowState:
    """Test _initialize_flow_if_needed method (renamed from _initialize_flow_state)."""

    @pytest.mark.asyncio
    async def test_initializes_flow_if_not_exists(
        self, completion_service, sample_patient, mock_flow_service, mock_db
    ):
        """
        GIVEN: Patient with no existing flow
        WHEN: _initialize_flow_if_needed is called
        THEN: Flow is initialized via flow_service
        """
        # Mock asyncio executor
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_event_loop = AsyncMock()
            mock_loop.return_value = mock_event_loop
            mock_event_loop.run_in_executor = AsyncMock(return_value=None)

            # Mock flow query to return None (no existing flow)
            mock_db.query.return_value.filter.return_value.first.return_value = None

            current_user = Mock()
            current_user.id = uuid4()

            await completion_service._initialize_flow_if_needed(sample_patient, current_user)

            mock_flow_service.initialize_default_flow.assert_called_once_with(
                sample_patient, current_user.id
            )

    @pytest.mark.asyncio
    async def test_skips_if_flow_exists(
        self, completion_service, sample_patient, mock_flow_service, mock_db
    ):
        """
        GIVEN: Patient with existing flow
        WHEN: _initialize_flow_if_needed is called
        THEN: Flow initialization is skipped
        """
        # Mock asyncio executor
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_event_loop = AsyncMock()
            mock_loop.return_value = mock_event_loop
            mock_event_loop.run_in_executor = AsyncMock(
                return_value=Mock()
            )  # Existing flow

            # Mock flow query to return existing flow
            existing_flow = Mock(spec=PatientFlowState)
            mock_db.query.return_value.filter.return_value.first.return_value = (
                existing_flow
            )

            await completion_service._initialize_flow_if_needed(sample_patient, None)

            mock_flow_service.initialize_default_flow.assert_not_called()

    @pytest.mark.asyncio
    async def test_continues_on_flow_initialization_error(
        self, completion_service, sample_patient, mock_flow_service, mock_db
    ):
        """
        GIVEN: Flow initialization fails
        WHEN: _initialize_flow_if_needed is called
        THEN: Exception is logged but method completes (no exception raised)
        """
        # Mock asyncio executor
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_event_loop = AsyncMock()
            mock_loop.return_value = mock_event_loop
            mock_event_loop.run_in_executor = AsyncMock(return_value=None)

            # Mock flow query to return None
            mock_db.query.return_value.filter.return_value.first.return_value = None

            # Mock flow service to raise exception
            mock_flow_service.initialize_default_flow.side_effect = Exception(
                "Flow error"
            )

            # Execute - should NOT raise exception
            await completion_service._initialize_flow_if_needed(sample_patient, None)

            # Verify flow initialization was attempted
            mock_flow_service.initialize_default_flow.assert_called_once()


# =============================================================================
# Test Class 5: Service Shutdown
# =============================================================================


class TestCompletionServiceShutdown:
    """Test CompletionService shutdown."""

    def test_shutdown_graceful(
        self,
        mock_db,
        mock_flow_service,
        mock_notification_service,
        mock_executor,
    ):
        """
        GIVEN: CompletionService with active executor
        WHEN: shutdown is called with wait=True
        THEN: Executor is shutdown gracefully
        """
        service = CompletionService(
            db=mock_db,
            flow_service=mock_flow_service,
            notification_service=mock_notification_service,
            executor=mock_executor,
        )

        service.shutdown(wait=True)

        mock_executor.shutdown.assert_called_once_with(wait=True)

    def test_shutdown_no_wait(
        self,
        mock_db,
        mock_flow_service,
        mock_notification_service,
        mock_executor,
    ):
        """
        GIVEN: CompletionService with active executor
        WHEN: shutdown is called with wait=False
        THEN: Executor is shutdown immediately
        """
        service = CompletionService(
            db=mock_db,
            flow_service=mock_flow_service,
            notification_service=mock_notification_service,
            executor=mock_executor,
        )

        service.shutdown(wait=False)

        mock_executor.shutdown.assert_called_once_with(wait=False)

    def test_shutdown_default_wait(
        self,
        mock_db,
        mock_flow_service,
        mock_notification_service,
        mock_executor,
    ):
        """
        GIVEN: CompletionService with active executor
        WHEN: shutdown is called without arguments
        THEN: Executor is shutdown with default wait=True
        """
        service = CompletionService(
            db=mock_db,
            flow_service=mock_flow_service,
            notification_service=mock_notification_service,
            executor=mock_executor,
        )

        service.shutdown()

        mock_executor.shutdown.assert_called_once_with(wait=True)


# =============================================================================
# Test Class 6: Integration Tests
# =============================================================================


class TestCompletionServiceIntegration:
    """Integration tests for CompletionService."""

    @pytest.mark.asyncio
    async def test_full_completion_workflow(
        self,
        completion_service,
        partial_patient,
        patient_data,
        mock_flow_service,
        mock_notification_service,
        mock_db,
    ):
        """
        GIVEN: Partial patient and complete patient data
        WHEN: Full completion workflow is executed
        THEN: All steps complete successfully
        """
        current_user = Mock()
        current_user.id = uuid4()

        # Mock asyncio executor
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_event_loop = AsyncMock()
            mock_loop.return_value = mock_event_loop
            mock_event_loop.run_in_executor = AsyncMock(
                side_effect=lambda executor, func: func() if callable(func) else None
            )

            # Mock cache manager
            with patch(
                "app.domain.patient.onboarding.completion_service.get_cache_manager"
            ) as mock_cache:
                mock_cache.return_value = Mock()

                # Mock flow query
                mock_db.query.return_value.filter.return_value.first.return_value = (
                    None
                )

                # Execute
                result = await completion_service.complete_partial_onboarding(
                    partial_patient, patient_data, current_user
                )

                # Verify all steps
                assert result == partial_patient
                assert result.name == "João Silva"
                mock_notification_service.publish_patient_created_event.assert_called_once()
                mock_notification_service.send_welcome_if_needed.assert_called_once()
                mock_flow_service.initialize_default_flow.assert_called_once()

    @pytest.mark.asyncio
    async def test_completion_with_partial_failure(
        self,
        completion_service,
        partial_patient,
        patient_data,
        mock_notification_service,
        mock_flow_service,
        mock_db,
    ):
        """
        GIVEN: Some services fail during completion
        WHEN: Completion is executed
        THEN: Process continues and patient is returned
        """
        # Mock notification failure
        mock_notification_service.send_welcome_if_needed.side_effect = Exception(
            "WhatsApp error"
        )

        # Mock asyncio executor
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_event_loop = AsyncMock()
            mock_loop.return_value = mock_event_loop
            mock_event_loop.run_in_executor = AsyncMock(
                side_effect=lambda executor, func: func() if callable(func) else None
            )

            # Mock cache manager
            with patch(
                "app.domain.patient.onboarding.completion_service.get_cache_manager"
            ) as mock_cache:
                mock_cache.return_value = Mock()

                # Mock flow query
                mock_db.query.return_value.filter.return_value.first.return_value = (
                    None
                )

                # Execute - should complete despite partial failure
                result = await completion_service.complete_partial_onboarding(
                    partial_patient, patient_data, None
                )

                # Assert patient returned
                assert result == partial_patient
                # Flow initialization should still be called
                mock_flow_service.initialize_default_flow.assert_called_once()


# =============================================================================
# Test Class 7: Edge Cases
# =============================================================================


class TestCompletionServiceEdgeCases:
    """Test edge cases for CompletionService."""

    @pytest.mark.asyncio
    async def test_completion_with_none_user(
        self, completion_service, partial_patient, patient_data, mock_db
    ):
        """
        GIVEN: No current user (None)
        WHEN: complete_partial_onboarding is called
        THEN: Process completes without user context
        """
        # Mock asyncio executor
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_event_loop = AsyncMock()
            mock_loop.return_value = mock_event_loop
            mock_event_loop.run_in_executor = AsyncMock(
                side_effect=lambda executor, func: func() if callable(func) else None
            )

            # Mock cache manager
            with patch(
                "app.domain.patient.onboarding.completion_service.get_cache_manager"
            ) as mock_cache:
                mock_cache.return_value = Mock()

                # Mock flow query
                mock_db.query.return_value.filter.return_value.first.return_value = (
                    Mock()
                )

                # Execute with None user
                result = await completion_service.complete_partial_onboarding(
                    partial_patient, patient_data, None
                )

                assert result == partial_patient

    @pytest.mark.asyncio
    async def test_completion_with_empty_metadata(
        self, completion_service, partial_patient, mock_db
    ):
        """
        GIVEN: Patient data with no metadata
        WHEN: complete_partial_onboarding is called
        THEN: Process completes without metadata update
        """
        patient_data = PatientCreate(
            phone=partial_patient.phone,
            name="João Silva",
            cpf=partial_patient.cpf,
        )  # No metadata

        # Mock asyncio executor
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_event_loop = AsyncMock()
            mock_loop.return_value = mock_event_loop
            mock_event_loop.run_in_executor = AsyncMock(
                side_effect=lambda executor, func: func() if callable(func) else None
            )

            # Mock cache manager
            with patch(
                "app.domain.patient.onboarding.completion_service.get_cache_manager"
            ) as mock_cache:
                mock_cache.return_value = Mock()

                # Mock flow query
                mock_db.query.return_value.filter.return_value.first.return_value = (
                    Mock()
                )

                # Execute
                result = await completion_service.complete_partial_onboarding(
                    partial_patient, patient_data, None
                )

                assert result == partial_patient
                assert result.name == "João Silva"
