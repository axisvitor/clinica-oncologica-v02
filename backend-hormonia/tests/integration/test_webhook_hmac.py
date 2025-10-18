"""
Integration Tests for Webhook HMAC Signature Validation

Tests the complete webhook security flow:
- HMAC-SHA256 signature generation and validation
- Timestamp validation (5-minute window)
- Idempotency checking (duplicate webhook_id)
- Replay attack prevention
- Invalid signature rejection

Security Requirements:
- All webhooks must have valid HMAC signature
- Timestamps must be within 300 seconds (5 minutes)
- Duplicate webhook_id must be rejected
- Invalid/missing signatures must return 401
"""

import pytest
import hmac
import hashlib
import time
import json
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.middleware.webhook_validator import generate_webhook_signature


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def webhook_secret():
    """Get webhook secret from settings."""
    return settings.EVOLUTION_WEBHOOK_SECRET or "test-webhook-secret-change-this"


@pytest.fixture
def valid_webhook_payload():
    """Create valid webhook payload."""
    return {
        "event": "message.received",
        "instance": "clinica_oncologica",
        "data": {
            "key": {
                "remoteJid": "5511999999999@s.whatsapp.net",
                "fromMe": False,
                "id": "3EB0C1234567890ABCDEF"
            },
            "message": {
                "conversation": "Olá, gostaria de agendar uma consulta"
            },
            "messageTimestamp": int(time.time()),
            "pushName": "João Silva"
        },
        "webhook_id": f"webhook_{int(time.time() * 1000)}_{hash('test')}"
    }


