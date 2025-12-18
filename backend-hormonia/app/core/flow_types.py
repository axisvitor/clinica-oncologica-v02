"""
Flow types and enumerations.
Moved here to avoid circular dependencies between services.
"""

from enum import Enum


class FlowType(Enum):
    """Flow type enumeration."""

    INITIAL_15_DAYS = "initial_15_days"
    DAYS_16_45 = "days_16_45"
    MONTHLY_RECURRING = "monthly_recurring"


class FlowState(Enum):
    """Flow state enumeration."""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
