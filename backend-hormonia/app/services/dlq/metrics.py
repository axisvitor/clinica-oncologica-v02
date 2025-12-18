"""
Metrics collection and monitoring for DLQ Service.

This module handles Prometheus metrics collection and
queue size monitoring for the DLQ system.
"""

import logging
from datetime import datetime

from sqlalchemy import func

from app.models.failed_message import FailedMessage, FailureReason
from app.monitoring.dlq_metrics import (
    record_dlq_message,
    record_dlq_retry,
    record_dlq_discard,
    update_dlq_queue_size,
    update_oldest_message_age,
    update_processing_count,
    record_retry_attempts,
    initialize_dlq_metrics,
)
from .base import RetryConfig

logger = logging.getLogger(__name__)


class DLQMetricsCollector:
    """
    Collects and reports DLQ metrics to Prometheus.

    Features:
    - Message addition tracking
    - Retry attempt tracking
    - Queue size monitoring
    - Age tracking
    - Processing metrics
    """

    def __init__(self, db):
        """
        Initialize metrics collector.

        Args:
            db: Database session
        """
        self.db = db
        self._initialize_metrics()

    def _initialize_metrics(self) -> None:
        """Initialize DLQ metrics with configuration."""
        config = RetryConfig()

        metrics_config = {
            "max_retries": config.MAX_RETRY_ATTEMPTS,
            "retry_delay_seconds": config.RETRY_DELAYS[0],
            "max_age_hours": 72,
            "retention_days": 30,
        }

        initialize_dlq_metrics(metrics_config)

    def record_message_added(
        self, failure_reason: FailureReason, error_type: str, source: str = "system"
    ) -> None:
        """
        Record message added to DLQ.

        Args:
            failure_reason: Reason for failure
            error_type: Type of error
            source: Source of the message
        """
        record_dlq_message(
            category=failure_reason.value,
            source=source,
            error_type=error_type,
            message_age_seconds=0,
        )

    def record_retry_success(
        self, failure_reason: FailureReason, duration_seconds: float, retry_count: int
    ) -> None:
        """
        Record successful retry.

        Args:
            failure_reason: Original failure reason
            duration_seconds: Processing duration
            retry_count: Number of retries
        """
        record_dlq_retry(
            category=failure_reason.value,
            status="success",
            duration_seconds=duration_seconds,
        )

        record_retry_attempts(
            category=failure_reason.value,
            attempts=retry_count,
        )

    def record_retry_failure(
        self, failure_reason: FailureReason, duration_seconds: float, error_type: str
    ) -> None:
        """
        Record failed retry.

        Args:
            failure_reason: Original failure reason
            duration_seconds: Processing duration
            error_type: Error type from retry
        """
        record_dlq_retry(
            category=failure_reason.value,
            status="failed",
            duration_seconds=duration_seconds,
            error_type=error_type,
        )

    def record_message_discarded(
        self, failure_reason: FailureReason, discard_reason: str
    ) -> None:
        """
        Record message discarded.

        Args:
            failure_reason: Original failure reason
            discard_reason: Reason for discarding
        """
        record_dlq_discard(
            category=failure_reason.value,
            reason=discard_reason,
        )

    def update_queue_metrics(self) -> None:
        """Update queue size and age metrics."""
        try:
            # Count messages by category and status
            results = (
                self.db.query(
                    FailedMessage.failure_reason,
                    FailedMessage.status,
                    func.count(FailedMessage.id).label("count"),
                )
                .group_by(FailedMessage.failure_reason, FailedMessage.status)
                .all()
            )

            for failure_reason, status, count in results:
                update_dlq_queue_size(
                    category=failure_reason.value,
                    status=status.value,
                    size=count,
                )

            # Update oldest message age
            oldest = (
                self.db.query(FailedMessage).order_by(FailedMessage.created_at).first()
            )

            if oldest:
                age_seconds = (datetime.utcnow() - oldest.created_at).total_seconds()
                update_oldest_message_age(
                    category=oldest.failure_reason.value,
                    age_seconds=age_seconds,
                )

        except Exception as e:
            logger.error(f"Error updating DLQ metrics: {e}", exc_info=True)

    def start_processing(self, failure_reason: FailureReason) -> None:
        """
        Mark processing started.

        Args:
            failure_reason: Failure reason category
        """
        update_processing_count(failure_reason.value, 1)

    def end_processing(self, failure_reason: FailureReason) -> None:
        """
        Mark processing ended.

        Args:
            failure_reason: Failure reason category
        """
        update_processing_count(failure_reason.value, 0)


__all__ = ["DLQMetricsCollector"]
