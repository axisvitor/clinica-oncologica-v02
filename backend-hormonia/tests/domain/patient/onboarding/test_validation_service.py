"""
Comprehensive tests for ValidationService.

This test suite ensures 100% code coverage for patient validation
and duplicate detection logic.
"""

import pytest
from uuid import uuid4
from unittest.mock import patch

from app.domain.patient.onboarding.validation_service import ValidationService
from app.models.patient import Patient
from app.schemas.patient import PatientCreate
from app.exceptions import ValidationError


class TestValidationServiceInitialization:
    """Tests for ValidationService initialization."""

    def test_init_with_all_dependencies(self, db_session):
        """Test initialization with all dependencies."""
        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=3)

        service = ValidationService(db=db_session, executor=executor)

        assert service.db == db_session
        assert service._executor == executor

    def test_init_creates_default_executor(self, db_session):
        """Test initialization creates default executor if not provided."""
        service = ValidationService(db=db_session)

        assert service.db == db_session
        assert service._executor is not None
        assert hasattr(service._executor, 'submit')


class TestFindExistingPatient:
    """Tests for find_existing_patient method."""

    @pytest.fixture
    def validation_service(self, db_session, sync_executor):
        """Create ValidationService instance."""
        return ValidationService(db=db_session, executor=sync_executor)

    @pytest.mark.asyncio
    async def test_find_by_cpf_success(self, validation_service, db_session):
        """Test finding existing patient by CPF."""
        # Setup: Create test patient
        doctor_id = uuid4()
        patient = Patient(
            id=uuid4(),
            name="João Silva",
            cpf="12345678909",
            phone="+5511999999999",
            email="joao@example.com",
            doctor_id=doctor_id,
        )
        db_session.add(patient)
        db_session.commit()

        # Execute
        found_patient = await validation_service.find_existing_patient(
            cpf="12345678909",
            email="different@example.com",
            phone="+5511888888888",
            doctor_id=doctor_id,
        )

        # Assert
        assert found_patient is not None
        assert found_patient.id == patient.id
        assert found_patient.cpf == "12345678909"

    @pytest.mark.asyncio
    async def test_find_by_email_success(self, validation_service, db_session):
        """Test finding existing patient by email."""
        # Setup: Create test patient without CPF
        doctor_id = uuid4()
        patient = Patient(
            id=uuid4(),
            name="Maria Santos",
            email="maria@example.com",
            phone="+5511999999999",
            doctor_id=doctor_id,
        )
        db_session.add(patient)
        db_session.commit()

        # Execute
        found_patient = await validation_service.find_existing_patient(
            cpf=None,
            email="maria@example.com",
            phone="+5511888888888",
            doctor_id=doctor_id,
        )

        # Assert
        assert found_patient is not None
        assert found_patient.id == patient.id
        assert found_patient.email == "maria@example.com"

    @pytest.mark.asyncio
    async def test_find_by_phone_success(self, validation_service, db_session):
        """Test finding existing patient by phone."""
        # Setup: Create test patient without CPF and email
        doctor_id = uuid4()
        patient = Patient(
            id=uuid4(),
            name="Pedro Costa",
            phone="+5511999999999",
            doctor_id=doctor_id,
        )
        db_session.add(patient)
        db_session.commit()

        # Execute
        found_patient = await validation_service.find_existing_patient(
            cpf=None,
            email=None,
            phone="+5511999999999",
            doctor_id=doctor_id,
        )

        # Assert
        assert found_patient is not None
        assert found_patient.id == patient.id
        assert found_patient.phone == "+5511999999999"

    @pytest.mark.asyncio
    async def test_find_no_match_returns_none(self, validation_service, db_session):
        """Test that no match returns None."""
        doctor_id = uuid4()

        # Execute
        found_patient = await validation_service.find_existing_patient(
            cpf="99999999999",
            email="nonexistent@example.com",
            phone="+5511000000000",
            doctor_id=doctor_id,
        )

        # Assert
        assert found_patient is None

    @pytest.mark.asyncio
    async def test_find_ignores_deleted_patients(self, validation_service, db_session):
        """Test that deleted patients are ignored."""
        from datetime import datetime

        # Setup: Create deleted patient
        doctor_id = uuid4()
        patient = Patient(
            id=uuid4(),
            name="Deleted Patient",
            cpf="12345678909",
            phone="+5511999999999",
            doctor_id=doctor_id,
            deleted_at=datetime.utcnow(),
        )
        db_session.add(patient)
        db_session.commit()

        # Execute
        found_patient = await validation_service.find_existing_patient(
            cpf="12345678909",
            email=None,
            phone="+5511999999999",
            doctor_id=doctor_id,
        )

        # Assert: Deleted patient should not be found
        assert found_patient is None

    @pytest.mark.asyncio
    async def test_find_respects_doctor_scope(self, validation_service, db_session):
        """Test that patient search is scoped to doctor."""
        # Setup: Create patient for different doctor
        doctor_id_1 = uuid4()
        doctor_id_2 = uuid4()
        patient = Patient(
            id=uuid4(),
            name="Patient for Doctor 1",
            cpf="12345678909",
            phone="+5511999999999",
            doctor_id=doctor_id_1,
        )
        db_session.add(patient)
        db_session.commit()

        # Execute: Search for same CPF but different doctor
        found_patient = await validation_service.find_existing_patient(
            cpf="12345678909",
            email=None,
            phone="+5511999999999",
            doctor_id=doctor_id_2,  # Different doctor
        )

        # Assert: Should not find patient from different doctor
        assert found_patient is None

    @pytest.mark.asyncio
    async def test_find_handles_database_error(self, validation_service, db_session):
        """Test graceful handling of database errors."""
        # Setup: Mock database to raise exception
        with patch.object(db_session, 'query', side_effect=Exception("Database error")):
            doctor_id = uuid4()

            # Execute: Should not raise exception
            found_patient = await validation_service.find_existing_patient(
                cpf="12345678909",
                email="test@example.com",
                phone="+5511999999999",
                doctor_id=doctor_id,
            )

            # Assert: Should return None on error
            assert found_patient is None


