import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

from app.services.unified_whatsapp_service import UnifiedWhatsAppService
from app.models.message import Message, MessageStatus, MessageType
from app.models.patient import Patient
from app.integrations.whatsapp.services.message_service import MessageResponse, MessageStatus as WhatsAppMessageStatus

from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive
@pytest.fixture
def mock_db():
    mock = AsyncMock()
    # Configure execute to return a MagicMock (the Result object)
    mock.execute.return_value = MagicMock()
    return mock

@pytest.fixture
def mock_queue_service():
    service = AsyncMock()
    service.send_message.return_value = MessageResponse(
        id="msg-123",
        status=WhatsAppMessageStatus.PENDING,
        message="Queued",
        timestamp=now_sao_paulo_naive()
    )
    return service

@pytest.fixture
def service(mock_db, mock_queue_service):
    # Patch internal methods to avoid real DB/Redis calls
    # LGPD: Create mock patient since Patient no longer has phone column
    mock_patient = MagicMock(spec=Patient)
    mock_patient.phone_decrypted = "5511999999999"

    # Use AsyncMock for async method _ensure_patient_loaded
    async_mock_ensure = AsyncMock(return_value=mock_patient)

    with patch("app.services.unified_whatsapp_service.UnifiedWhatsAppService._get_queue_service", return_value=mock_queue_service), \
         patch.object(UnifiedWhatsAppService, "_ensure_patient_loaded", async_mock_ensure):
        svc = UnifiedWhatsAppService(mock_db, redis_url="redis://mock")
        yield svc

@pytest.mark.asyncio
async def test_send_message_enqueues(service, mock_queue_service):
    message = Message(
        id=uuid4(),
        content="Hello",
        type=MessageType.TEXT,
        patient_id=uuid4(),
        message_metadata={}
    )
    
    success = await service.send_message(message)
    
    assert success is True
    mock_queue_service.send_message.assert_called_once()
    
    # Verify domain_message_id is injected
    call_args = mock_queue_service.send_message.call_args[0][0]
    assert call_args.message_data['domain_message_id'] == str(message.id)
    assert call_args.message_data['requires_queue'] is True

@pytest.mark.asyncio
async def test_send_quiz_message_enqueues(service, mock_queue_service):
    message = Message(
        id=uuid4(),
        content="Quiz Link",
        type=MessageType.MONTHLY_QUIZ_LINK,
        patient_id=uuid4(),
        message_metadata={"link_url": "http://quiz.com"}
    )
    
    success = await service.send_message(message)
    
    assert success is True
    mock_queue_service.send_message.assert_called_once()
    
    # Verify type mapping
    call_args = mock_queue_service.send_message.call_args[0][0]
    assert call_args.message_type.value == "text"

@pytest.mark.asyncio
async def test_status_handler_integration(mock_db):
    from app.services.message_status_handler import MessageStatusHandler
    
    handler = MessageStatusHandler(mock_db)
    message_id = uuid4()
    
    # Mock DB query
    mock_msg = Message(id=message_id, status=MessageStatus.PENDING)
    mock_db.execute.return_value.scalar_one_or_none.return_value = mock_msg
    
    await handler.handle_status_update(
        domain_message_id=message_id,
        new_status=MessageStatus.DELIVERED
    )
    
    assert mock_msg.status == MessageStatus.DELIVERED
    assert mock_msg.delivered_at is not None
    assert mock_db.commit.called