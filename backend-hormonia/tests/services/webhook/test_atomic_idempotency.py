"""
Tests for atomic webhook idempotency service.

QW-006: Tests for atomic SET NX EX based idempotency to prevent
race conditions in webhook processing.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.services.webhook.idempotency import (
    AtomicWebhookIdempotency,
    compute_event_hash
)


class TestAtomicWebhookIdempotency:
    """Tests for AtomicWebhookIdempotency class."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.set = AsyncMock(return_value=True)  # Default: SET NX succeeds
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock(return_value=1)
        redis.ttl = AsyncMock(return_value=3600)
        redis.script_load = AsyncMock(return_value="sha_hash")
        redis.evalsha = AsyncMock(return_value=1)
        redis.scan_iter = MagicMock(return_value=AsyncIteratorMock([]))
        return redis

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = MagicMock()
        db.execute = MagicMock()
        db.commit = MagicMock()
        db.rollback = MagicMock()
        return db

    @pytest.fixture
    def idempotency_service(self, mock_redis, mock_db):
        """Create idempotency service with mocks."""
        return AtomicWebhookIdempotency(mock_redis, mock_db)

    @pytest.mark.asyncio
    async def test_try_acquire_new_event(self, idempotency_service, mock_redis):
        """Test acquiring lock for new event succeeds."""
        # SET NX returns True for new key
        mock_redis.set.return_value = True

        acquired, reason = await idempotency_service.try_acquire(
            event_type="message",
            event_id="msg_123"
        )

        assert acquired is True
        assert reason == "acquired"

        # Verify SET was called with NX and EX
        mock_redis.set.assert_called_once()
        call_kwargs = mock_redis.set.call_args.kwargs
        assert call_kwargs["nx"] is True
        assert call_kwargs["ex"] == idempotency_service.MESSAGE_TTL

    @pytest.mark.asyncio
    async def test_try_acquire_duplicate_event(self, idempotency_service, mock_redis):
        """Test acquiring lock for duplicate event fails."""
        # SET NX returns False/None for existing key
        mock_redis.set.return_value = False

        acquired, reason = await idempotency_service.try_acquire(
            event_type="message",
            event_id="msg_123"
        )

        assert acquired is False
        assert reason == "duplicate"

    @pytest.mark.asyncio
    async def test_try_acquire_with_worker_id(self, idempotency_service, mock_redis):
        """Test worker ID is included in lock value."""
        mock_redis.set.return_value = True

        await idempotency_service.try_acquire(
            event_type="message",
            event_id="msg_123",
            worker_id="worker_1"
        )

        # Check that value contains worker ID
        call_args = mock_redis.set.call_args
        value = call_args[0][1]  # Second positional argument is value
        assert "worker_1" in value

    @pytest.mark.asyncio
    async def test_ttl_for_different_event_types(self, idempotency_service, mock_redis):
        """Test that different event types get different TTLs."""
        mock_redis.set.return_value = True

        # Message type should get MESSAGE_TTL (24 hours)
        await idempotency_service.try_acquire(
            event_type="message_upsert",
            event_id="msg_1"
        )
        msg_ttl = mock_redis.set.call_args.kwargs["ex"]
        assert msg_ttl == idempotency_service.MESSAGE_TTL

        mock_redis.set.reset_mock()

        # Status type should get STATUS_UPDATE_TTL (1 hour)
        await idempotency_service.try_acquire(
            event_type="status_update",
            event_id="status_1"
        )
        status_ttl = mock_redis.set.call_args.kwargs["ex"]
        assert status_ttl == idempotency_service.STATUS_UPDATE_TTL

    @pytest.mark.asyncio
    async def test_try_acquire_redis_failure_with_db_fallback(
        self, idempotency_service, mock_redis, mock_db
    ):
        """Test fallback to DB when Redis fails."""
        # Redis SET raises exception
        mock_redis.set.side_effect = Exception("Redis connection error")

        # DB fallback returns success (new event)
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("new_uuid",)
        mock_db.execute.return_value = mock_result

        acquired, reason = await idempotency_service.try_acquire(
            event_type="message",
            event_id="msg_123"
        )

        # Should succeed via DB fallback
        assert acquired is True
        assert reason == "acquired_db"

    @pytest.mark.asyncio
    async def test_try_acquire_redis_failure_no_db(self, mock_redis):
        """Test fail-open when Redis fails and no DB available."""
        mock_redis.set.side_effect = Exception("Redis connection error")

        # No DB fallback
        service = AtomicWebhookIdempotency(mock_redis, db=None)

        acquired, reason = await service.try_acquire(
            event_type="message",
            event_id="msg_123"
        )

        # Should fail-open and allow processing
        assert acquired is True
        assert reason == "fallback"

    @pytest.mark.asyncio
    async def test_mark_completed(self, idempotency_service, mock_redis):
        """Test marking event as completed."""
        mock_redis.ttl.return_value = 3600

        await idempotency_service.mark_completed(
            event_type="message",
            event_id="msg_123"
        )

        # Should update value with "completed:" prefix
        mock_redis.set.assert_called_once()
        value = mock_redis.set.call_args[0][1]
        assert value.startswith("completed:")

    @pytest.mark.asyncio
    async def test_mark_failed(self, idempotency_service, mock_redis):
        """Test marking event as failed."""
        await idempotency_service.mark_failed(
            event_type="message",
            event_id="msg_123",
            error="Processing error"
        )

        # Should set with "failed:" prefix and short TTL
        mock_redis.set.assert_called_once()
        value = mock_redis.set.call_args[0][1]
        assert value.startswith("failed:")
        assert "Processing error" in value
        assert mock_redis.set.call_args.kwargs["ex"] == 300  # 5 min retry window

    @pytest.mark.asyncio
    async def test_release_key(self, idempotency_service, mock_redis):
        """Test releasing idempotency key."""
        await idempotency_service.release(
            event_type="message",
            event_id="msg_123"
        )

        expected_key = idempotency_service._get_key("message", "msg_123")
        mock_redis.delete.assert_called_once_with(expected_key)

    @pytest.mark.asyncio
    async def test_is_processed(self, idempotency_service, mock_redis):
        """Test checking if event was processed."""
        # Event exists
        mock_redis.get.return_value = b"completed:2024-01-01"
        assert await idempotency_service.is_processed("message", "msg_123") is True

        # Event doesn't exist
        mock_redis.get.return_value = None
        assert await idempotency_service.is_processed("message", "msg_456") is False


