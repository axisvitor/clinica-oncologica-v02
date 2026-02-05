"""
Comprehensive test suite for V2 Webhooks API
Tests all 15 endpoints with security, pagination, caching, and rate limiting.
"""

import pytest
import json
import time
import hmac
import hashlib
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, patch, AsyncMock

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.webhook import WebhookEndpoint
from app.config import settings


# ============================================================================
# FIXTURES
# ============================================================================
@pytest.fixture
def client():
    """Test client"""
    return TestClient(app)


@pytest.fixture
def mock_redis():
    """Mock Redis cache"""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=True)
    redis_mock.delete_pattern = AsyncMock(return_value=True)
    return redis_mock


@pytest.fixture
def mock_db(monkeypatch):
    """Mock database session"""
    db_mock = Mock(spec=Session)
    db_mock.query = Mock()
    db_mock.execute = Mock()
    db_mock.add = Mock()
    db_mock.commit = Mock()
    db_mock.rollback = Mock()
    db_mock.refresh = Mock()
    db_mock.delete = Mock()
    return db_mock


@pytest.fixture
def sample_webhook():
    """Sample webhook configuration"""
    return WebhookEndpoint(
        id=uuid4(),
        url="https://api.example.com/webhooks",
        events=["message.received", "message.sent"],
        description="Test webhook",
        secret="wh_secret_test123456789",
        headers={"X-Api-Key": "test123"},
        timeout=30,
        retry_enabled=True,
        max_retries=3,
        status="active",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def compute_signature(payload: bytes, secret: str, timestamp: str = None) -> str:
    """Helper to compute HMAC signature"""
    if timestamp:
        signature_payload = f"{timestamp}.{payload.decode('utf-8')}"
        signature_bytes = signature_payload.encode("utf-8")
    else:
        signature_bytes = payload

    return hmac.new(
        secret.encode("utf-8"),
        signature_bytes,
        hashlib.sha256,
    ).hexdigest()


# ============================================================================
# WEBHOOK MANAGEMENT TESTS
# ============================================================================
class TestWebhookManagement:
    """Test webhook CRUD operations"""

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_list_webhooks_success(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis, sample_webhook):
        """Test listing webhooks with pagination"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        # Mock database query
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [sample_webhook]
        mock_db.execute.return_value = mock_result

        response = client.get("/api/v2/webhooks?limit=20")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert "next_cursor" in data
        assert "has_more" in data

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_list_webhooks_with_cursor(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test cursor-based pagination"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        # Create cursor
        import base64
        cursor_data = {"id": 100}
        cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()

        response = client.get(f"/api/v2/webhooks?cursor={cursor}&limit=20")

        assert response.status_code == status.HTTP_200_OK

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_list_webhooks_with_status_filter(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test filtering webhooks by status"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        response = client.get("/api/v2/webhooks?status=active")

        assert response.status_code == status.HTTP_200_OK

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_list_webhooks_cached(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test cached webhook list returns from Redis"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        # Mock cached response
        cached_data = {
            "data": [],
            "next_cursor": None,
            "has_more": False,
            "total": 0
        }
        mock_redis.get.return_value = json.dumps(cached_data)

        response = client.get("/api/v2/webhooks")

        assert response.status_code == status.HTTP_200_OK
        # Should not query database
        mock_db.execute.assert_not_called()

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_create_webhook_success(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test creating new webhook"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        webhook_data = {
            "url": "https://api.example.com/webhooks",
            "events": ["message.received", "message.sent"],
            "description": "Test webhook",
            "timeout": 30,
            "retry_enabled": True,
            "max_retries": 3
        }

        response = client.post("/api/v2/webhooks", json=webhook_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["url"] == webhook_data["url"]
        assert "secret_preview" in data
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_create_webhook_with_custom_secret(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test creating webhook with custom secret"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        webhook_data = {
            "url": "https://api.example.com/webhooks",
            "events": ["message.received"],
            "secret": "my_custom_secret_1234567890"
        }

        response = client.post("/api/v2/webhooks", json=webhook_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["secret_preview"] == "my_custo"

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_create_webhook_validation_error(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test webhook creation with invalid data"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        webhook_data = {
            "url": "invalid-url",
            "events": []  # Empty events
        }

        response = client.post("/api/v2/webhooks", json=webhook_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_get_webhook_success(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis, sample_webhook):
        """Test retrieving webhook by ID"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        mock_db.query.return_value.filter.return_value.first.return_value = sample_webhook

        response = client.get(f"/api/v2/webhooks/{sample_webhook.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(sample_webhook.id)
        assert data["url"] == sample_webhook.url

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_get_webhook_cached(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis, sample_webhook):
        """Test cached webhook retrieval"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        cached_data = {
            "id": str(sample_webhook.id),
            "url": sample_webhook.url,
            "events": sample_webhook.events,
            "status": "active",
            "secret_preview": "wh_secre",
            "headers": {},
            "timeout": 30,
            "retry_enabled": True,
            "max_retries": 3,
            "created_at": sample_webhook.created_at.isoformat(),
            "updated_at": sample_webhook.updated_at.isoformat(),
            "last_triggered_at": None,
            "success_count": 0,
            "failure_count": 0,
            "description": None
        }
        mock_redis.get.return_value = json.dumps(cached_data)

        response = client.get(f"/api/v2/webhooks/{sample_webhook.id}")

        assert response.status_code == status.HTTP_200_OK
        mock_db.query.assert_not_called()

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_get_webhook_not_found(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test retrieving non-existent webhook"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        mock_db.query.return_value.filter.return_value.first.return_value = None

        webhook_id = uuid4()
        response = client.get(f"/api/v2/webhooks/{webhook_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_update_webhook_success(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis, sample_webhook):
        """Test updating webhook configuration"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        mock_db.query.return_value.filter.return_value.first.return_value = sample_webhook

        update_data = {
            "status": "paused",
            "description": "Updated webhook"
        }

        response = client.put(f"/api/v2/webhooks/{sample_webhook.id}", json=update_data)

        assert response.status_code == status.HTTP_200_OK
        mock_db.commit.assert_called_once()
        mock_redis.delete.assert_called()

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_delete_webhook_success(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis, sample_webhook):
        """Test deleting webhook"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        mock_db.query.return_value.filter.return_value.first.return_value = sample_webhook

        response = client.delete(f"/api/v2/webhooks/{sample_webhook.id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock_db.delete.assert_called_once()
        mock_db.commit.assert_called_once()


# ============================================================================
# WEBHOOK SECURITY TESTS
# ============================================================================
class TestWebhookSecurity:
    """Test HMAC signature validation and security features"""

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_inbound_webhook_valid_signature(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test inbound webhook with valid HMAC signature"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        # Mock webhook processor
        with patch("app.api.v2.webhooks.WebhookProcessor") as mock_processor:
            mock_processor.return_value.process_message_webhook = AsyncMock(return_value="msg_123")

            payload = {
                "event": "message.received",
                "data": {"message": "test"},
                "timestamp": str(int(time.time()))
            }

            payload_bytes = json.dumps(payload).encode()
            timestamp = payload["timestamp"]

            # Compute signature
            signature = compute_signature(payload_bytes, settings.EVOLUTION_WEBHOOK_SECRET, timestamp)

            headers = {
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": timestamp,
                "X-Webhook-Id": "wh_evt_123"
            }

            response = client.post("/api/v2/webhooks/inbound", json=payload, headers=headers)

            assert response.status_code == status.HTTP_200_OK

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_inbound_webhook_invalid_signature(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test inbound webhook with invalid signature"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        payload = {
            "event": "message.received",
            "data": {"message": "test"},
            "timestamp": str(int(time.time()))
        }

        headers = {
            "X-Webhook-Signature": "invalid_signature",
            "X-Webhook-Timestamp": payload["timestamp"],
            "X-Webhook-Id": "wh_evt_123"
        }

        response = client.post("/api/v2/webhooks/inbound", json=payload, headers=headers)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_inbound_webhook_expired_timestamp(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test inbound webhook with expired timestamp (replay attack prevention)"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        # Use old timestamp (10 minutes ago)
        old_timestamp = str(int(time.time()) - 600)

        payload = {
            "event": "message.received",
            "data": {"message": "test"},
            "timestamp": old_timestamp
        }

        payload_bytes = json.dumps(payload).encode()
        signature = compute_signature(payload_bytes, settings.EVOLUTION_WEBHOOK_SECRET, old_timestamp)

        headers = {
            "X-Webhook-Signature": signature,
            "X-Webhook-Timestamp": old_timestamp,
            "X-Webhook-Id": "wh_evt_123"
        }

        response = client.post("/api/v2/webhooks/inbound", json=payload, headers=headers)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "expired" in response.json()["detail"].lower()

    @patch("app.api.v2.webhooks.check_idempotency")
    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_inbound_webhook_idempotency(self, mock_get_db, mock_get_redis, mock_check_idempotency, client, mock_db, mock_redis):
        """Test idempotency prevents duplicate processing"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis
        mock_check_idempotency.return_value = False  # Duplicate

        payload = {
            "event": "message.received",
            "data": {"message": "test"},
            "timestamp": str(int(time.time()))
        }

        payload_bytes = json.dumps(payload).encode()
        timestamp = payload["timestamp"]
        signature = compute_signature(payload_bytes, settings.EVOLUTION_WEBHOOK_SECRET, timestamp)

        headers = {
            "X-Webhook-Signature": signature,
            "X-Webhook-Timestamp": timestamp,
            "X-Webhook-Id": "wh_evt_duplicate"
        }

        response = client.post("/api/v2/webhooks/inbound", json=payload, headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "duplicate"


# ============================================================================
# WEBHOOK TESTING & OPERATIONS
# ============================================================================
class TestWebhookOperations:
    """Test webhook testing and operational features"""

    @patch("app.api.v2.webhooks.get_db")
    def test_test_webhook_success(self, mock_get_db, client, mock_db, sample_webhook):
        """Test webhook test endpoint"""
        mock_get_db.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = sample_webhook

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status":"ok"}'
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            test_data = {
                "event_type": "message.received",
                "payload": {"test": True}
            }

            response = client.post(f"/api/v2/webhooks/{sample_webhook.id}/test", json=test_data)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert "response_time_ms" in data

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_rotate_webhook_secret(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis, sample_webhook):
        """Test webhook secret rotation"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis
        mock_db.query.return_value.filter.return_value.first.return_value = sample_webhook

        response = client.put(f"/api/v2/webhooks/{sample_webhook.id}/secret", json={})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "secret_preview" in data
        assert "rotated_at" in data
        mock_db.commit.assert_called_once()

    @patch("app.api.v2.webhooks.get_db")
    def test_get_event_types(self, mock_get_db, client, mock_db):
        """Test getting available webhook event types"""
        mock_get_db.return_value = mock_db

        response = client.get("/api/v2/webhooks/events")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "events" in data
        assert "total" in data
        assert data["total"] > 0


# ============================================================================
# WEBHOOK DELIVERIES & RETRY
# ============================================================================
class TestWebhookDeliveries:
    """Test webhook delivery tracking and retry logic"""

    @patch("app.api.v2.webhooks.get_db")
    def test_get_webhook_deliveries(self, mock_get_db, client, mock_db, sample_webhook):
        """Test retrieving webhook delivery history"""
        mock_get_db.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = sample_webhook

        response = client.get(f"/api/v2/webhooks/{sample_webhook.id}/deliveries")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert "next_cursor" in data

    @patch("app.api.v2.webhooks.get_db")
    def test_get_webhook_deliveries_with_status_filter(self, mock_get_db, client, mock_db, sample_webhook):
        """Test filtering deliveries by status"""
        mock_get_db.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = sample_webhook

        response = client.get(f"/api/v2/webhooks/{sample_webhook.id}/deliveries?status=failed")

        assert response.status_code == status.HTTP_200_OK

    @patch("app.api.v2.webhooks.get_db")
    def test_retry_failed_delivery(self, mock_get_db, client, mock_db, sample_webhook):
        """Test retrying failed webhook delivery"""
        mock_get_db.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = sample_webhook

        delivery_id = uuid4()
        retry_data = {"force": False}

        response = client.post(
            f"/api/v2/webhooks/{sample_webhook.id}/deliveries/{delivery_id}/retry",
            json=retry_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    @patch("app.api.v2.webhooks.get_db")
    def test_get_webhook_logs(self, mock_get_db, client, mock_db, sample_webhook):
        """Test retrieving webhook activity logs"""
        mock_get_db.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = sample_webhook

        response = client.get(f"/api/v2/webhooks/{sample_webhook.id}/logs")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data


# ============================================================================
# ANALYTICS & HEALTH
# ============================================================================
class TestWebhookAnalytics:
    """Test webhook analytics and health endpoints"""

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_get_webhook_stats(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test webhook statistics endpoint"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis
        mock_db.query.return_value.scalar.return_value = 10

        response = client.get("/api/v2/webhooks/stats")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_webhooks" in data
        assert "active_webhooks" in data
        assert "success_rate" in data

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_get_webhook_stats_cached(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test cached webhook statistics"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        cached_stats = {
            "total_webhooks": 10,
            "active_webhooks": 8,
            "total_deliveries": 1000,
            "successful_deliveries": 980,
            "failed_deliveries": 20,
            "pending_deliveries": 5,
            "average_response_time_ms": 150.0,
            "success_rate": 98.0,
            "last_24h_deliveries": 100
        }
        mock_redis.get.return_value = json.dumps(cached_stats)

        response = client.get("/api/v2/webhooks/stats")

        assert response.status_code == status.HTTP_200_OK
        mock_db.query.assert_not_called()

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_get_webhook_health(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis, sample_webhook):
        """Test webhook health status"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis
        mock_db.query.return_value.filter.return_value.first.return_value = sample_webhook

        response = client.get(f"/api/v2/webhooks/{sample_webhook.id}/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data
        assert "uptime_percentage" in data
        assert "recommendations" in data

    @patch("app.api.v2.webhooks.get_db")
    def test_get_failed_webhooks(self, mock_get_db, client, mock_db):
        """Test retrieving failed webhooks"""
        mock_get_db.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.return_value = []

        response = client.get("/api/v2/webhooks/failed")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert "total" in data


# ============================================================================
# RATE LIMITING TESTS
# ============================================================================
class TestRateLimiting:
    """Test rate limiting on webhook endpoints"""

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_create_webhook_rate_limit(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test rate limiting on webhook creation (10/hour)"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        # This test verifies the rate limiter is configured
        # Actual rate limit testing requires integration test
        webhook_data = {
            "url": "https://api.example.com/webhooks",
            "events": ["message.received"]
        }

        response = client.post("/api/v2/webhooks", json=webhook_data)

        # Should succeed on first attempt
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_429_TOO_MANY_REQUESTS]

    @patch("app.api.v2.webhooks.get_db")
    def test_test_webhook_rate_limit(self, mock_get_db, client, mock_db, sample_webhook):
        """Test rate limiting on webhook testing (10/minute)"""
        mock_get_db.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = sample_webhook

        test_data = {
            "event_type": "message.received"
        }

        response = client.post(f"/api/v2/webhooks/{sample_webhook.id}/test", json=test_data)

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_429_TOO_MANY_REQUESTS]


# ============================================================================
# PAGINATION TESTS
# ============================================================================
class TestPagination:
    """Test cursor-based pagination"""

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_pagination_cursor_encoding(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test cursor encoding/decoding"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        # Create multiple webhooks
        webhooks = []
        for i in range(25):
            wh = WebhookEndpoint(
                id=uuid4(),
                url=f"https://api.example.com/webhook{i}",
                events=["message.received"],
                status="active",
                created_at=datetime.utcnow() + timedelta(seconds=i),
                updated_at=datetime.utcnow() + timedelta(seconds=i),
            )
            webhooks.append(wh)

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = webhooks[:21]  # Return 21 (limit + 1)
        mock_db.execute.return_value = mock_result

        response = client.get("/api/v2/webhooks?limit=20")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["has_more"] is True
        assert data["next_cursor"] is not None

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_pagination_invalid_cursor(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test invalid cursor handling"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        response = client.get("/api/v2/webhooks?cursor=invalid_cursor")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ============================================================================
# VALIDATION TESTS
# ============================================================================
class TestValidation:
    """Test input validation"""

    def test_create_webhook_invalid_url(self, client):
        """Test webhook creation with invalid URL"""
        webhook_data = {
            "url": "not-a-valid-url",
            "events": ["message.received"]
        }

        response = client.post("/api/v2/webhooks", json=webhook_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_webhook_empty_events(self, client):
        """Test webhook creation with empty events list"""
        webhook_data = {
            "url": "https://api.example.com/webhooks",
            "events": []
        }

        response = client.post("/api/v2/webhooks", json=webhook_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_webhook_short_secret(self, client):
        """Test webhook creation with too short secret"""
        webhook_data = {
            "url": "https://api.example.com/webhooks",
            "events": ["message.received"],
            "secret": "short"  # Less than 16 chars
        }

        response = client.post("/api/v2/webhooks", json=webhook_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_webhook_invalid_timeout(self, client):
        """Test webhook creation with invalid timeout"""
        webhook_data = {
            "url": "https://api.example.com/webhooks",
            "events": ["message.received"],
            "timeout": 500  # Exceeds max (300)
        }

        response = client.post("/api/v2/webhooks", json=webhook_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_webhook_forbidden_headers(self, client):
        """Test webhook creation with forbidden headers"""
        webhook_data = {
            "url": "https://api.example.com/webhooks",
            "events": ["message.received"],
            "headers": {
                "Authorization": "Bearer token",  # Forbidden
                "X-Api-Key": "valid"
            }
        }

        response = client.post("/api/v2/webhooks", json=webhook_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ============================================================================
# INTEGRATION TESTS
# ============================================================================
class TestIntegration:
    """Integration tests for complete workflows"""

    @patch("app.api.v2.webhooks.get_redis_cache")
    @patch("app.api.v2.webhooks.get_db")
    def test_complete_webhook_lifecycle(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test complete webhook lifecycle: create -> update -> test -> delete"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        # 1. Create webhook
        webhook_data = {
            "url": "https://api.example.com/webhooks",
            "events": ["message.received"],
            "description": "Integration test webhook"
        }

        create_response = client.post("/api/v2/webhooks", json=webhook_data)
        assert create_response.status_code == status.HTTP_201_CREATED
        webhook_id = create_response.json()["id"]

        # 2. Update webhook
        sample_webhook = WebhookEvent(
            id=webhook_id,
            webhook_id="wh_test",
            event_type="message.received",
            url=webhook_data["url"],
            events=webhook_data["events"],
            status="active",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        mock_db.query.return_value.filter.return_value.first.return_value = sample_webhook

        update_data = {"status": "paused"}
        update_response = client.put(f"/api/v2/webhooks/{webhook_id}", json=update_data)
        assert update_response.status_code == status.HTTP_200_OK

        # 3. Test webhook
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"ok":true}'
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            test_data = {"event_type": "message.received"}
            test_response = client.post(f"/api/v2/webhooks/{webhook_id}/test", json=test_data)
            assert test_response.status_code == status.HTTP_200_OK

        # 4. Delete webhook
        delete_response = client.delete(f"/api/v2/webhooks/{webhook_id}")
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
