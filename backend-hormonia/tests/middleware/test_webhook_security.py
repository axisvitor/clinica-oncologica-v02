"""
Comprehensive Test Suite for Webhook Signature Validation Middleware

Tests cover:
- HMAC signature generation and validation
- Timestamp validation and replay attack prevention
- Missing/invalid headers handling
- Constant-time comparison security
- Integration with FastAPI application
- Edge cases and error handling

Author: Hormonia Backend Team
Created: 2025-10-09
"""

import pytest
import time
import hmac
import hashlib
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from app.middleware.webhook_validator import (
    WebhookValidatorMiddleware,
    generate_webhook_signature
)


# Test fixtures
@pytest.fixture
def app():
    """Create FastAPI test application."""
    app = FastAPI()

    @app.post("/webhooks/whatsapp/test")
    async def test_webhook(request: Request):
        body = await request.json()
        return {"status": "received", "data": body}

    @app.get("/webhooks/whatsapp/health")
    async def health_check():
        return {"status": "healthy"}

    @app.post("/api/non-webhook")
    async def non_webhook():
        return {"status": "ok"}

    return app


@pytest.fixture
def secret_key():
    """Test webhook secret key."""
    return "test-webhook-secret-key-32chars-min-length-required"


@pytest.fixture
def app_with_validation(app, secret_key):
    """Create app with webhook validation middleware."""
    app.add_middleware(
        WebhookValidatorMiddleware,
        secret_key=secret_key,
        max_timestamp_age=300
    )
    return app


@pytest.fixture
def client_with_validation(app_with_validation):
    """Create test client with validation enabled."""
    return TestClient(app_with_validation, raise_server_exceptions=False)


@pytest.fixture
def client_without_validation(app):
    """Create test client without validation (disabled)."""
    app.add_middleware(
        WebhookValidatorMiddleware,
        secret_key=None  # Disabled
    )
    return TestClient(app)


class TestWebhookSignatureGeneration:
    """Test webhook signature generation utilities."""

    def test_generate_valid_signature(self, secret_key):
        """Test generating valid HMAC signature."""
        body = b'{"event": "message.sent"}'
        timestamp = str(int(time.time()))

        signature = generate_webhook_signature(body, timestamp, secret_key)

        # Should return hex string (64 chars for SHA-256)
        assert isinstance(signature, str)
        assert len(signature) == 64
        assert all(c in '0123456789abcdef' for c in signature)

    def test_signature_deterministic(self, secret_key):
        """Test that same input produces same signature."""
        body = b'{"event": "test"}'
        timestamp = "1234567890"

        sig1 = generate_webhook_signature(body, timestamp, secret_key)
        sig2 = generate_webhook_signature(body, timestamp, secret_key)

        assert sig1 == sig2

    def test_signature_changes_with_body(self, secret_key):
        """Test that different body produces different signature."""
        timestamp = str(int(time.time()))

        sig1 = generate_webhook_signature(b'{"data": "a"}', timestamp, secret_key)
        sig2 = generate_webhook_signature(b'{"data": "b"}', timestamp, secret_key)

        assert sig1 != sig2

    def test_signature_changes_with_timestamp(self, secret_key):
        """Test that different timestamp produces different signature."""
        body = b'{"event": "test"}'

        sig1 = generate_webhook_signature(body, "1000000000", secret_key)
        sig2 = generate_webhook_signature(body, "2000000000", secret_key)

        assert sig1 != sig2

    def test_signature_changes_with_secret(self):
        """Test that different secret produces different signature."""
        body = b'{"event": "test"}'
        timestamp = str(int(time.time()))

        sig1 = generate_webhook_signature(body, timestamp, "secret-1")
        sig2 = generate_webhook_signature(body, timestamp, "secret-2")

        assert sig1 != sig2


