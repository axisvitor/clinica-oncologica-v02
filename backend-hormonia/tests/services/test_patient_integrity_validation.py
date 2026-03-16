"""
Comprehensive tests for PatientIntegrityService validation consolidation.

This test suite validates that ALL patient validation logic is correctly
centralized in PatientIntegrityService.validate_patient_data() following
the DRY principle.

File: tests/services/test_patient_integrity_validation.py
"""
import pytest
from datetime import date, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, Mock, patch

from app.services.patient.integrity_service import PatientIntegrityService
from app.schemas.patient import PatientCreate, PatientUpdate
from app.exceptions import ValidationError
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.utils.db_retry import reset_circuit_breaker


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock()


@pytest.fixture
def mock_repository():
    """Mock patient repository."""
    return Mock()


@pytest.fixture
def integrity_service(mock_db, mock_repository):
    """Create PatientIntegrityService instance."""
    reset_circuit_breaker()
    return PatientIntegrityService(mock_db, mock_repository)


@pytest.fixture
def valid_patient_data():
    """Valid patient creation data."""
    return PatientCreate(
        name="João Silva",
        email="joao.silva@example.com",
        phone="+5511987654321",
        cpf="12345678909",
        birth_date=date(1990, 1, 1),
        treatment_type="Quimioterapia",
        treatment_start_date=date.today(),
        diagnosis="Câncer de mama",
        treatment_phase="inicial"
    )


@pytest.fixture
def mock_doctor():
    """Mock doctor user."""
    doctor_id = uuid4()
    doctor = Mock(spec=User)
    doctor.id = doctor_id
    doctor.role = UserRole.DOCTOR
    return doctor


class TestCPFValidation:
    """Test CPF validation consolidation."""

    @pytest.mark.asyncio
    async def test_cpf_normalization(self, integrity_service, valid_patient_data):
        """Test CPF normalization removes formatting."""
        # Test CPF with formatting
        patient_data = valid_patient_data.copy()
        patient_data.cpf = "123.456.789-01"

        normalized = integrity_service._normalize_cpf(patient_data.cpf)
        assert normalized == "12345678901"

    @pytest.mark.asyncio
    async def test_cpf_length_validation(self, integrity_service, valid_patient_data, mock_doctor):
        """Test CPF must have exactly 11 digits."""
        with patch.object(integrity_service, '_check_duplicate_cpf', new_callable=Mock, return_value=None):
            with patch.object(integrity_service, '_check_duplicate_email', new_callable=Mock, return_value=None):
                with patch.object(integrity_service, '_check_duplicate_phone', new_callable=Mock, return_value=None):
                    # Test CPF with less than 11 digits
                    patient_data = valid_patient_data.copy()
                    patient_data.cpf = "123456789"  # 9 digits

                    with pytest.raises(ValidationError) as exc_info:
                        integrity_service.validate_patient_data(
                            patient_data=patient_data,
                            doctor_id=mock_doctor.id,
                            is_update=False
                        )

                    assert "CPF must have exactly 11 digits" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cpf_duplicate_detection(self, integrity_service, valid_patient_data, mock_doctor):
        """Test duplicate CPF detection."""
        existing_patient = Mock(spec=Patient)
        existing_patient.name = "Existing Patient"

        with patch.object(integrity_service, '_check_duplicate_cpf', new_callable=Mock, return_value=existing_patient):
            with patch.object(integrity_service, '_check_duplicate_email', new_callable=Mock, return_value=None):
                with patch.object(integrity_service, '_check_duplicate_phone', new_callable=Mock, return_value=None):
                    with pytest.raises(ValidationError) as exc_info:
                        integrity_service.validate_patient_data(
                            patient_data=valid_patient_data,
                            doctor_id=mock_doctor.id,
                            is_update=False
                        )

                    assert "Patient with CPF already exists" in str(exc_info.value)


