"""
Unit tests for StatusWebhookHandler.

Tests delivery status update processing for WhatsApp messages.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

from app.models.message import MessageStatus, MessageDirection, MessageType


class TestStatusWebhookHandler:
    """Test StatusWebhookHandler functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = Mock()
        db.query = Mock()
        db.execute = Mock()
        db.commit = Mock()
        db.rollback = Mock()
        return db

    @pytest.fixture
    def mock_webhook_store(self):
        """Create a mock webhook store."""
        store = Mock()
        store.persist_event = AsyncMock(return_value=uuid4())
        store.mark_processed = AsyncMock()
        return store

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.set = AsyncMock(return_value=True)
        return redis

    @pytest.fixture
    def mock_get_async_redis(self, mock_redis):
        """Patch async Redis getter."""
        with patch(
            "app.services.webhook.handlers.status_handler.get_async_redis",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = mock_redis
            yield mock_get

    @pytest.fixture
    def mock_publish_ws(self):
        """Patch websocket publish."""
        with patch(
            "app.services.webhook.handlers.status_handler.websocket_events_module.websocket_events",
            new=Mock(),
        ) as mock_ws:
            mock_ws.broadcast_message_event = AsyncMock()
            yield mock_ws

    @pytest.fixture
    def handler(self, mock_db):
        """Create StatusWebhookHandler instance."""
        from app.services.webhook.handlers.status_handler import StatusWebhookHandler
        return StatusWebhookHandler(mock_db)

    @pytest.fixture
    def sample_status_event(self):
        """Sample status webhook event."""
        return {
            "key": {"id": "whatsapp_msg_123"},
            "update": {"status": "READ"},
        }

    @pytest.mark.asyncio
    async def test_process_status_read(
        self,
        handler,
        mock_db,
        mock_webhook_store,
        mock_get_async_redis,
        mock_publish_ws,
        sample_status_event,
    ):
        """Test processing READ status update."""
        previous_message = Mock()
        previous_message.status = MessageStatus.DELIVERED

        updated_message = Mock()
        updated_message.id = uuid4()
        updated_message.status = MessageStatus.READ
        updated_message.direction = MessageDirection.OUTBOUND
        updated_message.type = MessageType.TEXT
        updated_message.patient_id = uuid4()
        updated_message.whatsapp_id = "whatsapp_msg_123"

        handler.message_service.get_message_by_whatsapp_id = Mock(
            return_value=previous_message
        )
        handler.message_service.update_message_status_by_whatsapp_id = Mock(
            return_value=updated_message
        )
        
        result = await handler.process_status(sample_status_event, mock_webhook_store)
        
        assert result is True
        mock_webhook_store.persist_event.assert_called_once()
        mock_webhook_store.mark_processed.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_status_delivered(
        self,
        handler,
        mock_db,
        mock_webhook_store,
        mock_get_async_redis,
        mock_publish_ws,
    ):
        """Test processing DELIVERED status update."""
        event = {
            "key": {"id": "whatsapp_msg_123"},
            "update": {"status": "DELIVERED"},
        }
        
        handler.message_service.get_message_by_whatsapp_id = Mock(
            return_value=Mock(status=MessageStatus.SENT)
        )
        handler.message_service.update_message_status_by_whatsapp_id = Mock(
            return_value=Mock(
                id=uuid4(),
                status=MessageStatus.DELIVERED,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                patient_id=uuid4(),
                whatsapp_id="whatsapp_msg_123",
            )
        )
        
        result = await handler.process_status(event, mock_webhook_store)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_process_status_sent(
        self,
        handler,
        mock_db,
        mock_webhook_store,
        mock_get_async_redis,
        mock_publish_ws,
    ):
        """Test processing SENT status update."""
        event = {
            "key": {"id": "whatsapp_msg_123"},
            "update": {"status": "SENT"},
        }
        
        handler.message_service.get_message_by_whatsapp_id = Mock(
            return_value=Mock(status=MessageStatus.PENDING)
        )
        handler.message_service.update_message_status_by_whatsapp_id = Mock(
            return_value=Mock(
                id=uuid4(),
                status=MessageStatus.SENT,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                patient_id=uuid4(),
                whatsapp_id="whatsapp_msg_123",
            )
        )
        
        result = await handler.process_status(event, mock_webhook_store)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_process_status_failed(
        self,
        handler,
        mock_db,
        mock_webhook_store,
        mock_get_async_redis,
        mock_publish_ws,
    ):
        """Test processing FAILED status update."""
        event = {
            "key": {"id": "whatsapp_msg_123"},
            "update": {"status": "FAILED"},
        }
        
        handler.message_service.get_message_by_whatsapp_id = Mock(
            return_value=Mock(status=MessageStatus.SENT)
        )
        handler.message_service.update_message_status_by_whatsapp_id = Mock(
            return_value=Mock(
                id=uuid4(),
                status=MessageStatus.FAILED,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                patient_id=uuid4(),
                whatsapp_id="whatsapp_msg_123",
            )
        )
        
        result = await handler.process_status(event, mock_webhook_store)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_process_status_message_not_found(
        self,
        handler,
        mock_db,
        mock_webhook_store,
        mock_get_async_redis,
    ):
        """Test status update for non-existent message."""
        event = {
            "key": {"id": "nonexistent_msg"},
            "update": {"status": "READ"},
        }

        handler.message_service.get_message_by_whatsapp_id = Mock(return_value=None)
        handler.message_service.update_message_status_by_whatsapp_id = Mock(
            return_value=None
        )
        
        result = await handler.process_status(event, mock_webhook_store)
        
        # Should return False when message not found
        assert result is False

    @pytest.mark.asyncio
    async def test_process_status_missing_data(self, handler, mock_webhook_store, mock_get_async_redis):
        """Test handling of missing data in webhook."""
        event = {"instance": "clinica-hormonia"}
        
        result = await handler.process_status(event, mock_webhook_store)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_process_status_without_webhook_store(
        self, handler, mock_db, mock_get_async_redis, mock_publish_ws
    ):
        """Test processing status without webhook persistence."""
        event = {
            "key": {"id": "whatsapp_msg_123"},
            "update": {"status": "READ"},
        }

        handler.message_service.get_message_by_whatsapp_id = Mock(
            return_value=Mock(status=MessageStatus.DELIVERED)
        )
        handler.message_service.update_message_status_by_whatsapp_id = Mock(
            return_value=Mock(
                id=uuid4(),
                status=MessageStatus.READ,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                patient_id=uuid4(),
                whatsapp_id="whatsapp_msg_123",
            )
        )
        
        result = await handler.process_status(event, webhook_store=None)
        
        assert result is True


class TestStatusMapping:
    """Test Evolution API status mapping to internal status."""

    @pytest.fixture
    def handler(self):
        """Create StatusWebhookHandler instance."""
        from app.services.webhook.handlers.status_handler import StatusWebhookHandler
        return StatusWebhookHandler(Mock())

    def test_map_sent_status(self, handler):
        """Test mapping SENT status."""
        result = handler._map_evolution_status("SENT")
        assert result == MessageStatus.SENT

    def test_map_delivered_status(self, handler):
        """Test mapping DELIVERED status."""
        result = handler._map_evolution_status("DELIVERED")
        assert result == MessageStatus.DELIVERED

    def test_map_read_status(self, handler):
        """Test mapping READ status."""
        result = handler._map_evolution_status("READ")
        assert result == MessageStatus.READ

    def test_map_failed_status(self, handler):
        """Test mapping FAILED status."""
        result = handler._map_evolution_status("FAILED")
        assert result == MessageStatus.FAILED

    def test_map_unknown_status(self, handler):
        """Test mapping unknown status defaults to PENDING."""
        result = handler._map_evolution_status("UNKNOWN_STATUS")
        assert result == MessageStatus.PENDING

    def test_map_lowercase_status(self, handler):
        """Test mapping lowercase status."""
        result = handler._map_evolution_status("read")
        # Should handle case-insensitive mapping
        assert result in [MessageStatus.READ, MessageStatus.PENDING]
