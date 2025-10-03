"""
Flow Management Service for handling flow operations.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID

from app.exceptions import (
    FlowStateNotFoundError,
    FlowOperationError,
    FlowStateConflictError
)
from app.models.flow import PatientFlowState, FlowKind, FlowTemplateVersion
from app.models.flow_analytics import FlowMessage
from app.repositories.flow import FlowStateRepository
from app.schemas.flow import (
    FlowStateResponse,
    FlowAdvancementResponse,
    FlowPauseResponse,
    FlowResumeResponse,
    FlowHistoryResponse,
    FlowHistoryItem
)
from app.services.flow import FlowEngineIntegrationService

logger = logging.getLogger(__name__)


class FlowManagementService:
    """Service for managing patient flow operations."""
    
    def __init__(
        self,
        flow_repo: FlowStateRepository,
        flow_engine: FlowEngineIntegrationService
    ):
        self.flow_repo = flow_repo
        self.flow_engine = flow_engine
    
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
                logger.info(f"No active flow found for patient {patient_id}")
                return FlowStateResponse(
                    patient_id=patient_id,
                    has_active_flow=False,
                    message="No active flow found for patient"
                )
            
            # Calculate current day using flow engine
            current_day = await self.flow_engine.enhanced_flow_engine.calculate_patient_day(patient_id)
            
            # Get template version info
            template_version = self.flow_repo.db.query(FlowTemplateVersion).filter(
                FlowTemplateVersion.id == flow_state.template_version_id
            ).first()

            flow_type_name = ""
            version_string = ""
            if template_version:
                flow_kind = self.flow_repo.db.query(FlowKind).filter(
                    FlowKind.id == template_version.kind_id
                ).first()
                flow_type_name = flow_kind.flow_type if flow_kind else "unknown"
                version_string = template_version.version

            flow_state_data = {
                "id": str(flow_state.id),
                "flow_type": flow_type_name,
                "current_step": flow_state.current_step,
                "current_day": current_day,
                "started_at": flow_state.started_at.isoformat(),
                "completed_at": flow_state.completed_at.isoformat() if flow_state.completed_at else None,
                "template_version": version_string,
                "template_version_id": str(flow_state.template_version_id),
                "state_data": flow_state.state_data or {},
                "is_paused": flow_state.state_data.get("paused", False) if flow_state.state_data else False
            }
            
            return FlowStateResponse(
                patient_id=patient_id,
                has_active_flow=True,
                flow_state=flow_state_data
            )
            
        except Exception as e:
            logger.error(f"Failed to get flow state for patient {patient_id}: {e}")
            raise FlowOperationError(f"Failed to get flow state: {str(e)}")
    
    async def advance_patient_flow(
        self,
        patient_id: UUID,
        force_day: Optional[int] = None
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
                raise FlowStateNotFoundError(f"No active flow found for patient {patient_id}")
            
            # Advance flow using enhanced flow engine
            advancement_result = await self.flow_engine.enhanced_flow_engine.advance_patient_flow(
                patient_id=patient_id,
                force_day=force_day
            )
            
            logger.info(f"Successfully advanced flow for patient {patient_id} to day {advancement_result['current_day']}")
            
            return FlowAdvancementResponse(
                success=True,
                patient_id=patient_id,
                advancement_result=advancement_result,
                message=f"Patient flow advanced successfully to day {advancement_result['current_day']}"
            )
            
        except FlowStateNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to advance flow for patient {patient_id}: {e}")
            raise FlowOperationError(f"Failed to advance flow: {str(e)}")
    
    async def pause_patient_flow(
        self,
        patient_id: UUID,
        reason: Optional[str] = None,
        duration_hours: Optional[int] = None,
        user_id: UUID = None
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
                raise FlowStateNotFoundError(f"No active flow found for patient {patient_id}")
            
            # Check if already paused
            if flow_state.state_data and flow_state.state_data.get("paused"):
                raise FlowStateConflictError("Flow is already paused")
            
            # Update flow state to paused
            flow_state.state_data = flow_state.state_data or {}
            flow_state.state_data["paused"] = True
            flow_state.state_data["pause_reason"] = reason or "Manual pause by healthcare provider"
            flow_state.state_data["paused_at"] = datetime.utcnow().isoformat()
            
            if user_id:
                flow_state.state_data["paused_by"] = str(user_id)
            
            auto_resume_at = None
            if duration_hours:
                resume_at = datetime.utcnow() + timedelta(hours=duration_hours)
                flow_state.state_data["auto_resume_at"] = resume_at.isoformat()
                auto_resume_at = resume_at.isoformat()
            
            # Save changes
            self.flow_repo.db.commit()
            
            logger.info(f"Successfully paused flow for patient {patient_id}")
            
            return FlowPauseResponse(
                success=True,
                patient_id=patient_id,
                flow_id=flow_state.id,
                status="paused",
                reason=reason,
                paused_at=flow_state.state_data["paused_at"],
                auto_resume_at=auto_resume_at,
                message="Patient flow paused successfully"
            )
            
        except (FlowStateNotFoundError, FlowStateConflictError):
            raise
        except Exception as e:
            logger.error(f"Failed to pause flow for patient {patient_id}: {e}")
            raise FlowOperationError(f"Failed to pause flow: {str(e)}")
    
    async def resume_patient_flow(
        self,
        patient_id: UUID,
        user_id: UUID = None
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
                raise FlowStateNotFoundError(f"No active flow found for patient {patient_id}")
            
            # Check if flow is actually paused
            if not flow_state.state_data or not flow_state.state_data.get("paused"):
                raise FlowStateConflictError("Flow is not currently paused")
            
            # Update flow state to resumed
            flow_state.state_data["paused"] = False
            flow_state.state_data["resumed_at"] = datetime.utcnow().isoformat()
            
            if user_id:
                flow_state.state_data["resumed_by"] = str(user_id)
            
            # Remove auto-resume data if it exists
            flow_state.state_data.pop("auto_resume_at", None)
            
            # Save changes
            self.flow_repo.db.commit()
            
            logger.info(f"Successfully resumed flow for patient {patient_id}")
            
            return FlowResumeResponse(
                success=True,
                patient_id=patient_id,
                flow_id=flow_state.id,
                status="active",
                resumed_at=flow_state.state_data["resumed_at"],
                message="Patient flow resumed successfully"
            )
            
        except (FlowStateNotFoundError, FlowStateConflictError):
            raise
        except Exception as e:
            logger.error(f"Failed to resume flow for patient {patient_id}: {e}")
            raise FlowOperationError(f"Failed to resume flow: {str(e)}")
    
    async def get_patient_flow_history(
        self,
        patient_id: UUID,
        skip: int = 0,
        limit: int = 10
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
            flow_states = self.flow_repo.get_by_patient(patient_id, skip=skip, limit=limit)
            
            # Get current active flow
            current_flow = self.flow_repo.get_active_flow(patient_id)
            
            # Format flow history
            flow_history = []
            for flow_state in flow_states:
                # Get flow_type via template_version → kind
                flow_type = flow_state.template_version.kind.flow_type if flow_state.template_version and flow_state.template_version.kind else "unknown"
                version_str = flow_state.template_version.version_number if flow_state.template_version else "unknown"

                flow_history.append(FlowHistoryItem(
                    id=flow_state.id,
                    flow_type=flow_type,
                    current_step=flow_state.current_step,
                    started_at=flow_state.started_at.isoformat(),
                    completed_at=flow_state.completed_at.isoformat() if flow_state.completed_at else None,
                    template_version=version_str,
                    is_active=flow_state.completed_at is None,
                    is_paused=flow_state.state_data.get("paused", False) if flow_state.state_data else False,
                    state_data=flow_state.state_data or {}
                ))

            # Format current flow
            current_flow_item = None
            if current_flow:
                flow_type = current_flow.template_version.kind.flow_type if current_flow.template_version and current_flow.template_version.kind else "unknown"
                version_str = current_flow.template_version.version_number if current_flow.template_version else "unknown"

                current_flow_item = FlowHistoryItem(
                    id=current_flow.id,
                    flow_type=flow_type,
                    current_step=current_flow.current_step,
                    started_at=current_flow.started_at.isoformat(),
                    completed_at=current_flow.completed_at.isoformat() if current_flow.completed_at else None,
                    template_version=version_str,
                    is_active=True,
                    is_paused=current_flow.state_data.get("paused", False) if current_flow.state_data else False,
                    state_data=current_flow.state_data or {}
                )
            
            return FlowHistoryResponse(
                patient_id=patient_id,
                flow_history=flow_history,
                current_flow=current_flow_item,
                total_flows=len(flow_history),
                pagination={
                    "skip": skip,
                    "limit": limit,
                    "has_more": len(flow_states) == limit
                }
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
                    templates.append({
                        "flow_type": flow_kind.flow_type,
                        "name": flow_kind.name,
                        "description": flow_kind.description,
                        "category": flow_kind.category,
                        "version": template_data.version,
                        "is_active": flow_kind.is_active
                    })
            
            logger.info(f"Retrieved {len(templates)} flow templates")
            return templates
            
        except Exception as e:
            logger.error(f"Failed to get flow templates: {e}")
            raise FlowOperationError(f"Failed to get flow templates: {str(e)}")
    
    async def start_patient_flow(
        self,
        patient_id: UUID,
        flow_type: str,
        user_id: UUID = None
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
            # Start flow using FlowEngine (synchronous method)
            flow_state = self.flow_engine.start_flow(
                patient_id=patient_id,
                flow_type=flow_type,
                initial_data=None,
                fallback_to_default=True
            )
            
            logger.info(f"Started flow {flow_type} for patient {patient_id}")
            
            return FlowStateResponse(
                patient_id=patient_id,
                has_active_flow=True,
                flow_state={
                    "id": str(flow_state.id),
                    "flow_type": flow_type,
                    "current_step": flow_state.current_step,
                    "started_at": flow_state.started_at.isoformat(),
                    "state_data": flow_state.state_data
                },
                message="Flow started successfully"
            )
            
        except FlowStateNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to start flow for patient {patient_id}: {e}")
            raise FlowOperationError(f"Failed to start flow: {str(e)}")
