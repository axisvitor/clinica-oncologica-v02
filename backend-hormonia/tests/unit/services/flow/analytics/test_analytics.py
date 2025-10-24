"""
Unit Tests for FlowAnalytics - QW-021 Flow Services Consolidation.

Tests the main analytics service that integrates metrics collection,
event broadcasting, and health monitoring for the consolidated flow system.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, patch

from app.services.flow.analytics.analytics import FlowAnalytics, get_flow_analytics
from app.services.flow.types import (
    FlowContext,
    FlowType,
    FlowStatus,
    FlowPriority,
    FlowStepData,
    FlowStepType,
    FlowStepStatus,
    FlowEventType,
)


@pytest.fixture
def analytics():
    """Create FlowAnalytics instance."""
    return FlowAnalytics()


@pytest.fixture
def flow_instance_id():
    """Create test flow instance ID."""
    return uuid4()


@pytest.fixture
def patient_id():
    """Create test patient ID."""
    return uuid4()


@pytest.fixture
def sample_context(flow_instance_id, patient_id):
    """Create sample flow context for testing."""
    return FlowContext(
        flow_instance_id=flow_instance_id,
        flow_type=FlowType.DAILY_CHECKIN,
        patient_id=patient_id,
        status=FlowStatus.ACTIVE,
        started_at=datetime.utcnow() - timedelta(minutes=5),
    )


@pytest.fixture
def sample_step_data():
    """Create sample step data for testing."""
    return FlowStepData(
        step_id="step_001",
        step_type=FlowStepType.MESSAGE,
        step_name="Test Step",
        status=FlowStepStatus.COMPLETED,
        started_at=datetime.utcnow() - timedelta(seconds=30),
        completed_at=datetime.utcnow(),
    )


class TestFlowAnalyticsInitialization:
    """Test FlowAnalytics initialization."""

    def test_initialization(self, analytics):
        """Test analytics service initializes correctly."""
        assert analytics is not None
        assert analytics.config is not None
        assert analytics.metrics_collector is not None
        assert analytics.event_broadcaster is not None
        assert analytics.monitor is not None

    def test_subcomponents_initialized(self, analytics):
        """Test all sub-components are initialized."""
        assert hasattr(analytics, "metrics_collector")
        assert hasattr(analytics, "event_broadcaster")
        assert hasattr(analytics, "monitor")


class TestFlowLifecycleTracking:
    """Test flow lifecycle tracking integration."""

    def test_on_flow_started(self, analytics, flow_instance_id, sample_context):
        """Test tracking flow start."""
        analytics.on_flow_started(flow_instance_id, sample_context)

        # Verify metrics tracking started
        assert flow_instance_id in analytics.metrics_collector._flow_start_times

        # Verify monitoring started
        assert flow_instance_id in analytics.monitor._active_flows

        # Verify event was broadcast
        events = analytics.event_broadcaster.get_recent_events(
            flow_instance_id=flow_instance_id
        )
        assert len(events) > 0
        assert events[0].event_type == FlowEventType.FLOW_STARTED

    def test_on_flow_completed(self, analytics, flow_instance_id, sample_context):
        """Test tracking flow completion."""
        # Start flow first
        analytics.on_flow_started(flow_instance_id, sample_context)

        # Complete flow
        sample_context.status = FlowStatus.COMPLETED
        sample_context.completed_at = datetime.utcnow()
        analytics.on_flow_completed(flow_instance_id, sample_context)

        # Verify metrics recorded
        metrics = analytics.metrics_collector.get_flow_metrics(flow_instance_id)
        assert metrics is not None
        assert metrics.duration_seconds is not None

        # Verify monitoring stopped
        assert flow_instance_id not in analytics.monitor._active_flows

        # Verify event was broadcast
        events = analytics.event_broadcaster.get_recent_events(
            event_type=FlowEventType.FLOW_COMPLETED
        )
        assert len(events) > 0

    def test_on_flow_failed(self, analytics, flow_instance_id, sample_context):
        """Test tracking flow failure."""
        analytics.on_flow_started(flow_instance_id, sample_context)

        error = Exception("Test error")
        analytics.on_flow_failed(flow_instance_id, sample_context, error)

        # Verify metrics recorded
        metrics = analytics.metrics_collector.get_flow_metrics(flow_instance_id)
        assert metrics.error_count > 0

        # Verify health recorded error
        health = analytics.monitor.get_flow_health(flow_instance_id)
        assert health is not None
        assert health.error_count > 0

        # Verify event was broadcast
        events = analytics.event_broadcaster.get_recent_events(
            event_type=FlowEventType.FLOW_FAILED
        )
        assert len(events) > 0

    def test_on_flow_paused(self, analytics, flow_instance_id, sample_context):
        """Test tracking flow pause."""
        analytics.on_flow_started(flow_instance_id, sample_context)

        analytics.on_flow_paused(flow_instance_id, sample_context)

        # Verify event was broadcast
        events = analytics.event_broadcaster.get_recent_events(
            event_type=FlowEventType.FLOW_PAUSED
        )
        assert len(events) > 0

    def test_on_flow_resumed(self, analytics, flow_instance_id, sample_context):
        """Test tracking flow resume."""
        analytics.on_flow_started(flow_instance_id, sample_context)
        analytics.on_flow_paused(flow_instance_id, sample_context)

        analytics.on_flow_resumed(flow_instance_id, sample_context)

        # Verify event was broadcast
        events = analytics.event_broadcaster.get_recent_events(
            event_type=FlowEventType.FLOW_RESUMED
        )
        assert len(events) > 0

    def test_on_flow_cancelled(self, analytics, flow_instance_id, sample_context):
        """Test tracking flow cancellation."""
        analytics.on_flow_started(flow_instance_id, sample_context)

        analytics.on_flow_cancelled(flow_instance_id, sample_context)

        # Verify metrics recorded
        metrics = analytics.metrics_collector.get_flow_metrics(flow_instance_id)
        assert metrics is not None

        # Verify monitoring stopped
        assert flow_instance_id not in analytics.monitor._active_flows

        # Verify event was broadcast
        events = analytics.event_broadcaster.get_recent_events(
            event_type=FlowEventType.FLOW_CANCELLED
        )
        assert len(events) > 0


class TestStepLifecycleTracking:
    """Test step lifecycle tracking integration."""

    def test_on_step_started(self, analytics, flow_instance_id, sample_step_data):
        """Test tracking step start."""
        analytics.on_step_started(flow_instance_id, sample_step_data)

        # Verify metrics tracking started
        tracking_key = f"{flow_instance_id}:{sample_step_data.step_id}"
        assert tracking_key in analytics.metrics_collector._step_start_times

        # Verify event was broadcast
        events = analytics.event_broadcaster.get_recent_events(
            event_type=FlowEventType.STEP_STARTED
        )
        assert len(events) > 0

    def test_on_step_completed(self, analytics, flow_instance_id, sample_step_data):
        """Test tracking step completion."""
        analytics.on_step_started(flow_instance_id, sample_step_data)
        analytics.on_step_completed(flow_instance_id, sample_step_data)

        # Verify metrics recorded
        tracking_key = f"{flow_instance_id}:{sample_step_data.step_id}"
        assert tracking_key in analytics.metrics_collector._step_metrics

        # Verify event was broadcast
        events = analytics.event_broadcaster.get_recent_events(
            event_type=FlowEventType.STEP_COMPLETED
        )
        assert len(events) > 0

    def test_on_step_failed(self, analytics, flow_instance_id, sample_step_data):
        """Test tracking step failure."""
        analytics.on_step_started(flow_instance_id, sample_step_data)

        error = Exception("Step error")
        analytics.on_step_failed(flow_instance_id, sample_step_data, error)

        # Verify metrics recorded
        tracking_key = f"{flow_instance_id}:{sample_step_data.step_id}"
        step_metrics = analytics.metrics_collector._step_metrics.get(tracking_key)
        assert step_metrics is not None

        # Verify event was broadcast
        events = analytics.event_broadcaster.get_recent_events(
            event_type=FlowEventType.STEP_FAILED
        )
        assert len(events) > 0


class TestErrorAndRetryTracking:
    """Test error and retry tracking integration."""

    def test_on_error(self, analytics, flow_instance_id):
        """Test error tracking."""
        error = Exception("Test error")
        analytics.on_error(flow_instance_id, error, {"context": "test"})

        # Verify metrics recorded
        metrics = analytics.metrics_collector.get_flow_metrics(flow_instance_id)
        assert metrics is not None
        assert metrics.error_count > 0

        # Verify health recorded
        health = analytics.monitor.get_flow_health(flow_instance_id)
        assert health is not None
        assert health.error_count > 0

        # Verify event was broadcast
        events = analytics.event_broadcaster.get_recent_events(
            event_type=FlowEventType.ERROR_OCCURRED
        )
        assert len(events) > 0

    def test_on_retry(self, analytics, flow_instance_id):
        """Test retry tracking."""
        analytics.on_retry(flow_instance_id, 1, "Timeout")

        # Verify metrics recorded
        metrics = analytics.metrics_collector.get_flow_metrics(flow_instance_id)
        assert metrics is not None
        assert metrics.retry_count > 0

        # Verify health recorded
        health = analytics.monitor.get_flow_health(flow_instance_id)
        assert health is not None
        assert health.retry_count > 0


class TestHealthMonitoring:
    """Test health monitoring integration."""

    def test_check_flow_health(self, analytics, flow_instance_id, sample_context):
        """Test checking flow health."""
        analytics.on_flow_started(flow_instance_id, sample_context)

        health = analytics.check_flow_health(flow_instance_id, sample_context)

        assert health is not None
        assert health.flow_instance_id == flow_instance_id
        assert health.status is not None

    def test_get_system_health(self, analytics, flow_instance_id, sample_context):
        """Test getting system health."""
        analytics.on_flow_started(flow_instance_id, sample_context)

        system_health = analytics.get_system_health()

        assert isinstance(system_health, dict)
        assert "status" in system_health
        assert "active_flows" in system_health

    def test_get_unhealthy_flows(self, analytics):
        """Test getting unhealthy flows."""
        # Create unhealthy flow
        flow_id = uuid4()
        analytics.on_flow_started(
            flow_id,
            FlowContext(
                flow_instance_id=flow_id,
                flow_type=FlowType.DAILY_CHECKIN,
                patient_id=uuid4(),
            ),
        )
        for i in range(10):
            analytics.on_error(flow_id, Exception("Error"))

        unhealthy = analytics.get_unhealthy_flows()

        assert len(unhealthy) > 0


class TestMetricsQuery:
    """Test metrics query methods."""

    def test_get_flow_metrics(self, analytics, flow_instance_id, sample_context):
        """Test getting flow metrics."""
        analytics.on_flow_started(flow_instance_id, sample_context)

        metrics = analytics.get_flow_metrics(flow_instance_id)

        assert metrics is not None

    def test_get_aggregate_metrics(self, analytics):
        """Test getting aggregate metrics."""
        # Create some flows
        for i in range(5):
            flow_id = uuid4()
            context = FlowContext(
                flow_instance_id=flow_id,
                flow_type=FlowType.DAILY_CHECKIN,
                patient_id=uuid4(),
            )
            analytics.on_flow_started(flow_id, context)
            analytics.on_flow_completed(flow_id, context)

        aggregate = analytics.get_aggregate_metrics()

        assert isinstance(aggregate, dict)
        assert "total_flows_completed" in aggregate
        assert aggregate["total_flows_completed"] >= 5

    def test_get_metrics_by_flow_type(self, analytics):
        """Test getting metrics by flow type."""
        metrics = analytics.get_metrics_by_flow_type(FlowType.DAILY_CHECKIN)

        assert isinstance(metrics, dict)
        assert "flow_type" in metrics


class TestEventSubscription:
    """Test event subscription methods."""

    def test_subscribe_to_events(self, analytics):
        """Test subscribing to events."""
        handler = Mock()

        subscription_id = analytics.subscribe_to_events(
            FlowEventType.FLOW_STARTED, handler
        )

        assert subscription_id is not None

        # Trigger event
        flow_id = uuid4()
        context = FlowContext(
            flow_instance_id=flow_id,
            flow_type=FlowType.DAILY_CHECKIN,
            patient_id=uuid4(),
        )
        analytics.on_flow_started(flow_id, context)

        # Verify handler was called
        handler.assert_called_once()

    def test_subscribe_to_all_events(self, analytics):
        """Test subscribing to all events."""
        handler = Mock()

        subscription_id = analytics.subscribe_to_all_events(handler)

        assert subscription_id is not None

        # Trigger different events
        flow_id = uuid4()
        context = FlowContext(
            flow_instance_id=flow_id,
            flow_type=FlowType.DAILY_CHECKIN,
            patient_id=uuid4(),
        )
        analytics.on_flow_started(flow_id, context)
        analytics.on_flow_completed(flow_id, context)

        # Verify handler was called multiple times
        assert handler.call_count >= 2

    def test_unsubscribe(self, analytics):
        """Test unsubscribing from events."""
        handler = Mock()
        subscription_id = analytics.subscribe_to_events(
            FlowEventType.FLOW_STARTED, handler
        )

        result = analytics.unsubscribe(subscription_id)

        assert result is True

    def test_get_recent_events(self, analytics, flow_instance_id, sample_context):
        """Test getting recent events."""
        analytics.on_flow_started(flow_instance_id, sample_context)

        recent = analytics.get_recent_events(flow_instance_id=flow_instance_id)

        assert len(recent) > 0


class TestDashboardData:
    """Test dashboard data generation."""

    def test_get_dashboard_data(self, analytics):
        """Test getting dashboard data."""
        # Create some flows
        for i in range(3):
            flow_id = uuid4()
            context = FlowContext(
                flow_instance_id=flow_id,
                flow_type=FlowType.DAILY_CHECKIN,
                patient_id=uuid4(),
            )
            analytics.on_flow_started(flow_id, context)

        dashboard = analytics.get_dashboard_data()

        assert isinstance(dashboard, dict)
        assert "system_health" in dashboard
        assert "aggregate_metrics" in dashboard
        assert "unhealthy_flows" in dashboard
        assert "recent_events" in dashboard
        assert "generated_at" in dashboard

    def test_dashboard_data_structure(self, analytics):
        """Test dashboard data structure."""
        dashboard = analytics.get_dashboard_data()

        assert isinstance(dashboard["system_health"], dict)
        assert isinstance(dashboard["aggregate_metrics"], dict)
        assert isinstance(dashboard["unhealthy_flows"], list)
        assert isinstance(dashboard["recent_events"], list)


class TestAnalyticsExport:
    """Test analytics export functionality."""

    def test_export_analytics_report(self, analytics):
        """Test exporting complete analytics report."""
        # Create some data
        flow_id = uuid4()
        context = FlowContext(
            flow_instance_id=flow_id,
            flow_type=FlowType.DAILY_CHECKIN,
            patient_id=uuid4(),
        )
        analytics.on_flow_started(flow_id, context)

        report = analytics.export_analytics_report()

        assert isinstance(report, dict)
        assert "metrics" in report
        assert "health" in report
        assert "events" in report
        assert "generated_at" in report

    def test_export_report_structure(self, analytics):
        """Test export report structure."""
        report = analytics.export_analytics_report()

        assert isinstance(report["metrics"], dict)
        assert isinstance(report["health"], dict)
        assert isinstance(report["events"], dict)


class TestUtilityMethods:
    """Test utility methods."""

    def test_reset_analytics(self, analytics, flow_instance_id, sample_context):
        """Test resetting all analytics."""
        # Create some data
        analytics.on_flow_started(flow_instance_id, sample_context)

        analytics.reset_analytics()

        # Verify all cleared
        assert len(analytics.metrics_collector._flow_metrics) == 0
        assert len(analytics.monitor._flow_health) == 0
        assert len(analytics.event_broadcaster._event_queue) == 0

    def test_shutdown(self, analytics):
        """Test shutting down analytics service."""
        # Should not crash
        analytics.shutdown()


class TestCompleteFlowScenario:
    """Test complete flow lifecycle scenario."""

    def test_complete_flow_lifecycle(self, analytics, patient_id):
        """Test tracking complete flow from start to finish."""
        flow_id = uuid4()

        # Create context
        context = FlowContext(
            flow_instance_id=flow_id,
            flow_type=FlowType.DAILY_CHECKIN,
            patient_id=patient_id,
            started_at=datetime.utcnow(),
        )

        # Start flow
        analytics.on_flow_started(flow_id, context)

        # Execute steps
        for i in range(3):
            step_data = FlowStepData(
                step_id=f"step_{i:03d}",
                step_type=FlowStepType.MESSAGE,
                step_name=f"Step {i}",
                started_at=datetime.utcnow(),
            )

            analytics.on_step_started(flow_id, step_data)

            step_data.completed_at = datetime.utcnow()
            step_data.status = FlowStepStatus.COMPLETED
            analytics.on_step_completed(flow_id, step_data)

            context.steps_completed.append(step_data.step_id)
            context.steps_history.append(step_data)

        # Complete flow
        context.completed_at = datetime.utcnow()
        context.status = FlowStatus.COMPLETED
        analytics.on_flow_completed(flow_id, context)

        # Verify final state
        metrics = analytics.get_flow_metrics(flow_id)
        assert metrics is not None
        assert metrics.total_steps == 3
        assert metrics.completed_steps == 3

        # Verify events recorded
        events = analytics.get_recent_events(flow_instance_id=flow_id)
        assert len(events) >= 7  # 1 start + 3*2 steps + 1 complete


class TestMultipleFlowsScenario:
    """Test tracking multiple concurrent flows."""

    def test_multiple_concurrent_flows(self, analytics, patient_id):
        """Test tracking multiple flows concurrently."""
        flow_ids = [uuid4() for _ in range(5)]

        # Start all flows
        for flow_id in flow_ids:
            context = FlowContext(
                flow_instance_id=flow_id,
                flow_type=FlowType.DAILY_CHECKIN,
                patient_id=patient_id,
            )
            analytics.on_flow_started(flow_id, context)

        # Complete some, fail others
        for i, flow_id in enumerate(flow_ids):
            context = FlowContext(
                flow_instance_id=flow_id,
                flow_type=FlowType.DAILY_CHECKIN,
                patient_id=patient_id,
                started_at=datetime.utcnow() - timedelta(minutes=5),
            )

            if i < 3:
                analytics.on_flow_completed(flow_id, context)
            else:
                analytics.on_flow_failed(flow_id, context, Exception("Failed"))

        # Verify aggregate metrics
        aggregate = analytics.get_aggregate_metrics()
        assert aggregate["total_flows_completed"] >= 3
        assert aggregate["total_flows_failed"] >= 2


class TestSingletonPattern:
    """Test singleton pattern for global instance."""

    def test_get_flow_analytics(self):
        """Test getting global analytics instance."""
        analytics1 = get_flow_analytics()
        analytics2 = get_flow_analytics()

        assert analytics1 is analytics2

    def test_get_flow_analytics_returns_analytics_instance(self):
        """Test that get_flow_analytics returns FlowAnalytics instance."""
        analytics = get_flow_analytics()

        assert isinstance(analytics, FlowAnalytics)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_track_flow_without_context(self, analytics, flow_instance_id):
        """Test tracking flow without complete context."""
        # Should not crash
        minimal_context = FlowContext(
            flow_instance_id=flow_instance_id,
            flow_type=FlowType.DAILY_CHECKIN,
            patient_id=uuid4(),
        )

        analytics.on_flow_started(flow_instance_id, minimal_context)

    def test_complete_flow_without_start(self, analytics, flow_instance_id):
        """Test completing flow without starting."""
        context = FlowContext(
            flow_instance_id=flow_instance_id,
            flow_type=FlowType.DAILY_CHECKIN,
            patient_id=uuid4(),
        )

        # Should not crash
        analytics.on_flow_completed(flow_instance_id, context)

    def test_duplicate_flow_start(self, analytics, flow_instance_id, sample_context):
        """Test starting same flow multiple times."""
        analytics.on_flow_started(flow_instance_id, sample_context)
        analytics.on_flow_started(flow_instance_id, sample_context)

        # Should handle gracefully (overwrite or keep first)
        assert flow_instance_id in analytics.monitor._active_flows


class TestIntegrationBetweenComponents:
    """Test integration between analytics sub-components."""

    def test_metrics_and_health_coordination(
        self, analytics, flow_instance_id, sample_context
    ):
        """Test that metrics and health are coordinated."""
        analytics.on_flow_started(flow_instance_id, sample_context)

        # Trigger error
        for i in range(5):
            analytics.on_error(flow_instance_id, Exception("Error"))

        # Both should reflect the error state
        metrics = analytics.get_flow_metrics(flow_instance_id)
        health = analytics.monitor.get_flow_health(flow_instance_id)

        assert metrics.error_count == 5
        assert health.error_count == 5

    def test_events_and_metrics_coordination(self, analytics, flow_instance_id):
        """Test that events and metrics are coordinated."""
        context = FlowContext(
            flow_instance_id=flow_instance_id,
            flow_type=FlowType.DAILY_CHECKIN,
            patient_id=uuid4(),
        )

        analytics.on_flow_started(flow_instance_id, context)

        # Event should be recorded
        events = analytics.get_recent_events(event_type=FlowEventType.FLOW_STARTED)
        assert len(events) > 0

        # Metrics should be tracked
        assert flow_instance_id in analytics.metrics_collector._flow_start_times