class TestPhoneValidation:
    """Test phone validation consolidation."""

    @pytest.mark.asyncio
    async def test_phone_e164_formatting(self, integrity_service, valid_patient_data, mock_doctor):
        """Test phone is formatted to E.164."""
        with patch.object(integrity_service, '_check_duplicate_cpf', new_callable=Mock, return_value=None):
            with patch.object(integrity_service, '_check_duplicate_email', new_callable=Mock, return_value=None):
                with patch.object(integrity_service, '_check_duplicate_phone', new_callable=Mock, return_value=None):
                    mock_doctor_obj = Mock(spec=User)
                    mock_doctor_obj.id = mock_doctor.id
                    mock_doctor_obj.role = UserRole.DOCTOR
                    execute_result = Mock()
                    execute_result.scalars.return_value.first.return_value = mock_doctor_obj
                    integrity_service.db.execute.return_value = execute_result

                    validated = integrity_service.validate_patient_data(
                        patient_data=valid_patient_data,
                        doctor_id=mock_doctor.id,
                        is_update=False
                    )

                    assert validated['phone'] == "+5511987654321"

    @pytest.mark.asyncio
    async def test_phone_duplicate_detection(self, integrity_service, valid_patient_data, mock_doctor):
        """Test duplicate phone detection."""
        existing_patient = Mock(spec=Patient)
        existing_patient.name = "Existing Patient"

        with patch.object(integrity_service, '_check_duplicate_cpf', new_callable=Mock, return_value=None):
            with patch.object(integrity_service, '_check_duplicate_email', new_callable=Mock, return_value=None):
                with patch.object(integrity_service, '_check_duplicate_phone', new_callable=Mock, return_value=existing_patient):
                    with pytest.raises(ValidationError) as exc_info:
                        integrity_service.validate_patient_data(
                            patient_data=valid_patient_data,
                            doctor_id=mock_doctor.id,
                            is_update=False
                        )

                    assert "Patient with phone already exists" in str(exc_info.value)


class TestEmailValidation:
    """Test email validation consolidation."""

    @pytest.mark.asyncio
    async def test_email_format_validation(self, integrity_service, valid_patient_data, mock_doctor):
        """Test email format validation."""
        patient_data = valid_patient_data.copy()
        patient_data.email = "invalid-email"

        with patch.object(integrity_service, '_check_duplicate_cpf', new_callable=Mock, return_value=None):
            with patch.object(integrity_service, '_check_duplicate_phone', new_callable=Mock, return_value=None):
                with pytest.raises(ValidationError) as exc_info:
                    integrity_service.validate_patient_data(
                        patient_data=patient_data,
                        doctor_id=mock_doctor.id,
                        is_update=False
                    )

                assert "Invalid email format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_email_duplicate_detection(self, integrity_service, valid_patient_data, mock_doctor):
        """Test duplicate email detection."""
        existing_patient = Mock(spec=Patient)
        existing_patient.name = "Existing Patient"

        with patch.object(integrity_service, '_check_duplicate_cpf', new_callable=Mock, return_value=None):
            with patch.object(integrity_service, '_check_duplicate_email', new_callable=Mock, return_value=existing_patient):
                with patch.object(integrity_service, '_check_duplicate_phone', new_callable=Mock, return_value=None):
                    with pytest.raises(ValidationError) as exc_info:
                        integrity_service.validate_patient_data(
                            patient_data=valid_patient_data,
                            doctor_id=mock_doctor.id,
                            is_update=False
                        )

                    assert "Patient with email already exists" in str(exc_info.value)


class TestDoctorValidation:
    """Test doctor existence validation."""

    @pytest.mark.asyncio
    async def test_doctor_exists_validation(self, integrity_service, valid_patient_data):
        """Test doctor existence check."""
        fake_doctor_id = uuid4()

        # Mock query to return None (doctor not found)
        integrity_service.db.query.return_value.filter.return_value.first.return_value = None

        with patch.object(integrity_service, '_check_duplicate_cpf', new_callable=Mock, return_value=None):
            with patch.object(integrity_service, '_check_duplicate_email', new_callable=Mock, return_value=None):
                with patch.object(integrity_service, '_check_duplicate_phone', new_callable=Mock, return_value=None):
                    with pytest.raises(ValidationError) as exc_info:
                        integrity_service.validate_patient_data(
                            patient_data=valid_patient_data,
                            doctor_id=fake_doctor_id,
                            is_update=False
                        )

                    assert f"Doctor with id {fake_doctor_id} not found" in str(exc_info.value)


