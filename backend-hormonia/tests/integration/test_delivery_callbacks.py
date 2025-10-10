"""
Integration tests for delivery status callbacks and retry logic.

Tests the critical P1 fix that prevents flows from getting stuck in "waiting" state
when WhatsApp message delivery fails.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from app.models.message import Message, MessageStatus, MessageDirection, MessageType, DeliveryStatus
from app.models.patient import Patient
from app.models.flow import PatientFlowState
from app.services.message_scheduler import MessageScheduler, MessageSchedulerConfig
from app.repositories.message import MessageRepository
from app.repositories.patient import PatientRepository
from app.repositories.flow import FlowStateRepository


@pytest.fixture
def test_patient(db: Session) -> Patient:
    """Create a test patient."""
    patient = Patient(
        name="Test Patient",
        phone="+5511999999999",
        cpf="12345678901",
        treatment_type="hormone_therapy"
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@pytest.fixture
def test_flow_state(db: Session, test_patient: Patient) -> PatientFlowState:
    """Create a test flow state."""
    # Create a minimal flow kind and template version for testing
    from app.models.flow import FlowKind, FlowTemplateVersion

    flow_kind = FlowKind(
        flow_type="test_flow",
        name="Test Flow",
        description="Test flow for integration tests"
    )
    db.add(flow_kind)
    db.flush()

    template_version = FlowTemplateVersion(
        kind_id=flow_kind.id,
        version=1,
        is_current=True,
        template_data={"steps": []}
    )
    db.add(template_version)
    db.flush()

    flow_state = PatientFlowState(
        patient_id=test_patient.id,
        template_version_id=template_version.id,
        current_step=0,
        started_at=datetime.utcnow(),
        state_data={}
    )
    db.add(flow_state)
    db.commit()
    db.refresh(flow_state)
    return flow_state


@pytest.fixture
def test_message(db: Session, test_patient: Patient) -> Message:
    """Create a test message."""
    message = Message(
        patient_id=test_patient.id,
        direction=MessageDirection.OUTBOUND,
        type=MessageType.TEXT,
        content="Test message",
        status=MessageStatus.SENDING,
        delivery_status=DeliveryStatus.SENDING,
        message_metadata={
            "flow_context": {
                "flow_day": 1,
                "flow_type": "test_flow"
            }
        }
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@pytest.fixture
def message_scheduler(db: Session) -> MessageScheduler:
    """Create a MessageScheduler instance."""
    config = MessageSchedulerConfig()
    return MessageScheduler(db, config)


@pytest.mark.asyncio
async def test_on_delivery_failure_schedules_retry(
    db: Session,
    message_scheduler: MessageScheduler,
    test_message: Message
):
    """Test that delivery failure schedules a retry with exponential backoff."""
    # Mock Celery task scheduling
    with patch('app.services.message_scheduler.send_flow_message') as mock_task:
        mock_result = Mock()
        mock_result.id = "task_123"
        mock_task.apply_async.return_value = mock_result

        # Call on_delivery_failure
        result = await message_scheduler.on_delivery_failure(
            message_id=test_message.id,
            failure_reason="WhatsApp API error",
            whatsapp_error={"code": 500, "message": "Server error"}
        )

        # Verify result
        assert result["status"] == "retry_scheduled"
        assert result["retry_count"] == 1
        assert "next_retry_at" in result

        # Verify message was updated
        db.refresh(test_message)
        assert test_message.delivery_status == DeliveryStatus.FAILED
        assert test_message.status == MessageStatus.FAILED
        assert test_message.retry_count == 1
        assert test_message.failure_reason == "WhatsApp API error"
        assert test_message.next_retry_at is not None
        assert "whatsapp_error" in test_message.message_metadata

        # Verify retry task was scheduled
        mock_task.apply_async.assert_called_once()


@pytest.mark.asyncio
async def test_on_delivery_failure_exponential_backoff(
    db: Session,
    message_scheduler: MessageScheduler,
    test_message: Message
):
    """Test that retry delays follow exponential backoff."""
    with patch('app.services.message_scheduler.send_flow_message') as mock_task:
        mock_result = Mock()
        mock_result.id = "task_123"
        mock_task.apply_async.return_value = mock_result

        # First retry
        result1 = await message_scheduler.on_delivery_failure(
            message_id=test_message.id,
            failure_reason="Failure 1"
        )
        db.refresh(test_message)
        first_retry_time = test_message.next_retry_at

        # Second retry
        result2 = await message_scheduler.on_delivery_failure(
            message_id=test_message.id,
            failure_reason="Failure 2"
        )
        db.refresh(test_message)
        second_retry_time = test_message.next_retry_at

        # Verify exponential backoff
        # First retry: 5 minutes (base delay)
        # Second retry: 10 minutes (5 * 2^1)
        assert result1["retry_count"] == 1
        assert result2["retry_count"] == 2

        # Second retry should be scheduled later than first
        assert second_retry_time > first_retry_time


@pytest.mark.asyncio
async def test_on_delivery_failure_max_retries_updates_flow_state(
    db: Session,
    message_scheduler: MessageScheduler,
    test_message: Message,
    test_flow_state: PatientFlowState
):
    """Test that max retries exceeded updates flow state to prevent stuck flows."""
    # Set retry count to max - 1
    test_message.retry_count = message_scheduler.config.MAX_DELIVERY_RETRIES
    db.commit()

    # Mock Celery task scheduling (won't be called at max retries)
    with patch('app.services.message_scheduler.send_flow_message'):
        # Call on_delivery_failure (should trigger permanent failure)
        result = await message_scheduler.on_delivery_failure(
            message_id=test_message.id,
            failure_reason="Final failure"
        )

        # Verify permanent failure status
        assert result["status"] == "permanent_failure"
        assert result["flow_notified"] is True

        # Verify message was updated
        db.refresh(test_message)
        assert test_message.delivery_status == DeliveryStatus.FAILED
        assert test_message.next_retry_at is None

        # Verify flow state was updated
        db.refresh(test_flow_state)
        assert "delivery_failures" in test_flow_state.state_data
        assert len(test_flow_state.state_data["delivery_failures"]) == 1
        assert test_flow_state.state_data["skip_waiting_for_message"] == str(test_message.id)
        assert "last_delivery_failure" in test_flow_state.state_data


@pytest.mark.asyncio
async def test_on_delivery_failure_without_flow_context(
    db: Session,
    message_scheduler: MessageScheduler,
    test_patient: Patient
):
    """Test delivery failure handling when message has no flow context."""
    # Create message without flow context
    message = Message(
        patient_id=test_patient.id,
        direction=MessageDirection.OUTBOUND,
        type=MessageType.TEXT,
        content="Test message",
        status=MessageStatus.SENDING,
        delivery_status=DeliveryStatus.SENDING,
        retry_count=3,  # Set to max retries
        message_metadata={}  # No flow_context
    )
    db.add(message)
    db.commit()

    # Call on_delivery_failure
    result = await message_scheduler.on_delivery_failure(
        message_id=message.id,
        failure_reason="Final failure"
    )

    # Should still handle failure gracefully
    assert result["status"] == "permanent_failure"

    # Message should be marked as failed
    db.refresh(message)
    assert message.delivery_status == DeliveryStatus.FAILED


@pytest.mark.asyncio
async def test_calculate_retry_delay(message_scheduler: MessageScheduler):
    """Test retry delay calculation."""
    # First retry: 5 minutes (5 * 2^0)
    delay_0 = message_scheduler._calculate_retry_delay(0)
    assert delay_0 == timedelta(minutes=5)

    # Second retry: 10 minutes (5 * 2^1)
    delay_1 = message_scheduler._calculate_retry_delay(1)
    assert delay_1 == timedelta(minutes=10)

    # Third retry: 20 minutes (5 * 2^2)
    delay_2 = message_scheduler._calculate_retry_delay(2)
    assert delay_2 == timedelta(minutes=20)

    # Very high retry count should be capped at 2 hours
    delay_high = message_scheduler._calculate_retry_delay(10)
    assert delay_high == timedelta(minutes=120)


@pytest.mark.asyncio
async def test_on_delivery_failure_message_not_found(
    db: Session,
    message_scheduler: MessageScheduler
):
    """Test delivery failure handling when message doesn't exist."""
    non_existent_id = uuid4()

    result = await message_scheduler.on_delivery_failure(
        message_id=non_existent_id,
        failure_reason="Test failure"
    )

    assert result["status"] == "error"
    assert result["message"] == "Message not found"
    assert result["message_id"] == str(non_existent_id)


