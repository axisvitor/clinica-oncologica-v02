"""
Unit tests for MessageScheduler service.

Tests the core message scheduling functionality including:
- Message scheduling with different priorities
- Batch scheduling
- Schedule cancellation
- Recurring message scheduling
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4

from app.services.message_scheduler import MessageScheduler
from app.models.message import Message, MessageStatus, MessagePriority
from app.models.patient import Patient


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    db.query = Mock()
    return db


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis = Mock()
    redis.setex = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.delete = AsyncMock()
    return redis


@pytest.fixture
def mock_celery():
    """Mock Celery task."""
    task = Mock()
    task.apply_async = Mock()
    return task


@pytest.fixture
def scheduler(mock_db, mock_redis):
    """Create MessageScheduler instance with mocked dependencies."""
    return MessageScheduler(db=mock_db, redis_client=mock_redis)


@pytest.fixture
def sample_patient(mock_db):
    """Create a sample patient for testing."""
    patient = Patient(
        id=uuid4(),
        name="Test Patient",
        phone="+5511987654321",
        email="test@example.com"
    )
    mock_db.query.return_value.filter.return_value.first.return_value = patient
    return patient


class TestMessageScheduling:
    """Test message scheduling functionality."""

    def test_schedule_message_creates_message_record(self, scheduler, mock_db, sample_patient):
        """Test that scheduling a message creates a database record."""
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        
        message = scheduler.schedule_message(
            patient_id=sample_patient.id,
            content="Test message",
            scheduled_time=scheduled_time,
            priority=MessagePriority.NORMAL
        )
        
        # Verify message was added to database
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        
        # Verify message properties
        assert message.content == "Test message"
        assert message.status == MessageStatus.SCHEDULED
        assert message.priority == MessagePriority.NORMAL

    def test_schedule_urgent_message_has_high_priority(self, scheduler, mock_db, sample_patient):
        """Test that urgent messages are created with URGENT priority."""
        scheduled_time = datetime.utcnow() + timedelta(minutes=5)
        
        message = scheduler.schedule_message(
            patient_id=sample_patient.id,
            content="Urgent message",
            scheduled_time=scheduled_time,
            priority=MessagePriority.URGENT
        )
        
        assert message.priority == MessagePriority.URGENT

    def test_schedule_message_in_past_raises_error(self, scheduler, sample_patient):
        """Test that scheduling a message in the past raises ValueError."""
        past_time = datetime.utcnow() - timedelta(hours=1)
        
        with pytest.raises(ValueError, match="Cannot schedule message in the past"):
            scheduler.schedule_message(
                patient_id=sample_patient.id,
                content="Test message",
                scheduled_time=past_time
            )

    def test_schedule_message_with_invalid_patient_raises_error(self, scheduler, mock_db):
        """Test that scheduling with invalid patient ID raises error."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(ValueError, match="Patient not found"):
            scheduler.schedule_message(
                patient_id=uuid4(),
                content="Test message",
                scheduled_time=datetime.utcnow() + timedelta(hours=1)
            )


class TestBatchScheduling:
    """Test batch message scheduling."""

    def test_schedule_batch_creates_multiple_messages(self, scheduler, mock_db, sample_patient):
        """Test that batch scheduling creates multiple message records."""
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        patient_ids = [uuid4() for _ in range(5)]
        
        # Mock patient lookup to return valid patients
        mock_db.query.return_value.filter.return_value.first.return_value = sample_patient
        
        messages = scheduler.schedule_batch(
            patient_ids=patient_ids,
            content="Batch message",
            scheduled_time=scheduled_time
        )
        
        assert len(messages) == 5
        assert mock_db.add.call_count == 5
        assert mock_db.commit.call_count == 1  # Single commit for batch

    def test_schedule_batch_with_empty_list_returns_empty(self, scheduler):
        """Test that batch scheduling with empty list returns empty list."""
        messages = scheduler.schedule_batch(
            patient_ids=[],
            content="Test",
            scheduled_time=datetime.utcnow() + timedelta(hours=1)
        )
        
        assert messages == []


class TestScheduleCancellation:
    """Test message schedule cancellation."""

    def test_cancel_scheduled_message_updates_status(self, scheduler, mock_db):
        """Test that canceling a scheduled message updates its status."""
        message_id = uuid4()
        message = Message(
            id=message_id,
            status=MessageStatus.SCHEDULED,
            content="Test"
        )
        mock_db.query.return_value.filter.return_value.first.return_value = message
        
        result = scheduler.cancel_scheduled_message(message_id)
        
        assert result is True
        assert message.status == MessageStatus.CANCELLED
        mock_db.commit.assert_called_once()

    def test_cancel_already_sent_message_returns_false(self, scheduler, mock_db):
        """Test that canceling an already sent message returns False."""
        message_id = uuid4()
        message = Message(
            id=message_id,
            status=MessageStatus.SENT,
            content="Test"
        )
        mock_db.query.return_value.filter.return_value.first.return_value = message
        
        result = scheduler.cancel_scheduled_message(message_id)
        
        assert result is False
        assert message.status == MessageStatus.SENT  # Status unchanged

    def test_cancel_nonexistent_message_returns_false(self, scheduler, mock_db):
        """Test that canceling a nonexistent message returns False."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = scheduler.cancel_scheduled_message(uuid4())
        
        assert result is False


class TestRecurringMessages:
    """Test recurring message scheduling."""

    def test_schedule_recurring_message_creates_series(self, scheduler, mock_db, sample_patient):
        """Test that recurring messages create a series of scheduled messages."""
        start_time = datetime.utcnow() + timedelta(hours=1)
        
        messages = scheduler.schedule_recurring(
            patient_id=sample_patient.id,
            content="Daily reminder",
            start_time=start_time,
            interval_days=1,
            occurrences=7  # Weekly series
        )
        
        assert len(messages) == 7
        
        # Verify messages are scheduled at correct intervals
        for i, message in enumerate(messages):
            expected_time = start_time + timedelta(days=i)
            assert message.scheduled_time.date() == expected_time.date()

    def test_schedule_recurring_with_zero_occurrences_raises_error(self, scheduler, sample_patient):
        """Test that recurring schedule with 0 occurrences raises error."""
        with pytest.raises(ValueError, match="Occurrences must be at least 1"):
            scheduler.schedule_recurring(
                patient_id=sample_patient.id,
                content="Test",
                start_time=datetime.utcnow() + timedelta(hours=1),
                interval_days=1,
                occurrences=0
            )


class TestMessageRetrieval:
    """Test message retrieval and querying."""

    def test_get_scheduled_messages_for_patient(self, scheduler, mock_db, sample_patient):
        """Test retrieving scheduled messages for a specific patient."""
        messages = [
            Message(id=uuid4(), patient_id=sample_patient.id, status=MessageStatus.SCHEDULED),
            Message(id=uuid4(), patient_id=sample_patient.id, status=MessageStatus.SCHEDULED),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = messages
        
        result = scheduler.get_scheduled_messages(patient_id=sample_patient.id)
        
        assert len(result) == 2
        assert all(msg.status == MessageStatus.SCHEDULED for msg in result)

    def test_get_messages_due_for_sending(self, scheduler, mock_db):
        """Test retrieving messages that are due to be sent."""
        now = datetime.utcnow()
        due_messages = [
            Message(id=uuid4(), scheduled_time=now - timedelta(minutes=5)),
            Message(id=uuid4(), scheduled_time=now - timedelta(minutes=1)),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = due_messages
        
        result = scheduler.get_due_messages()
        
        assert len(result) == 2

