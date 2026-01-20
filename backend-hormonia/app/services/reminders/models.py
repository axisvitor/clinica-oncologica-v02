"""
Data models for the reminder system.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class DurationInfo:
    """Duration specification for recurring reminders."""

    occurrences: Optional[int] = None
    days: Optional[int] = None
    weeks: Optional[int] = None
    months: Optional[int] = None
    end_date: Optional[str] = None

    def has_value(self) -> bool:
        """Check if any duration value is set."""
        return any(
            value is not None
            for value in (
                self.occurrences,
                self.days,
                self.weeks,
                self.months,
                self.end_date,
            )
        )


@dataclass
class ReminderIntent:
    """Extracted reminder intent from patient message."""

    is_request: bool
    declined: bool
    reminder_text: Optional[str]
    time_local: Optional[str]
    date_local: Optional[str]
    recurrence: str
    interval_days: Optional[int]
    weekday: Optional[int]
    duration_occurrences: Optional[int]
    duration_days: Optional[int]
    duration_weeks: Optional[int]
    duration_months: Optional[int]
    duration_end_date: Optional[str]
    confidence: float
    needs_clarification: bool
    source: str


@dataclass
class ReminderHandlingResult:
    """Result of processing a reminder request."""

    action: str
    follow_up_message: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    reminder_id: Optional[str] = None
    commit_needed: bool = False
