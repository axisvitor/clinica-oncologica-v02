"""
Flow Orchestrator - Lifecycle Module

Handles flow lifecycle operations: start, pause, resume, stop, restart.
"""

import logging
from typing import Dict, Any, Optional, Callable
from uuid import UUID
from datetime import datetime, timezone

from app.repositories.patient import PatientRepository
from ..state import FlowStateManager, FlowStateValidator
from ..templates import TemplateRenderer
from ..rules import FlowRulesEngine
from ..analytics import AnalyticsCollector
from .models import FlowExecutionContext, FlowExecutionResult, FlowOperationType
from .utils import calculate_treatment_day

logger = logging.getLogger(__name__)


class FlowLifecycleManager:
    """Manages flow lifecycle operations."""

    def __init__(
        self,
        patient_repo: PatientRepository,
        state_manager: FlowStateManager,
        state_validator: FlowStateValidator,
        template_renderer: TemplateRenderer,
        rules_engine: FlowRulesEngine,
        analytics_collector: AnalyticsCollector,
    ):
        """
        Initialize FlowLifecycleManager.

        Args:
            patient_repo: Repository for patient data access
            state_manager: Manager for flow state operations
            state_validator: Validator for flow state transitions
            template_renderer: Renderer for flow templates
            rules_engine: Engine for flow business rules
            analytics_collector: Collector for analytics events
        """
        self.patient_repo = patient_repo
        self.state_manager = state_manager
        self.state_validator = state_validator
        self.template_renderer = template_renderer
        self.rules_engine = rules_engine
        self.analytics_collector = analytics_collector

    async def start_flow(
        self,
        patient_id: UUID,
        flow_type: Optional[str],
        metadata: Optional[Dict[str, Any]],
        flow_step_executor: Callable,
        callback_executor: Callable,
        error_tracker: Callable,
        execution_tracker: Callable,
        logger_instance: Optional[logging.Logger] = None,
    ) -> FlowExecutionResult:
        """
        Start a new flow for a patient.

        Args:
            patient_id: UUID of patient
            flow_type: Type of flow to start (or "auto_detect")
            metadata: Optional metadata for flow
            flow_step_executor: Callback to execute flow steps
            callback_executor: Callback to execute flow callbacks
            error_tracker: Callback to track errors
            execution_tracker: Callback to track executions
            logger_instance: Optional logger instance

        Returns:
            FlowExecutionResult with operation outcome
        """
        log = logger_instance or logger

        context = FlowExecutionContext(
            patient_id=patient_id,
            flow_type=flow_type or "auto_detect",
            operation=FlowOperationType.START,
            current_day=0,
            metadata=metadata or {},
        )

        try:
            await callback_executor("before_execution", context)

            # Get patient information
            patient = self.patient_repo.get(patient_id)
            if not patient:
                error_tracker()
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.START,
                    message="Patient not found",
                    errors=["Patient not found"],
                )

            # Calculate current treatment day
            current_day = calculate_treatment_day(patient, logger=log)
            context.current_day = current_day

            # Auto-detect flow type if not provided
            if context.flow_type == "auto_detect":
                context.flow_type = self.rules_engine.determine_flow_type(current_day)

            # Validate flow start
            existing_flow = self.state_manager.get_cached_flow_state(patient_id)
            is_valid, error_msg = self.state_validator.validate_flow_start(
                patient, existing_flow, context.flow_type
            )

            if not is_valid:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.START,
                    message=error_msg,
                    errors=[error_msg],
                )

            # Create new flow state
            flow_state = self.state_manager.create_flow_state(
                patient=patient,
                flow_type=context.flow_type,
                current_day=current_day,
                operation=context.operation.value,
                metadata=context.metadata,
            )

            # Load and validate flow template
            template_config = await self.template_renderer.load_flow_template(
                context.flow_type
            )
            if not template_config:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.START,
                    message=f"Flow template not found for type: {context.flow_type}",
                    errors=[f"Template not found: {context.flow_type}"],
                )

            # Execute initial flow step
            execution_result = await flow_step_executor(
                context, flow_state, template_config
            )

            # Track analytics
            await self.analytics_collector.track_flow_start(
                patient_id=patient_id,
                flow_type=context.flow_type,
                current_day=current_day,
                metadata=context.metadata,
            )

            await callback_executor("after_execution", context)
            execution_tracker()

            return FlowExecutionResult(
                success=execution_result.get("success", False),
                patient_id=patient_id,
                operation=FlowOperationType.START,
                message=f"Flow started successfully: {context.flow_type}",
                data={
                    "flow_state_id": str(flow_state.id),
                    "flow_type": context.flow_type,
                    "current_day": current_day,
                    "execution_result": execution_result,
                },
            )

        except Exception as e:
            log.error(f"Error starting flow for patient {patient_id}: {e}")
            await callback_executor("on_error", context, error=e)

            return FlowExecutionResult(
                success=False,
                patient_id=patient_id,
                operation=FlowOperationType.START,
                message=f"Flow start failed: {str(e)}",
                errors=[str(e)],
            )

    async def advance_flow(
        self,
        patient_id: UUID,
        target_day: Optional[int],
        force_advance: bool,
        flow_step_executor: Callable,
        callback_executor: Callable,
        execution_tracker: Callable,
        db_commit: Callable,
        logger_instance: Optional[logging.Logger] = None,
    ) -> FlowExecutionResult:
        """
        Advance patient flow to next step or specific day.

        Args:
            patient_id: UUID of patient
            target_day: Target day to advance to
            force_advance: Whether to force advancement
            flow_step_executor: Callback to execute flow steps
            callback_executor: Callback to execute flow callbacks
            execution_tracker: Callback to track executions
            db_commit: Callback to commit database changes
            logger_instance: Optional logger instance

        Returns:
            FlowExecutionResult with operation outcome
        """
        log = logger_instance or logger

        try:
            # Get current flow state
            flow_state = self.state_manager.get_cached_flow_state(patient_id)
            if not flow_state:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.ADVANCE,
                    message="No active flow found",
                    errors=["No active flow state"],
                )

            # Get patient for day calculation
            patient = self.patient_repo.get(patient_id)
            current_day = calculate_treatment_day(patient, logger=log)

            # Determine target day
            if target_day is None:
                target_day = current_day + 1

            # Validate advancement
            is_valid, error_msg = self.state_validator.validate_flow_advancement(
                current_day, target_day, force_advance, flow_state
            )

            if not is_valid:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.ADVANCE,
                    message=error_msg,
                    errors=[error_msg],
                )

            context = FlowExecutionContext(
                patient_id=patient_id,
                flow_type=flow_state.flow_type,
                operation=FlowOperationType.ADVANCE,
                current_day=current_day,
                target_day=target_day,
            )

            await callback_executor("before_execution", context)

            # Check if flow type should change
            needs_transition, new_flow_type = (
                self.rules_engine.should_transition_flow_type(
                    flow_state.flow_type, target_day
                )
            )

            if needs_transition:
                # Transition to new flow type
                transition_result = await self.state_manager.transition_flow_type(
                    flow_state,
                    new_flow_type,
                    patient_id,
                    target_day,
                    analytics_callback=self.analytics_collector.track_flow_event,
                )
                if not transition_result.get("success"):
                    return FlowExecutionResult(
                        success=False,
                        patient_id=patient_id,
                        operation=FlowOperationType.ADVANCE,
                        message="Flow type transition failed",
                        errors=transition_result.get("errors", []),
                    )

            # Update flow state
            flow_state.current_step = target_day
            flow_state.state_data = flow_state.state_data or {}
            flow_state.state_data.update(
                {
                    "last_advanced": datetime.now(timezone.utc).isoformat(),
                    "advanced_to_day": target_day,
                    "status": "active",
                }
            )

            db_commit()
            self.state_manager.invalidate_flow_cache(patient_id)

            # Load template for new day
            template_config = await self.template_renderer.load_flow_template(
                flow_state.flow_type
            )
            if template_config:
                # Execute flow step for new day
                execution_result = await flow_step_executor(
                    context, flow_state, template_config
                )
            else:
                execution_result = {
                    "success": True,
                    "message": "Advanced without template execution",
                }

            # Track analytics
            await self.analytics_collector.track_flow_advance(
                patient_id=patient_id,
                flow_type=flow_state.flow_type,
                from_day=current_day,
                to_day=target_day,
            )

            await callback_executor("after_execution", context)
            execution_tracker()

            return FlowExecutionResult(
                success=True,
                patient_id=patient_id,
                operation=FlowOperationType.ADVANCE,
                message=f"Flow advanced to day {target_day}",
                data={
                    "from_day": current_day,
                    "to_day": target_day,
                    "flow_type": flow_state.flow_type,
                    "execution_result": execution_result,
                },
            )

        except Exception as e:
            log.error(f"Error advancing flow for patient {patient_id}: {e}")

            return FlowExecutionResult(
                success=False,
                patient_id=patient_id,
                operation=FlowOperationType.ADVANCE,
                message=f"Flow advancement failed: {str(e)}",
                errors=[str(e)],
            )

    async def pause_flow(
        self,
        patient_id: UUID,
        reason: Optional[str],
        metadata: Optional[Dict[str, Any]],
        execution_tracker: Callable,
        logger_instance: Optional[logging.Logger] = None,
    ) -> FlowExecutionResult:
        """
        Pause patient flow execution.

        Args:
            patient_id: UUID of patient
            reason: Reason for pausing
            metadata: Optional metadata
            execution_tracker: Callback to track executions
            logger_instance: Optional logger instance

        Returns:
            FlowExecutionResult with operation outcome
        """
        log = logger_instance or logger

        try:
            flow_state = self.state_manager.get_cached_flow_state(patient_id)

            is_valid, error_msg = self.state_validator.validate_flow_pause(flow_state)
            if not is_valid:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.PAUSE,
                    message=error_msg,
                    errors=[error_msg],
                )

            # Update flow state to paused
            success = self.state_manager.update_flow_state_status(
                flow_state, "paused", reason, metadata
            )

            if success:
                # Track analytics
                await self.analytics_collector.track_flow_pause(
                    patient_id=patient_id,
                    flow_type=flow_state.flow_type,
                    current_day=flow_state.current_step,
                    reason=reason,
                )

                execution_tracker()

                return FlowExecutionResult(
                    success=True,
                    patient_id=patient_id,
                    operation=FlowOperationType.PAUSE,
                    message="Flow paused successfully",
                    data={
                        "flow_type": flow_state.flow_type,
                        "current_day": flow_state.current_step,
                        "reason": reason,
                    },
                )
            else:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.PAUSE,
                    message="Failed to update flow state",
                    errors=["State update failed"],
                )

        except Exception as e:
            log.error(f"Error pausing flow for patient {patient_id}: {e}")

            return FlowExecutionResult(
                success=False,
                patient_id=patient_id,
                operation=FlowOperationType.PAUSE,
                message=f"Flow pause failed: {str(e)}",
                errors=[str(e)],
            )

    async def resume_flow(
        self,
        patient_id: UUID,
        metadata: Optional[Dict[str, Any]],
        execution_tracker: Callable,
        logger_instance: Optional[logging.Logger] = None,
    ) -> FlowExecutionResult:
        """
        Resume paused patient flow.

        Args:
            patient_id: UUID of patient
            metadata: Optional metadata
            execution_tracker: Callback to track executions
            logger_instance: Optional logger instance

        Returns:
            FlowExecutionResult with operation outcome
        """
        log = logger_instance or logger

        try:
            flow_state = self.state_manager.get_cached_flow_state(patient_id)

            is_valid, error_msg = self.state_validator.validate_flow_resume(flow_state)
            if not is_valid:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.RESUME,
                    message=error_msg,
                    warnings=[error_msg] if flow_state else [],
                    errors=[error_msg] if not flow_state else [],
                )

            # Update flow state to active
            success = self.state_manager.update_flow_state_status(
                flow_state, "active", None, metadata
            )

            if success:
                # Track analytics
                await self.analytics_collector.track_flow_resume(
                    patient_id=patient_id,
                    flow_type=flow_state.flow_type,
                    current_day=flow_state.current_step,
                )

                execution_tracker()

                return FlowExecutionResult(
                    success=True,
                    patient_id=patient_id,
                    operation=FlowOperationType.RESUME,
                    message="Flow resumed successfully",
                    data={
                        "flow_type": flow_state.flow_type,
                        "current_day": flow_state.current_step,
                    },
                )
            else:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.RESUME,
                    message="Failed to update flow state",
                    errors=["State update failed"],
                )

        except Exception as e:
            log.error(f"Error resuming flow for patient {patient_id}: {e}")

            return FlowExecutionResult(
                success=False,
                patient_id=patient_id,
                operation=FlowOperationType.RESUME,
                message=f"Flow resume failed: {str(e)}",
                errors=[str(e)],
            )

    async def stop_flow(
        self,
        patient_id: UUID,
        reason: Optional[str],
        metadata: Optional[Dict[str, Any]],
        execution_tracker: Callable,
        logger_instance: Optional[logging.Logger] = None,
    ) -> FlowExecutionResult:
        """
        Stop patient flow execution.

        Args:
            patient_id: UUID of patient
            reason: Reason for stopping
            metadata: Optional metadata
            execution_tracker: Callback to track executions
            logger_instance: Optional logger instance

        Returns:
            FlowExecutionResult with operation outcome
        """
        log = logger_instance or logger

        try:
            flow_state = self.state_manager.get_cached_flow_state(patient_id)

            is_valid, error_msg = self.state_validator.validate_flow_stop(flow_state)
            if not is_valid:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.STOP,
                    message=error_msg,
                    errors=[error_msg],
                )

            # Update flow state to completed
            success = self.state_manager.update_flow_state_status(
                flow_state, "completed", reason, metadata
            )

            if success:
                # Track analytics
                await self.analytics_collector.track_flow_stop(
                    patient_id=patient_id,
                    flow_type=flow_state.flow_type,
                    final_day=flow_state.current_step,
                    reason=reason,
                )

                execution_tracker()

                return FlowExecutionResult(
                    success=True,
                    patient_id=patient_id,
                    operation=FlowOperationType.STOP,
                    message="Flow stopped successfully",
                    data={
                        "flow_type": flow_state.flow_type,
                        "final_day": flow_state.current_step,
                        "reason": reason,
                    },
                )
            else:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.STOP,
                    message="Failed to update flow state",
                    errors=["State update failed"],
                )

        except Exception as e:
            log.error(f"Error stopping flow for patient {patient_id}: {e}")

            return FlowExecutionResult(
                success=False,
                patient_id=patient_id,
                operation=FlowOperationType.STOP,
                message=f"Flow stop failed: {str(e)}",
                errors=[str(e)],
            )
