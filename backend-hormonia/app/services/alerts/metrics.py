"""
Metrics collector - Tracks alert system metrics and statistics.

This module handles collection and aggregation of alert metrics
for monitoring, reporting, and dashboard purposes.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from .types import (
    Alert,
    AlertStatistics,
    AlertSeverity,
    AlertStatus,
    AlertRuleType,
    DispatchResult,
)

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects and aggregates alert system metrics.

    Responsibilities:
    - Track alert lifecycle events
    - Calculate statistics
    - Generate reports
    - Timeline aggregation
    - Performance metrics
    """

    def __init__(self):
        """Initialize metrics collector."""
        # Counters
        self._total_created = 0
        self._total_dispatched = 0
        self._total_acknowledged = 0
        self._total_resolved = 0
        self._total_escalated = 0

        # By severity
        self._by_severity: Dict[AlertSeverity, int] = defaultdict(int)

        # By rule type
        self._by_rule_type: Dict[AlertRuleType, int] = defaultdict(int)

        # By status
        self._by_status: Dict[AlertStatus, int] = defaultdict(int)

        # Timing metrics
        self._acknowledgment_times: List[float] = []
        self._resolution_times: List[float] = []

        # Dispatch metrics
        self._dispatch_success_count = 0
        self._dispatch_failure_count = 0

        logger.info("MetricsCollector initialized")

    def record_alert_created(self, alert: Alert) -> None:
        """
        Record alert creation.

        Args:
            alert: Created alert
        """
        self._total_created += 1
        self._by_severity[alert.severity] += 1
        self._by_rule_type[alert.rule_type] += 1
        self._by_status[alert.status] += 1

        logger.debug(f"Recorded alert creation: {alert.id} ({alert.severity.value})")

    def record_alert_dispatched(
        self, alert: Alert, dispatch_result: DispatchResult
    ) -> None:
        """
        Record alert dispatch.

        Args:
            alert: Dispatched alert
            dispatch_result: Dispatch result
        """
        self._total_dispatched += 1
        self._dispatch_success_count += dispatch_result.total_sent
        self._dispatch_failure_count += dispatch_result.total_failed

        logger.debug(
            f"Recorded alert dispatch: {alert.id} "
            f"({dispatch_result.total_sent} sent, {dispatch_result.total_failed} failed)"
        )

    def record_alert_acknowledged(self, alert: Alert) -> None:
        """
        Record alert acknowledgment.

        Args:
            alert: Acknowledged alert
        """
        self._total_acknowledged += 1

        # Calculate acknowledgment time
        if alert.acknowledged_at and alert.created_at:
            ack_time = (alert.acknowledged_at - alert.created_at).total_seconds()
            self._acknowledgment_times.append(ack_time)

        # Update status count
        self._by_status[AlertStatus.ACTIVE] = max(
            0, self._by_status[AlertStatus.ACTIVE] - 1
        )
        self._by_status[AlertStatus.ACKNOWLEDGED] += 1

        logger.debug(f"Recorded alert acknowledgment: {alert.id}")

    def record_alert_resolved(self, alert: Alert) -> None:
        """
        Record alert resolution.

        Args:
            alert: Resolved alert
        """
        self._total_resolved += 1

        # Calculate resolution time
        if alert.resolved_at and alert.created_at:
            resolution_time = (alert.resolved_at - alert.created_at).total_seconds()
            self._resolution_times.append(resolution_time)

        # Update status count
        prev_status = (
            AlertStatus.ACKNOWLEDGED if alert.acknowledged_at else AlertStatus.ACTIVE
        )
        self._by_status[prev_status] = max(0, self._by_status[prev_status] - 1)
        self._by_status[AlertStatus.RESOLVED] += 1

        logger.debug(f"Recorded alert resolution: {alert.id}")

    def record_alert_escalated(self, alert: Alert) -> None:
        """
        Record alert escalation.

        Args:
            alert: Escalated alert
        """
        self._total_escalated += 1
        logger.debug(f"Recorded alert escalation: {alert.id}")

    def get_statistics(
        self,
        alerts: Optional[List[Alert]] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> AlertStatistics:
        """
        Get alert statistics.

        Args:
            alerts: Optional list of alerts to calculate stats from
            filters: Optional filters to apply

        Returns:
            AlertStatistics with aggregated metrics
        """
        # If alerts provided, calculate from them
        # Otherwise use tracked metrics
        if alerts:
            return self._calculate_from_alerts(alerts, filters)

        # Calculate averages
        avg_ack_time = (
            sum(self._acknowledgment_times) / len(self._acknowledgment_times)
            if self._acknowledgment_times
            else None
        )

        avg_resolution_time = (
            sum(self._resolution_times) / len(self._resolution_times)
            if self._resolution_times
            else None
        )

        return AlertStatistics(
            total_alerts=self._total_created,
            active_alerts=self._by_status.get(AlertStatus.ACTIVE, 0),
            acknowledged_alerts=self._by_status.get(AlertStatus.ACKNOWLEDGED, 0),
            resolved_alerts=self._by_status.get(AlertStatus.RESOLVED, 0),
            expired_alerts=self._by_status.get(AlertStatus.EXPIRED, 0),
            by_severity=dict(self._by_severity),
            by_rule_type=dict(self._by_rule_type),
            by_status=dict(self._by_status),
            average_resolution_time=avg_resolution_time,
            average_acknowledgment_time=avg_ack_time,
            metadata={
                "total_dispatched": self._total_dispatched,
                "total_escalated": self._total_escalated,
                "dispatch_success_count": self._dispatch_success_count,
                "dispatch_failure_count": self._dispatch_failure_count,
            },
        )

    def _calculate_from_alerts(
        self,
        alerts: List[Alert],
        filters: Optional[Dict[str, Any]] = None,
    ) -> AlertStatistics:
        """
        Calculate statistics from alert list.

        Args:
            alerts: List of alerts
            filters: Optional filters

        Returns:
            AlertStatistics
        """
        # Apply filters if provided
        if filters:
            alerts = self._apply_filters(alerts, filters)

        total_alerts = len(alerts)
        active_alerts = sum(1 for a in alerts if a.status == AlertStatus.ACTIVE)
        acknowledged_alerts = sum(
            1 for a in alerts if a.status == AlertStatus.ACKNOWLEDGED
        )
        resolved_alerts = sum(1 for a in alerts if a.status == AlertStatus.RESOLVED)
        expired_alerts = sum(1 for a in alerts if a.status == AlertStatus.EXPIRED)

        # By severity
        by_severity = {}
        for severity in AlertSeverity:
            by_severity[severity] = sum(1 for a in alerts if a.severity == severity)

        # By rule type
        by_rule_type = {}
        for rule_type in AlertRuleType:
            by_rule_type[rule_type] = sum(1 for a in alerts if a.rule_type == rule_type)

        # By status
        by_status = {}
        for status in AlertStatus:
            by_status[status] = sum(1 for a in alerts if a.status == status)

        # Calculate average times
        avg_resolution_time = self._calc_avg_resolution_time(alerts)
        avg_acknowledgment_time = self._calc_avg_acknowledgment_time(alerts)

        return AlertStatistics(
            total_alerts=total_alerts,
            active_alerts=active_alerts,
            acknowledged_alerts=acknowledged_alerts,
            resolved_alerts=resolved_alerts,
            expired_alerts=expired_alerts,
            by_severity=by_severity,
            by_rule_type=by_rule_type,
            by_status=by_status,
            average_resolution_time=avg_resolution_time,
            average_acknowledgment_time=avg_acknowledgment_time,
        )

    def generate_timeline(
        self, alerts: List[Alert], hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Generate hourly alert timeline.

        Args:
            alerts: List of alerts
            hours: Number of hours to include

        Returns:
            List of hourly buckets with counts
        """
        now = datetime.now()
        timeline = []

        for hour_offset in range(hours):
            hour_start = now - timedelta(hours=hour_offset + 1)
            hour_end = now - timedelta(hours=hour_offset)

            hour_alerts = [a for a in alerts if hour_start <= a.created_at < hour_end]

            timeline.append(
                {
                    "hour": hour_start.strftime("%Y-%m-%d %H:00"),
                    "count": len(hour_alerts),
                    "by_severity": {
                        severity.value: sum(
                            1 for a in hour_alerts if a.severity == severity
                        )
                        for severity in AlertSeverity
                    },
                }
            )

        timeline.reverse()
        return timeline

    def _apply_filters(
        self, alerts: List[Alert], filters: Dict[str, Any]
    ) -> List[Alert]:
        """Apply filters to alert list."""
        filtered = alerts

        if "severity" in filters:
            filtered = [a for a in filtered if a.severity == filters["severity"]]

        if "rule_type" in filters:
            filtered = [a for a in filtered if a.rule_type == filters["rule_type"]]

        if "status" in filters:
            filtered = [a for a in filtered if a.status == filters["status"]]

        if "start_date" in filters:
            start_date = filters["start_date"]
            filtered = [a for a in filtered if a.created_at >= start_date]

        if "end_date" in filters:
            end_date = filters["end_date"]
            filtered = [a for a in filtered if a.created_at <= end_date]

        return filtered

    def _calc_avg_resolution_time(self, alerts: List[Alert]) -> Optional[float]:
        """Calculate average resolution time."""
        resolved = [a for a in alerts if a.resolved_at and a.created_at]
        if not resolved:
            return None

        total_seconds = sum(
            (a.resolved_at - a.created_at).total_seconds() for a in resolved
        )
        return total_seconds / len(resolved)

    def _calc_avg_acknowledgment_time(self, alerts: List[Alert]) -> Optional[float]:
        """Calculate average acknowledgment time."""
        acknowledged = [a for a in alerts if a.acknowledged_at and a.created_at]
        if not acknowledged:
            return None

        total_seconds = sum(
            (a.acknowledged_at - a.created_at).total_seconds() for a in acknowledged
        )
        return total_seconds / len(acknowledged)

    def reset(self) -> None:
        """Reset all metrics."""
        self._total_created = 0
        self._total_dispatched = 0
        self._total_acknowledged = 0
        self._total_resolved = 0
        self._total_escalated = 0
        self._by_severity.clear()
        self._by_rule_type.clear()
        self._by_status.clear()
        self._acknowledgment_times.clear()
        self._resolution_times.clear()
        self._dispatch_success_count = 0
        self._dispatch_failure_count = 0

        logger.info("Metrics reset")


# Singleton instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """
    Get global MetricsCollector instance.

    Returns:
        MetricsCollector singleton
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def set_metrics_collector(collector: MetricsCollector) -> None:
    """
    Set global MetricsCollector instance.

    Args:
        collector: MetricsCollector instance to use
    """
    global _metrics_collector
    _metrics_collector = collector
