from pathlib import Path


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_compensator_import_unchanged() -> None:
    from app.orchestration.saga_orchestrator.compensation import SagaCompensator as from_compensation
    from app.orchestration.saga_orchestrator import SagaCompensator as from_package

    assert from_compensation is from_package


def test_handler_functions_importable() -> None:
    from app.orchestration.saga_orchestrator.compensation_handlers import (
        compensate_flow,
        compensate_message,
        compensate_patient,
        track_compensation_failure,
    )

    assert callable(compensate_message)
    assert callable(compensate_flow)
    assert callable(compensate_patient)
    assert callable(track_compensation_failure)


def test_compensation_under_500_lines() -> None:
    compensation_path = (
        _backend_root() / "app" / "orchestration" / "saga_orchestrator" / "compensation.py"
    )
    assert len(compensation_path.read_text(encoding="utf-8").splitlines()) < 500


def test_compensation_handlers_under_500_lines() -> None:
    handlers_path = (
        _backend_root()
        / "app"
        / "orchestration"
        / "saga_orchestrator"
        / "compensation_handlers.py"
    )
    assert len(handlers_path.read_text(encoding="utf-8").splitlines()) < 500


def test_no_circular_import() -> None:
    handlers_path = (
        _backend_root()
        / "app"
        / "orchestration"
        / "saga_orchestrator"
        / "compensation_handlers.py"
    )
    content = handlers_path.read_text(encoding="utf-8")

    assert "from .compensation import" not in content
    assert "from app.orchestration.saga_orchestrator.compensation import" not in content


def test_compensator_private_methods_exist() -> None:
    from app.orchestration.saga_orchestrator.compensation import SagaCompensator

    assert hasattr(SagaCompensator, "_compensate_message")
    assert hasattr(SagaCompensator, "_compensate_flow")
    assert hasattr(SagaCompensator, "_compensate_patient")
    assert hasattr(SagaCompensator, "_track_compensation_failure")
