"""
Birth date validation helpers shared across schema versions.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional


def validate_birth_date_min_age(value: Optional[date]) -> Optional[date]:
    """Validate birth date for future/age constraints (18-120 years)."""
    if value is None:
        return value

    today = date.today()

    if value > today:
        raise ValueError(f"Birth date {value.isoformat()} cannot be in the future.")

    min_date = today - timedelta(days=int(18 * 365.25))
    if value > min_date:
        age_years = (today - value).days / 365.25
        raise ValueError(
            f"Patient must be at least 18 years old. "
            f"Birth date {value.isoformat()} indicates age of {age_years:.1f} years."
        )

    max_date = today - timedelta(days=int(120 * 365.25))
    if value < max_date:
        age_years = (today - value).days / 365.25
        raise ValueError(
            f"Birth date {value.isoformat()} seems invalid "
            f"(indicates age of {age_years:.1f} years, over 120 years old)."
        )

    return value
