"""
Timezone handling and optimal delivery time calculation.
"""

import logging
from datetime import datetime, timedelta
import pytz

from app.models.patient import Patient
from .models import SchedulingWindow, TimezoneError
from .config import MessageSchedulerConfig

logger = logging.getLogger(__name__)


class TimezoneHandler:
    """Handles timezone operations and delivery time calculations."""

    def __init__(self, config: MessageSchedulerConfig = None):
        self.config = config or MessageSchedulerConfig()
        self.scheduling_windows = self.config.SCHEDULING_WINDOWS

    def get_patient_timezone(self, patient: Patient) -> str:
        """
        Get patient timezone from metadata or default to Brazil timezone.

        Args:
            patient: Patient object

        Returns:
            Timezone string
        """
        patient_data = patient.patient_data or {}

        preferences = patient_data.get("preferences")
        if isinstance(preferences, dict) and preferences.get("timezone"):
            return preferences["timezone"]

        legacy_timezone = patient_data.get("timezone")
        if legacy_timezone:
            return legacy_timezone

        return self.config.DEFAULT_TIMEZONE

    async def calculate_optimal_delivery_time(
        self, patient: Patient, scheduling_window: SchedulingWindow
    ) -> datetime:
        """
        Calculate optimal delivery time based on patient timezone and scheduling window.

        Args:
            patient: Patient object
            scheduling_window: Preferred scheduling window

        Returns:
            Optimal delivery time in UTC
        """
        try:
            # Get patient timezone with validation
            patient_tz_str = self.get_patient_timezone(patient)

            try:
                patient_tz = pytz.timezone(patient_tz_str)
            except pytz.UnknownTimeZoneError:
                logger.warning(
                    f"Unknown timezone {patient_tz_str} for patient {patient.id}, using default"
                )
                patient_tz = pytz.timezone(self.config.DEFAULT_TIMEZONE)

            # Get current time in patient timezone
            utc_now = datetime.utcnow()
            patient_now = pytz.UTC.localize(utc_now).astimezone(patient_tz)

            # Validate scheduling window
            if scheduling_window not in self.scheduling_windows:
                logger.warning(
                    f"Invalid scheduling window {scheduling_window}, using BUSINESS_HOURS"
                )
                scheduling_window = SchedulingWindow.BUSINESS_HOURS

            # Get scheduling window times
            window_start, window_end = self.scheduling_windows[scheduling_window]

            # Check if current time is within window
            current_time = patient_now.time()

            if window_start <= current_time <= window_end:
                # Schedule for configured buffer time from now
                delivery_time_patient = patient_now + timedelta(
                    minutes=self.config.MIN_SCHEDULING_BUFFER_MINUTES
                )
            else:
                # Schedule for next occurrence of window start
                if current_time < window_start:
                    # Later today
                    delivery_date = patient_now.date()
                else:
                    # Tomorrow
                    delivery_date = patient_now.date() + timedelta(days=1)

                delivery_time_patient = patient_tz.localize(
                    datetime.combine(delivery_date, window_start)
                )

            # Convert back to UTC
            delivery_time_utc = delivery_time_patient.astimezone(pytz.UTC).replace(
                tzinfo=None
            )

            # Ensure delivery time is not in the past
            if delivery_time_utc <= datetime.utcnow():
                delivery_time_utc = datetime.utcnow() + timedelta(
                    minutes=self.config.FALLBACK_DELAY_MINUTES
                )
                logger.warning(
                    f"Calculated delivery time was in the past, adjusted to {self.config.FALLBACK_DELAY_MINUTES} minutes from now"
                )

            return delivery_time_utc

        except Exception as e:
            logger.error(
                f"Failed to calculate optimal delivery time for patient {patient.id}: {e}"
            )
            raise TimezoneError(f"Unable to calculate delivery time: {e}")
