"""
Phase 29 audit verification tests for saga orchestrator package.

Covers:
- AUDIT-02: Shim re-export identity verification (6 sub-modules)
- AUDIT-03: Support module type definitions match callers
- AUDIT-04: __init__.py __all__ completeness
"""

from app.orchestration import saga_orchestrator as pkg


def test_orchestrator_identity() -> None:
    from app.orchestration.saga_orchestrator import SagaOrchestrator
    from app.orchestration.saga_orchestrator.orchestrator import SagaOrchestrator as direct

    assert SagaOrchestrator is direct


def test_step_executor_identity() -> None:
    from app.orchestration.saga_orchestrator import SagaStepExecutor
    from app.orchestration.saga_orchestrator.steps import SagaStepExecutor as direct

    assert SagaStepExecutor is direct


def test_compensator_identity() -> None:
    from app.orchestration.saga_orchestrator import SagaCompensator
    from app.orchestration.saga_orchestrator.compensation import SagaCompensator as direct

    assert SagaCompensator is direct


def test_persistence_identity() -> None:
    from app.orchestration.saga_orchestrator import SagaPersistence
    from app.orchestration.saga_orchestrator.persistence import SagaPersistence as direct

    assert SagaPersistence is direct


def test_exception_identities() -> None:
    from app.orchestration.saga_orchestrator.exceptions import (
        SagaAlreadyCompletedError,
        SagaCompensationError,
        SagaError,
        SagaLockError,
        SagaNotFoundError,
        SagaStepError,
    )

    assert pkg.SagaError is SagaError
    assert pkg.SagaCompensationError is SagaCompensationError
    assert pkg.SagaStepError is SagaStepError
    assert pkg.SagaLockError is SagaLockError
    assert pkg.SagaNotFoundError is SagaNotFoundError
    assert pkg.SagaAlreadyCompletedError is SagaAlreadyCompletedError


def test_type_identities() -> None:
    from app.orchestration.saga_orchestrator.types import (
        CompensationResult,
        FailedSagaSummary,
        ResumeResult,
        SagaLogEntry,
        SagaStatusInfo,
    )

    assert pkg.SagaLogEntry is SagaLogEntry
    assert pkg.SagaStatusInfo is SagaStatusInfo
    assert pkg.FailedSagaSummary is FailedSagaSummary
    assert pkg.CompensationResult is CompensationResult
    assert pkg.ResumeResult is ResumeResult


def test_all_symbols_resolve() -> None:
    for name in pkg.__all__:
        assert hasattr(pkg, name), f"__all__ contains '{name}' but it is not importable"


def test_all_covers_all_reexported_modules() -> None:
    expected = {
        "SagaOrchestrator",
        "SagaStepExecutor",
        "SagaCompensator",
        "SagaPersistence",
        "SagaError",
        "SagaCompensationError",
        "SagaStepError",
        "SagaLockError",
        "SagaNotFoundError",
        "SagaAlreadyCompletedError",
        "SagaLogEntry",
        "SagaStatusInfo",
        "FailedSagaSummary",
        "CompensationResult",
        "ResumeResult",
    }

    actual = set(pkg.__all__)
    missing = expected - actual
    assert not missing, f"Missing from __all__: {missing}"


def test_saga_log_entry_matches_runtime() -> None:
    from app.orchestration.saga_orchestrator.types import SagaLogEntry

    fields = set(SagaLogEntry.__annotations__.keys())
    expected = {"step", "action", "status", "timestamp", "message"}
    assert fields == expected, f"SagaLogEntry fields {fields} != expected {expected}"


def test_compensation_result_importable() -> None:
    from app.orchestration.saga_orchestrator.types import CompensationResult

    assert "step" in CompensationResult.__annotations__
    assert "success" in CompensationResult.__annotations__
