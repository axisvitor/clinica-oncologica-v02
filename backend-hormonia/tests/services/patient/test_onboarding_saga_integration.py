"""
Unit tests for PatientOnboardingService - Saga Integration.

This test suite covers Saga pattern integration including:
- Saga execution flow
- Fallback to direct creation when Saga fails
- Duplicate patient detection in fallback
- Partial onboarding completion
- Race condition prevention

Coverage Impact: +2%
Priority: P0 - Critical Distributed Transaction Handling
"""

import pytest
from datetime import datetime
from uuid import uuid4
from unittest.mock import Mock, patch, AsyncMock

from app.services.patient.onboarding_service import PatientOnboardingService
from app.schemas.patient import PatientCreate
from app.models.patient import Patient, FlowState
from app.models.user import User


class TestPatientOnboardingSagaIntegration:
    """Test Saga pattern integration in patient onboarding."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mocked dependencies."""
        db = Mock()
        integrity_service = Mock()
        flow_service = Mock()
        message_service = Mock()
        whatsapp_service = Mock()

        integrity_service.validate_patient_data = AsyncMock()
        integrity_service.generate_patient_hash = Mock(return_value="hash123")
        flow_service.initialize_default_flow = AsyncMock()
        whatsapp_service.send_message = AsyncMock(return_value=True)

        return {
            "db": db,
            "integrity_service": integrity_service,
            "flow_service": flow_service,
            "message_service": message_service,
            "whatsapp_service": whatsapp_service,
            "saga_orchestrator": None,
        }

    @pytest.fixture
    def test_doctor_id(self):
        return uuid4()

    @pytest.fixture
    def test_user(self):
        return User(id=uuid4(), email="doctor@example.com", full_name="Dr. Test")

    @pytest.fixture
    def valid_patient_data(self):
        return PatientCreate(
            name="Test Patient",
            email="test@example.com",
            phone="+5511999887766",
            birth_date=datetime(1980, 5, 15),
            treatment_type="Quimioterapia",
            cpf="12345678900"
        )

    @pytest.mark.asyncio
    async def test_saga_fallback_on_failure(
        self,
        mock_dependencies,
        valid_patient_data,
        test_doctor_id,
        test_user
    ):
        """
        Test fallback to direct creation when Saga fails.

        CRITICAL: This tests the race condition fix where Saga failure
        triggers direct creation with duplicate detection.
        """
        # Arrange
        saga_orchestrator = Mock()
        saga_orchestrator.execute_patient_onboarding_saga = AsyncMock(return_value=None)  # Saga failed
        mock_dependencies["saga_orchestrator"] = saga_orchestrator

        expected_patient = Patient(
            id=uuid4(),
            name=valid_patient_data.name,
            email=valid_patient_data.email,
            phone=valid_patient_data.phone,
            doctor_id=test_doctor_id,
        )

        service = PatientOnboardingService(**mock_dependencies)

        with patch("app.services.patient.onboarding_service.PatientRepository") as mock_repo_class:
            mock_repo = Mock()
            mock_repo.create = Mock(return_value=expected_patient)
            mock_repo_class.return_value = mock_repo

            with patch("app.services.patient.onboarding_service.get_cache_manager"):
                with patch("app.services.patient.onboarding_service.websocket_events") as mock_ws:
                    mock_ws.publish_patient_event = AsyncMock()

                    with patch("app.services.patient.onboarding_service.settings") as mock_settings:
                        mock_settings.ENABLE_SAGA_PATTERN = True
                        mock_settings.ENABLE_WHATSAPP_ON_REGISTRATION = False

                        # Act
                        result = await service.create_patient(
                            patient_data=valid_patient_data,
                            doctor_id=test_doctor_id,
                            current_user=test_user
                        )

        # Assert
        assert result is not None
        assert result.id == expected_patient.id

        # Verify Saga was attempted first
        saga_orchestrator.execute_patient_onboarding_saga.assert_called_once()

        # Verify fallback to direct creation
        mock_repo.create.assert_called_once()

        # Verify rollback was called after Saga failure
        mock_dependencies["db"].rollback.assert_called()

    @pytest.mark.asyncio
    async def test_saga_fallback_exception_handling(
        self,
        mock_dependencies,
        valid_patient_data,
        test_doctor_id,
        test_user
    ):
        """
        Test fallback when Saga raises exception.

        Verifies graceful degradation when Saga orchestrator fails.
        """
        # Arrange
        saga_orchestrator = Mock()
        saga_orchestrator.execute_patient_onboarding_saga = AsyncMock(
            side_effect=Exception("Saga orchestrator error")
        )
        mock_dependencies["saga_orchestrator"] = saga_orchestrator

        expected_patient = Patient(
            id=uuid4(),
            name=valid_patient_data.name,
            doctor_id=test_doctor_id,
        )

        service = PatientOnboardingService(**mock_dependencies)

        with patch("app.services.patient.onboarding_service.PatientRepository") as mock_repo_class:
            mock_repo = Mock()
            mock_repo.create = Mock(return_value=expected_patient)
            mock_repo_class.return_value = mock_repo

            with patch("app.services.patient.onboarding_service.get_cache_manager"):
                with patch("app.services.patient.onboarding_service.websocket_events") as mock_ws:
                    mock_ws.publish_patient_event = AsyncMock()

                    with patch("app.services.patient.onboarding_service.settings") as mock_settings:
                        mock_settings.ENABLE_SAGA_PATTERN = True
                        mock_settings.ENABLE_WHATSAPP_ON_REGISTRATION = False

                        # Act
                        result = await service.create_patient(
                            patient_data=valid_patient_data,
                            doctor_id=test_doctor_id,
                            current_user=test_user
                        )

        # Assert - fallback succeeded
        assert result is not None
        assert result.id == expected_patient.id

        # Verify Saga was attempted
        saga_orchestrator.execute_patient_onboarding_saga.assert_called_once()

        # Verify direct creation succeeded
        mock_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_detection_in_fallback(
        self,
        mock_dependencies,
        valid_patient_data,
        test_doctor_id,
        test_user
    ):
        """
        Test duplicate patient detection during Saga fallback.

        CRITICAL: This prevents duplicate creation when Saga partially succeeds
        then fails, leaving a patient record in the database.
        """
        # Arrange
        existing_patient = Patient(
            id=uuid4(),
            name=valid_patient_data.name,
            email=valid_patient_data.email,
            phone=valid_patient_data.phone,
            cpf=valid_patient_data.cpf,
            doctor_id=test_doctor_id,
            flow_state=FlowState.NOT_STARTED,
        )

        saga_orchestrator = Mock()
        saga_orchestrator.execute_patient_onboarding_saga = AsyncMock(return_value=None)
        mock_dependencies["saga_orchestrator"] = saga_orchestrator

        service = PatientOnboardingService(**mock_dependencies)

        # Mock finding existing patient
        with patch.object(service, '_find_existing_patient', new=AsyncMock(return_value=existing_patient)):
            with patch.object(service, '_complete_partial_onboarding', new=AsyncMock(return_value=existing_patient)):
                with patch("app.services.patient.onboarding_service.settings") as mock_settings:
                    mock_settings.ENABLE_SAGA_PATTERN = True

                    # Act
                    result = await service.create_patient(
                        patient_data=valid_patient_data,
                        doctor_id=test_doctor_id,
                        current_user=test_user
                    )

        # Assert
        assert result is not None
        assert result.id == existing_patient.id

        # Verify existing patient was found
        service._find_existing_patient.assert_called_once()

        # Verify partial onboarding was completed instead of creating new patient
        service._complete_partial_onboarding.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_partial_onboarding_updates_data(
        self,
        mock_dependencies,
        test_doctor_id,
        test_user
    ):
        """
        Test that partial onboarding completion updates missing fields.

        Verifies that existing patient data is updated with new information.
        """
        # Arrange
        existing_patient = Patient(
            id=uuid4(),
            name="Partial Name",
            email=None,  # Missing
            phone="+5511999887766",
            cpf="12345678900",
            doctor_id=test_doctor_id,
            birth_date=None,  # Missing
            treatment_type=None,  # Missing
        )

        updated_data = PatientCreate(
            name="Complete Name",
            email="complete@example.com",
            phone="+5511999887766",
            birth_date=datetime(1980, 5, 15),
            treatment_type="Quimioterapia",
            cpf="12345678900",
            metadata={"source": "update"}
        )

        service = PatientOnboardingService(**mock_dependencies)

        with patch("app.services.patient.onboarding_service.get_cache_manager"):
            with patch("app.services.patient.onboarding_service.websocket_events") as mock_ws:
                mock_ws.publish_patient_event = AsyncMock()

                with patch("app.services.patient.onboarding_service.settings") as mock_settings:
                    mock_settings.ENABLE_WHATSAPP_ON_REGISTRATION = False

                    # Act
                    result = await service._complete_partial_onboarding(
                        existing_patient=existing_patient,
                        patient_data=updated_data,
                        current_user=test_user
                    )

        # Assert - missing fields were updated
        assert result.email == "complete@example.com"
        assert result.birth_date == datetime(1980, 5, 15)
        assert result.treatment_type == "Quimioterapia"

        # Verify commit was called
        mock_dependencies["db"].commit.assert_called()

    @pytest.mark.asyncio
    async def test_complete_partial_onboarding_preserves_existing_data(
        self,
        mock_dependencies,
        test_doctor_id,
        test_user
    ):
        """
        Test that existing patient data is preserved during partial onboarding.

        Verifies that fields with existing values are not overwritten.
        """
        # Arrange
        existing_patient = Patient(
            id=uuid4(),
            name="Original Name",
            email="original@example.com",
            phone="+5511999887766",
            cpf="12345678900",
            doctor_id=test_doctor_id,
            birth_date=datetime(1980, 1, 1),
            treatment_type="Original Treatment",
        )

        # Attempt to update with different data
        new_data = PatientCreate(
            name="New Name",
            email="new@example.com",
            phone="+5511999887766",
            birth_date=datetime(1990, 1, 1),
            treatment_type="New Treatment",
            cpf="12345678900"
        )

        service = PatientOnboardingService(**mock_dependencies)

        with patch("app.services.patient.onboarding_service.get_cache_manager"):
            with patch("app.services.patient.onboarding_service.websocket_events") as mock_ws:
                mock_ws.publish_patient_event = AsyncMock()

                with patch("app.services.patient.onboarding_service.settings") as mock_settings:
                    mock_settings.ENABLE_WHATSAPP_ON_REGISTRATION = False

                    # Act
                    result = await service._complete_partial_onboarding(
                        existing_patient=existing_patient,
                        patient_data=new_data,
                        current_user=test_user
                    )

        # Assert - original data was preserved
        assert result.name == "Original Name"
        assert result.email == "original@example.com"
        assert result.birth_date == datetime(1980, 1, 1)
        assert result.treatment_type == "Original Treatment"

    @pytest.mark.asyncio
    async def test_saga_disabled_uses_direct_creation(
        self,
        mock_dependencies,
        valid_patient_data,
        test_doctor_id,
        test_user
    ):
        """
        Test that direct creation is used when Saga is disabled.

        Verifies correct behavior when ENABLE_SAGA_PATTERN is False.
        """
        # Arrange
        saga_orchestrator = Mock()
        saga_orchestrator.execute_patient_onboarding_saga = AsyncMock()
        mock_dependencies["saga_orchestrator"] = saga_orchestrator

        expected_patient = Patient(
            id=uuid4(),
            name=valid_patient_data.name,
            doctor_id=test_doctor_id,
        )

        service = PatientOnboardingService(**mock_dependencies)

        with patch("app.services.patient.onboarding_service.PatientRepository") as mock_repo_class:
            mock_repo = Mock()
            mock_repo.create = Mock(return_value=expected_patient)
            mock_repo_class.return_value = mock_repo

            with patch("app.services.patient.onboarding_service.get_cache_manager"):
                with patch("app.services.patient.onboarding_service.websocket_events") as mock_ws:
                    mock_ws.publish_patient_event = AsyncMock()

                    with patch("app.services.patient.onboarding_service.settings") as mock_settings:
                        mock_settings.ENABLE_SAGA_PATTERN = False  # Disabled
                        mock_settings.ENABLE_WHATSAPP_ON_REGISTRATION = False

                        # Act
                        result = await service.create_patient(
                            patient_data=valid_patient_data,
                            doctor_id=test_doctor_id,
                            current_user=test_user
                        )

        # Assert
        assert result is not None

        # Verify Saga was NOT called
        saga_orchestrator.execute_patient_onboarding_saga.assert_not_called()

        # Verify direct creation was used
        mock_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_saga_orchestrator_none_uses_direct_creation(
        self,
        mock_dependencies,
        valid_patient_data,
        test_doctor_id,
        test_user
    ):
        """
        Test direct creation when saga_orchestrator is None.

        Verifies correct behavior when Saga orchestrator is not injected.
        """
        # Arrange - saga_orchestrator is None
        assert mock_dependencies["saga_orchestrator"] is None

        expected_patient = Patient(
            id=uuid4(),
            name=valid_patient_data.name,
            doctor_id=test_doctor_id,
        )

        service = PatientOnboardingService(**mock_dependencies)

        with patch("app.services.patient.onboarding_service.PatientRepository") as mock_repo_class:
            mock_repo = Mock()
            mock_repo.create = Mock(return_value=expected_patient)
            mock_repo_class.return_value = mock_repo

            with patch("app.services.patient.onboarding_service.get_cache_manager"):
                with patch("app.services.patient.onboarding_service.websocket_events") as mock_ws:
                    mock_ws.publish_patient_event = AsyncMock()

                    with patch("app.services.patient.onboarding_service.settings") as mock_settings:
                        mock_settings.ENABLE_WHATSAPP_ON_REGISTRATION = False

                        # Act
                        result = await service.create_patient(
                            patient_data=valid_patient_data,
                            doctor_id=test_doctor_id,
                            current_user=test_user
                        )

        # Assert - direct creation succeeded
        assert result is not None
        assert result.id == expected_patient.id
        mock_repo.create.assert_called_once()
