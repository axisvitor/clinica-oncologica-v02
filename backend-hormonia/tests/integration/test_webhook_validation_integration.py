"""
Integration Tests for Webhook Security

Tests webhook validation in realistic scenarios:
- Integration with WhatsApp webhook endpoints
- End-to-end signature validation flow
- Configuration from environment variables
- Error handling and logging
- Performance under load

Author: Hormonia Backend Team
Created: 2025-10-09
"""

import pytest
import time
import asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock

from app.middleware.webhook_validator import (
    WebhookValidatorMiddleware,
    generate_webhook_signature
)
from app.config import Settings


@pytest.fixture
def mock_settings():
    """Mock settings with webhook secret configured."""
    settings = Mock(spec=Settings)
    settings.EVOLUTION_WEBHOOK_SECRET = "test-webhook-secret-32chars-min"
    settings.EVOLUTION_WEBHOOK_URL = "https://api.example.com/webhooks/whatsapp"
    return settings


@pytest.fixture
def app_with_webhooks():
    """Create app with webhook endpoints."""
    app = FastAPI()

    @app.post("/webhooks/whatsapp/evolution/{instance_name}")
    async def evolution_webhook(instance_name: str):
        return {
            "status": "received",
            "instance": instance_name,
            "timestamp": time.time()
        }

    @app.get("/webhooks/whatsapp/health")
    async def webhook_health():
        return {"status": "healthy"}

    return app


