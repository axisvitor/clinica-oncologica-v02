"""
Database health monitoring integration.

This module provides infrastructure monitoring for database health,
integrating with the unified alert system.
"""

import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from uuid import uuid4

from ..types import (
    Alert,
    AlertRuleType,
    AlertSeverity,
    AlertStatus,
    MonitoringThresholds,
)
from ..config import get_config

logger = logging.getLogger(__name__)


class DatabaseMonitor:
    """
    Database health monitoring.

    Features:
    - Pool exhaustion monitoring
    - Connection health checks
    - Slow query detection
    - Alert creation for infrastructure issues
    - Integration with unified AlertManager

    This replaces the original DatabaseAlertService with integration
    to the unified alert system.
    """

    def __init__(self, alert_manager=None):
        """
        Initialize DatabaseMonitor.

        Args:
            alert_manager: AlertManager instance for alert creation
        """
        self.alert_manager = alert_manager
        self.config = get_config()
        self.thresholds = self.config.monitoring_thresholds

        # Alert debouncing
        self._last_alert_times: Dict[str, datetime] = {}
        self._debounce_minutes = self.config.debounce_minutes

        # Callbacks for external systems (legacy support)
        self._callbacks: Dict[AlertSeverity, list] = {
            severity: [] for severity in AlertSeverity
        }

        logger.info("DatabaseMonitor initialized")

    def register_callback(self, severity: AlertSeverity, callback: Callable) -> None:
        """
        Register a callback for alert notifications (legacy support).

        Args:
            severity: Minimum severity level to trigger callback
            callback: Async function to call with alert details
        """
        self._callbacks[severity].append(callback)
        logger.info(f"Registered callback for {severity.value} alerts")

    async def check_pool_exhaustion(
        self, use_service_role: bool = True
    ) -> Optional[Alert]:
        """
        Check for connection pool exhaustion.

        Args:
            use_service_role: Whether to check service role pool or RLS pool

        Returns:
            Alert if threshold exceeded, None otherwise
        """
        try:
            # Import here to avoid circular dependencies
            from app.core.database import get_pool_status

            pool_name = "service_role" if use_service_role else "rls"
            pool_status = get_pool_status(use_service_role=use_service_role)

            # Calculate utilization
            total_capacity = pool_status.get("pool_size", 0) + pool_status.get(
                "overflow", 0
            )
            checked_out = pool_status.get("checked_out", 0)
            utilization = (
                (checked_out / total_capacity * 100) if total_capacity > 0 else 0
            )

            # Determine severity
            severity = None
            if utilization >= self.thresholds.pool_utilization_critical:
                severity = AlertSeverity.CRITICAL
            elif utilization >= self.thresholds.pool_utilization_warning:
                severity = AlertSeverity.WARNING

            if severity:
                # Check debouncing
                alert_key = f"pool_exhaustion_{pool_name}_{severity.value}"
                if self._should_debounce(alert_key):
                    logger.debug(f"Alert debounced: {alert_key}")
                    return None

                # Create alert
                alert = Alert(
                    id=uuid4(),
                    rule_id=uuid4(),  # TODO: Use actual rule ID
                    rule_type=AlertRuleType.POOL_EXHAUSTION,
                    severity=severity,
                    status=AlertStatus.ACTIVE,
                    title=f"{pool_name.upper()} Pool Utilization {severity.value.upper()}",
                    message=f"Pool utilization at {utilization:.1f}% ({checked_out}/{total_capacity} connections)",
                    context={
                        "pool_name": pool_name,
                        "utilization_percent": utilization,
                        "checked_out": checked_out,
                        "total_capacity": total_capacity,
                        **pool_status,
                    },
                    metadata={
                        "monitor_type": "database",
                        "check_type": "pool_exhaustion",
                    },
                    created_at=datetime.now(),
                )

                # Process through AlertManager if available
                if self.alert_manager:
                    await self.alert_manager.process_alert(alert)
                else:
                    # Fallback: execute callbacks
                    await self._execute_callbacks(alert)

                # Update debounce tracking
                self._last_alert_times[alert_key] = datetime.now()

                return alert

            return None

        except Exception as e:
            logger.error(f"Error checking pool exhaustion: {e}", exc_info=True)
            return None

    async def check_connection_health(
        self, use_service_role: bool = True
    ) -> Optional[Alert]:
        """
        Check database connection health.

        Args:
            use_service_role: Whether to check service role pool or RLS pool

        Returns:
            Alert if connection unhealthy, None otherwise
        """
        try:
            # Import here to avoid circular dependencies
            from app.core.database import test_connection

            pool_name = "service_role" if use_service_role else "rls"
            health_result = test_connection(use_service_role=use_service_role)

            if health_result.get("status") != "healthy":
                # Check debouncing
                alert_key = f"connection_health_{pool_name}"
                if self._should_debounce(alert_key):
                    logger.debug(f"Alert debounced: {alert_key}")
                    return None

                # Create alert
                alert = Alert(
                    id=uuid4(),
                    rule_id=uuid4(),  # TODO: Use actual rule ID
                    rule_type=AlertRuleType.UNHEALTHY_CONNECTION,
                    severity=AlertSeverity.CRITICAL,
                    status=AlertStatus.ACTIVE,
                    title=f"{pool_name.upper()} Connection Unhealthy",
                    message=f"Database connection test failed: {health_result.get('error', 'Unknown error')}",
                    context={
                        "pool_name": pool_name,
                        "health_result": health_result,
                    },
                    metadata={
                        "monitor_type": "database",
                        "check_type": "connection_health",
                    },
                    created_at=datetime.now(),
                )

                # Process through AlertManager if available
                if self.alert_manager:
                    await self.alert_manager.process_alert(alert)
                else:
                    # Fallback: execute callbacks
                    await self._execute_callbacks(alert)

                # Update debounce tracking
                self._last_alert_times[alert_key] = datetime.now()

                return alert

            return None

        except Exception as e:
            logger.error(f"Error checking connection health: {e}", exc_info=True)

            # Create error alert
            alert = Alert(
                id=uuid4(),
                rule_id=uuid4(),
                rule_type=AlertRuleType.CONNECTION_ERROR,
                severity=AlertSeverity.FATAL,
                status=AlertStatus.ACTIVE,
                title="Connection Health Check Failed",
                message=f"Unable to perform health check: {str(e)}",
                context={"error": str(e), "error_type": type(e).__name__},
                metadata={
                    "monitor_type": "database",
                    "check_type": "connection_health",
                },
                created_at=datetime.now(),
            )

            if self.alert_manager:
                await self.alert_manager.process_alert(alert)
            else:
                await self._execute_callbacks(alert)

            return alert

    async def check_all(self) -> list[Alert]:
        """
        Run all database health checks.

        Returns:
            List of alerts triggered
        """
        alerts = []

        # Check both pools
        for use_service_role in [True, False]:
            # Pool exhaustion
            pool_alert = await self.check_pool_exhaustion(use_service_role)
            if pool_alert:
                alerts.append(pool_alert)

            # Connection health
            health_alert = await self.check_connection_health(use_service_role)
            if health_alert:
                alerts.append(health_alert)

        return alerts

    async def run_periodic_checks(self, interval_seconds: int = 60) -> None:
        """
        Run periodic health checks.

        Args:
            interval_seconds: Time between checks in seconds
        """
        import asyncio

        logger.info(
            f"Starting periodic database health checks (interval: {interval_seconds}s)"
        )

        while True:
            try:
                await self.check_all()
                await asyncio.sleep(interval_seconds)
            except Exception as e:
                logger.error(f"Error in periodic health check: {e}", exc_info=True)
                await asyncio.sleep(interval_seconds)

    def update_thresholds(self, thresholds: MonitoringThresholds) -> None:
        """
        Update monitoring thresholds.

        Args:
            thresholds: New monitoring thresholds
        """
        self.thresholds = thresholds
        logger.info("Monitoring thresholds updated")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get monitoring statistics.

        Returns:
            Dictionary of statistics
        """
        return {
            "debounce_minutes": self._debounce_minutes,
            "active_debounces": len(self._last_alert_times),
            "registered_callbacks": sum(
                len(callbacks) for callbacks in self._callbacks.values()
            ),
            "thresholds": {
                "pool_utilization_warning": self.thresholds.pool_utilization_warning,
                "pool_utilization_critical": self.thresholds.pool_utilization_critical,
                "slow_query_duration": self.thresholds.slow_query_duration,
                "connection_errors_per_minute": self.thresholds.connection_errors_per_minute,
            },
        }

    # Private helper methods

    def _should_debounce(self, alert_key: str) -> bool:
        """
        Check if alert should be debounced.

        Args:
            alert_key: Unique key for alert type

        Returns:
            True if alert should be debounced
        """
        if alert_key not in self._last_alert_times:
            return False

        last_alert_time = self._last_alert_times[alert_key]
        time_since_last = datetime.now() - last_alert_time

        return time_since_last < timedelta(minutes=self._debounce_minutes)

    async def _execute_callbacks(self, alert: Alert) -> None:
        """
        Execute registered callbacks for an alert (legacy support).

        Args:
            alert: Alert to send to callbacks
        """
        import asyncio

        # Convert alert to legacy payload format
        alert_payload = {
            "severity": alert.severity.value,
            "alert_type": alert.rule_type.value,
            "title": alert.title,
            "message": alert.message,
            "metadata": {**alert.context, **alert.metadata},
            "timestamp": alert.created_at.isoformat(),
        }

        # Execute callbacks for this severity and higher
        severity_order = list(AlertSeverity)
        alert_severity_index = severity_order.index(alert.severity)

        for callback_severity, callbacks in self._callbacks.items():
            callback_severity_index = severity_order.index(callback_severity)

            if alert_severity_index >= callback_severity_index:
                for callback in callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(alert_payload)
                        else:
                            callback(alert_payload)
                    except Exception as e:
                        logger.error(
                            f"Error executing alert callback: {e}", exc_info=True
                        )


# Singleton instance
_database_monitor: Optional[DatabaseMonitor] = None


def get_database_monitor() -> DatabaseMonitor:
    """
    Get global DatabaseMonitor instance.

    Returns:
        DatabaseMonitor singleton
    """
    global _database_monitor
    if _database_monitor is None:
        _database_monitor = DatabaseMonitor()
    return _database_monitor


def set_database_monitor(monitor: DatabaseMonitor) -> None:
    """
    Set global DatabaseMonitor instance.

    Args:
        monitor: DatabaseMonitor instance to use
    """
    global _database_monitor
    _database_monitor = monitor


async def start_monitoring(interval_seconds: int = 60) -> None:
    """
    Start automated database monitoring in background.

    Args:
        interval_seconds: Time between checks in seconds
    """
    monitor = get_database_monitor()
    await monitor.run_periodic_checks(interval_seconds)
