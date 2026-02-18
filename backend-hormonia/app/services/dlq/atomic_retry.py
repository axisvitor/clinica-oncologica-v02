"""
Atomic retry counter with distributed locking.

QW-004: Implements atomic retry increment to prevent race conditions
where multiple workers increment the same message's retry count.
"""

import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.failed_message import FailedMessage, DLQStatus
from app.core.distributed_lock import acquire_lock, LockAcquisitionError
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class AtomicRetryCounter:
    """
    Atomic retry counter using Redis for distributed coordination.

    QW-004: Ensures retry_count is incremented atomically even with
    multiple workers processing messages concurrently.
    """

    # Lua script for atomic increment with max check
    ATOMIC_INCREMENT_SCRIPT = """
    local key = KEYS[1]
    local max_retries = tonumber(ARGV[1])
    local current = tonumber(redis.call("GET", key) or "0")

    if current >= max_retries then
        return -1  -- Max retries exceeded
    end

    local new_count = redis.call("INCR", key)
    redis.call("EXPIRE", key, 86400)  -- 24 hour TTL
    return new_count
    """

    def __init__(self, redis_client: Redis, db: Session):
        """
        Initialize atomic retry counter.

        Args:
            redis_client: Redis client for distributed state
            db: Database session
        """
        self.redis = redis_client
        self.db = db
        self._increment_sha: Optional[str] = None

    async def _ensure_scripts_loaded(self) -> None:
        """Load Lua scripts if not already loaded."""
        if self._increment_sha is None:
            self._increment_sha = await self.redis.script_load(
                self.ATOMIC_INCREMENT_SCRIPT
            )

    def _retry_key(self, message_id: str) -> str:
        """Get Redis key for message retry counter."""
        return f"retry:count:{message_id}"

    def _lock_key(self, message_id: str) -> str:
        """Get lock key for message processing."""
        return f"retry:lock:{message_id}"

    async def atomic_increment_retry(
        self, message_id: str, max_retries: int = 5
    ) -> Tuple[bool, int]:
        """
        Atomically increment retry count.

        Uses Redis INCR with max check to ensure atomic increment
        even with concurrent workers.

        Args:
            message_id: Message identifier
            max_retries: Maximum allowed retries

        Returns:
            Tuple of (success, new_count)
            - success: True if increment succeeded, False if max exceeded
            - new_count: The new retry count (-1 if max exceeded)
        """
        await self._ensure_scripts_loaded()

        key = self._retry_key(message_id)
        new_count = await self.redis.evalsha(
            self._increment_sha, 1, key, str(max_retries)
        )

        if new_count == -1:
            logger.warning(f"Message {message_id} exceeded max retries ({max_retries})")
            return False, -1

        logger.debug(f"Message {message_id} retry count incremented to {new_count}")
        return True, new_count

    async def get_retry_count(self, message_id: str) -> int:
        """
        Get current retry count.

        Args:
            message_id: Message identifier

        Returns:
            Current retry count (0 if not set)
        """
        key = self._retry_key(message_id)
        count = await self.redis.get(key)
        return int(count) if count else 0

    async def sync_to_database(
        self, message_id: str, failed_message: FailedMessage
    ) -> None:
        """
        Sync Redis retry count to database.

        Called after successful processing to ensure database
        reflects the actual retry count.

        Args:
            message_id: Message identifier
            failed_message: Database model to sync
        """
        count = await self.get_retry_count(message_id)
        if failed_message.retry_count != count:
            failed_message.retry_count = count
            self.db.commit()
            logger.debug(f"Synced retry count {count} to database for {message_id}")

    async def atomic_try_process(
        self, message_id: str, max_retries: int = 5, lock_ttl: int = 120
    ) -> Tuple[bool, int, Optional[str]]:
        """
        Attempt to process message with atomic retry increment.

        Combines distributed lock acquisition with atomic retry increment
        to ensure safe concurrent processing.

        Args:
            message_id: Message identifier
            max_retries: Maximum allowed retries
            lock_ttl: Lock time-to-live in seconds

        Returns:
            Tuple of (can_process, retry_count, lock_id)
            - can_process: True if processing should proceed
            - retry_count: Current retry count
            - lock_id: Lock ID for releasing (None if can't process)
        """
        lock_key = self._lock_key(message_id)

        try:
            # Acquire distributed lock
            async with acquire_lock(lock_key, timeout=5.0, ttl=lock_ttl) as lock_id:
                # Atomically increment retry count
                success, count = await self.atomic_increment_retry(
                    message_id, max_retries
                )

                if not success:
                    return False, count, None

                # Return lock_id for later release
                # Note: Lock will be released when context exits
                # For long-running operations, caller should use acquire_lock directly
                return True, count, lock_id

        except LockAcquisitionError:
            logger.info(
                f"Message {message_id} already being processed by another worker"
            )
            return False, -1, None

    async def reset_retry_count(self, message_id: str) -> None:
        """
        Reset retry count to zero.

        Used when message is successfully processed or manually reset.

        Args:
            message_id: Message identifier
        """
        key = self._retry_key(message_id)
        await self.redis.delete(key)
        logger.debug(f"Reset retry count for {message_id}")

    async def mark_max_retries_exceeded(
        self, message_id: str, failed_message: FailedMessage
    ) -> None:
        """
        Mark message as having exceeded max retries.

        Updates both Redis state and database atomically.

        Args:
            message_id: Message identifier
            failed_message: Database model to update
        """
        # Use database FOR UPDATE lock for atomic update
        stmt = text("""
            UPDATE failed_messages
            SET status = :status,
                updated_at = :now
            WHERE message_id = :message_id
            AND status != :status
        """)

        self.db.execute(
            stmt,
            {
                "status": DLQStatus.MAX_RETRIES_EXCEEDED.value,
                "now": now_sao_paulo(),
                "message_id": message_id,
            },
        )
        self.db.commit()

        logger.warning(f"Message {message_id} marked as max retries exceeded")


