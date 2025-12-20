"""
Alert Statistics - Analytics and reporting.

This module handles statistical analysis and dashboard data generation
for the alert system.
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime, timedelta, timezone

from .types import (
    Alert,
    AlertSeverity,
    AlertStatus,
    AlertRuleType,
    AlertStatistics,
    DashboardData,
)

logger = logging.getLogger(__name__)


class AlertStatisticsCollector:
    """
    Handles alert statistics and analytics.

    Responsible for:
    - Calculating alert statistics
    - Generating dashboard data
    - Applying filters to alerts
    - Computing metrics and timelines
    """

    def __init__(self):
        """Initialize AlertStatisticsCollector."""
        pass

    def get_alert_statistics(
        self, alert_cache: Dict[UUID, Alert], filters: Optional[Dict[str, Any]] = None
    ) -> AlertStatistics:
        """
        Get alert statistics.

        Args:
            alert_cache: Alert cache to analyze
            filters: Optional filters (date range, severity, rule type, etc.)

        Returns:
            Alert statistics
        """
        logger.info("Generating alert statistics")

        # Get all alerts
        alerts = list(alert_cache.values())

        # Apply filters
        if filters:
            alerts = self._apply_filters(alerts, filters)

        # Calculate statistics
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
        avg_resolution_time = self._calculate_average_resolution_time(alerts)
        avg_acknowledgment_time = self._calculate_average_acknowledgment_time(alerts)

        statistics = AlertStatistics(
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

        logger.info(f"Statistics generated: {total_alerts} total alerts")

        return statistics

    def get_dashboard_data(
        self, alert_cache: Dict[UUID, Alert], filters: Optional[Dict[str, Any]] = None
    ) -> DashboardData:
        """
        Get dashboard aggregated data.

        Args:
            alert_cache: Alert cache to analyze
            filters: Optional filters

        Returns:
            Dashboard data
        """
        logger.info("Generating dashboard data")

        # Get statistics
        statistics = self.get_alert_statistics(alert_cache, filters)

        # Get recent alerts
        alerts = list(alert_cache.values())
        if filters:
            alerts = self._apply_filters(alerts, filters)

        # Sort by created_at descending
        alerts.sort(key=lambda a: a.created_at, reverse=True)
        recent_alerts = alerts[:20]

        # Top alert types
        rule_type_counts = statistics.by_rule_type
        top_alert_types = [
            {"rule_type": rule_type.value, "count": count}
            for rule_type, count in sorted(
                rule_type_counts.items(), key=lambda x: x[1], reverse=True
            )[:10]
        ]

        # Alert timeline (last 24 hours by hour)
        alert_timeline = self._generate_alert_timeline(alerts)

        dashboard = DashboardData(
            statistics=statistics,
            recent_alerts=recent_alerts,
            top_alert_types=top_alert_types,
            alert_timeline=alert_timeline,
        )

        logger.info("Dashboard data generated successfully")

        return dashboard

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

    def _calculate_average_resolution_time(
        self, alerts: List[Alert]
    ) -> Optional[float]:
        """Calculate average time to resolve alerts."""
        resolved = [a for a in alerts if a.resolved_at and a.created_at]
        if not resolved:
            return None

        total_seconds = sum(
            (a.resolved_at - a.created_at).total_seconds() for a in resolved
        )
        return total_seconds / len(resolved)

    def _calculate_average_acknowledgment_time(
        self, alerts: List[Alert]
    ) -> Optional[float]:
        """Calculate average time to acknowledge alerts."""
        acknowledged = [a for a in alerts if a.acknowledged_at and a.created_at]
        if not acknowledged:
            return None

        total_seconds = sum(
            (a.acknowledged_at - a.created_at).total_seconds() for a in acknowledged
        )
        return total_seconds / len(acknowledged)

    def _generate_alert_timeline(self, alerts: List[Alert]) -> List[Dict[str, Any]]:
        """Generate hourly alert timeline for last 24 hours."""
        now = datetime.now(timezone.utc)
        timeline = []

        for hour_offset in range(24):
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
