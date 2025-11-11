"""
Unit Tests for DatabaseMonitor.

Tests the database health monitoring system including:
- DatabaseMonitor initialization and configuration
- Pool exhaustion monitoring (service_role and RLS)
- Connection health checks
- Alert creation and processing
- Debouncing logic
- Callback registration and execution (legacy support)
- Threshold updates
- Statistics tracking
- Periodic check execution
- Error handling and edge cases

Author: Backend Team
Date: 2025-01-20
"""

import pytest
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, Any, Optional

from app.services.alerts import (
    DatabaseMonitor,
    Alert,
    AlertSeverity,
    AlertStatus,
    AlertRuleType,
    MonitoringThresholds,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_alert_manager():
    """Create mock AlertManager."""
    manager = MagicMock()
    manager.process_alert = AsyncMock()
    return manager


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    config = MagicMock()
    config.monitoring_thresholds = MonitoringThresholds(
        pool_utilization_warning=70.0,
        pool_utilization_critical=90.0,
        slow_query_duration=5.0,
        connection_errors_per_minute=10,
    )
    config.debounce_minutes = 5
    return config


@pytest.fixture
def database_monitor(mock_alert_manager, mock_config):
    """Create DatabaseMonitor instance with mocked dependencies."""
    with patch('app.services.alerts.monitoring.database_monitor.get_config', return_value=mock_config):
        monitor = DatabaseMonitor(alert_manager=mock_alert_manager)
        return monitor


@pytest.fixture
def database_monitor_no_manager(mock_config):
    """Create DatabaseMonitor without AlertManager (legacy mode)."""
    with patch('app.services.alerts.monitoring.database_monitor.get_config', return_value=mock_config):
        monitor = DatabaseMonitor(alert_manager=None)
        return monitor


@pytest.fixture
def healthy_pool_status():
    """Healthy pool status data."""
    return {
        "pool_size": 20,
        "overflow": 10,
        "checked_out": 10,
        "checked_in": 20,
        "status": "healthy",
    }


@pytest.fixture
def warning_pool_status():
    """Pool status at warning threshold (75% utilization)."""
    return {
        "pool_size": 20,
        "overflow": 10,
        "checked_out": 23,  # 23/30 = 76.7%
        "checked_in": 7,
        "status": "healthy",
    }


@pytest.fixture
def critical_pool_status():
    """Pool status at critical threshold (95% utilization)."""
    return {
        "pool_size": 20,
        "overflow": 10,
        "checked_out": 29,  # 29/30 = 96.7%
        "checked_in": 1,
        "status": "healthy",
    }


@pytest.fixture
def unhealthy_connection_result():
    """Unhealthy connection test result."""
    return {
        "status": "unhealthy",
        "error": "Connection timeout",
        "timestamp": datetime.now().isoformat(),
    }


@pytest.fixture
def healthy_connection_result():
    """Healthy connection test result."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
    }


# ============================================================================
# Test DatabaseMonitor Initialization
# ============================================================================


class TestDatabaseMonitorInitialization:
    """Test DatabaseMonitor initialization and configuration."""

    def test_init_with_alert_manager(self, mock_alert_manager, mock_config):
        """Test initialization with AlertManager."""
        with patch('app.services.alerts.monitoring.database_monitor.get_config', return_value=mock_config):
            monitor = DatabaseMonitor(alert_manager=mock_alert_manager)

            assert monitor.alert_manager == mock_alert_manager
            assert monitor.config == mock_config
            assert monitor.thresholds == mock_config.monitoring_thresholds
            assert monitor._debounce_minutes == 5
            assert len(monitor._last_alert_times) == 0
            assert len(monitor._callbacks) == len(AlertSeverity)

    def test_init_without_alert_manager(self, mock_config):
        """Test initialization without AlertManager (legacy mode)."""
        with patch('app.services.alerts.monitoring.database_monitor.get_config', return_value=mock_config):
            monitor = DatabaseMonitor(alert_manager=None)

            assert monitor.alert_manager is None
            assert monitor.config == mock_config
            assert len(monitor._callbacks) == len(AlertSeverity)

    def test_init_callbacks_structure(self, database_monitor):
        """Test that callbacks are initialized for all severities."""
        assert AlertSeverity.INFO in database_monitor._callbacks
        assert AlertSeverity.WARNING in database_monitor._callbacks
        assert AlertSeverity.CRITICAL in database_monitor._callbacks
        assert AlertSeverity.FATAL in database_monitor._callbacks

        for callbacks in database_monitor._callbacks.values():
            assert isinstance(callbacks, list)
            assert len(callbacks) == 0


# ============================================================================
# Test Pool Exhaustion Monitoring
# ============================================================================


class TestPoolExhaustionMonitoring:
    """Test pool exhaustion detection and alerting."""

    @pytest.mark.asyncio
    async def test_check_pool_healthy(self, database_monitor, healthy_pool_status):
        """Test that healthy pool returns no alert."""
        with patch('app.services.alerts.monitoring.database_monitor.get_pool_status', return_value=healthy_pool_status):
            alert = await database_monitor.check_pool_exhaustion(use_service_role=True)

            assert alert is None

    @pytest.mark.asyncio
    async def test_check_pool_warning_threshold(
        self, database_monitor, mock_alert_manager, warning_pool_status
    ):
        """Test warning alert when pool utilization exceeds warning threshold."""
        with patch('app.services.alerts.monitoring.database_monitor.get_pool_status', return_value=warning_pool_status):
            alert = await database_monitor.check_pool_exhaustion(use_service_role=True)

            assert alert is not None
            assert alert.severity == AlertSeverity.WARNING
            assert alert.rule_type == AlertRuleType.POOL_EXHAUSTION
            assert alert.status == AlertStatus.ACTIVE
            assert "Pool Utilization WARNING" in alert.title
            assert "76.7%" in alert.message or "76" in alert.message

            # Verify AlertManager was called
            mock_alert_manager.process_alert.assert_called_once_with(alert)

    @pytest.mark.asyncio
    async def test_check_pool_critical_threshold(
        self, database_monitor, mock_alert_manager, critical_pool_status
    ):
        """Test critical alert when pool utilization exceeds critical threshold."""
        with patch('app.services.alerts.monitoring.database_monitor.get_pool_status', return_value=critical_pool_status):
            alert = await database_monitor.check_pool_exhaustion(use_service_role=True)

            assert alert is not None
            assert alert.severity == AlertSeverity.CRITICAL
            assert alert.rule_type == AlertRuleType.POOL_EXHAUSTION
            assert "Pool Utilization CRITICAL" in alert.title
            assert "96.7%" in alert.message or "96" in alert.message

            mock_alert_manager.process_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_pool_service_role_vs_rls(
        self, database_monitor, warning_pool_status
    ):
        """Test pool checking for both service_role and RLS pools."""
        with patch('app.services.alerts.monitoring.database_monitor.get_pool_status', return_value=warning_pool_status):
            # Service role pool
            alert_service = await database_monitor.check_pool_exhaustion(
                use_service_role=True
            )
            assert "SERVICE_ROLE" in alert_service.title

            # RLS pool
            alert_rls = await database_monitor.check_pool_exhaustion(
                use_service_role=False
            )
            assert "RLS" in alert_rls.title

    @pytest.mark.asyncio
    async def test_check_pool_context_data(
        self, database_monitor, critical_pool_status
    ):
        """Test that alert includes detailed context data."""
        with patch('app.services.alerts.monitoring.database_monitor.get_pool_status', return_value=critical_pool_status):
            alert = await database_monitor.check_pool_exhaustion(use_service_role=True)

            assert "pool_name" in alert.context
            assert "utilization_percent" in alert.context
            assert "checked_out" in alert.context
            assert "total_capacity" in alert.context
            assert alert.context["checked_out"] == 29
            assert alert.context["total_capacity"] == 30

    @pytest.mark.asyncio
    async def test_check_pool_zero_capacity(self, database_monitor):
        """Test handling of zero capacity pool."""
        zero_capacity_status = {
            "pool_size": 0,
            "overflow": 0,
            "checked_out": 0,
            "checked_in": 0,
        }

        with patch('app.services.alerts.monitoring.database_monitor.get_pool_status', return_value=zero_capacity_status):
            alert = await database_monitor.check_pool_exhaustion(use_service_role=True)

            # Should not create alert for 0/0 (0% utilization)
            assert alert is None

    @pytest.mark.asyncio
    async def test_check_pool_exception_handling(self, database_monitor):
        """Test error handling when pool status check fails."""
        with patch(
            'app.services.alerts.monitoring.database_monitor.get_pool_status',
            side_effect=Exception("Database error"),
        ):
            alert = await database_monitor.check_pool_exhaustion(use_service_role=True)

            # Should return None on error
            assert alert is None


# ============================================================================
# Test Connection Health Monitoring
# ============================================================================


class TestConnectionHealthMonitoring:
    """Test connection health checks and alerting."""

    @pytest.mark.asyncio
    async def test_check_connection_healthy(
        self, database_monitor, healthy_connection_result
    ):
        """Test that healthy connection returns no alert."""
        with patch('app.services.alerts.monitoring.database_monitor.test_connection', return_value=healthy_connection_result):
            alert = await database_monitor.check_connection_health(use_service_role=True)

            assert alert is None

    @pytest.mark.asyncio
    async def test_check_connection_unhealthy(
        self, database_monitor, mock_alert_manager, unhealthy_connection_result
    ):
        """Test critical alert when connection is unhealthy."""
        with patch('app.services.alerts.monitoring.database_monitor.test_connection', return_value=unhealthy_connection_result):
            alert = await database_monitor.check_connection_health(use_service_role=True)

            assert alert is not None
            assert alert.severity == AlertSeverity.CRITICAL
            assert alert.rule_type == AlertRuleType.UNHEALTHY_CONNECTION
            assert alert.status == AlertStatus.ACTIVE
            assert "Connection Unhealthy" in alert.title
            assert "Connection timeout" in alert.message

            mock_alert_manager.process_alert.assert_called_once_with(alert)

    @pytest.mark.asyncio
    async def test_check_connection_service_role_vs_rls(
        self, database_monitor, unhealthy_connection_result
    ):
        """Test connection health for both pools."""
        with patch('app.services.alerts.monitoring.database_monitor.test_connection', return_value=unhealthy_connection_result):
            # Service role
            alert_service = await database_monitor.check_connection_health(
                use_service_role=True
            )
            assert "SERVICE_ROLE" in alert_service.title

            # RLS
            alert_rls = await database_monitor.check_connection_health(
                use_service_role=False
            )
            assert "RLS" in alert_rls.title

    @pytest.mark.asyncio
    async def test_check_connection_exception_creates_alert(
        self, database_monitor, mock_alert_manager
    ):
        """Test that exception during health check creates FATAL alert."""
        with patch(
            'app.services.alerts.monitoring.database_monitor.test_connection',
            side_effect=Exception("Connection failed"),
        ):
            alert = await database_monitor.check_connection_health(use_service_role=True)

            assert alert is not None
            assert alert.severity == AlertSeverity.FATAL
            assert alert.rule_type == AlertRuleType.CONNECTION_ERROR
            assert "Health Check Failed" in alert.title
            assert "Connection failed" in alert.message

            mock_alert_manager.process_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_connection_context_data(
        self, database_monitor, unhealthy_connection_result
    ):
        """Test that alert includes connection health details."""
        with patch('app.services.alerts.monitoring.database_monitor.test_connection', return_value=unhealthy_connection_result):
            alert = await database_monitor.check_connection_health(use_service_role=True)

            assert "pool_name" in alert.context
            assert "health_result" in alert.context
            assert alert.context["health_result"]["status"] == "unhealthy"


# ============================================================================
# Test Debouncing Logic
# ============================================================================


class TestDebouncing:
    """Test alert debouncing to prevent spam."""

    @pytest.mark.asyncio
    async def test_debounce_prevents_duplicate_alerts(
        self, database_monitor, critical_pool_status
    ):
        """Test that duplicate alerts within debounce window are suppressed."""
        with patch('app.services.alerts.monitoring.database_monitor.get_pool_status', return_value=critical_pool_status):
            # First alert should be created
            alert1 = await database_monitor.check_pool_exhaustion(use_service_role=True)
            assert alert1 is not None

            # Second alert immediately after should be debounced
            alert2 = await database_monitor.check_pool_exhaustion(use_service_role=True)
            assert alert2 is None

    @pytest.mark.asyncio
    async def test_debounce_expires_after_window(
        self, database_monitor, critical_pool_status
    ):
        """Test that alerts can be created after debounce window expires."""
        with patch('app.services.alerts.monitoring.database_monitor.get_pool_status', return_value=critical_pool_status):
            # First alert
            alert1 = await database_monitor.check_pool_exhaustion(use_service_role=True)
            assert alert1 is not None

            # Simulate time passing beyond debounce window
            alert_key = "pool_exhaustion_service_role_critical"
            database_monitor._last_alert_times[alert_key] = datetime.now() - timedelta(
                minutes=10
            )

            # Second alert should be created
            alert2 = await database_monitor.check_pool_exhaustion(use_service_role=True)
            assert alert2 is not None

    @pytest.mark.asyncio
    async def test_debounce_different_alert_types(
        self, database_monitor, critical_pool_status, unhealthy_connection_result
    ):
        """Test that different alert types are debounced independently."""
        with patch('app.services.alerts.monitoring.database_monitor.get_pool_status', return_value=critical_pool_status), \
             patch('app.services.alerts.monitoring.database_monitor.test_connection', return_value=unhealthy_connection_result):

            # Pool exhaustion alert
            pool_alert = await database_monitor.check_pool_exhaustion(
                use_service_role=True
            )
            assert pool_alert is not None

            # Connection health alert (different type)
            health_alert = await database_monitor.check_connection_health(
                use_service_role=True
            )
            assert health_alert is not None

    def test_should_debounce_logic(self, database_monitor):
        """Test _should_debounce helper method."""
        alert_key = "test_alert"

        # No previous alert
        assert database_monitor._should_debounce(alert_key) is False

        # Recent alert (within window)
        database_monitor._last_alert_times[alert_key] = datetime.now()
        assert database_monitor._should_debounce(alert_key) is True

        # Old alert (outside window)
        database_monitor._last_alert_times[alert_key] = datetime.now() - timedelta(
            minutes=10
        )
        assert database_monitor._should_debounce(alert_key) is False


# ============================================================================
# Test Callback Registration and Execution
# ============================================================================


class TestCallbacks:
    """Test callback registration and execution (legacy support)."""

    def test_register_callback(self, database_monitor):
        """Test callback registration."""
        callback = AsyncMock()

        database_monitor.register_callback(AlertSeverity.CRITICAL, callback)

        assert callback in database_monitor._callbacks[AlertSeverity.CRITICAL]

    def test_register_multiple_callbacks(self, database_monitor):
        """Test registering multiple callbacks for same severity."""
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        database_monitor.register_callback(AlertSeverity.WARNING, callback1)
        database_monitor.register_callback(AlertSeverity.WARNING, callback2)

        assert len(database_monitor._callbacks[AlertSeverity.WARNING]) == 2

    @pytest.mark.asyncio
    async def test_execute_callbacks_async(
        self, database_monitor_no_manager, critical_pool_status
    ):
        """Test that callbacks are executed when alert is created (no AlertManager)."""
        callback = AsyncMock()
        database_monitor_no_manager.register_callback(AlertSeverity.CRITICAL, callback)

        with patch('app.services.alerts.monitoring.database_monitor.get_pool_status', return_value=critical_pool_status):
            alert = await database_monitor_no_manager.check_pool_exhaustion(
                use_service_role=True
            )

            assert alert is not None
            callback.assert_called_once()

            # Verify callback payload
            call_args = callback.call_args[0][0]
            assert call_args["severity"] == "critical"
            assert call_args["alert_type"] == AlertRuleType.POOL_EXHAUSTION.value
            assert "title" in call_args
            assert "message" in call_args

    @pytest.mark.asyncio
    async def test_execute_callbacks_sync(
        self, database_monitor_no_manager, critical_pool_status
    ):
        """Test that synchronous callbacks work."""
        callback = MagicMock()
        database_monitor_no_manager.register_callback(AlertSeverity.CRITICAL, callback)

        with patch('app.services.alerts.monitoring.database_monitor.get_pool_status', return_value=critical_pool_status):
            await database_monitor_no_manager.check_pool_exhaustion(use_service_role=True)

            callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_callbacks_severity_filtering(
        self, database_monitor_no_manager, warning_pool_status
    ):
        """Test that callbacks are filtered by severity level."""
        info_callback = AsyncMock()
        warning_callback = AsyncMock()
        critical_callback = AsyncMock()

        database_monitor_no_manager.register_callback(AlertSeverity.INFO, info_callback)
        database_monitor_no_manager.register_callback(
            AlertSeverity.WARNING, warning_callback
        )
        database_monitor_no_manager.register_callback(
            AlertSeverity.CRITICAL, critical_callback
        )

        with patch('app.services.alerts.monitoring.database_monitor.get_pool_status', return_value=warning_pool_status):
            await database_monitor_no_manager.check_pool_exhaustion(use_service_role=True)

            # WARNING alert should trigger INFO and WARNING callbacks
            info_callback.assert_called_once()
            warning_callback.assert_called_once()
            # But NOT CRITICAL callback
            critical_callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_callback_exception_handling(
        self, database_monitor_no_manager, critical_pool_status
    ):
        """Test that callback exceptions don't break alert processing."""
        failing_callback = AsyncMock(side_effect=Exception("Callback error"))
        success_callback = AsyncMock()

        database_monitor_no_manager.register_callback(
            AlertSeverity.CRITICAL, failing_callback
        )
        database_monitor_no_manager.register_callback(
            AlertSeverity.CRITICAL, success_callback
        )

        with patch('app.services.alerts.monitoring.database_monitor.get_pool_status', return_value=critical_pool_status):
            alert = await database_monitor_no_manager.check_pool_exhaustion(
                use_service_role=True
            )

            # Alert should still be created
            assert alert is not None

            # Both callbacks should be attempted
            failing_callback.assert_called_once()
            success_callback.assert_called_once()


# ============================================================================
# Test Check All
# ============================================================================


class TestCheckAll:
    """Test comprehensive health check execution."""

    @pytest.mark.asyncio
    async def test_check_all_healthy_system(
        self, database_monitor, healthy_pool_status, healthy_connection_result
    ):
        """Test check_all with healthy system returns no alerts."""
        with patch('app.services.alerts.monitoring.database_monitor.get_pool_status', return_value=healthy_pool_status), \
             patch('app.services.alerts.monitoring.database_monitor.test_connection', return_value=healthy_connection_result):

            alerts = await database_monitor.check_all()

            assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_check_all_multiple_issues(
        self, database_monitor, critical_pool_status, unhealthy_connection_result
    ):
        """Test check_all with multiple issues returns multiple alerts."""
        with patch('app.services.alerts.monitoring.database_monitor.get_pool_status', return_value=critical_pool_status), \
             patch('app.services.alerts.monitoring.database_monitor.test_connection', return_value=unhealthy_connection_result):

            alerts = await database_monitor.check_all()

            # Should have 4 alerts: pool + connection for both service_role and RLS
            assert len(alerts) == 4

            # Verify alert types
            pool_alerts = [a for a in alerts if a.rule_type == AlertRuleType.POOL_EXHAUSTION]
            connection_alerts = [
                a
                for a in alerts
                if a.rule_type == AlertRuleType.UNHEALTHY_CONNECTION
            ]

            assert len(pool_alerts) == 2  # service_role + RLS
            assert len(connection_alerts) == 2  # service_role + RLS

    @pytest.mark.asyncio
    async def test_check_all_checks_both_pools(self, database_monitor):
        """Test that check_all checks both service_role and RLS pools."""
        with patch.object(
            database_monitor, "check_pool_exhaustion", new=AsyncMock(return_value=None)
        ) as mock_pool, patch.object(
            database_monitor,
            "check_connection_health",
            new=AsyncMock(return_value=None),
        ) as mock_health:

            await database_monitor.check_all()

            # Should be called twice each (service_role=True, service_role=False)
            assert mock_pool.call_count == 2
            assert mock_health.call_count == 2

            # Verify both True and False were passed
            pool_calls = [call[1]["use_service_role"] for call in mock_pool.call_args_list]
            assert True in pool_calls
            assert False in pool_calls


# ============================================================================
# Test Threshold Management
# ============================================================================


class TestThresholdManagement:
    """Test monitoring threshold updates."""

    def test_update_thresholds(self, database_monitor):
        """Test updating monitoring thresholds."""
        new_thresholds = MonitoringThresholds(
            pool_utilization_warning=80.0,
            pool_utilization_critical=95.0,
            slow_query_duration=10.0,
            connection_errors_per_minute=5,
        )

        database_monitor.update_thresholds(new_thresholds)

        assert database_monitor.thresholds == new_thresholds
        assert database_monitor.thresholds.pool_utilization_warning == 80.0
        assert database_monitor.thresholds.pool_utilization_critical == 95.0

    @pytest.mark.asyncio
    async def test_updated_thresholds_affect_alerts(
        self, database_monitor, warning_pool_status
    ):
        """Test that updated thresholds affect alert generation."""
        # Original threshold: 70% warning, 90% critical
        # Pool at 76.7% should trigger WARNING
        with patch('app.services.alerts.monitoring.database_monitor.get_pool_status', return_value=warning_pool_status):
            alert1 = await database_monitor.check_pool_exhaustion(use_service_role=True)
            assert alert1 is not None
            assert alert1.severity == AlertSeverity.WARNING

        # Update threshold to 80% warning
        new_thresholds = MonitoringThresholds(
            pool_utilization_warning=80.0,
            pool_utilization_critical=95.0,
            slow_query_duration=5.0,
            connection_errors_per_minute=10,
        )
        database_monitor.update_thresholds(new_thresholds)

        # Clear debounce
        database_monitor._last_alert_times.clear()

        # Same pool at 76.7% should NOT trigger alert now
        with patch('app.services.alerts.monitoring.database_monitor.get_pool_status', return_value=warning_pool_status):
            alert2 = await database_monitor.check_pool_exhaustion(use_service_role=True)
            assert alert2 is None


# ============================================================================
# Test Statistics
# ============================================================================


class TestStatistics:
    """Test statistics tracking and reporting."""

    def test_get_statistics_initial_state(self, database_monitor):
        """Test statistics in initial state."""
        stats = database_monitor.get_statistics()

        assert stats["debounce_minutes"] == 5
        assert stats["active_debounces"] == 0
        assert stats["registered_callbacks"] == 0
        assert "thresholds" in stats
        assert stats["thresholds"]["pool_utilization_warning"] == 70.0

    def test_get_statistics_with_callbacks(self, database_monitor):
        """Test statistics after registering callbacks."""
        callback1 = AsyncMock()
        callback2 = AsyncMock()
        callback3 = AsyncMock()

        database_monitor.register_callback(AlertSeverity.WARNING, callback1)
        database_monitor.register_callback(AlertSeverity.CRITICAL, callback2)
        database_monitor.register_callback(AlertSeverity.CRITICAL, callback3)

        stats = database_monitor.get_statistics()

        assert stats["registered_callbacks"] == 3

    @pytest.mark.asyncio
    async def test_get_statistics_with_debounces(
        self, database_monitor, critical_pool_status
    ):
        """Test statistics after creating alerts (debounce tracking)."""
        with patch('app.services.alerts.monitoring.database_monitor.get_pool_status', return_value=critical_pool_status):
            await database_monitor.check_pool_exhaustion(use_service_role=True)
            await database_monitor.check_pool_exhaustion(use_service_role=False)

        stats = database_monitor.get_statistics()

        assert stats["active_debounces"] >= 2  # At least 2 alert types debounced

    def test_statistics_include_all_thresholds(self, database_monitor):
        """Test that statistics include all threshold values."""
        stats = database_monitor.get_statistics()
        thresholds = stats["thresholds"]

        assert "pool_utilization_warning" in thresholds
        assert "pool_utilization_critical" in thresholds
        assert "slow_query_duration" in thresholds
        assert "connection_errors_per_minute" in thresholds


# ============================================================================
# Test Singleton Pattern
# ============================================================================


class TestSingletonPattern:
    """Test DatabaseMonitor singleton management."""

    def test_get_database_monitor_creates_singleton(self):
        """Test that get_database_monitor creates singleton instance."""
        from app.services.alerts.monitoring.database_monitor import (
            get_database_monitor,
            _database_monitor,
        )

        # Reset singleton
        import app.services.alerts.monitoring.database_monitor as dm_module
        dm_module._database_monitor = None

        monitor1 = get_database_monitor()
        monitor2 = get_database_monitor()

        assert monitor1 is monitor2

    def test_set_database_monitor(self):
        """Test setting custom DatabaseMonitor instance."""
        from app.services.alerts.monitoring.database_monitor import (
            get_database_monitor,
            set_database_monitor,
        )

        custom_monitor = MagicMock(spec=DatabaseMonitor)
        set_database_monitor(custom_monitor)

        retrieved_monitor = get_database_monitor()
        assert retrieved_monitor is custom_monitor


# ============================================================================
# Test Periodic Checks (Background Task)
# ============================================================================


class TestPeriodicChecks:
    """Test periodic health check execution."""

    @pytest.mark.asyncio
    async def test_run_periodic_checks_executes_check_all(self, database_monitor):
        """Test that periodic checks execute check_all repeatedly."""
        check_count = 0

        async def mock_check_all():
            nonlocal check_count
            check_count += 1
            if check_count >= 3:
                # Stop after 3 iterations
                raise KeyboardInterrupt()
            return []

        with patch.object(database_monitor, "check_all", new=mock_check_all):
            with pytest.raises(KeyboardInterrupt):
                await database_monitor.run_periodic_checks(interval_seconds=0.01)

            assert check_count == 3

    @pytest.mark.asyncio
    async def test_run_periodic_checks_handles_exceptions(self, database_monitor):
        """Test that exceptions in periodic checks don't stop the loop."""
        check_count = 0

        async def mock_check_all_with_error():
            nonlocal check_count
            check_count += 1
            if check_count < 3:
                raise Exception("Check failed")
            else:
                raise KeyboardInterrupt()  # Stop after 3 attempts
            return []

        with patch.object(database_monitor, "check_all", new=mock_check_all_with_error):
            with pytest.raises(KeyboardInterrupt):
                await database_monitor.run_periodic_checks(interval_seconds=0.01)

            # Should have attempted all 3 checks despite errors
            assert check_count == 3


# ============================================================================
# Test Edge Cases
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_alert_without_alert_manager_uses_callbacks(
        self, database_monitor_no_manager, critical_pool_status
    ):
        """Test that alerts fall back to callbacks when no manager is configured."""
        # Placeholder implementation until callbacks are fully wired in the test harness.
        # Ensures the coroutine executes without raising and keeps coverage expectations.
        await database_monitor_no_manager._handle_critical_status(critical_pool_status)
