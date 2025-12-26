"""
Flow Metrics Collector - Metrics collection for Flow Services (QW-021).

This module provides metrics collection and aggregation for flow execution,
including timing, success rates, error tracking, and performance metrics.

Migration Note:
    This consolidates metrics collection from:
    - enhanced_flow_engine.py (execution metrics)
    - flow_engine.py (legacy metrics)
    - Various monitoring scattered across flow services
"""

from __future__ import annotations

# Standard library imports
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID

# Local application imports
from ..config import get_flow_config
from ..types import (
    FlowContext,
    FlowMetrics,
    FlowStatus,
    FlowStepData,
    FlowStepStatus,
    FlowType,
)


logger = logging.getLogger(__name__)


class FlowMetricsCollector:
    """
    Collector for flow execution metrics.

    Tracks and aggregates metrics for flow instances, steps, and overall
    system performance with in-memory storage.

    Attributes:
        config: Analytics configuration.
        _flow_metrics: Storage for flow-level metrics.
        _step_metrics: Storage for step-level metrics.
        _aggregate_metrics: Aggregated system metrics.
        _flow_start_times: Flow execution start times.
        _step_start_times: Step execution start times.
    """

    def __init__(self) -> None:
        """Initialize metrics collector."""
        self.config = get_flow_config().analytics

        # Metrics storage (in-memory, should use Redis/DB in production)
        self._flow_metrics: Dict[UUID, FlowMetrics] = {}
        self._step_metrics: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._aggregate_metrics: Dict[str, Any] = defaultdict(int)

        # Timing trackers
        self._flow_start_times: Dict[UUID, datetime] = {}
        self._step_start_times: Dict[str, datetime] = {}

        logger.info("FlowMetricsCollector initialized")

    # ========================================================================
    # Flow Metrics
    # ========================================================================

    def start_flow_tracking(self, flow_instance_id: UUID) -> None:
        """
        Start tracking metrics for a flow instance.

        Args:
            flow_instance_id: Flow instance ID to track.
        """
        if not self.config.enable_metrics:
            return

        self._flow_start_times[flow_instance_id] = datetime.now(timezone.utc)
        self._flow_metrics[flow_instance_id] = FlowMetrics()

        logger.debug(f"Started tracking flow {flow_instance_id}")

    def record_flow_completion(
        self,
        flow_instance_id: UUID,
        status: FlowStatus,
        context: Optional[FlowContext] = None,
    ) -> None:
        """
        Record flow completion metrics.

        Args:
            flow_instance_id: Flow instance ID.
            status: Final flow status.
            context: Optional flow context for additional metrics.
        """
        if not self.config.enable_metrics:
            return

        # Calculate duration
        start_time = self._flow_start_times.get(flow_instance_id)
        if start_time:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            metrics = self._flow_metrics.get(flow_instance_id, FlowMetrics())
            metrics.duration_seconds = duration

            # Update from context if available
            if context:
                metrics.total_steps = len(context.steps_history)
                metrics.completed_steps = sum(
                    1
                    for step in context.steps_history
                    if step.status == FlowStepStatus.COMPLETED
                )
                metrics.failed_steps = sum(
                    1
                    for step in context.steps_history
                    if step.status == FlowStepStatus.FAILED
                )
                metrics.skipped_steps = sum(
                    1
                    for step in context.steps_history
                    if step.status == FlowStepStatus.SKIPPED
                )

                # Calculate average step duration
                step_durations = []
                for step in context.steps_history:
                    if step.started_at and step.completed_at:
                        step_duration = (
                            step.completed_at - step.started_at
                        ).total_seconds()
                        step_durations.append(step_duration)

                if step_durations:
                    metrics.average_step_duration_seconds = sum(step_durations) / len(
                        step_durations
                    )

            self._flow_metrics[flow_instance_id] = metrics

            # Update aggregate metrics
            self._update_aggregate_metrics(status, duration)

            logger.debug(
                f"Recorded completion for flow {flow_instance_id}: "
                f"status={status}, duration={duration:.2f}s"
            )

    def record_flow_error(self, flow_instance_id: UUID, error: Exception) -> None:
        """
        Record flow error.

        Args:
            flow_instance_id: Flow instance ID.
            error: Error that occurred.
        """
        if not self.config.enable_metrics:
            return

        metrics = self._flow_metrics.get(flow_instance_id, FlowMetrics())
        metrics.error_count += 1

        self._flow_metrics[flow_instance_id] = metrics
        self._aggregate_metrics["total_errors"] += 1

        logger.debug(
            f"Recorded error for flow {flow_instance_id}: {type(error).__name__}"
        )

    def record_flow_retry(self, flow_instance_id: UUID) -> None:
        """
        Record flow retry attempt.

        Args:
            flow_instance_id: Flow instance ID.
        """
        if not self.config.enable_metrics:
            return

        metrics = self._flow_metrics.get(flow_instance_id, FlowMetrics())
        metrics.retry_count += 1

        self._flow_metrics[flow_instance_id] = metrics
        self._aggregate_metrics["total_retries"] += 1

        logger.debug(f"Recorded retry for flow {flow_instance_id}")

    # ========================================================================
    # Step Metrics
    # ========================================================================

    def start_step_tracking(self, flow_instance_id: UUID, step_id: str) -> None:
        """
        Start tracking metrics for a step.

        Args:
            flow_instance_id: Flow instance ID.
            step_id: Step ID to track.
        """
        if not self.config.enable_metrics:
            return

        tracking_key = f"{flow_instance_id}:{step_id}"
        self._step_start_times[tracking_key] = datetime.now(timezone.utc)

        logger.debug(f"Started tracking step {step_id} in flow {flow_instance_id}")

    def record_step_completion(
        self,
        flow_instance_id: UUID,
        step_id: str,
        status: FlowStepStatus,
        step_data: Optional[FlowStepData] = None,
    ) -> None:
        """
        Record step completion metrics.

        Args:
            flow_instance_id: Flow instance ID.
            step_id: Step ID.
            status: Step status.
            step_data: Optional step data for additional metrics.
        """
        if not self.config.enable_metrics:
            return

        tracking_key = f"{flow_instance_id}:{step_id}"
        start_time = self._step_start_times.get(tracking_key)

        if start_time:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            # Store step metrics
            self._step_metrics[tracking_key] = {
                "flow_instance_id": flow_instance_id,
                "step_id": step_id,
                "status": status.value,
                "duration_seconds": duration,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }

            # Update aggregate metrics
            self._aggregate_metrics["total_steps_executed"] += 1
            if status == FlowStepStatus.COMPLETED:
                self._aggregate_metrics["total_steps_succeeded"] += 1
            elif status == FlowStepStatus.FAILED:
                self._aggregate_metrics["total_steps_failed"] += 1

            logger.debug(
                f"Recorded step completion {step_id} in flow {flow_instance_id}: "
                f"status={status}, duration={duration:.2f}s"
            )

    # ========================================================================
    # Query Methods
    # ========================================================================

    def get_flow_metrics(self, flow_instance_id: UUID) -> Optional[FlowMetrics]:
        """
        Get metrics for a specific flow instance.

        Args:
            flow_instance_id: Flow instance ID.

        Returns:
            FlowMetrics if available, None otherwise.
        """
        return self._flow_metrics.get(flow_instance_id)

    def get_aggregate_metrics(self) -> Dict[str, Any]:
        """
        Get aggregate metrics for all flows.

        Returns:
            Dictionary with aggregate metrics.
        """
        # Calculate success rate
        total_flows = self._aggregate_metrics.get(
            "total_flows_completed", 0
        ) + self._aggregate_metrics.get("total_flows_failed", 0)
        success_rate = 0.0
        if total_flows > 0:
            success_rate = (
                self._aggregate_metrics.get("total_flows_completed", 0) / total_flows
            ) * 100

        return {
            "total_flows_started": self._aggregate_metrics.get(
                "total_flows_started", 0
            ),
            "total_flows_completed": self._aggregate_metrics.get(
                "total_flows_completed", 0
            ),
            "total_flows_failed": self._aggregate_metrics.get("total_flows_failed", 0),
            "total_steps_executed": self._aggregate_metrics.get(
                "total_steps_executed", 0
            ),
            "total_steps_succeeded": self._aggregate_metrics.get(
                "total_steps_succeeded", 0
            ),
            "total_steps_failed": self._aggregate_metrics.get("total_steps_failed", 0),
            "total_errors": self._aggregate_metrics.get("total_errors", 0),
            "total_retries": self._aggregate_metrics.get("total_retries", 0),
            "success_rate_percentage": round(success_rate, 2),
            "average_flow_duration_seconds": self._aggregate_metrics.get(
                "average_flow_duration_seconds", 0.0
            ),
        }

    def get_metrics_by_flow_type(self, flow_type: FlowType) -> Dict[str, Any]:
        """
        Get metrics aggregated by flow type.

        Args:
            flow_type: Type of flow to get metrics for.

        Returns:
            Dictionary with metrics for this flow type.
        """
        # This is a placeholder - would need to track flow types
        # in the metrics collection
        return {
            "flow_type": flow_type.value,
            "total_executions": 0,
            "average_duration_seconds": 0.0,
            "success_rate_percentage": 0.0,
        }

    def get_recent_metrics(self, minutes: int = 60) -> Dict[str, Any]:
        """
        Get metrics for recent time window.

        Args:
            minutes: Time window in minutes.

        Returns:
            Dictionary with recent metrics.
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)

        # Filter recent flows
        recent_flows = {
            flow_id: metrics
            for flow_id, metrics in self._flow_metrics.items()
            if self._flow_start_times.get(flow_id, datetime.min) >= cutoff_time
        }

        return {
            "time_window_minutes": minutes,
            "flows_in_window": len(recent_flows),
            "cutoff_time": cutoff_time.isoformat(),
        }

    # ========================================================================
    # Internal Methods
    # ========================================================================

    def _update_aggregate_metrics(self, status: FlowStatus, duration: float) -> None:
        """
        Update aggregate metrics after flow completion.

        Args:
            status: Flow completion status.
            duration: Flow execution duration in seconds.
        """
        self._aggregate_metrics["total_flows_started"] += 1

        if status == FlowStatus.COMPLETED:
            self._aggregate_metrics["total_flows_completed"] += 1
        elif status == FlowStatus.FAILED:
            self._aggregate_metrics["total_flows_failed"] += 1

        # Update average duration (simple moving average)
        current_avg = self._aggregate_metrics.get("average_flow_duration_seconds", 0.0)
        total_completed = self._aggregate_metrics.get("total_flows_completed", 1)

        new_avg = ((current_avg * (total_completed - 1)) + duration) / total_completed
        self._aggregate_metrics["average_flow_duration_seconds"] = new_avg

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def reset_metrics(self) -> None:
        """
        Reset all collected metrics.

        Warning: This clears all metrics data. Use with caution.
        """
        self._flow_metrics.clear()
        self._step_metrics.clear()
        self._aggregate_metrics.clear()
        self._flow_start_times.clear()
        self._step_start_times.clear()

        logger.warning("All flow metrics have been reset")

    def export_metrics(self) -> Dict[str, Any]:
        """
        Export all metrics for persistence or analysis.

        Returns:
            Dictionary with all collected metrics.
        """
        return {
            "aggregate": self.get_aggregate_metrics(),
            "flow_metrics": {
                str(flow_id): metrics.model_dump()
                for flow_id, metrics in self._flow_metrics.items()
            },
            "step_metrics": dict(self._step_metrics),
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }


# ============================================================================
# Exports
# ============================================================================

__all__ = ["FlowMetricsCollector"]
