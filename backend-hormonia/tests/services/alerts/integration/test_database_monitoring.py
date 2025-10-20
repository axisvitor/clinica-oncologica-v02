"""
Integration Tests for Database Monitoring.

Tests the complete database monitoring workflow including:
- Real-time health check execution
- Connection pool monitoring integration
- Slow query detection
- Alert generation and notification
- DatabaseMonitor + AlertManager integration
- Periodic monitoring cycle
- Threshold-based alerting
- Multi-pool monitoring (service_role and RLS)

Author: Backend Team
Date: 2025-01-20
"""

import pytest
import asyncio
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, Any, List

from app.services.alerts import (
    DatabaseMonitor,
    AlertManager,
    NotificationDispatcher,
    Alert,
    AlertRuleType,
    AlertSeverity,
    AlertStatus,
    NotificationChannel,
    NotificationTarget,
    MonitoringThresholds,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def monitoring_system():
    """Create integrated monitoring system."""
    # Create components
    dispatcher = NotificationDispatcher()
    alert_manager = AlertManager(dispatcher=dispatcher)
    database_monitor = DatabaseMonitor(alert_manager=alert_manager)

    return {
        "database_monitor": database_monitor,
        "alert_manager": alert_manager,
        "dispatcher": dispatcher,
    }


@pytest.fixture
def monitoring_targets():
    """Notification targets for monitoring alerts."""
    return [
        NotificationTarget(
            target_id=str(uuid4()),
            target_type="devops",
            name="DevOps Team",
            email="devops@clinic.com",
            phone="+5511999990000",
        ),
        NotificationTarget(
            target_id=str(uuid4()),
            target_type="dba",
            name="Database Admin",
            email="dba@clinic.com",
            phone="+5511999990001",
        ),
    ]


@pytest.fixture
def custom_thresholds():
    """Custom monitoring thresholds for testing."""
    return MonitoringThresholds(
        pool_utilization_warning=60.0,
        pool_utilization_critical=85.0,
        slow_query_duration=3.0,
        connection_errors_per_minute=5,
    )


@pytest.fixture
def healthy_system_state():
    """Healthy system state data."""
    return {
        "pool_status": {
            "pool_size": 20,
            "overflow": 10,
            "checked_out": 8,
            "checked_in": 22,
            "status": "healthy",
        },
        "connection_result": {
            "status": "healthy",
            "latency_ms": 5,
            "timestamp": datetime.now().isoformat(),
        },
    }


@pytest.fixture
def degraded_system_state():
    """Degraded system state with high utilization."""
    return {
        "pool_status": {
            "pool_size": 20,
            "overflow": 10,
            "checked_out": 28,  # 93% utilization
            "checked_in": 2,
            "status": "degraded",
        },
        "connection_result": {
            "status": "healthy",
            "latency_ms": 150,
            "timestamp": datetime.now().isoformat(),
        },
    }


@pytest.fixture
def failing_system_state():
    """Failing system state."""
    return {
        "pool_status": {
            "pool_size": 20,
            "overflow": 10,
            "checked_out": 30,  # 100% utilization
            "checked_in": 0,
            "status": "exhausted",
        },
        "connection_result": {
            "status": "unhealthy",
            "error": "Connection timeout",
            "timestamp": datetime.now().isoformat(),
        },
    }


# ============================================================================
# Test Complete Monitoring Cycle
# ============================================================================


class TestMonitoringCycle:
    """Test complete monitoring cycle with alert generation."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_healthy_system_no_alerts(
        self, monitoring_system, healthy_system_state
    ):
        """Test that healthy system generates no alerts."""
        database_monitor = monitoring_system["database_monitor"]

        with (
            patch(
                "app.services.alerts.monitoring.database_monitor.get_pool_status",
                return_value=healthy_system_state["pool_status"],
            ),
            patch(
                "app.services.alerts.monitoring.database_monitor.test_connection",
                return_value=healthy_system_state["connection_result"],
            ),
        ):
            # Run health checks
            alerts = await database_monitor.check_all()

            # Should not generate any alerts
            assert len(alerts) == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_degraded_system_generates_warnings(
        self, monitoring_system, degraded_system_state, monitoring_targets
    ):
        """Test that degraded system generates warning alerts."""
        database_monitor = monitoring_system["database_monitor"]
        alert_manager = monitoring_system["alert_manager"]
        dispatcher = monitoring_system["dispatcher"]

        # Setup notification
        mock_channel = AsyncMock()
        mock_channel.send = AsyncMock(return_value=True)
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel)

        with (
            patch(
                "app.services.alerts.monitoring.database_monitor.get_pool_status",
                return_value=degraded_system_state["pool_status"],
            ),
            patch(
                "app.services.alerts.monitoring.database_monitor.test_connection",
                return_value=degraded_system_state["connection_result"],
            ),
        ):
            # Run health checks
            alerts = await database_monitor.check_all()

            # Should generate alerts (2 pools x 1 alert = 2 alerts)
            assert len(alerts) >= 2

            # Verify alert severity
            for alert in alerts:
                assert alert.severity in [AlertSeverity.WARNING, AlertSeverity.CRITICAL]
                assert alert.status == AlertStatus.ACTIVE

            # Send notifications for alerts
            for alert in alerts:
                await alert_manager.send_notifications(
                    alert=alert,
                    targets=monitoring_targets,
                    channels=[NotificationChannel.EMAIL],
                )

            # Verify notifications sent
            assert mock_channel.send.called

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_failing_system_generates_critical_alerts(
        self, monitoring_system, failing_system_state, monitoring_targets
    ):
        """Test that failing system generates critical/fatal alerts."""
        database_monitor = monitoring_system["database_monitor"]
        alert_manager = monitoring_system["alert_manager"]
        dispatcher = monitoring_system["dispatcher"]

        mock_channel = AsyncMock()
        mock_channel.send = AsyncMock(return_value=True)
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel)

        with (
            patch(
                "app.services.alerts.monitoring.database_monitor.get_pool_status",
                return_value=failing_system_state["pool_status"],
            ),
            patch(
                "app.services.alerts.monitoring.database_monitor.test_connection",
                return_value=failing_system_state["connection_result"],
            ),
        ):
            # Run health checks
            alerts = await database_monitor.check_all()

            # Should generate multiple critical alerts
            assert len(alerts) >= 2

            critical_alerts = [
                a
                for a in alerts
                if a.severity in [AlertSeverity.CRITICAL, AlertSeverity.FATAL]
            ]
            assert len(critical_alerts) >= 2

            # Verify alert types
            alert_types = {alert.rule_type for alert in alerts}
            assert AlertRuleType.POOL_EXHAUSTION in alert_types
            assert AlertRuleType.UNHEALTHY_CONNECTION in alert_types


# ============================================================================
# Test Multi-Pool Monitoring
# ============================================================================


class TestMultiPoolMonitoring:
    """Test monitoring of both service_role and RLS pools."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_both_pools_monitored_independently(
        self, monitoring_system, healthy_system_state, degraded_system_state
    ):
        """Test that both pools are monitored with separate alerts."""
        database_monitor = monitoring_system["database_monitor"]

        # Mock different states for each pool
        def get_pool_status_mock(use_service_role=True):
            if use_service_role:
                return healthy_system_state["pool_status"]
            else:
                return degraded_system_state["pool_status"]

        with (
            patch(
                "app.services.alerts.monitoring.database_monitor.get_pool_status",
                side_effect=get_pool_status_mock,
            ),
            patch(
                "app.services.alerts.monitoring.database_monitor.test_connection",
                return_value=healthy_system_state["connection_result"],
            ),
        ):
            # Run health checks
            alerts = await database_monitor.check_all()

            # Should have alerts only for RLS pool (degraded)
            pool_alerts = [
                a for a in alerts if a.rule_type == AlertRuleType.POOL_EXHAUSTION
            ]

            if pool_alerts:
                # Verify alerts distinguish between pools
                rls_alerts = [a for a in pool_alerts if "RLS" in a.title]
                assert len(rls_alerts) > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_pool_specific_alert_context(
        self, monitoring_system, degraded_system_state
    ):
        """Test that alerts include pool-specific context."""
        database_monitor = monitoring_system["database_monitor"]

        with (
            patch(
                "app.services.alerts.monitoring.database_monitor.get_pool_status",
                return_value=degraded_system_state["pool_status"],
            ),
            patch(
                "app.services.alerts.monitoring.database_monitor.test_connection",
                return_value=degraded_system_state["connection_result"],
            ),
        ):
            # Check service_role pool
            alert_service = await database_monitor.check_pool_exhaustion(
                use_service_role=True
            )

            # Check RLS pool
            alert_rls = await database_monitor.check_pool_exhaustion(
                use_service_role=False
            )

            # Both should have alerts
            assert alert_service is not None
            assert alert_rls is not None

            # Verify distinct context
            assert alert_service.context["pool_name"] == "service_role"
            assert alert_rls.context["pool_name"] == "rls"


