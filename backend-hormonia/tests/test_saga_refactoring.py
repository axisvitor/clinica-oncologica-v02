"""
Test suite to validate SagaOrchestrator refactoring.

This test verifies that:
1. Backward compatibility is maintained
2. All classes are importable from both old and new paths
3. No functionality was lost in the refactoring
"""

import sys
import pytest


def test_backward_compatibility_imports():
    """Test that old imports still work."""
    # Old import path (backward compatibility)
    from app.coordination.saga_orchestrator import (
        SagaOrchestrator,
        SagaState,
        SagaStep,
        SagaStatus,
        SagaStepStatus,
        FlowKind,
    )

    assert SagaOrchestrator is not None
    assert SagaState is not None
    assert SagaStep is not None
    assert SagaStatus is not None
    assert SagaStepStatus is not None
    assert FlowKind is not None


def test_new_modular_imports():
    """Test that new modular imports work."""
    # New modular import paths
    from app.coordination.saga import (
        SagaOrchestrator,
        SagaState,
        SagaStep,
        SagaStatus,
        SagaStepStatus,
        FlowKind,
    )

    assert SagaOrchestrator is not None
    assert SagaState is not None
    assert SagaStep is not None
    assert SagaStatus is not None
    assert SagaStepStatus is not None
    assert FlowKind is not None


def test_individual_module_imports():
    """Test that individual modules can be imported."""
    from app.coordination.saga.orchestrator import SagaOrchestrator as BaseOrchestrator
    from app.coordination.saga.persistence import SagaPersistenceManager
    from app.coordination.saga.retry_strategy import SagaRetryStrategy
    from app.coordination.saga.patient_onboarding import PatientOnboardingSaga

    assert BaseOrchestrator is not None
    assert SagaPersistenceManager is not None
    assert SagaRetryStrategy is not None
    assert PatientOnboardingSaga is not None


def test_orchestrator_has_all_methods():
    """Test that SagaOrchestrator has all required methods."""
    from app.coordination.saga import SagaOrchestrator

    # Generic orchestration methods
    assert hasattr(SagaOrchestrator, 'execute_saga')
    assert hasattr(SagaOrchestrator, '_execute_saga_internal')
    assert hasattr(SagaOrchestrator, '_execute_step')
    assert hasattr(SagaOrchestrator, '_compensate_step')

    # Patient onboarding methods
    assert hasattr(SagaOrchestrator, 'execute_patient_onboarding_saga')
    assert hasattr(SagaOrchestrator, 'execute_patient_onboarding')
    assert hasattr(SagaOrchestrator, 'resume_saga')
    assert hasattr(SagaOrchestrator, '_create_patient_action')
    assert hasattr(SagaOrchestrator, '_delete_patient_compensation')
    assert hasattr(SagaOrchestrator, '_create_flow_state_action')
    assert hasattr(SagaOrchestrator, '_delete_flow_state_compensation')
    assert hasattr(SagaOrchestrator, '_send_initial_message_action')
    assert hasattr(SagaOrchestrator, '_send_cancellation_message_compensation')

    # Retry strategy methods
    assert hasattr(SagaOrchestrator, 'handle_saga_failure')
    assert hasattr(SagaOrchestrator, 'schedule_retry')
    assert hasattr(SagaOrchestrator, 'handle_max_retries_exceeded')
    assert hasattr(SagaOrchestrator, 'alert_admin')


def test_enums_are_accessible():
    """Test that all enums are accessible."""
    from app.coordination.saga import SagaStatus, SagaStepStatus, FlowKind

    # SagaStatus values
    assert hasattr(SagaStatus, 'PENDING')
    assert hasattr(SagaStatus, 'RUNNING')
    assert hasattr(SagaStatus, 'COMPLETED')
    assert hasattr(SagaStatus, 'COMPENSATING')
    assert hasattr(SagaStatus, 'COMPENSATED')
    assert hasattr(SagaStatus, 'FAILED')

    # SagaStepStatus values
    assert hasattr(SagaStepStatus, 'PENDING')
    assert hasattr(SagaStepStatus, 'RUNNING')
    assert hasattr(SagaStepStatus, 'COMPLETED')
    assert hasattr(SagaStepStatus, 'FAILED')
    assert hasattr(SagaStepStatus, 'COMPENSATING')
    assert hasattr(SagaStepStatus, 'COMPENSATED')

    # FlowKind values
    assert hasattr(FlowKind, 'ONBOARDING')
    assert hasattr(FlowKind, 'MONTHLY_QUIZ')
    assert hasattr(FlowKind, 'DAYS_16_45')


def test_dataclasses_are_accessible():
    """Test that dataclasses are accessible."""
    from app.coordination.saga import SagaState, SagaStep

    # SagaStep fields
    assert hasattr(SagaStep, 'name')
    assert hasattr(SagaStep, 'action')
    assert hasattr(SagaStep, 'compensation')
    assert hasattr(SagaStep, 'status')
    assert hasattr(SagaStep, 'result')
    assert hasattr(SagaStep, 'error')
    assert hasattr(SagaStep, 'started_at')
    assert hasattr(SagaStep, 'completed_at')
    assert hasattr(SagaStep, 'retry_count')
    assert hasattr(SagaStep, 'max_retries')

    # SagaState fields
    assert hasattr(SagaState, 'saga_id')
    assert hasattr(SagaState, 'saga_type')
    assert hasattr(SagaState, 'status')
    assert hasattr(SagaState, 'steps')
    assert hasattr(SagaState, 'context')
    assert hasattr(SagaState, 'created_at')
    assert hasattr(SagaState, 'updated_at')
    assert hasattr(SagaState, 'completed_at')
    assert hasattr(SagaState, 'error')
    assert hasattr(SagaState, 'to_dict')


if __name__ == "__main__":
    print("Running SagaOrchestrator refactoring validation tests...")
    pytest.main([__file__, "-v"])
