import logging
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select

from app.exceptions import FlowStateConflictError
from app.models.flow import PatientFlowState
from app.services.flow.types import FlowType, normalize_flow_type
from app.utils.timezone import now_sao_paulo

from .operations import (
    FLOW_ADVANCE_BLOCKED_CODE,
    FLOW_ADVANCE_BLOCKED_MESSAGE,
    FLOW_ADVANCE_BLOCKED_REASON,
    NotFoundError,
)

logger = logging.getLogger(__name__)


class FlowCoreTransitionsMixin:
    async def determine_flow_type(self, patient_id: UUID, current_day: int) -> FlowType:
        if current_day <= 15:
            return FlowType.ONBOARDING
        if current_day <= 45:
            return FlowType.DAILY_FOLLOW_UP
        return FlowType.QUIZ_MENSAL

    async def advance_patient_flow(
        self, patient_id: UUID, force_day: Optional[int] = None
    ) -> dict[str, Any]:
        try:
            result = await self.db.execute(
                select(PatientFlowState).filter(
                    PatientFlowState.patient_id == patient_id,
                    PatientFlowState.status == "active",
                )
            )
            flow_state = result.scalar_one_or_none()
            if not flow_state:
                raise NotFoundError(f"No active flow for patient {patient_id}")

            if self._is_awaiting_response(flow_state.step_data):
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

            current_day = force_day or await self.calculate_patient_day(patient_id)

            current_flow_type = normalize_flow_type(flow_state.flow_type)
            required_flow_type = await self.determine_flow_type(patient_id, current_day)

            expected_version = flow_state.version

            previous_state = {
                "flow_type": current_flow_type.value,
                "current_day": flow_state.current_step,
                "is_paused": flow_state.state_data.get("paused", False)
                if flow_state.state_data
                else False,
            }

            if current_flow_type != required_flow_type:
                await self._transition_flow_type(flow_state, required_flow_type, current_day)
                logger.info(
                    f"Patient {patient_id} transitioned from {current_flow_type.value} to {required_flow_type.value}"
                )

            previous_day = flow_state.current_step
            flow_state.current_step = current_day
            step_data = dict(flow_state.step_data or {})
            step_data["last_advancement"] = now_sao_paulo().isoformat()
            step_data["current_flow_day"] = current_day
            step_data["flow_kind"] = required_flow_type.value
            flow_state.step_data = step_data

            await self._commit_flow_state_with_lock(flow_state, expected_version)

            await self.flow_broadcaster.broadcast_flow_state_change(
                patient_id=patient_id,
                flow_state=flow_state,
                previous_state=previous_state,
            )

            if previous_day != current_day:
                milestone = (
                    "flow_transition"
                    if current_flow_type != required_flow_type
                    else None
                )
                await self.flow_broadcaster.broadcast_flow_progression(
                    patient_id=patient_id,
                    from_day=previous_day,
                    to_day=current_day,
                    flow_type=required_flow_type.value,
                    milestone_reached=milestone,
                )

            await self.platform_sync.sync_patient_record_update(
                patient_id=patient_id,
                flow_interaction_data={
                    "flow_advancement": {
                        "previous_day": previous_day,
                        "current_day": current_day,
                        "flow_type": required_flow_type.value,
                        "transitioned": current_flow_type != required_flow_type,
                        "timestamp": now_sao_paulo().isoformat(),
                    }
                },
            )

            return {
                "status": "success",
                "patient_id": str(patient_id),
                "current_day": current_day,
                "flow_type": required_flow_type.value,
                "previous_flow_type": current_flow_type.value,
                "transitioned": current_flow_type != required_flow_type,
            }

        except Exception as exc:
            logger.error(f"Failed to advance patient flow: {exc}")
            self.db.rollback()
            raise

    async def pause_patient_flow(
        self, patient_id: UUID, reason: str = None
    ) -> dict[str, Any]:
        try:
            result = await self.db.execute(
                select(PatientFlowState).filter(
                    PatientFlowState.patient_id == patient_id,
                    PatientFlowState.status == "active",
                )
            )
            flow_state = result.scalar_one_or_none()
            if not flow_state:
                raise NotFoundError(f"No active flow for patient {patient_id}")

            expected_version = flow_state.version

            previous_state = {
                "flow_type": flow_state.flow_type,
                "current_day": flow_state.current_step,
                "is_paused": False,
            }

            state_data = dict(flow_state.state_data or {})
            state_data["paused"] = True
            state_data["pause_reason"] = reason or "Manual pause"
            state_data["paused_at"] = now_sao_paulo().isoformat()
            state_data["paused_by_step"] = flow_state.current_step
            flow_state.state_data = state_data
            flow_state.status = "paused"

            await self._commit_flow_state_with_lock(flow_state, expected_version)

            await self.flow_broadcaster.broadcast_flow_state_change(
                patient_id=patient_id,
                flow_state=flow_state,
                previous_state=previous_state,
            )

            logger.info(f"Paused flow for patient {patient_id}")
            return {
                "status": "paused",
                "patient_id": str(patient_id),
                "reason": reason,
                "paused_at": now_sao_paulo().isoformat(),
            }

        except Exception as exc:
            logger.error(f"Failed to pause patient flow: {exc}")
            self.db.rollback()
            raise

    async def resume_patient_flow(self, patient_id: UUID) -> dict[str, Any]:
        try:
            result = await self.db.execute(
                select(PatientFlowState).filter(
                    PatientFlowState.patient_id == patient_id,
                    PatientFlowState.status == "paused",
                )
            )
            flow_state = result.scalar_one_or_none()
            if not flow_state:
                raise NotFoundError(f"No active flow for patient {patient_id}")

            expected_version = flow_state.version

            previous_state = {
                "flow_type": flow_state.flow_type,
                "current_day": flow_state.current_step,
                "is_paused": True,
            }

            state_data = dict(flow_state.state_data or {})
            paused_at = state_data.get("paused_at")
            pause_reason = state_data.get("pause_reason")
            state_data["paused"] = False
            state_data["resumed_at"] = now_sao_paulo().isoformat()
            state_data.pop("auto_resume_at", None)
            state_data["resumed"] = {
                "timestamp": state_data["resumed_at"],
                "was_paused_at": paused_at,
                "pause_reason": pause_reason,
            }
            flow_state.state_data = state_data
            flow_state.status = "active"

            await self._commit_flow_state_with_lock(flow_state, expected_version)

            await self.flow_broadcaster.broadcast_flow_state_change(
                patient_id=patient_id,
                flow_state=flow_state,
                previous_state=previous_state,
            )

            logger.info(f"Resumed flow for patient {patient_id}")
            return {
                "status": "resumed",
                "patient_id": str(patient_id),
                "resumed_at": now_sao_paulo().isoformat(),
            }

        except Exception as exc:
            logger.error(f"Failed to resume patient flow: {exc}")
            self.db.rollback()
            raise

    async def _transition_flow_type(
        self, flow_state: PatientFlowState, new_flow_type: FlowType, current_day: int
    ) -> None:
        old_flow_type = flow_state.flow_type

        flow_state.flow_type = new_flow_type.value
        flow_state.step_data = flow_state.step_data or {}
        flow_state.step_data["transitions"] = flow_state.step_data.get("transitions", [])
        flow_state.step_data["transitions"].append(
            {
                "timestamp": now_sao_paulo().isoformat(),
                "from_flow": old_flow_type,
                "to_flow": new_flow_type.value,
                "at_day": current_day,
            }
        )
