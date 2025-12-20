"""
Message Handler Module.
Handles message creation, scheduling, callbacks, and retry logic.
"""

import asyncio
import logging
from typing import Optional, Any
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.domain.messaging.scheduling import MessageScheduler
from app.services.unified_whatsapp_service import UnifiedWhatsAppService, MessagingMode
from app.services.template_loader import MessageTemplate
from app.services.analytics import FlowAnalyticsService
from app.domain.flows.events import flow_event_broadcaster
from app.services.platform_synchronization import get_platform_sync_service
from app.models.message import Message, MessageType, MessageStatus, MessageDirection
from app.models.flow import PatientFlowState
from app.repositories.patient import PatientRepository
from app.repositories.flow import FlowStateRepository
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class SchedulerError(Exception):
    """Exception raised when message scheduling fails."""

    pass


class MessageHandler:
    """Handles message creation, scheduling, and lifecycle callbacks."""

    def __init__(
        self,
        db: Session,
        message_scheduler: Optional[MessageScheduler] = None,
        analytics_service: Optional[FlowAnalyticsService] = None,
    ):
        """
        Initialize message handler.

        Args:
            db: Database session
            message_scheduler: Message scheduler instance
            analytics_service: Analytics service instance
        """
        self.db = db
        self.message_scheduler = message_scheduler or MessageScheduler(db)

        # Use unified service exclusively
        self.message_sender = UnifiedWhatsAppService(
            db=db, messaging_mode=MessagingMode.HYBRID
        )

        self.analytics_service = analytics_service or FlowAnalyticsService(db)
        self.flow_broadcaster = flow_event_broadcaster
        self.platform_sync = get_platform_sync_service(db)

        self.patient_repo = PatientRepository(db)
        self.flow_state_repo = FlowStateRepository(db)

        # Register flow callbacks
        self._register_flow_callbacks()

    def _register_flow_callbacks(self):
        """Register flow-specific callbacks with message sender."""
        self.message_sender.register_flow_callback(
            "message_sent", self._on_flow_message_sent
        )
        self.message_sender.register_flow_callback(
            "message_failed", self._on_flow_message_failed
        )
        self.message_sender.register_flow_callback(
            "status_updated", self._on_flow_message_status_updated
        )

    async def create_and_schedule_flow_message(
        self,
        patient_id: UUID,
        flow_state: PatientFlowState,
        message_template: MessageTemplate,
        personalized_content: str,
        current_day: int,
        send_time: datetime,
    ) -> bool:
        """
        Create and schedule a flow message with atomic transaction safety and comprehensive error handling.

        Implements robust message creation with:
        - Atomic database operations (flush before schedule, commit only on success)
        - Retry mechanism with exponential backoff (max 3 attempts)
        - Automatic rollback on scheduling failures
        - Failed message audit trail creation
        - Transient vs permanent error detection

        Error handling strategy:
        1. SQLAlchemyError → rollback, retry if transient
        2. SchedulerError → rollback, retry if transient, create FAILED record on final failure
        3. NotFoundError → no retry, immediate failure
        4. Generic exceptions → rollback, retry if transient

        Transaction safety:
        - Message created with db.flush() to get ID without commit
        - Scheduling attempted with that ID
        - Commit ONLY if scheduling succeeds
        - Rollback if scheduling fails, with retry logic

        Args:
            patient_id: Patient UUID
            flow_state: Current patient flow state
            message_template: Template used for message
            personalized_content: AI-generated personalized message
            current_day: Current day in flow
            send_time: When to send the message

        Returns:
            bool: True if message created and scheduled successfully, False otherwise
        """
        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                # Get patient for timezone and preferences
                patient = self.patient_repo.get(patient_id)
                if not patient:
                    raise NotFoundError(f"Patient {patient_id} not found")

                # Create message object but DON'T commit yet
                message = Message(
                    patient_id=patient_id,
                    direction=MessageDirection.OUTBOUND,
                    type=MessageType.TEXT,
                    content=personalized_content,
                    status=MessageStatus.PENDING,
                    message_metadata={
                        "flow_context": {
                            "flow_state_id": str(flow_state.id),
                            "flow_type": flow_state.flow_type,
                            "current_day": current_day,
                            "template_intent": message_template.intent,
                            "ai_generated": True,
                            "personalization_level": "high",
                        },
                        "template_data": {
                            "day": message_template.day,
                            "intent": message_template.intent,
                            "core_elements": message_template.core_elements,
                            "personalization_hints": message_template.personalization_hints,
                        },
                        "retry_policy": "flow_message",
                        "creation_attempt": attempt + 1,
                    },
                )

                self.db.add(message)
                self.db.flush()  # ✅ Get ID without committing

                # Try to schedule - if this fails, rollback everything
                try:
                    scheduled = await self.message_scheduler.schedule_existing_message(
                        message_id=message.id, send_time=send_time, priority="normal"
                    )

                    if not scheduled:
                        raise SchedulerError(
                            "Scheduler returned False - scheduling failed"
                        )

                    # ✅ Only commit if scheduling succeeded
                    self.db.commit()
                    self.db.refresh(message)

                    logger.info(
                        f"Message {message.id} created and scheduled atomically (attempt {attempt + 1})"
                    )

                    # Track analytics (non-critical)
                    try:
                        await self.analytics_service.track_message_sent(
                            patient_id=patient_id,
                            message_id=message.id,
                            flow_type=flow_state.flow_type,
                            flow_day=current_day,
                            template_id=message_template.intent,
                            additional_data={
                                "ai_generated": True,
                                "personalization_level": "high",
                                "scheduled_for": send_time.isoformat(),
                                "attempt_number": attempt + 1,
                            },
                        )
                    except Exception as analytics_error:
                        logger.warning(
                            f"Analytics tracking failed (non-critical): {analytics_error}"
                        )

                    return True

                except Exception as schedule_error:
                    # ✅ Rollback message creation on scheduling failure
                    logger.error(
                        f"Scheduling failed on attempt {attempt + 1}/{max_retries} for patient {patient_id}: {schedule_error}. "
                        f"Flow: {flow_state.flow_type}, Day: {current_day}, Template: {message_template.intent}",
                        exc_info=True if attempt == max_retries - 1 else False,
                    )
                    self.db.rollback()

                    # Check if transient error worth retrying
                    if (
                        self._is_transient_error(schedule_error)
                        and attempt < max_retries - 1
                    ):
                        logger.warning(
                            f"Transient error detected, retrying in {retry_delay * (attempt + 1)}s..."
                        )
                        await asyncio.sleep(retry_delay * (attempt + 1))
                        continue

                    # Final failure - create FAILED message record
                    logger.error(
                        f"Failed after {attempt + 1} attempts: {schedule_error}"
                    )

                    # Create a failed message record for audit trail
                    failed_message = Message(
                        patient_id=patient_id,
                        direction=MessageDirection.OUTBOUND,
                        type=MessageType.TEXT,
                        content=personalized_content,
                        status=MessageStatus.FAILED,
                        message_metadata={
                            "flow_context": {
                                "flow_state_id": str(flow_state.id),
                                "flow_type": flow_state.flow_type,
                                "current_day": current_day,
                                "template_intent": message_template.intent,
                            },
                            "error": str(schedule_error),
                            "failed_at": datetime.now(timezone.utc).isoformat(),
                            "total_attempts": attempt + 1,
                            "failure_type": "scheduling_failed",
                        },
                    )
                    self.db.add(failed_message)
                    self.db.commit()

                    return False

            except SQLAlchemyError as db_error:
                logger.error(
                    f"Database error on attempt {attempt + 1}/{max_retries} for patient {patient_id}: {db_error}. "
                    f"Flow: {flow_state.flow_type}, Day: {current_day}",
                    exc_info=True if attempt == max_retries - 1 else False,
                )
                self.db.rollback()

                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    return False

            except NotFoundError:
                # Don't retry for patient not found - this is a permanent error
                logger.error(
                    f"Patient {patient_id} not found during message creation. "
                    f"Flow: {flow_state.flow_type}, Day: {current_day}. No retry.",
                    exc_info=True,
                )
                return False

            except Exception as e:
                logger.error(
                    f"Unexpected error (attempt {attempt + 1}/{max_retries}) for patient {patient_id}: {e}. "
                    f"Flow: {flow_state.flow_type}, Day: {current_day}, Template: {message_template.intent}",
                    exc_info=True,
                )
                self.db.rollback()

                if self._is_transient_error(e) and attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    return False

        logger.error(
            f"FINAL FAILURE: Failed to create and schedule message after {max_retries} retries. "
            f"Patient: {patient_id}, Flow: {flow_state.flow_type}, Day: {current_day}, Template: {message_template.intent}"
        )
        return False

    def _is_transient_error(self, error: Exception) -> bool:
        """
        Determine if error is transient and worth retrying.

        Transient errors (retry recommended):
        - Connection issues (network, database)
        - Timeout errors
        - Temporary unavailability
        - Database deadlocks

        Permanent errors (no retry):
        - Validation errors
        - Not found errors
        - Permission errors
        - Data integrity violations

        Args:
            error: Exception to evaluate

        Returns:
            bool: True if error is transient and retry is recommended
        """
        transient_errors = [
            "connection",
            "timeout",
            "temporary",
            "unavailable",
            "deadlock",
        ]
        error_str = str(error).lower()
        return any(term in error_str for term in transient_errors)

    async def schedule_follow_up_message(
        self, patient_id: UUID, follow_up_content: str, context: dict[str, Any]
    ) -> bool:
        """Schedule an AI-generated follow-up message."""
        try:
            # Create follow-up message
            message = Message(
                patient_id=patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=follow_up_content,
                status=MessageStatus.PENDING,
                message_metadata={
                    "flow_context": {
                        "type": "ai_follow_up",
                        "triggered_by": "patient_response",
                        "ai_generated": True,
                        "empathetic_response": True,
                    },
                    "response_context": context,
                    "retry_policy": "urgent"
                    if context.get("requires_attention")
                    else "flow_message",
                },
            )

            # Save message
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)

            # Schedule for immediate delivery (within 5 minutes)
            send_time = datetime.now(timezone.utc) + timedelta(minutes=5)

            scheduled = await self.message_scheduler.schedule_existing_message(
                message_id=message.id,
                send_time=send_time,
                priority="high" if context.get("requires_attention") else "normal",
            )

            if scheduled:
                logger.info(f"Scheduled AI follow-up message for patient {patient_id}")
                return True
            else:
                logger.error(
                    f"Failed to schedule AI follow-up message for patient {patient_id}"
                )
                return False

        except Exception as e:
            logger.error(f"Failed to schedule follow-up message: {e}")
            self.db.rollback()
            return False

    async def _on_flow_message_sent(
        self, message: Message, flow_context: Optional[dict[str, Any]]
    ):
        """
        Callback for when flow message is sent successfully with robust error handling.

        This callback handles post-send operations:
        - Updates flow state with sent message metadata
        - Broadcasts message sent event to subscribers
        - Syncs with platform (non-critical)

        Error handling:
        - Each operation wrapped in separate try/catch
        - Database errors logged but don't fail callback
        - Broadcast/sync failures are non-critical (logged as warnings)

        Args:
            message: Sent message object
            flow_context: Flow metadata (state_id, day, intent, etc.)
        """
        try:
            if flow_context:
                flow_state_id = flow_context.get("flow_state_id")
                if flow_state_id:
                    # Update flow state with sent message info
                    try:
                        flow_state = self.flow_state_repo.get(UUID(flow_state_id))
                        if flow_state:
                            flow_state.state_data = flow_state.state_data or {}
                            flow_state.state_data["last_message_sent"] = {
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "message_id": str(message.id),
                                "day": flow_context.get("current_day"),
                                "intent": flow_context.get("template_intent"),
                            }
                            self.db.commit()
                    except Exception as db_error:
                        logger.error(
                            f"Failed to update flow state in callback: {db_error}"
                        )

                    # Broadcast flow message sent event (non-critical)
                    try:
                        await self.flow_broadcaster.broadcast_flow_message_sent(
                            patient_id=message.patient_id,
                            message=message,
                            flow_day=flow_context.get("current_day", 0),
                            flow_type=flow_context.get("flow_type", "unknown"),
                        )
                    except Exception as broadcast_error:
                        logger.warning(
                            f"Failed to broadcast flow message (non-critical): {broadcast_error}"
                        )

                    # Sync message processing to platform (non-critical)
                    try:
                        await self.platform_sync.sync_patient_record_update(
                            patient_id=message.patient_id,
                            flow_interaction_data={
                                "message_sent": {
                                    "message_id": str(message.id),
                                    "flow_day": flow_context.get("current_day"),
                                    "flow_type": flow_context.get("flow_type"),
                                    "intent": flow_context.get("template_intent"),
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                }
                            },
                        )
                    except Exception as sync_error:
                        logger.warning(
                            f"Failed to sync to platform (non-critical): {sync_error}"
                        )

            logger.info(f"Flow message sent callback executed for message {message.id}")

        except Exception as e:
            logger.error(f"Error in flow message sent callback: {e}", exc_info=True)

    async def _on_flow_message_failed(
        self, message: Message, flow_context: Optional[dict[str, Any]], error: str
    ):
        """
        Callback for when flow message fails to send.

        Updates flow state with failure information for audit trail and debugging.

        Args:
            message: Failed message object
            flow_context: Flow metadata
            error: Error description string
        """
        try:
            if flow_context:
                flow_state_id = flow_context.get("flow_state_id")
                if flow_state_id:
                    # Update flow state with failure info
                    flow_state = self.flow_state_repo.get(UUID(flow_state_id))
                    if flow_state:
                        flow_state.state_data = flow_state.state_data or {}
                        flow_state.state_data["last_message_failed"] = {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "message_id": str(message.id),
                            "error": error,
                            "day": flow_context.get("current_day"),
                        }
                        self.db.commit()

            logger.warning(
                f"Flow message failed callback executed for message {message.id}: {error}"
            )

        except Exception as e:
            logger.error(f"Error in flow message failed callback: {e}")

    async def _on_flow_message_status_updated(
        self,
        message: Message,
        status: MessageStatus,
        flow_state_id: Optional[UUID],
        additional_data: Optional[dict[str, Any]],
    ):
        """Callback for flow message status updates with error resilience."""
        try:
            if flow_state_id:
                # Update flow state (critical operation)
                try:
                    flow_state = self.flow_state_repo.get(flow_state_id)
                    if flow_state:
                        flow_state.state_data = flow_state.state_data or {}
                        flow_state.state_data["message_status_updates"] = (
                            flow_state.state_data.get("message_status_updates", [])
                        )
                        flow_state.state_data["message_status_updates"].append(
                            {
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "message_id": str(message.id),
                                "status": status.value,
                                "additional_data": additional_data,
                            }
                        )

                        # Keep only last 10 status updates
                        flow_state.state_data["message_status_updates"] = (
                            flow_state.state_data["message_status_updates"][-10:]
                        )

                        self.db.commit()
                except Exception as db_error:
                    logger.error(f"Failed to update flow state status: {db_error}")
                    self.db.rollback()

                # Broadcast message status update (non-critical)
                try:
                    await self.flow_broadcaster.broadcast_patient_interaction(
                        patient_id=message.patient_id,
                        message=message,
                        interaction_type=f"message_status_{status.value.lower()}",
                    )
                except Exception as broadcast_error:
                    logger.debug(
                        f"Failed to broadcast status update (non-critical): {broadcast_error}"
                    )

            logger.debug(f"Flow message status updated: {message.id} -> {status.value}")

        except Exception as e:
            logger.error(
                f"Error in flow message status update callback: {e}", exc_info=True
            )