class TestAsyncValidation:
    """Test async validation path used by AsyncSession-backed API routes."""

    @pytest.mark.asyncio
    async def test_async_doctor_exists_validation_passes(
        self,
        mock_repository,
        valid_patient_data,
        mock_doctor,
    ):
        """Async validation must accept a real doctor when db.execute is awaitable."""
        async_db = AsyncMock()
        execute_result = Mock()
        execute_result.scalars.return_value.first.return_value = mock_doctor
        async_db.execute = AsyncMock(return_value=execute_result)

        integrity_service = PatientIntegrityService(async_db, mock_repository)

        with patch.object(
            integrity_service,
            "check_duplicate_cpf_async",
            new=AsyncMock(return_value=None),
        ), patch.object(
            integrity_service,
            "check_duplicate_email_async",
            new=AsyncMock(return_value=None),
        ), patch.object(
            integrity_service,
            "check_duplicate_phone_async",
            new=AsyncMock(return_value=None),
        ):
            validated = await integrity_service.validate_patient_data_async(
                patient_data=valid_patient_data,
                doctor_id=mock_doctor.id,
                is_update=False,
            )

        assert validated["doctor_id"] == mock_doctor.id
        assert validated["validation_errors"] == []
        async_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_duplicate_phone_detection(
        self,
        mock_repository,
        valid_patient_data,
        mock_doctor,
    ):
        """Async validation must use async duplicate checks instead of sync AsyncSession fallbacks."""
        async_db = AsyncMock()
        execute_result = Mock()
        execute_result.scalars.return_value.first.return_value = mock_doctor
        async_db.execute = AsyncMock(return_value=execute_result)

        integrity_service = PatientIntegrityService(async_db, mock_repository)
        existing_patient = Mock(spec=Patient)
        existing_patient.name = "Existing Patient"

        with patch.object(
            integrity_service,
            "check_duplicate_cpf_async",
            new=AsyncMock(return_value=None),
        ), patch.object(
            integrity_service,
            "check_duplicate_email_async",
            new=AsyncMock(return_value=None),
        ), patch.object(
            integrity_service,
            "check_duplicate_phone_async",
            new=AsyncMock(return_value=existing_patient),
        ):
            with pytest.raises(ValidationError) as exc_info:
                await integrity_service.validate_patient_data_async(
                    patient_data=valid_patient_data,
                    doctor_id=mock_doctor.id,
                    is_update=False,
                )

        assert "Patient with phone already exists" in str(exc_info.value)


class TestTreatmentDateValidation:
    """Test treatment date validation."""

    @pytest.mark.asyncio
    async def test_treatment_date_future_limit(self, integrity_service, valid_patient_data, mock_doctor):
        """Test treatment date cannot be too far in future."""
        patient_data = valid_patient_data.copy()
        patient_data.treatment_start_date = date.today() + timedelta(days=60)  # 60 days in future

        with patch.object(integrity_service, '_check_duplicate_cpf', new_callable=Mock, return_value=None):
            with patch.object(integrity_service, '_check_duplicate_email', new_callable=Mock, return_value=None):
                with patch.object(integrity_service, '_check_duplicate_phone', new_callable=Mock, return_value=None):
                    with pytest.raises(ValidationError) as exc_info:
                        integrity_service.validate_patient_data(
                            patient_data=patient_data,
                            doctor_id=mock_doctor.id,
                            is_update=False
                        )

                    assert "Treatment start date cannot be more than" in str(exc_info.value)


class TestBirthDateValidation:
    """Test birth date validation."""

    @pytest.mark.asyncio
    async def test_birth_date_not_future(self, integrity_service, valid_patient_data, mock_doctor):
        """Test birth date cannot be in future."""
        patient_data = valid_patient_data.copy()
        patient_data.birth_date = date.today() + timedelta(days=1)

        with patch.object(integrity_service, '_check_duplicate_cpf', new_callable=Mock, return_value=None):
            with patch.object(integrity_service, '_check_duplicate_email', new_callable=Mock, return_value=None):
                with patch.object(integrity_service, '_check_duplicate_phone', new_callable=Mock, return_value=None):
                    with pytest.raises(ValidationError) as exc_info:
                        integrity_service.validate_patient_data(
                            patient_data=patient_data,
                            doctor_id=mock_doctor.id,
                            is_update=False
                        )

                    assert "Birth date cannot be in the future" in str(exc_info.value)


class TestNameValidation:
    """Test name validation."""

    @pytest.mark.asyncio
    async def test_name_minimum_length(self, integrity_service, valid_patient_data, mock_doctor):
        """Test name must have minimum 2 characters."""
        patient_data = valid_patient_data.copy()
        patient_data.name = "A"

        with patch.object(integrity_service, '_check_duplicate_cpf', new_callable=Mock, return_value=None):
            with patch.object(integrity_service, '_check_duplicate_email', new_callable=Mock, return_value=None):
                with patch.object(integrity_service, '_check_duplicate_phone', new_callable=Mock, return_value=None):
                    with pytest.raises(ValidationError) as exc_info:
                        integrity_service.validate_patient_data(
                            patient_data=patient_data,
                            doctor_id=mock_doctor.id,
                            is_update=False
                        )

                    assert "Name must have at least 2 characters" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_name_maximum_length(self, integrity_service, valid_patient_data, mock_doctor):
        """Test name must not exceed 200 characters."""
        patient_data = valid_patient_data.copy()
        patient_data.name = "A" * 201

        with patch.object(integrity_service, '_check_duplicate_cpf', new_callable=Mock, return_value=None):
            with patch.object(integrity_service, '_check_duplicate_email', new_callable=Mock, return_value=None):
                with patch.object(integrity_service, '_check_duplicate_phone', new_callable=Mock, return_value=None):
                    with pytest.raises(ValidationError) as exc_info:
                        integrity_service.validate_patient_data(
                            patient_data=patient_data,
                            doctor_id=mock_doctor.id,
                            is_update=False
                        )

                    assert "Name must not exceed 200 characters" in str(exc_info.value)


