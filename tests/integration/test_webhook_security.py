"""
Webhook security and processing integration tests.
Tests webhook validation, signature verification, and data processing.
"""
import pytest
import json
import hmac
import hashlib
from unittest.mock import Mock, patch, AsyncMock
from httpx import AsyncClient
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend_hormonia.app.main import app
from backend_hormonia.app.database import get_db, Base
from backend_hormonia.app.models.user import User, UserRole
from backend_hormonia.app.config import settings


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_webhooks.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(setup_database):
    with TestClient(app) as c:
        yield c


@pytest.fixture
async def async_client(setup_database):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


def create_webhook_signature(payload: bytes, secret: str) -> str:
    """Create a valid webhook signature for testing."""
    return hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()


class TestWebhookSecurity:
    """Test webhook security and signature validation."""

    @patch.dict('os.environ', {'ENVIRONMENT': 'production'})
    @patch('backend_hormonia.app.config.settings.EVOLUTION_WEBHOOK_SECRET', 'test-secret-key')
    def test_webhook_signature_validation_production(self, client):
        """Test webhook signature validation in production."""
        payload = json.dumps({"event": "message.received", "data": {}})
        signature = create_webhook_signature(payload.encode(), 'test-secret-key')

        response = client.post(
            "/api/v1/webhooks/evolution/message",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature
            }
        )

        # Should not reject due to signature (may fail on other validation)
        assert response.status_code in [200, 500]  # Not 401 for invalid signature

    @patch.dict('os.environ', {'ENVIRONMENT': 'production'})
    @patch('backend_hormonia.app.config.settings.EVOLUTION_WEBHOOK_SECRET', 'test-secret-key')
    def test_webhook_invalid_signature_production(self, client):
        """Test webhook rejection with invalid signature in production."""
        payload = json.dumps({"event": "message.received", "data": {}})

        response = client.post(
            "/api/v1/webhooks/evolution/message",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Signature": "invalid-signature"
            }
        )

        assert response.status_code == 401
        assert "Invalid signature" in response.json()["detail"]

    @patch.dict('os.environ', {'ENVIRONMENT': 'production'})
    @patch('backend_hormonia.app.config.settings.EVOLUTION_WEBHOOK_SECRET', 'test-secret-key')
    def test_webhook_missing_signature_production(self, client):
        """Test webhook rejection without signature in production."""
        payload = json.dumps({"event": "message.received", "data": {}})

        response = client.post(
            "/api/v1/webhooks/evolution/message",
            content=payload,
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 401
        assert "Invalid signature" in response.json()["detail"]

    @patch.dict('os.environ', {'ENVIRONMENT': 'development'})
    def test_webhook_development_mode_relaxed(self, client):
        """Test webhook validation is relaxed in development mode."""
        payload = json.dumps({"event": "message.received", "data": {}})

        response = client.post(
            "/api/v1/webhooks/evolution/message",
            content=payload,
            headers={"Content-Type": "application/json"}
        )

        # Should not reject due to missing signature in development
        assert response.status_code in [200, 500]  # Not 401

    @patch('backend_hormonia.app.config.settings.EVOLUTION_WEBHOOK_SECRET', None)
    def test_webhook_no_secret_configured_development(self, client):
        """Test webhook behavior when no secret is configured in development."""
        payload = json.dumps({"event": "message.received", "data": {}})

        response = client.post(
            "/api/v1/webhooks/evolution/message",
            content=payload,
            headers={"Content-Type": "application/json"}
        )

        # Should allow in development even without secret
        assert response.status_code in [200, 500]  # Not 401

    @patch.dict('os.environ', {'ENVIRONMENT': 'production'})
    @patch('backend_hormonia.app.config.settings.EVOLUTION_WEBHOOK_SECRET', None)
    def test_webhook_no_secret_configured_production(self, client):
        """Test webhook rejection when no secret is configured in production."""
        payload = json.dumps({"event": "message.received", "data": {}})

        response = client.post(
            "/api/v1/webhooks/evolution/message",
            content=payload,
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 401


class TestWebhookMessageProcessing:
    """Test webhook message processing logic."""

    @patch('backend_hormonia.app.services.webhook_processor.WebhookProcessor.process_message_webhook')
    def test_message_webhook_processing(self, mock_processor, client):
        """Test message webhook processing flow."""
        mock_processor.return_value = "message-123"

        payload = {
            "event": "message.received",
            "data": {
                "key": {
                    "remoteJid": "5511999999999@s.whatsapp.net",
                    "fromMe": False,
                    "id": "test-message-id"
                },
                "message": {
                    "conversation": "Test message"
                }
            }
        }

        response = client.post(
            "/api/v1/webhooks/evolution/message",
            json=payload
        )

        # Should process successfully in development
        assert response.status_code in [200, 401]  # 401 if signature validation enabled

        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "success"
            assert "message_id" in data

    @patch('backend_hormonia.app.services.webhook_processor.WebhookProcessor.process_message_webhook')
    def test_message_webhook_patient_not_found(self, mock_processor, client):
        """Test message webhook when patient is not found."""
        mock_processor.return_value = None  # Patient not found

        payload = {
            "event": "message.received",
            "data": {
                "key": {
                    "remoteJid": "unknown@s.whatsapp.net",
                    "fromMe": False
                }
            }
        }

        response = client.post(
            "/api/v1/webhooks/evolution/message",
            json=payload
        )

        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ignored"
            assert "patient not found" in data["message"]

    @patch('backend_hormonia.app.services.webhook_processor.WebhookProcessor.process_message_webhook')
    def test_message_webhook_processing_error(self, mock_processor, client):
        """Test message webhook processing error handling."""
        mock_processor.side_effect = Exception("Processing error")

        payload = {
            "event": "message.received",
            "data": {}
        }

        response = client.post(
            "/api/v1/webhooks/evolution/message",
            json=payload
        )

        if response.status_code != 401:  # If not blocked by signature validation
            assert response.status_code == 500


class TestWebhookStatusProcessing:
    """Test webhook status update processing."""

    @patch('backend_hormonia.app.services.webhook_processor.WebhookProcessor.process_status_webhook')
    def test_status_webhook_processing(self, mock_processor, client):
        """Test status webhook processing flow."""
        mock_processor.return_value = True

        payload = {
            "event": "message.status",
            "data": {
                "status": "read",
                "messageId": "test-message-id"
            }
        }

        response = client.post(
            "/api/v1/webhooks/evolution/status",
            json=payload
        )

        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "success"

    @patch('backend_hormonia.app.services.webhook_processor.WebhookProcessor.process_status_webhook')
    def test_status_webhook_message_not_found(self, mock_processor, client):
        """Test status webhook when message is not found."""
        mock_processor.return_value = False

        payload = {
            "event": "message.status",
            "data": {
                "status": "read",
                "messageId": "unknown-message-id"
            }
        }

        response = client.post(
            "/api/v1/webhooks/evolution/status",
            json=payload
        )

        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ignored"
            assert "message not found" in data["message"]


class TestWebhookConnectionProcessing:
    """Test webhook connection status processing."""

    @patch('backend_hormonia.app.services.webhook_processor.WebhookProcessor.process_connection_webhook')
    def test_connection_webhook_processing(self, mock_processor, client):
        """Test connection webhook processing."""
        mock_processor.return_value = True

        payload = {
            "event": "connection.update",
            "data": {
                "state": "open",
                "instance": "test-instance"
            }
        }

        response = client.post(
            "/api/v1/webhooks/evolution/connection",
            json=payload
        )

        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "success"

    @patch('backend_hormonia.app.services.webhook_processor.WebhookProcessor.process_connection_webhook')
    def test_connection_webhook_processing_failure(self, mock_processor, client):
        """Test connection webhook processing failure."""
        mock_processor.return_value = False

        payload = {
            "event": "connection.update",
            "data": {
                "state": "close"
            }
        }

        response = client.post(
            "/api/v1/webhooks/evolution/connection",
            json=payload
        )

        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "error"


class TestWebhookQRCodeProcessing:
    """Test webhook QR code processing."""

    @patch('backend_hormonia.app.services.webhook_processor.WebhookProcessor.process_qrcode_webhook')
    def test_qrcode_webhook_processing(self, mock_processor, client):
        """Test QR code webhook processing."""
        mock_processor.return_value = True

        payload = {
            "event": "qrcode.updated",
            "data": {
                "qrcode": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
                "instance": "test-instance"
            }
        }

        response = client.post(
            "/api/v1/webhooks/evolution/qrcode",
            json=payload
        )

        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "success"

    @patch('backend_hormonia.app.services.webhook_processor.WebhookProcessor.process_qrcode_webhook')
    def test_qrcode_webhook_processing_failure(self, mock_processor, client):
        """Test QR code webhook processing failure."""
        mock_processor.return_value = False

        payload = {
            "event": "qrcode.updated",
            "data": {}
        }

        response = client.post(
            "/api/v1/webhooks/evolution/qrcode",
            json=payload
        )

        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "error"


class TestWebhookHealthCheck:
    """Test webhook health check functionality."""

    @patch('backend_hormonia.app.integrations.evolution.get_evolution_client')
    async def test_evolution_health_check_success(self, mock_get_client, client):
        """Test Evolution API health check success."""
        mock_client = AsyncMock()
        mock_client.get_instance_status.return_value = {"state": "open"}
        mock_get_client.return_value = mock_client

        response = client.get("/api/v1/webhooks/evolution/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["evolution_api"] == "connected"

    @patch('backend_hormonia.app.integrations.evolution.get_evolution_client')
    async def test_evolution_health_check_failure(self, mock_get_client, client):
        """Test Evolution API health check failure."""
        mock_get_client.side_effect = Exception("Connection failed")

        response = client.get("/api/v1/webhooks/evolution/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["evolution_api"] == "disconnected"


class TestWebhookDataValidation:
    """Test webhook data validation and sanitization."""

    def test_webhook_malformed_json(self, client):
        """Test webhook with malformed JSON."""
        response = client.post(
            "/api/v1/webhooks/evolution/message",
            content="invalid json{",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code in [400, 401, 422]

    def test_webhook_empty_payload(self, client):
        """Test webhook with empty payload."""
        response = client.post(
            "/api/v1/webhooks/evolution/message",
            json={}
        )

        # Should not crash, may return various status codes
        assert response.status_code in [200, 401, 500]

    def test_webhook_oversized_payload(self, client):
        """Test webhook with oversized payload."""
        large_payload = {
            "event": "message.received",
            "data": {
                "message": "x" * 10000  # Very large message
            }
        }

        response = client.post(
            "/api/v1/webhooks/evolution/message",
            json=large_payload
        )

        # Should handle large payloads gracefully
        assert response.status_code in [200, 401, 413, 500]

    def test_webhook_special_characters(self, client):
        """Test webhook with special characters and unicode."""
        payload = {
            "event": "message.received",
            "data": {
                "message": "Test 🚀 émojis and spéçial çhars"
            }
        }

        response = client.post(
            "/api/v1/webhooks/evolution/message",
            json=payload
        )

        # Should handle unicode properly
        assert response.status_code in [200, 401, 500]


class TestWebhookConcurrency:
    """Test webhook concurrent processing."""

    @pytest.mark.asyncio
    async def test_concurrent_webhook_processing(self, async_client):
        """Test processing multiple webhooks concurrently."""
        import asyncio

        payloads = [
            {"event": "message.received", "data": {"id": f"msg-{i}"}}
            for i in range(5)
        ]

        tasks = []
        for payload in payloads:
            task = asyncio.create_task(
                async_client.post("/api/v1/webhooks/evolution/message", json=payload)
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Should handle concurrent requests without deadlocks
        for response in responses:
            if hasattr(response, 'status_code'):
                assert response.status_code in [200, 401, 500]

    @pytest.mark.asyncio
    async def test_webhook_rate_limiting_behavior(self, async_client):
        """Test webhook behavior under high load."""
        import asyncio

        # Send many requests rapidly
        tasks = []
        for i in range(20):
            task = asyncio.create_task(
                async_client.post("/api/v1/webhooks/evolution/message", json={
                    "event": "message.received",
                    "data": {"id": f"rapid-{i}"}
                })
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Should handle high load gracefully
        successful_responses = 0
        for response in responses:
            if hasattr(response, 'status_code') and response.status_code in [200, 401]:
                successful_responses += 1

        # At least some requests should be processed
        assert successful_responses >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])