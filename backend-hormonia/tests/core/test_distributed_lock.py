"""
Tests for distributed locking module.

Tests verify:
1. Lock acquisition and release
2. Lock exclusivity (concurrent access prevention)
3. Lock expiration (TTL)
4. Lock owner validation
5. Retry with exponential backoff
6. Context manager behavior
"""

import pytest
import asyncio
import threading
import time
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from uuid import uuid4

from app.core.distributed_lock import (
    DistributedLock,
    LockAcquisitionError,
    LockReleaseError,
    LockKeys,
    get_distributed_lock,
    acquire_lock,
    acquire_lock_sync,
    with_lock,
    with_lock_sync,
)


class TestDistributedLockBasics:
    """Test basic lock operations."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock async Redis client."""
        redis = AsyncMock()
        redis.set = AsyncMock(return_value=True)
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock(return_value=1)
        redis.exists = AsyncMock(return_value=0)
        redis.evalsha = AsyncMock(return_value=1)
        redis.script_load = AsyncMock(return_value="sha123")
        return redis

    @pytest.fixture
    def mock_sync_redis(self):
        """Create mock sync Redis client."""
        redis = MagicMock()
        redis.set = MagicMock(return_value=True)
        redis.get = MagicMock(return_value=None)
        redis.delete = MagicMock(return_value=1)
        redis.exists = MagicMock(return_value=0)
        redis.evalsha = MagicMock(return_value=1)
        redis.script_load = MagicMock(return_value="sha123")
        return redis

    @pytest.mark.asyncio
    async def test_try_acquire_success(self, mock_redis):
        """Test successful lock acquisition."""
        lock = DistributedLock()
        lock._async_redis = mock_redis
        lock._release_sha = "sha123"

        lock_id = await lock.try_acquire("test:key")

        assert lock_id is not None
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert "lock:test:key" in call_args[0]
        assert call_args[1]["nx"] is True
        assert call_args[1]["ex"] == lock.ttl

    @pytest.mark.asyncio
    async def test_try_acquire_failure(self, mock_redis):
        """Test lock acquisition failure when lock is held."""
        mock_redis.set.return_value = False  # Lock already held

        lock = DistributedLock()
        lock._async_redis = mock_redis
        lock._release_sha = "sha123"

        lock_id = await lock.try_acquire("test:key")

        assert lock_id is None

    @pytest.mark.asyncio
    async def test_release_success(self, mock_redis):
        """Test successful lock release."""
        lock = DistributedLock()
        lock._async_redis = mock_redis
        lock._release_sha = "sha123"

        result = await lock.release("test:key", "lock-id-123")

        assert result is True
        mock_redis.evalsha.assert_called_once()

    @pytest.mark.asyncio
    async def test_release_not_owner(self, mock_redis):
        """Test release fails when not owner."""
        mock_redis.evalsha.return_value = 0  # Not owner or expired

        lock = DistributedLock()
        lock._async_redis = mock_redis
        lock._release_sha = "sha123"

        result = await lock.release("test:key", "wrong-lock-id")

        assert result is False


class TestLockContextManager:
    """Test context manager behavior."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock async Redis client."""
        redis = AsyncMock()
        redis.set = AsyncMock(return_value=True)
        redis.evalsha = AsyncMock(return_value=1)
        redis.script_load = AsyncMock(return_value="sha123")
        return redis

    @pytest.mark.asyncio
    async def test_async_context_manager_success(self, mock_redis):
        """Test async context manager acquires and releases."""
        lock = DistributedLock()
        lock._async_redis = mock_redis
        lock._release_sha = "sha123"

        acquired = False
        async with lock.acquire("test:key") as lock_id:
            acquired = True
            assert lock_id is not None

        assert acquired
        assert mock_redis.set.call_count == 1
        assert mock_redis.evalsha.call_count == 1  # Release

    @pytest.mark.asyncio
    async def test_context_manager_releases_on_exception(self, mock_redis):
        """Test lock is released even when exception occurs."""
        lock = DistributedLock()
        lock._async_redis = mock_redis
        lock._release_sha = "sha123"

        with pytest.raises(ValueError):
            async with lock.acquire("test:key") as lock_id:
                raise ValueError("Test error")

        # Lock should still be released
        assert mock_redis.evalsha.call_count == 1


