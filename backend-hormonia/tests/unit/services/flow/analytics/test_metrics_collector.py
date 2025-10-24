"""
Unit Tests for FlowMetricsCollector - QW-021 Flow Services Consolidation.

Tests metrics collection, aggregation, and query functionality for the
consolidated flow analytics system.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.services.flow.analytics.metrics_collector import FlowMetricsCollector
from app.services.flow.types import (
    FlowStatus,
    FlowStepStatus,
    FlowContext,
    FlowStepData,
    FlowType,
    FlowStepType,
    FlowMetrics,
)


@pytest.fixture
def metrics_collector():
    """Create FlowMetricsCollector instance."""
    return FlowMetricsCollector()


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
        current_step_id="step_001",
        status=FlowStatus.ACTIVE,
        started_at=datetime.utcnow() - timedelta(minutes=5),
    )


@pytest.fixture
def sample_step_data():
    """Create sample step data for testing."""
    return FlowStepData(
        step_id="step_001",
        step_type=FlowStepType.QUESTION,
        step_name="Test Question",
        status=FlowStepStatus.COMPLETED,
        started_at=datetime.utcnow() - timedelta(seconds=30),
        completed_at=datetime.utcnow(),
    )


class TestFlowMetricsCollectorInitialization:
    """Test FlowMetricsCollector initialization."""

    def test_initialization(self, metrics_collector):
        """Test collector initializes correctly."""
        assert metrics_collector is not None
        assert metrics_collector.config is not None
        assert len(metrics_collector._flow_metrics) == 0
        assert len(metrics_collector._step_metrics) == 0

    def test_configuration_loaded(self, metrics_collector):
        """Test configuration is loaded."""
        assert metrics_collector.config.enable_metrics is not None


class TestFlowTracking:
    """Test flow-level metrics tracking."""

    def test_start_flow_tracking(self, metrics_collector, flow_instance_id):
        """Test starting flow tracking."""
        metrics_collector.start_flow_tracking(flow_instance_id)

        assert flow_instance_id in metrics_collector._flow_metrics
        assert flow_instance_id in metrics_collector._flow_start_times

        metrics = metrics_collector._flow_metrics[flow_instance_id]
        assert isinstance(metrics, FlowMetrics)
        assert metrics.total_steps == 0
        assert metrics.completed_steps == 0

    def test_start_flow_tracking_disabled(self, metrics_collector, flow_instance_id):
        """Test flow tracking when metrics are disabled."""
        metrics_collector.config.enable_metrics = False

        metrics_collector.start_flow_tracking(flow_instance_id)

        assert flow_instance_id not in metrics_collector._flow_metrics

    def test_record_flow_completion(
        self, metrics_collector, flow_instance_id, sample_flow_context
    ):
        """Test recording flow completion."""
        # Start tracking
        metrics_collector.start_flow_tracking(flow_instance_id)

        # Add some steps to context
        sample_flow_context.steps_history = [
            FlowStepData(
                step_id=f"step_{i}",
                step_type=FlowStepType.MESSAGE,
                step_name=f"Step {i}",
                status=FlowStepStatus.COMPLETED,
                started_at=datetime.utcnow() - timedelta(seconds=10),
                completed_at=datetime.utcnow(),
            )
            for i in range(3)
        ]

        # Record completion
        metrics_collector.record_flow_completion(
            flow_instance_id, FlowStatus.COMPLETED, sample_flow_context
        )

        metrics = metrics_collector._flow_metrics[flow_instance_id]
        assert metrics.duration_seconds is not None
        assert metrics.duration_seconds > 0
        assert metrics.total_steps == 3
        assert metrics.completed_steps == 3

    def test_record_flow_error(self, metrics_collector, flow_instance_id):
        """Test recording flow error."""
        metrics_collector.start_flow_tracking(flow_instance_id)

        error = Exception("Test error")
        metrics_collector.record_flow_error(flow_instance_id, error)

        metrics = metrics_collector._flow_metrics[flow_instance_id]
        assert metrics.error_count == 1

        # Record another error
        metrics_collector.record_flow_error(flow_instance_id, error)
        assert metrics.error_count == 2

    def test_record_flow_retry(self, metrics_collector, flow_instance_id):
        """Test recording flow retry."""
        metrics_collector.start_flow_tracking(flow_instance_id)

        metrics_collector.record_flow_retry(flow_instance_id)

        metrics = metrics_collector._flow_metrics[flow_instance_id]
        assert metrics.retry_count == 1


class TestStepTracking:
    """Test step-level metrics tracking."""

    def test_start_step_tracking(self, metrics_collector, flow_instance_id):
        """Test starting step tracking."""
        step_id = "step_001"

        metrics_collector.start_step_tracking(flow_instance_id, step_id)

        tracking_key = f"{flow_instance_id}:{step_id}"
        assert tracking_key in metrics_collector._step_start_times

    def test_record_step_completion(
        self, metrics_collector, flow_instance_id, sample_step_data
    ):
        """Test recording step completion."""
        step_id = sample_step_data.step_id

        # Start tracking
        metrics_collector.start_step_tracking(flow_instance_id, step_id)

        # Record completion
        metrics_collector.record_step_completion(
            flow_instance_id,
            step_id,
            FlowStepStatus.COMPLETED,
            sample_step_data,
        )

        tracking_key = f"{flow_instance_id}:{step_id}"
        assert tracking_key in metrics_collector._step_metrics

        step_metrics = metrics_collector._step_metrics[tracking_key]
        assert step_metrics["status"] == FlowStepStatus.COMPLETED.value
        assert step_metrics["duration_seconds"] is not None

    def test_step_metrics_aggregation(self, metrics_collector, flow_instance_id):
        """Test step metrics are aggregated correctly."""
        # Track multiple steps
        for i in range(5):
            step_id = f"step_{i:03d}"
            metrics_collector.start_step_tracking(flow_instance_id, step_id)

            status = FlowStepStatus.COMPLETED if i < 4 else FlowStepStatus.FAILED
            metrics_collector.record_step_completion(flow_instance_id, step_id, status)

        aggregate = metrics_collector.get_aggregate_metrics()
        assert aggregate["total_steps_executed"] == 5
        assert aggregate["total_steps_succeeded"] == 4
        assert aggregate["total_steps_failed"] == 1


class TestMetricsQueries:
    """Test metrics query methods."""

    def test_get_flow_metrics(self, metrics_collector, flow_instance_id):
        """Test getting metrics for specific flow."""
        metrics_collector.start_flow_tracking(flow_instance_id)

        metrics = metrics_collector.get_flow_metrics(flow_instance_id)

        assert metrics is not None
        assert isinstance(metrics, FlowMetrics)

    def test_get_flow_metrics_not_found(self, metrics_collector):
        """Test getting metrics for non-existent flow."""
        metrics = metrics_collector.get_flow_metrics(uuid4())
        assert metrics is None

    def test_get_aggregate_metrics(self, metrics_collector):
        """Test getting aggregate metrics."""
        aggregate = metrics_collector.get_aggregate_metrics()

        assert "total_flows_started" in aggregate
        assert "total_flows_completed" in aggregate
        assert "total_flows_failed" in aggregate
        assert "success_rate_percentage" in aggregate
        assert isinstance(aggregate["success_rate_percentage"], (int, float))

    def test_get_aggregate_metrics_with_data(self, metrics_collector):
        """Test aggregate metrics calculation with actual data."""
        # Create some flows
        for i in range(10):
            flow_id = uuid4()
            metrics_collector.start_flow_tracking(flow_id)

            status = FlowStatus.COMPLETED if i < 8 else FlowStatus.FAILED

            context = FlowContext(
                flow_instance_id=flow_id,
                flow_type=FlowType.DAILY_CHECKIN,
                patient_id=uuid4(),
                started_at=datetime.utcnow() - timedelta(minutes=5),
            )

            metrics_collector.record_flow_completion(flow_id, status, context)

        aggregate = metrics_collector.get_aggregate_metrics()

        # Should have 80% success rate (8/10)
        assert aggregate["total_flows_completed"] == 8
        assert aggregate["total_flows_failed"] == 2
        assert aggregate["success_rate_percentage"] == 80.0

    def test_get_recent_metrics(self, metrics_collector):
        """Test getting recent metrics."""
        # Create old flow
        old_flow = uuid4()
        metrics_collector._flow_start_times[old_flow] = datetime.utcnow() - timedelta(
            hours=2
        )
        metrics_collector._flow_metrics[old_flow] = FlowMetrics()

        # Create recent flow
        recent_flow = uuid4()
        metrics_collector.start_flow_tracking(recent_flow)

        # Query recent (last hour)
        recent = metrics_collector.get_recent_metrics(minutes=60)

        assert recent["flows_in_window"] == 1


class TestMetricsExport:
    """Test metrics export functionality."""

    def test_export_metrics(self, metrics_collector, flow_instance_id):
        """Test exporting all metrics."""
        metrics_collector.start_flow_tracking(flow_instance_id)

        export = metrics_collector.export_metrics()

        assert "aggregate" in export
        assert "flow_metrics" in export
        assert "step_metrics" in export
        assert "exported_at" in export

    def test_export_metrics_structure(self, metrics_collector):
        """Test exported metrics structure."""
        export = metrics_collector.export_metrics()

        assert isinstance(export["aggregate"], dict)
        assert isinstance(export["flow_metrics"], dict)
        assert isinstance(export["step_metrics"], dict)
        assert isinstance(export["exported_at"], str)


class TestMetricsReset:
    """Test metrics reset functionality."""

    def test_reset_metrics(self, metrics_collector, flow_instance_id):
        """Test resetting all metrics."""
        # Add some data
        metrics_collector.start_flow_tracking(flow_instance_id)
        metrics_collector.start_step_tracking(flow_instance_id, "step_001")

        # Reset
        metrics_collector.reset_metrics()

        # Verify all cleared
        assert len(metrics_collector._flow_metrics) == 0
        assert len(metrics_collector._step_metrics) == 0
        assert len(metrics_collector._flow_start_times) == 0
        assert len(metrics_collector._step_start_times) == 0


class TestAggregateCalculations:
    """Test aggregate metrics calculations."""

    def test_success_rate_calculation_no_flows(self, metrics_collector):
        """Test success rate with no flows."""
        aggregate = metrics_collector.get_aggregate_metrics()
        assert aggregate["success_rate_percentage"] == 0.0

    def test_success_rate_calculation_all_success(self, metrics_collector):
        """Test success rate with all successful flows."""
        for i in range(5):
            flow_id = uuid4()
            metrics_collector.start_flow_tracking(flow_id)
            metrics_collector.record_flow_completion(
                flow_id,
                FlowStatus.COMPLETED,
                FlowContext(
                    flow_instance_id=flow_id,
                    flow_type=FlowType.DAILY_CHECKIN,
                    patient_id=uuid4(),
                ),
            )

        aggregate = metrics_collector.get_aggregate_metrics()
        assert aggregate["success_rate_percentage"] == 100.0

    def test_average_duration_calculation(self, metrics_collector):
        """Test average duration calculation."""
        durations = [60, 120, 180]  # 1, 2, 3 minutes

        for duration in durations:
            flow_id = uuid4()
            metrics_collector._flow_start_times[flow_id] = (
                datetime.utcnow() - timedelta(seconds=duration)
            )
            metrics_collector.start_flow_tracking(flow_id)

            context = FlowContext(
                flow_instance_id=flow_id,
                flow_type=FlowType.DAILY_CHECKIN,
                patient_id=uuid4(),
                started_at=datetime.utcnow() - timedelta(seconds=duration),
            )

            metrics_collector.record_flow_completion(
                flow_id, FlowStatus.COMPLETED, context
            )

        aggregate = metrics_collector.get_aggregate_metrics()
        avg_duration = aggregate["average_flow_duration_seconds"]

        # Average should be around 120 seconds (2 minutes)
        assert 100 <= avg_duration <= 140


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_record_completion_without_start(self, metrics_collector, flow_instance_id):
        """Test recording completion without starting tracking."""
        # Should not crash
        metrics_collector.record_flow_completion(flow_instance_id, FlowStatus.COMPLETED)

        # Metrics should be created
        assert flow_instance_id in metrics_collector._flow_metrics

    def test_multiple_starts_same_flow(self, metrics_collector, flow_instance_id):
        """Test starting tracking multiple times for same flow."""
        metrics_collector.start_flow_tracking(flow_instance_id)
        metrics_collector.start_flow_tracking(flow_instance_id)

        # Should just overwrite
        assert flow_instance_id in metrics_collector._flow_metrics

    def test_step_completion_without_start(self, metrics_collector, flow_instance_id):
        """Test step completion without starting tracking."""
        # Should not crash
        metrics_collector.record_step_completion(
            flow_instance_id, "step_001", FlowStepStatus.COMPLETED
        )

        # Metrics should not include duration (no start time)
        tracking_key = f"{flow_instance_id}:step_001"
        if tracking_key in metrics_collector._step_metrics:
            step_metrics = metrics_collector._step_metrics[tracking_key]
            assert (
                "duration_seconds" not in step_metrics
                or step_metrics["duration_seconds"] is None
            )


class TestFlowTypeMetrics:
    """Test metrics by flow type."""

    def test_get_metrics_by_flow_type(self, metrics_collector):
        """Test getting metrics for specific flow type."""
        metrics = metrics_collector.get_metrics_by_flow_type(FlowType.DAILY_CHECKIN)

        assert isinstance(metrics, dict)
        assert "flow_type" in metrics
        assert metrics["flow_type"] == FlowType.DAILY_CHECKIN.value


class TestStepMetricsCalculation:
    """Test step metrics calculation."""

    def test_average_step_duration(self, metrics_collector, flow_instance_id):
        """Test average step duration calculation."""
        context = FlowContext(
            flow_instance_id=flow_instance_id,
            flow_type=FlowType.DAILY_CHECKIN,
            patient_id=uuid4(),
            started_at=datetime.utcnow() - timedelta(minutes=5),
        )

        # Add steps with different durations
        context.steps_history = [
            FlowStepData(
                step_id=f"step_{i}",
                step_type=FlowStepType.MESSAGE,
                step_name=f"Step {i}",
                status=FlowStepStatus.COMPLETED,
                started_at=datetime.utcnow() - timedelta(seconds=(i + 1) * 10),
                completed_at=datetime.utcnow() - timedelta(seconds=i * 10),
            )
            for i in range(3)
        ]

        metrics_collector.start_flow_tracking(flow_instance_id)
        metrics_collector.record_flow_completion(
            flow_instance_id, FlowStatus.COMPLETED, context
        )

        metrics = metrics_collector.get_flow_metrics(flow_instance_id)
        assert metrics.average_step_duration_seconds is not None
        assert metrics.average_step_duration_seconds > 0
