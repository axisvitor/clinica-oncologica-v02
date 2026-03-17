import logging
from datetime import timedelta
from typing import Optional
from uuid import UUID

from app.exceptions import (
    FlowOperationError,
    FlowStateConflictError,
    FlowStateNotFoundError,
)
from app.models.message import Message, MessageDirection, MessageStatus
from app.schemas.flow import FlowPauseResponse, FlowResumeResponse
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


def _compat_now_sao_paulo():
    try:
        from app.services import flow_management as legacy_flow_management

        return legacy_flow_management.now_sao_paulo()
    except Exception:
        return now_sao_paulo()


class FlowManagementPauseResumeMixin:
    async def pause_patient_flow(
        self,
        patient_id: UUID,
        reason: Optional[str] = None,
        duration_hours: Optional[int] = None,
        user_id: UUID = None,
    ) -> FlowPauseResponse:
        """
        Pause a patient's flow with proper state management.

        Args:
            patient_id: The patient's UUID
            reason: Optional reason for pausing
            duration_hours: Optional auto-resume duration
            user_id: ID of user performing the action

        Returns:
            FlowPauseResponse with pause result

        Raises:
            FlowStateNotFoundError: If no active flow exists
            FlowStateConflictError: If flow is already paused
        """
        try:
            flow_state = self.flow_repo.get_active_flow(patient_id)
            if not flow_state:
                raise FlowStateNotFoundError(
                    f"No active flow found for patient {patient_id}"
                )

            if flow_state.state_data and flow_state.state_data.get("paused"):
                flow_state.state_data = flow_state.state_data or {}
                flow_state.state_data["pause_reason"] = (
                    reason
                    or flow_state.state_data.get("pause_reason")
                    or "Manual pause by healthcare provider"
                )
                flow_state.state_data["paused_at"] = _compat_now_sao_paulo().isoformat()

                auto_resume_at = flow_state.state_data.get("auto_resume_at")
                if duration_hours:
                    resume_at = _compat_now_sao_paulo() + timedelta(hours=duration_hours)
                    flow_state.state_data["auto_resume_at"] = resume_at.isoformat()
                    auto_resume_at = resume_at.isoformat()

                flow_state.status = "paused"
                flow_state.last_interaction_at = _compat_now_sao_paulo()
                expected_version = flow_state.version
                flow_state.version = expected_version + 1
                self.db.commit()

                logger.info(
                    "Flow re-paused (idempotent)",
                    extra={"patient_id": str(patient_id), "flow_id": str(flow_state.id)},
                )

                return FlowPauseResponse(
                    success=True,
                    patient_id=patient_id,
                    flow_state_id=flow_state.id,
                    status="paused",
                    reason=reason,
                    paused_at=flow_state.state_data["paused_at"],
                    auto_resume_at=auto_resume_at,
                    message="Patient flow already paused; pause refreshed successfully",
                )

            flow_state.state_data = flow_state.state_data or {}
            flow_state.state_data["paused"] = True
            flow_state.state_data["pause_reason"] = (
                reason or "Manual pause by healthcare provider"
            )
            flow_state.state_data["paused_at"] = _compat_now_sao_paulo().isoformat()

            if user_id:
                flow_state.state_data["paused_by"] = str(user_id)

            auto_resume_at = None
            if duration_hours:
                resume_at = _compat_now_sao_paulo() + timedelta(hours=duration_hours)
                flow_state.state_data["auto_resume_at"] = resume_at.isoformat()
                auto_resume_at = resume_at.isoformat()

            flow_state.status = "paused"
            flow_state.last_interaction_at = _compat_now_sao_paulo()
            expected_version = flow_state.version
            flow_state.version = expected_version + 1
            self.db.commit()

            logger.info(
                "Flow paused",
                extra={"patient_id": str(patient_id), "flow_id": str(flow_state.id)},
            )

            return FlowPauseResponse(
                success=True,
                patient_id=patient_id,
                flow_state_id=flow_state.id,
                status="paused",
                reason=reason,
                paused_at=flow_state.state_data["paused_at"],
                auto_resume_at=auto_resume_at,
                message="Patient flow paused successfully",
            )

        except (FlowStateNotFoundError, FlowStateConflictError):
            raise
        except Exception as e:
            logger.error(f"Failed to pause flow for patient {patient_id}: {e}")
            raise FlowOperationError(f"Failed to pause flow: {str(e)}")

    async def resume_patient_flow(
        self, patient_id: UUID, user_id: UUID = None
    ) -> FlowResumeResponse:
        """
        Resume a previously paused flow.

        Args:
            patient_id: The patient's UUID
            user_id: ID of user performing the action

        Returns:
            FlowResumeResponse with resume result

        Raises:
            FlowStateNotFoundError: If no active flow exists
            FlowStateConflictError: If flow is not paused
        """
        try:
            flow_state = self.flow_repo.get_active_flow(patient_id)
            if not flow_state:
                raise FlowStateNotFoundError(
                    f"No active flow found for patient {patient_id}"
                )

            if not flow_state.state_data or not flow_state.state_data.get("paused"):
                raise FlowStateConflictError("Flow is not currently paused")

            flow_state.state_data["paused"] = False
            flow_state.state_data["resumed_at"] = _compat_now_sao_paulo().isoformat()

            if user_id:
                flow_state.state_data["resumed_by"] = str(user_id)

            flow_state.state_data.pop("auto_resume_at", None)

            flow_state.status = "active"
            flow_state.last_interaction_at = _compat_now_sao_paulo()
            expected_version = flow_state.version
            flow_state.version = expected_version + 1
            self.db.commit()

            logger.info(
                "Flow resumed",
                extra={"patient_id": str(patient_id), "flow_id": str(flow_state.id)},
            )

            return FlowResumeResponse(
                success=True,
                patient_id=patient_id,
                flow_state_id=flow_state.id,
                status="active",
                resumed_at=flow_state.state_data["resumed_at"],
                message="Patient flow resumed successfully",
            )

        except (FlowStateNotFoundError, FlowStateConflictError):
            raise
        except Exception as e:
            logger.error(f"Failed to resume flow for patient {patient_id}: {e}")
            raise FlowOperationError(f"Failed to resume flow: {str(e)}")

    async def cancel_patient_flow(
        self,
        patient_id: UUID,
        user_id: UUID = None,
    ) -> dict:
        """Cancel a patient's flow, cleaning up all pending messages and state."""
        try:
            flow_state = self.flow_repo.get_active_flow(patient_id)
            if not flow_state:
                raise FlowStateNotFoundError(
                    f"No active flow found for patient {patient_id}"
                )

            cancellable_statuses = [MessageStatus.PENDING, MessageStatus.SCHEDULED]
            if hasattr(MessageStatus, "QUEUED"):
                cancellable_statuses.append(MessageStatus.QUEUED)

            pending_messages = (
                self.db.query(Message)
                .filter(
                    Message.patient_id == patient_id,
                    Message.status.in_(cancellable_statuses),
                    Message.direction == MessageDirection.OUTBOUND,
                )
                .all()
            )

            revoked_count = 0
            for message in pending_messages:
                message.status = MessageStatus.CANCELLED

                task_id = None
                if message.message_metadata:
                    task_id = message.message_metadata.get("celery_task_id")
                if task_id:
                    # Pending message cancellation — Taskiq doesn't support task revocation
                    # The message will be sent but the flow is cancelled, so it will be ignored
                    logger.info(
                        "Skipping pending message cancel (no revocation in Taskiq)",
                        extra={"task_id": task_id, "message_id": str(message.id)},
                    )
                    revoked_count += 1

            now = _compat_now_sao_paulo()
            flow_state.status = "cancelled"
            flow_state.completed_at = now
            flow_state.last_interaction_at = now
            flow_state.state_data = flow_state.state_data or {}
            flow_state.state_data["paused"] = False
            flow_state.state_data["cancelled"] = True
            flow_state.state_data["cancelled_at"] = now.isoformat()
            flow_state.state_data["cancelled_by"] = str(user_id) if user_id else None
            flow_state.state_data["messages_cancelled"] = len(pending_messages)
            flow_state.state_data["tasks_revoked"] = revoked_count
            flow_state.state_data.pop("auto_resume_at", None)

            expected_version = flow_state.version
            flow_state.version = expected_version + 1
            self.db.commit()

            logger.info(
                "Flow cancelled",
                extra={
                    "patient_id": str(patient_id),
                    "flow_id": str(flow_state.id),
                    "cancelled_by": str(user_id) if user_id else "system",
                    "messages_cancelled": len(pending_messages),
                    "tasks_revoked": revoked_count,
                    "action": "cancel_flow",
                },
            )

            return {
                "flow_id": flow_state.id,
                "patient_id": patient_id,
                "status": "cancelled",
                "cancelled_at": now,
                "messages_cancelled": len(pending_messages),
                "tasks_revoked": revoked_count,
            }

        except (FlowStateNotFoundError, FlowStateConflictError):
            raise
        except Exception as e:
            logger.error(f"Failed to cancel flow for patient {patient_id}: {e}")
            raise FlowOperationError(f"Failed to cancel flow: {str(e)}")