class TestLockRetryMechanism:
    """Test retry with exponential backoff."""

    @pytest.mark.asyncio
    async def test_acquire_with_retry_success_first_try(self):
        """Test immediate acquisition on first try."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.script_load = AsyncMock(return_value="sha123")

        lock = DistributedLock()
        lock._async_redis = mock_redis
        lock._release_sha = "sha123"

        lock_id = await lock.acquire_with_retry("test:key", timeout=5.0)

        assert lock_id is not None
        assert mock_redis.set.call_count == 1

    @pytest.mark.asyncio
    async def test_acquire_with_retry_after_failures(self):
        """Test acquisition after initial failures."""
        mock_redis = AsyncMock()
        # Fail twice, then succeed
        mock_redis.set = AsyncMock(side_effect=[False, False, True])
        mock_redis.script_load = AsyncMock(return_value="sha123")

        lock = DistributedLock(retry_delay=0.01)  # Fast retries for test
        lock._async_redis = mock_redis
        lock._release_sha = "sha123"

        lock_id = await lock.acquire_with_retry("test:key", timeout=5.0)

        assert lock_id is not None
        assert mock_redis.set.call_count == 3

    @pytest.mark.asyncio
    async def test_acquire_with_retry_timeout(self):
        """Test timeout when lock cannot be acquired."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=False)  # Always fail
        mock_redis.script_load = AsyncMock(return_value="sha123")

        lock = DistributedLock(retry_delay=0.01)
        lock._async_redis = mock_redis
        lock._release_sha = "sha123"

        with pytest.raises(LockAcquisitionError) as exc_info:
            await lock.acquire_with_retry("test:key", timeout=0.1)

        assert "test:key" in str(exc_info.value)


class TestLockConcurrency:
    """Test concurrent access prevention."""

    @pytest.mark.asyncio
    async def test_concurrent_acquire_only_one_succeeds(self):
        """Test that only one concurrent acquire succeeds."""
        mock_redis = AsyncMock()
        call_count = {"count": 0}

        async def mock_set(*args, **kwargs):
            call_count["count"] += 1
            # Only first call succeeds
            return call_count["count"] == 1

        mock_redis.set = mock_set
        mock_redis.script_load = AsyncMock(return_value="sha123")
        mock_redis.evalsha = AsyncMock(return_value=1)

        lock = DistributedLock(acquire_timeout=0.5, retry_delay=0.01)
        lock._async_redis = mock_redis
        lock._release_sha = "sha123"

        results = await asyncio.gather(
            lock.try_acquire("test:key"),
            lock.try_acquire("test:key"),
            return_exceptions=True
        )

        # One should succeed, one should fail
        successes = [r for r in results if r is not None and not isinstance(r, Exception)]
        failures = [r for r in results if r is None]

        assert len(successes) == 1
        assert len(failures) == 1


class TestLockKeys:
    """Test LockKeys helper class."""

    def test_saga_key(self):
        """Test saga lock key generation."""
        key = LockKeys.saga("patient-123")
        assert key == "saga:patient:patient-123"

    def test_message_processing_key(self):
        """Test message processing lock key generation."""
        key = LockKeys.message_processing("patient-456")
        assert key == "message:processing:patient-456"

    def test_quiz_session_key(self):
        """Test quiz session lock key generation."""
        key = LockKeys.quiz_session("patient-789")
        assert key == "quiz:session:patient-789"

    def test_webhook_processing_key(self):
        """Test webhook processing lock key generation."""
        key = LockKeys.webhook_processing("webhook-abc")
        assert key == "webhook:webhook-abc"

    def test_retry_key(self):
        """Test retry lock key generation."""
        key = LockKeys.retry("message-xyz")
        assert key == "retry:message:message-xyz"


class TestLockMetrics:
    """Test lock metrics collection."""

    @pytest.mark.asyncio
    async def test_metrics_increment_on_acquire(self):
        """Test that metrics are incremented on successful acquire."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.script_load = AsyncMock(return_value="sha123")

        lock = DistributedLock()
        lock._async_redis = mock_redis
        lock._release_sha = "sha123"

        initial_acquired = lock._locks_acquired

        await lock.try_acquire("test:key")

        assert lock._locks_acquired == initial_acquired + 1

    @pytest.mark.asyncio
    async def test_metrics_increment_on_failure(self):
        """Test that failure metrics are incremented on timeout."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=False)
        mock_redis.script_load = AsyncMock(return_value="sha123")

        lock = DistributedLock(retry_delay=0.01)
        lock._async_redis = mock_redis
        lock._release_sha = "sha123"

        initial_failed = lock._locks_failed

        try:
            await lock.acquire_with_retry("test:key", timeout=0.05)
        except LockAcquisitionError:
            pass

        assert lock._locks_failed == initial_failed + 1

    def test_get_metrics(self):
        """Test get_metrics returns expected structure."""
        lock = DistributedLock(ttl=60, acquire_timeout=15)

        metrics = lock.get_metrics()

        assert "locks_acquired" in metrics
        assert "locks_released" in metrics
        assert "locks_failed" in metrics
        assert "locks_extended" in metrics
        assert metrics["default_ttl"] == 60
        assert metrics["acquire_timeout"] == 15