class TestConcurrentAcquisition:
    """Tests for concurrent acquisition scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_acquire_only_one_succeeds(self):
        """Test that only one worker acquires lock in concurrent scenario."""
        # Simulate Redis behavior where only first SET NX succeeds
        call_count = 0

        async def mock_set(key, value, **kwargs):
            nonlocal call_count
            call_count += 1
            if kwargs.get("nx"):
                # Only first call succeeds
                return call_count == 1
            return True

        mock_redis = AsyncMock()
        mock_redis.set = mock_set
        mock_redis.script_load = AsyncMock(return_value="sha")

        service = AtomicWebhookIdempotency(mock_redis)

        # Simulate 3 concurrent workers trying to acquire
        results = await asyncio.gather(
            service.try_acquire("message", "msg_123", worker_id="w1"),
            service.try_acquire("message", "msg_123", worker_id="w2"),
            service.try_acquire("message", "msg_123", worker_id="w3"),
        )

        # Only one should succeed
        acquired_count = sum(1 for acquired, _ in results if acquired)
        assert acquired_count == 1

        # Others should be duplicates
        duplicate_count = sum(1 for acquired, reason in results if not acquired and reason == "duplicate")
        assert duplicate_count == 2


class TestLuaScriptAcquisition:
    """Tests for Lua script based acquisition."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client for Lua tests."""
        redis = AsyncMock()
        redis.script_load = AsyncMock(return_value="test_sha")
        redis.evalsha = AsyncMock(return_value=1)  # Default: acquired
        redis.set = AsyncMock(return_value=True)
        return redis

    @pytest.fixture
    def idempotency_service(self, mock_redis):
        """Create idempotency service with mocks."""
        return AtomicWebhookIdempotency(mock_redis)

    @pytest.mark.asyncio
    async def test_acquire_with_script_new_event(self, idempotency_service, mock_redis):
        """Test Lua script acquisition for new event."""
        mock_redis.evalsha.return_value = 1  # New event acquired

        status, reason = await idempotency_service.try_acquire_with_script(
            event_type="message",
            event_id="msg_123"
        )

        assert status == 1
        assert reason == "acquired"

    @pytest.mark.asyncio
    async def test_acquire_with_script_reprocess_failed(self, idempotency_service, mock_redis):
        """Test Lua script allows reprocessing failed events."""
        mock_redis.evalsha.return_value = 2  # Reprocessing failed event

        status, reason = await idempotency_service.try_acquire_with_script(
            event_type="message",
            event_id="msg_123",
            allow_reprocess_failed=True
        )

        assert status == 2
        assert reason == "reprocessing"

    @pytest.mark.asyncio
    async def test_acquire_with_script_duplicate(self, idempotency_service, mock_redis):
        """Test Lua script rejects duplicate event."""
        mock_redis.evalsha.return_value = 0  # Duplicate

        status, reason = await idempotency_service.try_acquire_with_script(
            event_type="message",
            event_id="msg_123"
        )

        assert status == 0
        assert reason == "duplicate"


