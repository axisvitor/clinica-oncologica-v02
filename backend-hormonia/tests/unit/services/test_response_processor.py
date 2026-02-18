import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

from app.services.response_processor import (
    ResponseProcessor,
    InboundMessage,
    ResponseType,
    ResponseProcessingResult,
    InteractiveResponse,
)
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


@pytest.fixture
def response_processor_real_trigger(mock_db, mock_config):
    """ResponseProcessor instance with real sequential trigger logic."""
    with patch("app.services.response_processor.processor.get_platform_sync_service") as mock_sync, \
         patch("app.services.response_processor.processor.flow_event_broadcaster") as mock_broadcaster, \
         patch("app.services.response_processor.processor.get_conversational_quiz_service") as mock_quiz:
        mock_sync_service = AsyncMock()
        mock_sync_service.sync_patient_record_update = AsyncMock()
        mock_sync.return_value = mock_sync_service
        mock_broadcaster.broadcast_patient_interaction = AsyncMock()
        mock_quiz.return_value = AsyncMock()

        processor = ResponseProcessor(mock_db, mock_config)
        processor.flow_state_repo = MagicMock()
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
    trigger_call = response_processor._trigger_sequential_continuation.await_args
    assert trigger_call is not None
    assert trigger_call.kwargs["response_context"]["response_message_id"]

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


@pytest.mark.asyncio
async def test_handle_interactive_response_triggers_sequential_continuation(
    response_processor,
):
    patient_id = uuid4()
    flow_state = MagicMock()
    flow_state.step_data = {
        "current_flow_day": 3,
        "flow_kind": "daily_follow_up",
        "current_day_message_index": 1,
        "awaiting_response": True,
    }
    flow_state.id = uuid4()
    response_processor.flow_state_repo.get_active_flow.return_value = flow_state

    response_processor.validator.validate_interactive_response = AsyncMock(
        return_value=MagicMock(is_valid=True)
    )
    structured_response = MagicMock(
        medical_concerns=[],
        concern_level=MagicMock(value="low"),
        severity_score=0,
    )
    response_processor.extractor.extract_structured_data = AsyncMock(
        return_value=structured_response
    )
    response_processor.flow_helpers.determine_flow_actions = AsyncMock(return_value=[])
    response_processor.flow_helpers.generate_follow_up_message = AsyncMock(return_value=None)
    response_processor.flow_helpers.prepare_state_updates = AsyncMock(return_value=None)
    response_processor.flow_helpers.check_escalation_required = MagicMock(return_value=False)

    interactive_response = InteractiveResponse(
        patient_id=patient_id,
        response_value="Sim",
        response_type=ResponseType.BUTTON,
        metadata={},
    )

    result = await response_processor.handle_interactive_response(interactive_response)

    assert isinstance(result, ResponseProcessingResult)
    response_processor._trigger_sequential_continuation.assert_awaited_once()
    trigger_call = response_processor._trigger_sequential_continuation.await_args
    assert trigger_call is not None
    assert trigger_call.kwargs["response_context"]["response_message_id"]


def test_build_response_context_does_not_use_pending_prompt_as_received(
    response_processor_real_trigger,
):
    pending_prompt_message_id = str(uuid4())
    flow_state = MagicMock()
    flow_state.id = uuid4()
    flow_state.patient_id = uuid4()
    flow_state.step_data = {
        "current_flow_day": 3,
        "flow_kind": "daily_follow_up",
        "current_day_message_index": 1,
        "awaiting_response": True,
        "pending_response_context": {
            "prompt_message_id": pending_prompt_message_id,
        },
    }
    inbound = InboundMessage(
        patient_phone="",
        content="Sim",
        whatsapp_id="",
        metadata={
            "flow_context": {
                "flow_day": 3,
                "flow_kind": "daily_follow_up",
                "message_index": 1,
                "awaiting_response": True,
            }
        },
    )

    context = response_processor_real_trigger._build_response_context(
        flow_state=flow_state,
        message=None,
        inbound_message=inbound,
    )

    assert "prompt_message_id" not in context


def test_build_response_context_generates_deterministic_response_message_id(
    response_processor_real_trigger,
):
    flow_state = MagicMock()
    flow_state.id = uuid4()
    flow_state.patient_id = uuid4()
    flow_state.step_data = {
        "current_flow_day": 3,
        "flow_kind": "daily_follow_up",
        "current_day_message_index": 1,
        "awaiting_response": True,
    }
    inbound = InboundMessage(
        patient_phone="",
        content="Sim",
        whatsapp_id="",
        metadata={
            "timestamp": "1700000000",
            "flow_context": {
                "flow_day": 3,
                "flow_kind": "daily_follow_up",
                "message_index": 1,
                "awaiting_response": True,
            },
        },
    )

    context_first = response_processor_real_trigger._build_response_context(
        flow_state=flow_state,
        message=None,
        inbound_message=inbound,
    )
    context_second = response_processor_real_trigger._build_response_context(
        flow_state=flow_state,
        message=None,
        inbound_message=inbound,
    )

    assert context_first["response_message_id"] == context_second["response_message_id"]
    assert context_first["response_message_id"].startswith("interactive-")


