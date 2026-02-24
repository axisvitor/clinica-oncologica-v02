# DDD service agent - no LLM calls, not a pydantic-ai migration target.
"""Centralized flow phase constants for treatment timeline.

These constants define the treatment phase boundaries used across
the patient flow coordination system.
"""

# Treatment phase day boundaries
ONBOARDING_END_DAY = 15
DAILY_FOLLOWUP_END_DAY = 45
MONTHLY_CYCLE_START_DAY = 46
MONTHLY_CYCLE_DAYS = 30

# Daily flow default hours
DEFAULT_DAILY_FLOW_HOURS = [8, 14, 20]
DEFAULT_QUIZ_TRIGGER_DAY = 30

# Canonical list of flow types used for template loading
FLOW_TYPES = ["onboarding", "daily_follow_up", "quiz_mensal"]


def resolve_flow_type_and_day(current_day: int) -> tuple:
    """Resolve flow type and relative day from absolute treatment day.

    Returns:
        Tuple of (flow_type: str, relative_day: int)
    """
    if current_day <= ONBOARDING_END_DAY:
        return "onboarding", current_day
    elif current_day <= DAILY_FOLLOWUP_END_DAY:
        return "daily_follow_up", current_day
    else:
        cycle_day = ((current_day - MONTHLY_CYCLE_START_DAY) % MONTHLY_CYCLE_DAYS) + 1
        return "quiz_mensal", cycle_day


def normalize_flow_day(current_day: int) -> int:
    """Normalize day numbers to a minimum value of 1."""
    return current_day if current_day > 0 else 1
