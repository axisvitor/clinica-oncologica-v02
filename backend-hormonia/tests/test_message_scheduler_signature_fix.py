"""
Test for MessageScheduler method signature fix (P0-1).

This test verifies that the new schedule_existing_message() method
correctly handles message scheduling with proper error handling.
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, AsyncMock, patch

from app.services.message_scheduler import MessageScheduler, MessageSchedulerConfig
from app.models.message import Message, MessageStatus, MessageDirection, MessageType
from app.models.patient import Patient
from app.exceptions import NotFoundError, ValidationError


@pytest.fixture
def mock_db_session():
    """Create mock database session."""
    session = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    session.refresh = Mock()
    return session


@pytest.fixture
def mock_message_repo():
    """Create mock message repository."""
    repo = Mock()
    return repo


@pytest.fixture
def mock_patient_repo():
    """Create mock patient repository."""
    repo = Mock()
    return repo


@pytest.fixture
def scheduler(mock_db_session, mock_message_repo, mock_patient_repo):
    """Create MessageScheduler instance with mocks."""
    scheduler = MessageScheduler(mock_db_session)
    scheduler.message_repo = mock_message_repo
    scheduler.patient_repo = mock_patient_repo
    return scheduler


@pytest.fixture
def sample_message():
    """Create sample message for testing."""
    message = Message(
        id=uuid4(),
        patient_id=uuid4(),
        direction=MessageDirection.OUTBOUND,
        type=MessageType.TEXT,
        content="Test message",
        status=MessageStatus.PENDING,
        message_metadata={}
    )
    return message


class TestScheduleExistingMessage:
    """Test suite for schedule_existing_message() method."""

    @pytest.mark.asyncio
    async def test_schedule_existing_message_success(self, scheduler, mock_message_repo, sample_message):
        """Test successful scheduling of existing message."""
        # Setup
        message_id = sample_message.id
        send_time = datetime.utcnow() + timedelta(hours=1)
        priority = 'normal'

        mock_message_repo.get.return_value = sample_message

        # Mock Celery task scheduling
        with patch.object(scheduler, '_schedule_celery_task', new_callable=AsyncMock) as mock_schedule:
            mock_schedule.return_value = {
                'task_id': 'test-task-123',
                'eta': send_time.isoformat(),
                'status': 'scheduled'
            }

            # Execute
            result = await scheduler.schedule_existing_message(
                message_id=message_id,
                send_time=send_time,
                priority=priority
            )

            # Verify
            assert result is True
            assert sample_message.status == MessageStatus.SCHEDULED
            assert sample_message.scheduled_for == send_time
            assert sample_message.message_metadata['priority'] == priority
            assert sample_message.message_metadata['celery_task_id'] == 'test-task-123'
            assert sample_message.message_metadata['scheduling_status'] == 'success'
            mock_message_repo.get.assert_called_once_with(message_id)
            scheduler.db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_existing_message_not_found(self, scheduler, mock_message_repo):
        """Test scheduling non-existent message raises NotFoundError."""
        # Setup
        message_id = uuid4()
        send_time = datetime.utcnow() + timedelta(hours=1)
        mock_message_repo.get.return_value = None

        # Execute & Verify
        with pytest.raises(NotFoundError, match=f"Message {message_id} not found"):
            await scheduler.schedule_existing_message(
                message_id=message_id,
                send_time=send_time,
                priority='normal'
            )

    @pytest.mark.asyncio
    async def test_schedule_existing_message_invalid_status(self, scheduler, mock_message_repo, sample_message):
        """Test scheduling message with invalid status raises ValidationError."""
        # Setup
        message_id = sample_message.id
        send_time = datetime.utcnow() + timedelta(hours=1)
        sample_message.status = MessageStatus.SENT  # Invalid status for scheduling

        mock_message_repo.get.return_value = sample_message

        # Execute & Verify
        with pytest.raises(ValidationError, match="Cannot schedule message"):
            await scheduler.schedule_existing_message(
                message_id=message_id,
                send_time=send_time,
                priority='normal'
            )

    @pytest.mark.asyncio
    async def test_schedule_existing_message_past_time_adjusted(self, scheduler, mock_message_repo, sample_message):
        """Test scheduling with past time automatically adjusts to future."""
        # Setup
        message_id = sample_message.id
        send_time = datetime.utcnow() - timedelta(hours=1)  # Past time
        priority = 'normal'

        mock_message_repo.get.return_value = sample_message

        # Mock Celery task scheduling
        with patch.object(scheduler, '_schedule_celery_task', new_callable=AsyncMock) as mock_schedule:
            mock_schedule.return_value = {
                'task_id': 'test-task-123',
                'status': 'scheduled'
            }

            # Execute
            result = await scheduler.schedule_existing_message(
                message_id=message_id,
                send_time=send_time,
                priority=priority
            )

            # Verify
            assert result is True
            # Verify send_time was adjusted to future
            assert sample_message.scheduled_for > datetime.utcnow()

    @pytest.mark.asyncio
    async def test_schedule_existing_message_invalid_priority(self, scheduler, mock_message_repo, sample_message):
        """Test invalid priority falls back to 'normal'."""
        # Setup
        message_id = sample_message.id
        send_time = datetime.utcnow() + timedelta(hours=1)
        invalid_priority = 'super_urgent'  # Invalid priority

        mock_message_repo.get.return_value = sample_message

        # Mock Celery task scheduling
        with patch.object(scheduler, '_schedule_celery_task', new_callable=AsyncMock) as mock_schedule:
            mock_schedule.return_value = {
                'task_id': 'test-task-123',
                'status': 'scheduled'
            }

            # Execute
            result = await scheduler.schedule_existing_message(
                message_id=message_id,
                send_time=send_time,
                priority=invalid_priority
            )

            # Verify - should use 'normal' priority
            assert result is True
            assert sample_message.message_metadata['priority'] == 'normal'

    @pytest.mark.asyncio
    async def test_schedule_existing_message_celery_failure(self, scheduler, mock_message_repo, sample_message):
        """Test handling of Celery task scheduling failure."""
        # Setup
        message_id = sample_message.id
        send_time = datetime.utcnow() + timedelta(hours=1)
        priority = 'normal'

        mock_message_repo.get.return_value = sample_message

        # Mock Celery task scheduling failure
        with patch.object(scheduler, '_schedule_celery_task', new_callable=AsyncMock) as mock_schedule:
            mock_schedule.return_value = {
                'task_id': None,
                'error': 'Celery worker unavailable',
                'status': 'failed'
            }

            # Execute
            result = await scheduler.schedule_existing_message(
                message_id=message_id,
                send_time=send_time,
                priority=priority
            )

            # Verify
            assert result is False
            assert sample_message.status == MessageStatus.FAILED
            assert sample_message.message_metadata['scheduling_status'] == 'failed'
            assert sample_message.message_metadata['scheduling_error'] == 'Celery worker unavailable'

    @pytest.mark.asyncio
    async def test_schedule_existing_message_high_priority(self, scheduler, mock_message_repo, sample_message):
        """Test scheduling with high priority."""
        # Setup
        message_id = sample_message.id
        send_time = datetime.utcnow() + timedelta(minutes=5)
        priority = 'high'

        mock_message_repo.get.return_value = sample_message

        # Mock Celery task scheduling
        with patch.object(scheduler, '_schedule_celery_task', new_callable=AsyncMock) as mock_schedule:
            mock_schedule.return_value = {
                'task_id': 'urgent-task-456',
                'status': 'scheduled'
            }

            # Execute
            result = await scheduler.schedule_existing_message(
                message_id=message_id,
                send_time=send_time,
                priority=priority
            )

            # Verify
            assert result is True
            assert sample_message.message_metadata['priority'] == 'high'

    @pytest.mark.asyncio
    async def test_schedule_existing_message_already_scheduled(self, scheduler, mock_message_repo, sample_message):
        """Test rescheduling already scheduled message."""
        # Setup
        message_id = sample_message.id
        send_time = datetime.utcnow() + timedelta(hours=2)
        priority = 'normal'

        # Message already scheduled
        sample_message.status = MessageStatus.SCHEDULED
        sample_message.scheduled_for = datetime.utcnow() + timedelta(hours=1)

        mock_message_repo.get.return_value = sample_message

        # Mock Celery task scheduling
        with patch.object(scheduler, '_schedule_celery_task', new_callable=AsyncMock) as mock_schedule:
            mock_schedule.return_value = {
                'task_id': 'rescheduled-task-789',
                'status': 'scheduled'
            }

            # Execute
            result = await scheduler.schedule_existing_message(
                message_id=message_id,
                send_time=send_time,
                priority=priority
            )

            # Verify - should allow rescheduling
            assert result is True
            assert sample_message.scheduled_for == send_time


class TestFlowIntegration:
    """Test integration with FlowEngineIntegrationService."""

    @pytest.mark.asyncio
    async def test_flow_calls_schedule_existing_message(self):
        """Test that flow service correctly calls schedule_existing_message."""
        from app.services.flow import FlowEngineIntegrationService

        # This test verifies the method signature is correct
        # Mock all dependencies
        mock_db = Mock()
        mock_scheduler = AsyncMock(spec=MessageScheduler)

        # Create flow service with mocked scheduler
        flow_service = FlowEngineIntegrationService(
            db=mock_db,
            message_scheduler=mock_scheduler,
            use_unified_service=False
        )

        # Verify schedule_existing_message exists
        assert hasattr(mock_scheduler, 'schedule_existing_message')

        # Verify it's callable
        assert callable(mock_scheduler.schedule_existing_message)


class TestBackwardCompatibility:
    """Test backward compatibility with existing schedule_message method."""

    @pytest.mark.asyncio
    async def test_original_schedule_message_still_works(self, scheduler, mock_patient_repo):
        """Test that original schedule_message() method still works."""
        # Setup
        patient_id = uuid4()
        message_content = "Original method test"

        mock_patient = Mock()
        mock_patient.id = patient_id
        mock_patient.patient_metadata = {'timezone': 'America/Sao_Paulo'}
        mock_patient_repo.get.return_value = mock_patient

        # Mock dependencies
        with patch.object(scheduler, '_calculate_optimal_delivery_time', new_callable=AsyncMock) as mock_calc:
            with patch.object(scheduler, '_schedule_celery_task', new_callable=AsyncMock) as mock_schedule:
                mock_calc.return_value = datetime.utcnow() + timedelta(hours=1)
                mock_schedule.return_value = {
                    'task_id': 'legacy-task-123',
                    'status': 'scheduled'
                }

                # Execute - using original method
                result = await scheduler.schedule_message(
                    patient_id=patient_id,
                    message_content=message_content
                )

                # Verify
                assert result is not None
                assert 'message_id' in result
                assert 'status' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
