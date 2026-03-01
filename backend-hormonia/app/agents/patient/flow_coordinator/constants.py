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


def compute_cycle_number(days_since_enrollment: int) -> tuple[int, int]:
    """Compute monthly cycle and day within cycle from enrollment day count.

    Returns:
        Tuple of (monthly_cycle, day_in_cycle).
        - Before monthly phase (days < 45): (0, days_since_enrollment)
        - Monthly phase (days >= 45): cycle/day within 30-day cycles
    """
    if days_since_enrollment < DAILY_FOLLOWUP_END_DAY:
        return 0, days_since_enrollment

    days_in_monthly_phase = days_since_enrollment - DAILY_FOLLOWUP_END_DAY
    monthly_cycle = (days_in_monthly_phase // MONTHLY_CYCLE_DAYS) + 1
    day_in_cycle = (days_in_monthly_phase % MONTHLY_CYCLE_DAYS) + 1
    return monthly_cycle, day_in_cycle


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
        _, cycle_day = compute_cycle_number(current_day)
        return "quiz_mensal", cycle_day


def normalize_flow_day(current_day: int) -> int:
    """Normalize day numbers to a minimum value of 1."""
    return current_day if current_day > 0 else 1
