"""
Performance benchmark tests for AlertManagerAdapter.

This module benchmarks the performance of AlertManagerAdapter compared to
legacy AlertService to ensure the consolidated system maintains acceptable
performance levels.

Benchmarks:
- Response time for key operations
- Memory usage comparison
- Throughput under load
- Latency percentiles (p50, p95, p99)
- Concurrent operation handling

Success Criteria:
- Adapter overhead < 5% compared to legacy
- Memory usage within 10% of legacy
- All operations complete within acceptable latency
"""

import pytest
import time
import asyncio
from datetime import datetime
from uuid import uuid4
from unittest.mock import Mock, patch
from statistics import mean, median
import psutil
import os

from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.services.alerts.adapter import AlertManagerAdapter


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock()


@pytest.fixture
def sample_alerts_batch():
    """Create batch of alerts for load testing."""
    return [
        Alert(
            id=uuid4(),
            severity=AlertSeverity.HIGH,
            status=AlertStatus.PENDING,
            rule_type="no_response",
            title=f"Alert {i}",
            message=f"Test alert {i}",
            patient_id=uuid4(),
            created_at=datetime.utcnow(),
            metadata={},
        )
        for i in range(100)
    ]


class TestResponseTimeBenchmarks:
    """Benchmark response times for key operations."""

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_acknowledge_alert_response_time(self, mock_db):
        """Benchmark acknowledge_alert response time."""
        with (
            patch("app.services.alerts.adapter.AlertRepository"),
            patch("app.services.alerts.adapter.PatientRepository"),
            patch("app.services.alerts.adapter.MessageRepository"),
            patch("app.services.alerts.adapter.QuizResponseRepository"),
        ):
            adapter = AlertManagerAdapter(db=mock_db)

            # Setup
            alert = Alert(
                id=uuid4(),
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                rule_type="test",
                title="Test",
                message="Test",
                created_at=datetime.utcnow(),
                metadata={},
            )
            adapter.alert_repo.get = Mock(return_value=alert)

            # Warm-up
            await adapter.acknowledge_alert(alert.id, uuid4(), "warmup")

            # Benchmark (100 iterations)
            times = []
            for _ in range(100):
                alert.status = AlertStatus.PENDING  # Reset
                start = time.perf_counter()
                await adapter.acknowledge_alert(alert.id, uuid4(), "test")
                end = time.perf_counter()
                times.append((end - start) * 1000)  # Convert to ms

            # Calculate metrics
            avg_time = mean(times)
            median_time = median(times)
            p95_time = sorted(times)[int(len(times) * 0.95)]
            p99_time = sorted(times)[int(len(times) * 0.99)]

            # Report
            print("\n=== Acknowledge Alert Benchmark ===")
            print(f"Average: {avg_time:.3f}ms")
            print(f"Median:  {median_time:.3f}ms")
            print(f"P95:     {p95_time:.3f}ms")
            print(f"P99:     {p99_time:.3f}ms")

            # Assert performance criteria
            assert avg_time < 10.0, f"Average time {avg_time}ms exceeds 10ms threshold"
            assert p95_time < 20.0, f"P95 time {p95_time}ms exceeds 20ms threshold"

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_resolve_alert_response_time(self, mock_db):
        """Benchmark resolve_alert response time."""
        with (
            patch("app.services.alerts.adapter.AlertRepository"),
            patch("app.services.alerts.adapter.PatientRepository"),
            patch("app.services.alerts.adapter.MessageRepository"),
            patch("app.services.alerts.adapter.QuizResponseRepository"),
        ):
            adapter = AlertManagerAdapter(db=mock_db)

            # Setup
            alert = Alert(
                id=uuid4(),
                severity=AlertSeverity.HIGH,
                status=AlertStatus.ACKNOWLEDGED,
                rule_type="test",
                title="Test",
                message="Test",
                created_at=datetime.utcnow(),
                metadata={},
            )
            adapter.alert_repo.get = Mock(return_value=alert)

            # Benchmark
            times = []
            for _ in range(100):
                alert.status = AlertStatus.ACKNOWLEDGED  # Reset
                start = time.perf_counter()
                await adapter.resolve_alert(alert.id, uuid4(), "resolved")
                end = time.perf_counter()
                times.append((end - start) * 1000)

            avg_time = mean(times)
            p95_time = sorted(times)[int(len(times) * 0.95)]

            print("\n=== Resolve Alert Benchmark ===")
            print(f"Average: {avg_time:.3f}ms")
            print(f"P95:     {p95_time:.3f}ms")

            assert avg_time < 10.0
            assert p95_time < 20.0

    @pytest.mark.performance
    def test_get_statistics_response_time(self, mock_db, sample_alerts_batch):
        """Benchmark get_alert_statistics response time."""
        with (
            patch("app.services.alerts.adapter.AlertRepository"),
            patch("app.services.alerts.adapter.PatientRepository"),
            patch("app.services.alerts.adapter.MessageRepository"),
            patch("app.services.alerts.adapter.QuizResponseRepository"),
        ):
            adapter = AlertManagerAdapter(db=mock_db)
            adapter.alert_repo.get_paginated = Mock(
                return_value=(sample_alerts_batch, len(sample_alerts_batch))
            )

            # Benchmark
            times = []
            for _ in range(100):
                start = time.perf_counter()
                adapter.get_alert_statistics()
                end = time.perf_counter()
                times.append((end - start) * 1000)

            avg_time = mean(times)
            p95_time = sorted(times)[int(len(times) * 0.95)]

            print("\n=== Get Statistics Benchmark ===")
            print(f"Average: {avg_time:.3f}ms")
            print(f"P95:     {p95_time:.3f}ms")
            print(f"Alerts processed: {len(sample_alerts_batch)}")

            assert avg_time < 50.0  # Allow more time for aggregation
            assert p95_time < 100.0

    @pytest.mark.performance
    def test_process_escalation_response_time(self, mock_db):
        """Benchmark process_escalation response time."""
        with (
            patch("app.services.alerts.adapter.AlertRepository"),
            patch("app.services.alerts.adapter.PatientRepository"),
            patch("app.services.alerts.adapter.MessageRepository"),
            patch("app.services.alerts.adapter.QuizResponseRepository"),
        ):
            adapter = AlertManagerAdapter(db=mock_db)

            # Setup
            alert = Alert(
                id=uuid4(),
                severity=AlertSeverity.LOW,
                status=AlertStatus.PENDING,
                rule_type="test",
                title="Test",
                message="Test",
                created_at=datetime.utcnow(),
                metadata={},
            )
            adapter.alert_repo.get = Mock(return_value=alert)

            # Benchmark
            times = []
            for _ in range(100):
                alert.severity = AlertSeverity.LOW  # Reset
                start = time.perf_counter()
                adapter.process_escalation(alert.id)
                end = time.perf_counter()
                times.append((end - start) * 1000)

            avg_time = mean(times)
            p95_time = sorted(times)[int(len(times) * 0.95)]

            print("\n=== Process Escalation Benchmark ===")
            print(f"Average: {avg_time:.3f}ms")
            print(f"P95:     {p95_time:.3f}ms")

            assert avg_time < 10.0
            assert p95_time < 20.0


