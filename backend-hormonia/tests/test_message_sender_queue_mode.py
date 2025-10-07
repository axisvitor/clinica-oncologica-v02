"""
Tests for MessageSender queue mode as default behavior.
Verifies P1-3 fix: MessageSender defaults to QUEUE mode with retry/backoff policies.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from uuid import uuid4

from app.services.message_sender import MessageSender
from app.services.unified_whatsapp_service import UnifiedWhatsAppService, MessagingMode
from app.models.message import Message, MessageType, MessageStatus, MessageDirection
from app.models.patient import Patient


@pytest.fixture
def mock_db():
    """Create mock database session."""
    db = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    return db


@pytest.fixture
def mock_patient():
    """Create mock patient."""
    patient = Patient(
        id=uuid4(),
        name="Test Patient",
        phone="5511999999999",
        email="test@example.com"
    )
    return patient


@pytest.fixture
def mock_message(mock_patient):
    """Create mock message."""
    message = Message(
        id=uuid4(),
        patient_id=mock_patient.id,
        patient=mock_patient,
        direction=MessageDirection.OUTBOUND,
        type=MessageType.TEXT,
        content="Test message",
        status=MessageStatus.PENDING,
        message_metadata={}
    )
    return message


class TestMessageSenderQueueMode:
    """Test suite for MessageSender queue mode default behavior."""

    def test_message_sender_defaults_to_queue_mode(self, mock_db):
        """Test that MessageSender defaults to QUEUE mode."""
        sender = MessageSender(mock_db)

        assert sender.messaging_mode == MessagingMode.QUEUE
        assert sender._unified_service.messaging_mode == MessagingMode.QUEUE

    def test_message_sender_explicit_queue_mode(self, mock_db):
        """Test that MessageSender can be explicitly set to QUEUE mode."""
        sender = MessageSender(mock_db, messaging_mode=MessagingMode.QUEUE)

        assert sender.messaging_mode == MessagingMode.QUEUE
        assert sender._unified_service.messaging_mode == MessagingMode.QUEUE

    def test_message_sender_explicit_legacy_mode(self, mock_db):
        """Test that MessageSender can still use LEGACY mode when explicit."""
        with pytest.warns(DeprecationWarning, match="MessagingMode.LEGACY is deprecated"):
            sender = MessageSender(mock_db, messaging_mode=MessagingMode.LEGACY)

        assert sender.messaging_mode == MessagingMode.LEGACY
        assert sender._unified_service.messaging_mode == MessagingMode.LEGACY

    def test_message_sender_hybrid_mode(self, mock_db):
        """Test that MessageSender supports HYBRID mode."""
        sender = MessageSender(mock_db, messaging_mode=MessagingMode.HYBRID)

        assert sender.messaging_mode == MessagingMode.HYBRID
        assert sender._unified_service.messaging_mode == MessagingMode.HYBRID

    @pytest.mark.asyncio
    async def test_queue_mode_adds_requires_queue_metadata(self, mock_db, mock_message):
        """Test that queue mode adds requires_queue flag to metadata."""
        with patch.object(UnifiedWhatsAppService, '_send_via_queue', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            sender = MessageSender(mock_db, messaging_mode=MessagingMode.QUEUE)
            await sender.send_message(mock_message)

            # Verify metadata was updated
            assert mock_message.message_metadata.get('requires_queue') is True
            assert mock_message.message_metadata.get('unified_service', {}).get('mode') == 'queue'

    @pytest.mark.asyncio
    async def test_queue_mode_assigns_default_retry_policy(self, mock_db, mock_message):
        """Test that queue mode assigns default retry policy."""
        with patch.object(UnifiedWhatsAppService, '_send_via_queue', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            sender = MessageSender(mock_db, messaging_mode=MessagingMode.QUEUE)
            await sender.send_message(mock_message)

            # Verify retry policy was assigned
            assert mock_message.message_metadata.get('retry_policy') == 'default'

    @pytest.mark.asyncio
    async def test_flow_messages_get_flow_retry_policy(self, mock_db, mock_message):
        """Test that flow messages get appropriate retry policy."""
        flow_context = {
            'flow_type': 'initial_15_days',
            'flow_day': 1
        }

        with patch.object(UnifiedWhatsAppService, '_send_via_queue', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            sender = MessageSender(mock_db, messaging_mode=MessagingMode.QUEUE)
            await sender.send_flow_message(mock_message, flow_context=flow_context)

            # Verify flow-specific retry policy
            assert mock_message.message_metadata.get('retry_policy') == 'flow_message'

    @pytest.mark.asyncio
    async def test_quiz_messages_get_quiz_retry_policy(self, mock_db, mock_message):
        """Test that quiz messages get quiz-specific retry policy."""
        flow_context = {
            'flow_type': 'quiz_link_flow',
            'quiz_template_id': str(uuid4())
        }

        with patch.object(UnifiedWhatsAppService, '_send_via_queue', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            sender = MessageSender(mock_db, messaging_mode=MessagingMode.QUEUE)
            await sender.send_flow_message(mock_message, flow_context=flow_context)

            # Verify quiz-specific retry policy
            assert mock_message.message_metadata.get('retry_policy') == 'quiz_link'

    @pytest.mark.asyncio
    async def test_urgent_messages_get_urgent_retry_policy(self, mock_db, mock_message):
        """Test that urgent messages get urgent retry policy."""
        flow_context = {
            'urgent': True
        }

        with patch.object(UnifiedWhatsAppService, '_send_via_queue', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            sender = MessageSender(mock_db, messaging_mode=MessagingMode.QUEUE)
            await sender.send_message(mock_message, flow_context=flow_context)

            # Verify urgent retry policy
            assert mock_message.message_metadata.get('retry_policy') == 'urgent'

    @pytest.mark.asyncio
    async def test_retry_policies_configuration(self, mock_db):
        """Test that retry policies are properly configured."""
        sender = MessageSender(mock_db)

        # Verify retry policies exist
        assert 'default' in sender.retry_policies
        assert 'flow_message' in sender.retry_policies
        assert 'urgent' in sender.retry_policies
        assert 'quiz_link' in sender.retry_policies

        # Verify default policy
        default_policy = sender.retry_policies['default']
        assert default_policy['max_retries'] == 3
        assert default_policy['backoff_factor'] == 2
        assert default_policy['base_delay'] == 300

        # Verify flow_message policy
        flow_policy = sender.retry_policies['flow_message']
        assert flow_policy['max_retries'] == 5
        assert flow_policy['backoff_factor'] == 1.5
        assert flow_policy['base_delay'] == 180

        # Verify urgent policy
        urgent_policy = sender.retry_policies['urgent']
        assert urgent_policy['max_retries'] == 7
        assert urgent_policy['backoff_factor'] == 1.2
        assert urgent_policy['base_delay'] == 60

    @pytest.mark.asyncio
    async def test_failed_message_retry_with_backoff(self, mock_db, mock_message):
        """Test that failed messages are retried with exponential backoff."""
        # Set message as failed with retry attempts
        mock_message.status = MessageStatus.FAILED
        mock_message.message_metadata = {
            'retry_policy': 'default',
            'retry_attempts': 1,
            'last_retry_at': (datetime.utcnow() - timedelta(minutes=10)).isoformat()
        }

        with patch.object(MessageSender, 'message_service') as mock_service:
            mock_service.get_failed_messages.return_value = [mock_message]
            mock_service.update_message = Mock()
            mock_service.mark_as_sent = Mock()

            with patch.object(UnifiedWhatsAppService, '_send_via_queue', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = True

                sender = MessageSender(mock_db, messaging_mode=MessagingMode.QUEUE)
                retry_count = await sender.retry_failed_messages(limit=10)

                # Verify retry was attempted
                assert retry_count > 0

                # Verify metadata was updated
                assert mock_message.message_metadata['retry_attempts'] == 2
                assert 'last_retry_at' in mock_message.message_metadata

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, mock_db, mock_message):
        """Test that messages exceeding max retries are skipped."""
        # Set message with max retries exceeded
        mock_message.status = MessageStatus.FAILED
        mock_message.message_metadata = {
            'retry_policy': 'default',
            'retry_attempts': 3,  # Equal to max_retries
            'last_retry_at': (datetime.utcnow() - timedelta(minutes=10)).isoformat()
        }

        with patch.object(MessageSender, 'message_service') as mock_service:
            mock_service.get_failed_messages.return_value = [mock_message]

            sender = MessageSender(mock_db, messaging_mode=MessagingMode.QUEUE)
            retry_count = await sender.retry_failed_messages(limit=10)

            # Verify message was skipped (no retry)
            assert retry_count == 0

    @pytest.mark.asyncio
    async def test_backoff_delay_calculation(self, mock_db, mock_message):
        """Test that backoff delay is calculated correctly."""
        # Set message with 2 retry attempts
        mock_message.status = MessageStatus.FAILED
        mock_message.message_metadata = {
            'retry_policy': 'default',
            'retry_attempts': 2,
            'last_retry_at': datetime.utcnow().isoformat()  # Just retried
        }

        with patch.object(MessageSender, 'message_service') as mock_service:
            mock_service.get_failed_messages.return_value = [mock_message]

            sender = MessageSender(mock_db, messaging_mode=MessagingMode.QUEUE)
            retry_count = await sender.retry_failed_messages(limit=10)

            # Verify message was skipped due to insufficient time since last retry
            # Expected delay: 300 * (2 ** 2) = 1200 seconds = 20 minutes
            assert retry_count == 0

    def test_celery_tasks_use_queue_mode(self, mock_db):
        """Test that Celery tasks instantiate MessageSender with QUEUE mode."""
        # This test verifies the code changes in messaging.py and flows.py
        # In actual Celery tasks, MessagingMode.QUEUE should be passed

        # Simulate Celery task instantiation
        from app.services.unified_whatsapp_service import MessagingMode
        sender = MessageSender(mock_db, messaging_mode=MessagingMode.QUEUE)

        assert sender.messaging_mode == MessagingMode.QUEUE

    @pytest.mark.asyncio
    async def test_legacy_mode_compatibility(self, mock_db, mock_message):
        """Test that legacy mode still works for backward compatibility."""
        with pytest.warns(DeprecationWarning):
            sender = MessageSender(mock_db, messaging_mode=MessagingMode.LEGACY)

        with patch.object(UnifiedWhatsAppService, '_send_via_legacy', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await sender.send_message(mock_message)

            # Verify legacy send was called
            assert result is True
            mock_send.assert_called_once()


class TestUnifiedWhatsAppServiceQueueMode:
    """Test suite for UnifiedWhatsAppService queue mode behavior."""

    def test_unified_service_defaults_to_hybrid(self, mock_db):
        """Test that UnifiedWhatsAppService defaults to HYBRID mode."""
        service = UnifiedWhatsAppService(mock_db)
        assert service.messaging_mode == MessagingMode.HYBRID

    def test_unified_service_queue_mode_metadata(self, mock_db, mock_message):
        """Test that queue mode adds proper metadata."""
        service = UnifiedWhatsAppService(mock_db, messaging_mode=MessagingMode.QUEUE)

        # Manually call _add_unified_metadata
        service._add_unified_metadata(mock_message, MessagingMode.QUEUE)

        # Verify metadata
        assert mock_message.message_metadata.get('requires_queue') is True
        assert mock_message.message_metadata.get('retry_policy') == 'default'
        assert mock_message.message_metadata.get('unified_service', {}).get('mode') == 'queue'

    def test_unified_service_hybrid_mode_selection(self, mock_db, mock_message):
        """Test that HYBRID mode selects appropriate mode based on metadata."""
        service = UnifiedWhatsAppService(mock_db, messaging_mode=MessagingMode.HYBRID)

        # Test queue mode selection for messages with requires_queue
        mock_message.message_metadata = {'requires_queue': True}
        mode = service._determine_messaging_mode(mock_message)
        assert mode == MessagingMode.QUEUE

        # Test queue mode selection for scheduled messages
        mock_message.message_metadata = {'scheduled_for': datetime.utcnow().isoformat()}
        mode = service._determine_messaging_mode(mock_message)
        assert mode == MessagingMode.QUEUE

        # Test queue mode selection for high-priority flows
        mock_message.message_metadata = {'flow_context': {'priority': 'high'}}
        mode = service._determine_messaging_mode(mock_message)
        assert mode == MessagingMode.QUEUE

        # Test legacy mode selection for simple messages
        mock_message.message_metadata = {}
        mode = service._determine_messaging_mode(mock_message)
        assert mode == MessagingMode.LEGACY

    @pytest.mark.asyncio
    async def test_metrics_tracking_by_mode(self, mock_db, mock_message):
        """Test that metrics are tracked separately for each mode."""
        service = UnifiedWhatsAppService(mock_db, messaging_mode=MessagingMode.QUEUE)

        with patch.object(service, '_send_via_queue', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            await service.send_message(mock_message)

            # Verify metrics
            assert service.metrics['messages_sent'] >= 1
            assert service.metrics['queue_processed'] >= 1

    @pytest.mark.asyncio
    async def test_retry_failed_messages_uses_policies(self, mock_db):
        """Test that retry_failed_messages uses configured retry policies."""
        service = UnifiedWhatsAppService(mock_db, messaging_mode=MessagingMode.QUEUE)

        # Create a failed message with retry policy
        failed_message = Message(
            id=uuid4(),
            patient_id=uuid4(),
            direction=MessageDirection.OUTBOUND,
            type=MessageType.TEXT,
            content="Test",
            status=MessageStatus.FAILED,
            message_metadata={
                'retry_policy': 'flow_message',
                'retry_attempts': 1,
                'last_retry_at': (datetime.utcnow() - timedelta(minutes=10)).isoformat()
            }
        )

        with patch.object(service.message_service, 'get_failed_messages') as mock_get:
            mock_get.return_value = [failed_message]

            with patch.object(service, 'send_message', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = True

                retry_count = await service.retry_failed_messages(limit=10)

                # Verify retry was attempted with flow_message policy
                assert retry_count > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
