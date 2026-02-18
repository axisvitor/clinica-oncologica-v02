"""
Flow Management Service for handling flow operations.

Provides flow state management, advancement with optimistic locking,
pause/resume, history, template version migration, and response processing.
Delegates AI work to EnhancedFlowEngine.

Architecture note (QW-021 consolidation):
    This service provides production flow management with FlowStateRepository,
    optimistic locking, and schema-based responses (FlowStateResponse, etc.).
    NOT a duplicate of ``app.services.flow.core.manager.FlowManager`` which is
    the QW-021 step-execution orchestrator with Pydantic contexts.

    Canonical FlowType enum: ``app.services.flow.types.FlowType``
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from uuid import UUID

from app.exceptions import (
    FlowStateNotFoundError,
    FlowOperationError,
    FlowStateConflictError,
)
from app.models.flow import FlowKind, FlowTemplateVersion, PatientFlowState
from app.repositories.flow import FlowStateRepository
from app.schemas.flow import (
    FlowStateResponse,
    FlowAdvancementResponse,
    FlowPauseResponse,
    FlowResumeResponse,
    FlowHistoryResponse,
    FlowHistoryItem,
)
from app.services.enhanced_flow_engine import EnhancedFlowEngine
from app.services.flow.flags import is_awaiting_response as _is_awaiting_response
from app.services.flow.types import FlowType, normalize_flow_type  # canonical location
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)

FLOW_ADVANCE_BLOCKED_MESSAGE = "Cannot advance flow while awaiting patient response"
FLOW_ADVANCE_BLOCKED_CODE = "flow_advance_blocked_awaiting_response"
FLOW_ADVANCE_BLOCKED_REASON = "awaiting_response"


class FlowManagementService:
    """Service for managing patient flow operations."""

    def __init__(
        self,
        flow_repo: FlowStateRepository,
        db,
    ):
        self.flow_repo = flow_repo
        self.db = db
        self.enhanced_flow_engine = EnhancedFlowEngine(db)

    async def get_patient_flow_state(self, patient_id: UUID) -> FlowStateResponse:
        """
        Get comprehensive flow state for a patient.

        Args:
            patient_id: The patient's UUID

        Returns:
            FlowStateResponse with current flow state

        Raises:
            FlowStateNotFoundError: If no flow state exists
        """
        try:
            flow_state = self.flow_repo.get_active_flow(patient_id)

            if not flow_state:
                logger.debug(f"No active flow found for patient {patient_id}")
                return FlowStateResponse(
                    patient_id=patient_id,
                    has_active_flow=False,
                    message="No active flow found for patient",
                )

            # Calculate current day using enhanced flow engine
            current_day = await self.enhanced_flow_engine.calculate_patient_day(
                patient_id
            )

            # Get template version info
            template_version = (
                self.flow_repo.db.query(FlowTemplateVersion)
                .filter(FlowTemplateVersion.id == flow_state.flow_template_version_id)
                .first()
            )

            flow_type_name = ""
            version_string = ""
            if template_version:
                flow_kind = (
                    self.flow_repo.db.query(FlowKind)
                    .filter(FlowKind.id == template_version.kind_id)
                    .first()
                )
                flow_type_name = flow_kind.flow_type if flow_kind else "unknown"
                version_string = template_version.version

            flow_state_data = {
                "id": str(flow_state.id),
                "flow_type": flow_type_name,
                "current_step": flow_state.current_step,
                "current_day": current_day,
                "started_at": flow_state.started_at.isoformat(),
                "completed_at": flow_state.completed_at.isoformat()
                if flow_state.completed_at
                else None,
                "template_version": version_string,
                "template_version_id": str(flow_state.template_version_id),
                "state_data": flow_state.state_data or {},
                "is_paused": flow_state.state_data.get("paused", False)
                if flow_state.state_data
                else False,
            }

            return FlowStateResponse(
                patient_id=patient_id, has_active_flow=True, flow_state=flow_state_data
            )

        except Exception as e:
            logger.error(f"Failed to get flow state for patient {patient_id}: {e}")
            raise FlowOperationError(f"Failed to get flow state: {str(e)}")

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
            # Verify active flow exists
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

            self.enhanced_flow_engine._commit_flow_state_with_lock(
                flow_state, expected_version
            )

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
            # Get active flow
            flow_state = self.flow_repo.get_active_flow(patient_id)
            if not flow_state:
                raise FlowStateNotFoundError(
                    f"No active flow found for patient {patient_id}"
                )

            # Check if already paused
            if flow_state.state_data and flow_state.state_data.get("paused"):
                raise FlowStateConflictError("Flow is already paused")

            # Update flow state to paused
            flow_state.state_data = flow_state.state_data or {}
            flow_state.state_data["paused"] = True
            flow_state.state_data["pause_reason"] = (
                reason or "Manual pause by healthcare provider"
            )
            flow_state.state_data["paused_at"] = now_sao_paulo().isoformat()

            if user_id:
                flow_state.state_data["paused_by"] = str(user_id)

            auto_resume_at = None
            if duration_hours:
                resume_at = now_sao_paulo() + timedelta(hours=duration_hours)
                flow_state.state_data["auto_resume_at"] = resume_at.isoformat()
                auto_resume_at = resume_at.isoformat()

            flow_state.status = "paused"
            flow_state.last_interaction_at = now_sao_paulo()
            expected_version = flow_state.version
            self.enhanced_flow_engine._commit_flow_state_with_lock(
                flow_state, expected_version
            )

            logger.info(
                "Flow paused",
                extra={"patient_id": str(patient_id), "flow_id": str(flow_state.id)},
            )

            return FlowPauseResponse(
                success=True,
                patient_id=patient_id,
                flow_id=flow_state.id,
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
            # Get active flow
            flow_state = self.flow_repo.get_active_flow(patient_id)
            if not flow_state:
                raise FlowStateNotFoundError(
                    f"No active flow found for patient {patient_id}"
                )

            # Check if flow is actually paused
            if not flow_state.state_data or not flow_state.state_data.get("paused"):
                raise FlowStateConflictError("Flow is not currently paused")

            # Update flow state to resumed
            flow_state.state_data["paused"] = False
            flow_state.state_data["resumed_at"] = now_sao_paulo().isoformat()

            if user_id:
                flow_state.state_data["resumed_by"] = str(user_id)

            # Remove auto-resume data if it exists
            flow_state.state_data.pop("auto_resume_at", None)

            flow_state.status = "active"
            flow_state.last_interaction_at = now_sao_paulo()
            expected_version = flow_state.version
            self.enhanced_flow_engine._commit_flow_state_with_lock(
                flow_state, expected_version
            )

            logger.info(
                "Flow resumed",
                extra={"patient_id": str(patient_id), "flow_id": str(flow_state.id)},
            )

            return FlowResumeResponse(
                success=True,
                patient_id=patient_id,
                flow_id=flow_state.id,
                status="active",
                resumed_at=flow_state.state_data["resumed_at"],
                message="Patient flow resumed successfully",
            )

        except (FlowStateNotFoundError, FlowStateConflictError):
            raise
        except Exception as e:
            logger.error(f"Failed to resume flow for patient {patient_id}: {e}")
            raise FlowOperationError(f"Failed to resume flow: {str(e)}")

    async def get_patient_flow_history(
        self, patient_id: UUID, skip: int = 0, limit: int = 10
    ) -> FlowHistoryResponse:
        """
        Get paginated flow history for a patient.

        Args:
            patient_id: The patient's UUID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            FlowHistoryResponse with flow history
        """
        try:
            # Get flow history
            flow_states = self.flow_repo.get_by_patient(
                patient_id, skip=skip, limit=limit
            )

            # Get current active flow
            current_flow = self.flow_repo.get_active_flow(patient_id)

            # Format flow history
            flow_history = []
            for flow_state in flow_states:
                # Get flow_type via template_version → kind
                flow_type = (
                    flow_state.template_version.kind.flow_type
                    if flow_state.template_version and flow_state.template_version.kind
                    else "unknown"
                )
                version_str = (
                    flow_state.template_version.version_number
                    if flow_state.template_version
                    else "unknown"
                )

                flow_history.append(
                    FlowHistoryItem(
                        id=flow_state.id,
                        flow_type=flow_type,
                        current_step=flow_state.current_step,
                        started_at=flow_state.started_at.isoformat(),
                        completed_at=flow_state.completed_at.isoformat()
                        if flow_state.completed_at
                        else None,
                        template_version=version_str,
                        is_active=flow_state.completed_at is None,
                        is_paused=flow_state.state_data.get("paused", False)
                        if flow_state.state_data
                        else False,
                        state_data=flow_state.state_data or {},
                    )
                )

            # Format current flow
            current_flow_item = None
            if current_flow:
                flow_type = (
                    current_flow.template_version.kind.flow_type
                    if current_flow.template_version
                    and current_flow.template_version.kind
                    else "unknown"
                )
                version_str = (
                    current_flow.template_version.version_number
                    if current_flow.template_version
                    else "unknown"
                )

                current_flow_item = FlowHistoryItem(
                    id=current_flow.id,
                    flow_type=flow_type,
                    current_step=current_flow.current_step,
                    started_at=current_flow.started_at.isoformat(),
                    completed_at=current_flow.completed_at.isoformat()
                    if current_flow.completed_at
                    else None,
                    template_version=version_str,
                    is_active=True,
                    is_paused=current_flow.state_data.get("paused", False)
                    if current_flow.state_data
                    else False,
                    state_data=current_flow.state_data or {},
                )

            return FlowHistoryResponse(
                patient_id=patient_id,
                flow_history=flow_history,
                current_flow=current_flow_item,
                total_flows=len(flow_history),
                pagination={
                    "skip": skip,
                    "limit": limit,
                    "has_more": len(flow_states) == limit,
                },
            )

        except Exception as e:
            logger.error(f"Failed to get flow history for patient {patient_id}: {e}")
            raise FlowOperationError(f"Failed to get flow history: {str(e)}")

    async def get_flow_templates(self) -> list:
        """
        Get all available flow templates.

        Returns:
            List of flow templates with metadata
        """
        try:
            from app.services.flow_template import FlowTemplateService
            from app.repositories.flow_kind import FlowKindRepository

            flow_kind_repo = FlowKindRepository(self.flow_repo.db)
            template_service = FlowTemplateService(self.flow_repo.db)

            # Get all active flow kinds with their current versions
            flow_kinds = flow_kind_repo.get_all_active()

            templates = []
            for flow_kind in flow_kinds:
                template_data = template_service.get_template_data(flow_kind.flow_type)
                if template_data:
                    templates.append(
                        {
                            "flow_type": flow_kind.flow_type,
                            "name": flow_kind.name,
                            "description": flow_kind.description,
                            "category": getattr(flow_kind, "category", None),
                            "version": template_data.version,
                            "is_active": flow_kind.is_active,
                        }
                    )

            logger.info(f"Retrieved {len(templates)} flow templates")
            return templates

        except Exception as e:
            logger.error(f"Failed to get flow templates: {e}")
            raise FlowOperationError(f"Failed to get flow templates: {str(e)}")

    async def start_patient_flow(
        self, patient_id: UUID, flow_type: str, user_id: UUID = None
    ) -> FlowStateResponse:
        """
        Start a new flow for a patient.

        Args:
            patient_id: Patient's UUID
            flow_type: Type of flow to start
            user_id: Optional user ID who initiated the flow

        Returns:
            FlowStateResponse with new flow state
        """
        try:
            # Parse and validate flow type before starting the flow.
            flow_type_enum = normalize_flow_type(flow_type)
            if flow_type_enum == FlowType.CUSTOM:
                raise FlowOperationError(f"Invalid flow_type: {flow_type}")

            # Start flow using EnhancedFlowEngine (which inherits from FlowCore)
            flow_state = await self.enhanced_flow_engine.enroll_patient(
                patient_id=patient_id,
                flow_type=flow_type_enum,
                auto_commit=True,
            )

            # If user_id provided, maybe log it or store in metadata?
            # Existing code didn't seem to persist user_id in start_flow unless in state_data,
            # but enroll_patient sets a fresh step_data.
            # Let's add user_id if needed.
            if user_id:
                if not flow_state.step_data:
                    flow_state.step_data = {}
                flow_state.step_data["started_by"] = str(user_id)
                self.db.commit()

            logger.info(f"Started flow {flow_type} for patient {patient_id}")

            return FlowStateResponse(
                patient_id=patient_id,
                has_active_flow=True,
                flow_state={
                    "id": str(flow_state.id),
                    "flow_type": flow_type_enum.value,
                    "current_step": flow_state.current_step,
                    "started_at": flow_state.started_at.isoformat(),
                    "state_data": flow_state.state_data,
                },
                message="Flow started successfully",
            )

        except FlowStateNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to start flow for patient {patient_id}: {e}")
            raise FlowOperationError(f"Failed to start flow: {str(e)}")

    async def process_patient_response(
        self,
        patient_id: UUID,
        response_text: str,
        response_metadata: Optional[dict] = None,
    ) -> dict:
        """
        Process a patient response through the flow engine.

        Args:
            patient_id: Patient UUID
            response_text: Patient response content
            response_metadata: Optional metadata from channel

        Returns:
            Dict with response processing results
        """
        try:
            # EnhancedFlowEngine handles response processing and flow updates
            return await self.enhanced_flow_engine.process_patient_response(
                patient_id=patient_id,
                response_text=response_text,
                response_context=response_metadata,
            )
        except FlowStateNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to process response for patient {patient_id}: {e}")
            raise FlowOperationError(f"Failed to process patient response: {str(e)}")

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
                self.db.query(FlowKind)
                .filter(FlowKind.kind_key == target_kind_key)
                .first()
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