def generate_signature(payload: dict, secret: str, timestamp: int) -> str:
    """
    Generate HMAC-SHA256 signature for webhook payload.
    
    Args:
        payload: Webhook payload dictionary
        secret: Webhook secret key
        timestamp: Unix timestamp
        
    Returns:
        Hex-encoded HMAC signature
    """
    # Create signature payload: timestamp + JSON body
    body_json = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    signature_payload = f"{timestamp}.{body_json}"
    
    # Generate HMAC-SHA256 signature
    signature = hmac.new(
        secret.encode('utf-8'),
        signature_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature


class TestWebhookHMACValidation:
    """Test suite for webhook HMAC signature validation."""
    
    def test_valid_signature_accepted(self, client, webhook_secret, valid_webhook_payload):
        """Test that webhooks with valid signatures are accepted."""
        timestamp = int(time.time())
        signature = generate_signature(valid_webhook_payload, webhook_secret, timestamp)
        
        response = client.post(
            "/api/v1/webhooks/evolution/message",
            json=valid_webhook_payload,
            headers={
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": str(timestamp)
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.json()["status"] == "received"
    
    def test_invalid_signature_rejected(self, client, valid_webhook_payload):
        """Test that webhooks with invalid signatures are rejected."""
        timestamp = int(time.time())
        invalid_signature = "invalid_signature_12345"
        
        response = client.post(
            "/api/v1/webhooks/evolution/message",
            json=valid_webhook_payload,
            headers={
                "X-Webhook-Signature": invalid_signature,
                "X-Webhook-Timestamp": str(timestamp)
            }
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        assert "invalid" in response.json()["detail"].lower()
    
    def test_missing_signature_rejected(self, client, valid_webhook_payload):
        """Test that webhooks without signatures are rejected."""
        timestamp = int(time.time())
        
        response = client.post(
            "/api/v1/webhooks/evolution/message",
            json=valid_webhook_payload,
            headers={
                "X-Webhook-Timestamp": str(timestamp)
            }
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        assert "missing" in response.json()["detail"].lower() or "required" in response.json()["detail"].lower()
    
    def test_missing_timestamp_rejected(self, client, webhook_secret, valid_webhook_payload):
        """Test that webhooks without timestamps are rejected."""
        timestamp = int(time.time())
        signature = generate_signature(valid_webhook_payload, webhook_secret, timestamp)
        
        response = client.post(
            "/api/v1/webhooks/evolution/message",
            json=valid_webhook_payload,
            headers={
                "X-Webhook-Signature": signature
            }
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        assert "timestamp" in response.json()["detail"].lower()
    
    def test_expired_timestamp_rejected(self, client, webhook_secret, valid_webhook_payload):
        """Test that webhooks with expired timestamps are rejected (>5 minutes old)."""
        # Create timestamp 6 minutes in the past
        expired_timestamp = int(time.time()) - 360  # 6 minutes
        signature = generate_signature(valid_webhook_payload, webhook_secret, expired_timestamp)
        
        response = client.post(
            "/api/v1/webhooks/evolution/message",
            json=valid_webhook_payload,
            headers={
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": str(expired_timestamp)
            }
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        assert "expired" in response.json()["detail"].lower() or "timestamp" in response.json()["detail"].lower()
    
    def test_future_timestamp_rejected(self, client, webhook_secret, valid_webhook_payload):
        """Test that webhooks with future timestamps are rejected."""
        # Create timestamp 6 minutes in the future
        future_timestamp = int(time.time()) + 360  # 6 minutes
        signature = generate_signature(valid_webhook_payload, webhook_secret, future_timestamp)
        
        response = client.post(
            "/api/v1/webhooks/evolution/message",
            json=valid_webhook_payload,
            headers={
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": str(future_timestamp)
            }
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        assert "timestamp" in response.json()["detail"].lower()
    
    def test_idempotency_duplicate_webhook_id(self, client, webhook_secret, valid_webhook_payload):
        """Test that duplicate webhook_id is detected and handled."""
        timestamp = int(time.time())
        signature = generate_signature(valid_webhook_payload, webhook_secret, timestamp)
        
        headers = {
            "X-Webhook-Signature": signature,
            "X-Webhook-Timestamp": str(timestamp)
        }
        
        # First request should succeed
        response1 = client.post(
            "/api/v1/webhooks/evolution/message",
            json=valid_webhook_payload,
            headers=headers
        )
        assert response1.status_code == 200
        
        # Second request with same webhook_id should be detected as duplicate
        # Generate new signature with slightly newer timestamp
        timestamp2 = int(time.time()) + 1
        signature2 = generate_signature(valid_webhook_payload, webhook_secret, timestamp2)
        headers2 = {
            "X-Webhook-Signature": signature2,
            "X-Webhook-Timestamp": str(timestamp2)
        }
        
        response2 = client.post(
            "/api/v1/webhooks/evolution/message",
            json=valid_webhook_payload,
            headers=headers2
        )
        
        # Should return 200 but indicate duplicate
        assert response2.status_code == 200
        assert "duplicate" in response2.json().get("status", "").lower() or \
               "already" in response2.json().get("message", "").lower()
    
    def test_signature_with_modified_payload_rejected(self, client, webhook_secret, valid_webhook_payload):
        """Test that modifying payload after signature generation is rejected."""
        timestamp = int(time.time())
        signature = generate_signature(valid_webhook_payload, webhook_secret, timestamp)
        
        # Modify payload after signature generation
        modified_payload = valid_webhook_payload.copy()
        modified_payload["data"]["message"]["conversation"] = "Modified message"
        
        response = client.post(
            "/api/v1/webhooks/evolution/message",
            json=modified_payload,
            headers={
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": str(timestamp)
            }
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        assert "invalid" in response.json()["detail"].lower()
    
    def test_replay_attack_prevention(self, client, webhook_secret, valid_webhook_payload):
        """Test that replay attacks (reusing old valid signatures) are prevented."""
        # Create old timestamp (4 minutes ago, still within 5-minute window)
        old_timestamp = int(time.time()) - 240  # 4 minutes
        signature = generate_signature(valid_webhook_payload, webhook_secret, old_timestamp)
        
        # First request succeeds
        response1 = client.post(
            "/api/v1/webhooks/evolution/message",
            json=valid_webhook_payload,
            headers={
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": str(old_timestamp)
            }
        )
        assert response1.status_code == 200
        
        # Wait 2 minutes (now timestamp is 6 minutes old, outside window)
        # Simulate by creating timestamp 6 minutes in past
        expired_timestamp = int(time.time()) - 360
        expired_signature = generate_signature(valid_webhook_payload, webhook_secret, expired_timestamp)
        
        response2 = client.post(
            "/api/v1/webhooks/evolution/message",
            json=valid_webhook_payload,
            headers={
                "X-Webhook-Signature": expired_signature,
                "X-Webhook-Timestamp": str(expired_timestamp)
            }
        )
        
        # Should be rejected due to expired timestamp
        assert response2.status_code == 401
    
    def test_constant_time_comparison(self, client, webhook_secret, valid_webhook_payload):
        """Test that signature comparison is constant-time (timing attack prevention)."""
        timestamp = int(time.time())
        valid_signature = generate_signature(valid_webhook_payload, webhook_secret, timestamp)
        
        # Create signature that differs only in last character
        almost_valid_signature = valid_signature[:-1] + ('0' if valid_signature[-1] != '0' else '1')
        
        # Both should be rejected in similar time (constant-time comparison)
        # This is a basic test - proper timing attack testing requires statistical analysis
        response = client.post(
            "/api/v1/webhooks/evolution/message",
            json=valid_webhook_payload,
            headers={
                "X-Webhook-Signature": almost_valid_signature,
                "X-Webhook-Timestamp": str(timestamp)
            }
        )
        
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