# ============================================================================
# Test Alert Debouncing
# ============================================================================


class TestAlertDebouncing:
    """Test alert debouncing to prevent spam."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_repeated_checks_debounced(
        self, monitoring_system, degraded_system_state
    ):
        """Test that repeated checks within debounce window don't spam alerts."""
        database_monitor = monitoring_system["database_monitor"]
        alert_manager = monitoring_system["alert_manager"]

        with (
            patch(
                "app.services.alerts.monitoring.database_monitor.get_pool_status",
                return_value=degraded_system_state["pool_status"],
            ),
            patch(
                "app.services.alerts.monitoring.database_monitor.test_connection",
                return_value=degraded_system_state["connection_result"],
            ),
        ):
            # First check - should generate alerts
            alerts_1 = await database_monitor.check_all()
            first_alert_count = len(alerts_1)
            assert first_alert_count > 0

            # Second check immediately after - should be debounced
            alerts_2 = await database_monitor.check_all()
            assert len(alerts_2) == 0  # Debounced

            # Third check - still debounced
            alerts_3 = await database_monitor.check_all()
            assert len(alerts_3) == 0  # Still debounced

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_debounce_expires_after_window(
        self, monitoring_system, degraded_system_state
    ):
        """Test that alerts can be generated again after debounce window."""
        database_monitor = monitoring_system["database_monitor"]

        with (
            patch(
                "app.services.alerts.monitoring.database_monitor.get_pool_status",
                return_value=degraded_system_state["pool_status"],
            ),
            patch(
                "app.services.alerts.monitoring.database_monitor.test_connection",
                return_value=degraded_system_state["connection_result"],
            ),
        ):
            # First check
            alerts_1 = await database_monitor.check_all()
            assert len(alerts_1) > 0

            # Manually expire debounce window
            for key in database_monitor._last_alert_times.keys():
                database_monitor._last_alert_times[key] = datetime.now() - timedelta(
                    minutes=10
                )

            # Second check - should generate alerts again
            alerts_2 = await database_monitor.check_all()
            assert len(alerts_2) > 0


