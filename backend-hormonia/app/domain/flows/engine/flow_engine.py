"""
Flow engine for processing patient daily flows.
Enhanced with AI-powered message humanization.
Main orchestrator for flow execution and management.
"""
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import asyncio
import logging
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.flow import PatientFlowState, FlowKind, FlowTemplateVersion
from app.models.patient import Patient
from app.repositories.flow import FlowStateRepository
from app.repositories.flow_template import FlowTemplateRepository
from app.repositories.patient import PatientRepository
from app.services.template_loader import FlowTemplateData, FlowStep
from app.services.flow_template import FlowTemplateService
from app.services.state_machine import StateMachine, StateTransition, TransitionResult
from app.exceptions import NotFoundError, ValidationError
from app.core.event_loop_manager import EventLoopManager, AsyncFlowEngineBase
from app.core.async_context_manager import safe_create_task, ensure_async_context
from app.utils.db_retry import with_db_retry

# Import engine components
from app.domain.flows.engine.context_builder import ContextBuilder
from app.domain.flows.engine.condition_evaluator import ConditionEvaluator
from app.domain.flows.engine.step_executor import StepExecutor
from app.domain.flows.engine.transition_manager import TransitionManager

logger = logging.getLogger(__name__)


class FlowEngine(AsyncFlowEngineBase):
    """Engine for processing patient daily flows."""

    def __init__(self, db: Session):
        # Initialize parent class for proper async handling
        super().__init__()

        self.db = db
        self.flow_state_repo = FlowStateRepository(db)
        self.patient_repo = PatientRepository(db)
        self.template_service = FlowTemplateService(db)

        # Initialize engine components
        self.context_builder = ContextBuilder(db)
        self.condition_evaluator = ConditionEvaluator(db)
        self.step_executor = StepExecutor(db)
        self.transition_manager = TransitionManager(db)

        logger.info("FlowEngine initialized with modular architecture")

    def _get_flow_type_from_state(self, flow_state: PatientFlowState) -> str:
        """
        Helper method to get flow_type from a PatientFlowState using template_version_id.

        Args:
            flow_state: The patient flow state

        Returns:
            The flow_type string

        Raises:
            ValidationError: If template version or flow kind not found
        """
        template_version = self.db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.id == flow_state.template_version_id
        ).first()

        if not template_version:
            raise ValidationError(f"Template version not found for flow state {flow_state.id}")

        flow_kind = self.db.query(FlowKind).filter(
            FlowKind.id == template_version.kind_id
        ).first()

        if not flow_kind:
            raise ValidationError(f"Flow kind not found for template version {template_version.id}")

        return flow_kind.flow_type

    @with_db_retry(max_retries=3)
    def list_flows(self) -> List[dict[str, Any]]:
        """Return available flow templates."""
        templates = self.template_service.get_all_templates()
        return [
            {
                "flow_type": t.flow_type,
                "name": t.name,
                "version": t.version,
                "description": t.description,
            }
            for t in templates
        ]

    @with_db_retry(max_retries=3)
    def get_current_flow(self, patient_id: UUID) -> dict[str, Any]:
        """Get current flow status for a patient."""
        return self.get_flow_status(patient_id)

    @with_db_retry(max_retries=3)
    def get_flow_history(
        self, patient_id: UUID
    ) -> Tuple[List[PatientFlowState], Optional[PatientFlowState]]:
        """Return all flow states for a patient and the active one if exists."""
        flows = self.flow_state_repo.get_by_patient(patient_id)
        current = self.flow_state_repo.get_active_flow(patient_id)
        return flows, current

    def _validate_patient_data(self, patient: Patient) -> dict[str, Any]:
        """
        Validate patient data completeness before starting flow.

        Args:
            patient: Patient model instance

        Returns:
            Dict containing validation results with 'valid' flag and any errors

        Raises:
            ValidationError: If critical patient data is missing
        """
        errors = []
        warnings = []

        # Critical fields that MUST be present
        critical_fields = {
            'cpf': (patient.cpf, "CPF não informado"),
            'treatment_type': (patient.treatment_type, "Tipo de tratamento não informado"),
            'phone': (patient.phone, "Telefone não informado"),
        }

        # Check critical fields
        for field_name, (field_value, error_msg) in critical_fields.items():
            if not field_value or (isinstance(field_value, str) and not field_value.strip()):
                errors.append({
                    'field': field_name,
                    'message': error_msg,
                    'severity': 'error'
                })

        # Recommended fields for better flow execution
        recommended_fields = {
            'name': (patient.name, "Nome do paciente não informado"),
            'treatment_start_date': (patient.treatment_start_date, "Data de início do tratamento não informada"),
            'diagnosis': (patient.diagnosis, "Diagnóstico não informado"),
        }

        # Check recommended fields
        for field_name, (field_value, warning_msg) in recommended_fields.items():
            if not field_value or (isinstance(field_value, str) and not field_value.strip()):
                warnings.append({
                    'field': field_name,
                    'message': warning_msg,
                    'severity': 'warning'
                })

        # Additional validations
        if patient.phone:
            # Basic phone validation (Brazilian format)
            phone_digits = ''.join(filter(str.isdigit, patient.phone))
            if len(phone_digits) < 10 or len(phone_digits) > 11:
                errors.append({
                    'field': 'phone',
                    'message': f"Telefone com formato inválido: {patient.phone}",
                    'severity': 'error'
                })

        if patient.cpf:
            # Basic CPF validation (11 digits)
            cpf_digits = ''.join(filter(str.isdigit, patient.cpf))
            if len(cpf_digits) != 11:
                errors.append({
                    'field': 'cpf',
                    'message': f"CPF com formato inválido (deve ter 11 dígitos): {patient.cpf}",
                    'severity': 'error'
                })

        # Build validation result
        validation_result = {
            'valid': len(errors) == 0,
            'patient_id': str(patient.id),
            'errors': errors,
            'warnings': warnings,
            'checked_fields': {
                'critical': list(critical_fields.keys()),
                'recommended': list(recommended_fields.keys())
            }
        }

        # If there are critical errors, raise ValidationError
        if errors:
            error_messages = [f"{err['field']}: {err['message']}" for err in errors]
            raise ValidationError(
                f"Dados do paciente incompletos ou inválidos. Erros: {'; '.join(error_messages)}"
            )

        # Log warnings if any
        if warnings:
            warning_messages = [f"{warn['field']}: {warn['message']}" for warn in warnings]
            logger.warning(
                f"Paciente {patient.id} tem campos recomendados ausentes: {'; '.join(warning_messages)}"
            )

        return validation_result

    @with_db_retry(max_retries=3)
    def start_flow(
        self,
        patient_id: UUID,
        flow_type: str,
        initial_data: Optional[dict[str, Any]] = None,
        fallback_to_default: bool = True
    ) -> PatientFlowState:
        """
        Start a new flow for a patient with graceful template fallback.

        Args:
            patient_id: Patient UUID
            flow_type: Type of flow to start
            initial_data: Initial state data
            fallback_to_default: Whether to fallback to default template if specified template not found

        Returns:
            PatientFlowState: Created flow state

        Raises:
            NotFoundError: If patient not found or no suitable template available
            ValidationError: If flow validation fails or patient data incomplete
        """
        # Get patient
        patient = self.patient_repo.get(patient_id)
        if not patient:
            raise NotFoundError(f"Patient {patient_id} not found")

        # Pre-flight validation
        validation_result = self._validate_patient_data(patient)
        logger.info(
            f"Patient {patient_id} data validation passed. "
            f"Warnings: {len(validation_result.get('warnings', []))}"
        )

        # Get template with fallback handling
        template_data = self._get_template_with_fallback(flow_type, fallback_to_default)
        if not template_data:
            logger.error(f"No suitable template found for flow_type '{flow_type}' and patient {patient_id}")
            if not fallback_to_default:
                raise NotFoundError(f"Flow template '{flow_type}' not found")
            else:
                raise NotFoundError(f"Flow template '{flow_type}' not found and no default template available")

        # Log if we're using a fallback template
        if template_data.flow_type != flow_type:
            logger.warning(f"Using fallback template '{template_data.flow_type}' instead of requested '{flow_type}' for patient {patient_id}")

        # Validate template
        state_machine = StateMachine(template_data)
        validation_errors = state_machine.validate_flow()
        if validation_errors:
            raise ValidationError(f"Flow template validation failed: {validation_errors}")

        # Check if patient already has an active flow
        active_flow = self.flow_state_repo.get_active_flow(patient_id)
        if active_flow:
            raise ValidationError(f"Patient already has an active flow")

        # Get the FlowKind and current version for this template
        flow_kind = self.db.query(FlowKind).filter(
            FlowKind.flow_type == template_data.flow_type
        ).first()

        if not flow_kind:
            raise ValidationError(f"Flow kind not found for flow type: {template_data.flow_type}")

        # Get the current (is_current=true) template version
        from app.repositories.flow_template_version import FlowTemplateVersionRepository
        template_version_repo = FlowTemplateVersionRepository(self.db)
        current_version = template_version_repo.get_current_version_by_flow_type(template_data.flow_type)

        if not current_version:
            raise ValidationError(f"No current version found for flow type: {template_data.flow_type}")

        # Determine the first step (entry point) from the template
        entry_step = min(template_data.steps, key=lambda s: s.id).id if template_data.steps else 0

        # Create new flow state with template_version_id
        flow_state = PatientFlowState(
            patient_id=patient_id,
            template_version_id=current_version.id,
            current_step=entry_step,
            started_at=datetime.utcnow(),
            state_data={
                **(initial_data or {}),
                "requested_flow_type": flow_type,
                "actual_flow_type": template_data.flow_type,
                "fallback_used": template_data.flow_type != flow_type,
                "template_source": "fallback" if template_data.flow_type != flow_type else "requested",
                "entry_step": entry_step
            }
        )

        # Add to database session and flush to get ID
        self.db.add(flow_state)
        self.db.flush()
        created_flow = flow_state

        # Schedule initial step actions (async)
        safe_create_task(
            self.step_executor.schedule_step_actions(patient, created_flow.current_step, state_machine, self.condition_evaluator),
            name=f"schedule_step_actions_{patient_id}",
            context={"flow_type": template_data.flow_type, "step": created_flow.current_step}
        )

        # Schedule initial step (async)
        first_step = state_machine.get_current_step(0)
        if first_step:
            safe_create_task(
                self.step_executor.schedule_step(created_flow, first_step, created_flow.started_at, self.condition_evaluator),
                name=f"schedule_initial_step_{patient_id}",
                context={"flow_type": template_data.flow_type, "step": 0}
            )

        return created_flow

    def _get_template_with_fallback(self, flow_type: str, enable_fallback: bool = True) -> Optional[Any]:
        """
        Get template with fallback handling for missing templates.

        Args:
            flow_type: Requested flow type
            enable_fallback: Whether to try fallback templates

        Returns:
            Template data or None if not found
        """
        # Try to get the requested template first
        template_data = self.template_service.get_template_data(flow_type)
        if template_data:
            return template_data

        # If not found and fallback is enabled, try fallback options
        if not enable_fallback:
            return None

        # Define fallback hierarchy
        fallback_hierarchy = {
            "hormonia_fluxo_mama": ["hormonia_fluxo_hormonal", "hormonia_fluxo_padrao"],
            "hormonia_fluxo_prostata": ["hormonia_fluxo_hormonal", "hormonia_fluxo_padrao"],
            "hormonia_fluxo_pulmao": ["hormonia_fluxo_padrao"],
            "hormonia_fluxo_coloretal": ["hormonia_fluxo_padrao"],
            "hormonia_fluxo_hormonal": ["hormonia_fluxo_padrao"],
            "hormonia_fluxo_quimio": ["hormonia_fluxo_padrao"],
            "hormonia_fluxo_radio": ["hormonia_fluxo_padrao"],
            "initial_15_days": ["monthly_recurring", "hormonia_fluxo_padrao"],
            "days_16_45": ["monthly_recurring", "hormonia_fluxo_padrao"],
            "monthly_recurring": ["hormonia_fluxo_padrao"],
        }

        # Try fallbacks for this specific flow type
        fallbacks = fallback_hierarchy.get(flow_type, [])
        for fallback_type in fallbacks:
            template_data = self.template_service.get_template_data(fallback_type)
            if template_data:
                logger.info(f"Using fallback template '{fallback_type}' for requested '{flow_type}'")
                return template_data

        # Final fallback: try any available active template
        try:
            available_templates = self.template_service.get_all_templates(limit=1)
            if available_templates:
                fallback_template = available_templates[0]
                template_data = self.template_service.get_template_data(fallback_template.flow_type)
                if template_data:
                    logger.warning(f"Using emergency fallback template '{fallback_template.flow_type}' for requested '{flow_type}'")
                    return template_data
        except Exception as e:
            logger.error(f"Error during emergency fallback: {e}")

        return None

    async def process_patient_day_async(
        self,
        patient_id: UUID,
        force_transition: bool = False,
        additional_context: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Async version of process_patient_day for proper async chain."""
        return await self._process_patient_day_internal(patient_id, force_transition, additional_context)

    @with_db_retry(max_retries=3)
    def process_patient_day(
        self,
        patient_id: UUID,
        force_transition: bool = False,
        additional_context: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Process a patient's daily flow progression (sync wrapper).

        Args:
            patient_id: Patient UUID
            force_transition: Force transition ignoring conditions
            additional_context: Additional context for evaluation

        Returns:
            Dict containing processing results

        Raises:
            NotFoundError: If patient or flow not found
        """
        # Sync wrapper that delegates to async version
        try:
            return asyncio.run(self._process_patient_day_internal(patient_id, force_transition, additional_context))
        except RuntimeError:
            # Already in event loop, use safe task creation
            task = safe_create_task(
                self._process_patient_day_internal(patient_id, force_transition, additional_context),
                name=f"process_patient_day_{patient_id}",
                context={"force_transition": force_transition}
            )
            if task:
                return asyncio.get_event_loop().run_until_complete(task)
            else:
                # Task creation failed, run with fallback
                from app.core.async_context_manager import safe_run_coroutine
                return safe_run_coroutine(
                    self._process_patient_day_internal(patient_id, force_transition, additional_context),
                    timeout=300,
                    fallback_sync=True
                )

    @with_db_retry(max_retries=3)
    async def _process_patient_day_internal(
        self,
        patient_id: UUID,
        force_transition: bool = False,
        additional_context: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Internal async implementation of patient day processing."""
        # Get patient and active flow
        patient = self.patient_repo.get(patient_id)
        if not patient:
            raise NotFoundError(f"Patient {patient_id} not found")

        active_flow = self.flow_state_repo.get_active_flow(patient_id)
        if not active_flow:
            return {
                "status": "no_active_flow",
                "message": "Patient has no active flow",
                "patient_id": str(patient_id)
            }

        # Get flow type and template
        try:
            flow_type = self._get_flow_type_from_state(active_flow)
        except ValidationError as e:
            return {
                "status": "template_version_error",
                "message": str(e),
                "patient_id": str(patient_id),
                "flow_id": str(active_flow.id)
            }

        template_data = self.template_service.get_template_data(flow_type)
        if not template_data:
            return {
                "status": "template_not_found",
                "message": f"Template '{flow_type}' not found",
                "patient_id": str(patient_id),
                "flow_id": str(active_flow.id)
            }

        state_machine = StateMachine(template_data)

        # Build context
        context = self.context_builder.build_context(patient, active_flow, additional_context)

        # Attempt transition
        transition = state_machine.transition(
            from_step_id=active_flow.current_step,
            context=context,
            force=force_transition
        )

        # Handle transition result
        result = await self.transition_manager.handle_transition_result(
            active_flow, transition, context, state_machine, self.step_executor
        )

        return result

    @with_db_retry(max_retries=3)
    async def advance_flow(
        self,
        patient_id: UUID,
        to_step: Optional[int] = None,
        force: bool = False
    ) -> dict[str, Any]:
        """Manually advance a patient's flow."""
        active_flow = self.flow_state_repo.get_active_flow(patient_id)
        if not active_flow:
            raise NotFoundError(f"No active flow found for patient {patient_id}")

        patient = self.patient_repo.get(patient_id)
        if not patient:
            raise NotFoundError(f"Patient {patient_id} not found")

        flow_type = self._get_flow_type_from_state(active_flow)
        template_data = self.template_service.get_template_data(flow_type)
        if not template_data:
            raise NotFoundError(f"Template '{flow_type}' not found")

        state_machine = StateMachine(template_data)
        context = self.context_builder.build_context(patient, active_flow)

        if to_step is not None:
            if not state_machine.get_current_step(to_step):
                raise ValidationError(f"Step {to_step} does not exist in flow")

            active_flow.current_step = to_step
            active_flow.state_data = active_flow.state_data or {}
            active_flow.state_data["manual_override"] = {
                "timestamp": datetime.utcnow().isoformat(),
                "previous_step": active_flow.current_step,
                "forced": force
            }

            self.db.commit()

            return {
                "status": "manual_override",
                "message": f"Flow manually advanced to step {to_step}",
                "patient_id": str(patient_id),
                "flow_id": str(active_flow.id),
                "current_step": to_step,
                "previous_step": active_flow.current_step
            }
        else:
            return await self.process_patient_day_async(patient_id, force_transition=force)

    @with_db_retry(max_retries=3)
    def reset_flow(
        self,
        patient_id: UUID,
        to_step: int = 0,
        preserve_data: bool = True
    ) -> dict[str, Any]:
        """Reset a patient's flow to a specific step."""
        active_flow = self.flow_state_repo.get_active_flow(patient_id)
        if not active_flow:
            raise NotFoundError(f"No active flow found for patient {patient_id}")

        flow_type = self._get_flow_type_from_state(active_flow)
        template_data = self.template_service.get_template_data(flow_type)
        if not template_data:
            raise NotFoundError(f"Template '{flow_type}' not found")

        state_machine = StateMachine(template_data)
        if not state_machine.get_current_step(to_step):
            raise ValidationError(f"Step {to_step} does not exist in flow")

        reset_data = {
            "reset_timestamp": datetime.utcnow().isoformat(),
            "previous_step": active_flow.current_step,
            "reset_to_step": to_step,
            "preserve_data": preserve_data
        }

        active_flow.current_step = to_step
        active_flow.completed_at = None

        if preserve_data:
            active_flow.state_data = active_flow.state_data or {}
            active_flow.state_data["reset_history"] = active_flow.state_data.get("reset_history", [])
            active_flow.state_data["reset_history"].append(reset_data)
        else:
            active_flow.state_data = {"reset_history": [reset_data]}

        self.db.commit()

        return {
            "status": "flow_reset",
            "message": f"Flow reset to step {to_step}",
            "patient_id": str(patient_id),
            "flow_id": str(active_flow.id),
            "current_step": to_step,
            "previous_step": reset_data["previous_step"],
            "data_preserved": preserve_data
        }

    @with_db_retry(max_retries=3)
    def complete_flow(self, patient_id: UUID) -> dict[str, Any]:
        """Mark a patient's flow as completed."""
        active_flow = self.flow_state_repo.get_active_flow(patient_id)
        if not active_flow:
            raise NotFoundError(f"No active flow found for patient {patient_id}")

        active_flow.completed_at = datetime.utcnow()
        active_flow.state_data = active_flow.state_data or {}
        active_flow.state_data["completion"] = {
            "timestamp": datetime.utcnow().isoformat(),
            "final_step": active_flow.current_step,
            "manual_completion": True
        }

        self.db.commit()

        return {
            "status": "flow_completed",
            "message": "Flow marked as completed",
            "patient_id": str(patient_id),
            "flow_id": str(active_flow.id),
            "final_step": active_flow.current_step,
            "completed_at": active_flow.completed_at
        }

    @with_db_retry(max_retries=3)
    def get_flow_status(self, patient_id: UUID) -> dict[str, Any]:
        """Get current flow status for a patient."""
        patient = self.patient_repo.get(patient_id)
        if not patient:
            raise NotFoundError(f"Patient {patient_id} not found")

        active_flow = self.flow_state_repo.get_active_flow(patient_id)
        if not active_flow:
            return {
                "status": "no_active_flow",
                "patient_id": str(patient_id),
                "patient_name": patient.name,
                "has_active_flow": False
            }

        template_version = self.db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.id == active_flow.template_version_id
        ).first()

        if not template_version:
            raise ValidationError(f"Template version not found for flow state")

        flow_kind = self.db.query(FlowKind).filter(
            FlowKind.id == template_version.kind_id
        ).first()

        flow_type = flow_kind.flow_type if flow_kind else "unknown"

        template_data = self.template_service.get_template_data(flow_type)
        current_step = None
        available_transitions = []

        if template_data:
            state_machine = StateMachine(template_data)
            current_step = state_machine.get_current_step(active_flow.current_step)

            context = self.context_builder.build_context(patient, active_flow)
            available_transitions = state_machine.get_available_transitions(
                active_flow.current_step, context
            )

        return {
            "status": "active_flow",
            "patient_id": str(patient_id),
            "patient_name": patient.name,
            "has_active_flow": True,
            "flow": {
                "id": str(active_flow.id),
                "flow_type": active_flow.flow_type,
                "template_version": active_flow.template_version,
                "current_step": active_flow.current_step,
                "current_step_name": current_step.name if current_step else "Unknown",
                "current_step_type": current_step.type if current_step else "Unknown",
                "started_at": active_flow.started_at,
                "state_data": active_flow.state_data,
                "available_transitions": available_transitions
            }
        }

    def cleanup(self) -> None:
        """Cleanup FlowEngine resources."""
        try:
            logger.info("FlowEngine cleanup started")
            super().cleanup()
            logger.info("FlowEngine cleanup completed successfully")
        except Exception as e:
            logger.error(f"FlowEngine cleanup failed: {e}", exc_info=True)

    def __del__(self) -> None:
        """Destructor to ensure cleanup on garbage collection."""
        try:
            self.cleanup()
        except Exception as e:
            # Log cleanup failure during garbage collection
            logger.warning(f"FlowEngine cleanup failed during garbage collection: {e}")