@pytest.mark.asyncio
async def test_trigger_sequential_continuation_skips_when_not_awaiting(
    response_processor_real_trigger,
):
    flow_state = MagicMock()
    flow_state.step_data = {
        "current_flow_day": 3,
        "flow_kind": "daily_follow_up",
        "current_day_message_index": 1,
        "awaiting_response": False,
    }
    response_processor_real_trigger._get_sequential_handler = MagicMock()

    await response_processor_real_trigger._trigger_sequential_continuation(
        uuid4(),
        flow_state,
        response_context={
            "flow_day": 3,
            "flow_kind": "daily_follow_up",
            "message_index": 1,
            "awaiting_response": False,
            "prompt_message_id": str(uuid4()),
            "response_message_id": str(uuid4()),
        },
    )

    response_processor_real_trigger._get_sequential_handler.assert_not_called()


def test_evaluate_sequential_gate_blocks_when_required_identifier_missing(
    response_processor_real_trigger,
):
    step_data = {
        "current_flow_day": 3,
        "flow_kind": "daily_follow_up",
        "current_day_message_index": None,
        "awaiting_response": True,
    }
    gate_allowed, gate_reason, _ = response_processor_real_trigger._evaluate_sequential_gate(
        step_data,
        response_context={
            "flow_day": 3,
            "flow_kind": "daily_follow_up",
            "message_index": 1,
            "awaiting_response": True,
            "response_message_id": str(uuid4()),
        },
    )

    assert gate_allowed is False
    assert gate_reason == "missing_message_index"


@pytest.mark.asyncio
async def test_trigger_sequential_continuation_skips_on_context_mismatch(
    response_processor_real_trigger,
):
    flow_state = MagicMock()
    flow_state.step_data = {
        "current_flow_day": 3,
        "flow_kind": "daily_follow_up",
        "current_day_message_index": 1,
        "awaiting_response": True,
    }
    response_processor_real_trigger._get_sequential_handler = MagicMock()

    await response_processor_real_trigger._trigger_sequential_continuation(
        uuid4(),
        flow_state,
        response_context={
            "flow_day": 2,
            "flow_kind": "daily_follow_up",
            "message_index": 1,
            "awaiting_response": True,
            "prompt_message_id": str(uuid4()),
            "response_message_id": str(uuid4()),
        },
    )

    response_processor_real_trigger._get_sequential_handler.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_sequential_continuation_skips_duplicate_response_message_id(
    response_processor_real_trigger,
):
    duplicated_response_message_id = str(uuid4())
    flow_state = MagicMock()
    flow_state.step_data = {
        "current_flow_day": 3,
        "flow_kind": "daily_follow_up",
        "current_day_message_index": 1,
        "awaiting_response": True,
        "last_processed_response_message_id": duplicated_response_message_id,
    }
    response_processor_real_trigger._get_sequential_handler = MagicMock()

    await response_processor_real_trigger._trigger_sequential_continuation(
        uuid4(),
        flow_state,
        response_context={
            "flow_day": 3,
            "flow_kind": "daily_follow_up",
            "message_index": 1,
            "awaiting_response": True,
            "prompt_message_id": str(uuid4()),
            "response_message_id": duplicated_response_message_id,
        },
    )

    response_processor_real_trigger._get_sequential_handler.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_sequential_continuation_calls_handler_with_valid_context(
    response_processor_real_trigger,
):
    flow_state = MagicMock()
    flow_state.step_data = {
        "current_flow_day": 3,
        "flow_kind": "daily_follow_up",
        "current_day_message_index": 1,
        "awaiting_response": True,
    }
    handler = MagicMock()
    handler.handle_response_and_continue = AsyncMock(return_value={"status": "day_complete"})
    response_processor_real_trigger._get_sequential_handler = MagicMock(return_value=handler)

    response_message_id = str(uuid4())
    await response_processor_real_trigger._trigger_sequential_continuation(
        uuid4(),
        flow_state,
        response_context={
            "flow_day": 3,
            "flow_kind": "daily_follow_up",
            "message_index": 1,
            "awaiting_response": True,
            "prompt_message_id": str(uuid4()),
            "response_message_id": response_message_id,
        },
    )

    handler.handle_response_and_continue.assert_called_once()
    assert flow_state.step_data["last_processed_response_message_id"] == response_message_id


@pytest.mark.asyncio
async def test_trigger_sequential_continuation_does_not_mark_processed_when_graph_blocks(
    response_processor_real_trigger,
):
    response_message_id = str(uuid4())
    prompt_message_id = str(uuid4())
    flow_state = MagicMock()
    flow_state.step_data = {
        "current_flow_day": 3,
        "flow_kind": "daily_follow_up",
        "current_day_message_index": 1,
        "awaiting_response": True,
        "pending_response_context": {
            "flow_day": 3,
            "flow_kind": "daily_follow_up",
            "message_index": 1,
            "prompt_message_id": prompt_message_id,
        },
    }
    handler = MagicMock()
    handler.handle_response_and_continue = AsyncMock(
        return_value={"status": "waiting", "reason": "context_mismatch"}
    )
    response_processor_real_trigger._get_sequential_handler = MagicMock(return_value=handler)

    await response_processor_real_trigger._trigger_sequential_continuation(
        uuid4(),
        flow_state,
        response_context={
            "flow_day": 3,
            "flow_kind": "daily_follow_up",
            "message_index": 1,
            "awaiting_response": True,
            "prompt_message_id": prompt_message_id,
            "response_message_id": response_message_id,
        },
    )

    handler.handle_response_and_continue.assert_called_once()
    assert "last_processed_response_message_id" not in flow_state.step_data
