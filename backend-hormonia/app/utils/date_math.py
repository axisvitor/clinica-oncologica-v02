"""Shared date arithmetic helpers."""

from __future__ import annotations

import calendar
from datetime import date


def add_months(base_date: date, months: int) -> date:
    """Add months to a date while clamping day to target month length."""
    month = base_date.month - 1 + months
    year = base_date.year + month // 12
    month = month % 12 + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)
