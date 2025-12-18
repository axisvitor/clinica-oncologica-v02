"""
Dead Letter Queue (DLQ) handler for failed WhatsApp messages.
Routes failed messages to DLQ storage for manual review and retry.
"""

import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.failed_message import FailedMessage, FailureReason, DLQStatus
from app.models.message import Message, MessageStatus
from app.models.patient import Patient
from app.repositories.base import BaseRepository
from app.exceptions import NotFoundError, ValidationError


logger = logging.getLogger(__name__)


class DLQHandler:
    """
    Dead Letter Queue handler for failed message management.

    Responsibilities:
    - Route failed messages to DLQ storage
    - Categorize failure reasons
    - Track retry attempts
    - Enable manual review and re-queue
    - Provide DLQ analytics and monitoring
    """

    def __init__(self, db: Session):
        """
        Initialize DLQ handler.

        Args:
            db: Database session
        """
        self.db = db
        self.repository = BaseRepository(FailedMessage, db)

    async def route_to_dlq(
        self,
        message_id: Optional[UUID],
        patient_id: UUID,
        content: str,
        whatsapp_phone: str,
        failure_reason: FailureReason,
        failure_details: Dict[str, Any],
        retry_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FailedMessage:
        """
        Route a failed message to the Dead Letter Queue.

        Args:
            message_id: Original message ID (may be None if message was deleted)
            patient_id: Patient UUID
            content: Message content
            whatsapp_phone: Target WhatsApp number
            failure_reason: Categorized failure reason
            failure_details: Detailed error information
            retry_count: Number of retry attempts made
            metadata: Additional context (flow info, etc.)

        Returns:
            Created FailedMessage record

        Raises:
            ValidationError: If required data is missing
        """
        try:
            # Validate required fields
            if not patient_id:
                raise ValidationError("Patient ID is required for DLQ routing")

            if not content or not content.strip():
                raise ValidationError("Message content cannot be empty")

            if not whatsapp_phone:
                raise ValidationError("WhatsApp phone number is required")

            # Check if patient exists
            patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
            if not patient:
                logger.error(f"Patient {patient_id} not found for DLQ routing")
                raise NotFoundError(f"Patient {patient_id} not found")

            # Create DLQ entry
            failed_message = FailedMessage(
                original_message_id=message_id,
                patient_id=patient_id,
                content=content,
                whatsapp_phone=whatsapp_phone,
                failure_reason=failure_reason,
                failure_details=failure_details or {},
                retry_count=retry_count,
                last_retry_at=datetime.utcnow() if retry_count > 0 else None,
                failed_at=datetime.utcnow(),
                dlq_status=DLQStatus.PENDING_REVIEW,
                dlq_metadata=metadata or {},
            )

            self.db.add(failed_message)
            self.db.commit()
            self.db.refresh(failed_message)

            logger.info(
                f"Message routed to DLQ: id={failed_message.id}, "
                f"patient={patient_id}, reason={failure_reason.value}, "
                f"retries={retry_count}"
            )

            # Update original message status if it exists
            if message_id:
                self._update_original_message_status(message_id)

            return failed_message

        except Exception as e:
            logger.error(f"Failed to route message to DLQ: {e}", exc_info=True)
            self.db.rollback()
            raise

    def _update_original_message_status(self, message_id: UUID):
        """Update original message status to FAILED."""
        try:
            message = self.db.query(Message).filter(Message.id == message_id).first()
            if message:
                message.status = MessageStatus.FAILED
                if not message.message_metadata:
                    message.message_metadata = {}
                message.message_metadata["dlq_routed_at"] = (
                    datetime.utcnow().isoformat()
                )
                self.db.commit()
        except Exception as e:
            logger.error(f"Failed to update message {message_id} status: {e}")

    async def get_pending_review(
        self,
        limit: int = 50,
        offset: int = 0,
        failure_reason: Optional[FailureReason] = None,
    ) -> List[FailedMessage]:
        """
        Get messages pending review in DLQ.

        Args:
            limit: Maximum number of results
            offset: Offset for pagination
            failure_reason: Optional filter by failure reason

        Returns:
            List of failed messages pending review
        """
        try:
            query = self.db.query(FailedMessage).filter(
                FailedMessage.dlq_status == DLQStatus.PENDING_REVIEW
            )

            if failure_reason:
                query = query.filter(FailedMessage.failure_reason == failure_reason)

            messages = (
                query.order_by(FailedMessage.failed_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )

            logger.info(
                f"Retrieved {len(messages)} pending DLQ messages (limit={limit}, offset={offset})"
            )
            return messages

        except Exception as e:
            logger.error(f"Failed to get pending DLQ messages: {e}")
            return []

    async def review_message(
        self,
        dlq_id: UUID,
        reviewer_id: UUID,
        approve_retry: bool,
        notes: Optional[str] = None,
    ) -> FailedMessage:
        """
        Review a failed message and approve/reject retry.

        Args:
            dlq_id: Failed message UUID
            reviewer_id: Admin user UUID
            approve_retry: Whether to approve for retry
            notes: Review notes

        Returns:
            Updated FailedMessage

        Raises:
            NotFoundError: If message not found
            ValidationError: If message cannot be reviewed
        """
        try:
            failed_message = self.repository.get(dlq_id)
            if not failed_message:
                raise NotFoundError(f"Failed message {dlq_id} not found in DLQ")

            if failed_message.dlq_status not in [
                DLQStatus.PENDING_REVIEW,
                DLQStatus.UNDER_REVIEW,
            ]:
                raise ValidationError(
                    f"Message {dlq_id} has status {failed_message.dlq_status.value}, cannot review"
                )

            failed_message.mark_reviewed(reviewer_id, notes, approve_retry)
            self.db.commit()
            self.db.refresh(failed_message)

            logger.info(
                f"DLQ message {dlq_id} reviewed by {reviewer_id}, "
                f"approved={approve_retry}"
            )

            return failed_message

        except Exception as e:
            logger.error(f"Failed to review DLQ message {dlq_id}: {e}")
            self.db.rollback()
            raise

    async def requeue_for_retry(
        self, dlq_id: UUID, immediate: bool = False
    ) -> Dict[str, Any]:
        """
        Re-queue a failed message for retry delivery.

        Args:
            dlq_id: Failed message UUID
            immediate: Whether to retry immediately or schedule

        Returns:
            Re-queue result with task information

        Raises:
            NotFoundError: If message not found
            ValidationError: If message cannot be re-queued
        """
        try:
            failed_message = self.repository.get(dlq_id)
            if not failed_message:
                raise NotFoundError(f"Failed message {dlq_id} not found in DLQ")

            if not failed_message.can_requeue():
                raise ValidationError(
                    f"Message {dlq_id} cannot be re-queued (status: {failed_message.dlq_status.value})"
                )

            # Create new message for retry
            from app.models.message import MessageType, MessageDirection
            from app.domain.messaging.scheduling import MessageScheduler

            retry_message = Message(
                patient_id=failed_message.patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=failed_message.content,
                status=MessageStatus.PENDING,
                message_metadata={
                    "dlq_retry": True,
                    "dlq_entry_id": str(failed_message.id),
                    "original_failure_reason": failed_message.failure_reason.value,
                    "requeue_count": failed_message.requeue_count + 1,
                    "requeued_at": datetime.utcnow().isoformat(),
                },
            )

            self.db.add(retry_message)
            self.db.commit()
            self.db.refresh(retry_message)

            # Schedule for delivery
            scheduler = MessageScheduler(self.db)

            if immediate:
                # Schedule for immediate delivery (1 minute from now)
                send_time = datetime.utcnow() + timedelta(minutes=1)
            else:
                # Schedule for next business hours
                send_time = datetime.utcnow() + timedelta(hours=1)

            await scheduler.schedule_existing_message(
                message_id=retry_message.id, send_time=send_time, priority="high"
            )

            # Update DLQ entry
            failed_message.mark_requeued()
            self.db.commit()

            logger.info(
                f"DLQ message {dlq_id} re-queued as message {retry_message.id}, "
                f"scheduled for {send_time.isoformat()}"
            )

            return {
                "dlq_id": str(dlq_id),
                "new_message_id": str(retry_message.id),
                "scheduled_for": send_time.isoformat(),
                "immediate": immediate,
                "requeue_count": failed_message.requeue_count,
            }

        except Exception as e:
            logger.error(f"Failed to re-queue DLQ message {dlq_id}: {e}")
            self.db.rollback()
            raise

    async def get_dlq_metrics(self, days_back: int = 7) -> Dict[str, Any]:
        """
        Get DLQ metrics and analytics.

        Args:
            days_back: Number of days to analyze

        Returns:
            DLQ metrics including failure reasons, counts, trends
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)

            # Get all DLQ entries in period
            entries = (
                self.db.query(FailedMessage)
                .filter(FailedMessage.failed_at >= cutoff_date)
                .all()
            )

            if not entries:
                return {
                    "total_failures": 0,
                    "failure_by_reason": {},
                    "status_distribution": {},
                    "avg_retry_count": 0,
                    "requeue_rate": 0,
                    "period_days": days_back,
                }

            # Calculate metrics
            total_failures = len(entries)
            failure_by_reason = {}
            status_distribution = {}
            total_retries = 0
            requeued_count = 0

            for entry in entries:
                # Failure reasons
                reason = entry.failure_reason.value
                failure_by_reason[reason] = failure_by_reason.get(reason, 0) + 1

                # Status distribution
                status = entry.dlq_status.value
                status_distribution[status] = status_distribution.get(status, 0) + 1

                # Retry stats
                total_retries += entry.retry_count
                if entry.requeue_count > 0:
                    requeued_count += 1

            avg_retry_count = (
                total_retries / total_failures if total_failures > 0 else 0
            )
            requeue_rate = (
                (requeued_count / total_failures * 100) if total_failures > 0 else 0
            )

            return {
                "total_failures": total_failures,
                "failure_by_reason": failure_by_reason,
                "status_distribution": status_distribution,
                "avg_retry_count": round(avg_retry_count, 2),
                "requeue_rate": round(requeue_rate, 2),
                "period_days": days_back,
                "analysis_date": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get DLQ metrics: {e}")
            return {"error": str(e)}

    async def get_critical_failures(
        self, hours_back: int = 24, limit: int = 20
    ) -> List[FailedMessage]:
        """
        Get critical failures that require immediate attention.

        Criteria:
        - High retry count (>= 3)
        - Recent failures (within hours_back)
        - Pending review status

        Args:
            hours_back: Hours to look back
            limit: Maximum results

        Returns:
            List of critical failed messages
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)

            critical_failures = (
                self.db.query(FailedMessage)
                .filter(
                    and_(
                        FailedMessage.failed_at >= cutoff_time,
                        FailedMessage.retry_count >= 3,
                        FailedMessage.dlq_status == DLQStatus.PENDING_REVIEW,
                    )
                )
                .order_by(
                    FailedMessage.retry_count.desc(), FailedMessage.failed_at.desc()
                )
                .limit(limit)
                .all()
            )

            logger.info(
                f"Found {len(critical_failures)} critical DLQ failures "
                f"in last {hours_back} hours"
            )

            return critical_failures

        except Exception as e:
            logger.error(f"Failed to get critical DLQ failures: {e}")
            return []


def get_dlq_handler(db: Session) -> DLQHandler:
    """Get DLQ handler instance."""
    return DLQHandler(db)
