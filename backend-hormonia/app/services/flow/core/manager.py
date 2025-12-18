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

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import logging
import re


from app.repositories.flow import FlowStateRepository
from app.repositories.patient import PatientRepository

from ..types import (
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
from ..config import get_flow_config
from .engine import FlowEngine
from .context import FlowContextRepository
from .lifecycle import FlowLifecycleManager
from ..templates import FlowTemplateManager, get_template_manager
from ..validation import FlowValidator
from ..errors import FlowErrorHandler
from ..analytics import FlowEventBroadcaster
from ..integrations import FlowIntegrationManager
from ..integrations.base import FlowIntegration, LegacyIntegrationAdapter

PLACEHOLDER_PATTERN = re.compile(r"{{\s*([\w\.]+)\s*}}")
SQUARE_PLACEHOLDER_PATTERN = re.compile(r"\[([\w\.]+)\]")

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
        db: Any,
        engine: Optional[FlowEngine] = None,
        validator: Optional[FlowValidator] = None,
        template_manager: Optional[FlowTemplateManager] = None,
        integration_manager: Optional[FlowIntegrationManager] = None,
        context_repository: Optional[FlowContextRepository] = None,
        lifecycle: Optional[FlowLifecycleManager] = None,
        event_broadcaster: Optional[FlowEventBroadcaster] = None,
        error_handler: Optional[FlowErrorHandler] = None,
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
        self.validator = validator or FlowValidator()
        self.template_manager = template_manager or get_template_manager()
        self.integration_manager = integration_manager or FlowIntegrationManager()
        self.context_repository = context_repository or FlowContextRepository(db)
        self.lifecycle = lifecycle or FlowLifecycleManager(self.context_repository)
        self.event_broadcaster = event_broadcaster or FlowEventBroadcaster()
        self.error_handler = error_handler or FlowErrorHandler()
        self.flow_repository = FlowStateRepository(db)
        self.patient_repository = PatientRepository(db)

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
        logger.info("Starting flow: type=%s patient=%s", flow_type, patient_id)

        flow_instance_id = uuid4()
        template = await self._load_template(flow_type, template_id)
        if not template:
            raise ValueError(f"Template not found for flow type: {flow_type}")
        template_dict = template.model_dump()

        validation = await self.validator.validate_start(
            patient_id=patient_id,
            flow_type=flow_type,
            template=template_dict,
            context=metadata or {},
        )
        if not validation.is_valid:
            raise ValueError(f"Flow validation failed: {validation.errors}")

        expires_at = datetime.utcnow() + timedelta(
            minutes=template.default_timeout_minutes
        )
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
            expires_at=expires_at,
            metadata=metadata or {},
            priority=priority,
        )
        context.metadata.setdefault("template_id", template.template_id)
        if template.metadata.get("template_version_id"):
            context.metadata.setdefault(
                "template_version_id", template.metadata.get("template_version_id")
            )

        steps = template.steps
        if steps:
            context.current_step_id = steps[0].get("step_id")

        await self.lifecycle.start(context, expires_at)

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

        await self.integration_manager.notify("on_flow_start", context, template_dict)

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

        template = await self._load_template(
            context.flow_type, context.metadata.get("template_id")
        )
        template_dict = template.model_dump()

        current_step_id = context.current_step_id
        if not current_step_id:
            raise ValueError("No current step to execute")

        step_definition = self._find_step_in_template(template_dict, current_step_id)
        if not step_definition:
            raise ValueError(f"Step not found in template: {current_step_id}")

        if user_input:
            context.flow_data["pending_response"] = user_input.get("response")

        step_validation = await self.validator.validate_step_execution(
            context=context,
            step_definition=step_definition,
        )
        if not step_validation.is_valid:
            raise ValueError(f"Step validation failed: {step_validation.errors}")

        validation = await self.validator.validate_transition(
            context=context,
            from_step=current_step_id,
            to_step=None,
            template=template_dict,
        )
        if not validation.is_valid:
            raise ValueError(f"Transition validation failed: {validation.errors}")

        try:
            context, step_result = await self.engine.execute_step(
                context, step_definition
            )

            await self._broadcast_event(
                FlowEvent(
                    event_id=str(uuid4()),
                    event_type=FlowEventType.STEP_COMPLETED,
                    flow_instance_id=flow_instance_id,
                    step_id=current_step_id,
                    data={"output": step_result.output_data},
                )
            )

            await self.integration_manager.notify(
                "on_step_complete", context, template_dict, step_result
            )

        except Exception as e:
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

        next_step_id = self.engine.get_next_step(
            current_step_id, template_dict, context
        )

        context = await self.engine.transition_state(
            context, current_step_id, next_step_id
        )

        await self.context_repository.save(context, template)

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
            await self.integration_manager.notify(
                "on_flow_complete", context, template_dict
            )

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

        await self.lifecycle.pause(context, reason)

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

        await self.lifecycle.resume(context)

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

        await self.lifecycle.cancel(context, reason)

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
    ) -> FlowTemplate:
        """Load flow template from the template manager."""
        if template_id:
            template = self.template_manager.get_template(template_id)
        else:
            template = self.template_manager.get_template_for_flow_type(flow_type)
        if not template:
            raise ValueError(f"Template not found for flow type: {flow_type}")
        return template

    async def _load_context(self, flow_instance_id: UUID) -> Optional[FlowContext]:
        """Load flow context from storage."""
        logger.debug("Loading context for flow: %s", flow_instance_id)
        return await self.context_repository.get(flow_instance_id)

    async def _save_context(
        self, context: FlowContext, template: Optional[FlowTemplate] = None
    ) -> None:
        """Persist flow context."""
        await self.context_repository.save(context, template)

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
        if self.event_broadcaster:
            await self.event_broadcaster.broadcast(event)
        else:
            logger.debug(f"Event: {event.event_type} for flow {event.flow_instance_id}")

    def register_integration(
        self, name_or_plugin: Any, integration: Any = None
    ) -> None:
        """
        Register a new integration plugin or wrap a legacy integration.
        """
        if isinstance(name_or_plugin, FlowIntegration) and integration is None:
            plugin = name_or_plugin
        elif isinstance(integration, FlowIntegration):
            plugin = integration
        else:
            plugin = LegacyIntegrationAdapter(str(name_or_plugin), integration)

        self.integration_manager.register_plugin(plugin)

    def __repr__(self) -> str:
        """String representation."""
        return "<FlowManager(modular=True)>"

    # ========================================================================
    # Backward Compatibility Methods (for Legacy API)
    # ========================================================================

    async def get_flow_status(self, flow_id: UUID) -> Optional[FlowStatus]:
        """
        Get flow status (backward compatibility method).

        This method provides compatibility with legacy code that expects
        get_flow_status() instead of get_flow().status.

        Args:
            flow_id: Flow instance ID

        Returns:
            Flow status or None if flow not found

        Example:
            >>> status = await manager.get_flow_status(flow_id)
            >>> if status == FlowStatus.ACTIVE:
            ...     print("Flow is running")
        """
        context = await self._load_context(flow_id)
        return context.status if context else None

    async def complete_flow(self, flow_id: UUID, **kwargs) -> bool:
        """
        Complete a flow (backward compatibility method).

        This method provides compatibility with legacy code that expects
        complete_flow() instead of update_flow_status().

        Args:
            flow_id: Flow instance ID
            **kwargs: Additional completion data

        Returns:
            True if flow was completed successfully

        Example:
            >>> success = await manager.complete_flow(flow_id)
        """
        try:
            context = await self._load_context(flow_id)
            if not context:
                logger.warning(f"Cannot complete flow {flow_id}: not found")
                return False

            await self.lifecycle.complete(context)

            # Broadcast completion event
            await self._broadcast_event(
                FlowEvent(
                    event_type=FlowEventType.FLOW_COMPLETED,
                    flow_instance_id=flow_id,
                    timestamp=datetime.utcnow(),
                    data=kwargs,
                )
            )

            try:
                template = await self._load_template(
                    context.flow_type, context.metadata.get("template_id")
                )
                template_dict = template.model_dump()
            except Exception:
                template_dict = {"template_id": context.metadata.get("template_id")}

            await self.integration_manager.notify(
                "on_flow_complete", context, template_dict
            )

            logger.info(f"Flow {flow_id} completed successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to complete flow {flow_id}: {e}")
            return False

    async def cancel_flow(self, flow_id: UUID, reason: Optional[str] = None) -> bool:
        """
        Cancel a flow (backward compatibility method).

        This method provides compatibility with legacy code that expects
        cancel_flow() instead of update_flow_status().

        Args:
            flow_id: Flow instance ID
            reason: Cancellation reason

        Returns:
            True if flow was cancelled successfully

        Example:
            >>> success = await manager.cancel_flow(flow_id, "User requested")
        """
        try:
            context = await self._load_context(flow_id)
            if not context:
                logger.warning(f"Cannot cancel flow {flow_id}: not found")
                return False

            await self.lifecycle.cancel(context, reason)

            # Broadcast cancellation event
            await self._broadcast_event(
                FlowEvent(
                    event_type=FlowEventType.FLOW_CANCELLED,
                    flow_instance_id=flow_id,
                    timestamp=datetime.utcnow(),
                    data={"reason": reason} if reason else {},
                )
            )

            logger.info(f"Flow {flow_id} cancelled: {reason or 'no reason given'}")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel flow {flow_id}: {e}")
            return False

    async def get_flow_data(self, flow_id: UUID) -> Dict[str, Any]:
        """
        Get flow data (backward compatibility method).

        This method provides compatibility with legacy code that expects
        get_flow_data() instead of get_flow().data.

        Args:
            flow_id: Flow instance ID

        Returns:
            Flow data dictionary or empty dict if flow not found

        Example:
            >>> data = await manager.get_flow_data(flow_id)
            >>> patient_name = data.get("patient_name")
        """
        context = await self._load_context(flow_id)
        if not context:
            return {}

        return {
            "flow_data": context.flow_data,
            "current_data": context.current_data,
            "variables": context.variables,
            "steps_completed": context.steps_completed,
            "steps_history": context.steps_history,
        }
