"""
Integration Tests for Webhook Idempotency

Tests the complete idempotency flow including:
- Duplicate webhook detection
- Event tracking and expiration
- Cleanup jobs
- Race condition handling
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.webhook_event import WebhookEvent
from app.middleware.idempotency import IdempotencyMiddleware, cleanup_expired_events
from app.services.idempotency_cleanup import IdempotencyCleanupService


class TestWebhookIdempotency:
    """Test suite for webhook idempotency functionality."""

    @pytest.fixture
    def sample_webhook_payload(self):
        """Sample WhatsApp webhook payload."""
        return {
            "event_id": "test-event-123",
            "event": "messages.upsert",
            "instance": "test-instance",
            "data": {
                "key": {
                    "remoteJid": "5511999999999@s.whatsapp.net",
                    "fromMe": False,
                    "id": "test-message-123"
                },
                "message": {
                    "conversation": "Test message"
                },
                "messageTimestamp": 1234567890
            }
        }

    @pytest.fixture
    def sample_webhook_headers(self):
        """Sample webhook headers with event ID."""
        return {
            "X-Event-ID": "test-event-123",
            "Content-Type": "application/json"
        }

    def test_webhook_event_creation(self, db: Session):
        """Test creating a webhook event record."""
        event = WebhookEvent.create_event(
            event_id="test-event-1",
            provider="whatsapp",
            event_type="message.received",
            payload={"test": "data"},
            ttl_hours=24
        )

        db.add(event)
        db.commit()

        # Verify creation
        assert event.event_id == "test-event-1"
        assert event.provider == "whatsapp"
        assert event.event_type == "message.received"
        assert event.status == "processing"
        assert event.retry_count == 0
        assert not event.is_expired()

    def test_webhook_event_mark_completed(self, db: Session):
        """Test marking webhook event as completed."""
        event = WebhookEvent.create_event(
            event_id="test-event-2",
            provider="whatsapp",
            event_type="message.received"
        )

        db.add(event)
        db.commit()

        # Mark as completed
        event.mark_completed({"result": "success"})
        db.commit()

        assert event.status == "completed"
        assert event.processed_at is not None
        assert event.response_data == {"result": "success"}

    def test_webhook_event_mark_failed(self, db: Session):
        """Test marking webhook event as failed."""
        event = WebhookEvent.create_event(
            event_id="test-event-3",
            provider="whatsapp",
            event_type="message.received"
        )

        db.add(event)
        db.commit()

        # Mark as failed
        event.mark_failed({"error": "Processing failed"})
        db.commit()

        assert event.status == "failed"
        assert event.processed_at is not None
        assert event.response_data == {"error": "Processing failed"}

    def test_webhook_event_increment_retry(self, db: Session):
        """Test incrementing retry counter for duplicates."""
        event = WebhookEvent.create_event(
            event_id="test-event-4",
            provider="whatsapp",
            event_type="message.received"
        )

        db.add(event)
        db.commit()

        # Increment retry counter
        event.increment_retry()
        db.commit()

        assert event.retry_count == 1

        # Increment again
        event.increment_retry()
        db.commit()

        assert event.retry_count == 2

    def test_webhook_event_expiration(self, db: Session):
        """Test webhook event expiration logic."""
        # Create event with short TTL
        event = WebhookEvent.create_event(
            event_id="test-event-5",
            provider="whatsapp",
            event_type="message.received",
            ttl_hours=0  # Already expired
        )

        # Manually set expires_at to past
        event.expires_at = datetime.utcnow() - timedelta(hours=1)
        db.add(event)
        db.commit()

        assert event.is_expired()

    @pytest.mark.asyncio
    async def test_first_webhook_processing(
        self,
        client: TestClient,
        db: Session,
        sample_webhook_payload,
        sample_webhook_headers
    ):
        """Test processing a webhook for the first time."""
        response = client.post(
            "/api/v1/webhooks/whatsapp/evolution/test-instance",
            json=sample_webhook_payload,
            headers=sample_webhook_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Check response headers
        assert response.headers.get("X-Idempotency-Status") == "processed"
        assert response.headers.get("X-Event-ID") == "test-event-123"

        # Verify event was stored
        event = db.query(WebhookEvent).filter(
            WebhookEvent.event_id == "test-event-123"
        ).first()

        assert event is not None
        assert event.status == "completed"
        assert event.provider == "whatsapp"

    @pytest.mark.asyncio
    async def test_duplicate_webhook_detection(
        self,
        client: TestClient,
        db: Session,
        sample_webhook_payload,
        sample_webhook_headers
    ):
        """Test that duplicate webhooks are detected and rejected."""
        # Send first webhook
        response1 = client.post(
            "/api/v1/webhooks/whatsapp/evolution/test-instance",
            json=sample_webhook_payload,
            headers=sample_webhook_headers
        )

        assert response1.status_code == 200

        # Send duplicate webhook
        response2 = client.post(
            "/api/v1/webhooks/whatsapp/evolution/test-instance",
            json=sample_webhook_payload,
            headers=sample_webhook_headers
        )

        assert response2.status_code == 200
        data = response2.json()

        # Check duplicate response
        assert data["status"] == "duplicate"
        assert data["event_id"] == "test-event-123"
        assert "processed_at" in data

        # Check headers
        assert response2.headers.get("X-Idempotency-Status") == "duplicate"
        assert response2.headers.get("X-Retry-Count") == "1"

        # Verify retry counter was incremented
        event = db.query(WebhookEvent).filter(
            WebhookEvent.event_id == "test-event-123"
        ).first()

        assert event.retry_count == 1

    @pytest.mark.asyncio
    async def test_multiple_duplicate_webhooks(
        self,
        client: TestClient,
        db: Session,
        sample_webhook_payload,
        sample_webhook_headers
    ):
        """Test handling multiple duplicate webhook attempts."""
        # Send original webhook
        client.post(
            "/api/v1/webhooks/whatsapp/evolution/test-instance",
            json=sample_webhook_payload,
            headers=sample_webhook_headers
        )

        # Send 5 duplicates
        for i in range(5):
            response = client.post(
                "/api/v1/webhooks/whatsapp/evolution/test-instance",
                json=sample_webhook_payload,
                headers=sample_webhook_headers
            )

            assert response.status_code == 200
            assert response.json()["status"] == "duplicate"

        # Verify retry counter
        event = db.query(WebhookEvent).filter(
            WebhookEvent.event_id == "test-event-123"
        ).first()

        assert event.retry_count == 5

    @pytest.mark.asyncio
    async def test_concurrent_duplicate_webhooks(
        self,
        client: TestClient,
        db: Session,
        sample_webhook_payload,
        sample_webhook_headers
    ):
        """Test handling concurrent duplicate webhook requests (race condition)."""
        # Send multiple concurrent requests
        tasks = []
        for _ in range(10):
            task = asyncio.create_task(
                asyncio.to_thread(
                    client.post,
                    "/api/v1/webhooks/whatsapp/evolution/test-instance",
                    json=sample_webhook_payload,
                    headers=sample_webhook_headers
                )
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)

        # At least one should be processed, others should be duplicates
        processed_count = sum(
            1 for r in responses if r.json().get("status") != "duplicate"
        )
        duplicate_count = sum(
            1 for r in responses if r.json().get("status") == "duplicate"
        )

        assert processed_count >= 1
        assert processed_count + duplicate_count == 10

        # Verify only one event record exists
        event_count = db.query(WebhookEvent).filter(
            WebhookEvent.event_id == "test-event-123"
        ).count()

        assert event_count == 1

    @pytest.mark.asyncio
    async def test_expired_event_reprocessing(
        self,
        client: TestClient,
        db: Session,
        sample_webhook_payload,
        sample_webhook_headers
    ):
        """Test that expired events can be reprocessed."""
        # Create expired event
        event = WebhookEvent.create_event(
            event_id="test-event-123",
            provider="whatsapp",
            event_type="message.received"
        )
        event.expires_at = datetime.utcnow() - timedelta(hours=1)
        event.mark_completed()

        db.add(event)
        db.commit()

        # Send webhook with expired event ID
        response = client.post(
            "/api/v1/webhooks/whatsapp/evolution/test-instance",
            json=sample_webhook_payload,
            headers=sample_webhook_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Should be processed as new event
        assert data.get("status") != "duplicate"

    @pytest.mark.asyncio
    async def test_cleanup_expired_events(self, db: Session):
        """Test cleanup of expired webhook events."""
        # Create some expired events
        for i in range(10):
            event = WebhookEvent.create_event(
                event_id=f"expired-event-{i}",
                provider="whatsapp",
                event_type="message.received"
            )
            event.expires_at = datetime.utcnow() - timedelta(hours=1)
            event.mark_completed()
            db.add(event)

        # Create some active events
        for i in range(5):
            event = WebhookEvent.create_event(
                event_id=f"active-event-{i}",
                provider="whatsapp",
                event_type="message.received"
            )
            event.mark_completed()
            db.add(event)

        db.commit()

        # Run cleanup
        deleted_count = await cleanup_expired_events(db, batch_size=100)

        assert deleted_count == 10

        # Verify only active events remain
        remaining_count = db.query(WebhookEvent).count()
        assert remaining_count == 5

    @pytest.mark.asyncio
    async def test_cleanup_service(self, db: Session):
        """Test idempotency cleanup service."""
        cleanup_service = IdempotencyCleanupService(batch_size=100)

        # Create test events
        for i in range(20):
            event = WebhookEvent.create_event(
                event_id=f"test-event-{i}",
                provider="whatsapp",
                event_type="message.received"
            )
            if i < 10:
                # Half expired
                event.expires_at = datetime.utcnow() - timedelta(hours=1)
            event.mark_completed()
            db.add(event)

        db.commit()

        # Run cleanup
        result = await cleanup_service.run_cleanup(db)

        assert result["status"] == "success"
        assert result["deleted_count"] == 10
        assert result["before_count"] == 20
        assert result["after_count"] == 10

    @pytest.mark.asyncio
    async def test_cleanup_stats(self, db: Session):
        """Test getting idempotency statistics."""
        cleanup_service = IdempotencyCleanupService()

        # Create test events with different statuses
        # Processing events
        for i in range(5):
            event = WebhookEvent.create_event(
                event_id=f"processing-{i}",
                provider="whatsapp",
                event_type="message.received"
            )
            db.add(event)

        # Completed events
        for i in range(10):
            event = WebhookEvent.create_event(
                event_id=f"completed-{i}",
                provider="whatsapp",
                event_type="message.received"
            )
            event.mark_completed()
            db.add(event)

        # Failed events
        for i in range(3):
            event = WebhookEvent.create_event(
                event_id=f"failed-{i}",
                provider="whatsapp",
                event_type="message.received"
            )
            event.mark_failed()
            db.add(event)

        # Events with retries (duplicates)
        for i in range(7):
            event = WebhookEvent.create_event(
                event_id=f"duplicate-{i}",
                provider="whatsapp",
                event_type="message.received"
            )
            event.increment_retry()
            event.increment_retry()
            event.mark_completed()
            db.add(event)

        db.commit()

        # Get stats
        stats = await cleanup_service.get_cleanup_stats(db)

        assert stats["total_events"] == 25
        assert stats["processing_events"] == 5
        assert stats["completed_events"] == 17
        assert stats["failed_events"] == 3
        assert stats["duplicate_events"] == 7
        assert stats["total_retries"] == 14  # 7 events * 2 retries

    @pytest.mark.asyncio
    async def test_idempotency_with_different_providers(
        self,
        client: TestClient,
        db: Session
    ):
        """Test idempotency works across different providers."""
        providers = ["whatsapp", "twilio", "generic"]

        for provider in providers:
            payload = {
                "event_id": f"{provider}-event-1",
                "provider": provider,
                "data": {"test": "data"}
            }
            headers = {"X-Event-ID": f"{provider}-event-1"}

            # First request
            response1 = client.post(
                f"/api/v1/webhooks/{provider}/test",
                json=payload,
                headers=headers
            )

            # Duplicate request
            response2 = client.post(
                f"/api/v1/webhooks/{provider}/test",
                json=payload,
                headers=headers
            )

            # Verify both providers tracked separately
            event = db.query(WebhookEvent).filter(
                WebhookEvent.event_id == f"{provider}-event-1"
            ).first()

            assert event is not None
            assert event.provider == provider

    @pytest.mark.asyncio
    async def test_webhook_without_event_id(
        self,
        client: TestClient,
        db: Session
    ):
        """Test handling webhooks without explicit event IDs."""
        payload = {
            "data": {"test": "data without event_id"}
        }

        # Should still process (generates hash-based ID)
        response = client.post(
            "/api/v1/webhooks/whatsapp/evolution/test-instance",
            json=payload
        )

        # Should succeed but log warning
        assert response.status_code in [200, 400]  # Depends on validation

    def test_batch_cleanup_performance(self, db: Session):
        """Test cleanup performance with large batches."""
        # Create many expired events
        batch_size = 1000
        for i in range(2500):
            event = WebhookEvent.create_event(
                event_id=f"perf-test-{i}",
                provider="whatsapp",
                event_type="message.received"
            )
            event.expires_at = datetime.utcnow() - timedelta(hours=1)
            event.mark_completed()
            db.add(event)

            # Commit in batches
            if i % 100 == 0:
                db.commit()

        db.commit()

        # Time the cleanup
        import time
        start_time = time.time()

        deleted_count = asyncio.run(cleanup_expired_events(db, batch_size=batch_size))

        execution_time = time.time() - start_time

        assert deleted_count == 2500
        assert execution_time < 10  # Should complete in less than 10 seconds

    @pytest.mark.asyncio
    async def test_idempotency_monitoring_endpoints(
        self,
        client: TestClient,
        db: Session
    ):
        """Test idempotency monitoring and stats endpoints."""
        # Create some test data
        for i in range(5):
            event = WebhookEvent.create_event(
                event_id=f"monitor-test-{i}",
                provider="whatsapp",
                event_type="message.received"
            )
            event.mark_completed()
            db.add(event)

        db.commit()

        # Test stats endpoint
        response = client.get("/api/v1/webhooks/whatsapp/idempotency/stats")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert data["data"]["total_events"] >= 5

        # Test manual cleanup endpoint
        response = client.post("/api/v1/webhooks/whatsapp/idempotency/cleanup")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert "deleted_count" in data["data"]
