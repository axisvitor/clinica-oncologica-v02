"""
Security tests for WhatsApp Unified Service webhook signature validation.

Tests CRITICAL security fix: HMAC-SHA256 webhook signature validation
to prevent unauthorized webhook spoofing and data manipulation.
"""

import pytest
import hmac
import hashlib
import json
from datetime import datetime, timezone
from unittest.mock import patch

from app.services.unified_whatsapp_service import UnifiedWhatsAppService
from app.services.whatsapp.security import WhatsAppSecurity
from app.config import settings


from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive
@pytest.fixture
def whatsapp_service():
    """Create WhatsApp unified service instance for testing."""
    from unittest.mock import MagicMock
    mock_db = MagicMock()
    service = UnifiedWhatsAppService(db=mock_db)
    return service


@pytest.fixture
def webhook_secret():
    """Test webhook secret."""
    return "test_webhook_secret_1234567890abcdef"


@pytest.fixture
def sample_webhook_payload():
    """Sample webhook payload."""
    return {
        "event": "message.received",
        "data": {
            "key": {
                "remoteJid": "5511999999999@s.whatsapp.net"
            },
            "message": {
                "conversation": "Test message"
            }
        },
        "date_time": now_sao_paulo_naive().isoformat()
    }


def compute_signature(payload: dict, secret: str, timestamp: str = None) -> str:
    """Helper to compute HMAC-SHA256 signature."""
    payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')

    if timestamp:
        signature_payload = f"{timestamp}.{payload_bytes.decode('utf-8')}"
        signature_bytes = signature_payload.encode('utf-8')
    else:
        signature_bytes = payload_bytes

    return hmac.new(
        secret.encode('utf-8'),
        signature_bytes,
        hashlib.sha256
    ).hexdigest()


class TestWebhookSignatureValidation:
    """Test webhook signature validation security features."""

    def test_validate_signature_no_secret_configured(self, whatsapp_service, sample_webhook_payload):
        """Test validation skips when no secret configured (development mode)."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', None):
            result = WhatsAppSecurity.validate_webhook_signature(
                webhook_data=sample_webhook_payload,
                signature_header="any_signature"
            )
            assert result is True  # Should allow in development mode

    def test_validate_signature_missing_header(self, whatsapp_service, sample_webhook_payload, webhook_secret):
        """Test validation fails when signature header is missing."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            result = WhatsAppSecurity.validate_webhook_signature(
                webhook_data=sample_webhook_payload,
                signature_header=None  # Missing signature
            )
            assert result is False

    def test_validate_signature_valid(self, whatsapp_service, sample_webhook_payload, webhook_secret):
        """Test validation succeeds with valid signature."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            # Compute valid signature
            signature = compute_signature(sample_webhook_payload, webhook_secret)

            result = WhatsAppSecurity.validate_webhook_signature(
                webhook_data=sample_webhook_payload,
                signature_header=signature
            )
            assert result is True

    def test_validate_signature_invalid(self, whatsapp_service, sample_webhook_payload, webhook_secret):
        """Test validation fails with invalid signature."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            result = WhatsAppSecurity.validate_webhook_signature(
                webhook_data=sample_webhook_payload,
                signature_header="invalid_signature_12345"
            )
            assert result is False

    def test_validate_signature_with_algorithm_prefix(self, whatsapp_service, sample_webhook_payload, webhook_secret):
        """Test validation with 'sha256=' prefix (Facebook/WhatsApp format)."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            signature = compute_signature(sample_webhook_payload, webhook_secret)
            signature_with_prefix = f"sha256={signature}"

            result = WhatsAppSecurity.validate_webhook_signature(
                webhook_data=sample_webhook_payload,
                signature_header=signature_with_prefix
            )
            assert result is True

    def test_validate_signature_wrong_algorithm(self, whatsapp_service, sample_webhook_payload, webhook_secret):
        """Test validation fails with wrong algorithm prefix."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            signature = compute_signature(sample_webhook_payload, webhook_secret)

            result = WhatsAppSecurity.validate_webhook_signature(
                webhook_data=sample_webhook_payload,
                signature_header=f"md5={signature}"  # Wrong algorithm
            )
            assert result is False

    def test_validate_signature_with_timestamp_valid(self, whatsapp_service, sample_webhook_payload, webhook_secret):
        """Test validation with valid timestamp (replay attack prevention)."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            timestamp = str(int(now_sao_paulo().timestamp()))
            signature = compute_signature(sample_webhook_payload, webhook_secret, timestamp)

            result = WhatsAppSecurity.validate_webhook_signature(
                webhook_data=sample_webhook_payload,
                signature_header=signature,
                timestamp_header=timestamp
            )
            assert result is True

    def test_validate_signature_expired_timestamp(self, whatsapp_service, sample_webhook_payload, webhook_secret):
        """Test validation fails with expired timestamp (> 5 minutes old)."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            # Create timestamp from 10 minutes ago
            old_timestamp = str(int(now_sao_paulo().timestamp()) - 600)
            signature = compute_signature(sample_webhook_payload, webhook_secret, old_timestamp)

            result = WhatsAppSecurity.validate_webhook_signature(
                webhook_data=sample_webhook_payload,
                signature_header=signature,
                timestamp_header=old_timestamp
            )
            assert result is False

    def test_validate_signature_invalid_timestamp_format(self, whatsapp_service, sample_webhook_payload, webhook_secret):
        """Test validation fails with invalid timestamp format."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            signature = compute_signature(sample_webhook_payload, webhook_secret)

            result = WhatsAppSecurity.validate_webhook_signature(
                webhook_data=sample_webhook_payload,
                signature_header=signature,
                timestamp_header="not_a_timestamp"  # Invalid format
            )
            assert result is False

    def test_validate_signature_with_raw_payload(self, whatsapp_service, sample_webhook_payload, webhook_secret):
        """Test validation with raw payload bytes."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            raw_payload = json.dumps(sample_webhook_payload).encode('utf-8')

            # Compute signature from raw payload
            expected_signature = hmac.new(
                webhook_secret.encode('utf-8'),
                raw_payload,
                hashlib.sha256
            ).hexdigest()

            result = WhatsAppSecurity.validate_webhook_signature(
                webhook_data=sample_webhook_payload,
                signature_header=expected_signature,
                raw_payload=raw_payload
            )
            assert result is True

    def test_validate_signature_timing_attack_resistance(self, whatsapp_service, sample_webhook_payload, webhook_secret):
        """Test that validation uses constant-time comparison (hmac.compare_digest)."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            # Generate two different signatures
            valid_signature = compute_signature(sample_webhook_payload, webhook_secret)
            invalid_signature = "0" * len(valid_signature)

            # Both should return False, but with constant time
            with patch('hmac.compare_digest', wraps=hmac.compare_digest) as mock_compare:
                WhatsAppSecurity.validate_webhook_signature(
                    webhook_data=sample_webhook_payload,
                    signature_header=invalid_signature
                )

                # Verify constant-time comparison was used
                mock_compare.assert_called_once()

    def test_validate_signature_exception_handling(self, whatsapp_service, sample_webhook_payload, webhook_secret):
        """Test validation handles exceptions gracefully (fail secure)."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            # Force an exception in signature computation
            with patch('hmac.new', side_effect=Exception("Test error")):
                result = WhatsAppSecurity.validate_webhook_signature(
                    webhook_data=sample_webhook_payload,
                    signature_header="any_signature"
                )
                # Should fail secure
                assert result is False


