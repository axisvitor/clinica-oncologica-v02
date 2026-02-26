from pathlib import Path

from app.models.alert import AlertSeverity as ModelAlertSeverity
from app.services.flow_monitoring import (
    AlertSeverity as ShimAlertSeverity,
)
from app.services.flow_monitoring import FlowMonitoringService as ShimFlowMonitoringService
from app.services.flow_monitoring_pkg.alerting import FlowMonitoringAlertingMixin
from app.services.flow_monitoring_pkg.health import FlowMonitoringHealthMixin
from app.services.flow_monitoring_pkg.metrics import FlowMonitoringMetricsMixin
from app.services.flow_monitoring_pkg.service import (
    FlowMonitoringService as CanonicalFlowMonitoringService,
)
from app.services.flow_monitoring_pkg.trends import FlowMonitoringTrendsMixin


def test_shim_resolves_to_canonical() -> None:
    assert ShimFlowMonitoringService is CanonicalFlowMonitoringService


def test_alert_severity_reexported() -> None:
    assert ShimAlertSeverity is ModelAlertSeverity


def test_split_files_under_500_lines() -> None:
    root = Path(__file__).resolve().parents[3]
    files = [
        root / "app/services/flow_monitoring_pkg/models.py",
        root / "app/services/flow_monitoring_pkg/metrics.py",
        root / "app/services/flow_monitoring_pkg/health.py",
        root / "app/services/flow_monitoring_pkg/alerting.py",
        root / "app/services/flow_monitoring_pkg/trends.py",
        root / "app/services/flow_monitoring_pkg/service.py",
    ]

    for file_path in files:
        line_count = len(file_path.read_text(encoding="utf-8").splitlines())
        assert line_count < 500, f"{file_path} has {line_count} lines"


def test_responsibilities_split_by_module() -> None:
    assert (
        FlowMonitoringMetricsMixin.collect_performance_metrics.__module__
        == "app.services.flow_monitoring_pkg.metrics"
    )
    assert (
        FlowMonitoringHealthMixin.run_health_checks.__module__
        == "app.services.flow_monitoring_pkg.health"
    )
    assert (
        FlowMonitoringAlertingMixin.check_and_create_alerts.__module__
        == "app.services.flow_monitoring_pkg.alerting"
    )
    assert (
        FlowMonitoringTrendsMixin._get_performance_trends.__module__
        == "app.services.flow_monitoring_pkg.trends"
    )
