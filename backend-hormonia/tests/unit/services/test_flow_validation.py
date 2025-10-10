"""
Comprehensive tests for Flow Start Validation (Critical Fix #1).

Tests cover:
- Patient data completeness validation
- Required field checks (CPF, treatment_type, phone)
- Phone and CPF format validation
- Error message clarity
- Warning handling for recommended fields
"""
import pytest
from datetime import date, datetime
from uuid import uuid4
from unittest.mock import Mock, MagicMock, patch

from app.services.flow_engine import FlowEngine
from app.models.patient import Patient, FlowState
from app.models.user import User
from app.exceptions import ValidationError, NotFoundError


class TestFlowStartValidation:
    """Test suite for flow start validation (Critical Fix #1)."""

    @pytest.fixture
    def db_session(self):
        """Mock database session."""
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        return session

    @pytest.fixture
    def flow_engine(self, db_session):
        """Create FlowEngine instance with mocked dependencies."""
        with patch('app.services.flow_engine.FlowStateRepository'):
            with patch('app.services.flow_engine.PatientRepository'):
                with patch('app.services.flow_engine.FlowTemplateService'):
                    with patch('app.services.flow_engine.FlowContext'):
                        with patch('app.services.flow_engine.MessageService'):
                            with patch('app.services.flow_engine.QuizSessionService'):
                                with patch('app.services.flow_engine.QuizResponseService'):
                                    engine = FlowEngine(db_session)
                                    return engine

    @pytest.fixture
    def valid_patient(self):
        """Create a patient with all required fields."""
        patient = Patient(
            id=uuid4(),
            doctor_id=uuid4(),
            name="João Silva",
            phone="11987654321",
            cpf="12345678901",
            treatment_type="hormone_therapy",
            treatment_start_date=date(2025, 1, 1),
            diagnosis="Câncer de próstata",
            flow_state=FlowState.ONBOARDING,
            current_day=0
        )
        return patient

    @pytest.fixture
    def incomplete_patient(self):
        """Create a patient missing required fields."""
        patient = Patient(
            id=uuid4(),
            doctor_id=uuid4(),
            name="Maria Santos",
            phone="",  # Missing phone
            cpf="",    # Missing CPF
            treatment_type="",  # Missing treatment type
            flow_state=FlowState.ONBOARDING,
            current_day=0
        )
        return patient

    def test_validate_patient_data_with_valid_patient(self, flow_engine, valid_patient):
        """Test validation passes with complete patient data."""
        # Act
        result = flow_engine._validate_patient_data(valid_patient)

        # Assert
        assert result['valid'] is True
        assert result['patient_id'] == str(valid_patient.id)
        assert len(result['errors']) == 0
        assert 'critical' in result['checked_fields']
        assert 'recommended' in result['checked_fields']

    def test_validate_patient_data_missing_cpf(self, flow_engine, valid_patient):
        """Test validation fails when CPF is missing."""
        # Arrange
        valid_patient.cpf = None

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            flow_engine._validate_patient_data(valid_patient)

        assert "CPF não informado" in str(exc_info.value)
        assert "Dados do paciente incompletos" in str(exc_info.value)

    def test_validate_patient_data_missing_treatment_type(self, flow_engine, valid_patient):
        """Test validation fails when treatment_type is missing."""
        # Arrange
        valid_patient.treatment_type = None

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            flow_engine._validate_patient_data(valid_patient)

        assert "Tipo de tratamento não informado" in str(exc_info.value)

    def test_validate_patient_data_missing_phone(self, flow_engine, valid_patient):
        """Test validation fails when phone is missing."""
        # Arrange
        valid_patient.phone = None

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            flow_engine._validate_patient_data(valid_patient)

        assert "Telefone não informado" in str(exc_info.value)

    def test_validate_patient_data_empty_string_fields(self, flow_engine, valid_patient):
        """Test validation fails with empty string values."""
        # Arrange
        valid_patient.cpf = "   "
        valid_patient.phone = ""
        valid_patient.treatment_type = "  "

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            flow_engine._validate_patient_data(valid_patient)

        error_message = str(exc_info.value)
        assert "CPF não informado" in error_message
        assert "Telefone não informado" in error_message
        assert "Tipo de tratamento não informado" in error_message

    def test_validate_patient_data_invalid_phone_format(self, flow_engine, valid_patient):
        """Test validation fails with invalid phone format."""
        # Arrange - Phone with less than 10 digits
        valid_patient.phone = "1198765"

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            flow_engine._validate_patient_data(valid_patient)

        assert "Telefone com formato inválido" in str(exc_info.value)

    def test_validate_patient_data_valid_phone_formats(self, flow_engine, valid_patient):
        """Test validation passes with various valid phone formats."""
        valid_phones = [
            "11987654321",      # 11 digits (with DDD)
            "(11) 98765-4321",  # Formatted
            "11 98765-4321",    # Formatted with space
            "1234567890",       # 10 digits (landline)
        ]

        for phone in valid_phones:
            # Arrange
            valid_patient.phone = phone

            # Act
            result = flow_engine._validate_patient_data(valid_patient)

            # Assert
            assert result['valid'] is True, f"Phone {phone} should be valid"

    def test_validate_patient_data_invalid_cpf_format(self, flow_engine, valid_patient):
        """Test validation fails with invalid CPF format."""
        # Arrange - CPF with wrong number of digits
        valid_patient.cpf = "123456789"  # Only 9 digits

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            flow_engine._validate_patient_data(valid_patient)

        assert "CPF com formato inválido" in str(exc_info.value)
        assert "11 dígitos" in str(exc_info.value)

    def test_validate_patient_data_valid_cpf_formats(self, flow_engine, valid_patient):
        """Test validation passes with various valid CPF formats."""
        valid_cpfs = [
            "12345678901",          # 11 digits plain
            "123.456.789-01",       # Formatted
            "123 456 789 01",       # Formatted with spaces
        ]

        for cpf in valid_cpfs:
            # Arrange
            valid_patient.cpf = cpf

            # Act
            result = flow_engine._validate_patient_data(valid_patient)

            # Assert
            assert result['valid'] is True, f"CPF {cpf} should be valid"

    def test_validate_patient_data_warnings_for_recommended_fields(
        self, flow_engine, valid_patient, caplog
    ):
        """Test warnings are logged for missing recommended fields."""
        # Arrange
        valid_patient.diagnosis = None
        valid_patient.treatment_start_date = None

        # Act
        with caplog.at_level('WARNING'):
            result = flow_engine._validate_patient_data(valid_patient)

        # Assert
        assert result['valid'] is True  # Should still pass
        assert len(result['warnings']) == 2
        assert any('diagnosis' in w['field'] for w in result['warnings'])
        assert any('treatment_start_date' in w['field'] for w in result['warnings'])

        # Check logging
        warning_logs = [rec.message for rec in caplog.records if rec.levelname == 'WARNING']
        assert any('campos recomendados ausentes' in log for log in warning_logs)

    def test_validate_patient_data_multiple_errors(self, flow_engine, incomplete_patient):
        """Test validation collects all errors for incomplete patient."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            flow_engine._validate_patient_data(incomplete_patient)

        error_message = str(exc_info.value)

        # Should contain all three critical errors
        assert "CPF não informado" in error_message
        assert "Tipo de tratamento não informado" in error_message
        assert "Telefone não informado" in error_message

    @patch('app.services.flow_engine.FlowEngine._validate_patient_data')
    def test_start_flow_calls_validation(
        self, mock_validate, flow_engine, valid_patient
    ):
        """Test that start_flow calls patient data validation."""
        # Arrange
        mock_validate.return_value = {
            'valid': True,
            'patient_id': str(valid_patient.id),
            'errors': [],
            'warnings': []
        }

        flow_engine.patient_repo.get = Mock(return_value=valid_patient)
        flow_engine.template_service.get_template_data = Mock(return_value=None)
        flow_engine._get_template_with_fallback = Mock(return_value=None)

        # Act & Assert - Should raise NotFoundError for template, not ValidationError
        with pytest.raises(NotFoundError):
            flow_engine.start_flow(
                patient_id=valid_patient.id,
                flow_type="test_flow",
                fallback_to_default=False
            )

        # Validation should have been called
        mock_validate.assert_called_once_with(valid_patient)

    @patch('app.services.flow_engine.FlowEngine._validate_patient_data')
    def test_start_flow_fails_on_invalid_patient_data(
        self, mock_validate, flow_engine, incomplete_patient
    ):
        """Test that start_flow fails when patient data validation fails."""
        # Arrange
        mock_validate.side_effect = ValidationError(
            "Dados do paciente incompletos ou inválidos. Erros: cpf: CPF não informado"
        )

        flow_engine.patient_repo.get = Mock(return_value=incomplete_patient)

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            flow_engine.start_flow(
                patient_id=incomplete_patient.id,
                flow_type="test_flow"
            )

        assert "Dados do paciente incompletos" in str(exc_info.value)
        mock_validate.assert_called_once()

    def test_validation_error_message_clarity(self, flow_engine, valid_patient):
        """Test that validation error messages are clear and actionable."""
        # Arrange - Remove all critical fields
        valid_patient.cpf = None
        valid_patient.phone = None
        valid_patient.treatment_type = None

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            flow_engine._validate_patient_data(valid_patient)

        error_message = str(exc_info.value)

        # Error message should be clear and list all issues
        assert "Dados do paciente incompletos ou inválidos" in error_message
        assert "CPF" in error_message
        assert "Telefone" in error_message
        assert "Tipo de tratamento" in error_message

    def test_validation_result_structure(self, flow_engine, valid_patient):
        """Test that validation result has expected structure."""
        # Act
        result = flow_engine._validate_patient_data(valid_patient)

        # Assert
        assert 'valid' in result
        assert 'patient_id' in result
        assert 'errors' in result
        assert 'warnings' in result
        assert 'checked_fields' in result

        assert isinstance(result['valid'], bool)
        assert isinstance(result['errors'], list)
        assert isinstance(result['warnings'], list)
        assert isinstance(result['checked_fields'], dict)

        assert 'critical' in result['checked_fields']
        assert 'recommended' in result['checked_fields']

    def test_validation_with_whitespace_only_values(self, flow_engine, valid_patient):
        """Test that whitespace-only values are treated as missing."""
        # Arrange
        valid_patient.cpf = "   "
        valid_patient.treatment_type = "\t\n"

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            flow_engine._validate_patient_data(valid_patient)

        error_message = str(exc_info.value)
        assert "CPF não informado" in error_message
        assert "Tipo de tratamento não informado" in error_message


class TestFlowStartIntegration:
    """Integration tests for flow start with validation."""

    @pytest.fixture
    def db_session(self):
        """Mock database session."""
        session = MagicMock()
        return session

    @pytest.fixture
    def flow_engine(self, db_session):
        """Create FlowEngine with minimal mocking."""
        with patch('app.services.flow_engine.FlowStateRepository'):
            with patch('app.services.flow_engine.PatientRepository'):
                with patch('app.services.flow_engine.FlowTemplateService'):
                    with patch('app.services.flow_engine.FlowContext'):
                        with patch('app.services.flow_engine.MessageService'):
                            with patch('app.services.flow_engine.QuizSessionService'):
                                with patch('app.services.flow_engine.QuizResponseService'):
                                    engine = FlowEngine(db_session)
                                    return engine

    def test_start_flow_patient_not_found(self, flow_engine):
        """Test start_flow with non-existent patient."""
        # Arrange
        patient_id = uuid4()
        flow_engine.patient_repo.get = Mock(return_value=None)

        # Act & Assert
        with pytest.raises(NotFoundError) as exc_info:
            flow_engine.start_flow(patient_id=patient_id, flow_type="test_flow")

        assert f"Patient {patient_id} not found" in str(exc_info.value)

    def test_start_flow_validation_before_template_lookup(self, flow_engine):
        """Test that validation happens before template lookup."""
        # Arrange
        patient = Patient(
            id=uuid4(),
            doctor_id=uuid4(),
            name="Test Patient",
            phone="",  # Missing phone - will fail validation
            cpf="",    # Missing CPF
            treatment_type="",  # Missing treatment type
            flow_state=FlowState.ONBOARDING
        )

        flow_engine.patient_repo.get = Mock(return_value=patient)
        flow_engine.template_service.get_template_data = Mock()

        # Act & Assert
        with pytest.raises(ValidationError):
            flow_engine.start_flow(patient_id=patient.id, flow_type="test_flow")

        # Template service should NOT be called if validation fails
        flow_engine.template_service.get_template_data.assert_not_called()


# Performance and edge case tests
class TestValidationEdgeCases:
    """Test edge cases and performance for validation."""

    @pytest.fixture
    def flow_engine(self):
        """Create FlowEngine with mocked dependencies."""
        with patch('app.services.flow_engine.FlowStateRepository'):
            with patch('app.services.flow_engine.PatientRepository'):
                with patch('app.services.flow_engine.FlowTemplateService'):
                    with patch('app.services.flow_engine.FlowContext'):
                        with patch('app.services.flow_engine.MessageService'):
                            with patch('app.services.flow_engine.QuizSessionService'):
                                with patch('app.services.flow_engine.QuizResponseService'):
                                    engine = FlowEngine(MagicMock())
                                    return engine

    def test_validation_performance_with_complete_patient(self, flow_engine, benchmark):
        """Test validation performance with complete patient data."""
        patient = Patient(
            id=uuid4(),
            doctor_id=uuid4(),
            name="Performance Test Patient",
            phone="11987654321",
            cpf="12345678901",
            treatment_type="hormone_therapy",
            treatment_start_date=date(2025, 1, 1),
            diagnosis="Test diagnosis",
            flow_state=FlowState.ONBOARDING
        )

        # Benchmark the validation
        result = benchmark(flow_engine._validate_patient_data, patient)

        assert result['valid'] is True

    def test_validation_with_unicode_characters(self, flow_engine):
        """Test validation with unicode characters in patient data."""
        patient = Patient(
            id=uuid4(),
            doctor_id=uuid4(),
            name="José María Ñoño",
            phone="11987654321",
            cpf="12345678901",
            treatment_type="hormonioterapia",
            diagnosis="Câncer de próstata",
            flow_state=FlowState.ONBOARDING
        )

        # Act
        result = flow_engine._validate_patient_data(patient)

        # Assert - Should handle unicode gracefully
        assert result['valid'] is True

    def test_validation_with_very_long_phone_number(self, flow_engine):
        """Test validation rejects phone numbers that are too long."""
        patient = Patient(
            id=uuid4(),
            doctor_id=uuid4(),
            name="Test Patient",
            phone="119876543211234567890",  # Way too long
            cpf="12345678901",
            treatment_type="hormone_therapy",
            flow_state=FlowState.ONBOARDING
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            flow_engine._validate_patient_data(patient)

        assert "Telefone com formato inválido" in str(exc_info.value)
