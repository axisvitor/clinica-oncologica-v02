import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

from app.services.response_processor import ResponseProcessor, InboundMessage, ResponseType, ResponseProcessingResult
from app.models.patient import Patient

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.enable_ai_processing = False
    config.enable_sentiment_analysis = False
    return config

@pytest.fixture
def response_processor(mock_db, mock_config):
    # Patch services that require external connections
    with patch("app.services.response_processor.processor.get_platform_sync_service") as mock_sync, \
         patch("app.services.response_processor.processor.flow_event_broadcaster") as mock_broadcaster, \
         patch("app.services.response_processor.processor.get_conversational_quiz_service") as mock_quiz:
        mock_sync_service = AsyncMock()
        mock_sync_service.sync_patient_record_update = AsyncMock()
        mock_sync.return_value = mock_sync_service
        mock_broadcaster.broadcast_patient_interaction = AsyncMock()
        mock_quiz.return_value = AsyncMock()

        processor = ResponseProcessor(mock_db, mock_config)
        # Mock repositories
        processor.message_repo = MagicMock()
        processor.flow_state_repo = MagicMock()
        processor.patient_repo = MagicMock()
        processor.flow_broadcaster = mock_broadcaster
        processor.platform_sync = mock_sync_service
        processor.quiz_service = mock_quiz.return_value

        # Mock internal methods to avoid complex logic in unit tests
        processor._store_inbound_message = AsyncMock()
        processor._is_quiz_response = AsyncMock(return_value=False)
        processor._determine_response_type = MagicMock(return_value=ResponseType.TEXT)
        processor._apply_state_updates = AsyncMock()
        processor._trigger_sequential_continuation = AsyncMock()

        processor.validator = MagicMock()
        processor.validator.validate_response = AsyncMock()
        processor.extractor = MagicMock()
        processor.extractor.extract_structured_data = AsyncMock()
        processor.flow_helpers = MagicMock()
        processor.flow_helpers.determine_flow_actions = AsyncMock(return_value=[])
        processor.flow_helpers.generate_follow_up_message = AsyncMock(return_value=None)
        processor.flow_helpers.prepare_state_updates = AsyncMock(return_value=None)
        processor.flow_helpers.check_escalation_required = MagicMock(return_value=False)
        processor.handlers = MagicMock()
        processor.handlers.handle_invalid_response = AsyncMock()

        return processor

@pytest.mark.asyncio
async def test_process_inbound_message_success(response_processor):
    # Setup
    patient_id = uuid4()
    phone = "5511999999999"
    inbound = InboundMessage(
        patient_phone=phone,
        content="Hello",
        whatsapp_id="wamid.123"
    )
    
    # Mocks - use MagicMock since Patient no longer has phone column
    patient = MagicMock(spec=Patient)
    patient.id = patient_id
    patient.name = "Test Patient"
    patient.phone_decrypted = phone  # LGPD: encrypted field accessor
    response_processor.patient_repo.get_by_phone.return_value = patient
    
    response_processor._store_inbound_message.return_value = MagicMock(id=uuid4())
    response_processor.flow_state_repo.get_active_flow.return_value = None
    
    validation_result = MagicMock(is_valid=True, response_type=ResponseType.TEXT)
    response_processor.validator.validate_response.return_value = validation_result
    
    structured_response = MagicMock(
        extracted_data={},
        sentiment_analysis={"confidence": 0.9},
        requires_attention=False,
        medical_concerns=[]
    )
    response_processor.extractor.extract_structured_data.return_value = structured_response
    
    # Execute
    result = await response_processor.process_inbound_message(inbound)
    
    # Verify
    assert isinstance(result, ResponseProcessingResult)
    assert result.patient_id == patient_id
    response_processor.patient_repo.get_by_phone.assert_called_with(phone)
    response_processor._store_inbound_message.assert_called_once()
    response_processor.flow_broadcaster.broadcast_patient_interaction.assert_called_once()
    response_processor.platform_sync.sync_patient_record_update.assert_called_once()

@pytest.mark.asyncio
async def test_process_inbound_message_patient_not_found(response_processor):
    # Setup
    inbound = InboundMessage(
        patient_phone="5511000000000",
        content="Hello",
        whatsapp_id="wamid.123"
    )
    
    response_processor.patient_repo.get_by_phone.return_value = None
    
    # Execute & Verify
    from app.exceptions import NotFoundError
    with pytest.raises(NotFoundError):
        await response_processor.process_inbound_message(inbound)

@pytest.mark.asyncio
async def test_process_inbound_message_invalid_response(response_processor):
    # Setup
    patient_id = uuid4()
    phone = "5511999999999"
    inbound = InboundMessage(
        patient_phone=phone,
        content="",
        whatsapp_id="wamid.123"
    )
    
    # Mocks - use MagicMock since Patient no longer has phone column
    patient = MagicMock(spec=Patient)
    patient.id = patient_id
    patient.phone_decrypted = phone  # LGPD: encrypted field accessor
    response_processor.patient_repo.get_by_phone.return_value = patient
    response_processor._store_inbound_message.return_value = MagicMock(id=uuid4())
    
    validation_result = MagicMock(
        is_valid=False, 
        response_type=ResponseType.TEXT,
        validation_errors=["Empty content"]
    )
    response_processor.validator.validate_response.return_value = validation_result
    
    # Mock handle_invalid_response to return a result
    expected_result = ResponseProcessingResult(
        patient_id=patient_id,
        structured_response=MagicMock(),
        flow_actions=[],
        follow_up_message="Error"
    )
    response_processor.handlers.handle_invalid_response = AsyncMock(return_value=expected_result)
    
    # Execute
    result = await response_processor.process_inbound_message(inbound)
    
    # Verify
    assert result == expected_result
    response_processor.handlers.handle_invalid_response.assert_called_once()
