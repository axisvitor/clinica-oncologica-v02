"""
Atomic webhook idempotency service.

QW-006: Implements atomic idempotency checks for webhooks using Redis SET NX EX
to prevent race conditions where multiple workers process the same event.
"""

import logging
import hashlib
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


class AtomicWebhookIdempotency:
    """
    Atomic webhook idempotency using Redis SET NX EX.

    QW-006: Prevents duplicate webhook processing across distributed workers
    by using atomic Redis operations.

    The pattern:
    1. Try to SET key with NX (Not eXists) and EX (Expiry)
    2. If SET returns True, we're the first to process this event
    3. If SET returns False/None, another worker already has it
    """

    # Default TTLs for different event types
    DEFAULT_TTL_SECONDS = 7200  # 2 hours
    STATUS_UPDATE_TTL = 3600  # 1 hour for status updates
    MESSAGE_TTL = 86400  # 24 hours for messages

    # Lua script for atomic acquire + get previous state
    # Returns: 1 if acquired (new event), 0 if already exists
    ACQUIRE_SCRIPT = """
    local key = KEYS[1]
    local value = ARGV[1]
    local ttl = tonumber(ARGV[2])

    -- Try to set with NX (only if not exists)
    local result = redis.call("SET", key, value, "NX", "EX", ttl)

    if result then
        return 1  -- Acquired: we're the first worker
    else
        return 0  -- Already exists: another worker processing
    end
    """

    # Lua script for conditional acquire (check processing state)
    # Used for retry scenarios where we want to re-process failed events
    CONDITIONAL_ACQUIRE_SCRIPT = """
    local key = KEYS[1]
    local value = ARGV[1]
    local ttl = tonumber(ARGV[2])
    local allow_reprocess = ARGV[3]

    local existing = redis.call("GET", key)

    if existing == nil then
        -- New event, acquire it
        redis.call("SET", key, value, "EX", ttl)
        return 1
    elseif allow_reprocess == "true" and existing == "failed" then
        -- Failed event, allow reprocessing
        redis.call("SET", key, value, "EX", ttl)
        return 2  -- Reprocessing a failed event
    else
        return 0  -- Already processed or being processed
    end
    """

    def __init__(
        self,
        redis_client: Redis,
        db: Optional[Session] = None,
        default_ttl: int = DEFAULT_TTL_SECONDS,
    ):
        """
        Initialize atomic idempotency service.

        Args:
            redis_client: Redis client for atomic operations
            db: Optional database session for fallback/persistence
            default_ttl: Default TTL for idempotency keys
        """
        self.redis = redis_client
        self.db = db
        self.default_ttl = default_ttl
        self._acquire_sha: Optional[str] = None
        self._conditional_sha: Optional[str] = None

    async def _ensure_scripts_loaded(self) -> None:
        """Load Lua scripts if not already loaded."""
        if self._acquire_sha is None:
            self._acquire_sha = await self.redis.script_load(self.ACQUIRE_SCRIPT)
        if self._conditional_sha is None:
            self._conditional_sha = await self.redis.script_load(
                self.CONDITIONAL_ACQUIRE_SCRIPT
            )

    def _get_key(self, event_type: str, event_id: str) -> str:
        """
        Generate Redis key for idempotency.

        Args:
            event_type: Type of webhook event
            event_id: Unique event identifier

        Returns:
            Redis key string
        """
        return f"webhook:idem:{event_type}:{event_id}"

    def _get_ttl(self, event_type: str) -> int:
        """
        Get appropriate TTL for event type.

        Args:
            event_type: Type of webhook event

        Returns:
            TTL in seconds
        """
        if "status" in event_type.lower():
            return self.STATUS_UPDATE_TTL
        elif "message" in event_type.lower():
            return self.MESSAGE_TTL
        return self.default_ttl

    async def try_acquire(
        self,
        event_type: str,
        event_id: str,
        worker_id: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """
        Atomically try to acquire processing rights for an event.

        Uses Redis SET NX EX for atomic check-and-set.

        Args:
            event_type: Type of webhook event (e.g., 'message', 'status')
            event_id: Unique event identifier
            worker_id: Optional worker ID for debugging
            ttl: Optional TTL override

        Returns:
            Tuple of (acquired, reason)
            - (True, "acquired") if we got processing rights
            - (False, "duplicate") if already processed/processing
        """
        key = self._get_key(event_type, event_id)
        effective_ttl = ttl or self._get_ttl(event_type)

        # Value stores processing info for debugging
        value = f"processing:{worker_id or 'unknown'}:{datetime.now(timezone.utc).isoformat()}"

        try:
            # Atomic SET NX EX
            acquired = await self.redis.set(
                key,
                value,
                nx=True,  # Only set if Not eXists
                ex=effective_ttl,
            )

            if acquired:
                logger.debug(
                    f"Acquired idempotency lock for {event_type}:{event_id}",
                    extra={"key": key, "worker": worker_id},
                )
                return True, "acquired"
            else:
                logger.info(
                    f"Duplicate webhook event detected: {event_type}:{event_id}",
                    extra={"key": key, "idempotency": "protected"},
                )
                return False, "duplicate"

        except Exception as e:
            logger.error(f"Redis idempotency check failed: {e}", exc_info=True)
            # Try DB fallback if available
            if self.db:
                return await self._try_acquire_db_fallback(event_type, event_id)
            # FAIL-CLOSED: Reject event if both Redis and DB fail
            logger.error(
                "Both Redis and DB idempotency checks failed. "
                "Rejecting event to prevent duplicates.",
                extra={"event_type": event_type, "event_id": event_id}
            )
            return False, "infrastructure_failure"

    async def try_acquire_with_script(
        self,
        event_type: str,
        event_id: str,
        worker_id: Optional[str] = None,
        allow_reprocess_failed: bool = False,
        ttl: Optional[int] = None,
    ) -> Tuple[int, str]:
        """
        Acquire using Lua script for advanced scenarios.

        Returns:
            Tuple of (status_code, reason)
            - (1, "acquired") - New event, acquired
            - (2, "reprocessing") - Failed event being reprocessed
            - (0, "duplicate") - Already processed
        """
        await self._ensure_scripts_loaded()

        key = self._get_key(event_type, event_id)
        effective_ttl = ttl or self._get_ttl(event_type)
        value = f"processing:{worker_id or 'unknown'}:{datetime.now(timezone.utc).isoformat()}"

        try:
            result = await self.redis.evalsha(
                self._conditional_sha,
                1,
                key,
                value,
                str(effective_ttl),
                "true" if allow_reprocess_failed else "false",
            )

            status_map = {1: "acquired", 2: "reprocessing", 0: "duplicate"}

            return result, status_map.get(result, "unknown")

        except Exception as e:
            logger.error(f"Lua script execution failed: {e}")
            # Fallback to simple SET NX
            acquired, reason = await self.try_acquire(
                event_type, event_id, worker_id, ttl
            )
            return 1 if acquired else 0, reason

    async def mark_completed(self, event_type: str, event_id: str) -> None:
        """
        Mark event as successfully completed.

        Updates the key value to indicate completion.

        Args:
            event_type: Type of webhook event
            event_id: Unique event identifier
        """
        key = self._get_key(event_type, event_id)

        try:
            # Update value to show completed, keep remaining TTL
            ttl = await self.redis.ttl(key)
            if ttl > 0:
                await self.redis.set(
                    key, f"completed:{datetime.now(timezone.utc).isoformat()}", ex=ttl
                )
        except Exception as e:
            logger.debug(f"Could not mark event as completed in Redis: {e}")

    async def mark_failed(
        self, event_type: str, event_id: str, error: Optional[str] = None
    ) -> None:
        """
        Mark event as failed (allows reprocessing if configured).

        Args:
            event_type: Type of webhook event
            event_id: Unique event identifier
            error: Optional error message
        """
        key = self._get_key(event_type, event_id)

        try:
            # Set to 'failed' state with short TTL for retry window
            await self.redis.set(
                key,
                f"failed:{error or 'unknown'}:{datetime.now(timezone.utc).isoformat()}",
                ex=300,  # 5 minute retry window
            )
        except Exception as e:
            logger.debug(f"Could not mark event as failed in Redis: {e}")

    async def release(self, event_type: str, event_id: str) -> None:
        """
        Release idempotency key (for error recovery).

        Only use this if processing failed and you want to allow
        immediate reprocessing.

        Args:
            event_type: Type of webhook event
            event_id: Unique event identifier
        """
        key = self._get_key(event_type, event_id)

        try:
            await self.redis.delete(key)
            logger.debug(f"Released idempotency key: {key}")
        except Exception as e:
            logger.error(f"Could not release idempotency key: {e}")

    async def is_processed(self, event_type: str, event_id: str) -> bool:
        """
        Check if event was already processed (without acquiring).

        Args:
            event_type: Type of webhook event
            event_id: Unique event identifier

        Returns:
            True if event was already processed
        """
        key = self._get_key(event_type, event_id)

        try:
            value = await self.redis.get(key)
            return value is not None
        except Exception as e:
            logger.error(f"Could not check idempotency: {e}")
            return False

    async def _try_acquire_db_fallback(
        self, event_type: str, event_id: str
    ) -> Tuple[bool, str]:
        """
        Database fallback for idempotency when Redis fails.

        Uses INSERT with ON CONFLICT for atomicity.

        Args:
            event_type: Type of webhook event
            event_id: Unique event identifier

        Returns:
            Tuple of (acquired, reason)
        """
        if not self.db:
            return True, "no_db"

        try:
            # Use INSERT ON CONFLICT for atomic insert-or-ignore
            stmt = text("""
                INSERT INTO webhook_events (
                    id, event_id, event_type, source, processed, created_at
                )
                VALUES (
                    gen_random_uuid(), :event_id, :event_type, 'webhook', false, NOW()
                )
                ON CONFLICT (event_id) DO NOTHING
                RETURNING id
            """)

            result = self.db.execute(
                stmt, {"event_id": event_id, "event_type": event_type}
            )

            row = result.fetchone()
            self.db.commit()

            if row:
                return True, "acquired_db"
            else:
                return False, "duplicate_db"

        except IntegrityError:
            self.db.rollback()
            return False, "duplicate_db"
        except Exception as e:
            self.db.rollback()
            logger.error(f"DB fallback failed: {e}")
            # Fail-open as last resort
            return True, "fallback_error"

    async def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get statistics about webhook processing.

        Returns:
            Dictionary with processing statistics
        """
        try:
            # Count keys by pattern
            processing_count = 0
            completed_count = 0
            failed_count = 0

            async for key in self.redis.scan_iter(match="webhook:idem:*"):
                value = await self.redis.get(key)
                if value:
                    if isinstance(value, bytes):
                        value = value.decode("utf-8")
                    if value.startswith("processing:"):
                        processing_count += 1
                    elif value.startswith("completed:"):
                        completed_count += 1
                    elif value.startswith("failed:"):
                        failed_count += 1

            return {
                "processing": processing_count,
                "completed": completed_count,
                "failed": failed_count,
                "total": processing_count + completed_count + failed_count,
            }

        except Exception as e:
            logger.error(f"Could not get processing stats: {e}")
            return {"error": str(e)}


def compute_event_hash(payload: Dict[str, Any]) -> str:
    """
    Compute deterministic hash for event payload.

    Used as event_id when no explicit ID is provided.

    Args:
        payload: Event payload dictionary

    Returns:
        SHA-256 hash string
    """
    # Sort keys for deterministic ordering
    payload_str = str(sorted(payload.items()))
    return hashlib.sha256(payload_str.encode()).hexdigest()


__all__ = ["AtomicWebhookIdempotency", "compute_event_hash"]