class TestValidatePatientUniqueness:
    """Tests for validate_patient_uniqueness method."""

    @pytest.fixture
    def validation_service(self, db_session, sync_executor):
        """Create ValidationService instance."""
        return ValidationService(db=db_session, executor=sync_executor)

    @pytest.mark.asyncio
    async def test_validation_passes_for_new_patient(self, validation_service):
        """Test validation passes for new unique patient."""
        doctor_id = uuid4()
        patient_data = PatientCreate(
            name="New Patient",
            cpf="12345678909",
            email="new@example.com",
            phone="+5511999999999",
        )

        # Execute: Should not raise exception
        await validation_service.validate_patient_uniqueness(
            patient_data=patient_data,
            doctor_id=doctor_id,
        )

    @pytest.mark.asyncio
    async def test_validation_fails_for_existing_patient(
        self, validation_service, db_session
    ):
        """Test validation fails for existing patient."""
        # Setup: Create existing patient
        doctor_id = uuid4()
        existing_patient = Patient(
            id=uuid4(),
            name="Existing Patient",
            cpf="12345678909",
            phone="+5511999999999",
            doctor_id=doctor_id,
        )
        db_session.add(existing_patient)
        db_session.commit()

        patient_data = PatientCreate(
            name="Duplicate Patient",
            cpf="12345678909",
            phone="+5511999999999",
        )

        # Execute & Assert: Should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            await validation_service.validate_patient_uniqueness(
                patient_data=patient_data,
                doctor_id=doctor_id,
            )

        assert "already exists" in str(exc_info.value)
        assert str(existing_patient.id) in str(exc_info.value)


class TestValidatePhoneFormat:
    """Tests for validate_phone_format method."""

    @pytest.fixture
    def validation_service(self, db_session, sync_executor):
        """Create ValidationService instance."""
        return ValidationService(db=db_session, executor=sync_executor)

    @pytest.mark.asyncio
    async def test_valid_phone_10_digits(self, validation_service):
        """Test validation passes for valid 10-digit phone."""
        await validation_service.validate_phone_format("+551133334444")
        await validation_service.validate_phone_format("1133334444")
        await validation_service.validate_phone_format("(11) 3333-4444")

    @pytest.mark.asyncio
    async def test_valid_phone_11_digits(self, validation_service):
        """Test validation passes for valid 11-digit phone."""
        await validation_service.validate_phone_format("+5511987654321")
        await validation_service.validate_phone_format("11987654321")

    @pytest.mark.asyncio
    async def test_invalid_phone_empty(self, validation_service):
        """Test validation fails for empty phone."""
        with pytest.raises(ValidationError) as exc_info:
            await validation_service.validate_phone_format("")
        assert "required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_phone_too_short(self, validation_service):
        """Test validation fails for too short phone."""
        with pytest.raises(ValidationError) as exc_info:
            await validation_service.validate_phone_format("123456789")
        assert "Invalid phone number format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_phone_too_long(self, validation_service):
        """Test validation fails for too long phone."""
        with pytest.raises(ValidationError) as exc_info:
            await validation_service.validate_phone_format("123456789092")
        assert "Invalid phone number format" in str(exc_info.value)


