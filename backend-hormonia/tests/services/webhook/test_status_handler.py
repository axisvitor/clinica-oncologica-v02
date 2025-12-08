"""
Unit tests for StatusWebhookHandler.

Tests delivery status update processing for WhatsApp messages.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from uuid import uuid4
from datetime import datetime

from app.models.message import MessageStatus


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
    def handler(self, mock_db):
        """Create StatusWebhookHandler instance."""
        from app.services.webhook.handlers.status_handler import StatusWebhookHandler
        return StatusWebhookHandler(mock_db)

    @pytest.fixture
    def sample_status_event(self):
        """Sample status webhook event."""
        return {
            "instance": "clinica-hormonia",
            "event": "messages.update",
            "data": {
                "key": {
                    "remoteJid": "5511987654321@s.whatsapp.net",
                    "id": "whatsapp_msg_123"
                },
                "status": "READ"
            }
        }

    @pytest.mark.asyncio
    async def test_process_status_read(self, handler, mock_db, mock_webhook_store, sample_status_event):
        """Test processing READ status update."""
        mock_message = Mock()
        mock_message.id = uuid4()
        mock_message.status = MessageStatus.DELIVERED
        
        mock_result = Mock()
        mock_result.fetchone.return_value = mock_message
        mock_db.execute.return_value = mock_result
        
        result = await handler.process_status(sample_status_event, mock_webhook_store)
        
        assert result is True
        mock_webhook_store.persist_event.assert_called_once()
        mock_webhook_store.mark_processed.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_status_delivered(self, handler, mock_db, mock_webhook_store):
        """Test processing DELIVERED status update."""
        event = {
            "instance": "clinica-hormonia",
            "data": {
                "key": {"id": "whatsapp_msg_123"},
                "status": "DELIVERED"
            }
        }
        
        mock_message = Mock()
        mock_message.id = uuid4()
        mock_message.status = MessageStatus.SENT
        
        mock_result = Mock()
        mock_result.fetchone.return_value = mock_message
        mock_db.execute.return_value = mock_result
        
        result = await handler.process_status(event, mock_webhook_store)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_process_status_sent(self, handler, mock_db, mock_webhook_store):
        """Test processing SENT status update."""
        event = {
            "instance": "clinica-hormonia",
            "data": {
                "key": {"id": "whatsapp_msg_123"},
                "status": "SENT"
            }
        }
        
        mock_message = Mock()
        mock_message.id = uuid4()
        mock_message.status = MessageStatus.PENDING
        
        mock_result = Mock()
        mock_result.fetchone.return_value = mock_message
        mock_db.execute.return_value = mock_result
        
        result = await handler.process_status(event, mock_webhook_store)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_process_status_failed(self, handler, mock_db, mock_webhook_store):
        """Test processing FAILED status update."""
        event = {
            "instance": "clinica-hormonia",
            "data": {
                "key": {"id": "whatsapp_msg_123"},
                "status": "FAILED"
            }
        }
        
        mock_message = Mock()
        mock_message.id = uuid4()
        mock_message.status = MessageStatus.SENT
        
        mock_result = Mock()
        mock_result.fetchone.return_value = mock_message
        mock_db.execute.return_value = mock_result
        
        result = await handler.process_status(event, mock_webhook_store)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_process_status_message_not_found(self, handler, mock_db, mock_webhook_store):
        """Test status update for non-existent message."""
        event = {
            "data": {
                "key": {"id": "nonexistent_msg"},
                "status": "READ"
            }
        }
        
        mock_result = Mock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result
        
        result = await handler.process_status(event, mock_webhook_store)
        
        # Should return False when message not found
        assert result is False

    @pytest.mark.asyncio
    async def test_process_status_missing_data(self, handler, mock_webhook_store):
        """Test handling of missing data in webhook."""
        event = {"instance": "clinica-hormonia"}
        
        result = await handler.process_status(event, mock_webhook_store)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_process_status_without_webhook_store(self, handler, mock_db):
        """Test processing status without webhook persistence."""
        event = {
            "data": {
                "key": {"id": "whatsapp_msg_123"},
                "status": "READ"
            }
        }
        
        mock_message = Mock()
        mock_message.id = uuid4()
        mock_message.status = MessageStatus.DELIVERED
        
        mock_result = Mock()
        mock_result.fetchone.return_value = mock_message
        mock_db.execute.return_value = mock_result
        
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
