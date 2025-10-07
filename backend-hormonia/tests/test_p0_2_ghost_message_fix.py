"""
Test P0-2: Ghost Message Duplication Fix in Webhook Auto-Responses

Validates that _send_response() creates ONE message only and properly schedules it.

Test Coverage:
1. Single message creation (not duplicate)
2. Message persisted with PENDING status
3. WebSocket publish happens with the same message
4. schedule_existing_message() called with correct message_id
5. Status transition: PENDING → SCHEDULED
6. Transaction rollback on failures
7. Integration test with full webhook flow
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.services.webhook_processor import WebhookProcessor
from app.models.message import Message, MessageStatus, MessageDirection, MessageType
from app.models.patient import Patient


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    db.query = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    db.rollback = Mock()
    return db


@pytest.fixture
def mock_patient():
    """Mock patient for testing."""
    patient = Patient(
        id=uuid4(),
        name="Test Patient",
        phone="+5511987654321",
        email="test@example.com"
    )
    return patient


@pytest.fixture
def mock_message():
    """Mock message for testing."""
    message = Message(
        id=uuid4(),
        patient_id=uuid4(),
        direction=MessageDirection.OUTBOUND,
        type=MessageType.TEXT,
        content="Test response",
        status=MessageStatus.PENDING,
        message_metadata={}
    )
    return message


class TestP02GhostMessageFix:
    """Test suite for P0-2 ghost message duplication fix."""

    @pytest.mark.asyncio
    async def test_single_message_created(self, mock_db, mock_patient, mock_message):
        """
        TEST 1: Verify only ONE message is created

        Expected:
        - create_message() called exactly once
        - No duplicate message creation via schedule_message()
        """
        with patch('app.services.webhook_processor.MessageService') as mock_service_class, \
             patch('app.services.webhook_processor.get_message_scheduler') as mock_scheduler_getter, \
             patch('app.services.webhook_processor.websocket_events') as mock_ws:

            # Setup mocks
            mock_service = Mock()
            mock_service.create_message = Mock(return_value=mock_message)
            mock_service_class.return_value = mock_service

            mock_scheduler = AsyncMock()
            mock_scheduler.schedule_existing_message = AsyncMock(return_value=True)
            mock_scheduler_getter.return_value = mock_scheduler

            mock_ws.publish_message_event = AsyncMock()

            # Create processor
            processor = WebhookProcessor(db=mock_db)
            processor.message_service = mock_service

            # Call _send_response
            result = await processor._send_response(
                patient_id=mock_patient.id,
                content="Test response",
                metadata={"context": "test"}
            )

            # Assertions
            assert result is not None
            assert result.id == mock_message.id

            # Verify only ONE message created
            mock_service.create_message.assert_called_once()

            # Verify schedule_message NOT called (this was the bug)
            assert not hasattr(mock_service, 'schedule_message') or \
                   not mock_service.schedule_message.called

    @pytest.mark.asyncio
    async def test_message_starts_with_pending_status(self, mock_db, mock_patient):
        """
        TEST 2: Verify message created with PENDING status

        Expected:
        - MessageCreate called with status=MessageStatus.PENDING
        - Message persisted to database with PENDING status
        """
        with patch('app.services.webhook_processor.MessageService') as mock_service_class, \
             patch('app.services.webhook_processor.get_message_scheduler') as mock_scheduler_getter, \
             patch('app.services.webhook_processor.websocket_events') as mock_ws:

            # Setup mocks
            created_message = None

            def capture_create_message(message_data):
                nonlocal created_message
                created_message = Message(
                    id=uuid4(),
                    patient_id=message_data.patient_id,
                    direction=message_data.direction,
                    type=message_data.type,
                    content=message_data.content,
                    status=message_data.status or MessageStatus.PENDING,
                    message_metadata=message_data.message_metadata
                )
                return created_message

            mock_service = Mock()
            mock_service.create_message = Mock(side_effect=capture_create_message)
            mock_service_class.return_value = mock_service

            mock_scheduler = AsyncMock()
            mock_scheduler.schedule_existing_message = AsyncMock(return_value=True)
            mock_scheduler_getter.return_value = mock_scheduler

            mock_ws.publish_message_event = AsyncMock()

            # Create processor
            processor = WebhookProcessor(db=mock_db)
            processor.message_service = mock_service

            # Call _send_response
            await processor._send_response(
                patient_id=mock_patient.id,
                content="Test response",
                metadata={"context": "test"}
            )

            # Verify message created with PENDING status
            assert created_message is not None
            assert created_message.status == MessageStatus.PENDING

    @pytest.mark.asyncio
    async def test_websocket_publishes_same_message(self, mock_db, mock_patient, mock_message):
        """
        TEST 3: Verify WebSocket publishes the SAME message that gets scheduled

        Expected:
        - WebSocket event contains message_id of created message
        - No second message created for WebSocket
        """
        with patch('app.services.webhook_processor.MessageService') as mock_service_class, \
             patch('app.services.webhook_processor.get_message_scheduler') as mock_scheduler_getter, \
             patch('app.services.webhook_processor.websocket_events') as mock_ws:

            # Setup mocks
            mock_service = Mock()
            mock_service.create_message = Mock(return_value=mock_message)
            mock_service_class.return_value = mock_service

            mock_scheduler = AsyncMock()
            mock_scheduler.schedule_existing_message = AsyncMock(return_value=True)
            mock_scheduler_getter.return_value = mock_scheduler

            mock_ws.publish_message_event = AsyncMock()

            # Create processor
            processor = WebhookProcessor(db=mock_db)
            processor.message_service = mock_service

            # Call _send_response
            await processor._send_response(
                patient_id=mock_patient.id,
                content="Test response",
                metadata={"context": "test"}
            )

            # Verify WebSocket called with the same message
            mock_ws.publish_message_event.assert_called_once()
            call_kwargs = mock_ws.publish_message_event.call_args[1]
            assert call_kwargs['message_id'] == mock_message.id

    @pytest.mark.asyncio
    async def test_schedule_existing_message_called(self, mock_db, mock_patient, mock_message):
        """
        TEST 4: Verify schedule_existing_message() called with correct message_id

        Expected:
        - schedule_existing_message() called with message.id
        - Priority set to 'high' for auto-responses
        - Send time is ~1 second from now
        """
        with patch('app.services.webhook_processor.MessageService') as mock_service_class, \
             patch('app.services.webhook_processor.get_message_scheduler') as mock_scheduler_getter, \
             patch('app.services.webhook_processor.websocket_events') as mock_ws:

            # Setup mocks
            mock_service = Mock()
            mock_service.create_message = Mock(return_value=mock_message)
            mock_service_class.return_value = mock_service

            mock_scheduler = AsyncMock()
            mock_scheduler.schedule_existing_message = AsyncMock(return_value=True)
            mock_scheduler_getter.return_value = mock_scheduler

            mock_ws.publish_message_event = AsyncMock()

            # Create processor
            processor = WebhookProcessor(db=mock_db)
            processor.message_service = mock_service

            # Call _send_response
            await processor._send_response(
                patient_id=mock_patient.id,
                content="Test response",
                metadata={"context": "test"}
            )

            # Verify schedule_existing_message called with correct parameters
            mock_scheduler.schedule_existing_message.assert_called_once()
            call_kwargs = mock_scheduler.schedule_existing_message.call_args[1]

            assert call_kwargs['message_id'] == mock_message.id
            assert call_kwargs['priority'] == 'high'

            # Verify send_time is approximately 1 second from now
            send_time = call_kwargs['send_time']
            now = datetime.utcnow()
            time_diff = (send_time - now).total_seconds()
            assert 0 <= time_diff <= 2  # Allow small variance

    @pytest.mark.asyncio
    async def test_status_transition_pending_to_scheduled(self, mock_db, mock_patient):
        """
        TEST 5: Verify status transitions correctly: PENDING → SCHEDULED

        Expected:
        - Message created with PENDING status
        - After scheduling, status updated to SCHEDULED
        """
        with patch('app.services.webhook_processor.MessageService') as mock_service_class, \
             patch('app.services.webhook_processor.get_message_scheduler') as mock_scheduler_getter, \
             patch('app.services.webhook_processor.websocket_events') as mock_ws:

            # Create a real-ish message object that can be modified
            test_message = Message(
                id=uuid4(),
                patient_id=mock_patient.id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content="Test",
                status=MessageStatus.PENDING,
                message_metadata={}
            )

            async def mock_schedule(message_id, send_time, priority):
                # Simulate what the real scheduler does
                test_message.status = MessageStatus.SCHEDULED
                test_message.scheduled_for = send_time
                test_message.message_metadata['celery_task_id'] = 'task-123'
                return True

            mock_service = Mock()
            mock_service.create_message = Mock(return_value=test_message)
            mock_service_class.return_value = mock_service

            mock_scheduler = AsyncMock()
            mock_scheduler.schedule_existing_message = AsyncMock(side_effect=mock_schedule)
            mock_scheduler_getter.return_value = mock_scheduler

            mock_ws.publish_message_event = AsyncMock()

            # Create processor
            processor = WebhookProcessor(db=mock_db)
            processor.message_service = mock_service

            # Call _send_response
            result = await processor._send_response(
                patient_id=mock_patient.id,
                content="Test response",
                metadata={"context": "test"}
            )

            # Verify status transitioned
            assert result.status == MessageStatus.SCHEDULED
            assert result.message_metadata.get('celery_task_id') == 'task-123'

    @pytest.mark.asyncio
    async def test_rollback_on_failure(self, mock_db, mock_patient):
        """
        TEST 6: Verify transaction rollback on failures

        Expected:
        - If any step fails, db.rollback() is called
        - Exception is logged
        - None is returned
        """
        with patch('app.services.webhook_processor.MessageService') as mock_service_class, \
             patch('app.services.webhook_processor.websocket_events') as mock_ws:

            # Setup mocks to simulate failure
            mock_service = Mock()
            mock_service.create_message = Mock(side_effect=Exception("Database error"))
            mock_service_class.return_value = mock_service

            # Create processor
            processor = WebhookProcessor(db=mock_db)
            processor.message_service = mock_service

            # Call _send_response (should handle exception)
            result = await processor._send_response(
                patient_id=mock_patient.id,
                content="Test response",
                metadata={"context": "test"}
            )

            # Verify rollback called
            mock_db.rollback.assert_called_once()

            # Verify None returned on error
            assert result is None

    @pytest.mark.asyncio
    async def test_scheduling_failure_leaves_message_pending(self, mock_db, mock_patient, mock_message):
        """
        TEST 7: Verify message stays PENDING if scheduling fails

        Expected:
        - Message created successfully
        - Scheduling fails but doesn't crash
        - Message remains in PENDING state for retry
        """
        with patch('app.services.webhook_processor.MessageService') as mock_service_class, \
             patch('app.services.webhook_processor.get_message_scheduler') as mock_scheduler_getter, \
             patch('app.services.webhook_processor.websocket_events') as mock_ws:

            # Setup mocks
            mock_service = Mock()
            mock_service.create_message = Mock(return_value=mock_message)
            mock_service_class.return_value = mock_service

            # Scheduler fails
            mock_scheduler = AsyncMock()
            mock_scheduler.schedule_existing_message = AsyncMock(return_value=False)
            mock_scheduler_getter.return_value = mock_scheduler

            mock_ws.publish_message_event = AsyncMock()

            # Create processor
            processor = WebhookProcessor(db=mock_db)
            processor.message_service = mock_service

            # Call _send_response
            result = await processor._send_response(
                patient_id=mock_patient.id,
                content="Test response",
                metadata={"context": "test"}
            )

            # Verify message created but scheduling failed gracefully
            assert result is not None
            assert result.status == MessageStatus.PENDING  # Remains PENDING

            # Verify no rollback (partial success is OK)
            mock_db.rollback.assert_not_called()


class TestP02IntegrationWithWebhook:
    """Integration tests for the complete webhook flow."""

    @pytest.mark.asyncio
    async def test_full_flow_message_creation_and_scheduling(self, mock_db):
        """
        Integration Test: Complete webhook auto-response flow

        Verifies:
        1. Inbound message processed
        2. Single outbound message created
        3. WebSocket published
        4. Message scheduled for delivery
        5. No ghost messages created
        """
        with patch('app.services.webhook_processor.MessageService') as mock_service_class, \
             patch('app.services.webhook_processor.PatientService') as mock_patient_service_class, \
             patch('app.services.webhook_processor.FlowEngine') as mock_flow_engine_class, \
             patch('app.services.webhook_processor.EnhancedFlowEngine') as mock_enhanced_flow_class, \
             patch('app.services.webhook_processor.FlowStateRepository') as mock_flow_repo_class, \
             patch('app.services.webhook_processor.get_langchain_orchestrator') as mock_ai_client, \
             patch('app.services.webhook_processor.get_message_scheduler') as mock_scheduler_getter, \
             patch('app.services.webhook_processor.websocket_events') as mock_ws:

            # Setup patient
            patient = Patient(
                id=uuid4(),
                name="Integration Test Patient",
                phone="+5511987654321",
                email="integration@test.com"
            )

            # Setup messages
            inbound_message = Message(
                id=uuid4(),
                patient_id=patient.id,
                direction=MessageDirection.INBOUND,
                type=MessageType.TEXT,
                content="Hello",
                status=MessageStatus.READ,
                whatsapp_id="whatsapp-123"
            )

            outbound_message = Message(
                id=uuid4(),
                patient_id=patient.id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content="Hi! How can I help?",
                status=MessageStatus.PENDING,
                message_metadata={}
            )

            # Setup mocks
            mock_message_service = Mock()
            mock_message_service.process_inbound_message = Mock(return_value=inbound_message)
            mock_message_service.create_message = Mock(return_value=outbound_message)
            mock_service_class.return_value = mock_message_service

            mock_patient_service = Mock()
            mock_patient_service_class.return_value = mock_patient_service

            mock_flow_engine = Mock()
            mock_flow_engine_class.return_value = mock_flow_engine

            mock_enhanced_flow = AsyncMock()
            mock_enhanced_flow_class.return_value = mock_enhanced_flow

            mock_flow_repo = Mock()
            mock_flow_repo.get_active_flow = Mock(return_value=None)
            mock_flow_repo_class.return_value = mock_flow_repo

            mock_ai = AsyncMock()
            mock_ai.generate_contextual_response = AsyncMock(return_value="Hi! How can I help?")
            mock_ai_client.return_value = mock_ai

            mock_scheduler = AsyncMock()
            mock_scheduler.schedule_existing_message = AsyncMock(return_value=True)
            mock_scheduler_getter.return_value = mock_scheduler

            mock_ws.publish_message_event = AsyncMock()

            # Create processor
            processor = WebhookProcessor(db=mock_db)
            processor.message_service = mock_message_service
            processor.patient_service = mock_patient_service
            processor.flow_state_repo = mock_flow_repo
            processor.ai_client = mock_ai

            # Call _handle_general_chat (which calls _send_response)
            await processor._handle_general_chat(patient, inbound_message)

            # Verify flow
            mock_message_service.create_message.assert_called_once()
            mock_ws.publish_message_event.assert_called()
            mock_scheduler.schedule_existing_message.assert_called_once()

            # Verify only ONE outbound message created
            create_calls = mock_message_service.create_message.call_count
            assert create_calls == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