@pytest.mark.asyncio
async def test_retry_preserves_message_content(
    db: Session,
    message_scheduler: MessageScheduler,
    test_message: Message
):
    """Test that retry preserves original message content and metadata."""
    original_content = test_message.content
    original_metadata = dict(test_message.message_metadata)

    with patch('app.services.message_scheduler.send_flow_message') as mock_task:
        mock_result = Mock()
        mock_result.id = "task_123"
        mock_task.apply_async.return_value = mock_result

        # Trigger retry
        await message_scheduler.on_delivery_failure(
            message_id=test_message.id,
            failure_reason="Temporary failure"
        )

        # Verify task was called with correct message data
        call_args = mock_task.apply_async.call_args
        message_data = call_args[1]['args'][1]

        assert message_data["content"] == original_content
        assert message_data["is_retry"] is True
        assert message_data["retry_count"] == 1


@pytest.mark.asyncio
async def test_concurrent_delivery_failures(
    db: Session,
    message_scheduler: MessageScheduler,
    test_patient: Patient
):
    """Test handling concurrent delivery failures for multiple messages."""
    # Create multiple messages
    messages = []
    for i in range(3):
        msg = Message(
            patient_id=test_patient.id,
            direction=MessageDirection.OUTBOUND,
            type=MessageType.TEXT,
            content=f"Test message {i}",
            status=MessageStatus.SENDING,
            delivery_status=DeliveryStatus.SENDING,
            message_metadata={"flow_context": {"flow_day": i}}
        )
        db.add(msg)
        messages.append(msg)
    db.commit()

    with patch('app.services.message_scheduler.send_flow_message') as mock_task:
        mock_result = Mock()
        mock_result.id = "task_123"
        mock_task.apply_async.return_value = mock_result

        # Trigger failures concurrently
        tasks = [
            message_scheduler.on_delivery_failure(
                message_id=msg.id,
                failure_reason=f"Failure {i}"
            )
            for i, msg in enumerate(messages)
        ]

        results = await asyncio.gather(*tasks)

        # Verify all failures were handled
        assert len(results) == 3
        assert all(r["status"] == "retry_scheduled" for r in results)

        # Verify all messages were updated
        for msg in messages:
            db.refresh(msg)
            assert msg.retry_count == 1
            assert msg.delivery_status == DeliveryStatus.FAILED