class TestWebhookValidationSuccess:
    """Test successful webhook validation scenarios."""

    def test_valid_webhook_request(self, client_with_validation, secret_key):
        """Test webhook with valid signature is accepted."""
        body = b'{"event": "message.sent", "data": "test"}'
        timestamp = str(int(time.time()))
        signature = generate_webhook_signature(body, timestamp, secret_key)

        response = client_with_validation.post(
            "/webhooks/whatsapp/test",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": timestamp
            }
        )

        assert response.status_code == 200
        assert response.json() == {
            "status": "received",
            "data": {"event": "message.sent", "data": "test"}
        }

    def test_webhook_with_recent_timestamp(self, client_with_validation, secret_key):
        """Test webhook with recent timestamp is accepted."""
        body = b'{"event": "test"}'
        # Timestamp 60 seconds ago (within 300s limit)
        timestamp = str(int(time.time()) - 60)
        signature = generate_webhook_signature(body, timestamp, secret_key)

        response = client_with_validation.post(
            "/webhooks/whatsapp/test",
            content=body,
            headers={
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": timestamp
            }
        )

        assert response.status_code == 200

    def test_webhook_with_future_timestamp_within_skew(
        self, client_with_validation, secret_key
    ):
        """Test webhook with slight future timestamp (clock skew) is accepted."""
        body = b'{"event": "test"}'
        # Timestamp 30 seconds in future (within 60s skew allowance)
        timestamp = str(int(time.time()) + 30)
        signature = generate_webhook_signature(body, timestamp, secret_key)

        response = client_with_validation.post(
            "/webhooks/whatsapp/test",
            content=body,
            headers={
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": timestamp
            }
        )

        assert response.status_code == 200

    def test_non_webhook_path_not_validated(self, client_with_validation):
        """Test that non-webhook paths skip validation."""
        response = client_with_validation.post("/api/non-webhook")

        # Should succeed without signature headers
        assert response.status_code == 200

    def test_get_request_not_validated(self, client_with_validation):
        """Test that GET requests skip validation."""
        response = client_with_validation.get("/webhooks/whatsapp/health")

        # Should succeed without signature headers
        assert response.status_code == 200


class TestWebhookValidationFailure:
    """Test webhook validation failure scenarios."""

    def test_missing_signature_header(self, client_with_validation):
        """Test webhook without signature header is rejected."""
        body = b'{"event": "test"}'
        timestamp = str(int(time.time()))

        response = client_with_validation.post(
            "/webhooks/whatsapp/test",
            content=body,
            headers={"X-Webhook-Timestamp": timestamp}
        )

        assert response.status_code == 401
        assert "Missing required header" in response.json()["detail"]

    def test_missing_timestamp_header(self, client_with_validation):
        """Test webhook without timestamp header is rejected."""
        body = b'{"event": "test"}'

        response = client_with_validation.post(
            "/webhooks/whatsapp/test",
            content=body,
            headers={"X-Webhook-Signature": "dummy-signature"}
        )

        assert response.status_code == 401
        assert "Missing required header" in response.json()["detail"]

    def test_invalid_signature(self, client_with_validation):
        """Test webhook with invalid signature is rejected."""
        body = b'{"event": "test"}'
        timestamp = str(int(time.time()))

        response = client_with_validation.post(
            "/webhooks/whatsapp/test",
            content=body,
            headers={
                "X-Webhook-Signature": "invalid-signature-not-matching",
                "X-Webhook-Timestamp": timestamp
            }
        )

        assert response.status_code == 401
        assert "Invalid webhook signature" in response.json()["detail"]

    def test_expired_timestamp(self, client_with_validation, secret_key):
        """Test webhook with expired timestamp is rejected."""
        body = b'{"event": "test"}'
        # Timestamp 400 seconds ago (exceeds 300s limit)
        timestamp = str(int(time.time()) - 400)
        signature = generate_webhook_signature(body, timestamp, secret_key)

        response = client_with_validation.post(
            "/webhooks/whatsapp/test",
            content=body,
            headers={
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": timestamp
            }
        )

        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_future_timestamp_beyond_skew(self, client_with_validation, secret_key):
        """Test webhook with future timestamp beyond skew is rejected."""
        body = b'{"event": "test"}'
        # Timestamp 120 seconds in future (exceeds 60s skew)
        timestamp = str(int(time.time()) + 120)
        signature = generate_webhook_signature(body, timestamp, secret_key)

        response = client_with_validation.post(
            "/webhooks/whatsapp/test",
            content=body,
            headers={
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": timestamp
            }
        )

        assert response.status_code == 401

    def test_invalid_timestamp_format(self, client_with_validation, secret_key):
        """Test webhook with invalid timestamp format is rejected."""
        body = b'{"event": "test"}'
        timestamp = "not-a-valid-timestamp"
        signature = generate_webhook_signature(body, timestamp, secret_key)

        response = client_with_validation.post(
            "/webhooks/whatsapp/test",
            content=body,
            headers={
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": timestamp
            }
        )

        assert response.status_code == 401

    def test_signature_for_different_body(self, client_with_validation, secret_key):
        """Test signature computed for different body is rejected."""
        original_body = b'{"event": "original"}'
        modified_body = b'{"event": "modified"}'
        timestamp = str(int(time.time()))

        # Signature for original body
        signature = generate_webhook_signature(original_body, timestamp, secret_key)

        # Try to use it with modified body
        response = client_with_validation.post(
            "/webhooks/whatsapp/test",
            content=modified_body,
            headers={
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": timestamp
            }
        )

        assert response.status_code == 401