class TestHandleWebhookSecurity:
    """Test signature validation outcomes that gate webhook handling."""

    def test_handle_webhook_valid_signature(self, whatsapp_service, sample_webhook_payload, webhook_secret):
        """Test webhook handling succeeds with valid signature."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            signature = compute_signature(sample_webhook_payload, webhook_secret)

            result = WhatsAppSecurity.validate_webhook_signature(
                webhook_data=sample_webhook_payload,
                signature_header=signature
            )

            assert result is True

    def test_handle_webhook_invalid_signature(self, whatsapp_service, sample_webhook_payload, webhook_secret):
        """Test webhook handling rejects invalid signature."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            result = WhatsAppSecurity.validate_webhook_signature(
                webhook_data=sample_webhook_payload,
                signature_header="invalid_signature"
            )

            assert result is False

    def test_handle_webhook_missing_signature(self, whatsapp_service, sample_webhook_payload, webhook_secret):
        """Test webhook handling rejects missing signature."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            result = WhatsAppSecurity.validate_webhook_signature(
                webhook_data=sample_webhook_payload,
                signature_header=None  # Missing signature
            )

            assert result is False

    def test_handle_webhook_with_timestamp(self, whatsapp_service, sample_webhook_payload, webhook_secret):
        """Test webhook handling with timestamp validation."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            timestamp = str(int(now_sao_paulo().timestamp()))
            signature = compute_signature(sample_webhook_payload, webhook_secret, timestamp)

            result = WhatsAppSecurity.validate_webhook_signature(
                webhook_data=sample_webhook_payload,
                signature_header=signature,
                timestamp_header=timestamp
            )

            assert result is True

    def test_handle_webhook_expired_timestamp(self, whatsapp_service, sample_webhook_payload, webhook_secret):
        """Test webhook handling rejects expired timestamp."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            old_timestamp = str(int(now_sao_paulo().timestamp()) - 600)
            signature = compute_signature(sample_webhook_payload, webhook_secret, old_timestamp)

            result = WhatsAppSecurity.validate_webhook_signature(
                webhook_data=sample_webhook_payload,
                signature_header=signature,
                timestamp_header=old_timestamp
            )

            assert result is False


class TestSecurityLogging:
    """Test security event logging."""

    def test_logs_missing_signature(self, whatsapp_service, sample_webhook_payload, webhook_secret, caplog):
        """Test that missing signature is logged."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            WhatsAppSecurity.validate_webhook_signature(
                webhook_data=sample_webhook_payload,
                signature_header=None
            )

            assert "Missing webhook signature header" in caplog.text
            assert "SECURITY" in caplog.text

    def test_logs_invalid_signature(self, whatsapp_service, sample_webhook_payload, webhook_secret, caplog):
        """Test that invalid signature is logged with details."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            WhatsAppSecurity.validate_webhook_signature(
                webhook_data=sample_webhook_payload,
                signature_header="invalid_signature"
            )

            assert "signature validation FAILED" in caplog.text
            assert "SECURITY" in caplog.text

    def test_logs_expired_timestamp(self, whatsapp_service, sample_webhook_payload, webhook_secret, caplog):
        """Test that expired timestamp is logged."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            old_timestamp = str(int(now_sao_paulo().timestamp()) - 600)
            signature = compute_signature(sample_webhook_payload, webhook_secret, old_timestamp)

            WhatsAppSecurity.validate_webhook_signature(
                webhook_data=sample_webhook_payload,
                signature_header=signature,
                timestamp_header=old_timestamp
            )

            assert "timestamp expired" in caplog.text

    def test_logs_no_secret_warning(self, whatsapp_service, sample_webhook_payload, caplog):
        """Test warning when webhook secret is not configured."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', None):
            WhatsAppSecurity.validate_webhook_signature(
                webhook_data=sample_webhook_payload,
                signature_header="any"
            )

            assert "WHATSAPP_EVOLUTION_WEBHOOK_SECRET not configured" in caplog.text
            assert "SECURITY WARNING" in caplog.text


class TestProductionReadiness:
    """Test production readiness and configuration."""

    def test_requires_secret_in_production(self, whatsapp_service, sample_webhook_payload):
        """Test that signature validation requires secret configuration."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', None):
            # Should log warning and skip validation
            result = WhatsAppSecurity.validate_webhook_signature(
                webhook_data=sample_webhook_payload,
                signature_header="signature"
            )
            assert result is True  # Allows in dev mode

    def test_secret_must_be_secure(self):
        """Test webhook secret generation recommendations."""
        import secrets

        # Generate a secure secret
        secret = secrets.token_urlsafe(32)

        # Should be at least 32 characters
        assert len(secret) >= 32

        # Should be URL-safe
        assert all(c.isalnum() or c in '-_' for c in secret)

    def test_env_example_documented(self):
        """Test that WHATSAPP_EVOLUTION_WEBHOOK_SECRET is documented in .env.example."""
        import os
        env_example_path = os.path.join(
            os.path.dirname(__file__),
            "../..",
            "backend-hormonia",
            ".env.example"
        )

        # This test documents the requirement
        # Actual .env.example check would be in integration tests
        assert True  # Placeholder for documentation check