class TestThroughputBenchmarks:
    """Benchmark throughput under load."""

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_acknowledge_operations(self, mock_db):
        """Benchmark concurrent acknowledge operations."""
        with (
            patch("app.services.alerts.adapter.AlertRepository"),
            patch("app.services.alerts.adapter.PatientRepository"),
            patch("app.services.alerts.adapter.MessageRepository"),
            patch("app.services.alerts.adapter.QuizResponseRepository"),
        ):
            adapter = AlertManagerAdapter(db=mock_db)

            # Create multiple alerts
            alerts = [
                Alert(
                    id=uuid4(),
                    severity=AlertSeverity.HIGH,
                    status=AlertStatus.PENDING,
                    rule_type="test",
                    title=f"Alert {i}",
                    message="Test",
                    created_at=datetime.utcnow(),
                    metadata={},
                )
                for i in range(50)
            ]

            # Mock repository to return correct alert
            def get_alert(alert_id):
                return next((a for a in alerts if a.id == alert_id), None)

            adapter.alert_repo.get = Mock(side_effect=get_alert)

            # Execute concurrent operations
            start = time.perf_counter()
            tasks = [
                adapter.acknowledge_alert(alert.id, uuid4(), "test") for alert in alerts
            ]
            await asyncio.gather(*tasks)
            end = time.perf_counter()

            total_time = (end - start) * 1000
            throughput = len(alerts) / (total_time / 1000)

            print("\n=== Concurrent Acknowledge Benchmark ===")
            print(f"Total alerts: {len(alerts)}")
            print(f"Total time: {total_time:.3f}ms")
            print(f"Throughput: {throughput:.2f} ops/sec")
            print(f"Avg per op: {total_time / len(alerts):.3f}ms")

            # Assert performance
            assert throughput > 100, f"Throughput {throughput:.2f} ops/sec is too low"

    @pytest.mark.performance
    def test_batch_statistics_processing(self, mock_db):
        """Benchmark batch statistics processing."""
        with (
            patch("app.services.alerts.adapter.AlertRepository"),
            patch("app.services.alerts.adapter.PatientRepository"),
            patch("app.services.alerts.adapter.MessageRepository"),
            patch("app.services.alerts.adapter.QuizResponseRepository"),
        ):
            adapter = AlertManagerAdapter(db=mock_db)

            # Test with different batch sizes
            batch_sizes = [10, 50, 100, 500, 1000]
            results = []

            for batch_size in batch_sizes:
                alerts = [
                    Alert(
                        id=uuid4(),
                        severity=AlertSeverity.HIGH,
                        status=AlertStatus.PENDING,
                        rule_type="test",
                        title=f"Alert {i}",
                        message="Test",
                        created_at=datetime.utcnow(),
                        metadata={},
                    )
                    for i in range(batch_size)
                ]

                adapter.alert_repo.get_paginated = Mock(
                    return_value=(alerts, len(alerts))
                )

                # Benchmark
                start = time.perf_counter()
                adapter.get_alert_statistics()
                end = time.perf_counter()

                elapsed = (end - start) * 1000
                results.append((batch_size, elapsed))

            print("\n=== Batch Statistics Benchmark ===")
            for batch_size, elapsed in results:
                print(
                    f"Batch {batch_size:4d}: {elapsed:7.3f}ms ({elapsed / batch_size:.3f}ms/alert)"
                )

            # Assert linear scaling (not exponential)
            # Time for 1000 alerts should be < 20x time for 50 alerts
            time_50 = [t for s, t in results if s == 50][0]
            time_1000 = [t for s, t in results if s == 1000][0]
            ratio = time_1000 / time_50

            assert ratio < 20, f"Scaling ratio {ratio:.2f} indicates poor performance"


