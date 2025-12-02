"""
Unit tests for PatientOnboardingService - Validation Error Scenarios.

This test suite covers patient onboarding validation failures including:
- Data validation errors
- Database integrity constraint violations
- Duplicate patient detection
- Invalid field formats
- Business rule violations

Coverage Impact: +2%
Priority: P0 - Critical Error Handling
"""

import pytest
from datetime import datetime
from uuid import uuid4
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.exc import IntegrityError

from app.domain.patient.onboarding.coordinator import PatientOnboardingService
from app.schemas.patient import PatientCreate
from app.models.patient import Patient
from app.exceptions import ValidationError


class TestPatientOnboardingValidationErrors:
    """Test patient onboarding validation error scenarios."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create all mocked dependencies for onboarding service."""
        db = Mock()
        integrity_service = Mock()
        flow_service = Mock()
        message_service = Mock()
        whatsapp_service = Mock()

        # Setup async methods
        integrity_service.validate_patient_data = AsyncMock()
        integrity_service.generate_patient_hash = Mock(return_value="test_hash")
        flow_service.initialize_default_flow = AsyncMock()

        return {
            "db": db,
            "integrity_service": integrity_service,
            "flow_service": flow_service,
            "message_service": message_service,
            "whatsapp_service": whatsapp_service,
            "saga_orchestrator": None,
        }

    @pytest.fixture
    def onboarding_service(self, mock_dependencies):
        """Create PatientOnboardingService instance."""
        return PatientOnboardingService(**mock_dependencies)

    @pytest.fixture
    def test_doctor_id(self):
        """Test doctor UUID."""
        return uuid4()

    @pytest.mark.asyncio
    async def test_validation_error_propagated(
        self,
        onboarding_service,
        test_doctor_id,
        mock_dependencies
    ):
        """
        Test that validation errors from IntegrityService are propagated.

        Verifies that validation errors bubble up correctly without being caught.
        """
        # Arrange
        patient_data = PatientCreate(
            name="Invalid Patient",
            email="invalid-email",  # Invalid email format
            phone="+5511999887766",
            birth_date=datetime(1980, 5, 15),
            treatment_type="Test"
        )

        # Mock validation to raise error
        mock_dependencies["integrity_service"].validate_patient_data.side_effect = ValidationError(
            "Invalid email format"
        )

        # Act & Assert
        with pytest.raises(ValidationError, match="Invalid email format"):
            await onboarding_service.create_patient(
                patient_data=patient_data,
                doctor_id=test_doctor_id
            )

        # Verify validation was attempted
        mock_dependencies["integrity_service"].validate_patient_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_patient_cpf_error(
        self,
        onboarding_service,
        test_doctor_id,
        mock_dependencies
    ):
        """
        Test handling of duplicate CPF constraint violation.

        Verifies proper error handling when trying to create a patient
        with a CPF that already exists for the same doctor.
        """
        # Arrange
        patient_data = PatientCreate(
            name="João Silva",
            email="joao@example.com",
            phone="+5511999887766",
            birth_date=datetime(1980, 5, 15),
            treatment_type="Quimioterapia",
            cpf="12345678900"  # Duplicate CPF
        )

        with patch("app.services.patient.onboarding_service.PatientRepository") as mock_repo_class:
            mock_repo = Mock()
            # Simulate unique constraint violation on CPF
            mock_repo.create.side_effect = IntegrityError(
                "duplicate key value violates unique constraint \"uq_patient_cpf_doctor\"",
                None,
                None
            )
            mock_repo_class.return_value = mock_repo

            with patch("app.services.patient.onboarding_service.get_cache_manager"):
                with patch("app.services.patient.onboarding_service.websocket_events") as mock_ws:
                    mock_ws.publish_patient_event = AsyncMock()

                    # Act & Assert
                    with pytest.raises(ValidationError, match="data integrity constraints"):
                        await onboarding_service.create_patient(
                            patient_data=patient_data,
                            doctor_id=test_doctor_id
                        )

        # Verify rollback was called
        mock_dependencies["db"].rollback.assert_called()

    @pytest.mark.asyncio
    async def test_duplicate_patient_email_error(
        self,
        onboarding_service,
        test_doctor_id,
        mock_dependencies
    ):
        """
        Test handling of duplicate email constraint violation.

        Verifies proper error handling when email already exists.
        """
        # Arrange
        patient_data = PatientCreate(
            name="Maria Santos",
            email="duplicate@example.com",
            phone="+5511988776655",
            birth_date=datetime(1975, 3, 20),
            treatment_type="Radioterapia"
        )

        with patch("app.services.patient.onboarding_service.PatientRepository") as mock_repo_class:
            mock_repo = Mock()
            mock_repo.create.side_effect = IntegrityError(
                "duplicate key value violates unique constraint \"uq_patient_email_doctor\"",
                None,
                None
            )
            mock_repo_class.return_value = mock_repo

            with patch("app.services.patient.onboarding_service.get_cache_manager"):
                with patch("app.services.patient.onboarding_service.websocket_events") as mock_ws:
                    mock_ws.publish_patient_event = AsyncMock()

                    # Act & Assert
                    with pytest.raises(ValidationError):
                        await onboarding_service.create_patient(
                            patient_data=patient_data,
                            doctor_id=test_doctor_id
                        )

    @pytest.mark.asyncio
    async def test_duplicate_patient_phone_error(
        self,
        onboarding_service,
        test_doctor_id,
        mock_dependencies
    ):
        """
        Test handling of duplicate phone constraint violation.

        Verifies proper error handling when phone number already exists.
        """
        # Arrange
        patient_data = PatientCreate(
            name="Pedro Oliveira",
            email="pedro@example.com",
            phone="+5511999999999",  # Duplicate phone
            birth_date=datetime(1985, 7, 10),
            treatment_type="Imunoterapia"
        )

        with patch("app.services.patient.onboarding_service.PatientRepository") as mock_repo_class:
            mock_repo = Mock()
            mock_repo.create.side_effect = IntegrityError(
                "duplicate key value violates unique constraint \"uq_patient_phone_doctor\"",
                None,
                None
            )
            mock_repo_class.return_value = mock_repo

            with patch("app.services.patient.onboarding_service.get_cache_manager"):
                with patch("app.services.patient.onboarding_service.websocket_events") as mock_ws:
                    mock_ws.publish_patient_event = AsyncMock()

                    # Act & Assert
                    with pytest.raises(ValidationError):
                        await onboarding_service.create_patient(
                            patient_data=patient_data,
                            doctor_id=test_doctor_id
                        )

    @pytest.mark.asyncio
    async def test_invalid_doctor_id_foreign_key_error(
        self,
        onboarding_service,
        mock_dependencies
    ):
        """
        Test handling of invalid doctor_id foreign key constraint.

        Verifies proper error handling when doctor_id doesn't exist.
        """
        # Arrange
        invalid_doctor_id = uuid4()
        patient_data = PatientCreate(
            name="Test Patient",
            email="test@example.com",
            phone="+5511999887766",
            birth_date=datetime(1990, 1, 1),
            treatment_type="Test"
        )

        with patch("app.services.patient.onboarding_service.PatientRepository") as mock_repo_class:
            mock_repo = Mock()
            mock_repo.create.side_effect = IntegrityError(
                "insert or update on table \"patients\" violates foreign key constraint",
                None,
                None
            )
            mock_repo_class.return_value = mock_repo

            with patch("app.services.patient.onboarding_service.get_cache_manager"):
                with patch("app.services.patient.onboarding_service.websocket_events") as mock_ws:
                    mock_ws.publish_patient_event = AsyncMock()

                    # Act & Assert
                    with pytest.raises(ValidationError):
                        await onboarding_service.create_patient(
                            patient_data=patient_data,
                            doctor_id=invalid_doctor_id
                        )

    @pytest.mark.asyncio
    async def test_database_connection_error_handling(
        self,
        onboarding_service,
        test_doctor_id,
        mock_dependencies
    ):
        """
        Test handling of database connection errors.

        Verifies that database errors are properly caught and handled.
        """
        # Arrange
        patient_data = PatientCreate(
            name="Test Patient",
            email="test@example.com",
            phone="+5511999887766",
            birth_date=datetime(1990, 1, 1),
            treatment_type="Test"
        )

        with patch("app.services.patient.onboarding_service.PatientRepository") as mock_repo_class:
            mock_repo = Mock()
            mock_repo.create.side_effect = Exception("Database connection lost")
            mock_repo_class.return_value = mock_repo

            with patch("app.services.patient.onboarding_service.get_cache_manager"):
                with patch("app.services.patient.onboarding_service.websocket_events") as mock_ws:
                    mock_ws.publish_patient_event = AsyncMock()

                    # Act & Assert
                    with pytest.raises(Exception, match="Database connection lost"):
                        await onboarding_service.create_patient(
                            patient_data=patient_data,
                            doctor_id=test_doctor_id
                        )

        # Verify rollback was attempted
        mock_dependencies["db"].rollback.assert_called()

    @pytest.mark.asyncio
    async def test_validation_called_before_creation(
        self,
        onboarding_service,
        test_doctor_id,
        mock_dependencies
    ):
        """
        Test that validation is always called before patient creation.

        Ensures fail-fast behavior by validating before database operations.
        """
        # Arrange
        patient_data = PatientCreate(
            name="Test Patient",
            email="test@example.com",
            phone="+5511999887766",
            birth_date=datetime(1990, 1, 1),
            treatment_type="Test"
        )

        # Make validation fail
        mock_dependencies["integrity_service"].validate_patient_data.side_effect = ValidationError(
            "Invalid data"
        )

        with patch("app.services.patient.onboarding_service.PatientRepository") as mock_repo_class:
            mock_repo = Mock()
            mock_repo_class.return_value = mock_repo

            # Act & Assert
            with pytest.raises(ValidationError):
                await onboarding_service.create_patient(
                    patient_data=patient_data,
                    doctor_id=test_doctor_id
                )

        # Verify repository create was NEVER called
        mock_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_rollback_on_integrity_error(
        self,
        onboarding_service,
        test_doctor_id,
        mock_dependencies
    ):
        """
        Test that database rollback is called on integrity errors.

        Verifies proper transaction management.
        """
        # Arrange
        patient_data = PatientCreate(
            name="Test Patient",
            email="test@example.com",
            phone="+5511999887766",
            birth_date=datetime(1990, 1, 1),
            treatment_type="Test"
        )

        with patch("app.services.patient.onboarding_service.PatientRepository") as mock_repo_class:
            mock_repo = Mock()
            mock_repo.create.side_effect = IntegrityError("Test error", None, None)
            mock_repo_class.return_value = mock_repo

            with patch("app.services.patient.onboarding_service.get_cache_manager"):
                with patch("app.services.patient.onboarding_service.websocket_events") as mock_ws:
                    mock_ws.publish_patient_event = AsyncMock()

                    # Act & Assert
                    with pytest.raises(ValidationError):
                        await onboarding_service.create_patient(
                            patient_data=patient_data,
                            doctor_id=test_doctor_id
                        )

        # Verify rollback was called
        assert mock_dependencies["db"].rollback.called

    @pytest.mark.asyncio
    async def test_missing_required_fields_validation(
        self,
        onboarding_service,
        test_doctor_id,
        mock_dependencies
    ):
        """
        Test validation of missing required fields.

        Verifies that missing required fields are caught by validation.
        """
        # Arrange - missing birth_date
        patient_data = PatientCreate(
            name="Test Patient",
            email="test@example.com",
            phone="+5511999887766",
            treatment_type="Test"
            # birth_date is missing
        )

        mock_dependencies["integrity_service"].validate_patient_data.side_effect = ValidationError(
            "birth_date is required"
        )

        # Act & Assert
        with pytest.raises(ValidationError, match="birth_date is required"):
            await onboarding_service.create_patient(
                patient_data=patient_data,
                doctor_id=test_doctor_id
            )
