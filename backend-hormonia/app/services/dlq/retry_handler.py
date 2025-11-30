"""
Retry logic and backoff strategy for DLQ Service.

This module handles retry scheduling, backoff calculation,
and error categorization for intelligent retry.
"""

import logging
from typing import Optional
from datetime import datetime, timedelta

from app.models.failed_message import FailedMessage, DLQStatus
from .base import ErrorCategory, RetryConfig

logger = logging.getLogger(__name__)


class DLQRetryHandler:
    """
    Handles retry logic and scheduling for DLQ messages.

    Features:
    - Intelligent error categorization
    - Exponential backoff
    - Automatic retry scheduling
    - Max retry enforcement
    """

    def __init__(self, db):
        """
        Initialize retry handler.

        Args:
            db: Database session
        """
        self.db = db
        self.config = RetryConfig()

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
        Mark message as being retried.

        Args:
            failed_message: Message being retried
        """
        failed_message.retry_count += 1
        failed_message.status = DLQStatus.RETRYING
        failed_message.last_retry_at = datetime.utcnow()
        self.db.commit()

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
