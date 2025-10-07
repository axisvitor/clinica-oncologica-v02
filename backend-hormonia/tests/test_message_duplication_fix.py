"""
Test suite for P0-4: Message Duplication Fix

Verifies that scheduled messages are updated by Celery tasks instead of creating duplicates.
Tests the full workflow: schedule → send → status updates
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, Mock, patch

from app.models.message import Message, MessageStatus, MessageType, MessageDirection
from app.models.patient import Patient
from app.services.message_scheduler import MessageScheduler, SchedulingWindow
from app.tasks.flows import send_flow_message


class TestMessageDuplicationFix:
    """Test message scheduling without duplication."""

    @pytest.fixture
    def mock_patient(self):
        """Create mock patient."""
        patient = Mock(spec=Patient)
        patient.id = uuid4()
        patient.patient_metadata = {"timezone": "America/Sao_Paulo"}
        return patient

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        session = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.refresh = Mock()
        session.query = Mock()
        return session

    @pytest.fixture
    def mock_message_repo(self, mock_db_session):
        """Create mock message repository."""
        repo = Mock()
        repo.get = Mock()
        return repo

    @pytest.fixture
    def scheduler(self, mock_db_session):
        """Create MessageScheduler instance."""
        return MessageScheduler(mock_db_session)

    @pytest.mark.asyncio
    async def test_schedule_message_creates_single_record(self, scheduler, mock_patient, mock_db_session):
        """Test that schedule_message creates exactly ONE message record."""
        # Mock repository
        with patch.object(scheduler, 'patient_repo') as mock_patient_repo:
            mock_patient_repo.get.return_value = mock_patient

            # Mock Celery task scheduling
            with patch('app.services.message_scheduler.send_flow_message') as mock_task:
                mock_task.apply_async.return_value = Mock(id="task-123")

                # Schedule message
                result = await scheduler.schedule_message(
                    patient_id=mock_patient.id,
                    message_content="Test message",
                    scheduling_window=SchedulingWindow.BUSINESS_HOURS
                )

                # Verify only ONE message was added to database
                assert mock_db_session.add.call_count == 1
                message = mock_db_session.add.call_args[0][0]
                assert isinstance(message, Message)
                assert message.status == MessageStatus.SCHEDULED
                assert message.content == "Test message"

                # Verify Celery task was scheduled with message_id
                mock_task.apply_async.assert_called_once()
                args = mock_task.apply_async.call_args
                assert len(args[1]['args']) == 3  # patient_id, message_data, message_id
                assert str(message.id) in args[1]['args']  # message_id passed

    @pytest.mark.asyncio
    async def test_send_flow_message_updates_existing_message(self, mock_db_session):
        """Test that send_flow_message UPDATES existing scheduled message."""
        # Create existing scheduled message
        message_id = uuid4()
        patient_id = uuid4()
        existing_message = Message(
            id=message_id,
            patient_id=patient_id,
            direction=MessageDirection.OUTBOUND,
            type=MessageType.TEXT,
            content="Scheduled message",
            status=MessageStatus.SCHEDULED,
            message_metadata={"celery_task_id": "task-123"}
        )

        # Mock repositories
        mock_message_repo = Mock()
        mock_message_repo.get.return_value = existing_message

        mock_patient_repo = Mock()
        mock_patient_repo.get.return_value = Mock(id=patient_id)

        with patch('app.tasks.flows.MessageRepository', return_value=mock_message_repo):
            with patch('app.tasks.flows.PatientRepository', return_value=mock_patient_repo):
                with patch('app.tasks.flows.MessageSender') as mock_sender:
                    # Mock successful send
                    mock_sender_instance = mock_sender.return_value
                    mock_sender_instance.send_message = AsyncMock(return_value=True)

                    # Mock Celery task context
                    mock_self = Mock()
                    mock_self.request.id = "celery-task-456"
                    mock_self.request.retries = 0
                    mock_self.max_retries = 3

                    # Call send_flow_message with message_id
                    message_data = {
                        "content": "Updated content",
                        "type": "text",
                        "metadata": {}
                    }

                    with patch('app.tasks.flows.get_db', return_value=iter([mock_db_session])):
                        result = send_flow_message(
                            mock_self,
                            str(patient_id),
                            message_data,
                            message_id=str(message_id)  # KEY: Pass message_id
                        )

                    # Verify NO new message was created
                    assert mock_db_session.add.call_count == 0

                    # Verify existing message was loaded
                    mock_message_repo.get.assert_called_once_with(message_id)

                    # Verify message status was updated to SENDING
                    assert existing_message.status == MessageStatus.SENDING

                    # Verify send was called
                    mock_sender_instance.send_message.assert_called_once_with(existing_message)

    @pytest.mark.asyncio
    async def test_send_flow_message_status_transitions(self, mock_db_session):
        """Test proper status transitions: SCHEDULED → SENDING → SENT/FAILED."""
        message_id = uuid4()
        patient_id = uuid4()

        # Create scheduled message
        message = Message(
            id=message_id,
            patient_id=patient_id,
            direction=MessageDirection.OUTBOUND,
            type=MessageType.TEXT,
            content="Test",
            status=MessageStatus.SCHEDULED,
            message_metadata={}
        )

        mock_message_repo = Mock()
        mock_message_repo.get.return_value = message

        mock_patient_repo = Mock()
        mock_patient_repo.get.return_value = Mock(id=patient_id)

        # Test SUCCESS case
        with patch('app.tasks.flows.MessageRepository', return_value=mock_message_repo):
            with patch('app.tasks.flows.PatientRepository', return_value=mock_patient_repo):
                with patch('app.tasks.flows.MessageSender') as mock_sender:
                    mock_sender_instance = mock_sender.return_value
                    mock_sender_instance.send_message = AsyncMock(return_value=True)

                    mock_self = Mock()
                    mock_self.request.id = "task-123"
                    mock_self.request.retries = 0
                    mock_self.max_retries = 3

                    with patch('app.tasks.flows.get_db', return_value=iter([mock_db_session])):
                        result = send_flow_message(
                            mock_self,
                            str(patient_id),
                            {"content": "Test", "type": "text", "metadata": {}},
                            message_id=str(message_id)
                        )

                    # Verify status transitions
                    # SCHEDULED → SENDING (before send)
                    # SENDING → SENT (after successful send by MessageSender)
                    assert "execution_status" in message.message_metadata
                    assert message.message_metadata["execution_status"] == "success"

    @pytest.mark.asyncio
    async def test_send_flow_message_failure_updates_status(self, mock_db_session):
        """Test that failures update message status to FAILED."""
        message_id = uuid4()
        patient_id = uuid4()

        message = Message(
            id=message_id,
            patient_id=patient_id,
            direction=MessageDirection.OUTBOUND,
            type=MessageType.TEXT,
            content="Test",
            status=MessageStatus.SCHEDULED,
            message_metadata={}
        )

        mock_message_repo = Mock()
        mock_message_repo.get.return_value = message

        mock_patient_repo = Mock()
        mock_patient_repo.get.return_value = Mock(id=patient_id)

        # Test FAILURE case
        with patch('app.tasks.flows.MessageRepository', return_value=mock_message_repo):
            with patch('app.tasks.flows.PatientRepository', return_value=mock_patient_repo):
                with patch('app.tasks.flows.MessageSender') as mock_sender:
                    # Mock send failure
                    mock_sender_instance = mock_sender.return_value
                    mock_sender_instance.send_message = AsyncMock(return_value=False)

                    mock_self = Mock()
                    mock_self.request.id = "task-123"
                    mock_self.request.retries = 0
                    mock_self.max_retries = 3

                    with patch('app.tasks.flows.get_db', return_value=iter([mock_db_session])):
                        result = send_flow_message(
                            mock_self,
                            str(patient_id),
                            {"content": "Test", "type": "text", "metadata": {}},
                            message_id=str(message_id)
                        )

                    # Verify message was marked as FAILED
                    assert message.status == MessageStatus.FAILED
                    assert "failure_reason" in message.message_metadata

    @pytest.mark.asyncio
    async def test_backward_compatibility_without_message_id(self, mock_db_session):
        """Test that task still works without message_id (legacy behavior)."""
        patient_id = uuid4()

        mock_patient_repo = Mock()
        mock_patient_repo.get.return_value = Mock(id=patient_id)

        # Call without message_id (legacy)
        with patch('app.tasks.flows.PatientRepository', return_value=mock_patient_repo):
            with patch('app.tasks.flows.MessageSender') as mock_sender:
                mock_sender_instance = mock_sender.return_value
                mock_sender_instance.send_message = AsyncMock(return_value=True)

                mock_self = Mock()
                mock_self.request.id = "task-123"
                mock_self.request.retries = 0
                mock_self.max_retries = 3

                with patch('app.tasks.flows.get_db', return_value=iter([mock_db_session])):
                    result = send_flow_message(
                        mock_self,
                        str(patient_id),
                        {"content": "Test", "type": "text", "metadata": {}},
                        message_id=None  # Legacy: no message_id
                    )

                # Should create new message (backward compatibility)
                assert mock_db_session.add.call_count == 1

    def test_message_status_enum_has_sending(self):
        """Verify SENDING status exists in MessageStatus enum."""
        assert hasattr(MessageStatus, 'SENDING')
        assert MessageStatus.SENDING.value == 'sending'

    @pytest.mark.asyncio
    async def test_no_duplicate_messages_in_database(self, scheduler, mock_patient, mock_db_session):
        """
        Integration test: Verify that scheduling and sending creates exactly ONE message.
        This is the core fix for P0-4.
        """
        message_count = 0

        def track_message_creation(message):
            """Track how many messages are created."""
            nonlocal message_count
            message_count += 1

        mock_db_session.add.side_effect = track_message_creation

        with patch.object(scheduler, 'patient_repo') as mock_patient_repo:
            mock_patient_repo.get.return_value = mock_patient

            with patch('app.services.message_scheduler.send_flow_message') as mock_task:
                mock_task.apply_async.return_value = Mock(id="task-123")

                # Schedule message
                await scheduler.schedule_message(
                    patient_id=mock_patient.id,
                    message_content="Test message",
                    scheduling_window=SchedulingWindow.BUSINESS_HOURS
                )

        # Verify exactly ONE message was created
        assert message_count == 1, f"Expected 1 message, got {message_count} (duplication detected!)"


class TestMessageSchedulerIntegration:
    """Integration tests for MessageScheduler with Celery."""

    @pytest.mark.asyncio
    async def test_schedule_existing_message_passes_id_to_celery(self, mock_db_session):
        """Test that schedule_existing_message passes message_id to Celery."""
        message_id = uuid4()
        patient_id = uuid4()

        # Create existing message
        message = Message(
            id=message_id,
            patient_id=patient_id,
            direction=MessageDirection.OUTBOUND,
            type=MessageType.TEXT,
            content="Test",
            status=MessageStatus.PENDING,
            message_metadata={}
        )

        mock_message_repo = Mock()
        mock_message_repo.get.return_value = message

        scheduler = MessageScheduler(mock_db_session)
        scheduler.message_repo = mock_message_repo

        with patch('app.services.message_scheduler.send_flow_message') as mock_task:
            mock_task.apply_async.return_value = Mock(id="task-123")

            send_time = datetime.utcnow() + timedelta(hours=1)

            # Schedule existing message
            result = await scheduler.schedule_existing_message(
                message_id=message_id,
                send_time=send_time,
                priority='high'
            )

            # Verify task was scheduled with message_id
            mock_task.apply_async.assert_called_once()
            args = mock_task.apply_async.call_args[1]['args']
            assert len(args) == 3  # patient_id, message_data, message_id
            assert args[2] == str(message_id)  # message_id is third argument

            # Verify message status updated to SCHEDULED
            assert message.status == MessageStatus.SCHEDULED
            assert result is True