class TestComputeEventHash:
    """Tests for event hash computation."""

    def test_hash_deterministic(self):
        """Test that same payload produces same hash."""
        payload = {"key": "value", "number": 123}

        hash1 = compute_event_hash(payload)
        hash2 = compute_event_hash(payload)

        assert hash1 == hash2

    def test_hash_order_independent(self):
        """Test that key order doesn't affect hash."""
        payload1 = {"a": 1, "b": 2, "c": 3}
        payload2 = {"c": 3, "a": 1, "b": 2}

        hash1 = compute_event_hash(payload1)
        hash2 = compute_event_hash(payload2)

        assert hash1 == hash2

    def test_different_payloads_different_hashes(self):
        """Test that different payloads produce different hashes."""
        payload1 = {"event": "message"}
        payload2 = {"event": "status"}

        hash1 = compute_event_hash(payload1)
        hash2 = compute_event_hash(payload2)

        assert hash1 != hash2

    def test_hash_is_sha256(self):
        """Test that hash is valid SHA256."""
        payload = {"test": "data"}
        hash_value = compute_event_hash(payload)

        # SHA256 produces 64 character hex string
        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)


class TestDBFallback:
    """Tests for database fallback functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_db_fallback_acquires_new_event(self, mock_db):
        """Test DB fallback successfully acquires new event."""
        mock_redis = AsyncMock()
        mock_redis.set.side_effect = Exception("Redis down")

        # DB INSERT succeeds (returns row)
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("new-uuid",)
        mock_db.execute.return_value = mock_result

        service = AtomicWebhookIdempotency(mock_redis, mock_db)

        acquired, reason = await service.try_acquire(
            event_type="message",
            event_id="msg_123"
        )

        assert acquired is True
        assert reason == "acquired_db"

    @pytest.mark.asyncio
    async def test_db_fallback_detects_duplicate(self, mock_db):
        """Test DB fallback detects duplicate event."""
        mock_redis = AsyncMock()
        mock_redis.set.side_effect = Exception("Redis down")

        # DB INSERT returns None (conflict/duplicate)
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result

        service = AtomicWebhookIdempotency(mock_redis, mock_db)

        acquired, reason = await service.try_acquire(
            event_type="message",
            event_id="msg_123"
        )

        assert acquired is False
        assert reason == "duplicate_db"


class AsyncIteratorMock:
    """Helper class for mocking async iterators."""

    def __init__(self, items):
        self.items = items
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item


class TestProcessingStats:
    """Tests for processing statistics."""

    @pytest.mark.asyncio
    async def test_get_processing_stats(self):
        """Test getting processing statistics."""
        mock_redis = AsyncMock()

        # Mock scan_iter to return some keys
        async def mock_scan():
            keys = [
                b"webhook:idem:message:1",
                b"webhook:idem:message:2",
                b"webhook:idem:status:1",
            ]
            for key in keys:
                yield key

        mock_redis.scan_iter.return_value = mock_scan()

        # Mock get to return different states
        states = {
            b"webhook:idem:message:1": b"processing:w1:2024-01-01",
            b"webhook:idem:message:2": b"completed:2024-01-01",
            b"webhook:idem:status:1": b"failed:error:2024-01-01",
        }
        mock_redis.get.side_effect = lambda k: states.get(k)

        service = AtomicWebhookIdempotency(mock_redis)
        stats = await service.get_processing_stats()

        assert stats["processing"] == 1
        assert stats["completed"] == 1
        assert stats["failed"] == 1
        assert stats["total"] == 3


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
