"""
Saga Orchestrator Package.

This package provides a modular implementation of the saga orchestrator
for patient onboarding, split into focused, maintainable components.

Components:
    - orchestrator: Main SagaOrchestrator class
    - metrics: Prometheus counters/histograms and phone-format helper
    - steps: Individual saga step implementations
    - compensation: Rollback/compensation logic
    - compensation_handlers: Standalone compensation step handlers
    - persistence: Database operations
    - exceptions: Custom exception types
    - types: Type definitions and data structures

Usage:
    >>> from app.orchestration.saga_orchestrator import SagaOrchestrator
    >>> from app.orchestration.saga_orchestrator import SagaCompensationError
    >>>
    >>> orchestrator = SagaOrchestrator(db, redis_client)
    >>> patient = await orchestrator.execute_patient_onboarding_saga(
    ...     patient_data=patient_data,
    ...     doctor_id=doctor_id,
    ... )

Architecture:
    app/orchestration/saga_orchestrator/
    ├── __init__.py          # Public API (this file)
    ├── orchestrator.py      # Main orchestrator class
    ├── metrics.py           # Prometheus metrics and helpers
    ├── steps.py             # Step implementations
    ├── compensation.py      # Compensation logic
    ├── compensation_handlers.py  # Compensation step handlers
    ├── persistence.py       # Database operations
    ├── exceptions.py        # Custom exceptions
    └── types.py             # Type definitions
"""

# Main orchestrator class
from .orchestrator import SagaOrchestrator

# Step executor
from .steps import SagaStepExecutor

# Compensation handler
from .compensation import SagaCompensator

# Persistence layer
from .persistence import SagaPersistence

# Exception types
from .exceptions import (
    SagaError,
    SagaCompensationError,
    SagaStepError,
    SagaLockError,
    SagaNotFoundError,
    SagaAlreadyCompletedError,
)

# Type definitions
from .types import (
    SagaLogEntry,
    SagaStatusInfo,
    FailedSagaSummary,
    CompensationResult,
    ResumeResult,
)

__all__ = [
    # Main class
    "SagaOrchestrator",
    # Components
    "SagaStepExecutor",
    "SagaCompensator",
    "SagaPersistence",
    # Exceptions
    "SagaError",
    "SagaCompensationError",
    "SagaStepError",
    "SagaLockError",
    "SagaNotFoundError",
    "SagaAlreadyCompletedError",
    # Types
    "SagaLogEntry",
    "SagaStatusInfo",
    "FailedSagaSummary",
    "CompensationResult",
    "ResumeResult",
]

__version__ = "2.0.0"
__author__ = "Clinica Oncologica Development Team"
