"""
Unit tests for ConnectionWebhookHandler.

Tests connection state and QR code webhook processing.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4


class TestConnectionWebhookHandler:
    """Test ConnectionWebhookHandler functionality."""

    @pytest.fixture
    def mock_connection_state_repo(self):
        """Create a mock connection state repository."""
        repo = Mock()
        repo.set_state = AsyncMock()
        repo.get_state = AsyncMock(return_value="open")
        return repo

    @pytest.fixture
    def mock_webhook_store(self):
        """Create a mock webhook store."""
        store = Mock()
        store.persist_event = AsyncMock(return_value=uuid4())
        store.mark_processed = AsyncMock()
        return store

    @pytest.fixture
    def handler(self, mock_connection_state_repo):
        """Create ConnectionWebhookHandler instance."""
        from app.services.webhook.handlers.connection_handler import ConnectionWebhookHandler
        return ConnectionWebhookHandler(mock_connection_state_repo)

    @pytest.mark.asyncio
    async def test_process_connection_open(self, handler, mock_connection_state_repo, mock_webhook_store):
        """Test processing connection open event."""
        event = {
            "instance": "clinica-hormonia",
            "state": "open"
        }
        
        result = await handler.process_connection(event, mock_webhook_store)
        
        assert result is True
        mock_connection_state_repo.set_state.assert_called_once_with("clinica-hormonia", "open")
        mock_webhook_store.mark_processed.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_connection_close(self, handler, mock_connection_state_repo, mock_webhook_store):
        """Test processing connection close event."""
        event = {
            "instance": "clinica-hormonia",
            "state": "close"
        }
        
        result = await handler.process_connection(event, mock_webhook_store)
        
        assert result is True
        mock_connection_state_repo.set_state.assert_called_once_with("clinica-hormonia", "close")

    @pytest.mark.asyncio
    async def test_process_connection_connecting(self, handler, mock_connection_state_repo, mock_webhook_store):
        """Test processing connection connecting event."""
        event = {
            "instance": "clinica-hormonia",
            "state": "connecting"
        }
        
        result = await handler.process_connection(event, mock_webhook_store)
        
        assert result is True
        mock_connection_state_repo.set_state.assert_called_once_with("clinica-hormonia", "connecting")

    @pytest.mark.asyncio
    async def test_process_connection_state_from_data(self, handler, mock_connection_state_repo, mock_webhook_store):
        """Test extracting state from data object."""
        event = {
            "instance": "clinica-hormonia",
            "data": {"state": "open"}
        }
        
        result = await handler.process_connection(event, mock_webhook_store)
        
        assert result is True
        mock_connection_state_repo.set_state.assert_called_once_with("clinica-hormonia", "open")

    @pytest.mark.asyncio
    async def test_process_connection_missing_instance(self, handler, mock_webhook_store):
        """Test handling missing instance in webhook."""
        event = {"state": "open"}
        
        result = await handler.process_connection(event, mock_webhook_store)
        
        assert result is False
        mock_webhook_store.mark_processed.assert_called_with(
            mock_webhook_store.persist_event.return_value, False, "Missing required fields"
        )

    @pytest.mark.asyncio
    async def test_process_connection_missing_state(self, handler, mock_webhook_store):
        """Test handling missing state in webhook."""
        event = {"instance": "clinica-hormonia"}
        
        result = await handler.process_connection(event, mock_webhook_store)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_process_connection_without_webhook_store(self, handler, mock_connection_state_repo):
        """Test processing connection without webhook persistence."""
        event = {
            "instance": "clinica-hormonia",
            "state": "open"
        }
        
        result = await handler.process_connection(event, webhook_store=None)
        
        assert result is True
        mock_connection_state_repo.set_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_connection_repo_error(self, handler, mock_connection_state_repo, mock_webhook_store):
        """Test handling repository error."""
        mock_connection_state_repo.set_state.side_effect = Exception("Redis error")
        
        event = {
            "instance": "clinica-hormonia",
            "state": "open"
        }
        
        result = await handler.process_connection(event, mock_webhook_store)
        
        assert result is False
        mock_webhook_store.mark_processed.assert_called()


class TestQRCodeWebhookHandler:
    """Test QR code webhook processing."""

    @pytest.fixture
    def mock_webhook_store(self):
        """Create a mock webhook store."""
        store = Mock()
        store.persist_event = AsyncMock(return_value=uuid4())
        store.mark_processed = AsyncMock()
        return store

    @pytest.fixture
    def handler(self):
        """Create ConnectionWebhookHandler instance."""
        from app.services.webhook.handlers.connection_handler import ConnectionWebhookHandler
        return ConnectionWebhookHandler()

    @pytest.mark.asyncio
    @patch('app.services.webhook.handlers.connection_handler.get_async_redis')
    async def test_process_qrcode_success(self, mock_get_redis, handler, mock_webhook_store):
        """Test successful QR code processing."""
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()
        mock_get_redis.return_value = mock_redis
        
        event = {
            "instance": "clinica-hormonia",
            "qrcode": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
        }
        
        result = await handler.process_qrcode(event, mock_webhook_store)
        
        assert result is True
        mock_redis.setex.assert_called_once()
        mock_webhook_store.mark_processed.assert_called_with(
            mock_webhook_store.persist_event.return_value, True
        )

    @pytest.mark.asyncio
    @patch('app.services.webhook.handlers.connection_handler.get_async_redis')
    async def test_process_qrcode_from_data(self, mock_get_redis, handler, mock_webhook_store):
        """Test extracting QR code from data object."""
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()
        mock_get_redis.return_value = mock_redis
        
        event = {
            "instance": "clinica-hormonia",
            "data": {"qrcode": "base64_qr_code_data"}
        }
        
        result = await handler.process_qrcode(event, mock_webhook_store)
        
        assert result is True
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_qrcode_missing_instance(self, handler, mock_webhook_store):
        """Test handling missing instance in QR code webhook."""
        event = {"qrcode": "base64_data"}
        
        result = await handler.process_qrcode(event, mock_webhook_store)
        
        assert result is False
        mock_webhook_store.mark_processed.assert_called_with(
            mock_webhook_store.persist_event.return_value, False, "Missing instance"
        )

    @pytest.mark.asyncio
    @patch('app.services.webhook.handlers.connection_handler.get_async_redis')
    async def test_process_qrcode_redis_error(self, mock_get_redis, handler, mock_webhook_store):
        """Test handling Redis error during QR code storage."""
        mock_redis = AsyncMock()
        mock_redis.setex.side_effect = Exception("Redis connection error")
        mock_get_redis.return_value = mock_redis
        
        event = {
            "instance": "clinica-hormonia",
            "qrcode": "base64_qr_code_data"
        }
        
        result = await handler.process_qrcode(event, mock_webhook_store)
        
        assert result is False
        mock_webhook_store.mark_processed.assert_called()

    @pytest.mark.asyncio
    @patch('app.services.webhook.handlers.connection_handler.get_async_redis')
    async def test_process_qrcode_without_webhook_store(self, mock_get_redis, handler):
        """Test processing QR code without webhook persistence."""
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()
        mock_get_redis.return_value = mock_redis
        
        event = {
            "instance": "clinica-hormonia",
            "qrcode": "base64_qr_code_data"
        }
        
        result = await handler.process_qrcode(event, webhook_store=None)
        
        assert result is True
        mock_redis.setex.assert_called_once()
