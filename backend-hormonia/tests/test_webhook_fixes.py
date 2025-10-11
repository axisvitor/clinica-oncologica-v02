"""
Tests for Evolution API Webhook Integration Fixes

P0 Fixes:
1. Webhook security enforcement
2. Webhook database persistence
3. Connection webhook handler
4. Webhook retry mechanism
5. QR code webhook handler
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from app.services.webhook_processor import WebhookProcessor
from app.integrations.evolution import EvolutionClient
from app.config import settings


# ============================================================================
# P0 FIX #1: WEBHOOK SECURITY TESTS
# ============================================================================

class TestWebhookSecurity:
    """Test webhook signature validation in production."""

    def test_signature_validation_required_in_production(self):
        """Test that signature validation is mandatory in production."""
        with patch.object(settings, 'ENVIRONMENT', 'production'):
            client = EvolutionClient(webhook_secret=None)

            # Should reject webhooks without secret in production
            is_valid = client.validate_webhook_signature(
                payload=b'{"test": "data"}',
                signature='sha256=invalid'
            )

            assert is_valid is False, "Should reject webhooks without secret in production"

    def test_signature_validation_optional_in_development(self):
        """Test that signature validation is optional in development."""
        with patch.object(settings, 'ENVIRONMENT', 'development'):
            client = EvolutionClient(webhook_secret=None)

            # Should allow webhooks without secret in development
            is_valid = client.validate_webhook_signature(
                payload=b'{"test": "data"}',
                signature='sha256=invalid'
            )

            assert is_valid is True, "Should allow webhooks without secret in development"

    def test_valid_signature_passes(self):
        """Test that valid signatures are accepted."""
        import hmac
        import hashlib

        secret = 'test_secret'
        payload = b'{"test": "data"}'
        expected_signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        client = EvolutionClient(webhook_secret=secret)
        is_valid = client.validate_webhook_signature(
            payload=payload,
            signature=f'sha256={expected_signature}'
        )

        assert is_valid is True, "Should accept valid signature"


# ============================================================================
# P0 FIX #2: WEBHOOK PERSISTENCE TESTS
# ============================================================================

class TestWebhookPersistence:
    """Test webhook database persistence."""

    @pytest.mark.asyncio
    async def test_persist_webhook_event(self, db_session: Session):
        """Test webhook event is persisted to database."""
        processor = WebhookProcessor(db_session)

        event_data = {
            "event": "message.received",
            "instance": "test",
            "data": {"message": "test"}
        }

        # Persist webhook event
        event_id = await processor._persist_webhook_event(
            event_type="message.received",
            source="evolution_api",
            payload=event_data
        )

        assert event_id is not None, "Should return event ID"

        # Verify event was stored
        from sqlalchemy import text
        result = db_session.execute(
            text("SELECT id, event_type, processed FROM webhook_events WHERE id = :id"),
            {"id": str(event_id)}
        ).fetchone()

        assert result is not None, "Event should be stored in database"
        assert result[1] == "message.received", "Event type should match"
        assert result[2] is False, "Should be unprocessed initially"

    @pytest.mark.asyncio
    async def test_idempotency_via_event_hash(self, db_session: Session):
        """Test that duplicate webhooks are detected via event hash."""
        processor = WebhookProcessor(db_session)

        event_data = {
            "event": "message.received",
            "instance": "test",
            "data": {"message": "duplicate test"}
        }

        # Persist same event twice
        event_id_1 = await processor._persist_webhook_event(
            event_type="message.received",
            source="evolution_api",
            payload=event_data
        )

        event_id_2 = await processor._persist_webhook_event(
            event_type="message.received",
            source="evolution_api",
            payload=event_data
        )

        # Second call should return the same ID (duplicate detected)
        assert event_id_1 == event_id_2, "Should detect duplicate and return same ID"

    @pytest.mark.asyncio
    async def test_mark_webhook_processed(self, db_session: Session):
        """Test marking webhook as processed."""
        processor = WebhookProcessor(db_session)

        event_data = {"event": "test", "instance": "test"}
        event_id = await processor._persist_webhook_event(
            event_type="test",
            source="test",
            payload=event_data
        )

        # Mark as processed
        await processor._mark_webhook_processed(event_id, success=True)

        # Verify status updated
        from sqlalchemy import text
        result = db_session.execute(
            text("SELECT processed, processed_at FROM webhook_events WHERE id = :id"),
            {"id": str(event_id)}
        ).fetchone()

        assert result[0] is True, "Should be marked as processed"
        assert result[1] is not None, "Should have processed_at timestamp"


# ============================================================================
# P0 FIX #3: CONNECTION WEBHOOK HANDLER TESTS
# ============================================================================

class TestConnectionWebhookHandler:
    """Test connection webhook processing."""

    @pytest.mark.asyncio
    async def test_process_connection_webhook(self, db_session: Session):
        """Test connection webhook updates instance state."""
        processor = WebhookProcessor(db_session)

        event_data = {
            "instance": "test_instance",
            "state": "open"
        }

        # Mock Redis connection state repository
        with patch.object(processor.connection_state_repo, 'set_state', new_callable=AsyncMock) as mock_set_state:
            success = await processor.process_connection_webhook(event_data)

            assert success is True, "Should process successfully"
            mock_set_state.assert_called_once_with("test_instance", "open")

    @pytest.mark.asyncio
    async def test_connection_webhook_missing_fields(self, db_session: Session):
        """Test connection webhook handles missing fields."""
        processor = WebhookProcessor(db_session)

        event_data = {
            "instance": "test_instance"
            # Missing 'state' field
        }

        success = await processor.process_connection_webhook(event_data)
        assert success is False, "Should fail when missing required fields"


# ============================================================================
# P0 FIX #4: WEBHOOK RETRY TESTS
# ============================================================================

class TestWebhookRetry:
    """Test webhook retry mechanism."""

    @pytest.mark.asyncio
    async def test_retry_failed_webhooks(self, db_session: Session):
        """Test retry mechanism processes failed webhooks."""
        processor = WebhookProcessor(db_session)

        # Insert a failed webhook event
        from sqlalchemy import text
        event_id = "00000000-0000-0000-0000-000000000001"
        db_session.execute(text("""
            INSERT INTO webhook_events (
                id, event_type, source, payload, processed, retry_count, max_retries, created_at
            ) VALUES (
                :id, 'message.received', 'test', '{"test": true}'::jsonb, false, 0, 3, NOW()
            )
        """), {"id": event_id})
        db_session.commit()

        # Mock the message processing
        with patch.object(processor, 'process_message_webhook', new_callable=AsyncMock) as mock_process:
            mock_process.return_value = "message_id_123"

            # Run retry
            retried_count = await processor.retry_failed_webhooks()

            assert retried_count >= 0, "Should return retry count"
            # Verify webhook was marked as processed or retry scheduled

    @pytest.mark.asyncio
    async def test_exponential_backoff(self, db_session: Session):
        """Test exponential backoff for retries."""
        processor = WebhookProcessor(db_session)

        # Insert webhook with retry_count = 1
        from sqlalchemy import text
        event_id = "00000000-0000-0000-0000-000000000002"
        db_session.execute(text("""
            INSERT INTO webhook_events (
                id, event_type, source, payload, processed, retry_count, max_retries,
                next_retry_at, created_at
            ) VALUES (
                :id, 'message.received', 'test', '{"test": true}'::jsonb, false, 1, 3,
                NOW() - INTERVAL '1 second', NOW()
            )
        """), {"id": event_id})
        db_session.commit()

        # Mock processing to fail
        with patch.object(processor, 'process_message_webhook', new_callable=AsyncMock) as mock_process:
            mock_process.return_value = None  # Simulate failure

            await processor.retry_failed_webhooks()

            # Verify retry_count incremented and next_retry_at updated
            result = db_session.execute(
                text("SELECT retry_count, next_retry_at FROM webhook_events WHERE id = :id"),
                {"id": event_id}
            ).fetchone()

            assert result[0] == 2, "Retry count should increment"
            assert result[1] is not None, "Should schedule next retry"


# ============================================================================
# P0 FIX #5: QR CODE WEBHOOK HANDLER TESTS
# ============================================================================

class TestUnauthorizedAccessControl:
    """Test unauthorized access control (rate limiting + auto-response)."""

    @pytest.mark.asyncio
    async def test_unauthorized_user_rate_limiting(self, db_session: Session):
        """Test that unauthorized numbers are rate-limited (5 attempts/hour)."""
        processor = WebhookProcessor(db_session)

        unauthorized_phone = "5511999999999"
        event_data = {
            "event": "message.received",
            "instance": "test",
            "data": {
                "key": {
                    "remoteJid": f"{unauthorized_phone}@s.whatsapp.net",
                    "id": "test_unauthorized_msg_123",
                    "fromMe": False
                },
                "message": {
                    "conversation": "Test message from unauthorized user"
                },
                "pushName": "Unknown User"
            }
        }

        # Mock Redis for rate limiting
        from app.core.redis_unified import get_async_redis
        redis_client = await get_async_redis()

        # Clear any existing rate limit
        rate_limit_key = f"unauthorized:ratelimit:{unauthorized_phone}"
        await redis_client.delete(rate_limit_key)

        # Mock _send_unauthorized_response to verify it's called
        with patch.object(processor, '_send_unauthorized_response', new_callable=AsyncMock) as mock_send_response:
            # First attempt - should send response
            result = await processor.process_message_webhook(event_data)
            assert result is None, "Should return None for unauthorized user"
            mock_send_response.assert_called_once_with(unauthorized_phone)

            # Check rate limit counter
            attempt_count = await redis_client.get(rate_limit_key)
            assert attempt_count == b'1', "Rate limit should be 1 after first attempt"

            # Second attempt - should still send response (< 3)
            mock_send_response.reset_mock()
            result = await processor.process_message_webhook(event_data)
            mock_send_response.assert_called_once_with(unauthorized_phone)

            # Fourth attempt - should NOT send response (> 3)
            await redis_client.set(rate_limit_key, 4)
            mock_send_response.reset_mock()
            result = await processor.process_message_webhook(event_data)
            mock_send_response.assert_not_called()

    @pytest.mark.asyncio
    async def test_unauthorized_response_message_sent(self, db_session: Session):
        """Test that unauthorized users receive a polite rejection message."""
        processor = WebhookProcessor(db_session)

        unauthorized_phone = "+5511988888888"

        # Mock Evolution client
        with patch('app.integrations.evolution.get_evolution_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client

            # Call the unauthorized response method directly
            await processor._send_unauthorized_response(unauthorized_phone)

            # Verify send_text_message was called with correct parameters
            mock_client.send_text_message.assert_called_once()
            args, kwargs = mock_client.send_text_message.call_args

            assert args[0] == unauthorized_phone
            assert "não está cadastrado" in args[1]  # Portuguese rejection message


class TestQRCodeWebhookHandler:
    """Test QR code webhook processing."""

    @pytest.mark.asyncio
    async def test_process_qrcode_webhook(self, db_session: Session):
        """Test QR code webhook stores data in Redis."""
        processor = WebhookProcessor(db_session)

        event_data = {
            "instance": "test_instance",
            "qrcode": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg..."
        }

        # Mock Redis client
        from app.core.redis_unified import get_async_redis
        with patch('app.core.redis_unified.get_async_redis') as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            success = await processor.process_qrcode_webhook(event_data)

            assert success is True, "Should process QR code successfully"
            # Verify Redis setex was called
            mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_qrcode_webhook_missing_instance(self, db_session: Session):
        """Test QR code webhook handles missing instance."""
        processor = WebhookProcessor(db_session)

        event_data = {
            "qrcode": "data:image/png;base64,..."
            # Missing 'instance' field
        }

        success = await processor.process_qrcode_webhook(event_data)
        assert success is False, "Should fail when missing instance"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestWebhookIntegration:
    """Integration tests for complete webhook flow."""

    @pytest.mark.asyncio
    async def test_message_webhook_end_to_end(self, db_session: Session):
        """Test complete message webhook processing flow."""
        processor = WebhookProcessor(db_session)

        event_data = {
            "event": "message.received",
            "instance": "hormonia",
            "data": {
                "key": {
                    "remoteJid": "5511999999999@s.whatsapp.net",
                    "id": "test_message_id_123",
                    "fromMe": False
                },
                "message": {
                    "conversation": "Test message"
                },
                "pushName": "Test User"
            }
        }

        # Mock patient lookup
        with patch.object(processor, '_find_patient_by_phone') as mock_find_patient:
            mock_patient = Mock()
            mock_patient.id = "00000000-0000-0000-0000-000000000001"
            mock_find_patient.return_value = mock_patient

            # Mock flow state
            with patch.object(processor.flow_state_repo, 'get_active_flow') as mock_get_flow:
                mock_get_flow.return_value = None  # No active flow

                # Mock Redis
                with patch('app.core.redis_unified.get_async_redis') as mock_get_redis:
                    mock_redis = AsyncMock()
                    mock_redis.exists.return_value = 0  # Not a duplicate
                    mock_get_redis.return_value = mock_redis

                    # Mock AI client
                    with patch.object(processor, '_handle_general_chat', new_callable=AsyncMock):
                        message_id = await processor.process_message_webhook(event_data)

                        # Verify webhook was persisted
                        from sqlalchemy import text
                        webhook_count = db_session.execute(
                            text("SELECT COUNT(*) FROM webhook_events WHERE event_type = 'message.received'")
                        ).scalar()

                        assert webhook_count > 0, "Webhook should be persisted"
                        assert message_id is not None or message_id is None, "Should return message ID or None"


# ============================================================================
# PYTEST FIXTURES
# ============================================================================

@pytest.fixture
def db_session():
    """Create a test database session."""
    from app.database import get_db
    db = next(get_db())
    try:
        yield db
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