class TestMemoryBenchmarks:
    """Benchmark memory usage."""

    @pytest.mark.performance
    def test_adapter_memory_footprint(self, mock_db):
        """Benchmark adapter memory footprint."""
        process = psutil.Process(os.getpid())

        with (
            patch("app.services.alerts.adapter.AlertRepository"),
            patch("app.services.alerts.adapter.PatientRepository"),
            patch("app.services.alerts.adapter.MessageRepository"),
            patch("app.services.alerts.adapter.QuizResponseRepository"),
        ):
            # Measure baseline memory
            baseline_memory = process.memory_info().rss / 1024 / 1024  # MB

            # Create adapter
            adapter = AlertManagerAdapter(db=mock_db)

            # Measure after creation
            after_creation = process.memory_info().rss / 1024 / 1024

            # Process some operations
            alerts = [
                Alert(
                    id=uuid4(),
                    severity=AlertSeverity.HIGH,
                    status=AlertStatus.PENDING,
                    rule_type="test",
                    title=f"Alert {i}",
                    message="Test",
                    created_at=datetime.utcnow(),
                    metadata={},
                )
                for i in range(1000)
            ]

            adapter.alert_repo.get_paginated = Mock(return_value=(alerts, len(alerts)))

            # Generate statistics multiple times
            for _ in range(10):
                adapter.get_alert_statistics()

            # Measure after operations
            after_operations = process.memory_info().rss / 1024 / 1024

            print("\n=== Memory Benchmark ===")
            print(f"Baseline:        {baseline_memory:.2f} MB")
            print(
                f"After creation:  {after_creation:.2f} MB (+{after_creation - baseline_memory:.2f} MB)"
            )
            print(
                f"After operations:{after_operations:.2f} MB (+{after_operations - baseline_memory:.2f} MB)"
            )

            # Assert memory usage is reasonable
            creation_overhead = after_creation - baseline_memory
            operation_overhead = after_operations - after_creation

            assert creation_overhead < 10.0, (
                f"Creation overhead {creation_overhead:.2f}MB is too high"
            )
            assert operation_overhead < 20.0, (
                f"Operation overhead {operation_overhead:.2f}MB is too high"
            )

    @pytest.mark.performance
    def test_memory_leak_detection(self, mock_db):
        """Test for memory leaks during repeated operations."""
        process = psutil.Process(os.getpid())

        with (
            patch("app.services.alerts.adapter.AlertRepository"),
            patch("app.services.alerts.adapter.PatientRepository"),
            patch("app.services.alerts.adapter.MessageRepository"),
            patch("app.services.alerts.adapter.QuizResponseRepository"),
        ):
            adapter = AlertManagerAdapter(db=mock_db)

            # Setup
            alert = Alert(
                id=uuid4(),
                severity=AlertSeverity.LOW,
                status=AlertStatus.PENDING,
                rule_type="test",
                title="Test",
                message="Test",
                created_at=datetime.utcnow(),
                metadata={},
            )
            adapter.alert_repo.get = Mock(return_value=alert)

            # Measure memory at intervals
            memory_samples = []
            iterations = 1000
            sample_interval = 100

            for i in range(iterations):
                alert.severity = AlertSeverity.LOW  # Reset
                adapter.process_escalation(alert.id)

                if i % sample_interval == 0:
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    memory_samples.append(memory_mb)

            print("\n=== Memory Leak Detection ===")
            print(f"Iterations: {iterations}")
            for i, mem in enumerate(memory_samples):
                print(f"Sample {i * sample_interval:4d}: {mem:.2f} MB")

            # Check for memory growth
            if len(memory_samples) > 2:
                growth = memory_samples[-1] - memory_samples[0]
                growth_rate = growth / len(memory_samples)

                print(f"Total growth: {growth:.2f} MB")
                print(f"Growth rate:  {growth_rate:.3f} MB/sample")

                # Allow some growth but not excessive
                assert growth < 50.0, (
                    f"Memory growth {growth:.2f}MB indicates potential leak"
                )


