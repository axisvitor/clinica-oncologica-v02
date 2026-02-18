"""
Timezone helpers for Sao Paulo (America/Sao_Paulo).
"""

from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

SAO_PAULO_TZ_NAME = "America/Sao_Paulo"
SAO_PAULO_TZ = ZoneInfo(SAO_PAULO_TZ_NAME)


def now_sao_paulo() -> datetime:
    return datetime.now(SAO_PAULO_TZ)


def now_sao_paulo_naive() -> datetime:
    return now_sao_paulo().replace(tzinfo=None)


def today_sao_paulo() -> date:
    return now_sao_paulo().date()


def to_sao_paulo(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=SAO_PAULO_TZ)
    return dt.astimezone(SAO_PAULO_TZ)


def normalize_datetime_naive_sao_paulo(
    dt: Optional[datetime],
) -> Optional[datetime]:
    """
    Normalize datetime values to Sao Paulo naive format.

    - None stays None
    - naive datetime stays unchanged
    - timezone-aware datetime is converted to Sao Paulo and made naive
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return to_sao_paulo(dt).replace(tzinfo=None)
