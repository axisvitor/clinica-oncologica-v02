"""
Date calculation utilities for treatment day calculations and flow management.
Provides centralized date calculation functions to eliminate code duplication.
"""

import logging
from typing import Optional, Union, Tuple
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from app.config.template_loader import get_template_loader

logger = logging.getLogger(__name__)


def _calculate_treatment_day(
    treatment_start_date: Union[date, datetime, str, None],
    reference_date: Optional[Union[date, datetime, str]] = None,
    timezone: str = "America/Sao_Paulo",
) -> int:
    """
    Calculate the current treatment day based on treatment start date.

    This function provides centralized date calculation logic that was previously
    duplicated across multiple services.

    Args:
        treatment_start_date: The date treatment started (date, datetime, ISO string, or None)
        reference_date: Date to calculate from (defaults to today)
        timezone: Timezone for calculations (defaults to America/Sao_Paulo)

    Returns:
        Treatment day number (1-based), or 0 if treatment hasn't started or invalid data

    Examples:
        >>> from datetime import date
        >>> _calculate_treatment_day(date(2024, 1, 1), date(2024, 1, 1))
        1
        >>> _calculate_treatment_day(date(2024, 1, 1), date(2024, 1, 5))
        5
        >>> _calculate_treatment_day("2024-01-01", "2024-01-10")
        10
    """
    try:
        # Handle None or empty treatment start date
        if not treatment_start_date:
            logger.debug("No treatment start date provided")
            return 0

        # Convert treatment start date to date object
        start_date = _parse_date(treatment_start_date)
        if not start_date:
            logger.warning(f"Invalid treatment start date: {treatment_start_date}")
            return 0

        # Get reference date (default to today in specified timezone)
        if reference_date:
            ref_date = _parse_date(reference_date)
            if not ref_date:
                logger.warning(f"Invalid reference date: {reference_date}")
                ref_date = _get_today_in_timezone(timezone)
        else:
            ref_date = _get_today_in_timezone(timezone)

        # Calculate difference in days
        day_difference = (ref_date - start_date).days

        # Treatment day is 1-based (day 1 is the start date)
        treatment_day = day_difference + 1

        # Ensure treatment day is at least 1 (can't be in the future)
        if treatment_day < 1:
            logger.debug(
                f"Treatment start date {start_date} is in the future relative to {ref_date}"
            )
            return 0

        logger.debug(
            f"Calculated treatment day {treatment_day} (start: {start_date}, reference: {ref_date})"
        )
        return treatment_day

    except Exception as e:
        logger.error(f"Error calculating treatment day: {e}")
        return 0


def _parse_date(date_input: Union[date, datetime, str]) -> Optional[date]:
    """
    Parse various date input formats into a date object.

    Args:
        date_input: Date in various formats (date, datetime, ISO string)

    Returns:
        date object or None if parsing fails
    """
    if isinstance(date_input, date):
        return date_input

    if isinstance(date_input, datetime):
        return date_input.date()

    if isinstance(date_input, str):
        try:
            # Try parsing ISO format
            if "T" in date_input:
                # Full datetime string
                parsed_datetime = datetime.fromisoformat(
                    date_input.replace("Z", "+00:00")
                )
                return parsed_datetime.date()
            else:
                # Date-only string
                parsed_date = datetime.strptime(date_input, "%Y-%m-%d").date()
                return parsed_date
        except ValueError:
            try:
                # Try other common formats
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                    try:
                        return datetime.strptime(date_input, fmt).date()
                    except ValueError:
                        continue
            except Exception as e:
                logger.warning(
                    f"Failed to parse date with alternative formats: {e}", exc_info=True
                )

    return None


def _get_today_in_timezone(timezone: str = "America/Sao_Paulo") -> date:
    """
    Get today's date in the specified timezone.

    Args:
        timezone: Timezone name (defaults to America/Sao_Paulo)

    Returns:
        Today's date in the specified timezone
    """
    try:
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)
        return now.date()
    except Exception as e:
        logger.warning(
            f"Error getting date in timezone {timezone}: {e}, falling back to UTC"
        )
        return datetime.utcnow().date()


def calculate_flow_type_from_day(treatment_day: int) -> str:
    """
    Determine the appropriate flow type based on treatment day.

    Args:
        treatment_day: Current treatment day

    Returns:
        Flow type identifier (day_1_15, day_16_45, or monthly)
    """
    if treatment_day <= 0:
        return "day_1_15"  # Default to initial flow

    if treatment_day <= 15:
        return "day_1_15"
    elif treatment_day <= 45:
        return "day_16_45"
    else:
        return "monthly"


