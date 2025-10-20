"""
Flow Manager Adapter - Backward compatibility layer for Flow Services (QW-021).

This adapter bridges the consolidated FlowManager with the legacy flow system,
providing backward compatibility during the migration phase.

The adapter:
- Maintains legacy API signatures
- Translates between old and new data structures
- Provides deprecation warnings
- Enables gradual migration via feature flags

This is a transitional component - once migration is complete (QW-021 Phase 6),
this adapter can be removed and all code updated to use FlowManager directly.

Migration Strategy:
    1. Legacy code continues to work via this adapter
    2. New code uses FlowManager directly
    3. Deprecation warnings guide developers to migrate
    4. After 2-4 weeks of stable operation, remove adapter and legacy files

Example (Legacy code using adapter):
    >>> # Old code (still works)
    >>> from app.services.enhanced_flow_engine import get_enhanced_flow_engine
    >>> engine = get_enhanced_flow_engine(db)
    >>> result = engine.start_flow(patient_id, flow_type)
    >>>
    >>> # Behind the scenes, adapter translates to:
    >>> # manager = FlowManager(db)
    >>> # result = await manager.start_flow(patient_id, flow_type)
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import UUID
import logging
import warnings

from sqlalchemy.orm import Session

from .manager import FlowManager
from .types import (
    FlowType,
    FlowStatus,
    FlowContext,
    FlowPriority,
    FlowStepData,
    FlowMetrics,
)
from .config import get_flow_config

logger = logging.getLogger(__name__)


class FlowManagerAdapter:
    """
    Adapter for backward compatibility with legacy flow services.

    This adapter translates between legacy flow API and new FlowManager API,
    ensuring existing code continues to work during migration.

    Provides compatibility for:
    - enhanced_flow_engine.py (EnhancedFlowEngine)
    - flow_engine.py (FlowEngine - legacy)
    - flow.py (FlowEngineIntegrationService)
    - flow_management.py (FlowManagementService)
    - orchestrators/flow_orchestrator.py (FlowOrchestrator)

    Example:
        >>> # Legacy code path
        >>> adapter = FlowManagerAdapter(db)
        >>> flow_id = adapter.start_flow(patient_id, "daily_checkin")
        >>>
        >>> # New code path (preferred)
        >>> manager = FlowManager(db)
        >>> flow_id = await manager.start_flow(patient_id, FlowType.DAILY_CHECKIN)
    """

    def __init__(self, db: Session, show_warnings: bool = True):
        """
        Initialize the flow manager adapter.

        Args:
            db: Database session
            show_warnings: Show deprecation warnings (default: True)
        """
        self.db = db
        self.manager = FlowManager(db)
        self.config = get_flow_config()
        self.show_warnings = (
            show_warnings and self.config.feature_flags.show_legacy_deprecation_warnings
        )

        if self.show_warnings:
            warnings.warn(
                "FlowManagerAdapter is deprecated. "
                "Use FlowManager directly from app.services.flow. "
                "See QW-021 migration guide for details.",
                DeprecationWarning,
                stacklevel=2,
            )

        logger.info("FlowManagerAdapter initialized (backward compatibility layer)")

    # ========================================================================
    # Legacy API: enhanced_flow_engine.py compatibility
    # ========================================================================

    def start_flow(
        self,
        patient_id: UUID,
        flow_type: str,
        template_id: Optional[str] = None,
        initial_data: Optional[Dict[str, Any]] = None,
        priority: str = "medium",
        **kwargs,
    ) -> UUID:
        """
        Start a new flow (legacy API).

        Compatible with:
        - EnhancedFlowEngine.start_flow()
        - FlowEngine.start_flow()

        Args:
            patient_id: Patient UUID
            flow_type: Flow type as string (e.g., "daily_checkin")
            template_id: Optional template ID
            initial_data: Optional initial flow data
            priority: Priority as string (default: "medium")
            **kwargs: Additional legacy parameters

        Returns:
            Flow instance UUID

        Example:
            >>> flow_id = adapter.start_flow(
            ...     patient_id=uuid4(),
            ...     flow_type="daily_checkin",
            ...     priority="high"
            ... )
        """
        self._emit_deprecation_warning("start_flow")

        # Convert string flow_type to enum
        try:
            flow_type_enum = FlowType(flow_type)
        except ValueError:
            logger.error(f"Invalid flow type: {flow_type}")
            raise ValueError(f"Unknown flow type: {flow_type}")

        # Convert string priority to enum
        try:
            priority_enum = FlowPriority(priority)
        except ValueError:
            logger.warning(f"Invalid priority '{priority}', using MEDIUM")
            priority_enum = FlowPriority.MEDIUM

        # Call new API (synchronously wrap async for compatibility)
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        flow_id = loop.run_until_complete(
            self.manager.start_flow(
                patient_id=patient_id,
                flow_type=flow_type_enum,
                template_id=template_id,
                initial_data=initial_data,
                priority=priority_enum,
                metadata=kwargs,
            )
        )

        return flow_id

    def advance_flow(
        self,
        flow_instance_id: UUID,
        user_input: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Advance flow to next step (legacy API).

        Compatible with:
        - EnhancedFlowEngine.advance_flow()
        - FlowEngine.execute_next_step()

        Args:
            flow_instance_id: Flow instance UUID
            user_input: Optional user input data
            **kwargs: Additional legacy parameters

        Returns:
            Step result as dictionary

        Example:
            >>> result = adapter.advance_flow(
            ...     flow_id,
            ...     user_input={"response": "Good"}
            ... )
        """
        self._emit_deprecation_warning("advance_flow")

        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        step_result = loop.run_until_complete(
            self.manager.advance_flow(
                flow_instance_id=flow_instance_id, user_input=user_input
            )
        )

        # Convert FlowStepData to legacy dict format
        return self._step_data_to_legacy_dict(step_result)

    def pause_flow(
        self, flow_instance_id: UUID, reason: Optional[str] = None, **kwargs
    ) -> bool:
        """
        Pause flow execution (legacy API).

        Args:
            flow_instance_id: Flow instance UUID
            reason: Optional pause reason
            **kwargs: Additional legacy parameters

        Returns:
            True if successful

        Example:
            >>> success = adapter.pause_flow(flow_id, reason="User requested")
        """
        self._emit_deprecation_warning("pause_flow")

        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(self.manager.pause_flow(flow_instance_id, reason))
        return True

    def resume_flow(self, flow_instance_id: UUID, **kwargs) -> bool:
        """
        Resume paused flow execution (legacy API).

        Args:
            flow_instance_id: Flow instance UUID
            **kwargs: Additional legacy parameters

        Returns:
            True if successful

        Example:
            >>> success = adapter.resume_flow(flow_id)
        """
        self._emit_deprecation_warning("resume_flow")

        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(self.manager.resume_flow(flow_instance_id))
        return True

    def stop_flow(
        self, flow_instance_id: UUID, reason: str = "manual", **kwargs
    ) -> bool:
        """
        Stop flow execution (legacy API).

        Args:
            flow_instance_id: Flow instance UUID
            reason: Stop reason
            **kwargs: Additional legacy parameters

        Returns:
            True if successful

        Example:
            >>> success = adapter.stop_flow(flow_id, reason="Error occurred")
        """
        self._emit_deprecation_warning("stop_flow")

        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(self.manager.stop_flow(flow_instance_id, reason))
        return True

    def get_flow_state(self, flow_instance_id: UUID, **kwargs) -> Dict[str, Any]:
        """
        Get current flow state (legacy API).

        Args:
            flow_instance_id: Flow instance UUID
            **kwargs: Additional legacy parameters

        Returns:
            Flow state as dictionary

        Example:
            >>> state = adapter.get_flow_state(flow_id)
            >>> print(state["status"], state["current_step_id"])
        """
        self._emit_deprecation_warning("get_flow_state")

        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        context = loop.run_until_complete(self.manager.get_flow_state(flow_instance_id))

        if not context:
            return None

        # Convert FlowContext to legacy dict format
        return self._context_to_legacy_dict(context)

    def get_flow_metrics(self, flow_instance_id: UUID, **kwargs) -> Dict[str, Any]:
        """
        Get flow execution metrics (legacy API).

        Args:
            flow_instance_id: Flow instance UUID
            **kwargs: Additional legacy parameters

        Returns:
            Metrics as dictionary

        Example:
            >>> metrics = adapter.get_flow_metrics(flow_id)
            >>> print(f"Completed: {metrics['completed_steps']}/{metrics['total_steps']}")
        """
        self._emit_deprecation_warning("get_flow_metrics")

        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        metrics = loop.run_until_complete(
            self.manager.get_flow_metrics(flow_instance_id)
        )

        if not metrics:
            return None

        # Convert FlowMetrics to legacy dict format
        return {
            "total_steps": metrics.total_steps,
            "completed_steps": metrics.completed_steps,
            "failed_steps": metrics.failed_steps,
            "skipped_steps": metrics.skipped_steps,
            "duration_seconds": metrics.duration_seconds,
            "average_step_duration_seconds": metrics.average_step_duration_seconds,
            "retry_count": metrics.retry_count,
            "error_count": metrics.error_count,
        }

    # ========================================================================
    # Legacy API: flow_orchestrator.py compatibility
    # ========================================================================

    def orchestrate_flow(
        self, flow_instance_id: UUID, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Orchestrate flow execution (legacy FlowOrchestrator API).

        Args:
            flow_instance_id: Flow instance UUID
            context: Optional execution context

        Returns:
            Orchestration result

        Example:
            >>> result = adapter.orchestrate_flow(flow_id, context={})
        """
        self._emit_deprecation_warning("orchestrate_flow")

        # In legacy orchestrator, this would execute multiple steps
        # For now, just advance one step
        return self.advance_flow(flow_instance_id, user_input=context)

    # ========================================================================
    # Legacy API: flow_management.py compatibility
    # ========================================================================

    def list_patient_flows(
        self, patient_id: UUID, status: Optional[str] = None, **kwargs
    ) -> List[Dict[str, Any]]:
        """
        List flows for a patient (legacy FlowManagementService API).

        Args:
            patient_id: Patient UUID
            status: Optional status filter
            **kwargs: Additional filters

        Returns:
            List of flow dictionaries

        Example:
            >>> flows = adapter.list_patient_flows(patient_id, status="active")
        """
        self._emit_deprecation_warning("list_patient_flows")

        # In production, would query database
        # For now, return empty list
        logger.warning("list_patient_flows not fully implemented in adapter")
        return []

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _context_to_legacy_dict(self, context: FlowContext) -> Dict[str, Any]:
        """Convert FlowContext to legacy dictionary format."""
        return {
            "flow_instance_id": str(context.flow_instance_id),
            "flow_type": context.flow_type.value,
            "patient_id": str(context.patient_id),
            "current_step_id": context.current_step_id,
            "status": context.status.value,
            "flow_data": context.flow_data,
            "variables": context.variables,
            "steps_completed": context.steps_completed,
            "steps_history": [
                self._step_data_to_legacy_dict(s) for s in context.steps_history
            ],
            "started_at": context.started_at.isoformat()
            if context.started_at
            else None,
            "completed_at": (
                context.completed_at.isoformat() if context.completed_at else None
            ),
            "expires_at": (
                context.expires_at.isoformat() if context.expires_at else None
            ),
            "metadata": context.metadata,
            "priority": context.priority.value,
        }

    def _step_data_to_legacy_dict(self, step_data: FlowStepData) -> Dict[str, Any]:
        """Convert FlowStepData to legacy dictionary format."""
        return {
            "step_id": step_data.step_id,
            "step_type": step_data.step_type.value,
            "step_name": step_data.step_name,
            "status": step_data.status.value,
            "input_data": step_data.input_data,
            "output_data": step_data.output_data,
            "started_at": (
                step_data.started_at.isoformat() if step_data.started_at else None
            ),
            "completed_at": (
                step_data.completed_at.isoformat() if step_data.completed_at else None
            ),
            "metadata": step_data.metadata,
            "error": step_data.error,
        }

    def _emit_deprecation_warning(self, method_name: str) -> None:
        """Emit deprecation warning for legacy method."""
        if not self.show_warnings:
            return

        warnings.warn(
            f"FlowManagerAdapter.{method_name}() is deprecated. "
            f"Use FlowManager.{method_name}() directly. "
            "See QW-021 migration guide.",
            DeprecationWarning,
            stacklevel=3,
        )

    def __repr__(self) -> str:
        """String representation."""
        return f"<FlowManagerAdapter(manager={self.manager})>"


# ============================================================================
# Factory Functions (for gradual migration)
# ============================================================================


def get_enhanced_flow_engine(db: Session) -> FlowManagerAdapter:
    """
    Get enhanced flow engine (legacy compatibility).

    This function provides backward compatibility with legacy code
    that imports from app.services.enhanced_flow_engine.

    Args:
        db: Database session

    Returns:
        FlowManagerAdapter instance

    Example:
        >>> # Legacy code (still works)
        >>> from app.services.enhanced_flow_engine import get_enhanced_flow_engine
        >>> engine = get_enhanced_flow_engine(db)
        >>> flow_id = engine.start_flow(patient_id, "daily_checkin")

    Deprecated:
        Use get_flow_manager() instead:
        >>> from app.services.flow import get_flow_manager
        >>> manager = get_flow_manager(db)
        >>> flow_id = await manager.start_flow(patient_id, FlowType.DAILY_CHECKIN)
    """
    warnings.warn(
        "get_enhanced_flow_engine() is deprecated. "
        "Use get_flow_manager() from app.services.flow instead. "
        "See QW-021 migration guide.",
        DeprecationWarning,
        stacklevel=2,
    )

    config = get_flow_config()

    if config.is_consolidated_enabled():
        # Use new consolidated system via adapter
        return FlowManagerAdapter(db)
    else:
        # Import legacy system only when needed
        try:
            from app.services.enhanced_flow_engine import (
                EnhancedFlowEngine as LegacyEngine,
            )

            logger.info("Using legacy EnhancedFlowEngine (QW-021 not enabled)")
            return LegacyEngine(db)
        except ImportError:
            logger.warning("Legacy EnhancedFlowEngine not found, using adapter anyway")
            return FlowManagerAdapter(db)


def get_flow_orchestrator(db: Session) -> FlowManagerAdapter:
    """
    Get flow orchestrator (legacy compatibility).

    Args:
        db: Database session

    Returns:
        FlowManagerAdapter instance

    Deprecated:
        Use FlowManager directly.
    """
    warnings.warn(
        "get_flow_orchestrator() is deprecated. "
        "Use FlowManager from app.services.flow instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    return FlowManagerAdapter(db)


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "FlowManagerAdapter",
    "get_enhanced_flow_engine",
    "get_flow_orchestrator",
]
