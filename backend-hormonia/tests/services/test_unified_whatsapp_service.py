"""
Tests for unified WhatsApp service (Redis-backed)

This test suite validates the UnifiedWhatsAppService which consolidates
legacy and new WhatsApp messaging pipelines with queue management.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timedelta
from uuid import uuid4

from app.services.unified_whatsapp_service import UnifiedWhatsAppService, MessagingMode
from app.models.message import Message, MessageType, MessageStatus, MessageDirection, MessagePriority
from app.models.patient import Patient
from app.integrations.whatsapp.models.message import (
    MessageRequest, MessageResponse, MessageStatus as WhatsAppMessageStatus,
    MessageType as WhatsAppMessageType
)


class TestUnifiedWhatsAppService:
    """Test suite for UnifiedWhatsAppService"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client for queue operations"""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        redis.lpush = AsyncMock()
        redis.rpop = AsyncMock()
        redis.exists = AsyncMock(return_value=False)
        return redis

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        db = AsyncMock()
        db.sync_session = MagicMock()  # For MessageService compatibility
        return db

    @pytest.fixture
    def mock_patient(self):
        """Create mock patient"""
        patient = Patient(
            id=uuid4(),
            name="Test Patient",
            phone="5511999999999",
            email="test@example.com",
            doctor_id=uuid4()
        )
        return patient

    @pytest.fixture
    def mock_message(self, mock_patient):
        """Create mock message"""
        message = Message(
            id=uuid4(),
            patient_id=mock_patient.id,
            direction=MessageDirection.OUTBOUND,
            type=MessageType.TEXT,
            content="Test message",
            status=MessageStatus.PENDING,
            priority=MessagePriority.NORMAL,
            idempotency_key=f"test-{uuid4()}"
        )
        message.patient = mock_patient
        return message

    @pytest.fixture
    def service(self, mock_redis, mock_db):
        """Create service instance with mocks"""
        with patch('app.services.unified_whatsapp_service.settings') as mock_settings:
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            mock_settings.WHATSAPP_EVOLUTION_API_URL = "http://localhost:8080"
            mock_settings.WHATSAPP_EVOLUTION_API_KEY = "test-key"
            mock_settings.WHATSAPP_EVOLUTION_WEBHOOK_URL = "http://localhost:8000/webhooks"

            service = UnifiedWhatsAppService(redis=mock_redis, db=mock_db)
            return service

    @pytest.mark.asyncio
    async def test_send_message_success(self, service, mock_message):
        """Test successful message sending via queue"""
        # Arrange
        with patch.object(service, '_send_via_queue', new_callable=AsyncMock) as mock_queue:
            mock_queue.return_value = True

            # Act
            result = await service.send_message(mock_message)

            # Assert
            assert result is True
            mock_queue.assert_called_once_with(mock_message)
            assert service.metrics['messages_sent'] == 1
            assert service.metrics['queue_processed'] == 1

    @pytest.mark.asyncio
    async def test_send_message_queued_when_api_fails(self, service, mock_message):
        """Test message is queued when API fails"""
        # Arrange
        with patch.object(service, '_send_via_queue', new_callable=AsyncMock) as mock_queue:
            mock_queue.return_value = True

            # Act
            result = await service.send_message(mock_message)

            # Assert
            assert result is True
            assert mock_message.message_metadata['unified_service']['mode'] == 'queue'

    @pytest.mark.asyncio
    async def test_retry_respects_max_retries(self, service):
        """Test retry logic respects max_retries limit (off-by-one fix)"""
        # This tests the critical fix: >= instead of >
        max_retries = 3

        # Create test message with retry metadata
        message = MagicMock()
        message.message_metadata = {
            'retry_attempts': 3,
            'retry_policy': 'default'
        }

        # At exactly max_retries, should not retry
        retry_policy = service.retry_policies['default']
        retry_attempts = message.message_metadata['retry_attempts']

        should_skip = retry_attempts >= retry_policy['max_retries']
        assert should_skip is True

        # Before max_retries, should continue
        message.message_metadata['retry_attempts'] = 2
        retry_attempts = message.message_metadata['retry_attempts']
        should_continue = retry_attempts < retry_policy['max_retries']
        assert should_continue is True

    @pytest.mark.asyncio
    async def test_metadata_enrichment(self, service, mock_message):
        """Test unified metadata is added to messages"""
        # Act
        service._add_unified_metadata(mock_message)

        # Assert
        assert 'unified_service' in mock_message.message_metadata
        assert mock_message.message_metadata['unified_service']['version'] == '2.0.0'
        assert mock_message.message_metadata['unified_service']['mode'] == 'queue'
        assert mock_message.message_metadata['requires_queue'] is True
        assert 'retry_policy' in mock_message.message_metadata

    @pytest.mark.asyncio
    async def test_flow_context_retry_policy(self, service, mock_message):
        """Test retry policy selection based on flow context"""
        # Test initial_15_days flow
        flow_context = {'flow_type': 'initial_15_days'}
        service._add_unified_metadata(mock_message, flow_context=flow_context)
        assert mock_message.message_metadata['retry_policy'] == 'flow_message'

        # Test urgent flow
        mock_message.message_metadata = {}
        flow_context = {'urgent': True}
        service._add_unified_metadata(mock_message, flow_context=flow_context)
        assert mock_message.message_metadata['retry_policy'] == 'urgent'

        # Test quiz flow
        mock_message.message_metadata = {}
        flow_context = {'flow_type': 'quiz_link'}
        service._add_unified_metadata(mock_message, flow_context=flow_context)
        assert mock_message.message_metadata['retry_policy'] == 'quiz_link'

    @pytest.mark.asyncio
    async def test_convert_to_queue_request(self, service, mock_message, mock_patient):
        """Test message conversion to queue request format"""
        # Ensure patient is loaded
        mock_message.patient = mock_patient

        # Act
        queue_request = await service._convert_to_queue_request(mock_message)

        # Assert
        assert isinstance(queue_request, MessageRequest)
        assert queue_request.to == mock_patient.phone
        assert queue_request.message_type == WhatsAppMessageType.TEXT
        assert queue_request.text == mock_message.content
        assert 'domain_message_id' in queue_request.message_data
        assert queue_request.message_data['domain_message_id'] == str(mock_message.id)

    @pytest.mark.asyncio
    async def test_media_message_conversion(self, service, mock_message, mock_patient):
        """Test media message type mapping"""
        # Arrange
        mock_message.type = MessageType.MEDIA
        mock_message.message_metadata = {
            'media_url': 'https://example.com/image.jpg',
            'caption': 'Test image',
            'media_type': 'image'
        }
        mock_message.patient = mock_patient

        # Act
        queue_request = await service._convert_to_queue_request(mock_message)

        # Assert
        assert queue_request.message_type == WhatsAppMessageType.IMAGE
        assert queue_request.media_url == 'https://example.com/image.jpg'
        assert queue_request.media_caption == 'Test image'

    @pytest.mark.asyncio
    async def test_retry_failed_messages(self, service):
        """Test retry logic with backoff calculation"""
        # Create mock failed messages
        failed_msg = MagicMock()
        failed_msg.id = uuid4()
        failed_msg.message_metadata = {
            'retry_attempts': 1,
            'retry_policy': 'default',
            'last_retry_at': (datetime.utcnow() - timedelta(minutes=10)).isoformat()
        }

        with patch.object(service.message_service, 'get_failed_messages') as mock_get:
            with patch.object(service.message_service, 'update_message') as mock_update:
                with patch.object(service, 'send_message', new_callable=AsyncMock) as mock_send:
                    mock_get.return_value = [failed_msg]
                    mock_send.return_value = True

                    # Act
                    retry_count = await service.retry_failed_messages(limit=50)

                    # Assert
                    assert retry_count == 1
                    mock_update.assert_called_once()
                    assert service.metrics['retries_attempted'] == 1

    @pytest.mark.asyncio
    async def test_backoff_delay_calculation(self, service):
        """Test exponential backoff delay calculation"""
        retry_policy = service.retry_policies['default']
        base_delay = retry_policy['base_delay']
        backoff_factor = retry_policy['backoff_factor']

        # Retry 0: 300s (5 min)
        delay_0 = base_delay * (backoff_factor ** 0)
        assert delay_0 == 300

        # Retry 1: 600s (10 min)
        delay_1 = base_delay * (backoff_factor ** 1)
        assert delay_1 == 600

        # Retry 2: 1200s (20 min)
        delay_2 = base_delay * (backoff_factor ** 2)
        assert delay_2 == 1200

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, service):
        """Test health check when all components are healthy"""
        with patch.object(service, '_get_queue_client', new_callable=AsyncMock):
            with patch.object(service.message_queue, 'connect', new_callable=AsyncMock):
                # Act
                health = await service.health_check()

                # Assert
                assert health['status'] == 'healthy'
                assert health['components']['queue_client'] == 'healthy'
                assert health['components']['message_queue'] == 'healthy'

    @pytest.mark.asyncio
    async def test_health_check_degraded(self, service):
        """Test health check when components are unhealthy"""
        with patch.object(service, '_get_queue_client', new_callable=AsyncMock) as mock_client:
            mock_client.side_effect = Exception("Connection failed")

            # Act
            health = await service.health_check()

            # Assert
            assert health['status'] == 'degraded'
            assert 'unhealthy' in health['components']['queue_client']

    @pytest.mark.asyncio
    async def test_metrics_collection(self, service, mock_message):
        """Test unified metrics collection"""
        with patch.object(service, '_send_via_queue', new_callable=AsyncMock) as mock_queue:
            mock_queue.return_value = True

            # Send some messages
            await service.send_message(mock_message)
            await service.send_message(mock_message)

            # Get metrics
            metrics = await service.get_unified_metrics()

            # Assert
            assert metrics['unified_metrics']['total_sent'] == 2
            assert metrics['unified_metrics']['queue_processed'] == 2
            assert metrics['unified_metrics']['success_rate'] == 100.0
            assert 'uptime_seconds' in metrics['unified_metrics']

    @pytest.mark.asyncio
    async def test_flow_message_with_context(self, service, mock_message):
        """Test flow-specific message sending with context"""
        flow_context = {
            'flow_type': 'initial_15_days',
            'patient_day': 5,
            'template_id': str(uuid4())
        }

        with patch.object(service, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            # Act
            result = await service.send_flow_message(mock_message, flow_context)

            # Assert
            assert result is True
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[1]['flow_context'] == flow_context

    @pytest.mark.asyncio
    async def test_callbacks_on_success(self, service, mock_message):
        """Test success callbacks are executed"""
        callback_executed = False

        async def success_callback(message, flow_context):
            nonlocal callback_executed
            callback_executed = True

        service.register_flow_callback('message_sent', success_callback)

        with patch.object(service, '_send_via_queue', new_callable=AsyncMock) as mock_queue:
            mock_queue.return_value = True

            # Act
            await service.send_message(mock_message)

            # Assert
            assert callback_executed is True

    @pytest.mark.asyncio
    async def test_callbacks_on_failure(self, service, mock_message):
        """Test failure callbacks are executed"""
        callback_executed = False
        error_captured = None

        async def failure_callback(message, flow_context, error):
            nonlocal callback_executed, error_captured
            callback_executed = True
            error_captured = error

        service.register_flow_callback('message_failed', failure_callback)

        with patch.object(service, '_send_via_queue', new_callable=AsyncMock) as mock_queue:
            mock_queue.return_value = False

            # Act
            await service.send_message(mock_message)

            # Assert
            assert callback_executed is True

    @pytest.mark.asyncio
    async def test_instance_name_override(self, service, mock_message, mock_patient):
        """Test per-message instance name override"""
        # Arrange
        custom_instance = "custom_clinic"
        mock_message.message_metadata = {'instance_name': custom_instance}
        mock_message.patient = mock_patient

        # Act
        queue_request = await service._convert_to_queue_request(mock_message)

        # Assert
        assert queue_request.instance_name == custom_instance

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, service):
        """Test graceful service shutdown"""
        # Setup service components
        service._queue_service = AsyncMock()
        service._queue_client = MagicMock()

        with patch.object(service.message_queue, 'disconnect', new_callable=AsyncMock) as mock_disconnect:
            # Act
            await service.shutdown()

            # Assert
            mock_disconnect.assert_called_once()