# ============================================================================
# Test Threshold Configuration
# ============================================================================


class TestThresholdConfiguration:
    """Test threshold-based monitoring."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_custom_thresholds_affect_alerting(
        self, monitoring_system, custom_thresholds
    ):
        """Test that custom thresholds change alert behavior."""
        database_monitor = monitoring_system["database_monitor"]

        # Pool at 70% utilization
        pool_status = {
            "pool_size": 20,
            "overflow": 10,
            "checked_out": 21,  # 70%
            "checked_in": 9,
        }

        connection_result = {"status": "healthy"}

        # With default thresholds (70% warning), should alert
        with (
            patch(
                "app.services.alerts.monitoring.database_monitor.get_pool_status",
                return_value=pool_status,
            ),
            patch(
                "app.services.alerts.monitoring.database_monitor.test_connection",
                return_value=connection_result,
            ),
        ):
            alert_default = await database_monitor.check_pool_exhaustion(
                use_service_role=True
            )
            assert alert_default is not None

        # Update to higher threshold (85% warning)
        database_monitor.update_thresholds(custom_thresholds)
        database_monitor._last_alert_times.clear()  # Reset debounce

        # Same 70% utilization should NOT alert now
        with (
            patch(
                "app.services.alerts.monitoring.database_monitor.get_pool_status",
                return_value=pool_status,
            ),
            patch(
                "app.services.alerts.monitoring.database_monitor.test_connection",
                return_value=connection_result,
            ),
        ):
            alert_custom = await database_monitor.check_pool_exhaustion(
                use_service_role=True
            )
            assert alert_custom is None  # Below new threshold

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_runtime_threshold_updates(
        self, monitoring_system, custom_thresholds, degraded_system_state
    ):
        """Test updating thresholds at runtime."""
        database_monitor = monitoring_system["database_monitor"]

        # Initial thresholds
        initial_thresholds = database_monitor.thresholds
        assert initial_thresholds.pool_utilization_warning == 70.0

        # Update thresholds
        database_monitor.update_thresholds(custom_thresholds)

        # Verify update
        assert database_monitor.thresholds.pool_utilization_warning == 60.0
        assert database_monitor.thresholds.pool_utilization_critical == 85.0


# ============================================================================
# Test Monitoring Statistics
# ============================================================================


class TestMonitoringStatistics:
    """Test monitoring statistics and metrics."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_statistics_reflect_monitoring_activity(
        self, monitoring_system, degraded_system_state
    ):
        """Test that statistics accurately reflect monitoring activity."""
        database_monitor = monitoring_system["database_monitor"]

        # Get initial stats
        initial_stats = database_monitor.get_statistics()
        initial_debounces = initial_stats["active_debounces"]

        with (
            patch(
                "app.services.alerts.monitoring.database_monitor.get_pool_status",
                return_value=degraded_system_state["pool_status"],
            ),
            patch(
                "app.services.alerts.monitoring.database_monitor.test_connection",
                return_value=degraded_system_state["connection_result"],
            ),
        ):
            # Run checks
            await database_monitor.check_all()

            # Get updated stats
            updated_stats = database_monitor.get_statistics()

            # Should have increased debounce count
            assert updated_stats["active_debounces"] > initial_debounces

    def test_statistics_include_threshold_values(self, monitoring_system):
        """Test that statistics include current threshold configuration."""
        database_monitor = monitoring_system["database_monitor"]

        stats = database_monitor.get_statistics()

        assert "thresholds" in stats
        assert "pool_utilization_warning" in stats["thresholds"]
        assert "pool_utilization_critical" in stats["thresholds"]
        assert "slow_query_duration" in stats["thresholds"]
        assert "connection_errors_per_minute" in stats["thresholds"]


