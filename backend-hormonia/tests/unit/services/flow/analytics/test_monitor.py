"""
Unit Tests for FlowMonitor - QW-021 Flow Services Consolidation.

Tests health monitoring, system health calculation, and alert generation for the
consolidated flow analytics system.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.services.flow.analytics.monitor import (
    FlowMonitor,
    FlowHealthMetrics,
    HealthStatus,
)
from app.services.flow.types import (
    FlowContext,
    FlowType,
    FlowStatus,
    FlowPriority,
    FlowStepData,
    FlowStepType,
    FlowStepStatus,
)


@pytest.fixture
def monitor():
    """Create FlowMonitor instance."""
    return FlowMonitor()


@pytest.fixture
def flow_instance_id():
    """Create test flow instance ID."""
    return uuid4()


@pytest.fixture
def sample_flow_context(flow_instance_id):
    """Create sample flow context for testing."""
    return FlowContext(
        flow_instance_id=flow_instance_id,
        flow_type=FlowType.DAILY_CHECKIN,
        patient_id=uuid4(),
        status=FlowStatus.ACTIVE,
        started_at=datetime.utcnow() - timedelta(minutes=5),
    )


@pytest.fixture
def healthy_context(flow_instance_id):
    """Create healthy flow context."""
    context = FlowContext(
        flow_instance_id=flow_instance_id,
        flow_type=FlowType.DAILY_CHECKIN,
        patient_id=uuid4(),
        status=FlowStatus.ACTIVE,
        started_at=datetime.utcnow() - timedelta(minutes=2),
    )
    context.steps_history = [
        FlowStepData(
            step_id=f"step_{i}",
            step_type=FlowStepType.MESSAGE,
            step_name=f"Step {i}",
            status=FlowStepStatus.COMPLETED,
        )
        for i in range(3)
    ]
    return context


@pytest.fixture
def unhealthy_context(flow_instance_id):
    """Create unhealthy flow context (high error rate)."""
    context = FlowContext(
        flow_instance_id=flow_instance_id,
        flow_type=FlowType.DAILY_CHECKIN,
        patient_id=uuid4(),
        status=FlowStatus.ACTIVE,
        started_at=datetime.utcnow() - timedelta(hours=2),
    )
    # High failure rate
    context.steps_history = [
        FlowStepData(
            step_id=f"step_{i}",
            step_type=FlowStepType.MESSAGE,
            step_name=f"Step {i}",
            status=FlowStepStatus.FAILED if i % 2 == 0 else FlowStepStatus.COMPLETED,
            error="Test error" if i % 2 == 0 else None,
        )
        for i in range(10)
    ]
    return context


class TestFlowMonitorInitialization:
    """Test FlowMonitor initialization."""

    def test_initialization(self, monitor):
        """Test monitor initializes correctly."""
        assert monitor is not None
        assert monitor.config is not None
        assert len(monitor._flow_health) == 0
        assert len(monitor._active_flows) == 0

    def test_configuration_loaded(self, monitor):
        """Test configuration is loaded."""
        assert monitor.max_execution_time_seconds is not None
        assert monitor.max_step_failures_percentage is not None
        assert monitor.max_error_count is not None

    def test_initial_system_health(self, monitor):
        """Test initial system health is HEALTHY."""
        assert monitor._system_health_status == HealthStatus.HEALTHY


class TestFlowHealthMonitoring:
    """Test flow-level health monitoring."""

    def test_start_monitoring(self, monitor, flow_instance_id):
        """Test starting flow monitoring."""
        monitor.start_monitoring(flow_instance_id)

        assert flow_instance_id in monitor._flow_health
        assert flow_instance_id in monitor._active_flows

        metrics = monitor._flow_health[flow_instance_id]
        assert isinstance(metrics, FlowHealthMetrics)
        assert metrics.status == HealthStatus.HEALTHY

    def test_start_monitoring_disabled(self, monitor, flow_instance_id):
        """Test monitoring when health checks are disabled."""
        monitor.config.analytics.enable_health_checks = False

        monitor.start_monitoring(flow_instance_id)

        assert flow_instance_id not in monitor._flow_health

    def test_stop_monitoring(self, monitor, flow_instance_id):
        """Test stopping flow monitoring."""
        monitor.start_monitoring(flow_instance_id)
        assert flow_instance_id in monitor._active_flows

        monitor.stop_monitoring(flow_instance_id)

        assert flow_instance_id not in monitor._active_flows

    def test_check_flow_health_healthy(
        self, monitor, flow_instance_id, healthy_context
    ):
        """Test checking health of healthy flow."""
        monitor.start_monitoring(flow_instance_id)

        metrics = monitor.check_flow_health(flow_instance_id, healthy_context)

        assert metrics.status == HealthStatus.HEALTHY
        assert len(metrics.issues) == 0
        assert metrics.steps_executed == 3
        assert metrics.steps_failed == 0

    def test_check_flow_health_unhealthy(
        self, monitor, flow_instance_id, unhealthy_context
    ):
        """Test checking health of unhealthy flow."""
        monitor.start_monitoring(flow_instance_id)

        metrics = monitor.check_flow_health(flow_instance_id, unhealthy_context)

        assert metrics.status == HealthStatus.UNHEALTHY
        assert len(metrics.issues) > 0
        assert metrics.error_rate_high is True

    def test_check_flow_health_timeout(self, monitor, flow_instance_id):
        """Test health check for timed out flow."""
        monitor.start_monitoring(flow_instance_id)

        # Create context with long execution time
        context = FlowContext(
            flow_instance_id=flow_instance_id,
            flow_type=FlowType.DAILY_CHECKIN,
            patient_id=uuid4(),
            status=FlowStatus.ACTIVE,
            started_at=datetime.utcnow() - timedelta(hours=2),
        )

        metrics = monitor.check_flow_health(flow_instance_id, context)

        assert metrics.timeout_exceeded is True
        assert any("timeout" in issue.lower() for issue in metrics.issues)

    def test_check_flow_health_expired(self, monitor, flow_instance_id):
        """Test health check for expired flow."""
        monitor.start_monitoring(flow_instance_id)

        context = FlowContext(
            flow_instance_id=flow_instance_id,
            flow_type=FlowType.DAILY_CHECKIN,
            patient_id=uuid4(),
            status=FlowStatus.ACTIVE,
            started_at=datetime.utcnow() - timedelta(minutes=5),
            expires_at=datetime.utcnow() - timedelta(minutes=1),
        )

        metrics = monitor.check_flow_health(flow_instance_id, context)

        assert any("expired" in issue.lower() for issue in metrics.issues)

    def test_check_flow_health_high_priority_paused(self, monitor, flow_instance_id):
        """Test health check for paused high-priority flow."""
        monitor.start_monitoring(flow_instance_id)

        context = FlowContext(
            flow_instance_id=flow_instance_id,
            flow_type=FlowType.EMERGENCY_PROTOCOL,
            patient_id=uuid4(),
            status=FlowStatus.PAUSED,
            priority=FlowPriority.CRITICAL,
        )

        metrics = monitor.check_flow_health(flow_instance_id, context)

        assert any("paused" in warning.lower() for warning in metrics.warnings)


class TestErrorTracking:
    """Test error tracking functionality."""

    def test_record_flow_error(self, monitor, flow_instance_id):
        """Test recording flow error."""
        monitor.start_monitoring(flow_instance_id)

        error = Exception("Test error")
        monitor.record_flow_error(flow_instance_id, error)

        metrics = monitor._flow_health[flow_instance_id]
        assert metrics.error_count == 1

    def test_record_multiple_errors(self, monitor, flow_instance_id):
        """Test recording multiple errors."""
        monitor.start_monitoring(flow_instance_id)

        for i in range(3):
            error = Exception(f"Error {i}")
            monitor.record_flow_error(flow_instance_id, error)

        metrics = monitor._flow_health[flow_instance_id]
        assert metrics.error_count == 3

    def test_record_error_exceeds_max(self, monitor, flow_instance_id):
        """Test error count exceeding maximum."""
        monitor.start_monitoring(flow_instance_id)

        for i in range(monitor.max_error_count + 1):
            error = Exception(f"Error {i}")
            monitor.record_flow_error(flow_instance_id, error)

        metrics = monitor._flow_health[flow_instance_id]
        assert metrics.error_count > monitor.max_error_count
        assert any("error count" in issue.lower() for issue in metrics.issues)
        assert metrics.status != HealthStatus.HEALTHY


class TestRetryTracking:
    """Test retry tracking functionality."""

    def test_record_flow_retry(self, monitor, flow_instance_id):
        """Test recording flow retry."""
        monitor.start_monitoring(flow_instance_id)

        monitor.record_flow_retry(flow_instance_id)

        metrics = monitor._flow_health[flow_instance_id]
        assert metrics.retry_count == 1

    def test_record_multiple_retries(self, monitor, flow_instance_id):
        """Test recording multiple retries."""
        monitor.start_monitoring(flow_instance_id)

        for i in range(3):
            monitor.record_flow_retry(flow_instance_id)

        metrics = monitor._flow_health[flow_instance_id]
        assert metrics.retry_count == 3

    def test_record_retry_exceeds_max(self, monitor, flow_instance_id):
        """Test retry count exceeding maximum."""
        monitor.start_monitoring(flow_instance_id)

        max_retries = monitor.config.execution.max_step_retries
        for i in range(max_retries + 1):
            monitor.record_flow_retry(flow_instance_id)

        metrics = monitor._flow_health[flow_instance_id]
        assert metrics.max_retries_exceeded is True
        assert any("retry" in issue.lower() for issue in metrics.issues)


class TestSystemHealthMonitoring:
    """Test system-wide health monitoring."""

    def test_check_system_health_no_flows(self, monitor):
        """Test system health with no active flows."""
        health = monitor.check_system_health()

        assert health["status"] == HealthStatus.HEALTHY.value
        assert health["active_flows"] == 0

    def test_check_system_health_all_healthy(self, monitor):
        """Test system health with all healthy flows."""
        # Create multiple healthy flows
        for i in range(5):
            flow_id = uuid4()
            monitor.start_monitoring(flow_id)

            context = FlowContext(
                flow_instance_id=flow_id,
                flow_type=FlowType.DAILY_CHECKIN,
                patient_id=uuid4(),
                status=FlowStatus.ACTIVE,
                started_at=datetime.utcnow() - timedelta(minutes=2),
            )
            monitor.check_flow_health(flow_id, context)

        health = monitor.check_system_health()

        assert health["status"] == HealthStatus.HEALTHY.value
        assert health["healthy_flows"] == 5

    def test_check_system_health_some_unhealthy(self, monitor):
        """Test system health with some unhealthy flows."""
        # Create healthy flows
        for i in range(8):
            flow_id = uuid4()
            monitor.start_monitoring(flow_id)
            context = FlowContext(
                flow_instance_id=flow_id,
                flow_type=FlowType.DAILY_CHECKIN,
                patient_id=uuid4(),
                status=FlowStatus.ACTIVE,
                started_at=datetime.utcnow() - timedelta(minutes=2),
            )
            monitor.check_flow_health(flow_id, context)

        # Create unhealthy flow
        unhealthy_id = uuid4()
        monitor.start_monitoring(unhealthy_id)
        for i in range(monitor.max_error_count + 1):
            monitor.record_flow_error(unhealthy_id, Exception("Error"))

        health = monitor.check_system_health()

        assert health["status"] in [
            HealthStatus.DEGRADED.value,
            HealthStatus.UNHEALTHY.value,
        ]
        assert health["unhealthy_flows"] + health["critical_flows"] > 0

    def test_check_system_health_mostly_unhealthy(self, monitor):
        """Test system health with many unhealthy flows."""
        # Create mostly unhealthy flows
        for i in range(10):
            flow_id = uuid4()
            monitor.start_monitoring(flow_id)

            if i < 7:  # 70% unhealthy
                for j in range(monitor.max_error_count + 1):
                    monitor.record_flow_error(flow_id, Exception("Error"))
            else:
                context = FlowContext(
                    flow_instance_id=flow_id,
                    flow_type=FlowType.DAILY_CHECKIN,
                    patient_id=uuid4(),
                    status=FlowStatus.ACTIVE,
                )
                monitor.check_flow_health(flow_id, context)

        health = monitor.check_system_health()

        assert health["status"] in [
            HealthStatus.UNHEALTHY.value,
            HealthStatus.CRITICAL.value,
        ]


class TestUnhealthyFlowQueries:
    """Test queries for unhealthy flows."""

    def test_get_unhealthy_flows_empty(self, monitor):
        """Test getting unhealthy flows when none exist."""
        unhealthy = monitor.get_unhealthy_flows()
        assert len(unhealthy) == 0

    def test_get_unhealthy_flows(self, monitor):
        """Test getting unhealthy flows."""
        # Create healthy flow
        healthy_id = uuid4()
        monitor.start_monitoring(healthy_id)

        # Create unhealthy flows
        unhealthy_ids = []
        for i in range(3):
            flow_id = uuid4()
            unhealthy_ids.append(flow_id)
            monitor.start_monitoring(flow_id)
            for j in range(monitor.max_error_count + 1):
                monitor.record_flow_error(flow_id, Exception("Error"))

        unhealthy = monitor.get_unhealthy_flows()

        assert len(unhealthy) == 3
        assert all(m.status != HealthStatus.HEALTHY for m in unhealthy)

    def test_get_critical_flows(self, monitor):
        """Test getting critical flows only."""
        # Create critical flows
        for i in range(2):
            flow_id = uuid4()
            monitor.start_monitoring(flow_id)
            for j in range(monitor.max_error_count + 2):
                monitor.record_flow_error(flow_id, Exception("Error"))

        # Create degraded flow
        degraded_id = uuid4()
        monitor.start_monitoring(degraded_id)
        monitor.record_flow_retry(degraded_id)

        critical = monitor.get_critical_flows()

        assert len(critical) == 2
        assert all(m.status == HealthStatus.CRITICAL for m in critical)


class TestHealthQueries:
    """Test health query methods."""

    def test_get_flow_health(self, monitor, flow_instance_id):
        """Test getting health for specific flow."""
        monitor.start_monitoring(flow_instance_id)

        health = monitor.get_flow_health(flow_instance_id)

        assert health is not None
        assert isinstance(health, FlowHealthMetrics)

    def test_get_flow_health_not_found(self, monitor):
        """Test getting health for non-existent flow."""
        health = monitor.get_flow_health(uuid4())
        assert health is None

    def test_is_flow_healthy_true(self, monitor, flow_instance_id, healthy_context):
        """Test checking if flow is healthy (true case)."""
        monitor.start_monitoring(flow_instance_id)
        monitor.check_flow_health(flow_instance_id, healthy_context)

        is_healthy = monitor.is_flow_healthy(flow_instance_id)

        assert is_healthy is True

    def test_is_flow_healthy_false(self, monitor, flow_instance_id):
        """Test checking if flow is healthy (false case)."""
        monitor.start_monitoring(flow_instance_id)
        for i in range(monitor.max_error_count + 1):
            monitor.record_flow_error(flow_instance_id, Exception("Error"))

        is_healthy = monitor.is_flow_healthy(flow_instance_id)

        assert is_healthy is False

    def test_is_flow_healthy_unknown(self, monitor):
        """Test checking health of unknown flow."""
        is_healthy = monitor.is_flow_healthy(uuid4())
        assert is_healthy is True  # Unknown flows considered healthy

    def test_get_active_flow_count(self, monitor):
        """Test getting active flow count."""
        assert monitor.get_active_flow_count() == 0

        for i in range(5):
            monitor.start_monitoring(uuid4())

        assert monitor.get_active_flow_count() == 5


class TestAlertMethods:
    """Test alert detection and generation."""

    def test_should_alert_false_for_healthy(self, monitor, flow_instance_id):
        """Test should_alert returns False for healthy flow."""
        monitor.start_monitoring(flow_instance_id)

        should_alert = monitor.should_alert(flow_instance_id)

        assert should_alert is False

    def test_should_alert_true_for_unhealthy(self, monitor, flow_instance_id):
        """Test should_alert returns True for unhealthy flow."""
        monitor.start_monitoring(flow_instance_id)
        for i in range(monitor.max_error_count + 1):
            monitor.record_flow_error(flow_instance_id, Exception("Error"))

        should_alert = monitor.should_alert(flow_instance_id)

        assert should_alert is True

    def test_should_alert_for_timeout(self, monitor, flow_instance_id):
        """Test should_alert for timed out flow."""
        monitor.start_monitoring(flow_instance_id)

        context = FlowContext(
            flow_instance_id=flow_instance_id,
            flow_type=FlowType.DAILY_CHECKIN,
            patient_id=uuid4(),
            status=FlowStatus.ACTIVE,
            started_at=datetime.utcnow() - timedelta(hours=3),
        )
        monitor.check_flow_health(flow_instance_id, context)

        should_alert = monitor.should_alert(flow_instance_id)

        assert should_alert is True

    def test_get_alert_data(self, monitor, flow_instance_id):
        """Test getting alert data for flow."""
        monitor.start_monitoring(flow_instance_id)
        for i in range(monitor.max_error_count + 1):
            monitor.record_flow_error(flow_instance_id, Exception("Error"))

        alert_data = monitor.get_alert_data(flow_instance_id)

        assert alert_data is not None
        assert "flow_instance_id" in alert_data
        assert "health_status" in alert_data
        assert "issues" in alert_data
        assert "error_count" in alert_data

    def test_get_alert_data_no_alert_needed(self, monitor, flow_instance_id):
        """Test getting alert data when no alert needed."""
        monitor.start_monitoring(flow_instance_id)

        alert_data = monitor.get_alert_data(flow_instance_id)

        assert alert_data is None


class TestCleanupMethods:
    """Test cleanup and maintenance methods."""

    def test_cleanup_old_metrics(self, monitor):
        """Test cleaning up old metrics."""
        # Create old inactive flow
        old_flow = uuid4()
        monitor._flow_health[old_flow] = FlowHealthMetrics(old_flow)
        monitor._flow_health[old_flow].last_check = datetime.utcnow() - timedelta(
            hours=48
        )

        # Create recent flow
        recent_flow = uuid4()
        monitor.start_monitoring(recent_flow)

        cleaned = monitor.cleanup_old_metrics(hours=24)

        assert cleaned == 1
        assert old_flow not in monitor._flow_health
        assert recent_flow in monitor._flow_health

    def test_cleanup_old_metrics_active_flows_not_cleaned(self, monitor):
        """Test that active flows are not cleaned up."""
        flow_id = uuid4()
        monitor.start_monitoring(flow_id)
        monitor._flow_health[flow_id].last_check = datetime.utcnow() - timedelta(
            hours=48
        )

        cleaned = monitor.cleanup_old_metrics(hours=24)

        assert cleaned == 0
        assert flow_id in monitor._flow_health

    def test_reset_metrics(self, monitor, flow_instance_id):
        """Test resetting all metrics."""
        monitor.start_monitoring(flow_instance_id)
        monitor.record_flow_error(flow_instance_id, Exception("Error"))

        monitor.reset_metrics()

        assert len(monitor._flow_health) == 0
        assert len(monitor._active_flows) == 0
        assert monitor._system_health_status == HealthStatus.HEALTHY


class TestHealthReportExport:
    """Test health report export."""

    def test_export_health_report(self, monitor):
        """Test exporting complete health report."""
        # Create some flows
        for i in range(3):
            flow_id = uuid4()
            monitor.start_monitoring(flow_id)
            if i == 2:
                monitor.record_flow_error(flow_id, Exception("Error"))

        report = monitor.export_health_report()

        assert "system_health" in report
        assert "active_flows" in report
        assert "monitored_flows" in report
        assert "unhealthy_flows" in report
        assert "generated_at" in report

    def test_export_health_report_structure(self, monitor):
        """Test health report structure."""
        report = monitor.export_health_report()

        assert isinstance(report["system_health"], dict)
        assert isinstance(report["unhealthy_flows"], list)
        assert isinstance(report["generated_at"], str)


class TestHealthStatusCalculation:
    """Test health status calculation logic."""

    def test_healthy_status_no_issues(self, monitor, flow_instance_id):
        """Test HEALTHY status with no issues."""
        monitor.start_monitoring(flow_instance_id)

        context = FlowContext(
            flow_instance_id=flow_instance_id,
            flow_type=FlowType.DAILY_CHECKIN,
            patient_id=uuid4(),
            status=FlowStatus.ACTIVE,
            started_at=datetime.utcnow() - timedelta(minutes=1),
        )
        metrics = monitor.check_flow_health(flow_instance_id, context)

        assert metrics.status == HealthStatus.HEALTHY

    def test_degraded_status_with_warnings(self, monitor, flow_instance_id):
        """Test DEGRADED status with warnings."""
        monitor.start_monitoring(flow_instance_id)
        monitor.record_flow_retry(flow_instance_id)

        metrics = monitor._flow_health[flow_instance_id]
        assert metrics.status == HealthStatus.DEGRADED

    def test_unhealthy_status_with_issues(self, monitor, flow_instance_id):
        """Test UNHEALTHY status with issues."""
        monitor.start_monitoring(flow_instance_id)

        context = FlowContext(
            flow_instance_id=flow_instance_id,
            flow_type=FlowType.DAILY_CHECKIN,
            patient_id=uuid4(),
            status=FlowStatus.ACTIVE,
            started_at=datetime.utcnow() - timedelta(hours=2),
        )
        monitor.check_flow_health(flow_instance_id, context)

        metrics = monitor._flow_health[flow_instance_id]
        assert metrics.status == HealthStatus.UNHEALTHY

    def test_critical_status_max_errors(self, monitor, flow_instance_id):
        """Test CRITICAL status with max errors exceeded."""
        monitor.start_monitoring(flow_instance_id)

        for i in range(monitor.max_error_count + 1):
            monitor.record_flow_error(flow_instance_id, Exception("Error"))

        metrics = monitor._flow_health[flow_instance_id]
        assert metrics.status == HealthStatus.CRITICAL


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_check_health_without_start_monitoring(
        self, monitor, flow_instance_id, sample_flow_context
    ):
        """Test checking health without starting monitoring."""
        # Should create metrics on the fly
        metrics = monitor.check_flow_health(flow_instance_id, sample_flow_context)

        assert metrics is not None
        assert isinstance(metrics, FlowHealthMetrics)

    def test_record_error_without_start_monitoring(self, monitor, flow_instance_id):
        """Test recording error without starting monitoring."""
        # Should create metrics on the fly
        monitor.record_flow_error(flow_instance_id, Exception("Error"))

        metrics = monitor._flow_health.get(flow_instance_id)
        assert metrics is not None
        assert metrics.error_count == 1

    def test_multiple_health_checks_same_flow(
        self, monitor, flow_instance_id, sample_flow_context
    ):
        """Test multiple health checks for same flow."""
        monitor.start_monitoring(flow_instance_id)

        metrics1 = monitor.check_flow_health(flow_instance_id, sample_flow_context)
        metrics2 = monitor.check_flow_health(flow_instance_id, sample_flow_context)

        # Should update existing metrics
        assert metrics1.flow_instance_id == metrics2.flow_instance_id
        assert metrics2.last_check is not None
