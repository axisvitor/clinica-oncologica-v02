"""
Test suite for OnboardingCoordinator.

Tests the high-level orchestration of patient onboarding workflow.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.domain.patient.onboarding.coordinator import OnboardingCoordinator
from app.models.patient import Patient
from app.schemas.patient import PatientCreate
from app.exceptions import ValidationError


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.refresh = MagicMock()
    return db


@pytest.fixture
def mock_integrity_service():
    """Mock IntegrityService."""
    service = MagicMock()
    service.validate_patient_data = AsyncMock(return_value=None)
    service.generate_patient_hash = MagicMock(return_value="test_hash_123")
    return service


@pytest.fixture
def mock_validation_service():
    """Mock ValidationService."""
    service = MagicMock()
    service.find_existing_patient = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_saga_service():
    """Mock SagaIntegrationService."""
    service = MagicMock()
    service.is_enabled = MagicMock(return_value=False)
    service.create_patient_via_saga = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_notification_service():
    """Mock NotificationService."""
    service = MagicMock()
    service.send_welcome_message = AsyncMock(return_value=True)
    service.publish_patient_created_event = AsyncMock(return_value=True)
    service.send_welcome_if_needed = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_completion_service():
    """Mock CompletionService."""
    service = MagicMock()
    service.complete_partial_onboarding = AsyncMock()
    return service


@pytest.fixture
def mock_creation_service():
    """Mock CreationService."""
    service = MagicMock()
    service.create_patient_direct = AsyncMock()
    return service


@pytest.fixture
def coordinator(
    mock_db,
    mock_integrity_service,
    mock_validation_service,
    mock_saga_service,
    mock_notification_service,
    mock_completion_service,
    mock_creation_service,
):
    """Create OnboardingCoordinator instance with mocked dependencies."""
    return OnboardingCoordinator(
        db=mock_db,
        integrity_service=mock_integrity_service,
        validation_service=mock_validation_service,
        saga_service=mock_saga_service,
        notification_service=mock_notification_service,
        completion_service=mock_completion_service,
        creation_service=mock_creation_service,
    )


@pytest.fixture
def sample_patient_data():
    """Sample patient data for testing."""
    return PatientCreate(
        name="João Silva",
        phone="+5511999999999",
        email="joao@example.com",
        cpf="12345678909",
        birth_date="1990-01-01",
        treatment_type="quimioterapia",
    )


@pytest.fixture
def sample_patient():
    """Sample patient object."""
    patient_id = uuid4()
    patient = Patient(
        id=patient_id,
        name="João Silva",
        phone="+5511999999999",
        email="joao@example.com",
        cpf="12345678909",
        doctor_id=uuid4(),
    )
    return patient


class TestOnboardingCoordinatorSaga:
    """Test saga orchestration flow."""

    @pytest.mark.asyncio
    async def test_create_patient_saga_success(
        self,
        coordinator,
        sample_patient_data,
        sample_patient,
        mock_saga_service,
        mock_integrity_service,
    ):
        """
        GIVEN: Saga is enabled and succeeds
        WHEN: create_patient is called
        THEN: Patient is created via saga, direct creation not called
        """
        # Setup
        doctor_id = uuid4()
        mock_saga_service.is_enabled.return_value = True
        mock_saga_service.create_patient_via_saga.return_value = sample_patient

        # Execute
        result = await coordinator.create_patient(sample_patient_data, doctor_id)

        # Assert
        assert result == sample_patient
        mock_integrity_service.validate_patient_data.assert_called_once()
        mock_saga_service.create_patient_via_saga.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_patient_saga_fallback(
        self,
        coordinator,
        sample_patient_data,
        sample_patient,
        mock_saga_service,
        mock_creation_service,
        mock_validation_service,
    ):
        """
        GIVEN: Saga is enabled but fails
        WHEN: create_patient is called
        THEN: Fallback to direct creation is triggered
        """
        # Setup
        doctor_id = uuid4()
        mock_saga_service.is_enabled.return_value = True
        mock_saga_service.create_patient_via_saga.return_value = None  # Saga failed
        mock_validation_service.find_existing_patient.return_value = None
        mock_creation_service.create_patient_direct.return_value = sample_patient

        # Execute
        result = await coordinator.create_patient(sample_patient_data, doctor_id)

        # Assert
        assert result == sample_patient
        mock_saga_service.create_patient_via_saga.assert_called_once()
        mock_creation_service.create_patient_direct.assert_called_once()


class TestOnboardingCoordinatorDirect:
    """Test direct creation flow."""

    @pytest.mark.asyncio
    async def test_create_patient_direct_new(
        self,
        coordinator,
        sample_patient_data,
        sample_patient,
        mock_saga_service,
        mock_validation_service,
        mock_creation_service,
    ):
        """
        GIVEN: Saga disabled, no existing patient
        WHEN: create_patient is called
        THEN: New patient is created directly
        """
        # Setup
        doctor_id = uuid4()
        mock_saga_service.is_enabled.return_value = False
        mock_validation_service.find_existing_patient.return_value = None
        mock_creation_service.create_patient_direct.return_value = sample_patient

        # Execute
        result = await coordinator.create_patient(sample_patient_data, doctor_id)

        # Assert
        assert result == sample_patient
        mock_validation_service.find_existing_patient.assert_called_once()
        mock_creation_service.create_patient_direct.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_patient_direct_existing(
        self,
        coordinator,
        sample_patient_data,
        sample_patient,
        mock_saga_service,
        mock_validation_service,
        mock_completion_service,
        mock_creation_service,
    ):
        """
        GIVEN: Saga disabled, existing patient found
        WHEN: create_patient is called
        THEN: Existing patient onboarding is completed, not created
        """
        # Setup
        doctor_id = uuid4()
        mock_saga_service.is_enabled.return_value = False
        mock_validation_service.find_existing_patient.return_value = sample_patient
        mock_completion_service.complete_partial_onboarding.return_value = sample_patient

        # Execute
        result = await coordinator.create_patient(sample_patient_data, doctor_id)

        # Assert
        assert result == sample_patient
        mock_validation_service.find_existing_patient.assert_called_once()
        mock_completion_service.complete_partial_onboarding.assert_called_once()
        mock_creation_service.create_patient_direct.assert_not_called()


class TestOnboardingCoordinatorValidation:
    """Test validation flow."""

    @pytest.mark.asyncio
    async def test_create_patient_validation_error(
        self,
        coordinator,
        sample_patient_data,
        mock_integrity_service,
    ):
        """
        GIVEN: Invalid patient data
        WHEN: create_patient is called
        THEN: ValidationError is raised
        """
        # Setup
        doctor_id = uuid4()
        mock_integrity_service.validate_patient_data.side_effect = ValidationError(
            "Invalid phone number"
        )

        # Execute & Assert
        with pytest.raises(ValidationError) as exc_info:
            await coordinator.create_patient(sample_patient_data, doctor_id)

        assert "Invalid phone number" in str(exc_info.value)
        mock_integrity_service.validate_patient_data.assert_called_once()


class TestOnboardingCoordinatorIntegration:
    """Integration tests for complete workflow."""

    @pytest.mark.asyncio
    async def test_complete_workflow_saga_to_direct(
        self,
        coordinator,
        sample_patient_data,
        sample_patient,
        mock_integrity_service,
        mock_saga_service,
        mock_validation_service,
        mock_creation_service,
    ):
        """
        GIVEN: Complete workflow from validation to creation
        WHEN: Saga fails and fallback triggers
        THEN: All services are called in correct order
        """
        # Setup
        doctor_id = uuid4()
        mock_saga_service.is_enabled.return_value = True
        mock_saga_service.create_patient_via_saga.return_value = None
        mock_validation_service.find_existing_patient.return_value = None
        mock_creation_service.create_patient_direct.return_value = sample_patient

        # Execute
        result = await coordinator.create_patient(sample_patient_data, doctor_id)

        # Assert - verify call order
        assert result == sample_patient
        assert mock_integrity_service.validate_patient_data.call_count == 1
        assert mock_saga_service.create_patient_via_saga.call_count == 1
        assert mock_validation_service.find_existing_patient.call_count == 1
        assert mock_creation_service.create_patient_direct.call_count == 1

    @pytest.mark.asyncio
    async def test_complete_workflow_existing_patient(
        self,
        coordinator,
        sample_patient_data,
        sample_patient,
        mock_integrity_service,
        mock_saga_service,
        mock_validation_service,
        mock_completion_service,
    ):
        """
        GIVEN: Existing patient scenario
        WHEN: Patient already exists
        THEN: Completion service is called instead of creation
        """
        # Setup
        doctor_id = uuid4()
        mock_saga_service.is_enabled.return_value = False
        mock_validation_service.find_existing_patient.return_value = sample_patient
        mock_completion_service.complete_partial_onboarding.return_value = sample_patient

        # Execute
        result = await coordinator.create_patient(sample_patient_data, doctor_id)

        # Assert
        assert result == sample_patient
        mock_completion_service.complete_partial_onboarding.assert_called_once_with(
            existing_patient=sample_patient,
            patient_data=sample_patient_data,
            current_user=None,
        )


class TestOnboardingCoordinatorCurrentUser:
    """Test current_user parameter propagation."""

    @pytest.mark.asyncio
    async def test_current_user_propagated_to_saga(
        self,
        coordinator,
        sample_patient_data,
        sample_patient,
        mock_saga_service,
    ):
        """
        GIVEN: current_user is provided
        WHEN: Saga is called
        THEN: current_user is propagated to saga service
        """
        # Setup
        doctor_id = uuid4()
        current_user = MagicMock(id=uuid4(), email="doctor@example.com")
        mock_saga_service.is_enabled.return_value = True
        mock_saga_service.create_patient_via_saga.return_value = sample_patient

        # Execute
        await coordinator.create_patient(sample_patient_data, doctor_id, current_user)

        # Assert
        call_args = mock_saga_service.create_patient_via_saga.call_args
        assert call_args[1]["current_user"] == current_user

    @pytest.mark.asyncio
    async def test_current_user_propagated_to_creation(
        self,
        coordinator,
        sample_patient_data,
        sample_patient,
        mock_saga_service,
        mock_validation_service,
        mock_creation_service,
    ):
        """
        GIVEN: current_user is provided
        WHEN: Direct creation is called
        THEN: current_user is propagated to creation service
        """
        # Setup
        doctor_id = uuid4()
        current_user = MagicMock(id=uuid4(), email="doctor@example.com")
        mock_saga_service.is_enabled.return_value = False
        mock_validation_service.find_existing_patient.return_value = None
        mock_creation_service.create_patient_direct.return_value = sample_patient

        # Execute
        await coordinator.create_patient(sample_patient_data, doctor_id, current_user)

        # Assert
        call_args = mock_creation_service.create_patient_direct.call_args
        assert call_args[1]["current_user"] == current_user


class TestOnboardingCoordinatorLogging:
    """Test logging behavior."""

    @pytest.mark.asyncio
    async def test_saga_success_logging(
        self,
        coordinator,
        sample_patient_data,
        sample_patient,
        mock_saga_service,
        caplog,
    ):
        """
        GIVEN: Saga succeeds
        WHEN: create_patient is called
        THEN: Success is logged
        """
        # Setup
        doctor_id = uuid4()
        mock_saga_service.is_enabled.return_value = True
        mock_saga_service.create_patient_via_saga.return_value = sample_patient

        # Execute
        with caplog.at_level("INFO"):
            await coordinator.create_patient(sample_patient_data, doctor_id)

        # Assert
        assert "Patient created successfully via Saga" in caplog.text

    @pytest.mark.asyncio
    async def test_saga_fallback_logging(
        self,
        coordinator,
        sample_patient_data,
        sample_patient,
        mock_saga_service,
        mock_validation_service,
        mock_creation_service,
        caplog,
    ):
        """
        GIVEN: Saga fails
        WHEN: Fallback triggers
        THEN: Fallback is logged
        """
        # Setup
        doctor_id = uuid4()
        mock_saga_service.is_enabled.return_value = True
        mock_saga_service.create_patient_via_saga.return_value = None
        mock_validation_service.find_existing_patient.return_value = None
        mock_creation_service.create_patient_direct.return_value = sample_patient

        # Execute
        with caplog.at_level("WARNING"):
            await coordinator.create_patient(sample_patient_data, doctor_id)

        # Assert
        assert "falling back to direct creation" in caplog.text