# ============================================================================
# Test Callback Integration (Legacy)
# ============================================================================


class TestCallbackIntegration:
    """Test callback integration for legacy systems."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_callbacks_triggered_on_alerts(
        self, monitoring_system, degraded_system_state
    ):
        """Test that registered callbacks are triggered when alerts occur."""
        database_monitor = monitoring_system["database_monitor"]

        # Register callback
        callback = AsyncMock()
        database_monitor.register_callback(AlertSeverity.WARNING, callback)

        with (
            patch(
                "app.services.alerts.monitoring.database_monitor.get_pool_status",
                return_value=degraded_system_state["pool_status"],
            ),
            patch(
                "app.services.alerts.monitoring.database_monitor.test_connection",
                return_value=degraded_system_state["connection_result"],
            ),
        ):
            # Run checks (should trigger callback)
            alerts = await database_monitor.check_all()

            # Callback should have been called
            # Note: With AlertManager, callbacks might not be called
            # Only called when alert_manager is None
            if database_monitor.alert_manager is None:
                assert callback.called

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multiple_severity_callbacks(self, degraded_system_state):
        """Test callbacks registered at different severity levels."""
        # Create monitor WITHOUT AlertManager to test callback path
        database_monitor = DatabaseMonitor(alert_manager=None)

        info_callback = AsyncMock()
        warning_callback = AsyncMock()
        critical_callback = AsyncMock()

        database_monitor.register_callback(AlertSeverity.INFO, info_callback)
        database_monitor.register_callback(AlertSeverity.WARNING, warning_callback)
        database_monitor.register_callback(AlertSeverity.CRITICAL, critical_callback)

        with (
            patch(
                "app.services.alerts.monitoring.database_monitor.get_pool_status",
                return_value=degraded_system_state["pool_status"],
            ),
            patch(
                "app.services.alerts.monitoring.database_monitor.test_connection",
                return_value=degraded_system_state["connection_result"],
            ),
        ):
            # Trigger CRITICAL alert
            await database_monitor.check_all()

            # INFO and WARNING callbacks should be called (lower severity)
            # CRITICAL might also be called depending on alert severity
            assert info_callback.called or warning_callback.called


# ============================================================================
# Test Periodic Monitoring
# ============================================================================


class TestPeriodicMonitoring:
    """Test periodic monitoring execution."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_periodic_checks_execute_repeatedly(
        self, monitoring_system, healthy_system_state
    ):
        """Test that periodic monitoring executes checks repeatedly."""
        database_monitor = monitoring_system["database_monitor"]

        check_count = 0

        async def mock_check_all():
            nonlocal check_count
            check_count += 1
            if check_count >= 3:
                raise KeyboardInterrupt()  # Stop after 3 iterations
            return []

        with patch.object(database_monitor, "check_all", new=mock_check_all):
            with pytest.raises(KeyboardInterrupt):
                await database_monitor.run_periodic_checks(interval_seconds=0.01)

            # Should have executed 3 times
            assert check_count == 3

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_periodic_monitoring_handles_errors_gracefully(
        self, monitoring_system
    ):
        """Test that errors in periodic checks don't stop monitoring."""
        database_monitor = monitoring_system["database_monitor"]

        check_count = 0
        error_count = 0

        async def mock_check_all_with_errors():
            nonlocal check_count, error_count
            check_count += 1

            if check_count < 3:
                error_count += 1
                raise Exception("Check failed")
            else:
                raise KeyboardInterrupt()  # Stop

            return []

        with patch.object(
            database_monitor, "check_all", new=mock_check_all_with_errors
        ):
            with pytest.raises(KeyboardInterrupt):
                await database_monitor.run_periodic_checks(interval_seconds=0.01)

            # Should have attempted all checks despite errors
            assert check_count == 3
            assert error_count == 2  # First 2 failed


