"""
Dead Letter Queue (DLQ) handler for failed WhatsApp messages.
Routes failed messages to DLQ storage for manual review and retry.
"""

import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timedelta, timezone
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

            # Create DLQ entry using actual model fields
            failed_message = FailedMessage(
                original_message_id=message_id,
                patient_id=patient_id,
                message_content=content,
                phone_number=whatsapp_phone,
                message_type="text",  # Default type
                error_message=failure_details.get("error", str(failure_reason.value)),
                error_code=failure_reason.value,
                retry_count=retry_count,
                last_retry_at=datetime.now(timezone.utc) if retry_count > 0 else None,
                status=DLQStatus.PENDING_REVIEW.value,
                dlq_metadata={
                    **(metadata or {}),
                    "failure_reason": failure_reason.value,
                    "failure_details": failure_details,
                    "routed_at": datetime.now(timezone.utc).isoformat(),
                },
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
                    datetime.now(timezone.utc).isoformat()
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
                FailedMessage.status == DLQStatus.PENDING_REVIEW.value
            )

            if failure_reason:
                # Filter by error_code which stores the failure reason value
                query = query.filter(FailedMessage.error_code == failure_reason.value)

            messages = (
                query.order_by(FailedMessage.created_at.desc())
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

            if failed_message.status not in [
                DLQStatus.PENDING_REVIEW.value,
                DLQStatus.UNDER_REVIEW.value,
            ]:
                raise ValidationError(
                    f"Message {dlq_id} has status {failed_message.status}, cannot review"
                )

            # Update status inline (model doesn't have mark_reviewed method)
            failed_message.status = DLQStatus.RESOLVED.value if approve_retry else DLQStatus.DISCARDED.value
            failed_message.reviewed_by = reviewer_id
            failed_message.resolved_at = datetime.now(timezone.utc)
            failed_message.dlq_metadata = {
                **(failed_message.dlq_metadata or {}),
                "review_notes": notes,
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "approve_retry": approve_retry,
            }
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

            # Check if can requeue (inline logic, model doesn't have this method)
            requeue_count = (failed_message.dlq_metadata or {}).get("requeue_count", 0)
            if failed_message.status not in [DLQStatus.PENDING_REVIEW.value, DLQStatus.RESOLVED.value]:
                raise ValidationError(
                    f"Message {dlq_id} cannot be re-queued (status: {failed_message.status})"
                )

            # Create new message for retry
            from app.models.message import MessageType, MessageDirection
            from app.domain.messaging.scheduling import MessageScheduler

            retry_message = Message(
                patient_id=failed_message.patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=failed_message.message_content,
                status=MessageStatus.PENDING,
                message_metadata={
                    "dlq_retry": True,
                    "dlq_entry_id": str(failed_message.id),
                    "original_failure_reason": failed_message.error_code,
                    "requeue_count": requeue_count + 1,
                    "requeued_at": datetime.now(timezone.utc).isoformat(),
                },
            )

            self.db.add(retry_message)
            self.db.commit()
            self.db.refresh(retry_message)

            # Schedule for delivery
            scheduler = MessageScheduler(self.db)

            if immediate:
                # Schedule for immediate delivery (1 minute from now)
                send_time = datetime.now(timezone.utc) + timedelta(minutes=1)
            else:
                # Schedule for next business hours
                send_time = datetime.now(timezone.utc) + timedelta(hours=1)

            await scheduler.schedule_existing_message(
                message_id=retry_message.id, send_time=send_time, priority="high"
            )

            # Update DLQ entry inline (model doesn't have mark_requeued method)
            failed_message.status = DLQStatus.RESOLVED.value
            failed_message.dlq_metadata = {
                **(failed_message.dlq_metadata or {}),
                "requeue_count": requeue_count + 1,
                "requeued_at": datetime.now(timezone.utc).isoformat(),
                "new_message_id": str(retry_message.id),
            }
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
                "requeue_count": requeue_count + 1,
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
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

            # Get all DLQ entries in period
            entries = (
                self.db.query(FailedMessage)
                .filter(FailedMessage.created_at >= cutoff_date)
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
                # Get failure reason from error_code field
                reason = entry.error_code or "unknown"
                failure_by_reason[reason] = failure_by_reason.get(reason, 0) + 1

                # Status distribution
                status = entry.status
                status_distribution[status] = status_distribution.get(status, 0) + 1

                # Retry stats
                total_retries += entry.retry_count
                requeue_count_meta = (entry.dlq_metadata or {}).get("requeue_count", 0)
                if requeue_count_meta > 0:
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
                "analysis_date": datetime.now(timezone.utc).isoformat(),
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
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)

            critical_failures = (
                self.db.query(FailedMessage)
                .filter(
                    and_(
                        FailedMessage.created_at >= cutoff_time,
                        FailedMessage.retry_count >= 3,
                        FailedMessage.status == DLQStatus.PENDING_REVIEW.value,
                    )
                )
                .order_by(
                    FailedMessage.retry_count.desc(), FailedMessage.created_at.desc()
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
