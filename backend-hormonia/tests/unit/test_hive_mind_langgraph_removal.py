"""Regression tests for removing LangGraph-only HiveMind paths."""

from importlib import import_module
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).resolve().parents[2] / "app" / "services" / "hive_mind_integration.py"
MODULE_NAME = "app.services.hive_mind_integration"


def test_source_has_no_langgraph_only_symbols() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "LANGGRAPH_ONLY" not in source
    assert "_process_with_langgraph" not in source


def test_module_import_and_service_symbol_available(monkeypatch) -> None:
    monkeypatch.setenv("WHATSAPP_WUZAPI_TOKEN", "dummy-test-token")
    sys.modules.pop(MODULE_NAME, None)

    module = import_module(MODULE_NAME)

    assert hasattr(module, "HiveMindIntegrationService")


def test_supported_integration_modes_exclude_langgraph_only(monkeypatch) -> None:
    monkeypatch.setenv("WHATSAPP_WUZAPI_TOKEN", "dummy-test-token")
    sys.modules.pop(MODULE_NAME, None)

    module = import_module(MODULE_NAME)
    mode_values = {mode.value for mode in module.IntegrationMode}

    assert mode_values == {
        "flow_engine_only",
        "hive_mind_only",
        "hybrid",
        "gradual_migration",
    }