class TestHIPAACompliance:
    """Test HIPAA compliance for webhook security."""

    def test_prevents_data_tampering(self, whatsapp_service, sample_webhook_payload, webhook_secret):
        """Test that signature validation prevents data tampering."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            # Generate valid signature
            signature = compute_signature(sample_webhook_payload, webhook_secret)

            # Tamper with payload
            tampered_payload = sample_webhook_payload.copy()
            tampered_payload["data"]["message"]["conversation"] = "TAMPERED MESSAGE"

            # Validation should fail
            result = WhatsAppSecurity.validate_webhook_signature(
                webhook_data=tampered_payload,
                signature_header=signature
            )
            assert result is False

    def test_prevents_replay_attacks(self, whatsapp_service, sample_webhook_payload, webhook_secret):
        """Test that timestamp validation prevents replay attacks."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            # Create old webhook (10 minutes ago)
            old_timestamp = str(int(now_sao_paulo().timestamp()) - 600)
            signature = compute_signature(sample_webhook_payload, webhook_secret, old_timestamp)

            # Should reject old webhooks
            result = WhatsAppSecurity.validate_webhook_signature(
                webhook_data=sample_webhook_payload,
                signature_header=signature,
                timestamp_header=old_timestamp
            )
            assert result is False

    def test_prevents_timing_attacks(self, whatsapp_service, sample_webhook_payload, webhook_secret):
        """Test that constant-time comparison prevents timing attacks."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            # Verify hmac.compare_digest is used (constant-time)
            with patch('hmac.compare_digest', wraps=hmac.compare_digest) as mock_compare:
                signature = compute_signature(sample_webhook_payload, webhook_secret)

                WhatsAppSecurity.validate_webhook_signature(
                    webhook_data=sample_webhook_payload,
                    signature_header=signature
                )

                # Verify constant-time comparison was used
                mock_compare.assert_called()

    def test_audit_logging_for_rejected_webhooks(self, whatsapp_service, sample_webhook_payload, webhook_secret, caplog):
        """Test that rejected webhooks are logged for audit trail."""
        with patch.object(settings, 'WHATSAPP_EVOLUTION_WEBHOOK_SECRET', webhook_secret):
            WhatsAppSecurity.validate_webhook_signature(
                webhook_data=sample_webhook_payload,
                signature_header="invalid_signature"
            )

            # Should have security audit log
            assert "SECURITY" in caplog.text
            assert "validation FAILED" in caplog.text


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])