class TestDecoratorHelpers:
    """Test decorator helper functions."""

    @pytest.mark.asyncio
    async def test_with_lock_decorator(self):
        """Test with_lock decorator."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.evalsha = AsyncMock(return_value=1)
        mock_redis.script_load = AsyncMock(return_value="sha123")

        # Create a decorated function
        @with_lock("test:{resource_id}", timeout=1.0, ttl=10)
        async def process_resource(resource_id: str):
            return f"processed:{resource_id}"

        # Patch the redis client
        with patch("app.core.distributed_lock.get_distributed_lock") as mock_get_lock:
            lock = DistributedLock()
            lock._async_redis = mock_redis
            lock._release_sha = "sha123"
            mock_get_lock.return_value = lock

            result = await process_resource(resource_id="abc")

        assert result == "processed:abc"


class TestLockExtend:
    """Test lock extension functionality."""

    @pytest.mark.asyncio
    async def test_extend_success(self):
        """Test successful lock extension."""
        mock_redis = AsyncMock()
        mock_redis.evalsha = AsyncMock(return_value=1)
        mock_redis.script_load = AsyncMock(return_value="sha123")

        lock = DistributedLock()
        lock._async_redis = mock_redis
        lock._extend_sha = "sha456"

        result = await lock.extend("test:key", "lock-id-123", ttl=60)

        assert result is True
        mock_redis.evalsha.assert_called_once()

    @pytest.mark.asyncio
    async def test_extend_not_owner(self):
        """Test extension fails when not owner."""
        mock_redis = AsyncMock()
        mock_redis.evalsha = AsyncMock(return_value=0)
        mock_redis.script_load = AsyncMock(return_value="sha123")

        lock = DistributedLock()
        lock._async_redis = mock_redis
        lock._extend_sha = "sha456"

        result = await lock.extend("test:key", "wrong-lock-id")

        assert result is False


class TestLockIsLocked:
    """Test is_locked and get_lock_owner functionality."""

    @pytest.mark.asyncio
    async def test_is_locked_true(self):
        """Test is_locked returns True when locked."""
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=1)
        mock_redis.script_load = AsyncMock(return_value="sha123")

        lock = DistributedLock()
        lock._async_redis = mock_redis

        result = await lock.is_locked("test:key")

        assert result is True

    @pytest.mark.asyncio
    async def test_is_locked_false(self):
        """Test is_locked returns False when not locked."""
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=0)
        mock_redis.script_load = AsyncMock(return_value="sha123")

        lock = DistributedLock()
        lock._async_redis = mock_redis

        result = await lock.is_locked("test:key")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_lock_owner(self):
        """Test get_lock_owner returns lock_id."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="owner-123")
        mock_redis.script_load = AsyncMock(return_value="sha123")

        lock = DistributedLock()
        lock._async_redis = mock_redis

        result = await lock.get_lock_owner("test:key")

        assert result == "owner-123"


class TestSyncLock:
    """Test synchronous lock operations."""

    def test_try_acquire_sync_success(self):
        """Test successful sync lock acquisition."""
        mock_redis = MagicMock()
        mock_redis.set = MagicMock(return_value=True)
        mock_redis.script_load = MagicMock(return_value="sha123")

        lock = DistributedLock()
        lock._sync_redis = mock_redis
        lock._release_sha_sync = "sha123"

        lock_id = lock.try_acquire_sync("test:key")

        assert lock_id is not None
        mock_redis.set.assert_called_once()

    def test_sync_context_manager(self):
        """Test sync context manager."""
        mock_redis = MagicMock()
        mock_redis.set = MagicMock(return_value=True)
        mock_redis.evalsha = MagicMock(return_value=1)
        mock_redis.script_load = MagicMock(return_value="sha123")

        lock = DistributedLock()
        lock._sync_redis = mock_redis
        lock._release_sha_sync = "sha123"

        acquired = False
        with lock.acquire_sync("test:key") as lock_id:
            acquired = True
            assert lock_id is not None

        assert acquired
        assert mock_redis.set.call_count == 1
        assert mock_redis.evalsha.call_count == 1


class TestForceRelease:
    """Test force release functionality."""

    @pytest.mark.asyncio
    async def test_force_release(self):
        """Test force release deletes lock regardless of owner."""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=1)
        mock_redis.script_load = AsyncMock(return_value="sha123")

        lock = DistributedLock()
        lock._async_redis = mock_redis

        result = await lock.force_release("test:key")

        assert result is True
        mock_redis.delete.assert_called_once_with("lock:test:key")

    @pytest.mark.asyncio
    async def test_force_release_not_found(self):
        """Test force release when key doesn't exist."""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=0)
        mock_redis.script_load = AsyncMock(return_value="sha123")

        lock = DistributedLock()
        lock._async_redis = mock_redis

        result = await lock.force_release("nonexistent:key")

        assert result is False