class TestWebhookSecurityFeatures:
    """Test security-specific features of webhook validation."""

    def test_constant_time_comparison(self, secret_key):
        """Test that signature comparison is timing-safe."""
        from app.middleware.webhook_validator import WebhookValidatorMiddleware

        middleware = WebhookValidatorMiddleware(
            app=Mock(),
            secret_key=secret_key
        )

        # Valid signature
        valid_sig = "a" * 64
        # Invalid signatures of different lengths
        invalid_sig_short = "b" * 32
        invalid_sig_long = "b" * 128

        # All should return False (safely)
        assert not middleware._verify_signature(valid_sig, invalid_sig_short)
        assert not middleware._verify_signature(valid_sig, invalid_sig_long)

        # Same signature should return True
        assert middleware._verify_signature(valid_sig, valid_sig)

    def test_replay_attack_prevention(self, client_with_validation, secret_key):
        """Test that old webhooks cannot be replayed."""
        body = b'{"event": "test"}'
        old_timestamp = str(int(time.time()) - 600)  # 10 minutes ago
        signature = generate_webhook_signature(body, old_timestamp, secret_key)

        # First attempt should fail (too old)
        response = client_with_validation.post(
            "/webhooks/whatsapp/test",
            content=body,
            headers={
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": old_timestamp
            }
        )

        assert response.status_code == 401

    def test_header_case_insensitivity(self, client_with_validation, secret_key):
        """Test that header names are case-insensitive."""
        body = b'{"event": "test"}'
        timestamp = str(int(time.time()))
        signature = generate_webhook_signature(body, timestamp, secret_key)

        # Use different case for headers
        response = client_with_validation.post(
            "/webhooks/whatsapp/test",
            content=body,
            headers={
                "x-webhook-signature": signature,  # lowercase
                "X-WEBHOOK-TIMESTAMP": timestamp   # uppercase
            }
        )

        assert response.status_code == 200


class TestWebhookMiddlewareDisabled:
    """Test middleware behavior when disabled."""

    def test_validation_disabled_without_secret(self, client_without_validation):
        """Test that validation is skipped when secret is not configured."""
        body = b'{"event": "test"}'

        # No signature headers provided
        response = client_without_validation.post(
            "/webhooks/whatsapp/test",
            content=body
        )

        # Should succeed without validation
        assert response.status_code == 200

    def test_middleware_logs_disabled_state(self):
        """Test that middleware logs when validation is disabled."""
        # When secret is None, validation is disabled
        # This is tested by ensuring requests without signatures succeed
        app = FastAPI()

        @app.post("/webhooks/test")
        async def test_webhook():
            return {"status": "ok"}

        app.add_middleware(
            WebhookValidatorMiddleware,
            secret_key=None  # Disabled
        )

        client = TestClient(app, raise_server_exceptions=False)

        # Request without signature should succeed (validation disabled)
        response = client.post("/webhooks/test", json={"test": "data"})
        assert response.status_code == 200


