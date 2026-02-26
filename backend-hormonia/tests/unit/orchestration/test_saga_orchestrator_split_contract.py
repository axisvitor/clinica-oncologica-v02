"""Contract tests for saga orchestrator SPLIT-08 compatibility."""

from pathlib import Path

from app.orchestration.saga_orchestrator import SagaOrchestrator
from app.orchestration.saga_orchestrator.metrics import (
    METRICS_AVAILABLE,
    SAGA_STARTS_TOTAL,
    _detect_phone_format,
)
from app.orchestration.saga_orchestrator.orchestrator import SagaOrchestrator as SO2


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_package_import_unchanged() -> None:
    assert SagaOrchestrator is SO2


def test_metrics_module_exports() -> None:
    assert isinstance(METRICS_AVAILABLE, bool)
    assert SAGA_STARTS_TOTAL is not None or METRICS_AVAILABLE is False
    assert callable(_detect_phone_format)


def test_orchestrator_under_500_lines() -> None:
    orchestrator_path = (
        _backend_root()
        / "app"
        / "orchestration"
        / "saga_orchestrator"
        / "orchestrator.py"
    )
    assert len(orchestrator_path.read_text(encoding="utf-8").splitlines()) < 500


def test_metrics_under_500_lines() -> None:
    metrics_path = (
        _backend_root()
        / "app"
        / "orchestration"
        / "saga_orchestrator"
        / "metrics.py"
    )
    assert len(metrics_path.read_text(encoding="utf-8").splitlines()) < 500


def test_detect_phone_format_behavior() -> None:
    assert _detect_phone_format("+5511999990000") == "e164"
    assert _detect_phone_format("11999990000") == "brazilian"
    assert _detect_phone_format("") == "other"


def test_compat_wrappers_exist() -> None:
    for method_name in [
        "_compensate_saga",
        "_compensate_message",
        "_compensate_flow",
        "_compensate_patient",
        "_track_compensation_failure",
        "_compensate_step_with_retry",
    ]:
        assert hasattr(SagaOrchestrator, method_name)