class TestWebhookIntegrationBasic:
    """Basic integration tests for webhook validation."""

    def test_evolution_webhook_with_valid_signature(
        self, app_with_webhooks, mock_settings
    ):
        """Test Evolution API webhook with valid signature."""
        # Add middleware with secret from settings
        app_with_webhooks.add_middleware(
            WebhookValidatorMiddleware,
            secret_key=mock_settings.EVOLUTION_WEBHOOK_SECRET
        )
        client = TestClient(app_with_webhooks)

        # Prepare webhook payload
        body = b'{"event": "messages.upsert", "instance": "test_instance"}'
        timestamp = str(int(time.time()))
        signature = generate_webhook_signature(
            body,
            timestamp,
            mock_settings.EVOLUTION_WEBHOOK_SECRET
        )

        # Send webhook request
        response = client.post(
            "/webhooks/whatsapp/evolution/test_instance",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": timestamp
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"
        assert data["instance"] == "test_instance"

    def test_evolution_webhook_without_signature_rejected(
        self, app_with_webhooks, mock_settings
    ):
        """Test Evolution webhook without signature is rejected."""
        app_with_webhooks.add_middleware(
            WebhookValidatorMiddleware,
            secret_key=mock_settings.EVOLUTION_WEBHOOK_SECRET
        )
        client = TestClient(app_with_webhooks)

        # Send webhook without signature
        response = client.post(
            "/webhooks/whatsapp/evolution/test_instance",
            json={"event": "test"}
        )

        assert response.status_code == 401

    def test_health_check_not_validated(self, app_with_webhooks, mock_settings):
        """Test health check endpoint bypasses validation."""
        app_with_webhooks.add_middleware(
            WebhookValidatorMiddleware,
            secret_key=mock_settings.EVOLUTION_WEBHOOK_SECRET
        )
        client = TestClient(app_with_webhooks)

        # Health check should work without signature
        response = client.get("/webhooks/whatsapp/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestWebhookRealisticScenarios:
    """Test realistic webhook scenarios."""

    def test_message_upsert_webhook(self, app_with_webhooks, mock_settings):
        """Test messages.upsert webhook event."""
        app_with_webhooks.add_middleware(
            WebhookValidatorMiddleware,
            secret_key=mock_settings.EVOLUTION_WEBHOOK_SECRET
        )
        client = TestClient(app_with_webhooks)

        # Realistic Evolution API payload
        payload = {
            "event": "messages.upsert",
            "instance": "clinica_oncologica",
            "data": {
                "key": {
                    "remoteJid": "5511999999999@s.whatsapp.net",
                    "fromMe": False,
                    "id": "3EB0C12345ABCDEF"
                },
                "message": {
                    "conversation": "Olá, preciso de ajuda"
                },
                "messageTimestamp": int(time.time())
            }
        }

        import json
        body = json.dumps(payload).encode('utf-8')
        timestamp = str(int(time.time()))
        signature = generate_webhook_signature(
            body,
            timestamp,
            mock_settings.EVOLUTION_WEBHOOK_SECRET
        )

        response = client.post(
            "/webhooks/whatsapp/evolution/clinica_oncologica",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": timestamp,
                "User-Agent": "Evolution-API/1.0"
            }
        )

        assert response.status_code == 200

    def test_connection_update_webhook(self, app_with_webhooks, mock_settings):
        """Test connection.update webhook event."""
        app_with_webhooks.add_middleware(
            WebhookValidatorMiddleware,
            secret_key=mock_settings.EVOLUTION_WEBHOOK_SECRET
        )
        client = TestClient(app_with_webhooks)

        payload = {
            "event": "connection.update",
            "instance": "clinica_oncologica",
            "data": {
                "state": "open",
                "statusReason": 0
            }
        }

        import json
        body = json.dumps(payload).encode('utf-8')
        timestamp = str(int(time.time()))
        signature = generate_webhook_signature(
            body,
            timestamp,
            mock_settings.EVOLUTION_WEBHOOK_SECRET
        )

        response = client.post(
            "/webhooks/whatsapp/evolution/clinica_oncologica",
            content=body,
            headers={
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": timestamp
            }
        )

        assert response.status_code == 200


class TestWebhookPerformance:
    """Test webhook validation performance."""

    def test_signature_validation_performance(
        self, app_with_webhooks, mock_settings
    ):
        """Test that signature validation doesn't add significant overhead."""
        app_with_webhooks.add_middleware(
            WebhookValidatorMiddleware,
            secret_key=mock_settings.EVOLUTION_WEBHOOK_SECRET
        )
        client = TestClient(app_with_webhooks)

        body = b'{"event": "test"}'
        timestamp = str(int(time.time()))
        signature = generate_webhook_signature(
            body,
            timestamp,
            mock_settings.EVOLUTION_WEBHOOK_SECRET
        )

        # Measure time for 100 requests
        import time as time_module
        start = time_module.perf_counter()

        for _ in range(100):
            response = client.post(
                "/webhooks/whatsapp/evolution/test",
                content=body,
                headers={
                    "X-Webhook-Signature": signature,
                    "X-Webhook-Timestamp": timestamp
                }
            )
            assert response.status_code == 200

        elapsed = time_module.perf_counter() - start
        avg_time = elapsed / 100

        # Validation should take less than 10ms per request
        assert avg_time < 0.010, f"Validation too slow: {avg_time*1000:.2f}ms"

    def test_concurrent_webhook_requests(
        self, app_with_webhooks, mock_settings
    ):
        """Test handling concurrent webhook requests."""
        app_with_webhooks.add_middleware(
            WebhookValidatorMiddleware,
            secret_key=mock_settings.EVOLUTION_WEBHOOK_SECRET
        )
        client = TestClient(app_with_webhooks)

        def send_webhook(instance_id: int):
            body = f'{{"event": "test", "id": {instance_id}}}'.encode('utf-8')
            timestamp = str(int(time.time()))
            signature = generate_webhook_signature(
                body,
                timestamp,
                mock_settings.EVOLUTION_WEBHOOK_SECRET
            )

            response = client.post(
                f"/webhooks/whatsapp/evolution/instance_{instance_id}",
                content=body,
                headers={
                    "X-Webhook-Signature": signature,
                    "X-Webhook-Timestamp": timestamp
                }
            )
            return response.status_code

        # Send 10 concurrent requests
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(send_webhook, i) for i in range(10)]
            results = [f.result() for f in futures]

        # All should succeed
        assert all(status == 200 for status in results)


