"""
Test suite for OnboardingCoordinator.

Tests the high-level orchestration of patient onboarding workflow.

Phase 2 Simplification:
- Removed SagaIntegrationService wrapper tests
- Now tests direct SagaOrchestrator usage
- Removed fallback tests (fallback behavior removed in Phase 1)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.domain.patient.onboarding.coordinator import OnboardingCoordinator
from app.models.patient import Patient
from app.schemas.patient import PatientCreate
from app.exceptions import ValidationError
from app.utils.db_retry import reset_circuit_breaker


@pytest.fixture(autouse=True)
def _reset_db_circuit_breaker_state():
    """Ensure global DB circuit breaker state does not leak across tests."""
    reset_circuit_breaker()
    yield
    reset_circuit_breaker()


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
    service.validate_patient_data = MagicMock(return_value=None)
    service.generate_patient_hash = MagicMock(return_value="test_hash_123")
    return service


@pytest.fixture
def mock_validation_service():
    """Mock ValidationService."""
    service = MagicMock()
    service.find_existing_patient = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_saga_orchestrator():
    """Mock SagaOrchestrator (direct usage - Phase 2 simplification)."""
    orchestrator = MagicMock()
    orchestrator.execute_patient_onboarding_saga = AsyncMock(return_value=None)
    return orchestrator


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
    mock_saga_orchestrator,
    mock_notification_service,
    mock_completion_service,
    mock_creation_service,
):
    """Create OnboardingCoordinator instance with mocked dependencies."""
    return OnboardingCoordinator(
        db=mock_db,
        integrity_service=mock_integrity_service,
        validation_service=mock_validation_service,
        saga_orchestrator=mock_saga_orchestrator,
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
        doctor_id=uuid4(),
    )
    return patient


class TestOnboardingCoordinatorSaga:
    """Test saga orchestration flow (Phase 2: direct SagaOrchestrator usage)."""

    @pytest.mark.asyncio
    async def test_create_patient_saga_success(
        self,
        coordinator,
        sample_patient_data,
        sample_patient,
        mock_saga_orchestrator,
        mock_integrity_service,
    ):
        """
        GIVEN: Saga is enabled and succeeds
        WHEN: create_patient is called
        THEN: Patient is created via saga orchestrator directly
        """
        # Setup
        doctor_id = uuid4()
        mock_saga_orchestrator.execute_patient_onboarding_saga.return_value = sample_patient

        # Execute
        with patch.object(coordinator, '_is_saga_enabled', return_value=True):
            result = await coordinator.create_patient(sample_patient_data, doctor_id)

        # Assert
        assert result == sample_patient
        mock_integrity_service.validate_patient_data.assert_called_once()
        mock_saga_orchestrator.execute_patient_onboarding_saga.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_patient_saga_returns_none_raises_error(
        self,
        coordinator,
        sample_patient_data,
        mock_saga_orchestrator,
    ):
        """
        GIVEN: Saga is enabled but returns None
        WHEN: create_patient is called
        THEN: ValidationError is raised (no fallback - Phase 1 change)
        """
        # Setup
        doctor_id = uuid4()
        mock_saga_orchestrator.execute_patient_onboarding_saga.return_value = None

        # Execute & Assert
        with patch.object(coordinator, '_is_saga_enabled', return_value=True):
            with pytest.raises(ValidationError) as exc_info:
                await coordinator.create_patient(sample_patient_data, doctor_id)

        assert "não retornou paciente" in str(exc_info.value)
        mock_saga_orchestrator.execute_patient_onboarding_saga.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_patient_saga_exception_raises_error(
        self,
        coordinator,
        sample_patient_data,
        mock_saga_orchestrator,
    ):
        """
        GIVEN: Saga is enabled but raises exception
        WHEN: create_patient is called
        THEN: ValidationError is raised wrapping the original exception
        """
        # Setup
        doctor_id = uuid4()
        mock_saga_orchestrator.execute_patient_onboarding_saga.side_effect = Exception("Saga failed")

        # Execute & Assert
        with patch.object(coordinator, '_is_saga_enabled', return_value=True):
            with pytest.raises(ValidationError) as exc_info:
                await coordinator.create_patient(sample_patient_data, doctor_id)

        assert "Saga Pattern" in str(exc_info.value)
        mock_saga_orchestrator.execute_patient_onboarding_saga.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_patient_saga_disabled_raises_error(
        self,
        coordinator,
        sample_patient_data,
    ):
        """
        GIVEN: Saga is disabled
        WHEN: create_patient is called
        THEN: ValidationError is raised (saga is mandatory)
        """
        # Setup
        doctor_id = uuid4()

        # Execute & Assert
        with patch.object(coordinator, '_is_saga_enabled', return_value=False):
            with pytest.raises(ValidationError) as exc_info:
                await coordinator.create_patient(sample_patient_data, doctor_id)

        assert "desabilitado" in str(exc_info.value)


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


class TestOnboardingCoordinatorCurrentUser:
    """Test current_user parameter propagation."""

    @pytest.mark.asyncio
    async def test_current_user_propagated_to_saga(
        self,
        coordinator,
        sample_patient_data,
        sample_patient,
        mock_saga_orchestrator,
    ):
        """
        GIVEN: current_user is provided
        WHEN: Saga is called
        THEN: current_user is propagated to saga orchestrator
        """
        # Setup
        doctor_id = uuid4()
        current_user = MagicMock(id=uuid4(), email="doctor@example.com")
        mock_saga_orchestrator.execute_patient_onboarding_saga.return_value = sample_patient

        # Execute
        with patch.object(coordinator, '_is_saga_enabled', return_value=True):
            await coordinator.create_patient(sample_patient_data, doctor_id, current_user)

        # Assert
        call_args = mock_saga_orchestrator.execute_patient_onboarding_saga.call_args
        assert call_args[1]["current_user"] == current_user


class TestOnboardingCoordinatorIdempotency:
    """Test idempotency key propagation (QW-004)."""

    @pytest.mark.asyncio
    async def test_idempotency_key_propagated_to_saga(
        self,
        coordinator,
        sample_patient_data,
        sample_patient,
        mock_saga_orchestrator,
    ):
        """
        GIVEN: idempotency_key is provided
        WHEN: Saga is called
        THEN: idempotency_key is propagated to saga orchestrator
        """
        # Setup
        doctor_id = uuid4()
        idempotency_key = "unique-key-12345"
        mock_saga_orchestrator.execute_patient_onboarding_saga.return_value = sample_patient

        # Execute
        with patch.object(coordinator, '_is_saga_enabled', return_value=True):
            await coordinator.create_patient(
                sample_patient_data,
                doctor_id,
                idempotency_key=idempotency_key
            )

        # Assert
        call_args = mock_saga_orchestrator.execute_patient_onboarding_saga.call_args
        assert call_args[1]["idempotency_key"] == idempotency_key


class TestOnboardingCoordinatorLogging:
    """Test logging behavior."""

    @pytest.mark.asyncio
    async def test_saga_success_logging(
        self,
        coordinator,
        sample_patient_data,
        sample_patient,
        mock_saga_orchestrator,
        caplog,
    ):
        """
        GIVEN: Saga succeeds
        WHEN: create_patient is called
        THEN: Success is logged
        """
        # Setup
        doctor_id = uuid4()
        mock_saga_orchestrator.execute_patient_onboarding_saga.return_value = sample_patient

        # Execute
        with patch.object(coordinator, '_is_saga_enabled', return_value=True):
            with caplog.at_level("INFO"):
                await coordinator.create_patient(sample_patient_data, doctor_id)

        # Assert
        assert "Patient created successfully via Saga" in caplog.text

    @pytest.mark.asyncio
    async def test_saga_failure_logging(
        self,
        coordinator,
        sample_patient_data,
        mock_saga_orchestrator,
        caplog,
    ):
        """
        GIVEN: Saga fails
        WHEN: create_patient is called
        THEN: Failure is logged
        """
        # Setup
        doctor_id = uuid4()
        mock_saga_orchestrator.execute_patient_onboarding_saga.side_effect = Exception("Test error")

        # Execute & Assert
        with patch.object(coordinator, '_is_saga_enabled', return_value=True):
            with caplog.at_level("ERROR"):
                with pytest.raises(ValidationError):
                    await coordinator.create_patient(sample_patient_data, doctor_id)

        # Assert
        assert "Saga Pattern execution failed" in caplog.text


class TestOnboardingCoordinatorIsSagaEnabled:
    """Test _is_saga_enabled method."""

    def test_is_saga_enabled_true(
        self,
        mock_db,
        mock_integrity_service,
        mock_validation_service,
        mock_saga_orchestrator,
        mock_notification_service,
        mock_completion_service,
        mock_creation_service,
    ):
        """
        GIVEN: saga_orchestrator is not None and setting is True
        WHEN: _is_saga_enabled is called
        THEN: Returns True
        """
        coordinator = OnboardingCoordinator(
            db=mock_db,
            integrity_service=mock_integrity_service,
            validation_service=mock_validation_service,
            saga_orchestrator=mock_saga_orchestrator,
            notification_service=mock_notification_service,
            completion_service=mock_completion_service,
            creation_service=mock_creation_service,
        )

        with patch('app.domain.patient.onboarding.coordinator.settings') as mock_settings:
            mock_settings.ENABLE_SAGA_PATTERN = True
            assert coordinator._is_saga_enabled() is True

    def test_is_saga_enabled_false_no_orchestrator(
        self,
        mock_db,
        mock_integrity_service,
        mock_validation_service,
        mock_notification_service,
        mock_completion_service,
        mock_creation_service,
    ):
        """
        GIVEN: saga_orchestrator is None
        WHEN: _is_saga_enabled is called
        THEN: Returns False
        """
        coordinator = OnboardingCoordinator(
            db=mock_db,
            integrity_service=mock_integrity_service,
            validation_service=mock_validation_service,
            saga_orchestrator=None,  # No orchestrator
            notification_service=mock_notification_service,
            completion_service=mock_completion_service,
            creation_service=mock_creation_service,
        )

        assert coordinator._is_saga_enabled() is False

    def test_is_saga_enabled_false_setting_disabled(
        self,
        mock_db,
        mock_integrity_service,
        mock_validation_service,
        mock_saga_orchestrator,
        mock_notification_service,
        mock_completion_service,
        mock_creation_service,
    ):
        """
        GIVEN: saga_orchestrator exists but setting is False
        WHEN: _is_saga_enabled is called
        THEN: Returns False
        """
        coordinator = OnboardingCoordinator(
            db=mock_db,
            integrity_service=mock_integrity_service,
            validation_service=mock_validation_service,
            saga_orchestrator=mock_saga_orchestrator,
            notification_service=mock_notification_service,
            completion_service=mock_completion_service,
            creation_service=mock_creation_service,
        )

        with patch('app.domain.patient.onboarding.coordinator.settings') as mock_settings:
            mock_settings.ENABLE_SAGA_PATTERN = False
            assert coordinator._is_saga_enabled() is False
