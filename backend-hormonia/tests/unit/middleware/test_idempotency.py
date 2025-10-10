"""
Unit Tests for Idempotency Middleware

Tests the idempotency middleware in isolation without full integration.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from fastapi import Request, Response
from sqlalchemy.orm import Session

from app.middleware.idempotency import IdempotencyMiddleware
from app.models.webhook_event import WebhookEvent


class TestIdempotencyMiddleware:
    """Unit tests for IdempotencyMiddleware."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance for testing."""
        app = Mock()
        return IdempotencyMiddleware(
            app=app,
            ttl_hours=24,
            enabled_paths=["/api/v1/webhooks/"]
        )

    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = Mock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/v1/webhooks/whatsapp"
        request.headers = {"X-Event-ID": "test-event-123"}
        return request

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return Mock(spec=Session)

    def test_should_check_idempotency_enabled_path(self, middleware, mock_request):
        """Test idempotency checking is enabled for configured paths."""
        assert middleware._should_check_idempotency(mock_request) is True

    def test_should_check_idempotency_disabled_path(self, middleware):
        """Test idempotency checking is disabled for non-webhook paths."""
        request = Mock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/v1/users"

        assert middleware._should_check_idempotency(request) is False

    def test_should_check_idempotency_get_request(self, middleware):
        """Test idempotency checking is disabled for GET requests."""
        request = Mock(spec=Request)
        request.method = "GET"
        request.url.path = "/api/v1/webhooks/whatsapp"

        assert middleware._should_check_idempotency(request) is False

    @pytest.mark.asyncio
    async def test_extract_event_id_from_header(self, middleware, mock_request):
        """Test extracting event ID from X-Event-ID header."""
        mock_request.body = AsyncMock(return_value=b'{"data": "test"}')

        event_id = await middleware._extract_event_id(mock_request)

        assert event_id == "test-event-123"

    @pytest.mark.asyncio
    async def test_extract_event_id_from_body(self, middleware):
        """Test extracting event ID from request body."""
        request = Mock(spec=Request)
        request.headers = {}
        request.body = AsyncMock(
            return_value=b'{"event_id": "body-event-456"}'
        )

        event_id = await middleware._extract_event_id(request)

        assert event_id == "body-event-456"

    @pytest.mark.asyncio
    async def test_extract_event_id_from_whatsapp_payload(self, middleware):
        """Test extracting event ID from WhatsApp webhook structure."""
        request = Mock(spec=Request)
        request.headers = {}

        whatsapp_payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "id": "whatsapp-msg-789"
                        }]
                    }
                }]
            }]
        }

        request.body = AsyncMock(
            return_value=json.dumps(whatsapp_payload).encode()
        )

        event_id = await middleware._extract_event_id(request)

        assert event_id == "whatsapp-msg-789"

    @pytest.mark.asyncio
    async def test_extract_event_id_generates_hash(self, middleware):
        """Test generating hash-based event ID when no ID found."""
        request = Mock(spec=Request)
        request.headers = {}

        payload = {"data": "test", "timestamp": 123456}
        request.body = AsyncMock(
            return_value=json.dumps(payload).encode()
        )

        event_id = await middleware._extract_event_id(request)

        # Should generate consistent hash
        assert event_id is not None
        assert len(event_id) == 32  # SHA256 truncated to 32 chars

    def test_extract_provider_whatsapp(self, middleware):
        """Test extracting provider from WhatsApp webhook path."""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/webhooks/whatsapp"

        provider = middleware._extract_provider(request)

        assert provider == "whatsapp"

    def test_extract_provider_twilio(self, middleware):
        """Test extracting provider from Twilio webhook path."""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/webhooks/twilio"

        provider = middleware._extract_provider(request)

        assert provider == "twilio"

    def test_extract_provider_generic(self, middleware):
        """Test extracting provider from generic webhook path."""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/webhook/custom"

        provider = middleware._extract_provider(request)

        assert provider == "generic"

    @pytest.mark.asyncio
    async def test_check_idempotency_new_event(
        self,
        middleware,
        mock_request,
        mock_db
    ):
        """Test checking idempotency for new event."""
        # Mock database query returning None (no existing event)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_request.body = AsyncMock(return_value=b'{"data": "test"}')

        event = await middleware._check_idempotency(
            db=mock_db,
            event_id="new-event-123",
            provider="whatsapp",
            event_type="webhook.received",
            request=mock_request
        )

        # Should create new event
        assert event is not None
        assert event.event_id == "new-event-123"
        assert event.status == "processing"

    @pytest.mark.asyncio
    async def test_check_idempotency_existing_event(
        self,
        middleware,
        mock_request,
        mock_db
    ):
        """Test checking idempotency for existing event."""
        # Create existing event
        existing_event = WebhookEvent.create_event(
            event_id="existing-event-123",
            provider="whatsapp",
            event_type="webhook.received"
        )
        existing_event.mark_completed()

        # Mock database query returning existing event
        mock_db.query.return_value.filter.return_value.first.return_value = existing_event
        mock_request.body = AsyncMock(return_value=b'{"data": "test"}')

        event = await middleware._check_idempotency(
            db=mock_db,
            event_id="existing-event-123",
            provider="whatsapp",
            event_type="webhook.received",
            request=mock_request
        )

        # Should return existing event
        assert event.event_id == "existing-event-123"
        assert event.status == "completed"

    @pytest.mark.asyncio
    async def test_check_idempotency_expired_event(
        self,
        middleware,
        mock_request,
        mock_db
    ):
        """Test checking idempotency for expired event."""
        # Create expired event
        expired_event = WebhookEvent.create_event(
            event_id="expired-event-123",
            provider="whatsapp",
            event_type="webhook.received"
        )
        expired_event.expires_at = datetime.utcnow() - timedelta(hours=1)
        expired_event.mark_completed()

        # Mock database query
        mock_db.query.return_value.filter.return_value.first.return_value = expired_event
        mock_request.body = AsyncMock(return_value=b'{"data": "test"}')

        event = await middleware._check_idempotency(
            db=mock_db,
            event_id="expired-event-123",
            provider="whatsapp",
            event_type="webhook.received",
            request=mock_request
        )

        # Should delete expired and create new
        mock_db.delete.assert_called_once_with(expired_event)

    @pytest.mark.asyncio
    async def test_middleware_call_new_webhook(
        self,
        middleware,
        mock_request,
        mock_db
    ):
        """Test middleware processing new webhook."""
        # Mock call_next
        call_next = AsyncMock()
        mock_response = Mock(spec=Response)
        mock_response.status_code = 200
        mock_response.headers = {}
        call_next.return_value = mock_response

        # Mock database operations
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_request.body = AsyncMock(return_value=b'{"data": "test"}')

        with patch('app.middleware.idempotency.get_db', return_value=[mock_db]):
            response = await middleware(mock_request, call_next)

        # Should process webhook
        call_next.assert_called_once()
        assert response.headers["X-Idempotency-Status"] == "processed"

    @pytest.mark.asyncio
    async def test_middleware_call_duplicate_webhook(
        self,
        middleware,
        mock_request,
        mock_db
    ):
        """Test middleware handling duplicate webhook."""
        # Create completed event
        existing_event = WebhookEvent.create_event(
            event_id="test-event-123",
            provider="whatsapp",
            event_type="webhook.received"
        )
        existing_event.mark_completed({"result": "success"})

        # Mock database query
        mock_db.query.return_value.filter.return_value.first.return_value = existing_event
        mock_request.body = AsyncMock(return_value=b'{"data": "test"}')

        # Mock call_next (should not be called for duplicate)
        call_next = AsyncMock()

        with patch('app.middleware.idempotency.get_db', return_value=[mock_db]):
            response = await middleware(mock_request, call_next)

        # Should not process webhook
        call_next.assert_not_called()

        # Should return duplicate response
        assert response.status_code == 200
        data = json.loads(response.body)
        assert data["status"] == "duplicate"

    @pytest.mark.asyncio
    async def test_middleware_error_handling(
        self,
        middleware,
        mock_request,
        mock_db
    ):
        """Test middleware error handling."""
        # Mock call_next to raise exception
        call_next = AsyncMock(side_effect=Exception("Processing error"))

        # Mock database operations
        new_event = WebhookEvent.create_event(
            event_id="test-event-123",
            provider="whatsapp",
            event_type="webhook.received"
        )
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.side_effect = lambda x: setattr(x, 'event_id', 'test-event-123')
        mock_request.body = AsyncMock(return_value=b'{"data": "test"}')

        with patch('app.middleware.idempotency.get_db', return_value=[mock_db]):
            with pytest.raises(Exception):
                await middleware(mock_request, call_next)

        # Should mark event as failed
        # (verify through mock calls)

    def test_middleware_ttl_configuration(self):
        """Test middleware TTL configuration."""
        app = Mock()
        middleware = IdempotencyMiddleware(
            app=app,
            ttl_hours=48
        )

        assert middleware.ttl_hours == 48

    def test_middleware_enabled_paths_configuration(self):
        """Test middleware enabled paths configuration."""
        app = Mock()
        custom_paths = ["/custom/webhook", "/api/hooks"]

        middleware = IdempotencyMiddleware(
            app=app,
            enabled_paths=custom_paths
        )

        assert middleware.enabled_paths == custom_paths
