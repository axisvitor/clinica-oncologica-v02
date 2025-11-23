"""
Unit tests for SagaIntegrationService.

ISSUE-005 Phase 3: Comprehensive test coverage for saga integration.

Test Coverage:
- Saga enabled/disabled detection
- Saga success scenario
- Saga failure scenario (None return)
- Saga exception scenario
- Compensation execution
- Fallback triggering
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.domain.patient.onboarding.saga_integration_service import SagaIntegrationService
from app.schemas.patient import PatientCreate
from app.models.patient import Patient


class TestSagaIntegrationService:
    """Unit tests for SagaIntegrationService."""

    @pytest.fixture
    def patient_data(self):
        """Create sample patient data."""
        # Use valid CPF for testing (11144477735 is a valid test CPF)
        return PatientCreate(
            name="João Silva",
            phone="+5511999999999",
            email="joao@example.com",
            cpf="11144477735",  # Valid test CPF
            birth_date="1990-01-01",
            treatment_type="oncology",
        )

    @pytest.fixture
    def doctor_id(self):
        """Create sample doctor ID."""
        return uuid4()

    @pytest.fixture
    def mock_saga_orchestrator(self):
        """Create mock saga orchestrator."""
        mock = MagicMock()
        mock.execute_patient_onboarding_saga = AsyncMock()
        return mock

    @pytest.fixture
    def saga_service(self, mock_saga_orchestrator):
        """Create SagaIntegrationService instance."""
        return SagaIntegrationService(saga_orchestrator=mock_saga_orchestrator)

    @pytest.fixture
    def saga_service_disabled(self):
        """Create SagaIntegrationService with saga disabled."""
        return SagaIntegrationService(saga_orchestrator=None)

    # -------------------------------------------------------------------------
    # Test: Saga Availability Detection
    # -------------------------------------------------------------------------

    def test_is_enabled_with_orchestrator(self, saga_service):
        """
        GIVEN: SagaIntegrationService with saga orchestrator
        WHEN: is_enabled() is called
        THEN: Returns True
        """
        assert saga_service.is_enabled() is True

    def test_is_enabled_without_orchestrator(self, saga_service_disabled):
        """
        GIVEN: SagaIntegrationService without saga orchestrator
        WHEN: is_enabled() is called
        THEN: Returns False
        """
        assert saga_service_disabled.is_enabled() is False

    @patch("app.domain.patient.onboarding.saga_integration_service.settings")
    def test_is_enabled_with_setting_disabled(self, mock_settings, mock_saga_orchestrator):
        """
        GIVEN: SagaIntegrationService with ENABLE_SAGA_PATTERN=False
        WHEN: is_enabled() is called
        THEN: Returns False
        """
        mock_settings.ENABLE_SAGA_PATTERN = False
        service = SagaIntegrationService(saga_orchestrator=mock_saga_orchestrator)
        assert service.is_enabled() is False

    # -------------------------------------------------------------------------
    # Test: Saga Success Scenario
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_patient_via_saga_success(
        self, saga_service, patient_data, doctor_id, mock_saga_orchestrator
    ):
        """
        GIVEN: Valid patient data and saga enabled
        WHEN: Saga succeeds and returns patient
        THEN: Patient is returned successfully
        """
        # Setup: Mock saga to return patient
        mock_patient = MagicMock(spec=Patient)
        mock_patient.id = uuid4()
        mock_patient.name = "João Silva"
        mock_saga_orchestrator.execute_patient_onboarding_saga.return_value = mock_patient

        # Execute
        result = await saga_service.create_patient_via_saga(
            patient_data=patient_data,
            doctor_id=doctor_id,
        )

        # Assert
        assert result == mock_patient
        mock_saga_orchestrator.execute_patient_onboarding_saga.assert_called_once_with(
            patient_data=patient_data,
            doctor_id=doctor_id,
            current_user=None,
        )

    # -------------------------------------------------------------------------
    # Test: Saga Failure Scenario (None Return)
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_patient_via_saga_returns_none(
        self, saga_service, patient_data, doctor_id, mock_saga_orchestrator
    ):
        """
        GIVEN: Valid patient data and saga enabled
        WHEN: Saga fails and returns None
        THEN: None is returned (triggers fallback)
        """
        # Setup: Mock saga to return None (failure)
        mock_saga_orchestrator.execute_patient_onboarding_saga.return_value = None

        # Execute
        result = await saga_service.create_patient_via_saga(
            patient_data=patient_data,
            doctor_id=doctor_id,
        )

        # Assert
        assert result is None
        mock_saga_orchestrator.execute_patient_onboarding_saga.assert_called_once()

    # -------------------------------------------------------------------------
    # Test: Saga Exception Scenario
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_patient_via_saga_exception(
        self, saga_service, patient_data, doctor_id, mock_saga_orchestrator
    ):
        """
        GIVEN: Valid patient data and saga enabled
        WHEN: Saga raises exception
        THEN: None is returned (triggers fallback) and compensations executed
        """
        # Setup: Mock saga to raise exception
        mock_saga_orchestrator.execute_patient_onboarding_saga.side_effect = Exception(
            "Database timeout"
        )

        # Execute
        result = await saga_service.create_patient_via_saga(
            patient_data=patient_data,
            doctor_id=doctor_id,
        )

        # Assert
        assert result is None
        mock_saga_orchestrator.execute_patient_onboarding_saga.assert_called_once()

    # -------------------------------------------------------------------------
    # Test: Saga Disabled Scenario
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_patient_via_saga_disabled(
        self, saga_service_disabled, patient_data, doctor_id
    ):
        """
        GIVEN: Saga is disabled (no orchestrator)
        WHEN: create_patient_via_saga is called
        THEN: None is returned immediately without saga execution
        """
        # Execute
        result = await saga_service_disabled.create_patient_via_saga(
            patient_data=patient_data,
            doctor_id=doctor_id,
        )

        # Assert
        assert result is None

    # -------------------------------------------------------------------------
    # Test: Compensation Execution
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_execute_compensations(self, saga_service, patient_data, doctor_id):
        """
        GIVEN: Saga failure scenario
        WHEN: _execute_compensations is called
        THEN: Compensations are executed without errors
        """
        # Execute
        await saga_service._execute_compensations(
            patient_data=patient_data,
            doctor_id=doctor_id,
        )

        # Assert: No exceptions raised
        # Compensations are logged but handled by orchestrator

    # -------------------------------------------------------------------------
    # Test: Current User Parameter
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_patient_via_saga_with_current_user(
        self, saga_service, patient_data, doctor_id, mock_saga_orchestrator
    ):
        """
        GIVEN: Valid patient data and current_user provided
        WHEN: Saga succeeds
        THEN: current_user is passed to orchestrator
        """
        # Setup
        mock_patient = MagicMock(spec=Patient)
        mock_patient.id = uuid4()
        mock_saga_orchestrator.execute_patient_onboarding_saga.return_value = mock_patient
        mock_user = MagicMock()
        mock_user.id = uuid4()

        # Execute
        result = await saga_service.create_patient_via_saga(
            patient_data=patient_data,
            doctor_id=doctor_id,
            current_user=mock_user,
        )

        # Assert
        assert result == mock_patient
        mock_saga_orchestrator.execute_patient_onboarding_saga.assert_called_once_with(
            patient_data=patient_data,
            doctor_id=doctor_id,
            current_user=mock_user,
        )

    # -------------------------------------------------------------------------
    # Test: Integration with OnboardingService
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_saga_integration_with_fallback_flow(
        self, saga_service, patient_data, doctor_id, mock_saga_orchestrator
    ):
        """
        GIVEN: Saga is enabled but fails
        WHEN: create_patient_via_saga returns None
        THEN: Calling service should fallback to direct creation

        This tests the contract between SagaIntegrationService and OnboardingService.
        """
        # Setup: Saga fails
        mock_saga_orchestrator.execute_patient_onboarding_saga.return_value = None

        # Execute
        result = await saga_service.create_patient_via_saga(
            patient_data=patient_data,
            doctor_id=doctor_id,
        )

        # Assert: None returned (triggers fallback in OnboardingService)
        assert result is None

    # -------------------------------------------------------------------------
    # Test: Saga Success with Logging
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_saga_success_logging(
        self, saga_service, patient_data, doctor_id, mock_saga_orchestrator, caplog
    ):
        """
        GIVEN: Saga succeeds
        WHEN: create_patient_via_saga is called
        THEN: Success is logged with patient details
        """
        import logging

        # Setup
        mock_patient = MagicMock(spec=Patient)
        mock_patient.id = uuid4()
        mock_patient.name = "João Silva"
        mock_saga_orchestrator.execute_patient_onboarding_saga.return_value = mock_patient

        # Execute
        with caplog.at_level(logging.INFO):
            await saga_service.create_patient_via_saga(
                patient_data=patient_data,
                doctor_id=doctor_id,
            )

        # Assert
        assert "Saga Pattern succeeded" in caplog.text
        assert "Patient" in caplog.text

    # -------------------------------------------------------------------------
    # Test: Saga Failure with Logging
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_saga_failure_logging(
        self, saga_service, patient_data, doctor_id, mock_saga_orchestrator, caplog
    ):
        """
        GIVEN: Saga fails
        WHEN: create_patient_via_saga is called
        THEN: Failure is logged with fallback message
        """
        import logging

        # Setup: Saga returns None
        mock_saga_orchestrator.execute_patient_onboarding_saga.return_value = None

        # Execute
        with caplog.at_level(logging.WARNING):
            await saga_service.create_patient_via_saga(
                patient_data=patient_data,
                doctor_id=doctor_id,
            )

        # Assert
        assert "Saga Pattern returned None" in caplog.text
        assert "fallback to direct creation" in caplog.text

    # -------------------------------------------------------------------------
    # Test: Saga Exception with Logging
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_saga_exception_logging(
        self, saga_service, patient_data, doctor_id, mock_saga_orchestrator, caplog
    ):
        """
        GIVEN: Saga raises exception
        WHEN: create_patient_via_saga is called
        THEN: Exception is logged with error details
        """
        import logging

        # Setup: Saga raises exception
        mock_saga_orchestrator.execute_patient_onboarding_saga.side_effect = Exception(
            "Network timeout"
        )

        # Execute
        with caplog.at_level(logging.ERROR):
            await saga_service.create_patient_via_saga(
                patient_data=patient_data,
                doctor_id=doctor_id,
            )

        # Assert
        assert "Saga Pattern execution failed" in caplog.text
        assert "Network timeout" in caplog.text
