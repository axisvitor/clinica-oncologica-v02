"""
Shared enumerations for database models.

This module consolidates enum definitions that are used across multiple models
to avoid duplication and ensure consistency.

Usage:
    from app.models.enums import FlowState, SagaStatus
"""

import enum


class FlowState(enum.Enum):
    """
    Patient flow state enumeration.

    Represents the lifecycle state of a patient in the treatment flow:
    - ONBOARDING: Initial registration and setup
    - ACTIVE: Actively receiving treatment
    - PAUSED: Treatment temporarily suspended
    - COMPLETED: Treatment successfully finished
    - CANCELLED: Treatment cancelled or archived

    Used in: Patient model, Flow model
    Database type: PostgreSQL ENUM 'flow_state'
    """
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SagaStatus(enum.Enum):
    """
    Saga execution status enumeration.

    Represents the state of a distributed transaction (saga):
    - STARTED: Saga initiated
    - IN_PROGRESS: Saga executing steps
    - STEP_1_PATIENT_CREATED: Patient record created
    - STEP_2_FIREBASE_USER_CREATED: (Deprecated) Firebase user created
    - STEP_3_FLOW_INITIALIZED: Flow state initialized
    - STEP_4_MESSAGE_SENT: Welcome message sent
    - COMPLETED: All steps successful
    - FAILED: Saga failed
    - COMPENSATING: Running compensation
    - COMPENSATED: Compensation complete
    - RETRY_SCHEDULED: Retry pending

    Used in: PatientOnboardingSaga model
    """
    STARTED = "STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    STEP_1_PATIENT_CREATED = "STEP_1_PATIENT_CREATED"
    STEP_2_FIREBASE_USER_CREATED = "STEP_2_FIREBASE_USER_CREATED"  # Deprecated, kept for DB compatibility
    STEP_3_FLOW_INITIALIZED = "STEP_3_FLOW_INITIALIZED"
    STEP_4_MESSAGE_SENT = "STEP_4_MESSAGE_SENT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"


# Backward compatibility exports
__all__ = [
    "FlowState",
    "SagaStatus",
]