def get_treatment_phase_info(
    treatment_start_date: Union[date, datetime, str, None],
    reference_date: Optional[Union[date, datetime, str]] = None,
) -> Tuple[int, str]:
    """
    Get comprehensive treatment phase information.

    Args:
        treatment_start_date: The date treatment started
        reference_date: Date to calculate from (defaults to today)

    Returns:
        Tuple of (treatment_day, flow_type)
    """
    treatment_day = _calculate_treatment_day(treatment_start_date, reference_date)
    flow_type = calculate_flow_type_from_day(treatment_day)
    return treatment_day, flow_type


def is_business_day(
    check_date: Union[date, datetime, str, None] = None,
    timezone: str = "America/Sao_Paulo",
) -> bool:
    """
    Check if a given date is a business day (Monday-Friday).

    Args:
        check_date: Date to check (defaults to today)
        timezone: Timezone for calculation

    Returns:
        True if business day, False if weekend
    """
    if check_date is None:
        check_date = _get_today_in_timezone(timezone)
    else:
        check_date = _parse_date(check_date)

    if not check_date:
        return False

    # Monday = 0, Sunday = 6
    return check_date.weekday() < 5


def get_next_business_day(
    from_date: Union[date, datetime, str, None] = None,
    timezone: str = "America/Sao_Paulo",
) -> date:
    """
    Get the next business day from a given date.

    Args:
        from_date: Starting date (defaults to today)
        timezone: Timezone for calculation

    Returns:
        Next business day
    """
    if from_date is None:
        current_date = _get_today_in_timezone(timezone)
    else:
        current_date = _parse_date(from_date)

    if not current_date:
        current_date = _get_today_in_timezone(timezone)

    # Find next business day
    next_date = current_date + timedelta(days=1)
    while not is_business_day(next_date, timezone):
        next_date += timedelta(days=1)

    return next_date


def calculate_days_until_next_phase(
    treatment_start_date: Union[date, datetime, str, None],
    reference_date: Optional[Union[date, datetime, str]] = None,
) -> Optional[int]:
    """
    Calculate how many days until the next treatment phase.

    Args:
        treatment_start_date: The date treatment started
        reference_date: Date to calculate from (defaults to today)

    Returns:
        Days until next phase, or None if already in final phase
    """
    treatment_day = _calculate_treatment_day(treatment_start_date, reference_date)

    if treatment_day <= 15:
        # In day_1_15 phase, next phase starts at day 16
        return 16 - treatment_day
    elif treatment_day <= 45:
        # In day_16_45 phase, next phase starts at day 46
        return 46 - treatment_day
    else:
        # Already in monthly phase (final phase)
        return None


def format_treatment_day_info(
    treatment_start_date: Union[date, datetime, str, None],
    reference_date: Optional[Union[date, datetime, str]] = None,
    include_phase: bool = True,
) -> str:
    """
    Format treatment day information as a human-readable string.

    Args:
        treatment_start_date: The date treatment started
        reference_date: Date to calculate from (defaults to today)
        include_phase: Whether to include phase information

    Returns:
        Formatted string with treatment day information
    """
    treatment_day, flow_type = get_treatment_phase_info(
        treatment_start_date, reference_date
    )

    if treatment_day <= 0:
        return "Tratamento não iniciado"

    base_info = f"Dia {treatment_day} do tratamento"

    if include_phase:
        phase_names = {
            "day_1_15": "Fase Inicial",
            "day_16_45": "Fase de Manutenção",
            "monthly": "Acompanhamento Mensal",
        }
        phase_name = phase_names.get(flow_type, "Fase Desconhecida")
        return f"{base_info} ({phase_name})"

    return base_info


def is_within_business_hours(
    check_time: Optional[datetime] = None,
    timezone: str = "America/Sao_Paulo",
    start_hour: int = 9,
    end_hour: int = 18,
) -> bool:
    """
    Check if a given time is within business hours.

    Args:
        check_time: Time to check (defaults to now)
        timezone: Timezone for calculation
        start_hour: Business hours start (24-hour format)
        end_hour: Business hours end (24-hour format)

    Returns:
        True if within business hours, False otherwise
    """
    if check_time is None:
        try:
            tz = ZoneInfo(timezone)
            check_time = datetime.now(tz)
        except Exception:
            check_time = datetime.utcnow()

    # Check if it's a business day
    if not is_business_day(check_time.date(), timezone):
        return False

    # Check if within business hours
    hour = check_time.hour
    return start_hour <= hour < end_hour


