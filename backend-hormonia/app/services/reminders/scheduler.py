"""
Schedule resolution and duration handling for reminders.
"""

import calendar
from datetime import date, datetime, time, timedelta
from typing import Optional, Tuple

from pytz.exceptions import AmbiguousTimeError, NonExistentTimeError

from app.utils.timezone import SAO_PAULO_TZ_NAME

from .models import DurationInfo
from .patterns import SAO_PAULO_PYTZ_TZ


def parse_time_parts(time_local: str) -> Tuple[Optional[int], Optional[int]]:
    """Parse time string 'HH:MM' into hour and minute."""
    try:
        parts = time_local.split(":")
        if len(parts) != 2:
            return None, None
        return int(parts[0]), int(parts[1])
    except (TypeError, ValueError):
        return None, None


def add_months(base_date: date, months: int) -> date:
    """Add months to a date, handling month-end edge cases."""
    month = base_date.month - 1 + months
    year = base_date.year + month // 12
    month = month % 12 + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def resolve_schedule(
    time_local: str,
    date_local: Optional[str],
    weekday: Optional[int],
) -> Tuple[Optional[datetime], Optional[datetime], Optional[str]]:
    """
    Resolve schedule datetime from time, date, and weekday.

    Returns:
        Tuple of (local_dt, local_dt, timezone_name) or (None, None, None/tz_name)
    """
    if not time_local:
        return None, None, None

    tz_name = SAO_PAULO_TZ_NAME
    tz = SAO_PAULO_PYTZ_TZ

    now_local = datetime.now(tz)
    hour, minute = parse_time_parts(time_local)
    if hour is None or minute is None:
        return None, None, tz_name

    target_date = resolve_target_date(
        now_local=now_local,
        date_local=date_local,
        weekday=weekday,
        time_local=time(hour, minute),
    )
    if not target_date:
        return None, None, tz_name

    try:
        local_dt = tz.localize(
            datetime.combine(target_date, time(hour, minute)),
            is_dst=None,
        )
    except (AmbiguousTimeError, NonExistentTimeError):
        return None, None, tz_name

    return local_dt, local_dt, tz_name


def resolve_target_date(
    now_local: datetime,
    date_local: Optional[str],
    weekday: Optional[int],
    time_local: time,
) -> Optional[date]:
    """Resolve the target date from explicit date, weekday, or default to today/tomorrow."""
    if date_local:
        try:
            return datetime.fromisoformat(date_local).date()
        except ValueError:
            return None

    if weekday is not None and 0 <= weekday <= 6:
        return next_weekday(now_local.date(), weekday, time_local, now_local)

    target_date = now_local.date()
    if time_local <= now_local.time():
        target_date = target_date + timedelta(days=1)
    return target_date


def next_weekday(
    start_date: date,
    weekday: int,
    time_local: time,
    now_local: datetime,
) -> date:
    """Calculate the next occurrence of a given weekday."""
    days_ahead = (weekday - start_date.weekday()) % 7
    if days_ahead == 0 and time_local <= now_local.time():
        days_ahead = 7
    return start_date + timedelta(days=days_ahead)


def combine_local_date(local_dt: datetime, target_date: date) -> datetime:
    """Combine date with time, handling DST edge cases."""
    target_time = local_dt.time().replace(microsecond=0)
    try:
        local_target = SAO_PAULO_PYTZ_TZ.localize(
            datetime.combine(target_date, target_time),
            is_dst=None,
        )
    except AmbiguousTimeError:
        # DST transition: prefer standard time (is_dst=False)
        local_target = SAO_PAULO_PYTZ_TZ.localize(
            datetime.combine(target_date, target_time),
            is_dst=False,
        )
    except NonExistentTimeError:
        # DST gap: shift forward by 1 hour
        shifted_time = (datetime.combine(target_date, target_time) + timedelta(hours=1)).time()
        local_target = SAO_PAULO_PYTZ_TZ.localize(
            datetime.combine(target_date, shifted_time),
            is_dst=True,
        )
    return local_target


def resolve_duration_settings(
    local_dt: datetime, duration_info: DurationInfo
) -> Tuple[Optional[int], Optional[datetime]]:
    """
    Resolve duration settings into remaining count and end datetime.

    Returns:
        Tuple of (reminder_remaining, reminder_end_at)
    """
    reminder_remaining = None
    reminder_end_at = None

    if duration_info.occurrences:
        reminder_remaining = max(duration_info.occurrences - 1, 0)

    end_date = None
    if duration_info.end_date:
        try:
            end_date = datetime.fromisoformat(duration_info.end_date).date()
        except ValueError:
            end_date = None
    if end_date is None and duration_info.months:
        end_date = add_months(local_dt.date(), duration_info.months) - timedelta(days=1)
    if end_date is None and duration_info.weeks:
        end_date = local_dt.date() + timedelta(days=(duration_info.weeks * 7 - 1))
    if end_date is None and duration_info.days:
        end_date = local_dt.date() + timedelta(days=(duration_info.days - 1))

    if end_date:
        reminder_end_at = combine_local_date(local_dt, end_date)

    return reminder_remaining, reminder_end_at


def infer_recurrence_from_duration(duration_info: DurationInfo) -> str:
    """Infer recurrence type from duration info."""
    if duration_info.months:
        return "monthly"
    if duration_info.weeks:
        return "weekly"
    if duration_info.days or duration_info.occurrences:
        return "daily"
    return "none"


def duration_from_intent(intent) -> DurationInfo:
    """Extract DurationInfo from a ReminderIntent."""
    return DurationInfo(
        occurrences=intent.duration_occurrences,
        days=intent.duration_days,
        weeks=intent.duration_weeks,
        months=intent.duration_months,
        end_date=intent.duration_end_date,
    )


def duration_from_pending(pending: dict) -> DurationInfo:
    """Extract DurationInfo from pending reminder data."""
    def safe_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    return DurationInfo(
        occurrences=safe_int(pending.get("duration_occurrences")),
        days=safe_int(pending.get("duration_days")),
        weeks=safe_int(pending.get("duration_weeks")),
        months=safe_int(pending.get("duration_months")),
        end_date=pending.get("duration_end_date"),
    )


def merge_duration_info(primary: DurationInfo, fallback: DurationInfo) -> DurationInfo:
    """Merge two DurationInfo objects, preferring primary values."""
    return DurationInfo(
        occurrences=primary.occurrences or fallback.occurrences,
        days=primary.days or fallback.days,
        weeks=primary.weeks or fallback.weeks,
        months=primary.months or fallback.months,
        end_date=primary.end_date or fallback.end_date,
    )
