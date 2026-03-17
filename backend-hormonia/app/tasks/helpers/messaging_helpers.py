"""Messaging helpers extracted from app.tasks.messaging."""

import logging
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

import pytz
from pytz.exceptions import AmbiguousTimeError, NonExistentTimeError

from app.models.message import (
    Message,
    MessageDirection,
    MessageStatus,
    MessageType,
)
from app.utils.date_math import add_months
from app.utils.idempotency import build_message_idempotency_key
from app.utils.timezone import SAO_PAULO_TZ, SAO_PAULO_TZ_NAME, now_sao_paulo

logger = logging.getLogger(__name__)


def _build_idempotency_key(
    patient_id: UUID,
    content: str,
    scheduled_for: datetime,
    message_type: MessageType,
) -> str:
    return build_message_idempotency_key(
        patient_id=patient_id,
        content=content,
        scheduled_for=scheduled_for,
        message_type_value=message_type.value,
    )


def _parse_time_str(time_str: Optional[str]) -> Optional[Tuple[int, int]]:
    if not time_str:
        return None
    try:
        hour_str, minute_str = time_str.split(":")
        hour = int(hour_str)
        minute = int(minute_str)
    except (ValueError, AttributeError):
        return None
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour, minute
    return None


def _add_months(base_date: date, months: int) -> date:
    return add_months(base_date, months)


def _compute_next_reminder_time(
    metadata: Dict[str, Any],
    current_scheduled_for: Optional[datetime],
) -> Optional[Tuple[datetime, date]]:
    recurrence = (metadata or {}).get("reminder_recurrence")
    if recurrence not in {"daily", "weekly", "monthly", "interval"}:
        return None

    tz_name = metadata.get("reminder_timezone") or SAO_PAULO_TZ_NAME
    try:
        tz = pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        tz = pytz.timezone(SAO_PAULO_TZ_NAME)
        tz_name = SAO_PAULO_TZ_NAME

    base_dt = current_scheduled_for or now_sao_paulo()
    if base_dt.tzinfo is None:
        try:
            base_dt = tz.localize(base_dt, is_dst=None)
        except AmbiguousTimeError:
            base_dt = tz.localize(base_dt, is_dst=False)
        except NonExistentTimeError:
            base_dt = tz.localize(base_dt + timedelta(hours=1), is_dst=True)
    base_local = base_dt.astimezone(tz)

    time_local_str = metadata.get("reminder_time_local")
    parsed_time = _parse_time_str(time_local_str)
    if parsed_time:
        base_time = time(parsed_time[0], parsed_time[1])
    else:
        base_time = base_local.time().replace(microsecond=0)

    date_local_str = metadata.get("reminder_date_local")
    try:
        base_date = datetime.fromisoformat(date_local_str).date()
    except (TypeError, ValueError):
        base_date = base_local.date()

    if recurrence == "daily":
        next_date = base_date + timedelta(days=1)
    elif recurrence == "weekly":
        weekday = metadata.get("reminder_weekday")
        if weekday is not None:
            try:
                weekday = int(weekday)
            except (TypeError, ValueError):
                weekday = None
        if isinstance(weekday, int) and 0 <= weekday <= 6:
            days_ahead = (weekday - base_date.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            next_date = base_date + timedelta(days=days_ahead)
        else:
            next_date = base_date + timedelta(days=7)
    elif recurrence == "monthly":
        next_date = _add_months(base_date, 1)
    else:
        interval_days = metadata.get("reminder_interval_days")
        try:
            interval_days = int(interval_days)
        except (TypeError, ValueError):
            return None
        if interval_days <= 0:
            return None
        next_date = base_date + timedelta(days=interval_days)

    try:
        next_local = tz.localize(datetime.combine(next_date, base_time), is_dst=None)
    except AmbiguousTimeError:
        next_local = tz.localize(datetime.combine(next_date, base_time), is_dst=False)
    except NonExistentTimeError:
        shifted = datetime.combine(next_date, base_time) + timedelta(hours=1)
        next_local = tz.localize(shifted, is_dst=True)
    return next_local.astimezone(SAO_PAULO_TZ), next_date


async def _schedule_next_reminder(message, db) -> bool:
    metadata = message.message_metadata or {}
    recurrence = metadata.get("reminder_recurrence")
    if not recurrence or recurrence == "none":
        return False

    next_info = _compute_next_reminder_time(metadata, message.scheduled_for)
    if not next_info:
        return False

    next_utc, next_date = next_info
    end_at = metadata.get("reminder_end_at")
    if end_at:
        try:
            end_dt = datetime.fromisoformat(end_at)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=SAO_PAULO_TZ)
            if next_utc > end_dt:
                return False
        except ValueError:
            pass

    remaining = metadata.get("reminder_remaining")
    if remaining is not None:
        try:
            remaining = int(remaining)
        except (TypeError, ValueError):
            remaining = None
        if remaining is not None:
            if remaining <= 0:
                return False
            remaining -= 1

    new_metadata = dict(metadata)
    try:
        sequence = int(metadata.get("reminder_sequence", 1))
    except (TypeError, ValueError):
        sequence = 1
    new_metadata["reminder_sequence"] = sequence + 1
    new_metadata["reminder_date_local"] = next_date.isoformat()
    if remaining is not None:
        new_metadata["reminder_remaining"] = remaining

    new_message = Message(
        patient_id=message.patient_id,
        direction=MessageDirection.OUTBOUND,
        type=MessageType(message.type),
        content=message.content,
        status=MessageStatus.PENDING,
        scheduled_for=next_utc,
        message_metadata=new_metadata,
    )
    db.add(new_message)
    db.flush()

    logger.info(
        "Scheduled next reminder",
        extra={
            "patient_id": str(message.patient_id),
            "recurrence": recurrence,
            "next_utc": next_utc.isoformat(),
            "sequence": new_metadata["reminder_sequence"],
        },
    )
    return True
