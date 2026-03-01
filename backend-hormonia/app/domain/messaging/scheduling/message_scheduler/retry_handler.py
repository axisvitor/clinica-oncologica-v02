"""
Retry logic and Dead Letter Queue (DLQ) handling for failed message deliveries.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.message import Message
from app.models.failed_message import FailureReason
from app.repositories.patient import PatientRepository
from app.utils.db_retry import with_db_retry
from .config import MessageSchedulerConfig
from .shared import ensure_message_metadata
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class RetryHandler:
    """Handles message delivery retry logic and DLQ routing."""

    def __init__(self, db: Session, config: MessageSchedulerConfig = None):
        self.db = db
        self.config = config or MessageSchedulerConfig()
        self.patient_repo = PatientRepository(db)

    @staticmethod
    def _ensure_message_metadata(message: Message) -> Dict[str, Any]:
        """Guarantee message.message_metadata is a mutable dict."""
        return ensure_message_metadata(message, logger)

    def calculate_retry_delay(self, retry_count: int) -> timedelta:
        """
        Calculate exponential backoff delay for retry.

        Args:
            retry_count: Current retry attempt number

        Returns:
            Timedelta for retry delay
        """
        # Exponential backoff: initial_delay * (base ^ retry_count)
        delay_minutes = self.config.RETRY_INITIAL_DELAY_MINUTES * (
            self.config.RETRY_BACKOFF_BASE**retry_count
        )

        # Cap maximum delay at 2 hours
        delay_minutes = min(delay_minutes, 120)

        return timedelta(minutes=delay_minutes)

    @with_db_retry(max_retries=3)
    async def schedule_retry(self, message: Message, retry_time: datetime) -> None:
        """
        Schedule a retry attempt for a failed message.

        Args:
            message: Message to retry
            retry_time: When to retry the message
        """
        try:
            # Import here to avoid circular imports
            from app.tasks.messaging import send_scheduled_message

            # Schedule retry task with ETA using the message id
            task_result = send_scheduled_message.apply_async(
                args=[str(message.id)],
                eta=retry_time,
            )

            # Update message metadata with retry task ID
            message_metadata = self._ensure_message_metadata(message)
            message_metadata["retry_task_id"] = task_result.id
            message_metadata["retry_scheduled_at"] = (
                now_sao_paulo().isoformat()
            )

            logger.info(
                f"Scheduled retry task {task_result.id} for message {message.id} "
                f"at {retry_time.isoformat()}"
            )

        except Exception as e:
            logger.error(f"Failed to schedule retry for message {message.id}: {e}")
            raise

    async def route_to_dlq_on_max_retries(
        self,
        message: Message,
        failure_reason: str,
        whatsapp_error: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Route message to Dead Letter Queue when max retries exceeded.

        Args:
            message: Message that exceeded max retries
            failure_reason: Human-readable failure reason
            whatsapp_error: WhatsApp API error details
        """
        try:
            from app.integrations.whatsapp.queue.dlq import DLQHandler

            # Get patient phone number
            patient = self.patient_repo.get(message.patient_id)
            whatsapp_phone = patient.phone if patient else "unknown"

            # Categorize failure reason
            categorized_reason = self.categorize_failure_reason(
                whatsapp_error or {"error": failure_reason}
            )

            # Prepare failure details
            failure_details = {
                "original_failure_reason": failure_reason,
                "whatsapp_error": whatsapp_error,
                "max_retries": message.retry_count,
                "last_retry_at": message.last_retry_at.isoformat()
                if message.last_retry_at
                else None,
                "routed_at": now_sao_paulo().isoformat(),
            }

            # Route to DLQ
            dlq_handler = DLQHandler(self.db)
            message_metadata = self._ensure_message_metadata(message)
            await dlq_handler.route_to_dlq(
                message_id=message.id,
                patient_id=message.patient_id,
                content=message.content,
                whatsapp_phone=whatsapp_phone,
                failure_reason=categorized_reason,
                failure_details=failure_details,
                retry_count=message.retry_count,
                metadata=message_metadata,
            )

            logger.info(
                f"Message {message.id} routed to DLQ after {message.retry_count} retries"
            )

        except Exception as e:
            logger.error(
                f"Failed to route message {message.id} to DLQ: {e}", exc_info=True
            )
            # Don't raise - DLQ routing failure shouldn't break delivery failure handling

    def categorize_failure_reason(
        self, delivery_info: Dict[str, Any] = None
    ) -> FailureReason:
        """
        Categorize failure reason from delivery info.

        Args:
            delivery_info: Delivery failure information

        Returns:
            Categorized FailureReason
        """
        if not delivery_info:
            return FailureReason.UNKNOWN

        error_message = str(delivery_info.get("error", "")).lower()
        error_code = delivery_info.get("error_code", "")

        # Network errors
        if "timeout" in error_message or "timed out" in error_message:
            return FailureReason.TIMEOUT
        if "network" in error_message or "connection" in error_message:
            return FailureReason.NETWORK_ERROR

        # Phone number issues
        if "invalid" in error_message and "phone" in error_message:
            return FailureReason.INVALID_PHONE
        if "blocked" in error_message or "banned" in error_message:
            return FailureReason.BLOCKED_NUMBER

        # API errors
        if "rate limit" in error_message or error_code in [429, "429"]:
            return FailureReason.RATE_LIMIT
        if error_code in [400, 401, 403, 404, 500, 502, 503, 504]:
            return FailureReason.API_ERROR

        # Max retries (explicit)
        if "max retries" in error_message or "retry limit" in error_message:
            return FailureReason.MAX_RETRIES_EXCEEDED

        return FailureReason.UNKNOWN

    @with_db_retry(max_retries=3)
    async def notify_flow_engine_failure(self, message: Message) -> None:
        """
        Notify flow engine when a message permanently fails.
        Updates flow state to prevent being stuck in "waiting" state.

        Args:
            message: Message that permanently failed
        """
        try:
            # Get flow context from message metadata
            flow_context = self._ensure_message_metadata(message).get("flow_context", {})

            if not flow_context:
                logger.warning(
                    f"No flow context found in message {message.id} metadata, "
                    f"cannot update flow state"
                )
                return

            # Import FlowStateRepository to update flow state
            from app.repositories.flow import FlowStateRepository

            flow_repo = FlowStateRepository(self.db)

            # Get active flow for patient
            active_flow = flow_repo.get_active_flow(message.patient_id)

            if not active_flow:
                logger.warning(
                    f"No active flow found for patient {message.patient_id}, "
                    f"cannot update flow state"
                )
                return

            # Update flow state to handle delivery failure
            flow_state_data = active_flow.state_data or {}
            flow_state_data["delivery_failures"] = flow_state_data.get(
                "delivery_failures", []
            )
            flow_state_data["delivery_failures"].append(
                {
                    "message_id": str(message.id),
                    "failure_timestamp": now_sao_paulo().isoformat(),
                    "failure_reason": message.failure_reason,
                    "retry_count": message.retry_count,
                    "step": active_flow.current_step,
                }
            )

            # Mark that flow should not wait for this message
            flow_state_data["skip_waiting_for_message"] = str(message.id)
            flow_state_data["last_delivery_failure"] = now_sao_paulo().isoformat()

            active_flow.state_data = flow_state_data
            self.db.commit()

            logger.info(
                f"Updated flow state for patient {message.patient_id} "
                f"due to permanent message delivery failure {message.id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to notify flow engine of delivery failure for message {message.id}: {e}"
            )
            # Don't raise - this is a best-effort notification
