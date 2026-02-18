"""
Flow Monitor - Health monitoring for Flow Services (QW-021).

This module provides health monitoring and alerting for flow execution,
tracking flow health, detecting issues, and triggering alerts when needed.

Migration Note:
    This consolidates monitoring from:
    - enhanced_flow_engine.py (health checks)
    - flow_engine.py (legacy monitoring)
    - Various health checks scattered across flow services
"""

from __future__ import annotations

# Standard library imports
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from copy import deepcopy
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

# Local application imports
from ..config import get_flow_config
from ..types import FlowContext, FlowPriority, FlowStatus
from app.utils.timezone import normalize_datetime_naive_sao_paulo, now_sao_paulo_naive


logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """
    Health status levels for flow monitoring.

    Attributes:
        HEALTHY: System is operating normally.
        DEGRADED: System is experiencing minor issues.
        UNHEALTHY: System has significant issues.
        CRITICAL: System is in critical state.
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


class FlowHealthMetrics:
    """
    Health metrics for a flow instance.

    Tracks health status, performance metrics, and issues for
    individual flow instances.

    Attributes:
        flow_instance_id: Flow instance UUID.
        status: Current health status.
        last_check: Timestamp of last health check.
        issues: List of identified issues.
        warnings: List of warnings.
        execution_time_seconds: Total execution time.
        steps_executed: Number of steps executed.
        steps_failed: Number of failed steps.
        error_count: Total error count.
        retry_count: Total retry count.
        timeout_exceeded: Timeout threshold exceeded flag.
        max_retries_exceeded: Max retries exceeded flag.
        error_rate_high: High error rate flag.
    """

    def __init__(self, flow_instance_id: UUID) -> None:
        """
        Initialize flow health metrics.

        Args:
            flow_instance_id: Flow instance UUID.
        """
        self.flow_instance_id = flow_instance_id
        self.status = HealthStatus.HEALTHY
        self.last_check: Optional[datetime] = None
        self.issues: List[str] = []
        self.warnings: List[str] = []

        # Performance metrics
        self.execution_time_seconds: Optional[float] = None
        self.steps_executed: int = 0
        self.steps_failed: int = 0
        self.error_count: int = 0
        self.retry_count: int = 0

        # Thresholds exceeded
        self.timeout_exceeded: bool = False
        self.max_retries_exceeded: bool = False
        self.error_rate_high: bool = False


class FlowMonitor:
    """
    Monitor for flow health and performance.

    Tracks flow execution health, detects issues, and provides
    comprehensive health status reporting.

    Attributes:
        config: Flow configuration.
        _flow_health: Storage for flow health metrics.
        _active_flows: Set of active flow UUIDs.
        _system_health_status: Overall system health status.
        _system_issues: System-level issues.
        max_execution_time_seconds: Maximum allowed execution time.
        max_step_failures_percentage: Maximum step failure rate.
        max_error_count: Maximum allowed errors.
    """

    def __init__(self) -> None:
        """Initialize flow monitor."""
        self.config = deepcopy(get_flow_config())

        # Health tracking
        self._flow_health: Dict[UUID, FlowHealthMetrics] = {}
        self._active_flows: Set[UUID] = set()

        # System-wide health
        self._system_health_status = HealthStatus.HEALTHY
        self._system_issues: List[str] = []

        # Performance thresholds
        self.max_execution_time_seconds = (
            self.config.execution.default_flow_timeout_minutes * 60
        )
        self.max_step_failures_percentage = 50.0  # 50% failure rate
        self.max_error_count = 5

        logger.info("FlowMonitor initialized")

    # ========================================================================
    # Flow Health Monitoring
    # ========================================================================

    def start_monitoring(self, flow_instance_id: UUID) -> None:
        """
        Start monitoring a flow instance.

        Args:
            flow_instance_id: Flow instance ID to monitor.
        """
        if not self.config.analytics.enable_health_checks:
            return

        self._flow_health[flow_instance_id] = FlowHealthMetrics(flow_instance_id)
        self._active_flows.add(flow_instance_id)

        logger.debug(f"Started monitoring flow {flow_instance_id}")

    def stop_monitoring(self, flow_instance_id: UUID) -> None:
        """
        Stop monitoring a flow instance.

        Args:
            flow_instance_id: Flow instance ID.
        """
        self._active_flows.discard(flow_instance_id)
        logger.debug(f"Stopped monitoring flow {flow_instance_id}")

    def check_flow_health(
        self,
        flow_instance_id: UUID,
        context: FlowContext,
    ) -> FlowHealthMetrics:
        """
        Check health of a specific flow instance.

        Args:
            flow_instance_id: Flow instance ID.
            context: Flow context with execution data.

        Returns:
            FlowHealthMetrics with current health status.
        """
        metrics = self._flow_health.get(
            flow_instance_id,
            FlowHealthMetrics(flow_instance_id),
        )

        metrics.last_check = now_sao_paulo_naive()

        # Update metrics from context
        if context.started_at:
            started_at = normalize_datetime_naive_sao_paulo(context.started_at)
            execution_time = (
                (now_sao_paulo_naive() - started_at).total_seconds()
                if started_at
                else None
            )
            metrics.execution_time_seconds = execution_time

            # Check execution time
            if execution_time is not None and execution_time > self.max_execution_time_seconds:
                metrics.timeout_exceeded = True
                metrics.issues.append(
                    f"Execution time ({execution_time:.0f}s) exceeds timeout "
                    f"({self.max_execution_time_seconds:.0f}s)"
                )

        # Update step metrics
        metrics.steps_executed = len(context.steps_history)
        metrics.steps_failed = sum(
            1 for step in context.steps_history if step.error is not None
        )

        # Check failure rate
        if metrics.steps_executed > 0:
            failure_rate = (metrics.steps_failed / metrics.steps_executed) * 100
            if failure_rate >= self.max_step_failures_percentage:
                metrics.error_rate_high = True
                metrics.issues.append(
                    f"Step failure rate ({failure_rate:.1f}%) is too high"
                )

        # Check for expired flows
        if context.expires_at:
            expires_at = normalize_datetime_naive_sao_paulo(context.expires_at)
            if expires_at and now_sao_paulo_naive() > expires_at:
                metrics.issues.append("Flow has expired")

        # Check priority handling
        if context.priority in [FlowPriority.URGENT, FlowPriority.CRITICAL]:
            if context.status == FlowStatus.PAUSED:
                metrics.warnings.append(
                    f"High priority ({context.priority.value}) flow is paused"
                )

        # Determine overall health status
        metrics.status = self._calculate_health_status(metrics)

        self._flow_health[flow_instance_id] = metrics
        return metrics

    def record_flow_error(
        self,
        flow_instance_id: UUID,
        error: Exception,
    ) -> None:
        """
        Record an error for flow health tracking.

        Args:
            flow_instance_id: Flow instance ID.
            error: Error that occurred.
        """
        metrics = self._flow_health.get(
            flow_instance_id,
            FlowHealthMetrics(flow_instance_id),
        )

        metrics.error_count += 1

        if metrics.error_count >= self.max_error_count:
            metrics.issues.append(
                f"Error count ({metrics.error_count}) exceeds maximum ({self.max_error_count})"
            )

        # Re-evaluate health status
        metrics.status = self._calculate_health_status(metrics)

        self._flow_health[flow_instance_id] = metrics

        logger.warning(
            f"Recorded error for flow {flow_instance_id}: {type(error).__name__}"
        )

    def record_flow_retry(self, flow_instance_id: UUID) -> None:
        """
        Record a retry attempt for flow health tracking.

        Args:
            flow_instance_id: Flow instance ID.
        """
        metrics = self._flow_health.get(
            flow_instance_id,
            FlowHealthMetrics(flow_instance_id),
        )

        metrics.retry_count += 1

        if metrics.retry_count >= self.config.execution.max_step_retries:
            metrics.max_retries_exceeded = True
            metrics.issues.append(
                f"Retry count ({metrics.retry_count}) exceeds maximum "
                f"({self.config.execution.max_step_retries})"
            )

        # Re-evaluate health status
        metrics.status = self._calculate_health_status(metrics)

        self._flow_health[flow_instance_id] = metrics

    # ========================================================================
    # System Health Monitoring
    # ========================================================================

    def check_system_health(self) -> Dict[str, Any]:
        """
        Check overall system health.

        Returns:
            Dictionary with system health information.
        """
        # Count flows by health status
        health_counts = defaultdict(int)
        for metrics in self._flow_health.values():
            health_counts[metrics.status.value] += 1

        total_active = len(self._active_flows)
        unhealthy_count = (
            health_counts[HealthStatus.UNHEALTHY.value]
            + health_counts[HealthStatus.CRITICAL.value]
        )

        # Determine system health
        from ..constants import FlowEngine

        if unhealthy_count == 0:
            self._system_health_status = HealthStatus.HEALTHY
        elif unhealthy_count < total_active * FlowEngine.UNHEALTHY_THRESHOLD_PERCENT:
            self._system_health_status = HealthStatus.DEGRADED
        elif unhealthy_count < total_active * 0.3:  # Less than 30%
            self._system_health_status = HealthStatus.UNHEALTHY
        else:
            self._system_health_status = HealthStatus.CRITICAL

        return {
            "status": self._system_health_status.value,
            "active_flows": total_active,
            "healthy_flows": health_counts[HealthStatus.HEALTHY.value],
            "degraded_flows": health_counts[HealthStatus.DEGRADED.value],
            "unhealthy_flows": health_counts[HealthStatus.UNHEALTHY.value],
            "critical_flows": health_counts[HealthStatus.CRITICAL.value],
            "checked_at": now_sao_paulo_naive().isoformat(),
        }

    def get_unhealthy_flows(self) -> List[FlowHealthMetrics]:
        """
        Get list of unhealthy flows.

        Returns:
            List of FlowHealthMetrics for unhealthy flows.
        """
        return [
            metrics
            for metrics in self._flow_health.values()
            if metrics.status
            in [HealthStatus.UNHEALTHY, HealthStatus.CRITICAL, HealthStatus.DEGRADED]
        ]

    def get_critical_flows(self) -> List[FlowHealthMetrics]:
        """
        Get list of flows in critical state.

        Returns:
            List of FlowHealthMetrics for critical flows.
        """
        return [
            metrics
            for metrics in self._flow_health.values()
            if metrics.status == HealthStatus.CRITICAL
        ]

    # ========================================================================
    # Query Methods
    # ========================================================================

    def get_flow_health(self, flow_instance_id: UUID) -> Optional[FlowHealthMetrics]:
        """
        Get health metrics for a specific flow.

        Args:
            flow_instance_id: Flow instance ID.

        Returns:
            FlowHealthMetrics if available, None otherwise.
        """
        return self._flow_health.get(flow_instance_id)

    def is_flow_healthy(self, flow_instance_id: UUID) -> bool:
        """
        Check if a flow is healthy.

        Args:
            flow_instance_id: Flow instance ID.

        Returns:
            True if flow is healthy, False otherwise.
        """
        metrics = self._flow_health.get(flow_instance_id)
        if not metrics:
            return True  # Unknown flows are considered healthy

        return metrics.status == HealthStatus.HEALTHY

    def get_active_flow_count(self) -> int:
        """
        Get count of active flows being monitored.

        Returns:
            Number of active flows.
        """
        return len(self._active_flows)

    # ========================================================================
    # Alert Methods
    # ========================================================================

    def should_alert(self, flow_instance_id: UUID) -> bool:
        """
        Determine if an alert should be triggered for a flow.

        Args:
            flow_instance_id: Flow instance ID.

        Returns:
            True if alert should be triggered, False otherwise.
        """
        metrics = self._flow_health.get(flow_instance_id)
        if not metrics:
            return False

        # Alert on unhealthy or critical status
        if metrics.status in [HealthStatus.UNHEALTHY, HealthStatus.CRITICAL]:
            return True

        # Alert on specific conditions
        if metrics.timeout_exceeded or metrics.max_retries_exceeded:
            return True

        if metrics.error_count >= self.max_error_count:
            return True

        return False

    def get_alert_data(self, flow_instance_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get alert data for a flow.

        Args:
            flow_instance_id: Flow instance ID.

        Returns:
            Dictionary with alert data, or None if no alert needed.
        """
        if not self.should_alert(flow_instance_id):
            return None

        metrics = self._flow_health.get(flow_instance_id)
        if not metrics:
            return None

        return {
            "flow_instance_id": str(flow_instance_id),
            "health_status": metrics.status.value,
            "issues": metrics.issues,
            "warnings": metrics.warnings,
            "error_count": metrics.error_count,
            "retry_count": metrics.retry_count,
            "execution_time_seconds": metrics.execution_time_seconds,
            "steps_executed": metrics.steps_executed,
            "steps_failed": metrics.steps_failed,
            "timestamp": now_sao_paulo_naive().isoformat(),
        }

    # ========================================================================
    # Internal Methods
    # ========================================================================

    def _calculate_health_status(self, metrics: FlowHealthMetrics) -> HealthStatus:
        """
        Calculate health status based on metrics.

        Args:
            metrics: Flow health metrics.

        Returns:
            Calculated health status.
        """
        # Critical conditions
        if metrics.max_retries_exceeded:
            return HealthStatus.CRITICAL

        if metrics.error_count >= self.max_error_count:
            return HealthStatus.CRITICAL

        # Unhealthy conditions
        if len(metrics.issues) > 0:
            return HealthStatus.UNHEALTHY

        if metrics.error_rate_high:
            return HealthStatus.UNHEALTHY

        # Degraded conditions
        if len(metrics.warnings) > 0:
            return HealthStatus.DEGRADED

        if metrics.retry_count > 0:
            return HealthStatus.DEGRADED

        # Healthy
        return HealthStatus.HEALTHY

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def cleanup_old_metrics(self, hours: int = 24) -> int:
        """
        Clean up old health metrics.

        Args:
            hours: Age threshold in hours.

        Returns:
            Number of metrics cleaned up.
        """
        cutoff_time = now_sao_paulo_naive() - timedelta(hours=hours)
        cleaned = 0

        flow_ids_to_remove = []
        for flow_id, metrics in self._flow_health.items():
            if flow_id not in self._active_flows:
                last_check = normalize_datetime_naive_sao_paulo(metrics.last_check)
                if last_check and last_check < cutoff_time:
                    flow_ids_to_remove.append(flow_id)
                    cleaned += 1

        for flow_id in flow_ids_to_remove:
            del self._flow_health[flow_id]

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} old health metrics")

        return cleaned

    def reset_metrics(self) -> None:
        """
        Reset all health metrics.

        Warning: This clears all health data. Use with caution.
        """
        self._flow_health.clear()
        self._active_flows.clear()
        self._system_health_status = HealthStatus.HEALTHY
        self._system_issues.clear()

        logger.warning("All health metrics have been reset")

    def export_health_report(self) -> Dict[str, Any]:
        """
        Export complete health report.

        Returns:
            Dictionary with complete health data.
        """
        return {
            "system_health": self.check_system_health(),
            "active_flows": len(self._active_flows),
            "monitored_flows": len(self._flow_health),
            "unhealthy_flows": [
                {
                    "flow_instance_id": str(m.flow_instance_id),
                    "status": m.status.value,
                    "issues": m.issues,
                    "warnings": m.warnings,
                    "error_count": m.error_count,
                }
                for m in self.get_unhealthy_flows()
            ],
            "generated_at": now_sao_paulo_naive().isoformat(),
        }


# ============================================================================
# Exports
# ============================================================================

__all__ = ["FlowMonitor", "FlowHealthMetrics", "HealthStatus"]