class TestValidateCPFFormat:
    """Tests for validate_cpf_format method."""

    @pytest.fixture
    def validation_service(self, db_session, sync_executor):
        """Create ValidationService instance."""
        return ValidationService(db=db_session, executor=sync_executor)

    @pytest.mark.asyncio
    async def test_valid_cpf(self, validation_service):
        """Test validation passes for valid CPF."""
        await validation_service.validate_cpf_format("12345678909")
        await validation_service.validate_cpf_format("123.456.789-01")

    @pytest.mark.asyncio
    async def test_cpf_optional(self, validation_service):
        """Test validation passes for None CPF."""
        await validation_service.validate_cpf_format(None)

    @pytest.mark.asyncio
    async def test_invalid_cpf_too_short(self, validation_service):
        """Test validation fails for too short CPF."""
        with pytest.raises(ValidationError) as exc_info:
            await validation_service.validate_cpf_format("1234567890")
        assert "Invalid CPF format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_cpf_too_long(self, validation_service):
        """Test validation fails for too long CPF."""
        with pytest.raises(ValidationError) as exc_info:
            await validation_service.validate_cpf_format("123456789092")
        assert "Invalid CPF format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_cpf_all_same_digits(self, validation_service):
        """Test validation fails for CPF with all same digits."""
        with pytest.raises(ValidationError) as exc_info:
            await validation_service.validate_cpf_format("11111111111")
        assert "all digits are the same" in str(exc_info.value)


class TestValidateEmailFormat:
    """Tests for validate_email_format method."""

    @pytest.fixture
    def validation_service(self, db_session, sync_executor):
        """Create ValidationService instance."""
        return ValidationService(db=db_session, executor=sync_executor)

    @pytest.mark.asyncio
    async def test_valid_email(self, validation_service):
        """Test validation passes for valid email."""
        await validation_service.validate_email_format("test@example.com")
        await validation_service.validate_email_format("user.name+tag@example.co.uk")

    @pytest.mark.asyncio
    async def test_email_optional(self, validation_service):
        """Test validation passes for None email."""
        await validation_service.validate_email_format(None)

    @pytest.mark.asyncio
    async def test_invalid_email_no_at(self, validation_service):
        """Test validation fails for email without @."""
        with pytest.raises(ValidationError) as exc_info:
            await validation_service.validate_email_format("testexample.com")
        assert "Invalid email format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_email_no_dot(self, validation_service):
        """Test validation fails for email without dot."""
        with pytest.raises(ValidationError) as exc_info:
            await validation_service.validate_email_format("test@examplecom")
        assert "Invalid email format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_email_too_short(self, validation_service):
        """Test validation fails for too short email."""
        with pytest.raises(ValidationError) as exc_info:
            await validation_service.validate_email_format("a@b")
        assert "Invalid email format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_email_too_long(self, validation_service):
        """Test validation fails for too long email."""
        long_email = "a" * 250 + "@example.com"
        with pytest.raises(ValidationError) as exc_info:
            await validation_service.validate_email_format(long_email)
        assert "too long" in str(exc_info.value)


class TestValidatePatientDataFormat:
    """Tests for validate_patient_data_format method."""

    @pytest.fixture
    def validation_service(self, db_session, sync_executor):
        """Create ValidationService instance."""
        return ValidationService(db=db_session, executor=sync_executor)

    @pytest.mark.asyncio
    async def test_all_validations_pass(self, validation_service):
        """Test all format validations pass for valid data."""
        patient_data = PatientCreate(
            name="Valid Patient",
            cpf="12345678909",
            email="valid@example.com",
            phone="+5511999999999",
        )

        # Execute: Should not raise exception
        await validation_service.validate_patient_data_format(patient_data)

    @pytest.mark.asyncio
    async def test_validation_fails_on_invalid_phone(self, validation_service):
        """Test validation fails when phone is invalid."""
        patient_data = PatientCreate.model_construct(
            name="Invalid Phone",
            phone="123",  # Too short
        )

        with pytest.raises(ValidationError) as exc_info:
            await validation_service.validate_patient_data_format(patient_data)
        assert "phone" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validation_fails_on_invalid_cpf(self, validation_service):
        """Test validation fails when CPF is invalid."""
        patient_data = PatientCreate.model_construct(
            name="Invalid CPF",
            cpf="123",  # Too short
            phone="+5511999999999",
        )

        with pytest.raises(ValidationError) as exc_info:
            await validation_service.validate_patient_data_format(patient_data)
        assert "CPF" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validation_fails_on_invalid_email(self, validation_service):
        """Test validation fails when email is invalid."""
        patient_data = PatientCreate.model_construct(
            name="Invalid Email",
            email="invalid-email",  # No @ or dot
            phone="+5511999999999",
        )

        with pytest.raises(ValidationError) as exc_info:
            await validation_service.validate_patient_data_format(patient_data)
        assert "email" in str(exc_info.value).lower()


class TestValidationServiceShutdown:
    """Tests for shutdown method."""

    def test_shutdown_graceful(self, db_session):
        """Test graceful executor shutdown."""
        service = ValidationService(db=db_session)

        # Execute
        service.shutdown(wait=True)

        # Executor should be shutdown
        assert service._executor._shutdown is True

    def test_shutdown_no_wait(self, db_session):
        """Test executor shutdown without waiting."""
        service = ValidationService(db=db_session)

        # Execute
        service.shutdown(wait=False)

        # Executor should be shutdown
        assert service._executor._shutdown is True


# Pytest fixtures removed - using real db_session from conftest.py
# (Previously had a MagicMock here which caused all tests to fail)