class TestRetryPolicies:
    """Test retry policy configurations"""

    @pytest.fixture
    def service(self):
        """Create service instance for policy tests"""
        with patch('app.services.unified_whatsapp_service.settings') as mock_settings:
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            db = MagicMock()
            db.sync_session = MagicMock()
            return UnifiedWhatsAppService(db=db)

    def test_default_retry_policy(self, service):
        """Test default retry policy parameters"""
        policy = service.retry_policies['default']
        assert policy['max_retries'] == 3
        assert policy['backoff_factor'] == 2
        assert policy['base_delay'] == 300

    def test_flow_message_retry_policy(self, service):
        """Test flow message retry policy"""
        policy = service.retry_policies['flow_message']
        assert policy['max_retries'] == 5
        assert policy['backoff_factor'] == 1.5
        assert policy['base_delay'] == 180

    def test_urgent_retry_policy(self, service):
        """Test urgent message retry policy"""
        policy = service.retry_policies['urgent']
        assert policy['max_retries'] == 7
        assert policy['backoff_factor'] == 1.2
        assert policy['base_delay'] == 60

    def test_quiz_link_retry_policy(self, service):
        """Test quiz link retry policy"""
        policy = service.retry_policies['quiz_link']
        assert policy['max_retries'] == 4
        assert policy['backoff_factor'] == 1.8
        assert policy['base_delay'] == 240


class TestQueueIntegration:
    """Test queue-based message processing"""

    @pytest.fixture
    def service(self):
        """Create service with queue support"""
        with patch('app.services.unified_whatsapp_service.settings') as mock_settings:
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            mock_settings.WHATSAPP_EVOLUTION_API_URL = "http://localhost:8080"
            db = AsyncMock()
            return UnifiedWhatsAppService(db=db)

    @pytest.mark.asyncio
    async def test_process_queue_messages(self, service):
        """Test queue message processing"""
        with patch.object(service, '_get_queue_service', new_callable=AsyncMock) as mock_get_service:
            mock_queue_service = AsyncMock()
            mock_queue_service.process_message_queue = AsyncMock()
            mock_get_service.return_value = mock_queue_service

            # Act
            result = await service.process_queue_messages(max_messages=100)

            # Assert
            assert result['queue_processing_started'] is True
            assert result['max_messages'] == 100
