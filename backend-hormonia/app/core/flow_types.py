"""
Flow types and enumerations for treatment phase tracking.

NOTE: This module defines TREATMENT PHASES (time-based progression), not to be confused
with app.services.flow.types.FlowType which defines FLOW ACTIVITY TYPES (onboarding, daily_checkin, etc.).

Treatment Phases:
- INITIAL_15_DAYS: First 15 days of treatment (intensive monitoring)
- DAYS_16_45: Days 16-45 (transition phase)
- MONTHLY_RECURRING: After day 45 (ongoing monthly monitoring)

For flow activity types (onboarding, daily_checkin, etc.), see: app.services.flow.types.FlowType

Moved here to avoid circular dependencies between services.
"""

from enum import Enum


class FlowType(Enum):
    """
    Treatment phase enumeration for time-based progression tracking.

    IMPORTANT: This enum represents TREATMENT PHASES, not flow activity types.
    For flow activity types, use app.services.flow.types.FlowType instead.

    Treatment phases define the time-based progression of patient care:
    - INITIAL_15_DAYS: First 15 days (intensive monitoring period)
    - DAYS_16_45: Days 16-45 (transition and adjustment phase)
    - MONTHLY_RECURRING: After day 45 (ongoing monthly monitoring)

    These phases determine:
    - Message frequency
    - Quiz scheduling
    - Monitoring intensity
    """

    INITIAL_15_DAYS = "initial_15_days"
    DAYS_16_45 = "days_16_45"
    MONTHLY_RECURRING = "monthly_recurring"


# Alias for clarity - these are treatment phases, not flow types
TreatmentPhase = FlowType


class FlowState(Enum):
    """
    Flow state enumeration for tracking flow execution status.

    States:
    - ACTIVE: Flow is currently executing
    - PAUSED: Flow execution is paused
    - COMPLETED: Flow completed successfully
    - ERROR: Flow encountered an error
    """

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
