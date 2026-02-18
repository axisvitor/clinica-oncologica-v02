"""
Flow Event Broadcaster - Event broadcasting for Flow Services (QW-021).

This module provides event broadcasting capabilities for flow execution,
allowing subscribers to receive real-time notifications of flow events.

Migration Note:
    This consolidates event handling from:
    - enhanced_flow_engine.py (event emissions)
    - flow_engine.py (legacy event handling)
    - Various event listeners scattered across flow services
"""

from __future__ import annotations

# Standard library imports
import asyncio
import logging
from collections import defaultdict
from copy import deepcopy
from typing import Callable, Dict, List, Optional
from uuid import UUID, uuid4

# Local application imports
from ..config import get_flow_config
from ..types import FlowContext, FlowEvent, FlowEventType, FlowStepData
from app.core.executors import get_event_executor


logger = logging.getLogger(__name__)


class FlowEventBroadcaster:
    """
    Broadcaster for flow execution events.

    Manages event subscriptions and broadcasts events to all subscribers.
    Supports both synchronous and asynchronous event handlers.

    Attributes:
        config: Analytics configuration.
        _subscribers: Event type-specific subscribers.
        _wildcard_subscribers: Subscribers to all events.
        _event_queue: Queue of recent events.
        _max_queue_size: Maximum event queue size.
        _executor: Thread pool for async handlers.
        _is_processing: Processing status flag.
    """

    def __init__(self, max_workers: int = 5) -> None:
        """
        Initialize event broadcaster.

        Args:
            max_workers: Maximum worker threads for async event processing.
        """
        self.config = deepcopy(get_flow_config()).analytics

        # Event subscribers
        self._subscribers: Dict[FlowEventType, List[Callable]] = defaultdict(list)
        self._wildcard_subscribers: List[Callable] = []

        # Event queue
        self._event_queue: List[FlowEvent] = []
        self._max_queue_size = self.config.event_queue_size

        # Use centralized executor from app.core.executors
        self._executor = get_event_executor()
        self._is_processing = False

        logger.info("FlowEventBroadcaster initialized")

    # ========================================================================
    # Subscription Management
    # ========================================================================

    def subscribe(
        self,
        event_type: FlowEventType,
        handler: Callable[[FlowEvent], None],
    ) -> str:
        """
        Subscribe to a specific event type.

        Args:
            event_type: Type of event to subscribe to.
            handler: Callback function to handle events.

        Returns:
            Subscription ID (for unsubscribing).
        """
        subscription_id = str(uuid4())

        handler._subscription_id = subscription_id  # type: ignore[attr-defined]
        self._subscribers[event_type].append(handler)

        logger.debug(f"Subscribed to {event_type}: {subscription_id}")
        return subscription_id

    def subscribe_all(self, handler: Callable[[FlowEvent], None]) -> str:
        """
        Subscribe to all event types (wildcard subscription).

        Args:
            handler: Callback function to handle all events.

        Returns:
            Subscription ID (for unsubscribing).
        """
        subscription_id = str(uuid4())

        handler._subscription_id = subscription_id  # type: ignore[attr-defined]
        self._wildcard_subscribers.append(handler)

        logger.debug(f"Subscribed to all events: {subscription_id}")
        return subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from events.

        Args:
            subscription_id: Subscription ID returned from subscribe().

        Returns:
            True if unsubscribed successfully, False otherwise.
        """
        # Check wildcard subscribers
        for handler in self._wildcard_subscribers[:]:
            if getattr(handler, "_subscription_id", None) == subscription_id:
                self._wildcard_subscribers.remove(handler)
                logger.debug(f"Unsubscribed from all events: {subscription_id}")
                return True

        # Check specific event type subscribers
        for event_type, handlers in self._subscribers.items():
            for handler in handlers[:]:
                if getattr(handler, "_subscription_id", None) == subscription_id:
                    handlers.remove(handler)
                    logger.debug(f"Unsubscribed from {event_type}: {subscription_id}")
                    return True

        logger.warning(f"Subscription ID not found: {subscription_id}")
        return False

    def unsubscribe_all(self) -> None:
        """
        Unsubscribe all handlers from all events.

        Warning: This removes all subscriptions. Use with caution.
        """
        self._subscribers.clear()
        self._wildcard_subscribers.clear()
        logger.warning("All event subscriptions have been cleared")

    # ========================================================================
    # Event Broadcasting
    # ========================================================================

    def broadcast(self, event: FlowEvent) -> None:
        """
        Broadcast an event to all subscribers.

        Args:
            event: Event to broadcast.
        """
        if not self.config.enable_event_broadcasting:
            return

        # Add to queue
        self._add_to_queue(event)

        # Notify specific subscribers
        handlers = self._subscribers.get(event.event_type, [])
        for handler in handlers:
            self._execute_handler(handler, event)

        # Notify wildcard subscribers
        for handler in self._wildcard_subscribers:
            self._execute_handler(handler, event)

        logger.debug(
            f"Broadcasted event {event.event_type} for flow {event.flow_instance_id}"
        )

    def broadcast_flow_started(
        self,
        flow_instance_id: UUID,
        context: FlowContext,
    ) -> None:
        """
        Broadcast flow started event.

        Args:
            flow_instance_id: Flow instance ID.
            context: Flow context.
        """
        event = FlowEvent(
            event_id=str(uuid4()),
            event_type=FlowEventType.FLOW_STARTED,
            flow_instance_id=flow_instance_id,
            data={
                "flow_type": context.flow_type.value,
                "patient_id": str(context.patient_id),
                "priority": context.priority.value,
            },
            source="flow_engine",
        )
        self.broadcast(event)

    def broadcast_flow_completed(
        self,
        flow_instance_id: UUID,
        context: FlowContext,
    ) -> None:
        """
        Broadcast flow completed event.

        Args:
            flow_instance_id: Flow instance ID.
            context: Flow context.
        """
        event = FlowEvent(
            event_id=str(uuid4()),
            event_type=FlowEventType.FLOW_COMPLETED,
            flow_instance_id=flow_instance_id,
            data={
                "flow_type": context.flow_type.value,
                "patient_id": str(context.patient_id),
                "duration_seconds": (
                    (context.completed_at - context.started_at).total_seconds()
                    if context.started_at and context.completed_at
                    else None
                ),
                "steps_completed": len(context.steps_completed),
            },
            source="flow_engine",
        )
        self.broadcast(event)

    def broadcast_flow_failed(
        self,
        flow_instance_id: UUID,
        context: FlowContext,
        error: Exception,
    ) -> None:
        """
        Broadcast flow failed event.

        Args:
            flow_instance_id: Flow instance ID.
            context: Flow context.
            error: Error that caused the failure.
        """
        event = FlowEvent(
            event_id=str(uuid4()),
            event_type=FlowEventType.FLOW_FAILED,
            flow_instance_id=flow_instance_id,
            data={
                "flow_type": context.flow_type.value,
                "patient_id": str(context.patient_id),
                "error_type": type(error).__name__,
                "error_message": str(error),
                "steps_completed": len(context.steps_completed),
            },
            source="flow_engine",
        )
        self.broadcast(event)

    def broadcast_step_started(
        self,
        flow_instance_id: UUID,
        step_data: FlowStepData,
    ) -> None:
        """
        Broadcast step started event.

        Args:
            flow_instance_id: Flow instance ID.
            step_data: Step data.
        """
        event = FlowEvent(
            event_id=str(uuid4()),
            event_type=FlowEventType.STEP_STARTED,
            flow_instance_id=flow_instance_id,
            step_id=step_data.step_id,
            data={
                "step_name": step_data.step_name,
                "step_type": step_data.step_type.value,
            },
            source="flow_engine",
        )
        self.broadcast(event)

    def broadcast_step_completed(
        self,
        flow_instance_id: UUID,
        step_data: FlowStepData,
    ) -> None:
        """
        Broadcast step completed event.

        Args:
            flow_instance_id: Flow instance ID.
            step_data: Step data.
        """
        event = FlowEvent(
            event_id=str(uuid4()),
            event_type=FlowEventType.STEP_COMPLETED,
            flow_instance_id=flow_instance_id,
            step_id=step_data.step_id,
            data={
                "step_name": step_data.step_name,
                "step_type": step_data.step_type.value,
                "duration_seconds": (
                    (step_data.completed_at - step_data.started_at).total_seconds()
                    if step_data.started_at and step_data.completed_at
                    else None
                ),
            },
            source="flow_engine",
        )
        self.broadcast(event)

    def broadcast_step_failed(
        self,
        flow_instance_id: UUID,
        step_data: FlowStepData,
        error: Exception,
    ) -> None:
        """
        Broadcast step failed event.

        Args:
            flow_instance_id: Flow instance ID.
            step_data: Step data.
            error: Error that caused the failure.
        """
        event = FlowEvent(
            event_id=str(uuid4()),
            event_type=FlowEventType.STEP_FAILED,
            flow_instance_id=flow_instance_id,
            step_id=step_data.step_id,
            data={
                "step_name": step_data.step_name,
                "step_type": step_data.step_type.value,
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
            source="flow_engine",
        )
        self.broadcast(event)

    # ========================================================================
    # Event Queue Management
    # ========================================================================

    def _add_to_queue(self, event: FlowEvent) -> None:
        """
        Add event to queue.

        Args:
            event: Event to add.
        """
        if len(self._event_queue) >= self._max_queue_size:
            # Remove oldest event
            self._event_queue.pop(0)
            logger.warning("Event queue full, removed oldest event")

        self._event_queue.append(event)

    def get_recent_events(
        self,
        flow_instance_id: Optional[UUID] = None,
        event_type: Optional[FlowEventType] = None,
        limit: int = 100,
    ) -> List[FlowEvent]:
        """
        Get recent events from queue.

        Args:
            flow_instance_id: Optional filter by flow instance ID.
            event_type: Optional filter by event type.
            limit: Maximum number of events to return.

        Returns:
            List of recent events matching filters.
        """
        events = self._event_queue[:]

        # Apply filters
        if flow_instance_id:
            events = [e for e in events if e.flow_instance_id == flow_instance_id]

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        # Return most recent events
        return events[-limit:]

    def clear_event_queue(self) -> None:
        """
        Clear the event queue.

        Warning: This removes all queued events. Use with caution.
        """
        self._event_queue.clear()
        logger.warning("Event queue has been cleared")

    # ========================================================================
    # Internal Methods
    # ========================================================================

    def _execute_handler(self, handler: Callable, event: FlowEvent) -> None:
        """
        Execute event handler.

        Args:
            handler: Handler function to execute.
            event: Event to pass to handler.
        """
        try:
            # Check if handler is async
            if asyncio.iscoroutinefunction(handler):
                # Submit to executor for async execution
                self._executor.submit(self._run_async_handler, handler, event)
                return

            # Execute synchronously
            result = handler(event)
            if asyncio.iscoroutine(result):
                # Handler returned coroutine (e.g., AsyncMock); execute safely
                self._executor.submit(self._run_async_coroutine, result)
        except Exception as e:
            logger.error(
                f"Error executing event handler: {e}",
                exc_info=True,
            )

    def _run_async_handler(
        self,
        handler: Callable,
        event: FlowEvent,
    ) -> None:
        """
        Run async handler in executor.

        Args:
            handler: Async handler function.
            event: Event to pass to handler.
        """
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(handler(event))
            loop.close()
        except Exception as e:
            logger.error(
                f"Error in async event handler: {e}",
                exc_info=True,
            )

    def _run_async_coroutine(self, coroutine) -> None:
        """Run a coroutine returned by a sync handler in a new event loop."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(coroutine)
            loop.close()
        except Exception as e:
            logger.error(
                f"Error in async coroutine handler: {e}",
                exc_info=True,
            )

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def get_subscriber_count(self, event_type: Optional[FlowEventType] = None) -> int:
        """
        Get count of subscribers.

        Args:
            event_type: Optional event type to count subscribers for.

        Returns:
            Number of subscribers.
        """
        if event_type:
            return len(self._subscribers.get(event_type, []))
        else:
            total = len(self._wildcard_subscribers)
            for handlers in self._subscribers.values():
                total += len(handlers)
            return total

    def get_queue_size(self) -> int:
        """
        Get current event queue size.

        Returns:
            Number of events in queue.
        """
        return len(self._event_queue)

    def shutdown(self) -> None:
        """
        Shutdown the event broadcaster.

        Waits for pending async operations to complete.
        """
        logger.info("Shutting down FlowEventBroadcaster")
        self._executor.shutdown(wait=True)
        logger.info("FlowEventBroadcaster shutdown complete")


# ============================================================================
# Exports
# ============================================================================

__all__ = ["FlowEventBroadcaster"]
