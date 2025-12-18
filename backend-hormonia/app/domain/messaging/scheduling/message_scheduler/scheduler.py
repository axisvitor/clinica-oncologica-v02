"""
Core MessageScheduler service for time-based message delivery.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.message import (
    Message,
    MessageType,
    MessageDirection,
    MessageStatus,
    DeliveryStatus,
)
from app.repositories.patient import PatientRepository
from app.repositories.message import MessageRepository
from app.domain.messaging.delivery import MessageSender
from app.exceptions import ValidationError, NotFoundError
from app.utils.db_retry import with_db_retry

from .models import SchedulingWindow
from .config import MessageSchedulerConfig
from .timezone_handler import TimezoneHandler
from .task_scheduler import TaskScheduler
from .retry_handler import RetryHandler
from .metrics import MetricsCollector

logger = logging.getLogger(__name__)


class MessageScheduler:
    """
    Service for scheduling and managing time-based message delivery.
    Handles patient timezone preferences, appropriate sending hours, and Celery integration.
    """

    def __init__(self, db: Session, config: MessageSchedulerConfig = None):
        self.db = db
        self.config = config or MessageSchedulerConfig()

        if db:
            self.patient_repo = PatientRepository(db)
            self.message_repo = MessageRepository(db)
            self.message_sender = MessageSender(db)

        # Initialize component handlers
        self.timezone_handler = TimezoneHandler(self.config)
        self.task_scheduler = TaskScheduler()
        self.retry_handler = RetryHandler(db, self.config)
        self.metrics_collector = MetricsCollector(db)

    @with_db_retry(max_retries=3)
    async def schedule_message(
        self,
        patient_id: UUID,
        message_content: str,
        scheduling_window: SchedulingWindow = SchedulingWindow.BUSINESS_HOURS,
        message_type: str = "text",
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Schedule a message for delivery to a patient.

        Args:
            patient_id: Patient UUID
            message_content: Message content to send
            scheduling_window: When to send the message
            message_type: Type of message (text, interactive, etc.)
            metadata: Additional message metadata

        Returns:
            Scheduling result with task information
        """
        # Input validation
        if not patient_id:
            raise ValidationError("Patient ID is required")

        if not message_content or not message_content.strip():
            raise ValidationError("Message content cannot be empty")

        if len(message_content) > self.config.MAX_MESSAGE_LENGTH:
            raise ValidationError(
                f"Message content exceeds maximum length ({self.config.MAX_MESSAGE_LENGTH} characters)"
            )

        if not isinstance(scheduling_window, SchedulingWindow):
            raise ValidationError("Invalid scheduling window")

        try:
            # Get patient
            patient = self.patient_repo.get(patient_id)
            if not patient:
                raise NotFoundError(f"Patient {patient_id} not found")

            # Calculate optimal delivery time
            delivery_time = await self.timezone_handler.calculate_optimal_delivery_time(
                patient, scheduling_window
            )

            # Create message record
            message = Message(
                patient_id=patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType(message_type),
                content=message_content,
                status=MessageStatus.SCHEDULED,
                scheduled_for=delivery_time,
                message_metadata=metadata or {},
            )

            # Save to database
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)

            # Schedule Celery task
            task_result = await self.task_scheduler.schedule_celery_task(
                message, delivery_time
            )

            # Update message with task ID
            message.message_metadata["celery_task_id"] = task_result.get("task_id")
            self.db.commit()

            return {
                "message_id": str(message.id),
                "patient_id": str(patient_id),
                "scheduled_for": delivery_time.isoformat(),
                "status": DeliveryStatus.SCHEDULED.value,
                "scheduling_window": scheduling_window.value,
                "task_id": task_result.get("task_id"),
            }

        except Exception as e:
            logger.error(f"Failed to schedule message for patient {patient_id}: {e}")
            raise

    @with_db_retry(max_retries=3)
    async def schedule_flow_message(
        self,
        patient_id: UUID,
        flow_day: int,
        flow_type: str,
        template_id: str,
        personalized_content: str,
        scheduling_window: SchedulingWindow = SchedulingWindow.BUSINESS_HOURS,
    ) -> Dict[str, Any]:
        """
        Schedule a flow-specific message with flow context.

        Args:
            patient_id: Patient UUID
            flow_day: Current day in the flow
            flow_type: Type of flow (initial_15_days, etc.)
            template_id: Template identifier
            personalized_content: AI-personalized message content
            scheduling_window: When to send the message

        Returns:
            Scheduling result with flow context
        """
        flow_metadata = {
            "flow_context": {
                "flow_day": flow_day,
                "flow_type": flow_type,
                "template_id": template_id,
                "personalized": True,
                "generated_at": datetime.utcnow().isoformat(),
            }
        }

        return await self.schedule_message(
            patient_id=patient_id,
            message_content=personalized_content,
            scheduling_window=scheduling_window,
            metadata=flow_metadata,
        )

    @with_db_retry(max_retries=3)
    async def cancel_scheduled_message(self, message_id: UUID) -> bool:
        """
        Cancel a scheduled message.

        Args:
            message_id: Message UUID to cancel

        Returns:
            True if cancelled successfully, False otherwise
        """
        try:
            message = self.message_repo.get(message_id)
            if not message:
                logger.warning(f"Message {message_id} not found for cancellation")
                return False

            if message.status not in [MessageStatus.SCHEDULED, MessageStatus.PENDING]:
                logger.warning(
                    f"Cannot cancel message {message_id} with status {message.status}"
                )
                return False

            # Cancel Celery task if exists
            task_id = message.message_metadata.get("celery_task_id")
            if task_id:
                self.task_scheduler.cancel_celery_task(task_id)

            # Update message status
            message.status = MessageStatus.CANCELLED
            message.message_metadata["cancelled_at"] = datetime.utcnow().isoformat()
            self.db.commit()

            return True

        except Exception as e:
            logger.error(f"Failed to cancel message {message_id}: {e}")
            return False

    @with_db_retry(max_retries=3)
    async def reschedule_message(
        self,
        message_id: UUID,
        new_delivery_time: datetime,
        reason: str = "user_requested",
    ) -> Dict[str, Any]:
        """
        Reschedule a message to a new delivery time.

        Args:
            message_id: Message UUID to reschedule
            new_delivery_time: New delivery time
            reason: Reason for rescheduling

        Returns:
            Rescheduling result
        """
        try:
            if new_delivery_time <= datetime.utcnow():
                raise ValidationError("Cannot reschedule to past time")

            message = self.message_repo.get(message_id)
            if not message:
                raise NotFoundError(f"Message {message_id} not found")

            if message.status not in [MessageStatus.SCHEDULED, MessageStatus.PENDING]:
                raise ValidationError(
                    f"Cannot reschedule message with status {message.status}"
                )

            # Cancel old task
            old_task_id = message.message_metadata.get("celery_task_id")
            if old_task_id:
                self.task_scheduler.cancel_celery_task(old_task_id)

            # Schedule new task
            task_result = await self.task_scheduler.schedule_celery_task(
                message, new_delivery_time
            )

            # Update message
            message.scheduled_for = new_delivery_time
            message.status = MessageStatus.SCHEDULED
            message.message_metadata.update(
                {
                    "celery_task_id": task_result.get("task_id"),
                    "rescheduled_at": datetime.utcnow().isoformat(),
                    "reschedule_reason": reason,
                    "previous_task_id": old_task_id,
                }
            )
            self.db.commit()

            return {
                "message_id": str(message_id),
                "new_delivery_time": new_delivery_time.isoformat(),
                "task_id": task_result.get("task_id"),
                "reason": reason,
            }

        except Exception as e:
            logger.error(f"Failed to reschedule message {message_id}: {e}")
            raise

    @with_db_retry(max_retries=3)
    async def update_delivery_status(
        self,
        message_id: UUID,
        status: DeliveryStatus,
        whatsapp_id: str = None,
        delivery_info: Dict[str, Any] = None,
    ) -> bool:
        """
        Update message delivery status.

        Args:
            message_id: Message UUID
            status: New delivery status
            whatsapp_id: WhatsApp message ID
            delivery_info: Additional delivery information

        Returns:
            True if updated successfully
        """
        try:
            message = self.message_repo.get(message_id)
            if not message:
                logger.warning(f"Message {message_id} not found for status update")
                return False

            # Update message status
            if status == DeliveryStatus.SENT:
                message.status = MessageStatus.SENT
                message.sent_at = datetime.utcnow()
            elif status == DeliveryStatus.DELIVERED:
                message.status = MessageStatus.DELIVERED
                message.delivered_at = datetime.utcnow()
            elif status == DeliveryStatus.READ:
                message.status = MessageStatus.READ
                message.read_at = datetime.utcnow()
            elif status == DeliveryStatus.FAILED:
                message.status = MessageStatus.FAILED

            if whatsapp_id:
                message.whatsapp_id = whatsapp_id

            # Update metadata
            message.message_metadata.update(
                {
                    "status_updated_at": datetime.utcnow().isoformat(),
                    "delivery_status": status.value,
                }
            )

            if delivery_info:
                message.message_metadata["delivery_tracking"] = delivery_info

            self.db.commit()
            return True

        except Exception as e:
            logger.error(
                f"Failed to update delivery status for message {message_id}: {e}"
            )
            return False

    @with_db_retry(max_retries=3)
    async def schedule_existing_message(
        self, message_id: UUID, send_time: datetime, priority: str = "normal"
    ) -> bool:
        """
        Schedule an existing message that has already been created in the database.
        This method is used when the message record exists but needs to be scheduled for delivery.

        Args:
            message_id: UUID of the existing message
            send_time: When to send the message
            priority: Message priority ('low', 'normal', 'high', 'urgent')

        Returns:
            True if scheduled successfully, False otherwise

        Raises:
            NotFoundError: If message doesn't exist
            ValidationError: If message is in invalid state for scheduling
        """
        try:
            # Validate priority
            valid_priorities = ["low", "normal", "high", "urgent"]
            if priority not in valid_priorities:
                logger.warning(f"Invalid priority '{priority}', using 'normal'")
                priority = "normal"

            # Get the existing message
            message = self.message_repo.get(message_id)
            if not message:
                raise NotFoundError(f"Message {message_id} not found")

            # Validate message state
            if message.status not in [MessageStatus.PENDING, MessageStatus.SCHEDULED]:
                raise ValidationError(
                    f"Cannot schedule message {message_id} with status {message.status}. "
                    f"Message must be in PENDING or SCHEDULED status."
                )

            # Validate send_time is in the future
            if send_time <= datetime.utcnow():
                logger.warning(
                    f"Send time {send_time} is in the past, adjusting to 1 minute from now"
                )
                send_time = datetime.utcnow() + timedelta(minutes=1)

            # Update message with scheduling information
            message.scheduled_for = send_time
            message.status = MessageStatus.SCHEDULED

            # Add priority to metadata
            if message.message_metadata is None:
                message.message_metadata = {}
            message.message_metadata["priority"] = priority
            message.message_metadata["scheduled_at"] = datetime.utcnow().isoformat()

            # Schedule Celery task
            task_result = await self.task_scheduler.schedule_celery_task(
                message, send_time
            )

            if task_result.get("task_id"):
                # Update message with task ID
                message.message_metadata["celery_task_id"] = task_result.get("task_id")
                message.message_metadata["scheduling_status"] = "success"
                self.db.commit()

                logger.info(
                    f"Successfully scheduled existing message {message_id} for {send_time.isoformat()} "
                    f"with priority {priority}, task_id: {task_result.get('task_id')}"
                )
                return True
            else:
                # Scheduling failed
                message.message_metadata["scheduling_status"] = "failed"
                message.message_metadata["scheduling_error"] = task_result.get(
                    "error", "Unknown error"
                )
                message.status = MessageStatus.FAILED
                self.db.commit()

                logger.error(
                    f"Failed to schedule message {message_id}: {task_result.get('error', 'Unknown error')}"
                )
                return False

        except NotFoundError:
            logger.error(f"Message {message_id} not found for scheduling")
            raise
        except ValidationError:
            logger.error(f"Invalid message state for scheduling: {message_id}")
            raise
        except Exception as e:
            logger.error(
                f"Failed to schedule existing message {message_id}: {e}", exc_info=True
            )
            self.db.rollback()
            return False

    @with_db_retry(max_retries=3)
    async def on_delivery_failure(
        self,
        message_id: UUID,
        failure_reason: str,
        whatsapp_error: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Handle message delivery failure with retry logic and flow state update.

        Args:
            message_id: Message UUID that failed to deliver
            failure_reason: Human-readable failure reason
            whatsapp_error: WhatsApp API error details

        Returns:
            Dict containing failure handling results
        """
        try:
            message = self.message_repo.get(message_id)
            if not message:
                logger.error(
                    f"Message {message_id} not found for delivery failure handling"
                )
                return {
                    "status": "error",
                    "message": "Message not found",
                    "message_id": str(message_id),
                }

            # Update delivery status
            message.delivery_status = DeliveryStatus.FAILED
            message.status = MessageStatus.FAILED
            message.failure_reason = failure_reason
            message.last_retry_at = datetime.utcnow()

            # Store WhatsApp error details in metadata
            if whatsapp_error:
                message.message_metadata = message.message_metadata or {}
                message.message_metadata["whatsapp_error"] = whatsapp_error
                message.message_metadata["failure_timestamp"] = (
                    datetime.utcnow().isoformat()
                )

            # Check if we should retry
            if message.retry_count < self.config.MAX_DELIVERY_RETRIES:
                # Calculate exponential backoff
                retry_delay = self.retry_handler.calculate_retry_delay(
                    message.retry_count
                )
                next_retry = datetime.utcnow() + retry_delay

                message.retry_count += 1
                message.next_retry_at = next_retry

                # Schedule retry task
                await self.retry_handler.schedule_retry(message, next_retry)

                self.db.commit()

                logger.info(
                    f"Scheduled retry {message.retry_count}/{self.config.MAX_DELIVERY_RETRIES} "
                    f"for message {message_id} at {next_retry.isoformat()}"
                )

                return {
                    "status": "retry_scheduled",
                    "message_id": str(message_id),
                    "retry_count": message.retry_count,
                    "next_retry_at": next_retry.isoformat(),
                    "failure_reason": failure_reason,
                }
            else:
                # Max retries exceeded - route to DLQ and update flow state
                message.next_retry_at = None

                # Route to DLQ before committing
                await self.retry_handler.route_to_dlq_on_max_retries(
                    message, failure_reason, whatsapp_error
                )

                self.db.commit()

                # Notify flow engine of permanent failure
                await self.retry_handler.notify_flow_engine_failure(message)

                logger.error(
                    f"Message {message_id} failed permanently after "
                    f"{message.retry_count} retries: {failure_reason}"
                )

                return {
                    "status": "permanent_failure",
                    "message_id": str(message_id),
                    "retry_count": message.retry_count,
                    "failure_reason": failure_reason,
                    "flow_notified": True,
                    "dlq_routed": True,
                }

        except Exception as e:
            logger.error(
                f"Error handling delivery failure for message {message_id}: {e}"
            )
            self.db.rollback()
            return {"status": "error", "message": str(e), "message_id": str(message_id)}

    # Delegate metrics methods to MetricsCollector
    async def get_scheduled_messages(
        self, patient_id: UUID = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get scheduled messages with optional patient filter."""
        return await self.metrics_collector.get_scheduled_messages(patient_id, limit)

    async def get_delivery_metrics(
        self, patient_id: UUID = None, days_back: int = 7
    ) -> Dict[str, Any]:
        """Get message delivery metrics."""
        return await self.metrics_collector.get_delivery_metrics(patient_id, days_back)


# Dependency injection function
def get_message_scheduler(
    db: Session, config: MessageSchedulerConfig = None
) -> MessageScheduler:
    """Get MessageScheduler instance with database session and optional configuration."""
    return MessageScheduler(db, config)