class TestUpdateValidation:
    """Test update validation scenarios."""

    @pytest.mark.asyncio
    async def test_update_excludes_current_patient(self, integrity_service, mock_doctor):
        """Test update validation excludes current patient from duplicate checks."""
        patient_id = uuid4()
        update_data = PatientUpdate(
            cpf="12345678909",
            email="new@example.com"
        )

        with patch.object(integrity_service, '_check_duplicate_cpf', new_callable=Mock) as mock_cpf:
            with patch.object(integrity_service, '_check_duplicate_email', new_callable=Mock) as mock_email:
                with patch.object(integrity_service, '_check_duplicate_phone', new_callable=Mock):
                    mock_cpf.return_value = None
                    mock_email.return_value = None

                    integrity_service.validate_patient_data(
                        patient_data=update_data,
                        doctor_id=mock_doctor.id,
                        patient_id=patient_id,
                        is_update=True
                    )

                    # Verify exclude_patient_id was passed
                    mock_cpf.assert_called_once()
                    assert mock_cpf.call_args.args[2] == patient_id


class TestFieldLengthValidation:
    """Test field length validations."""

    @pytest.mark.asyncio
    async def test_diagnosis_max_length(self, integrity_service, valid_patient_data, mock_doctor):
        """Test diagnosis must not exceed 500 characters."""
        patient_data = valid_patient_data.copy()
        patient_data.diagnosis = "A" * 501

        with patch.object(integrity_service, '_check_duplicate_cpf', new_callable=Mock, return_value=None):
            with patch.object(integrity_service, '_check_duplicate_email', new_callable=Mock, return_value=None):
                with patch.object(integrity_service, '_check_duplicate_phone', new_callable=Mock, return_value=None):
                    with pytest.raises(ValidationError) as exc_info:
                        integrity_service.validate_patient_data(
                            patient_data=patient_data,
                            doctor_id=mock_doctor.id,
                            is_update=False
                        )

                    assert "Diagnosis must not exceed 500 characters" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_treatment_phase_max_length(self, integrity_service, valid_patient_data, mock_doctor):
        """Test treatment phase must not exceed 100 characters."""
        patient_data = valid_patient_data.copy()
        patient_data.treatment_phase = "A" * 101

        with patch.object(integrity_service, '_check_duplicate_cpf', new_callable=Mock, return_value=None):
            with patch.object(integrity_service, '_check_duplicate_email', new_callable=Mock, return_value=None):
                with patch.object(integrity_service, '_check_duplicate_phone', new_callable=Mock, return_value=None):
                    with pytest.raises(ValidationError) as exc_info:
                        integrity_service.validate_patient_data(
                            patient_data=patient_data,
                            doctor_id=mock_doctor.id,
                            is_update=False
                        )

                    assert "Treatment phase must not exceed 100 characters" in str(exc_info.value)


class TestSuccessfulValidation:
    """Test successful validation scenarios."""

    @pytest.mark.asyncio
    async def test_valid_patient_data_passes(self, integrity_service, valid_patient_data, mock_doctor):
        """Test valid patient data passes all validations."""
        mock_doctor_obj = Mock(spec=User)
        mock_doctor_obj.id = mock_doctor.id
        mock_doctor_obj.role = UserRole.DOCTOR
        execute_result = Mock()
        execute_result.scalars.return_value.first.return_value = mock_doctor_obj
        integrity_service.db.execute.return_value = execute_result

        with patch.object(integrity_service, '_check_duplicate_cpf', new_callable=Mock, return_value=None):
            with patch.object(integrity_service, '_check_duplicate_email', new_callable=Mock, return_value=None):
                with patch.object(integrity_service, '_check_duplicate_phone', new_callable=Mock, return_value=None):
                    validated = integrity_service.validate_patient_data(
                        patient_data=valid_patient_data,
                        doctor_id=mock_doctor.id,
                        is_update=False
                    )

                    # Verify all expected fields are validated
                    assert 'cpf' in validated
                    assert 'email' in validated
                    assert 'phone' in validated
                    assert 'name' in validated
                    assert validated['validation_errors'] == []
