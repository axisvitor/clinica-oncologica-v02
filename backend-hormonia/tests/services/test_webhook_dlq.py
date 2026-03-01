"""
Tests for Webhook Dead Letter Queue (DLQ) service.

Tests cover:
- DLQ event storage and retrieval
- Exponential backoff retry logic
- Max retries and dead letter storage
- DLQ statistics and monitoring
- Overflow alerts
"""

import pytest
import json
from datetime import datetime, timedelta
from uuid import uuid4

from app.services.webhook_dlq import WebhookDLQ, get_webhook_dlq
from app.core.redis_manager import get_async_redis_client as get_async_redis


from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive
@pytest.fixture
async def dlq_service(db_session):
    """Create DLQ service instance."""
    return WebhookDLQ(db_session)


@pytest.fixture
async def redis_client():
    """Get Redis client."""
    return await get_async_redis()


@pytest.fixture
async def cleanup_dlq(redis_client):
    """Cleanup DLQ after tests."""
    yield
    # Cleanup all DLQ keys
    pattern = "webhook:dlq:*"
    keys = await redis_client.keys(pattern)
    if keys:
        await redis_client.delete(*keys)


class TestWebhookDLQ:
    """Test WebhookDLQ service."""

    @pytest.mark.asyncio
    async def test_send_to_dlq(self, dlq_service, redis_client, cleanup_dlq):
        """Test sending event to DLQ."""
        event_id = uuid4()
        event_type = "message.received"
        event_data = {"data": {"message": "test"}}
        error = "Test error"

        # Send to DLQ
        success = await dlq_service.send_to_dlq(
            event_id=event_id,
            event_type=event_type,
            event_data=event_data,
            error=error,
            retry_count=0
        )

        assert success is True

        # Verify event in Redis
        dlq_key = f"webhook:dlq:{event_type}"
        queue_size = await redis_client.llen(dlq_key)
        assert queue_size == 1

        # Verify event data
        event_json = await redis_client.lindex(dlq_key, 0)
        event = json.loads(event_json)

        assert event["event_id"] == str(event_id)
        assert event["event_type"] == event_type
        assert event["event_data"] == event_data
        assert event["error"] == error
        assert event["retry_count"] == 0
        assert event["max_retries"] == dlq_service.MAX_RETRIES

    @pytest.mark.asyncio
    async def test_exponential_backoff(self, dlq_service):
        """Test exponential backoff calculation."""
        # Test retry delays
        retry_0 = dlq_service._calculate_next_retry(0)
        retry_1 = dlq_service._calculate_next_retry(1)
        retry_2 = dlq_service._calculate_next_retry(2)
        retry_3 = dlq_service._calculate_next_retry(3)

        now = now_sao_paulo_naive()

        # Verify exponential backoff
        assert (retry_0 - now).total_seconds() == pytest.approx(60, abs=1)  # 60s
        assert (retry_1 - now).total_seconds() == pytest.approx(120, abs=1)  # 120s
        assert (retry_2 - now).total_seconds() == pytest.approx(240, abs=1)  # 240s
        assert (retry_3 - now).total_seconds() == pytest.approx(480, abs=1)  # 480s

    @pytest.mark.asyncio
    async def test_process_dlq_success(self, dlq_service, redis_client, cleanup_dlq, mocker):
        """Test successful DLQ processing."""
        # Mock successful webhook processing
        mock_retry = mocker.patch.object(
            dlq_service,
            "_retry_webhook_event",
            return_value=True
        )

        # Add event to DLQ with past retry time
        event_id = uuid4()
        event = {
            "event_id": str(event_id),
            "event_type": "message.received",
            "event_data": {"test": "data"},
            "error": "Test error",
            "retry_count": 0,
            "max_retries": 5,
            "timestamp": now_sao_paulo_naive().isoformat(),
            "added_to_dlq_at": now_sao_paulo_naive().isoformat(),
            "next_retry_at": (now_sao_paulo_naive() - timedelta(seconds=10)).isoformat()  # Past
        }

        dlq_key = "webhook:dlq:message.received"
        await redis_client.rpush(dlq_key, json.dumps(event))

        # Process DLQ
        processed_count = await dlq_service.process_dlq(batch_size=10)

        assert processed_count == 1
        mock_retry.assert_called_once()

        # Verify event removed from queue
        queue_size = await redis_client.llen(dlq_key)
        assert queue_size == 0

    @pytest.mark.asyncio
    async def test_process_dlq_retry_failed(self, dlq_service, redis_client, cleanup_dlq, mocker):
        """Test DLQ processing when retry fails."""
        # Mock failed webhook processing
        mock_retry = mocker.patch.object(
            dlq_service,
            "_retry_webhook_event",
            return_value=False
        )

        # Add event to DLQ
        event_id = uuid4()
        event = {
            "event_id": str(event_id),
            "event_type": "message.received",
            "event_data": {"test": "data"},
            "error": "Test error",
            "retry_count": 0,
            "max_retries": 5,
            "timestamp": now_sao_paulo_naive().isoformat(),
            "added_to_dlq_at": now_sao_paulo_naive().isoformat(),
            "next_retry_at": (now_sao_paulo_naive() - timedelta(seconds=10)).isoformat()
        }

        dlq_key = "webhook:dlq:message.received"
        await redis_client.rpush(dlq_key, json.dumps(event))

        # Process DLQ
        processed_count = await dlq_service.process_dlq(batch_size=10)

        assert processed_count == 0
        mock_retry.assert_called_once()

        # Verify event re-queued with updated retry count
        queue_size = await redis_client.llen(dlq_key)
        assert queue_size == 1

        event_json = await redis_client.lindex(dlq_key, 0)
        requeued_event = json.loads(event_json)
        assert requeued_event["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_max_retries_dead_letter(self, dlq_service, redis_client, cleanup_dlq, mocker):
        """Test event moved to dead letter after max retries."""
        # Mock failed webhook processing
        mock_retry = mocker.patch.object(
            dlq_service,
            "_retry_webhook_event",
            return_value=False
        )

        # Add event with max retries
        event_id = uuid4()
        event = {
            "event_id": str(event_id),
            "event_type": "message.received",
            "event_data": {"test": "data"},
            "error": "Test error",
            "retry_count": 4,  # One below max
            "max_retries": 5,
            "timestamp": now_sao_paulo_naive().isoformat(),
            "added_to_dlq_at": now_sao_paulo_naive().isoformat(),
            "next_retry_at": (now_sao_paulo_naive() - timedelta(seconds=10)).isoformat()
        }

        dlq_key = "webhook:dlq:message.received"
        await redis_client.rpush(dlq_key, json.dumps(event))

        # Process DLQ (will fail and reach max retries)
        processed_count = await dlq_service.process_dlq(batch_size=10)

        assert processed_count == 0

        # Verify event removed from DLQ
        queue_size = await redis_client.llen(dlq_key)
        assert queue_size == 0

        # Verify event in dead letter
        dead_letter_key = "webhook:dead_letter:message.received"
        dead_letter_size = await redis_client.llen(dead_letter_key)
        assert dead_letter_size == 1

    @pytest.mark.asyncio
    async def test_dlq_stats(self, dlq_service, redis_client, cleanup_dlq):
        """Test DLQ statistics."""
        # Add events to DLQ
        event_type = "message.received"

        for i in range(3):
            event = {
                "event_id": str(uuid4()),
                "event_type": event_type,
                "event_data": {},
                "error": "Test",
                "retry_count": 0,
                "max_retries": 5,
                "timestamp": now_sao_paulo_naive().isoformat(),
                "added_to_dlq_at": now_sao_paulo_naive().isoformat(),
                "next_retry_at": now_sao_paulo_naive().isoformat()
            }
            await redis_client.rpush(f"webhook:dlq:{event_type}", json.dumps(event))

        # Update metadata
        await dlq_service._update_dlq_metadata(event_type, "added")
        await dlq_service._update_dlq_metadata(event_type, "added")
        await dlq_service._update_dlq_metadata(event_type, "processed")

        # Get stats
        stats = await dlq_service.get_dlq_stats()

        assert stats["total_pending"] == 3
        assert event_type in stats["by_event_type"]
        assert stats["by_event_type"][event_type]["pending"] == 3
        assert stats["by_event_type"][event_type]["total_added"] >= 2
        assert stats["by_event_type"][event_type]["total_processed"] >= 1

    @pytest.mark.asyncio
    async def test_overflow_alert(self, dlq_service, redis_client, cleanup_dlq, caplog):
        """Test DLQ overflow alert."""
        event_type = "message.received"

        # Set lower threshold for testing
        original_threshold = dlq_service.MAX_DLQ_SIZE
        dlq_service.MAX_DLQ_SIZE = 5

        try:
            # Add events exceeding threshold
            for i in range(6):
                await dlq_service.send_to_dlq(
                    event_id=uuid4(),
                    event_type=event_type,
                    event_data={},
                    error="Test",
                    retry_count=0
                )

            # Check for overflow alert in logs
            assert "DLQ OVERFLOW ALERT" in caplog.text

        finally:
            # Restore original threshold
            dlq_service.MAX_DLQ_SIZE = original_threshold

    @pytest.mark.asyncio
    async def test_singleton_pattern(self, db_session):
        """Test get_webhook_dlq singleton."""
        dlq1 = get_webhook_dlq(db_session)
        dlq2 = get_webhook_dlq(db_session)

        assert dlq1 is dlq2  # Same instance


class TestDLQRetryLogic:
    """Test DLQ retry logic."""

    @pytest.mark.asyncio
    async def test_not_ready_for_retry(self, dlq_service, redis_client, cleanup_dlq):
        """Test event not ready for retry (next_retry_at in future)."""
        # Add event with future retry time
        event = {
            "event_id": str(uuid4()),
            "event_type": "message.received",
            "event_data": {},
            "error": "Test",
            "retry_count": 0,
            "max_retries": 5,
            "timestamp": now_sao_paulo_naive().isoformat(),
            "added_to_dlq_at": now_sao_paulo_naive().isoformat(),
            "next_retry_at": (now_sao_paulo_naive() + timedelta(hours=1)).isoformat()  # Future
        }

        dlq_key = "webhook:dlq:message.received"
        await redis_client.rpush(dlq_key, json.dumps(event))

        # Process DLQ
        processed_count = await dlq_service.process_dlq(batch_size=10)

        assert processed_count == 0

        # Verify event still in queue (at front)
        queue_size = await redis_client.llen(dlq_key)
        assert queue_size == 1
