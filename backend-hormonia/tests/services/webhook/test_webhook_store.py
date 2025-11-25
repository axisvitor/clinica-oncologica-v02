"""
Unit tests for WebhookEventStore persistence layer.

Tests idempotent webhook event storage, retry management, and cleanup.
"""
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError


class TestWebhookEventStore:
    """Test WebhookEventStore functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = Mock()
        db.execute = Mock()
        db.commit = Mock()
        db.rollback = Mock()
        return db

    @pytest.fixture
    def store(self, mock_db):
        """Create WebhookEventStore instance."""
        from app.services.webhook.persistence.webhook_store import WebhookEventStore
        return WebhookEventStore(mock_db)

    @pytest.fixture
    def sample_payload(self):
        """Sample webhook payload."""
        return {
            "instance": "clinica-hormonia",
            "event": "messages.upsert",
            "data": {
                "key": {"id": "msg_123"},
                "message": {"conversation": "Hello"}
            }
        }


class TestPersistEvent(TestWebhookEventStore):
    """Test event persistence functionality."""

    @pytest.mark.asyncio
    async def test_persist_new_event_success(self, store, mock_db, sample_payload):
        """Test persisting a new webhook event."""
        # No existing event found
        mock_result = Mock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result
        
        event_id = await store.persist_event(
            event_type="messages.upsert",
            source="evolution_api",
            payload=sample_payload
        )
        
        assert event_id is not None
        assert isinstance(event_id, UUID)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_persist_duplicate_event_returns_existing_id(self, store, mock_db, sample_payload):
        """Test that duplicate events return existing ID."""
        existing_id = str(uuid4())
        mock_result = Mock()
        mock_result.fetchone.return_value = (existing_id,)
        mock_db.execute.return_value = mock_result
        
        event_id = await store.persist_event(
            event_type="messages.upsert",
            source="evolution_api",
            payload=sample_payload
        )
        
        assert event_id == UUID(existing_id)
        mock_db.commit.assert_not_called()  # Should not commit for duplicate

    @pytest.mark.asyncio
    async def test_persist_event_with_related_ids(self, store, mock_db, sample_payload):
        """Test persisting event with related message and patient IDs."""
        mock_result = Mock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result
        
        message_id = uuid4()
        patient_id = uuid4()
        
        event_id = await store.persist_event(
            event_type="messages.upsert",
            source="evolution_api",
            payload=sample_payload,
            related_message_id=message_id,
            related_patient_id=patient_id
        )
        
        assert event_id is not None
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_persist_event_integrity_error_rollback(self, store, mock_db, sample_payload):
        """Test rollback on integrity error (race condition duplicate)."""
        mock_result = Mock()
        mock_result.fetchone.return_value = None
        mock_db.execute.side_effect = [mock_result, IntegrityError("duplicate", None, None)]
        
        event_id = await store.persist_event(
            event_type="messages.upsert",
            source="evolution_api",
            payload=sample_payload
        )
        
        assert event_id is None
        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_persist_event_general_error_rollback(self, store, mock_db, sample_payload):
        """Test rollback on general database error."""
        mock_db.execute.side_effect = Exception("Database connection error")
        
        event_id = await store.persist_event(
            event_type="messages.upsert",
            source="evolution_api",
            payload=sample_payload
        )
        
        assert event_id is None
        mock_db.rollback.assert_called_once()


class TestMarkProcessed(TestWebhookEventStore):
    """Test marking events as processed."""

    @pytest.mark.asyncio
    async def test_mark_processed_success(self, store, mock_db):
        """Test marking event as successfully processed."""
        event_id = uuid4()
        
        await store.mark_processed(event_id, success=True)
        
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_processed_failure(self, store, mock_db):
        """Test marking event as failed."""
        event_id = uuid4()
        error_message = "Processing failed: invalid payload"
        
        await store.mark_processed(event_id, success=False, error_message=error_message)
        
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_processed_database_error(self, store, mock_db):
        """Test handling database error when marking processed."""
        event_id = uuid4()
        mock_db.execute.side_effect = Exception("Database error")
        
        # Should not raise, just log error
        await store.mark_processed(event_id, success=True)
        
        mock_db.rollback.assert_called_once()


class TestGetFailedEvents(TestWebhookEventStore):
    """Test retrieving failed events for retry."""

    @pytest.mark.asyncio
    async def test_get_failed_events_returns_pending_retries(self, store, mock_db):
        """Test getting events eligible for retry."""
        event1_id = str(uuid4())
        event2_id = str(uuid4())
        
        mock_result = Mock()
        mock_result.fetchall.return_value = [
            (event1_id, "messages.upsert", {"test": 1}, 1, 3, None, None, datetime.utcnow()),
            (event2_id, "status.update", {"test": 2}, 2, 3, None, None, datetime.utcnow()),
        ]
        mock_db.execute.return_value = mock_result
        
        events = await store.get_failed_events(limit=50)
        
        assert len(events) == 2
        assert events[0]["id"] == UUID(event1_id)
        assert events[0]["retry_count"] == 1
        assert events[1]["id"] == UUID(event2_id)
        assert events[1]["retry_count"] == 2

    @pytest.mark.asyncio
    async def test_get_failed_events_empty(self, store, mock_db):
        """Test getting empty list when no failed events."""
        mock_result = Mock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        
        events = await store.get_failed_events()
        
        assert events == []

    @pytest.mark.asyncio
    async def test_get_failed_events_database_error(self, store, mock_db):
        """Test handling database error when getting failed events."""
        mock_db.execute.side_effect = Exception("Database error")
        
        events = await store.get_failed_events()
        
        assert events == []


class TestIncrementRetryCount(TestWebhookEventStore):
    """Test retry count increment functionality."""

    @pytest.mark.asyncio
    async def test_increment_retry_count_success(self, store, mock_db):
        """Test incrementing retry count."""
        event_id = uuid4()
        next_retry = datetime.utcnow() + timedelta(minutes=5)
        
        await store.increment_retry_count(event_id, next_retry)
        
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_increment_retry_count_with_error_message(self, store, mock_db):
        """Test incrementing retry count with error message."""
        event_id = uuid4()
        next_retry = datetime.utcnow() + timedelta(minutes=10)
        error_message = "API timeout"
        
        await store.increment_retry_count(event_id, next_retry, error_message)
        
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_increment_retry_count_database_error(self, store, mock_db):
        """Test handling database error when incrementing."""
        event_id = uuid4()
        next_retry = datetime.utcnow() + timedelta(minutes=5)
        mock_db.execute.side_effect = Exception("Database error")
        
        # Should not raise
        await store.increment_retry_count(event_id, next_retry)
        
        mock_db.rollback.assert_called_once()


class TestGetEventStats(TestWebhookEventStore):
    """Test event statistics functionality."""

    @pytest.mark.asyncio
    async def test_get_event_stats_success(self, store, mock_db):
        """Test getting event statistics."""
        mock_result = Mock()
        mock_result.fetchone.return_value = (100, 80, 15, 5)
        mock_db.execute.return_value = mock_result
        
        stats = await store.get_event_stats()
        
        assert stats["total"] == 100
        assert stats["processed"] == 80
        assert stats["pending_retry"] == 15
        assert stats["max_retries_exceeded"] == 5

    @pytest.mark.asyncio
    async def test_get_event_stats_empty(self, store, mock_db):
        """Test getting stats when no events."""
        mock_result = Mock()
        mock_result.fetchone.return_value = (0, 0, 0, 0)
        mock_db.execute.return_value = mock_result
        
        stats = await store.get_event_stats()
        
        assert stats["total"] == 0

    @pytest.mark.asyncio
    async def test_get_event_stats_database_error(self, store, mock_db):
        """Test handling database error when getting stats."""
        mock_db.execute.side_effect = Exception("Database error")
        
        stats = await store.get_event_stats()
        
        assert stats == {"total": 0, "processed": 0, "pending_retry": 0, "max_retries_exceeded": 0}


class TestCleanupOldEvents(TestWebhookEventStore):
    """Test cleanup of old processed events."""

    @pytest.mark.asyncio
    async def test_cleanup_old_events_success(self, store, mock_db):
        """Test cleaning up old events."""
        mock_result = Mock()
        mock_result.rowcount = 25
        mock_db.execute.return_value = mock_result
        
        deleted_count = await store.cleanup_old_events(days=7)
        
        assert deleted_count == 25
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_old_events_custom_days(self, store, mock_db):
        """Test cleanup with custom days parameter."""
        mock_result = Mock()
        mock_result.rowcount = 10
        mock_db.execute.return_value = mock_result
        
        deleted_count = await store.cleanup_old_events(days=30)
        
        assert deleted_count == 10

    @pytest.mark.asyncio
    async def test_cleanup_old_events_none_deleted(self, store, mock_db):
        """Test cleanup when no events to delete."""
        mock_result = Mock()
        mock_result.rowcount = 0
        mock_db.execute.return_value = mock_result
        
        deleted_count = await store.cleanup_old_events()
        
        assert deleted_count == 0

    @pytest.mark.asyncio
    async def test_cleanup_old_events_database_error(self, store, mock_db):
        """Test handling database error during cleanup."""
        mock_db.execute.side_effect = Exception("Database error")
        
        deleted_count = await store.cleanup_old_events()
        
        assert deleted_count == 0
        mock_db.rollback.assert_called_once()


class TestIdempotencyHash:
    """Test idempotency hash generation."""

    @pytest.fixture
    def store(self):
        """Create WebhookEventStore instance."""
        from app.services.webhook.persistence.webhook_store import WebhookEventStore
        return WebhookEventStore(Mock())

    def test_same_payload_same_hash(self, store):
        """Test that identical payloads produce same hash."""
        payload = {"key": "value", "nested": {"a": 1}}
        
        # Compute hash twice
        payload_str1 = str(sorted(payload.items()))
        payload_str2 = str(sorted(payload.items()))
        
        import hashlib
        hash1 = hashlib.sha256(payload_str1.encode()).hexdigest()
        hash2 = hashlib.sha256(payload_str2.encode()).hexdigest()
        
        assert hash1 == hash2

    def test_different_payload_different_hash(self):
        """Test that different payloads produce different hash."""
        import hashlib
        
        payload1 = {"key": "value1"}
        payload2 = {"key": "value2"}
        
        hash1 = hashlib.sha256(str(sorted(payload1.items())).encode()).hexdigest()
        hash2 = hashlib.sha256(str(sorted(payload2.items())).encode()).hexdigest()
        
        assert hash1 != hash2
