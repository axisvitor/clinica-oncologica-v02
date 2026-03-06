import logging
from inspect import isawaitable
from typing import Any, Callable, Optional
from uuid import UUID

from sqlalchemy import select

from app.exceptions import (
    FlowOperationError,
    FlowStateConflictError,
    FlowStateNotFoundError,
)
from app.models.flow import FlowKind, FlowTemplateVersion, PatientFlowState
from app.schemas.flow import FlowAdvancementResponse
from app.services.flow.flags import is_awaiting_response as _is_awaiting_response
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)

FLOW_ADVANCE_BLOCKED_MESSAGE = "Cannot advance flow while awaiting patient response"
FLOW_ADVANCE_BLOCKED_CODE = "flow_advance_blocked_awaiting_response"
FLOW_ADVANCE_BLOCKED_REASON = "awaiting_response"


async def advance_day_atomic(
    *,
    db: Any,
    flow_state: PatientFlowState,
    patient_id: Optional[UUID],
    day_number: int,
    flow_kind: str,
    message_index: int,
    sent_count: Optional[int] = None,
    mark_last_message_sent: Optional[Callable[[dict[str, Any]], None]] = None,
) -> dict[str, Any]:
    """Persist day-complete state with optimistic locking and verification markers."""
    step_data = dict(flow_state.step_data or {})
    step_data["day_complete"] = True
    step_data["awaiting_response"] = False
    step_data["current_day_message_index"] = message_index
    if sent_count is not None:
        step_data["messages_sent"] = sent_count
    if callable(mark_last_message_sent):
        mark_last_message_sent(step_data)
    step_data.pop("pending_response_context", None)
    step_data["day_advance_verified"] = False
    step_data.pop("day_advance_verified_at", None)

    expected_version = getattr(flow_state, "version", 0)
    version_result = db.execute(
        select(PatientFlowState.version).filter(PatientFlowState.id == flow_state.id)
    )
    if isawaitable(version_result):
        version_result = await version_result
    current_version = version_result.scalar_one_or_none()
    if current_version is None:
        raise FlowStateNotFoundError(f"Flow state {flow_state.id} not found")
    if isinstance(current_version, bool) or not isinstance(current_version, int):
        current_version = expected_version
    if current_version != expected_version:
        raise FlowStateConflictError(
            "Concurrent flow update detected during day completion",
            details={
                "patient_id": str(patient_id) if patient_id else None,
                "flow_kind": flow_kind,
                "day_number": day_number,
                "expected_version": expected_version,
                "actual_version": current_version,
            },
        )

    flow_state.step_data = step_data
    flow_state.last_interaction_at = now_sao_paulo()
    flow_state.version = expected_version + 1

    try:
        commit_result = db.commit()
        if isawaitable(commit_result):
            await commit_result
        step_data["day_advance_verified"] = True
        step_data["day_advance_verified_at"] = now_sao_paulo().isoformat()
        flow_state.step_data = step_data
        flow_state.last_interaction_at = now_sao_paulo()
        flow_state.version = expected_version + 2
        commit_result = db.commit()
        if isawaitable(commit_result):
            await commit_result
    except Exception as exc:
        flow_state.step_data = step_data
        logger.error(
            "Day advancement commit failed - flow may be in inconsistent state",
            extra={
                "patient_id": str(patient_id) if patient_id else None,
                "day_number": day_number,
                "flow_kind": flow_kind,
                "error": str(exc),
            },
        )
        raise

    return step_data


