import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

from app.services.webhook_service import WebhookService
from app.models.webhook import WebhookEndpoint, WebhookDelivery, WebhookLog
from app.schemas.v2.webhooks import WebhookCreate, WebhookTestRequest, WebhookRetryRequest

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def service(mock_db):
    return WebhookService(mock_db)

@pytest.mark.asyncio
async def test_create_webhook(service, mock_db):
    webhook_data = WebhookCreate(
        url="https://example.com/webhook",
        events=["message.received"],
        description="Test Webhook"
    )
    
    # Mock DB add/commit/refresh
    mock_db.add = MagicMock()
    mock_db.commit = MagicMock()
    mock_db.refresh = MagicMock()
    
    # Mock Redis
    with patch.object(service, '_get_redis', return_value=AsyncMock()) as mock_redis:
        response = await service.create_webhook(webhook_data)
        
        assert response.url == "https://example.com/webhook"
        assert response.events == ["message.received"]
        assert mock_db.add.call_count == 2  # Webhook + Log
        assert mock_db.commit.called

@pytest.mark.asyncio
async def test_test_webhook(service, mock_db):
    webhook_id = uuid4()
    webhook = WebhookEndpoint(
        id=webhook_id,
        url="https://example.com/webhook",
        status="active",
        timeout=30,
        headers={}
    )
    
    # Mock DB query
    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = webhook
    mock_db.query.return_value = mock_query
    
    test_data = WebhookTestRequest(
        event_type="message.received",
        payload={"test": True}
    )
    
    # Mock httpx
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.text = "OK"
        mock_post.return_value.is_success = True
        
        response = await service.test_webhook(webhook_id, test_data)
        
        assert response.success is True
        assert response.status_code == 200
        assert mock_db.add.called # Delivery record created
        assert mock_db.commit.called

@pytest.mark.asyncio
async def test_retry_webhook_delivery(service, mock_db):
    webhook_id = uuid4()
    delivery_id = uuid4()
    
    webhook = WebhookEndpoint(
        id=webhook_id,
        url="https://example.com/webhook",
        max_retries=3,
        timeout=30
    )
    
    original_delivery = WebhookDelivery(
        id=delivery_id,
        webhook_id=webhook_id,
        event_type="message.received",
        payload={"test": True},
        attempt=1,
        status="failed"
    )
    
    # Mock DB queries
    def side_effect(*args, **kwargs):
        query_mock = MagicMock()
        if args and args[0] == WebhookDelivery:
            query_mock.filter.return_value.first.return_value = original_delivery
        elif args and args[0] == WebhookEndpoint:
            query_mock.filter.return_value.first.return_value = webhook
        return query_mock
        
    mock_db.query.side_effect = side_effect
    
    # Mock httpx
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.is_success = True
        
        response = await service.retry_webhook_delivery(webhook_id, delivery_id)
        
        assert response.success is True
        assert response.attempt == 2
        assert mock_db.add.called # New delivery record
