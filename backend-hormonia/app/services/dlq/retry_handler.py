"""
Retry logic and backoff strategy for DLQ Service.

This module handles retry scheduling, backoff calculation,
and error categorization for intelligent retry.

QW-004: Enhanced with atomic retry counter support.
"""

import logging
from typing import Optional, Tuple

from datetime import datetime, timedelta

from redis.asyncio import Redis

from app.models.failed_message import FailedMessage, DLQStatus
from .base import ErrorCategory, RetryConfig
from .atomic_retry import AtomicRetryCounter, AtomicRetryScheduler

logger = logging.getLogger(__name__)


class DLQRetryHandler:
    """
    Handles retry logic and scheduling for DLQ messages.

    Features:
    - Intelligent error categorization
    - Exponential backoff
    - Automatic retry scheduling
    - Max retry enforcement
    - QW-004: Atomic retry counter for distributed safety
    """

    def __init__(self, db, redis_client: Optional[Redis] = None):
        """
        Initialize retry handler.

        Args:
            db: Database session
            redis_client: Optional Redis client for atomic operations
        """
        self.db = db
        self.redis = redis_client
        self.config = RetryConfig()

        # QW-004: Initialize atomic helpers if Redis available
        self._atomic_counter: Optional[AtomicRetryCounter] = None
        self._atomic_scheduler: Optional[AtomicRetryScheduler] = None
        if redis_client:
            self._atomic_counter = AtomicRetryCounter(redis_client, db)
            self._atomic_scheduler = AtomicRetryScheduler(redis_client, db)

    def categorize_error(
        self,
        error_message: str,
        error_type: str
    ) -> ErrorCategory:
        """
        Categorize error to determine retry strategy.

        Args:
            error_message: Error message text
            error_type: Error type/class name

        Returns:
            Error category
        """
        error_message_lower = error_message.lower()
        error_type_lower = error_type.lower()

        # Check for transient errors
        for transient_error in self.config.TRANSIENT_ERRORS:
            if (
                transient_error.lower() in error_message_lower
                or transient_error.lower() in error_type_lower
            ):
                return ErrorCategory.TRANSIENT

        # Check for permanent errors
        for permanent_error in self.config.PERMANENT_ERRORS:
            if (
                permanent_error.lower() in error_message_lower
                or permanent_error.lower() in error_type_lower
            ):
                return ErrorCategory.PERMANENT

        # Unknown error
        return ErrorCategory.UNKNOWN

    def should_retry(
        self,
        failed_message: FailedMessage
    ) -> bool:
        """
        Determine if message should be retried.

        Args:
            failed_message: Message to check

        Returns:
            True if should retry
        """
        # Check max retries
        if failed_message.retry_count >= self.config.MAX_RETRY_ATTEMPTS:
            return False

        # Check error category
        error_category = failed_message.metadata.get(
            "error_category",
            ErrorCategory.UNKNOWN.value
        )

        # Only retry transient and unknown errors
        return error_category in [
            ErrorCategory.TRANSIENT.value,
            ErrorCategory.UNKNOWN.value
        ]

    def get_retry_delay(self, retry_count: int) -> int:
        """
        Calculate delay before next retry using exponential backoff.

        Args:
            retry_count: Current retry count

        Returns:
            Delay in seconds
        """
        index = min(retry_count, len(self.config.RETRY_DELAYS) - 1)
        return self.config.RETRY_DELAYS[index]

    def schedule_retry(
        self,
        failed_message: FailedMessage
    ) -> bool:
        """
        Schedule automatic retry for message.

        Args:
            failed_message: Message to schedule

        Returns:
            True if scheduled successfully
        """
        if not self.should_retry(failed_message):
            logger.warning(
                f"Message {failed_message.message_id} cannot be retried "
                f"(retry_count: {failed_message.retry_count})"
            )

            # Mark as max retries exceeded if applicable
            if failed_message.retry_count >= self.config.MAX_RETRY_ATTEMPTS:
                failed_message.status = DLQStatus.MAX_RETRIES_EXCEEDED
                self.db.commit()

            return False

        # Calculate delay
        delay_seconds = self.get_retry_delay(failed_message.retry_count)
        next_retry_at = datetime.utcnow() + timedelta(seconds=delay_seconds)

        # Update message metadata
        failed_message.metadata["next_retry_at"] = next_retry_at.isoformat()
        failed_message.status = DLQStatus.RETRY_SCHEDULED
        self.db.commit()

        logger.info(
            f"Retry scheduled for {failed_message.message_id} "
            f"in {delay_seconds}s (attempt {failed_message.retry_count + 1}/"
            f"{self.config.MAX_RETRY_ATTEMPTS})"
        )

        return True

    def is_retry_due(self, failed_message: FailedMessage) -> bool:
        """
        Check if scheduled retry is due.

        Args:
            failed_message: Message to check

        Returns:
            True if retry should be executed now
        """
        if failed_message.status != DLQStatus.RETRY_SCHEDULED:
            return False

        next_retry_str = failed_message.metadata.get("next_retry_at")
        if not next_retry_str:
            return False

        try:
            next_retry = datetime.fromisoformat(next_retry_str)
            return datetime.utcnow() >= next_retry
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid next_retry_at format: {e}")
            return False

    def mark_retry_started(self, failed_message: FailedMessage) -> None:
        """
        Mark message as being retried (LEGACY - non-atomic).

        Args:
            failed_message: Message being retried

        DEPRECATED: Use mark_retry_started_atomic for distributed safety.
        """
        failed_message.retry_count += 1
        failed_message.status = DLQStatus.RETRYING
        failed_message.last_retry_at = datetime.utcnow()
        self.db.commit()

    async def mark_retry_started_atomic(
        self,
        failed_message: FailedMessage
    ) -> Tuple[bool, int]:
        """
        Mark message as being retried with atomic increment.

        QW-004: Uses atomic retry counter for distributed safety.

        Args:
            failed_message: Message being retried

        Returns:
            Tuple of (can_retry, new_count)
        """
        if not self._atomic_counter:
            # Fallback to legacy if no Redis
            self.mark_retry_started(failed_message)
            return True, failed_message.retry_count

        # Atomic increment
        success, new_count = await self._atomic_counter.atomic_increment_retry(
            failed_message.message_id,
            self.config.MAX_RETRY_ATTEMPTS
        )

        if not success:
            # Max retries exceeded
            await self._atomic_counter.mark_max_retries_exceeded(
                failed_message.message_id,
                failed_message
            )
            return False, new_count

        # Update database (non-blocking, for consistency)
        failed_message.retry_count = new_count
        failed_message.status = DLQStatus.RETRYING
        failed_message.last_retry_at = datetime.utcnow()
        self.db.commit()

        return True, new_count

    async def try_acquire_for_retry(
        self,
        failed_message: FailedMessage,
        lock_ttl: int = 120
    ) -> Tuple[bool, int, Optional[str]]:
        """
        Attempt to acquire message for retry processing.

        QW-004: Combines lock acquisition with atomic retry increment.

        Args:
            failed_message: Message to process
            lock_ttl: Lock time-to-live

        Returns:
            Tuple of (can_process, retry_count, lock_id)
        """
        if not self._atomic_counter:
            # Fallback without atomic support
            self.mark_retry_started(failed_message)
            return True, failed_message.retry_count, None

        return await self._atomic_counter.atomic_try_process(
            failed_message.message_id,
            self.config.MAX_RETRY_ATTEMPTS,
            lock_ttl
        )

    def mark_retry_success(self, failed_message: FailedMessage) -> None:
        """
        Mark retry as successful.

        Args:
            failed_message: Successfully processed message
        """
        failed_message.status = DLQStatus.RESOLVED
        failed_message.resolved_at = datetime.utcnow()
        self.db.commit()

    def mark_retry_failed(
        self,
        failed_message: FailedMessage,
        error_message: Optional[str] = None
    ) -> None:
        """
        Mark retry as failed and schedule next retry if applicable.

        Args:
            failed_message: Message that failed retry
            error_message: Optional error message
        """
        if error_message:
            failed_message.error_message = error_message

        # Try to schedule next retry
        if not self.schedule_retry(failed_message):
            # Cannot retry anymore
            error_category = failed_message.metadata.get("error_category")

            if error_category == ErrorCategory.PERMANENT.value:
                # Permanent error - mark as pending for manual intervention
                failed_message.status = DLQStatus.PENDING
            else:
                # Max retries exceeded
                failed_message.status = DLQStatus.MAX_RETRIES_EXCEEDED

            self.db.commit()


__all__ = ["DLQRetryHandler"]
