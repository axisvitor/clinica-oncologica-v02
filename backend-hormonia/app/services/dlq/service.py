"""
DLQ Service - Main orchestrator.

This module provides the main DLQService class that coordinates
all DLQ operations by composing smaller, focused components.

IMPORTANT: Maintains backward compatibility with original DLQService API.
"""

import logging
import time
from typing import Optional, Tuple
from uuid import UUID
from datetime import datetime

from app.models.failed_message import FailedMessage, FailureReason
from app.schemas.dlq import DLQMessageList, DLQStats

from .base import ErrorCategory
from .message_processor import DLQMessageProcessor
from .retry_handler import DLQRetryHandler
from .dead_letter_handler import DeadLetterHandler
from .metrics import DLQMetricsCollector

logger = logging.getLogger(__name__)


class DLQService:
    """
    Dead Letter Queue Service - Main orchestrator.

    Coordinates message processing, retry logic, and metrics collection
    through composition of specialized components.

    Features:
    - Automatic error categorization
    - Intelligent retry with exponential backoff
    - Administrative dashboard support
    - Comprehensive metrics and statistics
    - Pagination and filtering

    This is a refactored version maintaining full backward compatibility
    with the original DLQService API.
    """

    def __init__(self, db):
        """
        Initialize DLQ Service.

        Args:
            db: Database session
        """
        self.db = db

        # Initialize components
        self.retry_handler = DLQRetryHandler(db)
        self.message_processor = DLQMessageProcessor()
        self.dead_letter_handler = DeadLetterHandler(db, self.retry_handler)
        self.metrics_collector = DLQMetricsCollector(db)

        # Legacy properties for backward compatibility
        self.MAX_RETRY_ATTEMPTS = self.retry_handler.config.MAX_RETRY_ATTEMPTS
        self.RETRY_DELAYS = self.retry_handler.config.RETRY_DELAYS
        self.TRANSIENT_ERRORS = self.retry_handler.config.TRANSIENT_ERRORS
        self.PERMANENT_ERRORS = self.retry_handler.config.PERMANENT_ERRORS

    # ========================================================================
    # Public API Methods (Backward Compatible)
    # ========================================================================

    def categorize_error(self, error_message: str, error_type: str) -> ErrorCategory:
        """
        Categorize error for retry strategy.

        Args:
            error_message: Error message text
            error_type: Error type/class

        Returns:
            Error category
        """
        return self.retry_handler.categorize_error(error_message, error_type)

    def add_to_dlq(
        self,
        message_id: UUID,
        patient_id: UUID,
        error_message: str,
        error_type: str,
        payload: dict,
        failure_reason: FailureReason,
    ) -> FailedMessage:
        """
        Add message to Dead Letter Queue.

        Args:
            message_id: Message ID
            patient_id: Patient ID
            error_message: Error message
            error_type: Error type
            payload: Original payload
            failure_reason: Reason for failure

        Returns:
            Created FailedMessage
        """
        failed_message = self.dead_letter_handler.add_message(
            message_id=message_id,
            patient_id=patient_id,
            error_message=error_message,
            error_type=error_type,
            payload=payload,
            failure_reason=failure_reason,
        )

        # Record metrics
        self.metrics_collector.record_message_added(
            failure_reason=failure_reason,
            error_type=error_type,
        )

        self.metrics_collector.update_queue_metrics()

        return failed_message

    def retry_message(
        self,
        dlq_id: UUID,
        manual: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Retry processing a DLQ message.

        Args:
            dlq_id: DLQ entry ID
            manual: Whether this is a manual retry

        Returns:
            Tuple of (success, error_message)
        """
        start_time = time.time()

        failed_message = (
            self.db.query(FailedMessage)
            .filter(FailedMessage.id == dlq_id)
            .first()
        )

        if not failed_message:
            return False, "Message not found in DLQ"

        # Mark retry started
        self.retry_handler.mark_retry_started(failed_message)

        if manual:
            failed_message.metadata["manual_retry"] = True
            failed_message.metadata["manual_retry_at"] = datetime.utcnow().isoformat()
            self.db.commit()

        # Start processing metrics
        self.metrics_collector.start_processing(failed_message.failure_reason)

        try:
            # Try to reprocess
            success = self.message_processor.reprocess_message(failed_message)

            duration = time.time() - start_time

            if success:
                # Mark success
                self.retry_handler.mark_retry_success(failed_message)

                # Record metrics
                self.metrics_collector.record_retry_success(
                    failure_reason=failed_message.failure_reason,
                    duration_seconds=duration,
                    retry_count=failed_message.retry_count,
                )

                logger.info(
                    f"Message {failed_message.message_id} reprocessed successfully"
                )

                self.metrics_collector.update_queue_metrics()
                self.metrics_collector.end_processing(failed_message.failure_reason)

                return True, None

            else:
                # Mark failure
                self.retry_handler.mark_retry_failed(failed_message)

                # Record metrics
                error_category = failed_message.metadata.get("error_category", "unknown")
                self.metrics_collector.record_retry_failure(
                    failure_reason=failed_message.failure_reason,
                    duration_seconds=duration,
                    error_type=error_category,
                )

                self.metrics_collector.update_queue_metrics()
                self.metrics_collector.end_processing(failed_message.failure_reason)

                return False, "Failed to reprocess message"

        except Exception as e:
            duration = time.time() - start_time

            logger.error(f"Error retrying {dlq_id}: {e}", exc_info=True)

            # Mark failure
            self.retry_handler.mark_retry_failed(failed_message, str(e))

            # Record metrics
            self.metrics_collector.record_retry_failure(
                failure_reason=failed_message.failure_reason,
                duration_seconds=duration,
                error_type=type(e).__name__,
            )

            self.metrics_collector.update_queue_metrics()
            self.metrics_collector.end_processing(failed_message.failure_reason)

            return False, str(e)

    def discard_message(self, dlq_id: UUID, reason: str = "manual") -> bool:
        """
        Discard message from DLQ.

        Args:
            dlq_id: DLQ entry ID
            reason: Reason for discarding

        Returns:
            True if successful
        """
        # Get message first for metrics
        failed_message = (
            self.db.query(FailedMessage)
            .filter(FailedMessage.id == dlq_id)
            .first()
        )

        if not failed_message:
            return False

        # Discard
        success = self.dead_letter_handler.discard_message(dlq_id, reason)

        if success:
            # Record metrics
            self.metrics_collector.record_message_discarded(
                failure_reason=failed_message.failure_reason,
                discard_reason=reason,
            )

            self.metrics_collector.update_queue_metrics()

        return success

    def list_messages(
        self,
        page: int = 1,
        size: int = 20,
        status=None,
        category=None,
        patient_id=None,
    ) -> DLQMessageList:
        """
        List DLQ messages with pagination and filters.

        Args:
            page: Page number
            size: Page size
            status: Filter by status
            category: Filter by category
            patient_id: Filter by patient

        Returns:
            Paginated message list
        """
        return self.dead_letter_handler.list_messages(
            page=page,
            size=size,
            status=status,
            category=category,
            patient_id=patient_id,
        )

    def get_stats(self) -> DLQStats:
        """
        Get DLQ statistics.

        Returns:
            Statistics object
        """
        return self.dead_letter_handler.get_stats()

    def process_scheduled_retries(self) -> int:
        """
        Process scheduled retries (called by worker/cron).

        Returns:
            Number of messages processed
        """
        messages = self.dead_letter_handler.get_scheduled_retries()

        processed = 0

        for message in messages:
            try:
                success, error = self.retry_message(message.id, manual=False)

                if success:
                    processed += 1
                    logger.info(f"Auto retry successful: {message.message_id}")
                else:
                    logger.warning(f"Auto retry failed: {message.message_id} - {error}")

            except Exception as e:
                logger.error(
                    f"Error processing scheduled retry {message.id}: {e}",
                    exc_info=True,
                )

        logger.info(f"Processed {processed} scheduled retries")
        return processed

    # ========================================================================
    # Legacy Methods (For Backward Compatibility)
    # ========================================================================

    def _update_queue_metrics(self):
        """Legacy method - delegates to metrics collector."""
        self.metrics_collector.update_queue_metrics()

    def _schedule_automatic_retry(self, failed_message: FailedMessage):
        """Legacy method - delegates to retry handler."""
        self.retry_handler.schedule_retry(failed_message)

    def _reprocess_message(self, failed_message: FailedMessage) -> bool:
        """Legacy method - delegates to message processor."""
        return self.message_processor.reprocess_message(failed_message)


__all__ = ["DLQService", "ErrorCategory"]