@pytest.mark.asyncio
async def test_flow_state_tracks_multiple_failures(
    db: Session,
    message_scheduler: MessageScheduler,
    test_patient: Patient,
    test_flow_state: PatientFlowState
):
    """Test that flow state tracks multiple delivery failures."""
    # Create multiple messages at max retries
    messages = []
    for i in range(3):
        msg = Message(
            patient_id=test_patient.id,
            direction=MessageDirection.OUTBOUND,
            type=MessageType.TEXT,
            content=f"Test message {i}",
            status=MessageStatus.SENDING,
            delivery_status=DeliveryStatus.SENDING,
            retry_count=3,  # Max retries
            message_metadata={"flow_context": {"flow_day": i}}
        )
        db.add(msg)
        messages.append(msg)
    db.commit()

    # Trigger permanent failures
    for msg in messages:
        await message_scheduler.on_delivery_failure(
            message_id=msg.id,
            failure_reason=f"Permanent failure for message {msg.id}"
        )

    # Verify flow state tracks all failures
    db.refresh(test_flow_state)
    assert "delivery_failures" in test_flow_state.state_data
    assert len(test_flow_state.state_data["delivery_failures"]) == 3

    # Verify each failure is tracked
    for i, failure in enumerate(test_flow_state.state_data["delivery_failures"]):
        assert "message_id" in failure
        assert "failure_timestamp" in failure
        assert "failure_reason" in failure
        assert failure["retry_count"] == 3
