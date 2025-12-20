"""
Recovery action implementations for different error recovery strategies.
Each strategy handles a specific type of error recovery approach.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING


from app.models.message import Message, MessageType, MessageDirection, MessageStatus
from app.models.patient import Patient
from app.services.websocket_events import websocket_events
from app.schemas.websocket import WebSocketEventType

from .classifier import (
    ErrorCategory,
    ErrorSeverity,
    RecoveryStrategy,
    ErrorHandlerConstants,
)
from .retry_manager import ErrorRecord, RecoveryResult

if TYPE_CHECKING:
    from .error_handler import FlowErrorHandler

logger = logging.getLogger(__name__)


class RecoveryAction(ABC):
    """Abstract base class for recovery actions."""

    @abstractmethod
    async def execute(
        self, error_record: ErrorRecord, context: "FlowErrorHandler"
    ) -> RecoveryResult:
        """Execute the recovery action."""
        pass


class ExponentialBackoffRetry(RecoveryAction):
    """Retry with exponential backoff."""

    async def execute(
        self, error_record: ErrorRecord, context: "FlowErrorHandler"
    ) -> RecoveryResult:
        if error_record.recovery_attempts >= error_record.max_recovery_attempts:
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.RETRY_EXPONENTIAL,
                attempts_made=error_record.recovery_attempts,
                error_resolved=False,
                message="Max retry attempts exceeded",
            )

        # Calculate next retry delay
        delays = context.config.retry_delays[RecoveryStrategy.RETRY_EXPONENTIAL]
        delay_index = min(error_record.recovery_attempts, len(delays) - 1)
        delay_seconds = delays[delay_index]

        next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)

        # Schedule retry
        await context.retry_manager.schedule_retry(error_record, next_retry_at)

        error_record.recovery_attempts += 1

        return RecoveryResult(
            success=True,
            strategy_used=RecoveryStrategy.RETRY_EXPONENTIAL,
            attempts_made=error_record.recovery_attempts,
            error_resolved=False,
            next_retry_at=next_retry_at,
            message=f"Scheduled retry #{error_record.recovery_attempts} in {delay_seconds} seconds",
        )


class LinearBackoffRetry(RecoveryAction):
    """Retry with linear backoff."""

    async def execute(
        self, error_record: ErrorRecord, context: "FlowErrorHandler"
    ) -> RecoveryResult:
        if error_record.recovery_attempts >= error_record.max_recovery_attempts:
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.RETRY_LINEAR,
                attempts_made=error_record.recovery_attempts,
                error_resolved=False,
                message="Max retry attempts exceeded",
            )

        # Fixed delay for linear backoff
        delay_seconds = ErrorHandlerConstants.DEFAULT_LINEAR_DELAY
        next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)

        # Schedule retry
        await context.retry_manager.schedule_retry(error_record, next_retry_at)

        error_record.recovery_attempts += 1

        return RecoveryResult(
            success=True,
            strategy_used=RecoveryStrategy.RETRY_LINEAR,
            attempts_made=error_record.recovery_attempts,
            error_resolved=False,
            next_retry_at=next_retry_at,
            message=f"Scheduled linear retry #{error_record.recovery_attempts} in {delay_seconds} seconds",
        )


class FallbackMessageAction(RecoveryAction):
    """Send fallback message when primary message fails."""

    async def execute(
        self, error_record: ErrorRecord, context: "FlowErrorHandler"
    ) -> RecoveryResult:
        try:
            error_context = error_record.context

            # Get patient information
            patient = context.patient_repo.get(error_context.patient_id)
            if not patient:
                return RecoveryResult(
                    success=False,
                    strategy_used=RecoveryStrategy.FALLBACK_MESSAGE,
                    attempts_made=1,
                    error_resolved=False,
                    message="Patient not found for fallback message",
                )

            # Create fallback message
            fallback_content = self._generate_fallback_content(error_record, patient)

            # Create and send fallback message
            fallback_message = Message(
                patient_id=error_context.patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=fallback_content,
                message_metadata={
                    "fallback_message": True,
                    "original_error": error_record.error_type,
                    "error_id": error_record.id,
                },
                status=MessageStatus.PENDING,
                scheduled_for=datetime.now(timezone.utc),
            )

            context.db.add(fallback_message)
            context.db.commit()

            # Send via message sender
            from app.domain.messaging.delivery import MessageSender

            message_sender = MessageSender(context.db)
            success = await message_sender.send_message(fallback_message)

            if success:
                error_record.resolved = True
                error_record.resolved_at = datetime.now(timezone.utc)

                return RecoveryResult(
                    success=True,
                    strategy_used=RecoveryStrategy.FALLBACK_MESSAGE,
                    attempts_made=1,
                    error_resolved=True,
                    fallback_applied=True,
                    message="Fallback message sent successfully",
                )
            else:
                return RecoveryResult(
                    success=False,
                    strategy_used=RecoveryStrategy.FALLBACK_MESSAGE,
                    attempts_made=1,
                    error_resolved=False,
                    message="Fallback message failed to send",
                )

        except Exception as e:
            logger.error(f"Fallback message failed: {e}")
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.FALLBACK_MESSAGE,
                attempts_made=1,
                error_resolved=False,
                message=f"Fallback message error: {str(e)}",
            )

    def _generate_fallback_content(
        self, error_record: ErrorRecord, patient: Patient
    ) -> str:
        """Generate appropriate fallback message content."""
        patient_name = patient.name or "paciente"

        template_key = {
            ErrorCategory.MESSAGE_DELIVERY: "message_delivery",
            ErrorCategory.EXTERNAL_SERVICE: "external_service",
            ErrorCategory.FLOW_PROCESSING: "flow_processing",
        }.get(error_record.category, "default")

        template = ErrorHandlerConstants.FALLBACK_MESSAGE_TEMPLATES[template_key]
        return template.format(name=patient_name)


class SkipAndContinueAction(RecoveryAction):
    """Skip current operation and continue with flow."""

    async def execute(
        self, error_record: ErrorRecord, context: "FlowErrorHandler"
    ) -> RecoveryResult:
        try:
            error_context = error_record.context

            # Get flow state
            if error_context.flow_state_id:
                flow_state = context.flow_repo.get(error_context.flow_state_id)
                if flow_state:
                    # Mark error as resolved and continue
                    flow_state.state_data = flow_state.state_data or {}
                    flow_state.state_data["skipped_operations"] = (
                        flow_state.state_data.get("skipped_operations", [])
                    )
                    flow_state.state_data["skipped_operations"].append(
                        {
                            "operation": error_context.operation,
                            "error_id": error_record.id,
                            "skipped_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )

                    context.db.commit()

            error_record.resolved = True
            error_record.resolved_at = datetime.now(timezone.utc)

            return RecoveryResult(
                success=True,
                strategy_used=RecoveryStrategy.SKIP_AND_CONTINUE,
                attempts_made=1,
                error_resolved=True,
                message="Operation skipped, flow continues",
            )

        except Exception as e:
            logger.error(f"Skip and continue failed: {e}")
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.SKIP_AND_CONTINUE,
                attempts_made=1,
                error_resolved=False,
                message=f"Skip operation failed: {str(e)}",
            )


class PauseFlowAction(RecoveryAction):
    """Pause flow temporarily for recovery."""

    async def execute(
        self, error_record: ErrorRecord, context: "FlowErrorHandler"
    ) -> RecoveryResult:
        try:
            error_context = error_record.context

            # Get flow state
            if error_context.flow_state_id:
                flow_state = context.flow_repo.get(error_context.flow_state_id)
                if flow_state:
                    # Pause flow
                    flow_state.state_data = flow_state.state_data or {}
                    flow_state.state_data["paused"] = True
                    flow_state.state_data["pause_reason"] = (
                        f"Error recovery: {error_record.error_type}"
                    )
                    flow_state.state_data["paused_at"] = datetime.now(timezone.utc).isoformat()
                    flow_state.state_data["error_id"] = error_record.id

                    context.db.commit()

                    # Schedule resume
                    resume_at = datetime.now(timezone.utc) + timedelta(
                        hours=ErrorHandlerConstants.FLOW_RESUME_DELAY_HOURS
                    )
                    await context.retry_manager.schedule_flow_resume(
                        error_context.patient_id, resume_at
                    )

            return RecoveryResult(
                success=True,
                strategy_used=RecoveryStrategy.PAUSE_FLOW,
                attempts_made=1,
                error_resolved=False,
                message=f"Flow paused for recovery, will resume in {ErrorHandlerConstants.FLOW_RESUME_DELAY_HOURS} hour(s)",
            )

        except Exception as e:
            logger.error(f"Pause flow failed: {e}")
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.PAUSE_FLOW,
                attempts_made=1,
                error_resolved=False,
                message=f"Flow pause failed: {str(e)}",
            )


class ResetFlowAction(RecoveryAction):
    """Reset flow state to recover from corruption."""

    async def execute(
        self, error_record: ErrorRecord, context: "FlowErrorHandler"
    ) -> RecoveryResult:
        try:
            error_context = error_record.context

            # Get flow state
            if error_context.flow_state_id:
                flow_state = context.flow_repo.get(error_context.flow_state_id)
                if flow_state:
                    # Backup current state
                    backup_data = {
                        "original_state": flow_state.state_data,
                        "reset_reason": error_record.error_type,
                        "reset_at": datetime.now(timezone.utc).isoformat(),
                        "error_id": error_record.id,
                    }

                    # Reset to safe state
                    flow_state.state_data = {
                        "reset": True,
                        "backup": backup_data,
                        "current_step": max(
                            1, flow_state.current_step - 1
                        ),  # Go back one step
                        "reset_recovery": True,
                    }

                    context.db.commit()

                    error_record.resolved = True
                    error_record.resolved_at = datetime.now(timezone.utc)

            return RecoveryResult(
                success=True,
                strategy_used=RecoveryStrategy.RESET_FLOW,
                attempts_made=1,
                error_resolved=True,
                message="Flow state reset to safe state",
            )

        except Exception as e:
            logger.error(f"Flow reset failed: {e}")
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.RESET_FLOW,
                attempts_made=1,
                error_resolved=False,
                message=f"Flow reset failed: {str(e)}",
            )


class EscalateManualAction(RecoveryAction):
    """Escalate error for manual intervention."""

    async def execute(
        self, error_record: ErrorRecord, context: "FlowErrorHandler"
    ) -> RecoveryResult:
        try:
            # Create escalation notification
            escalation_data = {
                "error_id": error_record.id,
                "patient_id": str(error_record.context.patient_id),
                "error_type": error_record.error_type,
                "category": error_record.category.value,
                "severity": error_record.severity.value,
                "message": error_record.message,
                "context": {
                    "operation": error_record.context.operation,
                    "timestamp": error_record.created_at.isoformat(),
                },
                "requires_manual_intervention": True,
            }

            # Publish escalation event
            await websocket_events.publish_alert_event(
                event_type=WebSocketEventType.ALERT_CREATED,
                patient_id=error_record.context.patient_id,
                alert_type="flow_error_escalation",
                priority="high"
                if error_record.severity == ErrorSeverity.CRITICAL
                else "medium",
                message=f"Flow error requires manual intervention: {error_record.error_type}",
                metadata=escalation_data,
            )

            return RecoveryResult(
                success=True,
                strategy_used=RecoveryStrategy.ESCALATE_MANUAL,
                attempts_made=1,
                error_resolved=False,
                message="Error escalated for manual intervention",
            )

        except Exception as e:
            logger.error(f"Escalation failed: {e}")
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.ESCALATE_MANUAL,
                attempts_made=1,
                error_resolved=False,
                message=f"Escalation failed: {str(e)}",
            )


class RecoveryActionFactory:
    """Factory for creating recovery actions."""

    _actions = {
        RecoveryStrategy.RETRY_EXPONENTIAL: ExponentialBackoffRetry,
        RecoveryStrategy.RETRY_LINEAR: LinearBackoffRetry,
        RecoveryStrategy.FALLBACK_MESSAGE: FallbackMessageAction,
        RecoveryStrategy.SKIP_AND_CONTINUE: SkipAndContinueAction,
        RecoveryStrategy.PAUSE_FLOW: PauseFlowAction,
        RecoveryStrategy.RESET_FLOW: ResetFlowAction,
        RecoveryStrategy.ESCALATE_MANUAL: EscalateManualAction,
    }

    @classmethod
    def create_action(cls, strategy: RecoveryStrategy) -> RecoveryAction:
        """Create recovery action for given strategy."""
        action_class = cls._actions.get(strategy)
        if not action_class:
            raise ValueError(f"Unknown recovery strategy: {strategy}")
        return action_class()
