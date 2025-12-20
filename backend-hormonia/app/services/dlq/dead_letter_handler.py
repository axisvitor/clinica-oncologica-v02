"""
Dead Letter Queue management for DLQ Service.

This module handles adding messages to DLQ, discarding messages,
and managing the queue lifecycle.
"""

import logging
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, and_

from app.models.failed_message import FailedMessage, FailureReason, DLQStatus
from app.schemas.dlq import DLQMessageResponse, DLQMessageList, DLQStats
from .base import ErrorCategory
from .retry_handler import DLQRetryHandler

logger = logging.getLogger(__name__)


class DeadLetterHandler:
    """
    Manages the Dead Letter Queue operations.

    Features:
    - Add messages to DLQ
    - Discard messages
    - List and filter messages
    - Generate statistics
    """

    def __init__(self, db, retry_handler: DLQRetryHandler):
        """
        Initialize dead letter handler.

        Args:
            db: Database session
            retry_handler: Retry handler instance
        """
        self.db = db
        self.retry_handler = retry_handler

    def add_message(
        self,
        message_id: UUID,
        patient_id: UUID,
        error_message: str,
        error_type: str,
        payload: Dict[str, Any],
        failure_reason: FailureReason,
    ) -> FailedMessage:
        """
        Add message to Dead Letter Queue.

        Args:
            message_id: Message ID
            patient_id: Patient ID
            error_message: Error message text
            error_type: Error type/class
            payload: Original message payload
            failure_reason: Reason for failure

        Returns:
            Created FailedMessage instance
        """
        # Categorize error
        category = self.retry_handler.categorize_error(error_message, error_type)

        # Create DLQ entry
        failed_message = FailedMessage(
            message_id=message_id,
            patient_id=patient_id,
            error_message=error_message,
            error_type=error_type,
            payload=payload,
            failure_reason=failure_reason,
            retry_count=0,
            status=DLQStatus.PENDING,
            metadata={
                "error_category": category.value,
                "added_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        self.db.add(failed_message)
        self.db.commit()
        self.db.refresh(failed_message)

        logger.info(f"Message added to DLQ: {message_id} (category: {category.value})")

        # Schedule automatic retry for transient errors
        if category == ErrorCategory.TRANSIENT:
            self.retry_handler.schedule_retry(failed_message)

        return failed_message

    def discard_message(self, dlq_id: UUID, reason: str = "manual") -> bool:
        """
        Discard message from DLQ (will not be processed again).

        Args:
            dlq_id: DLQ entry ID
            reason: Reason for discarding

        Returns:
            True if successful
        """
        failed_message = (
            self.db.query(FailedMessage).filter(FailedMessage.id == dlq_id).first()
        )

        if not failed_message:
            return False

        failed_message.status = DLQStatus.DISCARDED
        failed_message.resolved_at = datetime.now(timezone.utc)
        failed_message.metadata["discard_reason"] = reason
        failed_message.metadata["discarded_at"] = datetime.now(timezone.utc).isoformat()

        self.db.commit()

        logger.info(f"Message {failed_message.message_id} discarded: {reason}")

        return True

    def list_messages(
        self,
        page: int = 1,
        size: int = 20,
        status: Optional[DLQStatus] = None,
        category: Optional[ErrorCategory] = None,
        patient_id: Optional[UUID] = None,
    ) -> DLQMessageList:
        """
        List DLQ messages with pagination and filters.

        Args:
            page: Page number (1-indexed)
            size: Page size
            status: Filter by status
            category: Filter by error category
            patient_id: Filter by patient

        Returns:
            Paginated list of messages
        """
        query = self.db.query(FailedMessage)

        # Apply filters
        filters = []

        if status:
            filters.append(FailedMessage.status == status)

        if category:
            filters.append(
                FailedMessage.metadata["error_category"].astext == category.value
            )

        if patient_id:
            filters.append(FailedMessage.patient_id == patient_id)

        if filters:
            query = query.filter(and_(*filters))

        # Order by creation date (newest first)
        query = query.order_by(desc(FailedMessage.created_at))

        # Get total count
        total = query.count()

        # Paginate
        messages = query.offset((page - 1) * size).limit(size).all()

        # Convert to schema
        items = [DLQMessageResponse.from_orm(msg) for msg in messages]

        return DLQMessageList(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=(total + size - 1) // size,
        )

    def get_stats(self) -> DLQStats:
        """
        Get DLQ statistics.

        Returns:
            Statistics object
        """
        # Total messages
        total = self.db.query(FailedMessage).count()

        # By status
        pending = (
            self.db.query(FailedMessage)
            .filter(FailedMessage.status == DLQStatus.PENDING)
            .count()
        )

        retry_scheduled = (
            self.db.query(FailedMessage)
            .filter(FailedMessage.status == DLQStatus.RETRY_SCHEDULED)
            .count()
        )

        retrying = (
            self.db.query(FailedMessage)
            .filter(FailedMessage.status == DLQStatus.RETRYING)
            .count()
        )

        resolved = (
            self.db.query(FailedMessage)
            .filter(FailedMessage.status == DLQStatus.RESOLVED)
            .count()
        )

        discarded = (
            self.db.query(FailedMessage)
            .filter(FailedMessage.status == DLQStatus.DISCARDED)
            .count()
        )

        max_retries = (
            self.db.query(FailedMessage)
            .filter(FailedMessage.status == DLQStatus.MAX_RETRIES_EXCEEDED)
            .count()
        )

        # By category (last 24h)
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        recent_messages = (
            self.db.query(FailedMessage)
            .filter(FailedMessage.created_at >= yesterday)
            .all()
        )

        transient_count = sum(
            1
            for msg in recent_messages
            if msg.metadata.get("error_category") == ErrorCategory.TRANSIENT.value
        )

        permanent_count = sum(
            1
            for msg in recent_messages
            if msg.metadata.get("error_category") == ErrorCategory.PERMANENT.value
        )

        unknown_count = sum(
            1
            for msg in recent_messages
            if msg.metadata.get("error_category") == ErrorCategory.UNKNOWN.value
        )

        # Retry success rate
        total_retries = (
            self.db.query(FailedMessage).filter(FailedMessage.retry_count > 0).count()
        )

        successful_retries = resolved

        retry_success_rate = (
            (successful_retries / total_retries * 100) if total_retries > 0 else 0
        )

        return DLQStats(
            total=total,
            pending=pending,
            retry_scheduled=retry_scheduled,
            retrying=retrying,
            resolved=resolved,
            discarded=discarded,
            max_retries_exceeded=max_retries,
            transient_errors_24h=transient_count,
            permanent_errors_24h=permanent_count,
            unknown_errors_24h=unknown_count,
            retry_success_rate=round(retry_success_rate, 2),
        )

    def get_scheduled_retries(self) -> list[FailedMessage]:
        """
        Get messages scheduled for retry.

        Returns:
            List of messages ready for retry
        """
        messages = (
            self.db.query(FailedMessage)
            .filter(FailedMessage.status == DLQStatus.RETRY_SCHEDULED)
            .all()
        )

        # Filter by those that are due
        due_messages = [msg for msg in messages if self.retry_handler.is_retry_due(msg)]

        return due_messages


__all__ = ["DeadLetterHandler"]