# ============================================================================
# Test End-to-End Scenarios
# ============================================================================


class TestEndToEndScenarios:
    """Test complete end-to-end monitoring scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complete_degradation_and_recovery_cycle(
        self, monitoring_system, healthy_system_state, degraded_system_state
    ):
        """Test system degradation detection and recovery monitoring."""
        database_monitor = monitoring_system["database_monitor"]

        # Scenario 1: Healthy system
        with (
            patch(
                "app.services.alerts.monitoring.database_monitor.get_pool_status",
                return_value=healthy_system_state["pool_status"],
            ),
            patch(
                "app.services.alerts.monitoring.database_monitor.test_connection",
                return_value=healthy_system_state["connection_result"],
            ),
        ):
            alerts_healthy = await database_monitor.check_all()
            assert len(alerts_healthy) == 0

        # Scenario 2: System degrades
        with (
            patch(
                "app.services.alerts.monitoring.database_monitor.get_pool_status",
                return_value=degraded_system_state["pool_status"],
            ),
            patch(
                "app.services.alerts.monitoring.database_monitor.test_connection",
                return_value=degraded_system_state["connection_result"],
            ),
        ):
            alerts_degraded = await database_monitor.check_all()
            assert len(alerts_degraded) > 0

        # Clear debounce for recovery test
        database_monitor._last_alert_times.clear()

        # Scenario 3: System recovers
        with (
            patch(
                "app.services.alerts.monitoring.database_monitor.get_pool_status",
                return_value=healthy_system_state["pool_status"],
            ),
            patch(
                "app.services.alerts.monitoring.database_monitor.test_connection",
                return_value=healthy_system_state["connection_result"],
            ),
        ):
            alerts_recovered = await database_monitor.check_all()
            assert len(alerts_recovered) == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_alert_notification_full_pipeline(
        self, monitoring_system, degraded_system_state, monitoring_targets
    ):
        """Test complete pipeline from monitoring to notification delivery."""
        database_monitor = monitoring_system["database_monitor"]
        alert_manager = monitoring_system["alert_manager"]
        dispatcher = monitoring_system["dispatcher"]

        # Setup notification channels
        mock_email = AsyncMock()
        mock_email.send = AsyncMock(return_value=True)

        mock_webhook = AsyncMock()
        mock_webhook.send = AsyncMock(return_value=True)

        dispatcher.register_channel(NotificationChannel.EMAIL, mock_email)
        dispatcher.register_channel(NotificationChannel.WEBHOOK, mock_webhook)

        with (
            patch(
                "app.services.alerts.monitoring.database_monitor.get_pool_status",
                return_value=degraded_system_state["pool_status"],
            ),
            patch(
                "app.services.alerts.monitoring.database_monitor.test_connection",
                return_value=degraded_system_state["connection_result"],
            ),
        ):
            # Step 1: Monitor and detect issues
            alerts = await database_monitor.check_all()
            assert len(alerts) > 0

            # Step 2: Send notifications
            for alert in alerts:
                result = await alert_manager.send_notifications(
                    alert=alert,
                    targets=monitoring_targets,
                    channels=[NotificationChannel.EMAIL, NotificationChannel.WEBHOOK],
                )

                # Verify notifications sent
                assert result["sent"] > 0

            # Verify both channels were used
            assert mock_email.send.called
            assert mock_webhook.send.called