class TestWebhookErrorHandling:
    """Test error handling in webhook validation."""

    def test_malformed_json_body(self, app_with_webhooks, mock_settings):
        """Test handling of malformed JSON in webhook body."""
        app_with_webhooks.add_middleware(
            WebhookValidatorMiddleware,
            secret_key=mock_settings.EVOLUTION_WEBHOOK_SECRET
        )
        client = TestClient(app_with_webhooks)

        # Malformed JSON
        body = b'{invalid json'
        timestamp = str(int(time.time()))
        signature = generate_webhook_signature(
            body,
            timestamp,
            mock_settings.EVOLUTION_WEBHOOK_SECRET
        )

        response = client.post(
            "/webhooks/whatsapp/evolution/test",
            content=body,
            headers={
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": timestamp
            }
        )

        # Signature validation should pass, JSON parsing fails later
        assert response.status_code in [200, 422]

    def test_tampered_webhook_detected(self, app_with_webhooks, mock_settings):
        """Test that tampered webhooks are detected."""
        app_with_webhooks.add_middleware(
            WebhookValidatorMiddleware,
            secret_key=mock_settings.EVOLUTION_WEBHOOK_SECRET
        )
        client = TestClient(app_with_webhooks)

        # Original payload
        original_body = b'{"amount": 10}'
        timestamp = str(int(time.time()))
        signature = generate_webhook_signature(
            original_body,
            timestamp,
            mock_settings.EVOLUTION_WEBHOOK_SECRET
        )

        # Attacker modifies payload
        tampered_body = b'{"amount": 1000}'

        # Try to use original signature with tampered body
        response = client.post(
            "/webhooks/whatsapp/evolution/test",
            content=tampered_body,
            headers={
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": timestamp
            }
        )

        # Should be rejected
        assert response.status_code == 401

    def test_replay_attack_detected(self, app_with_webhooks, mock_settings):
        """Test that replay attacks are detected."""
        app_with_webhooks.add_middleware(
            WebhookValidatorMiddleware,
            secret_key=mock_settings.EVOLUTION_WEBHOOK_SECRET,
            max_timestamp_age=60  # Short window for testing
        )
        client = TestClient(app_with_webhooks)

        # Old webhook (2 minutes ago)
        body = b'{"event": "old_webhook"}'
        old_timestamp = str(int(time.time()) - 120)
        signature = generate_webhook_signature(
            body,
            old_timestamp,
            mock_settings.EVOLUTION_WEBHOOK_SECRET
        )

        # Try to replay old webhook
        response = client.post(
            "/webhooks/whatsapp/evolution/test",
            content=body,
            headers={
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": old_timestamp
            }
        )

        # Should be rejected as expired
        assert response.status_code == 401


class TestWebhookLogging:
    """Test webhook validation logging."""

    def test_successful_validation_logged(
        self, app_with_webhooks, mock_settings, caplog
    ):
        """Test that successful validation is logged."""
        import logging
        caplog.set_level(logging.INFO)

        app_with_webhooks.add_middleware(
            WebhookValidatorMiddleware,
            secret_key=mock_settings.EVOLUTION_WEBHOOK_SECRET
        )
        client = TestClient(app_with_webhooks)

        body = b'{"event": "test"}'
        timestamp = str(int(time.time()))
        signature = generate_webhook_signature(
            body,
            timestamp,
            mock_settings.EVOLUTION_WEBHOOK_SECRET
        )

        client.post(
            "/webhooks/whatsapp/evolution/test",
            content=body,
            headers={
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": timestamp
            }
        )

        # Check for success log
        assert any("signature validated" in record.message.lower()
                  for record in caplog.records)

    def test_failed_validation_logged(
        self, app_with_webhooks, mock_settings, caplog
    ):
        """Test that failed validation is logged."""
        import logging
        caplog.set_level(logging.ERROR)

        app_with_webhooks.add_middleware(
            WebhookValidatorMiddleware,
            secret_key=mock_settings.EVOLUTION_WEBHOOK_SECRET
        )
        client = TestClient(app_with_webhooks)

        # Invalid signature
        client.post(
            "/webhooks/whatsapp/evolution/test",
            json={"event": "test"},
            headers={
                "X-Webhook-Signature": "invalid-signature",
                "X-Webhook-Timestamp": str(int(time.time()))
            }
        )

        # Check for error log
        assert any("signature validation failed" in record.message.lower()
                  for record in caplog.records)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
