import logging
from typing import Any, Optional
from uuid import UUID

from app.exceptions import FlowOperationError, FlowStateNotFoundError
from app.models.flow import FlowKind, FlowTemplateVersion
from app.schemas.flow import (
    FlowHistoryItem,
    FlowHistoryResponse,
    FlowStateResponse,
)
from app.services.flow.types import FlowType, normalize_flow_type

logger = logging.getLogger(__name__)


class FlowManagementStateMixin:
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

            current_day = await self.enhanced_flow_engine.calculate_patient_day(patient_id)

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
            flow_states = self.flow_repo.get_by_patient(patient_id, skip=skip, limit=limit)
            current_flow = self.flow_repo.get_active_flow(patient_id)

            flow_history = []
            for flow_state in flow_states:
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

            current_flow_item = None
            if current_flow:
                flow_type = (
                    current_flow.template_version.kind.flow_type
                    if current_flow.template_version and current_flow.template_version.kind
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
            from app.repositories.flow_kind import FlowKindRepository
            from app.services.flow_template import FlowTemplateService

            flow_kind_repo = FlowKindRepository(self.flow_repo.db)
            template_service = FlowTemplateService(self.flow_repo.db)

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
            flow_type_enum = normalize_flow_type(flow_type)
            if flow_type_enum == FlowType.CUSTOM:
                raise FlowOperationError(f"Invalid flow_type: {flow_type}")

            flow_state = await self.enhanced_flow_engine.enroll_patient(
                patient_id=patient_id,
                flow_type=flow_type_enum,
                auto_commit=True,
            )

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
