"""
Flow Analytics - Main analytics service for Flow Services (QW-021).

This module provides the main analytics service that aggregates metrics collection,
event broadcasting, and health monitoring for the consolidated flow system.

Migration Note:
    This consolidates analytics capabilities from:
    - enhanced_flow_engine.py (metrics and monitoring)
    - flow_engine.py (legacy analytics)
    - Various analytics scattered across flow services
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID
import logging

from ..types import (
    FlowType,
    FlowStatus,
    FlowContext,
    FlowStepData,
    FlowStepStatus,
    FlowEvent,
    FlowEventType,
    FlowMetrics,
)
from ..config import get_flow_config

from .metrics_collector import FlowMetricsCollector
from .event_broadcaster import FlowEventBroadcaster
from .monitor import FlowMonitor, FlowHealthMetrics


logger = logging.getLogger(__name__)


class FlowAnalytics:
    """
    Main analytics service for Flow Services.

    Aggregates metrics collection, event broadcasting, and health monitoring
    into a unified analytics interface.
    """

    def __init__(self):
        """Initialize flow analytics service."""
        self.config = get_flow_config().analytics

        # Initialize sub-components
        self.metrics_collector = FlowMetricsCollector()
        self.event_broadcaster = FlowEventBroadcaster()
        self.monitor = FlowMonitor()

        logger.info("FlowAnalytics initialized")

    # ========================================================================
    # Flow Lifecycle Tracking
    # ========================================================================

    def on_flow_started(self, flow_instance_id: UUID, context: FlowContext) -> None:
        """
        Track flow start event.

        Args:
            flow_instance_id: Flow instance ID.
            context: Flow context.
        """
        # Start metrics tracking
        self.metrics_collector.start_flow_tracking(flow_instance_id)

        # Start health monitoring
        self.monitor.start_monitoring(flow_instance_id)

        # Broadcast event
        self.event_broadcaster.broadcast_flow_started(flow_instance_id, context)

        logger.info(
            f"Flow started: {flow_instance_id} (type: {context.flow_type.value})"
        )

    def on_flow_completed(
        self,
        flow_instance_id: UUID,
        context: FlowContext,
    ) -> None:
        """
        Track flow completion event.

        Args:
            flow_instance_id: Flow instance ID.
            context: Flow context.
        """
        # Record completion metrics
        self.metrics_collector.record_flow_completion(
            flow_instance_id,
            FlowStatus.COMPLETED,
            context,
        )

        # Stop health monitoring
        self.monitor.stop_monitoring(flow_instance_id)

        # Broadcast event
        self.event_broadcaster.broadcast_flow_completed(flow_instance_id, context)

        logger.info(
            f"Flow completed: {flow_instance_id} "
            f"(steps: {len(context.steps_completed)})"
        )

    def on_flow_failed(
        self,
        flow_instance_id: UUID,
        context: FlowContext,
        error: Exception,
    ) -> None:
        """
        Track flow failure event.

        Args:
            flow_instance_id: Flow instance ID.
            context: Flow context.
            error: Error that caused the failure.
        """
        # Record failure metrics
        self.metrics_collector.record_flow_completion(
            flow_instance_id,
            FlowStatus.FAILED,
            context,
        )

        # Record error
        self.metrics_collector.record_flow_error(flow_instance_id, error)
        self.monitor.record_flow_error(flow_instance_id, error)

        # Stop health monitoring
        self.monitor.stop_monitoring(flow_instance_id)

        # Broadcast event
        self.event_broadcaster.broadcast_flow_failed(flow_instance_id, context, error)

        logger.error(
            f"Flow failed: {flow_instance_id} - {type(error).__name__}: {error}"
        )

    def on_flow_paused(self, flow_instance_id: UUID, context: FlowContext) -> None:
        """
        Track flow pause event.

        Args:
            flow_instance_id: Flow instance ID.
            context: Flow context.
        """
        # Broadcast event
        event = FlowEvent(
            event_id=str(UUID),
            event_type=FlowEventType.FLOW_PAUSED,
            flow_instance_id=flow_instance_id,
            data={"flow_type": context.flow_type.value},
            source="flow_analytics",
        )
        self.event_broadcaster.broadcast(event)

        logger.info(f"Flow paused: {flow_instance_id}")

    def on_flow_resumed(self, flow_instance_id: UUID, context: FlowContext) -> None:
        """
        Track flow resume event.

        Args:
            flow_instance_id: Flow instance ID.
            context: Flow context.
        """
        # Broadcast event
        event = FlowEvent(
            event_id=str(UUID),
            event_type=FlowEventType.FLOW_RESUMED,
            flow_instance_id=flow_instance_id,
            data={"flow_type": context.flow_type.value},
            source="flow_analytics",
        )
        self.event_broadcaster.broadcast(event)

        logger.info(f"Flow resumed: {flow_instance_id}")

    def on_flow_cancelled(self, flow_instance_id: UUID, context: FlowContext) -> None:
        """
        Track flow cancellation event.

        Args:
            flow_instance_id: Flow instance ID.
            context: Flow context.
        """
        # Record completion metrics
        self.metrics_collector.record_flow_completion(
            flow_instance_id,
            FlowStatus.CANCELLED,
            context,
        )

        # Stop health monitoring
        self.monitor.stop_monitoring(flow_instance_id)

        # Broadcast event
        event = FlowEvent(
            event_id=str(UUID),
            event_type=FlowEventType.FLOW_CANCELLED,
            flow_instance_id=flow_instance_id,
            data={"flow_type": context.flow_type.value},
            source="flow_analytics",
        )
        self.event_broadcaster.broadcast(event)

        logger.info(f"Flow cancelled: {flow_instance_id}")

    # ========================================================================
    # Step Lifecycle Tracking
    # ========================================================================

    def on_step_started(
        self,
        flow_instance_id: UUID,
        step_data: FlowStepData,
    ) -> None:
        """
        Track step start event.

        Args:
            flow_instance_id: Flow instance ID.
            step_data: Step data.
        """
        # Start metrics tracking
        self.metrics_collector.start_step_tracking(flow_instance_id, step_data.step_id)

        # Broadcast event
        self.event_broadcaster.broadcast_step_started(flow_instance_id, step_data)

        logger.debug(
            f"Step started: {step_data.step_id} in flow {flow_instance_id} "
            f"(type: {step_data.step_type.value})"
        )

    def on_step_completed(
        self,
        flow_instance_id: UUID,
        step_data: FlowStepData,
    ) -> None:
        """
        Track step completion event.

        Args:
            flow_instance_id: Flow instance ID.
            step_data: Step data.
        """
        # Record completion metrics
        self.metrics_collector.record_step_completion(
            flow_instance_id,
            step_data.step_id,
            FlowStepStatus.COMPLETED,
            step_data,
        )

        # Broadcast event
        self.event_broadcaster.broadcast_step_completed(flow_instance_id, step_data)

        logger.debug(f"Step completed: {step_data.step_id} in flow {flow_instance_id}")

    def on_step_failed(
        self,
        flow_instance_id: UUID,
        step_data: FlowStepData,
        error: Exception,
    ) -> None:
        """
        Track step failure event.

        Args:
            flow_instance_id: Flow instance ID.
            step_data: Step data.
            error: Error that caused the failure.
        """
        # Record failure metrics
        self.metrics_collector.record_step_completion(
            flow_instance_id,
            step_data.step_id,
            FlowStepStatus.FAILED,
            step_data,
        )

        # Broadcast event
        self.event_broadcaster.broadcast_step_failed(
            flow_instance_id,
            step_data,
            error,
        )

        logger.warning(
            f"Step failed: {step_data.step_id} in flow {flow_instance_id} - "
            f"{type(error).__name__}: {error}"
        )

    # ========================================================================
    # Error and Retry Tracking
    # ========================================================================

    def on_error(
        self,
        flow_instance_id: UUID,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Track error occurrence.

        Args:
            flow_instance_id: Flow instance ID.
            error: Error that occurred.
            context: Optional error context.
        """
        # Record error metrics
        self.metrics_collector.record_flow_error(flow_instance_id, error)
        self.monitor.record_flow_error(flow_instance_id, error)

        # Broadcast event
        event = FlowEvent(
            event_id=str(UUID),
            event_type=FlowEventType.ERROR_OCCURRED,
            flow_instance_id=flow_instance_id,
            data={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context or {},
            },
            source="flow_analytics",
        )
        self.event_broadcaster.broadcast(event)

        logger.error(
            f"Error in flow {flow_instance_id}: {type(error).__name__}: {error}"
        )

    def on_retry(
        self,
        flow_instance_id: UUID,
        retry_count: int,
        reason: str,
    ) -> None:
        """
        Track retry attempt.

        Args:
            flow_instance_id: Flow instance ID.
            retry_count: Current retry count.
            reason: Reason for retry.
        """
        # Record retry metrics
        self.metrics_collector.record_flow_retry(flow_instance_id)
        self.monitor.record_flow_retry(flow_instance_id)

        logger.info(
            f"Flow retry: {flow_instance_id} (attempt #{retry_count}) - {reason}"
        )

    # ========================================================================
    # Health Monitoring
    # ========================================================================

    def check_flow_health(
        self,
        flow_instance_id: UUID,
        context: FlowContext,
    ) -> FlowHealthMetrics:
        """
        Check health of a specific flow.

        Args:
            flow_instance_id: Flow instance ID.
            context: Flow context.

        Returns:
            FlowHealthMetrics with current health status.
        """
        return self.monitor.check_flow_health(flow_instance_id, context)

    def get_system_health(self) -> Dict[str, Any]:
        """
        Get overall system health.

        Returns:
            Dictionary with system health information.
        """
        return self.monitor.check_system_health()

    def get_unhealthy_flows(self) -> List[FlowHealthMetrics]:
        """
        Get list of unhealthy flows.

        Returns:
            List of FlowHealthMetrics for unhealthy flows.
        """
        return self.monitor.get_unhealthy_flows()

    # ========================================================================
    # Metrics Query
    # ========================================================================

    def get_flow_metrics(self, flow_instance_id: UUID) -> Optional[FlowMetrics]:
        """
        Get metrics for a specific flow.

        Args:
            flow_instance_id: Flow instance ID.

        Returns:
            FlowMetrics if available, None otherwise.
        """
        return self.metrics_collector.get_flow_metrics(flow_instance_id)

    def get_aggregate_metrics(self) -> Dict[str, Any]:
        """
        Get aggregate metrics for all flows.

        Returns:
            Dictionary with aggregate metrics.
        """
        return self.metrics_collector.get_aggregate_metrics()

    def get_metrics_by_flow_type(self, flow_type: FlowType) -> Dict[str, Any]:
        """
        Get metrics aggregated by flow type.

        Args:
            flow_type: Type of flow to get metrics for.

        Returns:
            Dictionary with metrics for this flow type.
        """
        return self.metrics_collector.get_metrics_by_flow_type(flow_type)

    # ========================================================================
    # Event Subscription
    # ========================================================================

    def subscribe_to_events(
        self,
        event_type: FlowEventType,
        handler: Any,
    ) -> str:
        """
        Subscribe to flow events.

        Args:
            event_type: Type of event to subscribe to.
            handler: Callback function to handle events.

        Returns:
            Subscription ID (for unsubscribing).
        """
        return self.event_broadcaster.subscribe(event_type, handler)

    def subscribe_to_all_events(self, handler: Any) -> str:
        """
        Subscribe to all flow events.

        Args:
            handler: Callback function to handle all events.

        Returns:
            Subscription ID (for unsubscribing).
        """
        return self.event_broadcaster.subscribe_all(handler)

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from events.

        Args:
            subscription_id: Subscription ID returned from subscribe().

        Returns:
            True if unsubscribed successfully, False otherwise.
        """
        return self.event_broadcaster.unsubscribe(subscription_id)

    def get_recent_events(
        self,
        flow_instance_id: Optional[UUID] = None,
        event_type: Optional[FlowEventType] = None,
        limit: int = 100,
    ) -> List[FlowEvent]:
        """
        Get recent events.

        Args:
            flow_instance_id: Optional filter by flow instance ID.
            event_type: Optional filter by event type.
            limit: Maximum number of events to return.

        Returns:
            List of recent events matching filters.
        """
        return self.event_broadcaster.get_recent_events(
            flow_instance_id,
            event_type,
            limit,
        )

    # ========================================================================
    # Dashboard and Reporting
    # ========================================================================

    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data.

        Returns:
            Dictionary with dashboard data including metrics, health, and events.
        """
        return {
            "system_health": self.get_system_health(),
            "aggregate_metrics": self.get_aggregate_metrics(),
            "unhealthy_flows": [
                {
                    "flow_instance_id": str(m.flow_instance_id),
                    "status": m.status.value,
                    "issues": m.issues,
                }
                for m in self.get_unhealthy_flows()
            ],
            "recent_events": [
                {
                    "event_type": e.event_type.value,
                    "flow_instance_id": str(e.flow_instance_id),
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in self.get_recent_events(limit=10)
            ],
            "generated_at": datetime.utcnow().isoformat(),
        }

    def export_analytics_report(self) -> Dict[str, Any]:
        """
        Export complete analytics report.

        Returns:
            Dictionary with complete analytics data.
        """
        return {
            "metrics": self.metrics_collector.export_metrics(),
            "health": self.monitor.export_health_report(),
            "events": {
                "queue_size": self.event_broadcaster.get_queue_size(),
                "subscriber_count": self.event_broadcaster.get_subscriber_count(),
            },
            "generated_at": datetime.utcnow().isoformat(),
        }

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def reset_analytics(self) -> None:
        """
        Reset all analytics data.

        Warning: This clears all metrics, health data, and events. Use with caution.
        """
        self.metrics_collector.reset_metrics()
        self.monitor.reset_metrics()
        self.event_broadcaster.clear_event_queue()

        logger.warning("All analytics data has been reset")

    def shutdown(self) -> None:
        """
        Shutdown the analytics service.

        Cleans up resources and waits for pending operations to complete.
        """
        logger.info("Shutting down FlowAnalytics")

        # Shutdown event broadcaster (waits for async operations)
        self.event_broadcaster.shutdown()

        # Clean up old metrics
        self.monitor.cleanup_old_metrics()

        logger.info("FlowAnalytics shutdown complete")


# ============================================================================
# Singleton Instance
# ============================================================================

_flow_analytics_instance: Optional[FlowAnalytics] = None


def get_flow_analytics() -> FlowAnalytics:
    """
    Get global flow analytics instance.

    Returns:
        Global FlowAnalytics instance (singleton).
    """
    global _flow_analytics_instance
    if _flow_analytics_instance is None:
        _flow_analytics_instance = FlowAnalytics()
    return _flow_analytics_instance


def reset_flow_analytics() -> None:
    """
    Reset global flow analytics instance.

    Useful for testing.
    """
    global _flow_analytics_instance
    if _flow_analytics_instance:
        _flow_analytics_instance.shutdown()
    _flow_analytics_instance = None


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "FlowAnalytics",
    "get_flow_analytics",
    "reset_flow_analytics",
]
