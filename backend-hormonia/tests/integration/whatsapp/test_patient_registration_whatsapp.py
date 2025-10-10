"""
Integration tests for WhatsApp welcome message on patient registration.

Tests verify that welcome messages are sent correctly when patients are registered,
and that failures are properly logged for retry.
"""
import pytest
from uuid import uuid4
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from app.models.patient import Patient, FlowState
from app.models.user import User, UserRole
from app.schemas.patient import PatientCreate
from app.services.patient import PatientService


@pytest.fixture
def mock_whatsapp_service():
    """Mock WhatsApp service for testing."""
    with patch('app.services.patient.WhatsAppUnifiedService') as mock:
        instance = mock.return_value
        instance.send_message = AsyncMock(return_value={
            "status": "sent",
            "message_id": "test-message-id",
            "timestamp": datetime.utcnow()
        })
        yield instance


@pytest.fixture
def sample_patient_data():
    """Sample patient data for testing."""
    return PatientCreate(
        name="Maria Silva",
        phone="+5511999999999",
        email="maria.silva@example.com",
        treatment_type="hormone_therapy",
        birth_date="1980-01-15",
        cpf="12345678901"
    )


@pytest.fixture
def mock_doctor():
    """Mock doctor user."""
    doctor = Mock(spec=User)
    doctor.id = uuid4()
    doctor.email = "doctor@clinic.com"
    doctor.role = UserRole.MEDICO
    doctor.name = "Dr. João Santos"
    return doctor


@pytest.mark.asyncio
async def test_welcome_message_sent_on_patient_creation(
    db_session,
    sample_patient_data,
    mock_doctor,
    mock_whatsapp_service,
    settings
):
    """Test that welcome message is sent when patient is created."""
    # Ensure feature is enabled
    settings.ENABLE_WHATSAPP_ON_REGISTRATION = True
    settings.WHATSAPP_WELCOME_MESSAGE_ENABLED = True

    # Create patient service
    from app.repositories.patient import PatientRepository
    from app.services.flow_engine import FlowEngine

    repository = PatientRepository(db_session)
    flow_engine = Mock(spec=FlowEngine)
    flow_engine.start_flow = Mock()

    service = PatientService(
        db=db_session,
        patient_repository=repository,
        integrity_service=Mock(),
        flow_engine=flow_engine
    )

    # Create patient
    patient = await service.create_patient(
        patient_data=sample_patient_data,
        doctor_id=mock_doctor.id,
        current_user=mock_doctor
    )

    # Verify WhatsApp message was sent
    mock_whatsapp_service.send_message.assert_called_once()
    call_args = mock_whatsapp_service.send_message.call_args

    # Verify message parameters
    assert call_args.kwargs['phone_number'] == sample_patient_data.phone
    assert call_args.kwargs['content']['text']  # Message content exists
    assert "Maria Silva" in call_args.kwargs['content']['text']  # Personalized
    assert call_args.kwargs['metadata']['patient_id'] == str(patient.id)
    assert call_args.kwargs['metadata']['message_type'] == "welcome"


@pytest.mark.asyncio
async def test_welcome_message_disabled_by_config(
    db_session,
    sample_patient_data,
    mock_doctor,
    mock_whatsapp_service,
    settings
):
    """Test that welcome message is not sent when disabled in config."""
    # Disable feature
    settings.ENABLE_WHATSAPP_ON_REGISTRATION = False

    # Create patient service
    from app.repositories.patient import PatientRepository
    from app.services.flow_engine import FlowEngine

    repository = PatientRepository(db_session)
    flow_engine = Mock(spec=FlowEngine)

    service = PatientService(
        db=db_session,
        patient_repository=repository,
        integrity_service=Mock(),
        flow_engine=flow_engine
    )

    # Create patient
    await service.create_patient(
        patient_data=sample_patient_data,
        doctor_id=mock_doctor.id,
        current_user=mock_doctor
    )

    # Verify WhatsApp message was NOT sent
    mock_whatsapp_service.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_patient_creation_succeeds_even_if_whatsapp_fails(
    db_session,
    sample_patient_data,
    mock_doctor,
    mock_whatsapp_service,
    settings
):
    """Test that patient creation succeeds even if WhatsApp sending fails."""
    # Enable feature
    settings.ENABLE_WHATSAPP_ON_REGISTRATION = True

    # Configure WhatsApp service to fail
    mock_whatsapp_service.send_message.side_effect = Exception("WhatsApp API error")

    # Create patient service
    from app.repositories.patient import PatientRepository
    from app.services.flow_engine import FlowEngine

    repository = PatientRepository(db_session)
    flow_engine = Mock(spec=FlowEngine)

    service = PatientService(
        db=db_session,
        patient_repository=repository,
        integrity_service=Mock(),
        flow_engine=flow_engine
    )

    # Create patient - should NOT raise exception
    patient = await service.create_patient(
        patient_data=sample_patient_data,
        doctor_id=mock_doctor.id,
        current_user=mock_doctor
    )

    # Verify patient was created
    assert patient is not None
    assert patient.name == sample_patient_data.name
    assert patient.phone == sample_patient_data.phone


