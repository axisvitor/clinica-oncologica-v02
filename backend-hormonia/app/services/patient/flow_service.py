"""
PatientFlowService - Flow management for patients.

This service handles patient flow lifecycle management including
activation, pausing, completion, and template selection.

File: backend-hormonia/app/services/patient/flow_service.py
LOC: ~150
Responsibility: Patient flow management
"""
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID


from app.models.patient import Patient
from app.models.flow import PatientFlowState
from app.models.patient import FlowState
from app.services.enhanced_flow_engine import EnhancedFlowEngine, get_enhanced_flow_engine
from app.services.flow_core import FlowType
from app.services.websocket_events import websocket_events
from app.schemas.websocket import WebSocketEventType
from app.config import settings
from app.config.template_loader import get_template_for_treatment
from app.utils.db_retry import with_db_retry
import logging

logger = logging.getLogger(__name__)


class PatientFlowService:
    """
    Service for managing patient flows.

    Responsibilities:
    - Initialize default flows for new patients
    - Activate patient flows
    - Pause patient flows
    - Complete patient treatment
    - Check flow status
    - Template selection based on treatment type
    """

    def __init__(
        self,
        db: Any,
        flow_engine: Optional[EnhancedFlowEngine] = None,
    ):
        self.db = db
        self.flow_engine = flow_engine or get_enhanced_flow_engine(db)

    async def initialize_default_flow(
        self,
        patient: Patient,
        current_user_id: Optional[UUID] = None,
    ) -> Optional[PatientFlowState]:
        """
        Initialize default flow for patient based on treatment type.

        Args:
            patient: Patient to initialize flow for
            current_user_id: ID of user creating the flow

        Returns:
            Created PatientFlowState or None if auto-enrollment disabled
        """
        if not settings.ENABLE_AUTO_FLOW_ENROLLMENT:
            logger.info(
                f"Auto-enrollment disabled for patient {patient.id}"
            )
            return None

        try:
            template_name = self._select_template(patient.treatment_type)

            if not template_name:
                logger.warning(
                    f"No template found for patient {patient.id} "
                    f"(treatment_type: {patient.treatment_type})"
                )
                return None

            # Get flow configuration to find the correct Enum value
            from app.config.template_loader import get_template_loader
            
            loader = get_template_loader()
            flow_config = loader.get_flow_type_config(template_name)
            
            # Default to INITIAL_15_DAYS if mapping fails or template unknown
            flow_type = FlowType.INITIAL_15_DAYS
            
            if flow_config and flow_config.enum_value:
                try:
                    flow_type = FlowType(flow_config.enum_value)
                except ValueError:
                    logger.warning(f"Invalid enum value {flow_config.enum_value} for template {template_name}")

            # Enroll patient using the new engine
            flow_state = await self.flow_engine.enroll_patient(
                patient_id=patient.id,
                flow_type=flow_type
            )

            logger.info(
                f"Flow started for patient {patient.id} with type {flow_type.value} (template: {template_name})"
            )

            # Update patient metadata
            if not patient.patient_data:
                patient.patient_data = {}

            patient.patient_data.update({
                "auto_flow_started": True,
                "requested_template": template_name,
                "actual_flow_type": flow_type.value,
                "flow_start_time": flow_state.started_at.isoformat(),
                "initialized_by": str(current_user_id) if current_user_id else "system"
            })
            self.db.commit()

            return flow_state

        except Exception as e:
            logger.error(
                f"Failed to start flow for patient {patient.id}: {e}"
            )
            # Store error in metadata but don't fail the request
            if not patient.patient_data:
                patient.patient_data = {}

            patient.patient_data.update({
                "auto_flow_error": str(e),
                "flow_start_attempted": True,
                "flow_start_failed": True,
                "error_timestamp": datetime.now(timezone.utc).isoformat(),
            })

            try:
                self.db.commit()
            except Exception as commit_error:
                logger.error(
                    f"Failed to save flow error metadata for patient {patient.id}: "
                    f"{commit_error}"
                )

            return None

    @with_db_retry(max_retries=3)
    async def activate_patient(self, patient_id: UUID) -> Optional[Patient]:
        """Activate patient and set flow state to active."""
        from app.repositories.patient import PatientRepository

        repository = PatientRepository(self.db)
        patient = repository.get_by_id(patient_id)
        if not patient:
            return None

        update_data = {"flow_state": FlowState.ACTIVE}
        updated_patient = repository.update(patient, update_data)

        # Publish WebSocket event
        await websocket_events.publish_patient_event(
            event_type=WebSocketEventType.PATIENT_FLOW_CHANGED,
            patient_id=patient_id,
            patient_name=updated_patient.name,
            doctor_id=updated_patient.doctor_id,
            changes={"flow_state": FlowState.ACTIVE.value},
            metadata={"action": "activated"},
        )

        return updated_patient

    @with_db_retry(max_retries=3)
    async def pause_patient(self, patient_id: UUID) -> Optional[Patient]:
        """Pause patient flow."""
        from app.repositories.patient import PatientRepository

        repository = PatientRepository(self.db)
        patient = repository.get_by_id(patient_id)
        if not patient:
            return None

        update_data = {"flow_state": FlowState.PAUSED}
        updated_patient = repository.update(patient, update_data)

        # Publish WebSocket event
        await websocket_events.publish_patient_event(
            event_type=WebSocketEventType.PATIENT_FLOW_CHANGED,
            patient_id=patient_id,
            patient_name=updated_patient.name,
            doctor_id=updated_patient.doctor_id,
            changes={"flow_state": FlowState.PAUSED.value},
            metadata={"action": "paused"},
        )

        return updated_patient

    @with_db_retry(max_retries=3)
    def complete_patient_treatment(self, patient_id: UUID) -> Optional[Patient]:
        """Mark patient treatment as completed."""
        from app.repositories.patient import PatientRepository

        repository = PatientRepository(self.db)
        patient = repository.get_by_id(patient_id)
        if not patient:
            return None

        update_data = {"flow_state": "COMPLETED"}
        return repository.update(patient, update_data)

    def _select_template(self, treatment_type: Optional[str]) -> Optional[str]:
        """
        Select appropriate flow template based on treatment type.

        Uses centralized template configuration from flow_templates.yaml
        instead of hardcoded mapping.

        Args:
            treatment_type: Patient's treatment type

        Returns:
            Flow template identifier from configuration
        """
        # Use centralized template loader
        return get_template_for_treatment(treatment_type)

    @with_db_retry(max_retries=3)
    async def delete_flow(self, patient_id: UUID) -> bool:
        """
        Delete active flow for a patient.
        Used primarily for saga compensation.
        """
        try:
            # Find active flow state
            # We delete any flow state associated with the patient to be safe during compensation
            flow_states = self.db.query(PatientFlowState).filter(
                PatientFlowState.patient_id == patient_id
            ).all()
            
            if flow_states:
                for state in flow_states:
                    self.db.delete(state)
                self.db.commit()
                logger.info(f"Deleted {len(flow_states)} flow states for patient {patient_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete flow for patient {patient_id}: {e}")
            raise e
