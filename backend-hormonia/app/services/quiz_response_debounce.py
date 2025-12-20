"""
Quiz Response Debounce Service

Prevents duplicate quiz responses from rapid messages using Redis-based debouncing.
Implements a configurable time window to ignore duplicate responses within the debounce period.

HIGH-005 Fix: Prevents multiple rapid messages being processed as different answers.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from uuid import UUID

from app.core.redis_unified import get_async_redis

logger = logging.getLogger(__name__)


class QuizResponseDebouncer:
    """
    Debounce service for quiz responses.

    Prevents processing duplicate responses within a configurable time window.
    Uses Redis for distributed debouncing across multiple worker instances.
    """

    # Default debounce window: 3 seconds
    DEFAULT_DEBOUNCE_WINDOW_SECONDS = 3

    # Redis key prefix for debounce tracking
    DEBOUNCE_KEY_PREFIX = "quiz:debounce"

    def __init__(self, debounce_window_seconds: int = DEFAULT_DEBOUNCE_WINDOW_SECONDS):
        """
        Initialize debouncer.

        Args:
            debounce_window_seconds: Time window in seconds to debounce responses (default: 3)
        """
        self.debounce_window = debounce_window_seconds
        logger.info(
            f"QuizResponseDebouncer initialized with {self.debounce_window}s window"
        )

    async def should_process_response(
        self,
        session_id: UUID,
        question_id: str,
        message_metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Check if a quiz response should be processed based on debounce state.

        Args:
            session_id: Quiz session ID
            question_id: Current question ID
            message_metadata: Optional metadata for additional context

        Returns:
            True if response should be processed, False if it should be debounced
        """
        try:
            redis_client = await get_async_redis()

            # Build debounce key: quiz:debounce:{session_id}:{question_id}
            debounce_key = self._build_debounce_key(session_id, question_id)

            # Check if key exists (response was recently processed)
            exists = await redis_client.exists(debounce_key)

            if exists:
                # Response is within debounce window - ignore
                logger.info(
                    "Quiz response debounced - ignoring duplicate",
                    extra={
                        "session_id": str(session_id),
                        "question_id": question_id,
                        "debounce_window": self.debounce_window,
                        "message_metadata": message_metadata,
                    },
                )

                # Track debounce metrics
                await self._increment_debounce_counter(session_id, question_id)

                return False

            # Response is not within debounce window - allow processing
            # Set debounce key with TTL
            await redis_client.setex(
                debounce_key,
                self.debounce_window,
                self._serialize_debounce_data(message_metadata),
            )

            logger.debug(
                "Quiz response allowed - setting debounce window",
                extra={
                    "session_id": str(session_id),
                    "question_id": question_id,
                    "debounce_window": self.debounce_window,
                },
            )

            return True

        except Exception as e:
            logger.error(
                f"Error checking debounce state - allowing response by default: {e}",
                extra={"session_id": str(session_id), "question_id": question_id},
                exc_info=True,
            )
            # On error, allow the response (fail open to prevent blocking legitimate responses)
            return True

    async def clear_debounce(
        self, session_id: UUID, question_id: Optional[str] = None
    ) -> bool:
        """
        Manually clear debounce state for a session/question.

        Useful for:
        - Force-resetting quiz state
        - Handling clarification requests
        - Administrative overrides

        Args:
            session_id: Quiz session ID
            question_id: Optional specific question ID (if None, clears all for session)

        Returns:
            True if cleared successfully
        """
        try:
            redis_client = await get_async_redis()

            if question_id:
                # Clear specific question
                debounce_key = self._build_debounce_key(session_id, question_id)
                deleted = await redis_client.delete(debounce_key)

                logger.info(
                    "Cleared debounce state for specific question",
                    extra={
                        "session_id": str(session_id),
                        "question_id": question_id,
                        "deleted": bool(deleted),
                    },
                )

                return bool(deleted)
            else:
                # Clear all questions for session (scan pattern)
                pattern = f"{self.DEBOUNCE_KEY_PREFIX}:{session_id}:*"
                cursor = 0
                deleted_count = 0

                while True:
                    cursor, keys = await redis_client.scan(
                        cursor=cursor, match=pattern, count=100
                    )

                    if keys:
                        deleted = await redis_client.delete(*keys)
                        deleted_count += deleted

                    if cursor == 0:
                        break

                logger.info(
                    "Cleared all debounce state for session",
                    extra={
                        "session_id": str(session_id),
                        "deleted_keys": deleted_count,
                    },
                )

                return deleted_count > 0

        except Exception as e:
            logger.error(
                f"Error clearing debounce state: {e}",
                extra={"session_id": str(session_id), "question_id": question_id},
                exc_info=True,
            )
            return False

    async def get_debounce_stats(self, session_id: UUID) -> Dict[str, Any]:
        """
        Get debouncing statistics for a quiz session.

        Args:
            session_id: Quiz session ID

        Returns:
            Dictionary with debounce statistics
        """
        try:
            redis_client = await get_async_redis()

            # Get debounce counter
            counter_key = f"{self.DEBOUNCE_KEY_PREFIX}:counter:{session_id}"
            debounced_count = await redis_client.get(counter_key)
            debounced_count = int(debounced_count) if debounced_count else 0

            # Get active debounce keys
            pattern = f"{self.DEBOUNCE_KEY_PREFIX}:{session_id}:*"
            cursor = 0
            active_debounces = []

            while True:
                cursor, keys = await redis_client.scan(
                    cursor=cursor, match=pattern, count=100
                )

                for key in keys:
                    # Skip counter key
                    if "counter" in key.decode():
                        continue

                    ttl = await redis_client.ttl(key)
                    active_debounces.append({"key": key.decode(), "ttl_seconds": ttl})

                if cursor == 0:
                    break

            return {
                "session_id": str(session_id),
                "total_debounced": debounced_count,
                "active_debounces": len(active_debounces),
                "debounce_window": self.debounce_window,
                "active_keys": active_debounces,
            }

        except Exception as e:
            logger.error(
                f"Error getting debounce stats: {e}",
                extra={"session_id": str(session_id)},
                exc_info=True,
            )
            return {"session_id": str(session_id), "error": str(e)}

    def _build_debounce_key(self, session_id: UUID, question_id: str) -> str:
        """
        Build Redis key for debouncing.

        Format: quiz:debounce:{session_id}:{question_id}

        Args:
            session_id: Quiz session ID
            question_id: Question ID

        Returns:
            Redis key string
        """
        return f"{self.DEBOUNCE_KEY_PREFIX}:{session_id}:{question_id}"

    def _serialize_debounce_data(
        self, message_metadata: Optional[Dict[str, Any]]
    ) -> str:
        """
        Serialize debounce data for storage.

        Args:
            message_metadata: Optional metadata

        Returns:
            Serialized data string
        """
        import json

        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": message_metadata or {},
        }

        return json.dumps(data)

    async def _increment_debounce_counter(
        self, session_id: UUID, question_id: str
    ) -> None:
        """
        Increment debounce counter for metrics.

        Args:
            session_id: Quiz session ID
            question_id: Question ID
        """
        try:
            redis_client = await get_async_redis()

            # Counter key with 24-hour TTL
            counter_key = f"{self.DEBOUNCE_KEY_PREFIX}:counter:{session_id}"
            await redis_client.incr(counter_key)
            await redis_client.expire(counter_key, 86400)  # 24 hours

        except Exception as e:
            # Don't fail on counter errors
            logger.debug(f"Failed to increment debounce counter: {e}")


# Global debouncer instance
_debouncer: Optional[QuizResponseDebouncer] = None


def get_quiz_debouncer(debounce_window_seconds: int = 3) -> QuizResponseDebouncer:
    """
    Get or create global quiz response debouncer instance.

    Args:
        debounce_window_seconds: Debounce window in seconds

    Returns:
        QuizResponseDebouncer instance
    """
    global _debouncer

    if _debouncer is None:
        _debouncer = QuizResponseDebouncer(debounce_window_seconds)

    return _debouncer
