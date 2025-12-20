"""
Performance reporting and dashboard generation.
Generates reports, summaries, and real-time dashboard data.
"""

import logging
from typing import Any, List
from datetime import datetime, timedelta, timezone

from app.services.performance_monitoring.models import (
    PerformanceMetric,
    PerformanceBottleneck,
)
from app.services.performance_monitoring.collectors import MetricCollector
from app.services.performance_monitoring.analyzers import PerformanceAnalyzer

logger = logging.getLogger(__name__)


class PerformanceReporter:
    """Generates performance reports and dashboards."""

    def __init__(self, collector: MetricCollector, analyzer: PerformanceAnalyzer):
        self.collector = collector
        self.analyzer = analyzer

    async def generate_performance_report(
        self, time_range: timedelta, current_bottlenecks: List[PerformanceBottleneck]
    ) -> dict[str, Any]:
        """Generate comprehensive performance report."""
        try:
            end_time = datetime.now(timezone.utc)
            start_time = end_time - time_range

            # Get metrics for time range
            metrics = await self.collector.get_metrics_for_range(start_time, end_time)

            # Calculate statistics
            stats = self.analyzer.calculate_performance_statistics(metrics)

            # Get trends
            trends = self.analyzer.calculate_performance_trends(metrics)

            # Generate recommendations
            recommendations = self.analyzer.generate_performance_recommendations(
                stats, current_bottlenecks
            )

            return {
                "report_generated_at": datetime.now(timezone.utc).isoformat(),
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                    "duration_hours": time_range.total_seconds() / 3600,
                },
                "statistics": stats,
                "bottlenecks": [
                    {
                        "type": b.bottleneck_type.value,
                        "severity": b.severity,
                        "description": b.description,
                        "affected_components": b.affected_components,
                        "recommendations": b.recommendations,
                        "detected_at": b.detected_at.isoformat(),
                    }
                    for b in current_bottlenecks
                ],
                "trends": trends,
                "recommendations": recommendations,
                "health_score": self.analyzer.calculate_health_score(stats),
            }

        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            return {"error": str(e)}

    async def generate_real_time_dashboard(
        self,
        current_metrics: List[PerformanceMetric],
        active_bottlenecks: List[PerformanceBottleneck],
    ) -> dict[str, Any]:
        """Get real-time performance dashboard data."""
        try:
            # Get recent trends (last hour)
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            recent_metrics = await self.collector.get_metrics_for_range(
                one_hour_ago, datetime.now(timezone.utc)
            )

            # Calculate dashboard data
            dashboard_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "current_metrics": {
                    metric.metric_type.value: {
                        "value": metric.value,
                        "component": metric.component,
                        "status": self.analyzer.get_metric_status(metric),
                        "metadata": metric.metadata,
                    }
                    for metric in current_metrics
                },
                "trends": self.analyzer.calculate_performance_trends(recent_metrics),
                "active_bottlenecks": len(active_bottlenecks),
                "system_health": await self._get_system_health_summary(
                    active_bottlenecks
                ),
                "alerts": self._get_performance_alerts(active_bottlenecks),
            }

            return dashboard_data

        except Exception as e:
            logger.error(f"Error getting performance dashboard: {e}")
            return {"error": str(e)}

    async def _get_system_health_summary(
        self, bottlenecks: List[PerformanceBottleneck]
    ) -> dict[str, Any]:
        """Get system health summary."""
        try:
            critical_bottlenecks = [b for b in bottlenecks if b.severity == "critical"]

            return {
                "status": "critical" if critical_bottlenecks else "healthy",
                "bottleneck_count": len(bottlenecks),
                "critical_issues": len(critical_bottlenecks),
            }

        except Exception as e:
            logger.error(f"Error getting system health summary: {e}")
            return {"status": "unknown", "error": str(e)}

    def _get_performance_alerts(
        self, bottlenecks: List[PerformanceBottleneck]
    ) -> List[dict[str, Any]]:
        """Get current performance alerts."""
        alerts = []

        try:
            for bottleneck in bottlenecks:
                if bottleneck.severity in ["high", "critical"]:
                    alerts.append(
                        {
                            "type": bottleneck.bottleneck_type.value,
                            "severity": bottleneck.severity,
                            "description": bottleneck.description,
                            "detected_at": bottleneck.detected_at.isoformat(),
                        }
                    )

            return alerts

        except Exception as e:
            logger.error(f"Error getting performance alerts: {e}")
            return []
