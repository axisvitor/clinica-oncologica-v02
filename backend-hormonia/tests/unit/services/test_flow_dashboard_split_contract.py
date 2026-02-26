from pathlib import Path

from app.services.flow_dashboard import (
    DashboardTimeframe as ShimDashboardTimeframe,
    FlowDashboardService as ShimFlowDashboardService,
    TrendDirection as ShimTrendDirection,
    get_flow_dashboard_service as shim_get_flow_dashboard_service,
)
from app.services.flow_dashboard_pkg import (
    DashboardTimeframe,
    TrendDirection,
    get_flow_dashboard_service,
)
from app.services.flow_dashboard_pkg.alerts import FlowDashboardAlertsMixin
from app.services.flow_dashboard_pkg.analytics import FlowDashboardAnalyticsMixin
from app.services.flow_dashboard_pkg.optimization import FlowDashboardOptimizationMixin
from app.services.flow_dashboard_pkg.risk import FlowDashboardRiskMixin
from app.services.flow_dashboard_pkg.service import (
    FlowDashboardService as CanonicalFlowDashboardService,
)
from app.services.flow_dashboard_pkg.trends import FlowDashboardTrendsMixin


def test_shim_resolves_to_canonical() -> None:
    assert ShimFlowDashboardService is CanonicalFlowDashboardService


def test_factory_function_reexported() -> None:
    assert callable(shim_get_flow_dashboard_service)
    assert shim_get_flow_dashboard_service is get_flow_dashboard_service


def test_enums_reexported() -> None:
    assert ShimDashboardTimeframe is DashboardTimeframe
    assert ShimTrendDirection is TrendDirection


def test_split_files_under_500_lines() -> None:
    root = Path(__file__).resolve().parents[3]
    files = [
        root / "app/services/flow_dashboard_pkg/models.py",
        root / "app/services/flow_dashboard_pkg/analytics.py",
        root / "app/services/flow_dashboard_pkg/trends.py",
        root / "app/services/flow_dashboard_pkg/risk.py",
        root / "app/services/flow_dashboard_pkg/alerts.py",
        root / "app/services/flow_dashboard_pkg/optimization.py",
        root / "app/services/flow_dashboard_pkg/service.py",
    ]

    for file_path in files:
        line_count = len(file_path.read_text(encoding="utf-8").splitlines())
        assert line_count < 500, f"{file_path} has {line_count} lines"


def test_responsibilities_split_by_module() -> None:
    assert (
        FlowDashboardAnalyticsMixin.get_dashboard_overview.__module__
        == "app.services.flow_dashboard_pkg.analytics"
    )
    assert (
        FlowDashboardTrendsMixin.get_patient_engagement_trends.__module__
        == "app.services.flow_dashboard_pkg.trends"
    )
    assert (
        FlowDashboardRiskMixin.get_at_risk_patient_dashboard.__module__
        == "app.services.flow_dashboard_pkg.risk"
    )
    assert (
        FlowDashboardAlertsMixin.get_real_time_alerts.__module__
        == "app.services.flow_dashboard_pkg.alerts"
    )
    assert (
        FlowDashboardOptimizationMixin.get_flow_optimization_recommendations.__module__
        == "app.services.flow_dashboard_pkg.optimization"
    )
