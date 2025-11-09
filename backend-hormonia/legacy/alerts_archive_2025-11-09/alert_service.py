"""
Automated alerting for database issues.

Monitors database health and sends alerts when thresholds are exceeded.
Integrates with external alerting systems (Slack, PagerDuty, etc.).
"""
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
from app.core.database import get_pool_status, is_pool_healthy, test_connection
import asyncio

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    FATAL = "fatal"


class AlertType(str, Enum):
    """Types of database alerts."""
    POOL_EXHAUSTION = "pool_exhaustion"
    SLOW_QUERY = "slow_query"
    CONNECTION_ERROR = "connection_error"
    QUERY_TIMEOUT = "query_timeout"
    HIGH_UTILIZATION = "high_utilization"
    UNHEALTHY_CONNECTION = "unhealthy_connection"


class DatabaseAlertService:
    """
    Monitor database health and send alerts.

    Features:
    - Configurable alert thresholds
    - Alert debouncing (prevents spam)
    - Multiple alert channels
    - Historical tracking
    """

    def __init__(self):
        """Initialize alert service with default thresholds."""
        self.alert_thresholds = {
            "pool_utilization_warning": 75,  # %
            "pool_utilization_critical": 85,  # %
            "slow_query_duration": 1.0,  # seconds
            "connection_errors_per_minute": 5,
            "query_timeout_rate": 0.01,  # 1%
            "connection_test_failure_count": 3
        }
        self.alert_history: Dict[str, datetime] = {}
        self.debounce_minutes = 5
        self.alert_callbacks: Dict[AlertSeverity, list] = {
            severity: [] for severity in AlertSeverity
        }
        logger.info("Database alert service initialized")

    def register_callback(self, severity: AlertSeverity, callback: Callable):
        """
        Register a callback for alert notifications.

        Args:
            severity: Minimum severity level to trigger callback
            callback: Async function to call with alert details
        """
        self.alert_callbacks[severity].append(callback)
        logger.info(f"Registered alert callback for {severity} alerts")

    async def check_pool_exhaustion(self) -> None:
        """Check for connection pool exhaustion and alert if needed."""
        try:
            # Check both pools
            for use_service_role in [True, False]:
                pool_name = "service_role" if use_service_role else "rls"
                pool_status = get_pool_status(use_service_role=use_service_role)

                # Calculate utilization
                total_capacity = pool_status.get("pool_size", 0) + pool_status.get("overflow", 0)
                checked_out = pool_status.get("checked_out", 0)
                utilization = (checked_out / total_capacity * 100) if total_capacity > 0 else 0

                # Determine severity
                severity = None
                if utilization >= self.alert_thresholds["pool_utilization_critical"]:
                    severity = AlertSeverity.CRITICAL
                elif utilization >= self.alert_thresholds["pool_utilization_warning"]:
                    severity = AlertSeverity.WARNING

                if severity:
                    await self.send_alert(
                        severity=severity,
                        alert_type=AlertType.POOL_EXHAUSTION,
                        title=f"{pool_name.upper()} Pool Utilization {severity.value.upper()}",
                        message=f"Pool utilization at {utilization:.1f}% "
                               f"({checked_out}/{total_capacity} connections)",
                        metadata={
                            "pool_name": pool_name,
                            "utilization_percent": utilization,
                            "checked_out": checked_out,
                            "total_capacity": total_capacity,
                            **pool_status
                        }
                    )
        except Exception as e:
            logger.error(f"Error checking pool exhaustion: {e}", exc_info=True)

    async def check_connection_health(self) -> None:
        """Check database connection health and alert on failures."""
        try:
            for use_service_role in [True, False]:
                pool_name = "service_role" if use_service_role else "rls"

                # Test connection
                health_result = test_connection(use_service_role=use_service_role)

                if health_result.get("status") != "healthy":
                    await self.send_alert(
                        severity=AlertSeverity.CRITICAL,
                        alert_type=AlertType.UNHEALTHY_CONNECTION,
                        title=f"{pool_name.upper()} Connection Unhealthy",
                        message=f"Database connection test failed: {health_result.get('error', 'Unknown error')}",
                        metadata={
                            "pool_name": pool_name,
                            "health_result": health_result
                        }
                    )
        except Exception as e:
            logger.error(f"Error checking connection health: {e}", exc_info=True)
            await self.send_alert(
                severity=AlertSeverity.FATAL,
                alert_type=AlertType.CONNECTION_ERROR,
                title="Connection Health Check Failed",
                message=f"Unable to perform health check: {str(e)}",
                metadata={"error": str(e), "error_type": type(e).__name__}
            )

    async def send_alert(
        self,
        severity: AlertSeverity,
        alert_type: AlertType,
        title: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Send alert through configured channels.

        Args:
            severity: Alert severity level
            alert_type: Type of alert
            title: Alert title
            message: Alert message
            metadata: Additional context information
        """
        alert_key = f"{severity}:{alert_type}:{title}"

        # Debounce: don't send same alert within debounce period
        if alert_key in self.alert_history:
            last_sent = self.alert_history[alert_key]
            if datetime.now() - last_sent < timedelta(minutes=self.debounce_minutes):
                logger.debug(f"Alert debounced: {alert_key}")
                return

        # Create alert payload
        alert_payload = {
            "severity": severity.value,
            "alert_type": alert_type.value,
            "title": title,
            "message": message,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat()
        }

        # Log alert
        log_level = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.WARNING: logging.WARNING,
            AlertSeverity.CRITICAL: logging.CRITICAL,
            AlertSeverity.FATAL: logging.CRITICAL
        }.get(severity, logging.ERROR)

        logger.log(
            log_level,
            f"DATABASE ALERT [{severity.value.upper()}] {alert_type.value}: {title} - {message}",
            extra=alert_payload
        )

        # Execute registered callbacks
        for callback_severity, callbacks in self.alert_callbacks.items():
            # Execute callbacks for this severity and higher
            severity_order = list(AlertSeverity)
            if severity_order.index(severity) >= severity_order.index(callback_severity):
                for callback in callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(alert_payload)
                        else:
                            callback(alert_payload)
                    except Exception as e:
                        logger.error(f"Error executing alert callback: {e}", exc_info=True)

        # Update alert history
        self.alert_history[alert_key] = datetime.now()

        # TODO: Integrate with external alerting systems
        # - Slack webhook
        # - PagerDuty
        # - Email notifications
        # - SMS alerts
        await self._send_to_external_systems(alert_payload)

    async def _send_to_external_systems(self, alert_payload: Dict[str, Any]) -> None:
        """
        Send alerts to external systems.

        Placeholder for integration with:
        - Slack
        - PagerDuty
        - Email
        - SMS

        Args:
            alert_payload: Alert information to send
        """
        # TODO: Implement external integrations
        # Example Slack integration:
        # if slack_webhook_url:
        #     await send_slack_alert(slack_webhook_url, alert_payload)

        # Example PagerDuty integration:
        # if pagerduty_api_key and severity >= AlertSeverity.CRITICAL:
        #     await trigger_pagerduty_incident(pagerduty_api_key, alert_payload)

        pass

    async def run_periodic_checks(self, interval_seconds: int = 60) -> None:
        """
        Run periodic health checks.

        Args:
            interval_seconds: Time between checks in seconds
        """
        logger.info(f"Starting periodic database health checks (interval: {interval_seconds}s)")

        while True:
            try:
                await self.check_pool_exhaustion()
                await self.check_connection_health()
                await asyncio.sleep(interval_seconds)
            except Exception as e:
                logger.error(f"Error in periodic health check: {e}", exc_info=True)
                await asyncio.sleep(interval_seconds)


# Global alert service instance
_alert_service: Optional[DatabaseAlertService] = None


def get_alert_service() -> DatabaseAlertService:
    """
    Get global alert service instance.

    Returns:
        DatabaseAlertService singleton
    """
    global _alert_service
    if _alert_service is None:
        _alert_service = DatabaseAlertService()
    return _alert_service


async def start_alert_monitoring(interval_seconds: int = 60) -> None:
    """
    Start automated alert monitoring in background.

    Args:
        interval_seconds: Time between checks in seconds
    """
    alert_service = get_alert_service()
    await alert_service.run_periodic_checks(interval_seconds)