"""
Shared date helpers for analytics domain services.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from app.utils.timezone import now_sao_paulo


def build_date_window(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    """
    Build inclusive date window [start, end+1day) in Sao Paulo timezone.
    """
    tz = now_sao_paulo().tzinfo
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=tz)
    end_dt_exclusive = datetime.combine(
        end_date + timedelta(days=1), datetime.min.time(), tzinfo=tz
    )
    return start_dt, end_dt_exclusive

