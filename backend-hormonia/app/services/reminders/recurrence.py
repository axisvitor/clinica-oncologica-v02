"""
Shared recurrence helpers for reminder extraction/scheduling.
"""

from __future__ import annotations

from .models import DurationInfo


def infer_recurrence_from_duration(duration_info: DurationInfo) -> str:
    """Infer recurrence type from duration info."""
    if duration_info.months:
        return "monthly"
    if duration_info.weeks:
        return "weekly"
    if duration_info.days or duration_info.occurrences:
        return "daily"
    return "none"