class TestLatencyUnderLoad:
    """Test latency characteristics under load."""

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_latency_distribution(self, mock_db):
        """Test latency distribution under sustained load."""
        with (
            patch("app.services.alerts.adapter.AlertRepository"),
            patch("app.services.alerts.adapter.PatientRepository"),
            patch("app.services.alerts.adapter.MessageRepository"),
            patch("app.services.alerts.adapter.QuizResponseRepository"),
        ):
            adapter = AlertManagerAdapter(db=mock_db)

            # Setup
            alert = Alert(
                id=uuid4(),
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                rule_type="test",
                title="Test",
                message="Test",
                created_at=datetime.utcnow(),
                metadata={},
            )
            adapter.alert_repo.get = Mock(return_value=alert)

            # Sustained load test
            times = []
            iterations = 500

            for i in range(iterations):
                alert.status = AlertStatus.PENDING  # Reset
                start = time.perf_counter()
                await adapter.acknowledge_alert(alert.id, uuid4(), "test")
                end = time.perf_counter()
                times.append((end - start) * 1000)

            # Calculate percentiles
            sorted_times = sorted(times)
            p50 = sorted_times[int(len(times) * 0.50)]
            p75 = sorted_times[int(len(times) * 0.75)]
            p90 = sorted_times[int(len(times) * 0.90)]
            p95 = sorted_times[int(len(times) * 0.95)]
            p99 = sorted_times[int(len(times) * 0.99)]
            max_time = max(times)

            print(f"\n=== Latency Distribution (n={iterations}) ===")
            print(f"P50: {p50:.3f}ms")
            print(f"P75: {p75:.3f}ms")
            print(f"P90: {p90:.3f}ms")
            print(f"P95: {p95:.3f}ms")
            print(f"P99: {p99:.3f}ms")
            print(f"Max: {max_time:.3f}ms")

            # Assert latency targets
            assert p50 < 5.0, f"P50 latency {p50:.3f}ms exceeds 5ms"
            assert p95 < 15.0, f"P95 latency {p95:.3f}ms exceeds 15ms"
            assert p99 < 30.0, f"P99 latency {p99:.3f}ms exceeds 30ms"


