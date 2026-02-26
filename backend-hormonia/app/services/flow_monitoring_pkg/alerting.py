"""Alert lifecycle management for flow monitoring."""

import json
import logging
from datetime import datetime
from typing import Optional

from app.models.alert import AlertSeverity
from app.utils.timezone import now_sao_paulo

from .models import SystemAlert

logger = logging.getLogger(__name__)


class FlowMonitoringAlertingMixin:
    async def check_and_create_alerts(self) -> list[SystemAlert]:
        """Check system metrics and create alerts if thresholds are exceeded."""
        alerts = []

        try:
            metrics = await self.collect_performance_metrics()

            if metrics.error_rate >= self.thresholds["error_rate_critical"]:
                alert = await self._create_alert(
                    AlertSeverity.CRITICAL,
                    "High Error Rate",
                    f"Error rate is {metrics.error_rate:.2%}, exceeding critical threshold",
                    "flow_processing",
                    metrics.error_rate,
                    self.thresholds["error_rate_critical"],
                )
                if alert:
                    alerts.append(alert)

            elif metrics.error_rate >= self.thresholds["error_rate_warning"]:
                alert = await self._create_alert(
                    AlertSeverity.HIGH,
                    "Elevated Error Rate",
                    f"Error rate is {metrics.error_rate:.2%}, exceeding warning threshold",
                    "flow_processing",
                    metrics.error_rate,
                    self.thresholds["error_rate_warning"],
                )
                if alert:
                    alerts.append(alert)

            if metrics.average_response_time >= self.thresholds["response_time_critical"]:
                alert = await self._create_alert(
                    AlertSeverity.CRITICAL,
                    "Slow Response Time",
                    f"Average response time is {metrics.average_response_time:.2f}s",
                    "performance",
                    metrics.average_response_time,
                    self.thresholds["response_time_critical"],
                )
                if alert:
                    alerts.append(alert)

            if metrics.queue_depth >= self.thresholds["queue_depth_critical"]:
                alert = await self._create_alert(
                    AlertSeverity.CRITICAL,
                    "High Queue Depth",
                    f"Message queue depth is {metrics.queue_depth}",
                    "message_queue",
                    metrics.queue_depth,
                    self.thresholds["queue_depth_critical"],
                )
                if alert:
                    alerts.append(alert)

            if metrics.redis_memory_usage >= self.thresholds["redis_memory_critical"]:
                alert = await self._create_alert(
                    AlertSeverity.CRITICAL,
                    "High Redis Memory Usage",
                    f"Redis memory usage is {metrics.redis_memory_usage:.1%}",
                    "redis",
                    metrics.redis_memory_usage,
                    self.thresholds["redis_memory_critical"],
                )
                if alert:
                    alerts.append(alert)

            stale_flows = await self._count_stale_flows()
            if stale_flows >= self.thresholds["stale_flows_critical"]:
                alert = await self._create_alert(
                    AlertSeverity.HIGH,
                    "Stale Flows Detected",
                    f"{stale_flows} flows haven't been processed in over 24 hours",
                    "flow_processing",
                    stale_flows,
                    self.thresholds["stale_flows_critical"],
                )
                if alert:
                    alerts.append(alert)

            corruption_rate = await self._calculate_corruption_rate()
            if corruption_rate >= self.thresholds["corruption_rate_critical"]:
                alert = await self._create_alert(
                    AlertSeverity.CRITICAL,
                    "High Data Corruption Rate",
                    f"Data corruption rate is {corruption_rate:.2%}",
                    "data_integrity",
                    corruption_rate,
                    self.thresholds["corruption_rate_critical"],
                )
                if alert:
                    alerts.append(alert)

            return alerts

        except Exception as e:
            logger.error(f"Error checking alerts: {e}")
            return []

    async def get_active_alerts(self) -> list[SystemAlert]:
        """Get all active (unresolved) alerts."""
        try:
            alert_keys = list(self.redis.scan_iter(match="alert:*", count=100))
            alerts = []

            for key in alert_keys:
                alert_data = self.redis.get(key)
                if alert_data:
                    alert_dict = json.loads(alert_data)
                    if not alert_dict.get("resolved_at"):
                        alert = SystemAlert(
                            id=alert_dict["id"],
                            severity=AlertSeverity(alert_dict["severity"]),
                            title=alert_dict["title"],
                            message=alert_dict["message"],
                            component=alert_dict["component"],
                            metric_value=alert_dict.get("metric_value"),
                            threshold=alert_dict.get("threshold"),
                            created_at=datetime.fromisoformat(alert_dict["created_at"]),
                            resolved_at=datetime.fromisoformat(alert_dict["resolved_at"])
                            if alert_dict.get("resolved_at")
                            else None,
                            metadata=alert_dict.get("metadata", {}),
                        )
                        alerts.append(alert)

            return sorted(alerts, key=lambda alert: alert.created_at, reverse=True)

        except Exception as e:
            logger.error(f"Error getting active alerts: {e}")
            return []

    async def resolve_alert(
        self, alert_id: str, resolution_note: Optional[str] = None
    ) -> bool:
        """Resolve an active alert."""
        try:
            alert_key = f"alert:{alert_id}"
            alert_data = self.redis.get(alert_key)

            if not alert_data:
                return False

            alert_dict = json.loads(alert_data)
            alert_dict["resolved_at"] = now_sao_paulo().isoformat()
            if resolution_note:
                alert_dict["resolution_note"] = resolution_note

            self.redis.setex(alert_key, 86400 * 7, json.dumps(alert_dict))

            logger.info(f"Resolved alert {alert_id}: {resolution_note}")
            return True

        except Exception as e:
            logger.error(f"Error resolving alert {alert_id}: {e}")
            return False

    async def _create_alert(
        self,
        severity: AlertSeverity,
        title: str,
        message: str,
        component: str,
        metric_value: Optional[float] = None,
        threshold: Optional[float] = None,
    ) -> Optional[SystemAlert]:
        """Create a new alert if not in cooldown period."""
        try:
            cooldown_key = f"alert_cooldown:{component}:{title}"
            if self.redis.exists(cooldown_key):
                return None

            alert_id = (
                f"{component}_{title.replace(' ', '_').lower()}_"
                f"{int(now_sao_paulo().timestamp())}"
            )
            alert = SystemAlert(
                id=alert_id,
                severity=severity,
                title=title,
                message=message,
                component=component,
                metric_value=metric_value,
                threshold=threshold,
                created_at=now_sao_paulo(),
                resolved_at=None,
                metadata={},
            )

            alert_key = f"alert:{alert_id}"
            alert_data = {
                "id": alert.id,
                "severity": alert.severity.value,
                "title": alert.title,
                "message": alert.message,
                "component": alert.component,
                "metric_value": alert.metric_value,
                "threshold": alert.threshold,
                "created_at": alert.created_at.isoformat(),
                "resolved_at": None,
                "metadata": alert.metadata,
            }

            self.redis.setex(alert_key, 86400 * 7, json.dumps(alert_data))

            cooldown_seconds = self.alert_cooldowns[severity]
            self.redis.setex(cooldown_key, cooldown_seconds, "1")

            logger.warning(f"Created {severity.value} alert: {title} - {message}")

            if severity == AlertSeverity.CRITICAL:
                await self._send_critical_alert_notification(alert)

            return alert

        except Exception as e:
            logger.error(f"Error creating alert: {e}")
            return None

    async def _send_critical_alert_notification(self, alert: SystemAlert) -> None:
        """Send notification for critical alerts."""
        try:
            critical_key = f"critical_alert:{alert.id}"
            notification_data = {
                "alert_id": alert.id,
                "severity": alert.severity.value,
                "title": alert.title,
                "message": alert.message,
                "component": alert.component,
                "created_at": alert.created_at.isoformat(),
                "requires_immediate_attention": True,
            }

            self.redis.setex(critical_key, 86400, json.dumps(notification_data))
            logger.critical(f"CRITICAL ALERT: {alert.title} - {alert.message}")

        except Exception as e:
            logger.error(f"Error sending critical alert notification: {e}")
