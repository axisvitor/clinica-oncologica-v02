"""Contract tests verifying compatibility shim export parity."""

import importlib

import pytest


SHIM_REGISTRY = {
    "app.services.flow_core": {
        "FLOW_ADVANCE_BLOCKED_CODE",
        "FLOW_ADVANCE_BLOCKED_MESSAGE",
        "FLOW_ADVANCE_BLOCKED_REASON",
        "FlowCore",
        "NotFoundError",
        "ValidationError",
    },
    "app.services.enhanced_flow_engine": {
        "EnhancedFlowEngine",
        "FlowContext",
        "FlowType",
        "get_enhanced_flow_engine",
        "test_enhanced_flow_engine",
    },
    "app.services.flow_management": {
        "FLOW_ADVANCE_BLOCKED_CODE",
        "FLOW_ADVANCE_BLOCKED_MESSAGE",
        "FLOW_ADVANCE_BLOCKED_REASON",
        "EnhancedFlowEngine",
        "FlowManagementService",
        "now_sao_paulo",
    },
    "app.services.flow_dashboard": {
        "FlowDashboardService",
        "DashboardTimeframe",
        "TrendDirection",
        "get_flow_dashboard_service",
    },
    "app.services.flow_monitoring": {
        "FlowMonitoringService",
        "HealthStatus",
        "PerformanceMetrics",
        "SystemAlert",
        "AlertSeverity",
    },
    "app.services.flow_integrity": {
        "FlowIntegrityService",
        "get_flow_integrity_service",
    },
}


@pytest.mark.parametrize(
    "shim_module_name,expected_symbols",
    list(SHIM_REGISTRY.items()),
    ids=list(SHIM_REGISTRY.keys()),
)
class TestShimSymbolParity:
    def test_shim_all_matches_expected_symbol_set(
        self,
        shim_module_name,
        expected_symbols,
    ):
        module = importlib.import_module(shim_module_name)
        assert hasattr(module, "__all__"), f"{shim_module_name} must define __all__"
        actual_all = set(module.__all__)
        missing = expected_symbols - actual_all
        extra = actual_all - expected_symbols
        assert not missing and not extra, (
            f"{shim_module_name}: missing={missing}, extra={extra}"
        )

    def test_shim_all_symbols_are_importable(self, shim_module_name, expected_symbols):
        del expected_symbols
        module = importlib.import_module(shim_module_name)
        for symbol in module.__all__:
            assert hasattr(module, symbol), (
                f"{shim_module_name}.{symbol} in __all__ but not importable"
            )

    def test_shim_all_symbols_are_not_none(self, shim_module_name, expected_symbols):
        del expected_symbols
        module = importlib.import_module(shim_module_name)
        for symbol in module.__all__:
            assert getattr(module, symbol) is not None, (
                f"{shim_module_name}.{symbol} resolved to None"
            )
