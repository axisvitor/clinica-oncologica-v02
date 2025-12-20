"""
Follow-Up Scheduling Module - Follow-Up Message Scheduling

Handles follow-up message scheduling logic.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from app.utils.date_helpers import get_next_scheduled_time, is_business_day


logger = logging.getLogger(__name__)


class FollowUpScheduler:
    """
    Manages follow-up message scheduling.

    Responsibilities:
    - Calculate follow-up times
    - Schedule reminder messages
    - Manage recurring follow-ups
    - Handle business day logic
    """

    def __init__(self):
        """Initialize FollowUpScheduler."""
        logger.info("FollowUpScheduler initialized")

    def calculate_next_follow_up(
        self, base_time: datetime, frequency: str, timezone: str = "America/Sao_Paulo"
    ) -> datetime:
        """
        Calculate next follow-up time.

        Args:
            base_time: Base time to calculate from
            frequency: Follow-up frequency (daily, weekly, monthly)
            timezone: Timezone for calculation

        Returns:
            Next follow-up datetime
        """
        try:
            next_time = get_next_scheduled_time(frequency, base_time, timezone)

            # Ensure it's a business day
            while not is_business_day(next_time):
                next_time += timedelta(days=1)

            logger.debug(f"Next follow-up calculated: {next_time} ({frequency})")
            return next_time

        except Exception as e:
            logger.error(f"Error calculating next follow-up: {e}")
            # Default to tomorrow
            return datetime.now(timezone.utc) + timedelta(days=1)

    def should_send_follow_up(
        self, last_message_time: Optional[datetime], follow_up_interval_hours: int = 24
    ) -> bool:
        """
        Determine if follow-up should be sent.

        Args:
            last_message_time: Time of last message
            follow_up_interval_hours: Minimum hours between follow-ups

        Returns:
            True if follow-up should be sent
        """
        if not last_message_time:
            return True

        time_since_last = datetime.now(timezone.utc) - last_message_time
        hours_since_last = time_since_last.total_seconds() / 3600

        should_send = hours_since_last >= follow_up_interval_hours

        logger.debug(
            f"Follow-up check: {hours_since_last:.1f}h since last message, "
            f"threshold: {follow_up_interval_hours}h, should_send: {should_send}"
        )

        return should_send

    def schedule_reminder_sequence(
        self,
        base_time: datetime,
        reminder_intervals: list[int],
        timezone: str = "America/Sao_Paulo",
    ) -> list[datetime]:
        """
        Schedule a sequence of reminder messages.

        Args:
            base_time: Base time to start from
            reminder_intervals: List of intervals in hours
            timezone: Timezone for scheduling

        Returns:
            List of scheduled times
        """
        scheduled_times = []

        for interval_hours in reminder_intervals:
            reminder_time = base_time + timedelta(hours=interval_hours)

            # Adjust to business day if needed
            while not is_business_day(reminder_time):
                reminder_time += timedelta(days=1)

            scheduled_times.append(reminder_time)

        logger.info(
            f"Scheduled {len(scheduled_times)} reminders starting from {base_time}"
        )
        return scheduled_times