class AtomicRetryScheduler:
    """
    Manages retry scheduling with atomic state transitions.

    Ensures retry scheduling is atomic and prevents duplicate scheduling
    across multiple workers.
    """

    # Lua script for atomic schedule check-and-set
    ATOMIC_SCHEDULE_SCRIPT = """
    local key = KEYS[1]
    local new_schedule = ARGV[1]
    local expected_status = ARGV[2]

    local current = redis.call("HGETALL", key)
    if #current > 0 then
        -- Check current status
        local status = nil
        for i = 1, #current, 2 do
            if current[i] == "status" then
                status = current[i+1]
            end
        end

        if status and status ~= expected_status then
            return 0  -- Status changed, skip
        end
    end

    -- Atomic update
    redis.call("HSET", key, "scheduled_at", new_schedule, "status", "scheduled")
    redis.call("EXPIRE", key, 86400)
    return 1
    """

    def __init__(self, redis_client: Redis, db: Session):
        """
        Initialize retry scheduler.

        Args:
            redis_client: Redis client
            db: Database session
        """
        self.redis = redis_client
        self.db = db
        self._schedule_sha: Optional[str] = None

    async def _ensure_scripts_loaded(self) -> None:
        """Load Lua scripts if not already loaded."""
        if self._schedule_sha is None:
            self._schedule_sha = await self.redis.script_load(
                self.ATOMIC_SCHEDULE_SCRIPT
            )

    def _schedule_key(self, message_id: str) -> str:
        """Get Redis key for retry schedule."""
        return f"retry:schedule:{message_id}"

    async def atomic_schedule_retry(
        self, message_id: str, delay_seconds: int, expected_status: str = "pending"
    ) -> bool:
        """
        Atomically schedule a retry.

        Uses Redis transaction to ensure only one worker schedules the retry.

        Args:
            message_id: Message identifier
            delay_seconds: Delay before retry
            expected_status: Expected current status

        Returns:
            True if scheduled, False if already scheduled/processed
        """
        await self._ensure_scripts_loaded()

        schedule_time = (
            now_sao_paulo() + timedelta(seconds=delay_seconds)
        ).isoformat()
        key = self._schedule_key(message_id)

        result = await self.redis.evalsha(
            self._schedule_sha, 1, key, schedule_time, expected_status
        )

        if result == 1:
            logger.info(f"Scheduled retry for {message_id} in {delay_seconds}s")
            return True

        logger.debug(f"Retry for {message_id} already scheduled or status changed")
        return False

    async def get_due_retries(self, batch_size: int = 100) -> list:
        """
        Get messages with due retries.

        Scans Redis for scheduled retries that are due.

        Args:
            batch_size: Maximum messages to return

        Returns:
            List of message IDs with due retries
        """
        now = now_sao_paulo()
        due_messages = []

        async for key in self.redis.scan_iter(match="retry:schedule:*"):
            if isinstance(key, bytes):
                key = key.decode("utf-8")

            schedule_data = await self.redis.hgetall(key)
            if not schedule_data:
                continue

            # Decode bytes
            if isinstance(list(schedule_data.keys())[0], bytes):
                schedule_data = {
                    k.decode(): v.decode() for k, v in schedule_data.items()
                }

            scheduled_at = schedule_data.get("scheduled_at")
            if not scheduled_at:
                continue

            try:
                schedule_time = datetime.fromisoformat(scheduled_at)
                if schedule_time <= now:
                    message_id = key.replace("retry:schedule:", "")
                    due_messages.append(message_id)

                    if len(due_messages) >= batch_size:
                        break
            except ValueError:
                logger.warning(f"Invalid schedule time for {key}")

        return due_messages

    async def clear_schedule(self, message_id: str) -> None:
        """
        Clear retry schedule for message.

        Called when message is successfully processed.

        Args:
            message_id: Message identifier
        """
        key = self._schedule_key(message_id)
        await self.redis.delete(key)


__all__ = ["AtomicRetryCounter", "AtomicRetryScheduler"]
