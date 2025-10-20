"""
Flow Manager - Main orchestrator for Flow Services (QW-021).

This module implements the FlowManager class, which serves as the main
entry point for flow operations. It coordinates the execution engine,
validators, event system, and integrations.

The manager is stateful and handles:
- Flow lifecycle (start, pause, resume, stop)
- State persistence
- Error handling and recovery
- Integration coordination
- Event broadcasting

Migration Note:
    This consolidates orchestration logic from:
    - orchestrators/flow_orchestrator.py (main orchestrator)
    - flow.py (FlowEngineIntegrationService)
    - flow_management.py (management layer)
    - enhanced_flow_engine.py (enhanced features)
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import logging

from sqlalchemy.orm import Session

from .types import (
    FlowContext,
    FlowTemplate,
    FlowType,
    FlowStatus,
    FlowPriority,
    FlowStepData,
    FlowEvent,
    FlowEventType,
    FlowMetrics,
)
from .config import get_flow_config
from .core.engine import FlowEngine

logger = logging.getLogger(__name__)


class FlowManager:
    """
    Main flow orchestrator.

    Coordinates all flow operations including execution, validation,
    monitoring, and integration with other systems.

    This is the primary interface for flow operations - all external
    code should interact with flows through this manager.

    Example:
        >>> manager = FlowManager(db)
        >>> flow_id = await manager.start_flow(
        ...     patient_id=patient_id,
        ...     flow_type=FlowType.DAILY_CHECKIN
        ... )
        >>> await manager.advance_flow(flow_id)
        >>> await manager.pause_flow(flow_id)
        >>> await manager.resume_flow(flow_id)
    """

    def __init__(
        self,
        db: Session,
        engine: Optional[FlowEngine] = None,
    ):
        """
        Initialize the flow manager.

        Args:
            db: Database session for persistence
            engine: Optional FlowEngine instance (for dependency injection)
        """
        self.db = db
        self.config = get_flow_config()
        self.engine = engine or FlowEngine()

        # Lazy-loaded components
        self._validator = None
        self._event_broadcaster = None
        self._integrations = {}

        logger.info("FlowManager initialized")

    async def start_flow(
        self,
        patient_id: UUID,
        flow_type: FlowType,
        template_id: Optional[str] = None,
        initial_data: Optional[Dict[str, Any]] = None,
        priority: FlowPriority = FlowPriority.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        """
        Start a new flow instance.

        Args:
            patient_id: Patient ID this flow is for
            flow_type: Type of flow to start
            template_id: Optional specific template ID to use
            initial_data: Optional initial flow data
            priority: Execution priority
            metadata: Optional flow metadata

        Returns:
            Flow instance ID

        Raises:
            ValueError: If validation fails
            RuntimeError: If flow cannot be started

        Example:
            >>> flow_id = await manager.start_flow(
            ...     patient_id=uuid4(),
            ...     flow_type=FlowType.DAILY_CHECKIN,
            ...     initial_data={"checkin_count": 0}
            ... )
        """
        logger.info(f"Starting flow: type={flow_type}, patient={patient_id}")

        # Generate flow instance ID
        flow_instance_id = uuid4()

        # Load template
        template = await self._load_template(flow_type, template_id)
        if not template:
            raise ValueError(f"Template not found for flow type: {flow_type}")

        # Validate flow can start
        if self._validator:
            validation = await self._validator.validate_start(
                patient_id=patient_id,
                flow_type=flow_type,
                template=template,
            )
            if not validation.is_valid:
                raise ValueError(f"Flow validation failed: {validation.errors}")

        # Create flow context
        context = FlowContext(
            flow_instance_id=flow_instance_id,
            flow_type=flow_type,
            patient_id=patient_id,
            status=FlowStatus.ACTIVE,
            flow_data=initial_data or {},
            variables={},
            steps_completed=[],
            steps_history=[],
            started_at=datetime.utcnow(),
            expires_at=datetime.utcnow()
            + timedelta(minutes=template.get("default_timeout_minutes", 60)),
            metadata=metadata or {},
            priority=priority,
        )

        # Get first step
        steps = template.get("steps", [])
        if steps:
            context.current_step_id = steps[0].get("step_id")

        # Persist context
        await self._save_context(context)

        # Broadcast event
        await self._broadcast_event(
            FlowEvent(
                event_id=str(uuid4()),
                event_type=FlowEventType.FLOW_STARTED,
                flow_instance_id=flow_instance_id,
                data={
                    "flow_type": flow_type.value,
                    "patient_id": str(patient_id),
                    "priority": priority.value,
                },
            )
        )

        # Notify integrations
        await self._notify_integrations("on_flow_start", context, template)

        logger.info(f"Flow started: {flow_instance_id}")
        return flow_instance_id

    async def advance_flow(
        self,
        flow_instance_id: UUID,
        user_input: Optional[Dict[str, Any]] = None,
    ) -> FlowStepData:
        """
        Advance flow to next step.

        Executes the current step and transitions to the next step.

        Args:
            flow_instance_id: Flow instance ID
            user_input: Optional user input (for question steps)

        Returns:
            Result of executed step

        Raises:
            ValueError: If flow not found or invalid state
            RuntimeError: If step execution fails

        Example:
            >>> result = await manager.advance_flow(
            ...     flow_id,
            ...     user_input={"response": "I'm feeling good"}
            ... )
        """
        logger.info(f"Advancing flow: {flow_instance_id}")

        # Load context
        context = await self._load_context(flow_instance_id)
        if not context:
            raise ValueError(f"Flow not found: {flow_instance_id}")

        if context.status != FlowStatus.ACTIVE:
            raise ValueError(f"Flow is not active: {context.status}")

        # Load template
        template = await self._load_template(context.flow_type)

        # Get current step definition
        current_step_id = context.current_step_id
        if not current_step_id:
            raise ValueError("No current step to execute")

        step_definition = self._find_step_in_template(template, current_step_id)
        if not step_definition:
            raise ValueError(f"Step not found in template: {current_step_id}")

        # Add user input to context if provided
        if user_input:
            context.flow_data["pending_response"] = user_input.get("response")

        # Validate transition
        if self._validator:
            validation = await self._validator.validate_transition(
                context=context,
                from_step=current_step_id,
                to_step=None,  # Will be determined
            )
            if not validation.is_valid:
                raise ValueError(f"Transition validation failed: {validation.errors}")

        # Execute step
        try:
            context, step_result = await self.engine.execute_step(
                context, step_definition
            )

            # Broadcast step completed event
            await self._broadcast_event(
                FlowEvent(
                    event_id=str(uuid4()),
                    event_type=FlowEventType.STEP_COMPLETED,
                    flow_instance_id=flow_instance_id,
                    step_id=current_step_id,
                    data={"output": step_result.output_data},
                )
            )

            # Notify integrations
            await self._notify_integrations(
                "on_step_complete", context, template, step_result
            )

        except Exception as e:
            # Broadcast step failed event
            await self._broadcast_event(
                FlowEvent(
                    event_id=str(uuid4()),
                    event_type=FlowEventType.STEP_FAILED,
                    flow_instance_id=flow_instance_id,
                    step_id=current_step_id,
                    data={"error": str(e)},
                )
            )
            raise

        # Determine next step
        next_step_id = self.engine.get_next_step(current_step_id, template, context)

        # Transition to next step
        context = await self.engine.transition_state(
            context, current_step_id, next_step_id
        )

        # Persist updated context
        await self._save_context(context)

        # Broadcast transition event
        await self._broadcast_event(
            FlowEvent(
                event_id=str(uuid4()),
                event_type=FlowEventType.TRANSITION_OCCURRED,
                flow_instance_id=flow_instance_id,
                data={"from": current_step_id, "to": next_step_id},
            )
        )

        # If flow completed, notify
        if context.status == FlowStatus.COMPLETED:
            await self._broadcast_event(
                FlowEvent(
                    event_id=str(uuid4()),
                    event_type=FlowEventType.FLOW_COMPLETED,
                    flow_instance_id=flow_instance_id,
                    data={},
                )
            )
            await self._notify_integrations("on_flow_complete", context, template)

        logger.info(f"Flow advanced: {flow_instance_id}, next_step={next_step_id}")
        return step_result

    async def pause_flow(
        self, flow_instance_id: UUID, reason: Optional[str] = None
    ) -> None:
        """
        Pause flow execution.

        Args:
            flow_instance_id: Flow instance ID
            reason: Optional reason for pausing

        Example:
            >>> await manager.pause_flow(flow_id, reason="User requested")
        """
        logger.info(f"Pausing flow: {flow_instance_id}")

        context = await self._load_context(flow_instance_id)
        if not context:
            raise ValueError(f"Flow not found: {flow_instance_id}")

        if context.status != FlowStatus.ACTIVE:
            raise ValueError(f"Flow is not active: {context.status}")

        context.status = FlowStatus.PAUSED
        context.metadata["paused_at"] = datetime.utcnow().isoformat()
        context.metadata["pause_reason"] = reason or "manual"

        await self._save_context(context)

        await self._broadcast_event(
            FlowEvent(
                event_id=str(uuid4()),
                event_type=FlowEventType.FLOW_PAUSED,
                flow_instance_id=flow_instance_id,
                data={"reason": reason},
            )
        )

        logger.info(f"Flow paused: {flow_instance_id}")

    async def resume_flow(self, flow_instance_id: UUID) -> None:
        """
        Resume paused flow execution.

        Args:
            flow_instance_id: Flow instance ID

        Example:
            >>> await manager.resume_flow(flow_id)
        """
        logger.info(f"Resuming flow: {flow_instance_id}")

        context = await self._load_context(flow_instance_id)
        if not context:
            raise ValueError(f"Flow not found: {flow_instance_id}")

        if context.status != FlowStatus.PAUSED:
            raise ValueError(f"Flow is not paused: {context.status}")

        context.status = FlowStatus.ACTIVE
        context.metadata["resumed_at"] = datetime.utcnow().isoformat()

        await self._save_context(context)

        await self._broadcast_event(
            FlowEvent(
                event_id=str(uuid4()),
                event_type=FlowEventType.FLOW_RESUMED,
                flow_instance_id=flow_instance_id,
                data={},
            )
        )

        logger.info(f"Flow resumed: {flow_instance_id}")

    async def stop_flow(
        self, flow_instance_id: UUID, reason: str = "manual", force: bool = False
    ) -> None:
        """
        Stop flow execution.

        Args:
            flow_instance_id: Flow instance ID
            reason: Reason for stopping
            force: Force stop even if in invalid state

        Example:
            >>> await manager.stop_flow(flow_id, reason="Error occurred")
        """
        logger.info(f"Stopping flow: {flow_instance_id}, reason={reason}")

        context = await self._load_context(flow_instance_id)
        if not context:
            raise ValueError(f"Flow not found: {flow_instance_id}")

        if not force and context.status in [FlowStatus.COMPLETED, FlowStatus.CANCELLED]:
            raise ValueError(f"Flow already stopped: {context.status}")

        context.status = FlowStatus.CANCELLED
        context.completed_at = datetime.utcnow()
        context.metadata["stopped_at"] = datetime.utcnow().isoformat()
        context.metadata["stop_reason"] = reason

        await self._save_context(context)

        await self._broadcast_event(
            FlowEvent(
                event_id=str(uuid4()),
                event_type=FlowEventType.FLOW_CANCELLED,
                flow_instance_id=flow_instance_id,
                data={"reason": reason},
            )
        )

        logger.info(f"Flow stopped: {flow_instance_id}")

    async def get_flow_state(self, flow_instance_id: UUID) -> Optional[FlowContext]:
        """
        Get current flow state.

        Args:
            flow_instance_id: Flow instance ID

        Returns:
            Flow context, or None if not found

        Example:
            >>> context = await manager.get_flow_state(flow_id)
            >>> print(context.status, context.current_step_id)
        """
        return await self._load_context(flow_instance_id)

    async def get_flow_metrics(self, flow_instance_id: UUID) -> Optional[FlowMetrics]:
        """
        Get flow execution metrics.

        Args:
            flow_instance_id: Flow instance ID

        Returns:
            Flow metrics, or None if flow not found
        """
        context = await self._load_context(flow_instance_id)
        if not context:
            return None

        completed_steps = len(
            [s for s in context.steps_history if s.status.value == "completed"]
        )
        failed_steps = len(
            [s for s in context.steps_history if s.status.value == "failed"]
        )
        skipped_steps = len(
            [s for s in context.steps_history if s.status.value == "skipped"]
        )

        duration = None
        if context.started_at and context.completed_at:
            duration = (context.completed_at - context.started_at).total_seconds()

        avg_step_duration = None
        if completed_steps > 0:
            total_step_time = sum(
                (s.completed_at - s.started_at).total_seconds()
                for s in context.steps_history
                if s.started_at and s.completed_at
            )
            avg_step_duration = total_step_time / completed_steps

        return FlowMetrics(
            total_steps=len(context.steps_history),
            completed_steps=completed_steps,
            failed_steps=failed_steps,
            skipped_steps=skipped_steps,
            duration_seconds=duration,
            average_step_duration_seconds=avg_step_duration,
            retry_count=context.metadata.get("retry_count", 0),
            error_count=failed_steps,
        )

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    async def _load_template(
        self, flow_type: FlowType, template_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Load flow template from storage."""
        # In production, this would load from database/cache
        # For now, return a basic template structure
        return {
            "template_id": template_id or f"{flow_type.value}_v1",
            "flow_type": flow_type.value,
            "steps": [],
            "transitions": [],
            "default_timeout_minutes": 60,
        }

    async def _load_context(self, flow_instance_id: UUID) -> Optional[FlowContext]:
        """Load flow context from storage."""
        # In production, this would query database
        # For now, return None (will be implemented with repository)
        logger.debug(f"Loading context for flow: {flow_instance_id}")
        return None

    async def _save_context(self, context: FlowContext) -> None:
        """Save flow context to storage."""
        # In production, this would persist to database
        # For now, just log
        logger.debug(f"Saving context for flow: {context.flow_instance_id}")

    def _find_step_in_template(
        self, template: Dict[str, Any], step_id: str
    ) -> Optional[Dict[str, Any]]:
        """Find step definition in template."""
        steps = template.get("steps", [])
        for step in steps:
            if step.get("step_id") == step_id:
                return step
        return None

    async def _broadcast_event(self, event: FlowEvent) -> None:
        """Broadcast flow event."""
        if self._event_broadcaster:
            await self._event_broadcaster.broadcast(event)
        else:
            logger.debug(f"Event: {event.event_type} for flow {event.flow_instance_id}")

    async def _notify_integrations(
        self, method: str, context: FlowContext, template: Dict[str, Any], *args
    ) -> None:
        """Notify registered integrations."""
        for integration in self._integrations.values():
            if hasattr(integration, method):
                try:
                    await getattr(integration)(context, template, *args)
                except Exception as e:
                    logger.error(f"Integration {method} failed: {e}")

    def register_integration(self, name: str, integration: Any) -> None:
        """
        Register an integration (quiz, AI, etc.).

        Args:
            name: Integration name
            integration: Integration instance

        Example:
            >>> manager.register_integration("quiz", QuizFlowIntegration())
        """
        self._integrations[name] = integration
        logger.info(f"Integration registered: {name}")

    def __repr__(self) -> str:
        """String representation."""
        return f"<FlowManager(engine={self.engine}, integrations={len(self._integrations)})>"