def get_next_scheduled_time(
    flow_type: str,
    from_time: Optional[datetime] = None,
    timezone: str = "America/Sao_Paulo",
) -> datetime:
    """
    Calculate the next scheduled time for a flow type based on its configuration.

    Args:
        flow_type: Flow type identifier
        from_time: Starting time (defaults to now)
        timezone: Timezone for calculation

    Returns:
        Next scheduled datetime
    """
    try:
        # Get flow configuration
        loader = get_template_loader()
        config = loader.get_flow_type_config(flow_type)

        if not config:
            # Fallback to next business day at 9 AM
            return _get_default_next_time(from_time, timezone)

        # Get timing configuration
        timing = config.timing
        start_hour = timing.get("start_hour", 9)
        end_hour = timing.get("end_hour", 18)

        if from_time is None:
            try:
                tz = ZoneInfo(timezone)
                from_time = datetime.now(tz)
            except Exception:
                from_time = datetime.utcnow()

        # Calculate based on frequency
        frequency = config.frequency
        if frequency == "daily":
            return _get_next_daily_time(from_time, start_hour, end_hour, timezone)
        elif frequency == "every_2_days":
            return _get_next_interval_time(from_time, 2, start_hour, end_hour, timezone)
        elif frequency == "monthly":
            return _get_next_monthly_time(from_time, start_hour, timezone)
        else:
            return _get_default_next_time(from_time, timezone)

    except Exception as e:
        logger.error(f"Error calculating next scheduled time for {flow_type}: {e}")
        return _get_default_next_time(from_time, timezone)


def _get_next_daily_time(
    from_time: datetime, start_hour: int, end_hour: int, timezone: str
) -> datetime:
    """Get next daily scheduled time."""
    # If current time is before business hours today, schedule for today
    if from_time.hour < start_hour and is_business_day(from_time.date(), timezone):
        return from_time.replace(hour=start_hour, minute=0, second=0, microsecond=0)

    # Otherwise, schedule for next business day
    next_business = get_next_business_day(from_time.date(), timezone)
    try:
        tz = ZoneInfo(timezone)
        return datetime.combine(
            next_business, datetime.min.time().replace(hour=start_hour)
        ).replace(tzinfo=tz)
    except Exception:
        return datetime.combine(
            next_business, datetime.min.time().replace(hour=start_hour)
        )


def _get_next_interval_time(
    from_time: datetime,
    interval_days: int,
    start_hour: int,
    end_hour: int,
    timezone: str,
) -> datetime:
    """Get next scheduled time for interval-based flows."""
    target_date = from_time.date() + timedelta(days=interval_days)

    # Ensure it's a business day
    while not is_business_day(target_date, timezone):
        target_date += timedelta(days=1)

    try:
        tz = ZoneInfo(timezone)
        return datetime.combine(
            target_date, datetime.min.time().replace(hour=start_hour)
        ).replace(tzinfo=tz)
    except Exception:
        return datetime.combine(
            target_date, datetime.min.time().replace(hour=start_hour)
        )


def _get_next_monthly_time(
    from_time: datetime, start_hour: int, timezone: str
) -> datetime:
    """Get next monthly scheduled time."""
    # Schedule for same day next month
    try:
        if from_time.month == 12:
            target_date = from_time.replace(year=from_time.year + 1, month=1)
        else:
            target_date = from_time.replace(month=from_time.month + 1)
    except ValueError:
        # Handle edge cases like Jan 31 -> Feb
        if from_time.month == 12:
            target_date = from_time.replace(year=from_time.year + 1, month=2, day=28)
        else:
            target_date = from_time.replace(month=from_time.month + 1, day=28)

    # Ensure it's a business day
    target_date = target_date.date()
    while not is_business_day(target_date, timezone):
        target_date += timedelta(days=1)

    try:
        tz = ZoneInfo(timezone)
        return datetime.combine(
            target_date, datetime.min.time().replace(hour=start_hour)
        ).replace(tzinfo=tz)
    except Exception:
        return datetime.combine(
            target_date, datetime.min.time().replace(hour=start_hour)
        )


def _get_default_next_time(from_time: Optional[datetime], timezone: str) -> datetime:
    """Get default next scheduled time (next business day at 9 AM)."""
    if from_time is None:
        from_time = datetime.now()

    next_business = get_next_business_day(from_time.date(), timezone)
    try:
        tz = ZoneInfo(timezone)
        return datetime.combine(
            next_business, datetime.min.time().replace(hour=9)
        ).replace(tzinfo=tz)
    except Exception:
        return datetime.combine(next_business, datetime.min.time().replace(hour=9))