class FlowManagementAdvancementMixin:
    async def advance_patient_flow(
        self, patient_id: UUID, force_day: Optional[int] = None
    ) -> FlowAdvancementResponse:
        """
        Advance patient flow to next step or specific day.

        Args:
            patient_id: The patient's UUID
            force_day: Optional specific day to advance to

        Returns:
            FlowAdvancementResponse with advancement result

        Raises:
            FlowStateNotFoundError: If no active flow exists
            FlowOperationError: If advancement fails
        """
        try:
            flow_state = self.flow_repo.get_active_flow(patient_id)
            if not flow_state:
                raise FlowStateNotFoundError(
                    f"No active flow found for patient {patient_id}"
                )

            if flow_state.status == "paused":
                raise FlowStateConflictError("Cannot advance a paused flow")

            if _is_awaiting_response(flow_state.step_data):
                raise FlowStateConflictError(
                    FLOW_ADVANCE_BLOCKED_MESSAGE,
                    details={
                        "patient_id": str(patient_id),
                        "blocked": True,
                        "block_reason": FLOW_ADVANCE_BLOCKED_REASON,
                        "current_step": flow_state.current_step,
                    },
                    code=FLOW_ADVANCE_BLOCKED_CODE,
                )

            template_version = (
                self.flow_repo.db.query(FlowTemplateVersion)
                .filter(FlowTemplateVersion.id == flow_state.flow_template_version_id)
                .first()
            )
            total_steps = self._get_total_steps(template_version)
            next_step = force_day if force_day is not None else flow_state.current_step + 1

            if next_step <= flow_state.current_step:
                raise FlowStateConflictError("Cannot move to a previous or current step")
            if next_step > flow_state.current_step + 1:
                raise FlowStateConflictError("Step progression must be sequential")

            previous_step = flow_state.current_step
            expected_version = flow_state.version

            flow_state.current_step = next_step
            flow_state.last_interaction_at = now_sao_paulo()
            flow_state.step_data = flow_state.step_data or {}
            flow_state.step_data.setdefault("step_timestamps", {})
            flow_state.step_data["step_timestamps"][
                f"step_{next_step}"
            ] = now_sao_paulo().isoformat()

            if total_steps and next_step >= total_steps:
                flow_state.status = "completed"
                flow_state.completed_at = now_sao_paulo()

            flow_state.version = expected_version + 1
            self.db.commit()

            advancement_result = {
                "previous_step": previous_step,
                "current_step": flow_state.current_step,
                "next_actions": [],
                "message": "Flow advanced successfully",
                "completed": flow_state.completed_at is not None,
            }

            logger.info(
                "Flow advanced",
                extra={
                    "patient_id": str(patient_id),
                    "previous_step": advancement_result["previous_step"],
                    "current_step": advancement_result["current_step"],
                    "completed": advancement_result["completed"],
                },
            )

            return FlowAdvancementResponse(
                success=True,
                patient_id=patient_id,
                advancement_result=advancement_result,
                message="Patient flow advanced successfully",
            )

        except (FlowStateNotFoundError, FlowStateConflictError):
            raise
        except Exception as e:
            logger.error(f"Failed to advance flow for patient {patient_id}: {e}")
            raise FlowOperationError(f"Failed to advance flow: {str(e)}")

    def _get_total_steps(self, template_version: Optional[FlowTemplateVersion]) -> int:
        if not template_version or template_version.steps is None:
            return 0
        steps = template_version.steps
        if isinstance(steps, list):
            return len(steps)
        if isinstance(steps, dict):
            return len(steps.keys())
        return 0

    async def migrate_patient_flow_version(
        self,
        patient_id: UUID,
        target_version_id: Optional[UUID] = None,
        target_kind_key: Optional[str] = None,
    ) -> PatientFlowState:
        """Optionally migrate a patient to a new template version."""
        flow_state = self.flow_repo.get_active_flow(patient_id)
        if not flow_state:
            raise FlowStateNotFoundError(f"No active flow found for patient {patient_id}")

        target_version = None
        if target_version_id:
            target_version = (
                self.db.query(FlowTemplateVersion)
                .filter(FlowTemplateVersion.id == target_version_id)
                .first()
            )
        elif target_kind_key:
            flow_kind = (
                self.db.query(FlowKind).filter(FlowKind.kind_key == target_kind_key).first()
            )
            if flow_kind:
                target_version = (
                    self.db.query(FlowTemplateVersion)
                    .filter(
                        FlowTemplateVersion.flow_kind_id == flow_kind.id,
                        FlowTemplateVersion.is_active.is_(True),
                    )
                    .order_by(FlowTemplateVersion.version_number.desc())
                    .first()
                )

        if not target_version:
            raise FlowOperationError("Target template version not found")

        if flow_state.flow_template_version_id == target_version.id:
            return flow_state

        expected_version = flow_state.version
        previous_version_id = flow_state.flow_template_version_id
        flow_state.flow_template_version_id = target_version.id
        flow_state.flow_metadata = flow_state.flow_metadata or {}
        flow_state.flow_metadata.update(
            {
                "migrated_from": str(previous_version_id),
                "migrated_to": str(target_version.id),
                "migrated_at": now_sao_paulo().isoformat(),
            }
        )

        self.enhanced_flow_engine._commit_flow_state_with_lock(flow_state, expected_version)

        logger.info(
            "Flow template version migrated",
            extra={
                "patient_id": str(patient_id),
                "from_version": str(previous_version_id),
                "to_version": str(target_version.id),
            },
        )

        return flow_state
