"""
Test suite to validate SagaOrchestrator refactoring.

This test verifies that:
1. Core public API is importable
2. Expected methods exist on SagaOrchestrator
3. Public types are available for monitoring and status reporting
"""

import pytest

from app.models.enums import SagaStatus


def test_public_imports():
    """Test that current public imports are available."""
    from app.orchestration.saga_orchestrator import (
        SagaOrchestrator,
        SagaStepExecutor,
        SagaCompensator,
        SagaPersistence,
        SagaLogEntry,
        SagaStatusInfo,
        FailedSagaSummary,
        CompensationResult,
        ResumeResult,
        SagaError,
        SagaCompensationError,
        SagaStepError,
        SagaLockError,
        SagaNotFoundError,
        SagaAlreadyCompletedError,
    )

    assert SagaOrchestrator is not None
    assert SagaStepExecutor is not None
    assert SagaCompensator is not None
    assert SagaPersistence is not None
    assert SagaStatus is not None
    assert SagaLogEntry is not None
    assert SagaStatusInfo is not None
    assert FailedSagaSummary is not None
    assert CompensationResult is not None
    assert ResumeResult is not None
    assert SagaError is not None
    assert SagaCompensationError is not None
    assert SagaStepError is not None
    assert SagaLockError is not None
    assert SagaNotFoundError is not None
    assert SagaAlreadyCompletedError is not None


def test_individual_module_imports():
    """Test that individual modules can be imported."""
    from app.orchestration.saga_orchestrator import SagaOrchestrator
    from app.orchestration.saga_orchestrator import SagaStepExecutor
    from app.orchestration.saga_orchestrator import SagaCompensator
    from app.orchestration.saga_orchestrator import SagaPersistence

    assert SagaOrchestrator is not None
    assert SagaStepExecutor is not None
    assert SagaCompensator is not None
    assert SagaPersistence is not None


def test_orchestrator_has_all_methods():
    """Test that SagaOrchestrator has all required methods."""
    from app.orchestration.saga_orchestrator import SagaOrchestrator

    assert hasattr(SagaOrchestrator, "execute_patient_onboarding_saga")
    assert hasattr(SagaOrchestrator, "resume_saga")
    assert hasattr(SagaOrchestrator, "get_saga_status")
    assert hasattr(SagaOrchestrator, "list_failed_sagas")
    assert hasattr(SagaOrchestrator, "_compensate_saga")
    assert hasattr(SagaOrchestrator, "_track_compensation_failure")


def test_enums_are_accessible():
    """Test that saga enums are accessible."""
    assert hasattr(SagaStatus, "STARTED")
    assert hasattr(SagaStatus, "IN_PROGRESS")
    assert hasattr(SagaStatus, "COMPLETED")
    assert hasattr(SagaStatus, "COMPENSATING")
    assert hasattr(SagaStatus, "COMPENSATED")
    assert hasattr(SagaStatus, "FAILED")
    assert hasattr(SagaStatus, "RETRY_SCHEDULED")


def test_types_are_accessible():
    """Test that monitoring types are accessible."""
    from app.orchestration.saga_orchestrator import (
        SagaLogEntry,
        SagaStatusInfo,
        FailedSagaSummary,
        CompensationResult,
        ResumeResult,
    )

    for type_obj in (
        SagaLogEntry,
        SagaStatusInfo,
        FailedSagaSummary,
        CompensationResult,
        ResumeResult,
    ):
        assert hasattr(type_obj, "__annotations__")


if __name__ == "__main__":
    print("Running SagaOrchestrator refactoring validation tests...")
    pytest.main([__file__, "-v"])
