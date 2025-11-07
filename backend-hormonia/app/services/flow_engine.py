"""
DEPRECATED: Flow engine service.

This module is deprecated and maintained only for backward compatibility.
Please use app.domain.flows.engine.FlowEngine instead.

All functionality has been refactored into modular components:
- app.domain.flows.engine.flow_engine.FlowEngine - Main engine orchestrator
- app.domain.flows.engine.context_builder.ContextBuilder - Context building
- app.domain.flows.engine.condition_evaluator.ConditionEvaluator - Condition evaluation
- app.domain.flows.engine.step_executor.StepExecutor - Step execution
- app.domain.flows.engine.transition_manager.TransitionManager - State transitions

This wrapper will be removed in a future version.
"""
import warnings
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session

from app.domain.flows.engine import FlowEngine as NewFlowEngine
from app.domain.flows.engine import ContextBuilder as NewContextBuilder
from app.models.flow import PatientFlowState

# Issue deprecation warning
warnings.warn(
    "app.services.flow_engine is deprecated. "
    "Use app.domain.flows.engine instead. "
    "This module will be removed in version 3.0.0.",
    DeprecationWarning,
    stacklevel=2
)


class FlowContext:
    """
    DEPRECATED: Context builder for flow execution.

    Use app.domain.flows.engine.ContextBuilder instead.
    """

    def __init__(self, db: Session):
        warnings.warn(
            "FlowContext is deprecated. Use app.domain.flows.engine.ContextBuilder instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self._impl = NewContextBuilder(db)

    def __getattr__(self, name):
        return getattr(self._impl, name)


class FlowEngine:
    """
    DEPRECATED: Flow engine for processing patient daily flows.

    Use app.domain.flows.engine.FlowEngine instead.

    This is a backward compatibility wrapper that delegates all calls
    to the new modular implementation.
    """

    def __init__(self, db: Session):
        warnings.warn(
            "app.services.flow_engine.FlowEngine is deprecated. "
            "Use app.domain.flows.engine.FlowEngine instead. "
            "This wrapper will be removed in version 3.0.0.",
            DeprecationWarning,
            stacklevel=2
        )
        self._impl = NewFlowEngine(db)
        self.db = db

    def __getattr__(self, name):
        """Delegate all attribute access to the new implementation."""
        return getattr(self._impl, name)

    # Explicitly proxy key methods for better IDE support
    def list_flows(self) -> List[dict[str, Any]]:
        """Return available flow templates."""
        return self._impl.list_flows()

    def get_current_flow(self, patient_id: UUID) -> dict[str, Any]:
        """Get current flow status for a patient."""
        return self._impl.get_current_flow(patient_id)

    def get_flow_history(
        self, patient_id: UUID
    ) -> Tuple[List[PatientFlowState], Optional[PatientFlowState]]:
        """Return all flow states for a patient and the active one if exists."""
        return self._impl.get_flow_history(patient_id)

    def start_flow(
        self,
        patient_id: UUID,
        flow_type: str,
        initial_data: Optional[dict[str, Any]] = None,
        fallback_to_default: bool = True
    ) -> PatientFlowState:
        """Start a new flow for a patient with graceful template fallback."""
        return self._impl.start_flow(patient_id, flow_type, initial_data, fallback_to_default)

    def process_patient_day(
        self,
        patient_id: UUID,
        force_transition: bool = False,
        additional_context: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Process a patient's daily flow progression (sync wrapper)."""
        return self._impl.process_patient_day(patient_id, force_transition, additional_context)

    async def process_patient_day_async(
        self,
        patient_id: UUID,
        force_transition: bool = False,
        additional_context: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Async version of process_patient_day for proper async chain."""
        return await self._impl.process_patient_day_async(patient_id, force_transition, additional_context)

    async def advance_flow(
        self,
        patient_id: UUID,
        to_step: Optional[int] = None,
        force: bool = False
    ) -> dict[str, Any]:
        """Manually advance a patient's flow."""
        return await self._impl.advance_flow(patient_id, to_step, force)

    def reset_flow(
        self,
        patient_id: UUID,
        to_step: int = 0,
        preserve_data: bool = True
    ) -> dict[str, Any]:
        """Reset a patient's flow to a specific step."""
        return self._impl.reset_flow(patient_id, to_step, preserve_data)

    def complete_flow(self, patient_id: UUID) -> dict[str, Any]:
        """Mark a patient's flow as completed."""
        return self._impl.complete_flow(patient_id)

    def get_flow_status(self, patient_id: UUID) -> dict[str, Any]:
        """Get current flow status for a patient."""
        return self._impl.get_flow_status(patient_id)

    def cleanup(self) -> None:
        """Cleanup FlowEngine resources."""
        return self._impl.cleanup()

    def __del__(self) -> None:
        """Destructor to ensure cleanup on garbage collection."""
        try:
            self.cleanup()
        except Exception:
            pass


# Maintain backward compatibility for direct imports
__all__ = ["FlowEngine", "FlowContext"]