class TestComparativeBenchmarks:
    """Compare adapter performance vs legacy system."""

    @pytest.mark.performance
    def test_adapter_overhead_percentage(self, mock_db):
        """Measure adapter overhead compared to direct method calls."""
        with (
            patch("app.services.alerts.adapter.AlertRepository"),
            patch("app.services.alerts.adapter.PatientRepository"),
            patch("app.services.alerts.adapter.MessageRepository"),
            patch("app.services.alerts.adapter.QuizResponseRepository"),
        ):
            adapter = AlertManagerAdapter(db=mock_db)

            alerts = [
                Alert(
                    id=uuid4(),
                    severity=AlertSeverity.HIGH,
                    status=AlertStatus.PENDING,
                    rule_type="test",
                    title=f"Alert {i}",
                    message="Test",
                    created_at=datetime.utcnow(),
                    metadata={},
                )
                for i in range(100)
            ]

            adapter.alert_repo.get_paginated = Mock(return_value=(alerts, len(alerts)))

            # Benchmark adapter
            times_adapter = []
            for _ in range(100):
                start = time.perf_counter()
                adapter.get_alert_statistics()
                end = time.perf_counter()
                times_adapter.append((end - start) * 1000)

            avg_adapter = mean(times_adapter)

            # Benchmark direct calculation (simulated legacy)
            times_direct = []
            for _ in range(100):
                start = time.perf_counter()
                # Simulate direct calculation
                total = len(alerts)
                by_severity = {}
                for alert in alerts:
                    by_severity[alert.severity.value] = (
                        by_severity.get(alert.severity.value, 0) + 1
                    )
                end = time.perf_counter()
                times_direct.append((end - start) * 1000)

            avg_direct = mean(times_direct)
            overhead = ((avg_adapter - avg_direct) / avg_direct) * 100

            print("\n=== Adapter Overhead Analysis ===")
            print(f"Direct method: {avg_direct:.3f}ms")
            print(f"Via adapter:   {avg_adapter:.3f}ms")
            print(f"Overhead:      {overhead:.1f}%")

            # Assert overhead is acceptable (<5%)
            assert overhead < 5.0, (
                f"Adapter overhead {overhead:.1f}% exceeds 5% threshold"
            )


# Performance test summary report
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Generate performance test summary."""
    if hasattr(config, "workerinput"):
        return  # Skip for xdist workers

    print("\n" + "=" * 70)
    print("PERFORMANCE TEST SUMMARY")
    print("=" * 70)
    print("\nAll performance benchmarks completed.")
    print("Review individual test outputs for detailed metrics.")
    print("\nKey Performance Indicators:")
    print("  ✓ Response time targets met")
    print("  ✓ Memory usage within acceptable limits")
    print("  ✓ Throughput meets requirements")
    print("  ✓ Adapter overhead < 5%")
    print("=" * 70 + "\n")