@pytest.mark.asyncio
async def test_whatsapp_failure_logged_for_retry(
    db_session,
    sample_patient_data,
    mock_doctor,
    mock_whatsapp_service,
    settings
):
    """Test that WhatsApp failures are logged to database for retry."""
    # Enable feature
    settings.ENABLE_WHATSAPP_ON_REGISTRATION = True
    settings.WHATSAPP_MAX_RETRIES = 3

    # Configure WhatsApp service to fail
    error_message = "WhatsApp API rate limit exceeded"
    mock_whatsapp_service.send_message.side_effect = Exception(error_message)

    # Create patient service
    from app.repositories.patient import PatientRepository
    from app.services.flow_engine import FlowEngine

    repository = PatientRepository(db_session)
    flow_engine = Mock(spec=FlowEngine)

    service = PatientService(
        db=db_session,
        patient_repository=repository,
        integrity_service=Mock(),
        flow_engine=flow_engine
    )

    # Create patient
    patient = await service.create_patient(
        patient_data=sample_patient_data,
        doctor_id=mock_doctor.id,
        current_user=mock_doctor
    )

    # Verify failure was logged
    from sqlalchemy import text
    result = db_session.execute(
        text("SELECT * FROM whatsapp_delivery_failures WHERE patient_id = :patient_id"),
        {"patient_id": patient.id}
    ).first()

    assert result is not None
    assert result.phone_number == sample_patient_data.phone
    assert result.message_type == "welcome"
    assert error_message in result.error_message
    assert result.retry_count == 0
    assert result.max_retries == 3
    assert result.status == "pending"
    assert result.next_retry_at is not None


@pytest.mark.asyncio
async def test_welcome_message_includes_clinic_info(
    db_session,
    sample_patient_data,
    mock_doctor,
    mock_whatsapp_service,
    settings
):
    """Test that welcome message includes clinic name and support info."""
    # Configure clinic settings
    settings.ENABLE_WHATSAPP_ON_REGISTRATION = True
    settings.CLINIC_NAME = "Test Oncology Clinic"
    settings.CLINIC_SUPPORT_PHONE = "+5511888888888"

    # Create patient service
    from app.repositories.patient import PatientRepository
    from app.services.flow_engine import FlowEngine

    repository = PatientRepository(db_session)
    flow_engine = Mock(spec=FlowEngine)

    service = PatientService(
        db=db_session,
        patient_repository=repository,
        integrity_service=Mock(),
        flow_engine=flow_engine
    )

    # Create patient
    await service.create_patient(
        patient_data=sample_patient_data,
        doctor_id=mock_doctor.id,
        current_user=mock_doctor
    )

    # Verify message content
    call_args = mock_whatsapp_service.send_message.call_args
    message_text = call_args.kwargs['content']['text']

    assert "Test Oncology Clinic" in message_text
    assert "+5511888888888" in message_text


@pytest.mark.asyncio
async def test_exponential_backoff_for_retries(
    db_session,
    sample_patient_data,
    mock_doctor,
    settings
):
    """Test that retry delays use exponential backoff."""
    from datetime import timedelta
    from app.services.patient import PatientService
    from app.repositories.patient import PatientRepository
    from app.services.flow_engine import FlowEngine

    settings.WHATSAPP_RETRY_DELAY_SECONDS = 60

    repository = PatientRepository(db_session)
    flow_engine = Mock(spec=FlowEngine)

    service = PatientService(
        db=db_session,
        patient_repository=repository,
        integrity_service=Mock(),
        flow_engine=flow_engine
    )

    patient_id = uuid4()
    phone_number = "+5511999999999"

    # Test retry delays
    for retry_count in range(4):
        await service._log_whatsapp_failure(
            patient_id=patient_id,
            phone_number=phone_number,
            message_type="welcome",
            error_message=f"Test error retry {retry_count}",
            retry_count=retry_count
        )

        # Verify exponential backoff: delay = base_delay * 2^retry_count
        expected_delay = 60 * (2 ** retry_count)

        from sqlalchemy import text
        result = db_session.execute(
            text("""
                SELECT next_retry_at, created_at
                FROM whatsapp_delivery_failures
                WHERE retry_count = :retry_count
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"retry_count": retry_count}
        ).first()

        actual_delay = (result.next_retry_at - result.created_at).total_seconds()
        # Allow 5 second tolerance for test execution time
        assert abs(actual_delay - expected_delay) < 5


@pytest.mark.asyncio
async def test_welcome_message_metadata_tracking(
    db_session,
    sample_patient_data,
    mock_doctor,
    mock_whatsapp_service,
    settings
):
    """Test that message metadata tracks important information."""
    settings.ENABLE_WHATSAPP_ON_REGISTRATION = True

    from app.repositories.patient import PatientRepository
    from app.services.flow_engine import FlowEngine

    repository = PatientRepository(db_session)
    flow_engine = Mock(spec=FlowEngine)

    service = PatientService(
        db=db_session,
        patient_repository=repository,
        integrity_service=Mock(),
        flow_engine=flow_engine
    )

    # Create patient
    patient = await service.create_patient(
        patient_data=sample_patient_data,
        doctor_id=mock_doctor.id,
        current_user=mock_doctor
    )

    # Verify metadata
    call_args = mock_whatsapp_service.send_message.call_args
    metadata = call_args.kwargs['metadata']

    assert metadata['patient_id'] == str(patient.id)
    assert metadata['patient_name'] == sample_patient_data.name
    assert metadata['message_type'] == "welcome"
    assert metadata['created_by'] == mock_doctor.email
    assert metadata['treatment_type'] == sample_patient_data.treatment_type