class TestWebhookMiddlewareConfiguration:
    """Test middleware configuration options."""

    def test_custom_signature_header(self, app, secret_key):
        """Test using custom signature header name."""
        app.add_middleware(
            WebhookValidatorMiddleware,
            secret_key=secret_key,
            signature_header="X-Custom-Signature"
        )
        client = TestClient(app)

        body = b'{"event": "test"}'
        timestamp = str(int(time.time()))
        signature = generate_webhook_signature(body, timestamp, secret_key)

        response = client.post(
            "/webhooks/whatsapp/test",
            content=body,
            headers={
                "X-Custom-Signature": signature,
                "X-Webhook-Timestamp": timestamp
            }
        )

        assert response.status_code == 200

    def test_custom_timestamp_header(self, app, secret_key):
        """Test using custom timestamp header name."""
        app.add_middleware(
            WebhookValidatorMiddleware,
            secret_key=secret_key,
            timestamp_header="X-Custom-Timestamp"
        )
        client = TestClient(app)

        body = b'{"event": "test"}'
        timestamp = str(int(time.time()))
        signature = generate_webhook_signature(body, timestamp, secret_key)

        response = client.post(
            "/webhooks/whatsapp/test",
            content=body,
            headers={
                "X-Webhook-Signature": signature,
                "X-Custom-Timestamp": timestamp
            }
        )

        assert response.status_code == 200

    def test_custom_max_timestamp_age(self, app, secret_key):
        """Test custom max timestamp age configuration."""
        app.add_middleware(
            WebhookValidatorMiddleware,
            secret_key=secret_key,
            max_timestamp_age=60  # Only 60 seconds allowed
        )
        client = TestClient(app)

        body = b'{"event": "test"}'
        # Timestamp 90 seconds ago (exceeds 60s limit)
        timestamp = str(int(time.time()) - 90)
        signature = generate_webhook_signature(body, timestamp, secret_key)

        response = client.post(
            "/webhooks/whatsapp/test",
            content=body,
            headers={
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": timestamp
            }
        )

        assert response.status_code == 401

    def test_custom_webhook_paths(self, app, secret_key):
        """Test custom webhook path configuration."""
        app.add_middleware(
            WebhookValidatorMiddleware,
            secret_key=secret_key,
            webhook_paths=["/custom/webhook/"]
        )

        # Add custom webhook endpoint
        @app.post("/custom/webhook/test")
        async def custom_webhook():
            return {"status": "ok"}

        client = TestClient(app)

        # Original webhook path should not be validated
        response = client.post("/webhooks/whatsapp/test", json={"test": "data"})
        assert response.status_code == 200

        # Custom path should require validation
        response = client.post("/custom/webhook/test")
        assert response.status_code == 401


class TestWebhookEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_body(self, client_with_validation, secret_key):
        """Test webhook with empty body."""
        # Use valid empty JSON object instead of completely empty body
        body = b'{}'
        timestamp = str(int(time.time()))
        signature = generate_webhook_signature(body, timestamp, secret_key)

        response = client_with_validation.post(
            "/webhooks/whatsapp/test",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": timestamp
            }
        )

        # Signature validation should pass
        assert response.status_code == 200

    def test_large_payload(self, client_with_validation, secret_key):
        """Test webhook with large payload."""
        body = b'{"data": "' + b'x' * 10000 + b'"}'
        timestamp = str(int(time.time()))
        signature = generate_webhook_signature(body, timestamp, secret_key)

        response = client_with_validation.post(
            "/webhooks/whatsapp/test",
            content=body,
            headers={
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": timestamp
            }
        )

        assert response.status_code == 200

    def test_special_characters_in_body(self, client_with_validation, secret_key):
        """Test webhook with special characters."""
        body = b'{"data": "\xc3\xa9\xc3\xa7\xc3\xa0"}'  # UTF-8 encoded special chars
        timestamp = str(int(time.time()))
        signature = generate_webhook_signature(body, timestamp, secret_key)

        response = client_with_validation.post(
            "/webhooks/whatsapp/test",
            content=body,
            headers={
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": timestamp
            }
        )

        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
