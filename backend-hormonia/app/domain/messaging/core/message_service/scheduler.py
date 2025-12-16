"""
Message Scheduler - Time-based Message Scheduling (QW-022).

This module handles scheduling messages based on patient timezone
preferences and appropriate sending windows.
Consolidated from: app/services/message_scheduler.py
"""

from typing import List, Optional, Any, Dict, Tuple
from uuid import UUID
from datetime import datetime, timedelta, time
import logging
import pytz

from sqlalchemy.orm import Session

from app.models.message import Message, MessageType, MessageStatus
from app.models.patient import Patient
from app.repositories.message import MessageRepository
from app.repositories.patient import PatientRepository
from app.exceptions import NotFoundError

from .config import SchedulingWindow, MessageSchedulerConfig
from .service import MessageService


logger = logging.getLogger(__name__)


class MessageScheduler:
    """
    Service for scheduling and managing time-based message delivery.
    Handles patient timezone preferences and appropriate sending hours.

    Consolidated from: app/services/message_scheduler.py
    """

    def __init__(self, db: Session, config: Optional[MessageSchedulerConfig] = None):
        """
        Initialize MessageScheduler.

        Args:
            db: Database session
            config: Optional configuration
        """
        self.db = db
        self.config = config or MessageSchedulerConfig()

        if db:
            self.patient_repo = PatientRepository(db)
            self.message_repo = MessageRepository(db)
            self.message_service = MessageService(db)

        # Use configuration for scheduling windows
        self.scheduling_windows = self.config.SCHEDULING_WINDOWS

    def _get_patient_timezone(self, patient: Patient) -> str:
        """
        Get patient timezone from metadata or default to Brazil timezone.

        Args:
            patient: Patient object

        Returns:
            Timezone string
        """
        timezone_str = getattr(patient, "timezone", None)
        return timezone_str or self.config.DEFAULT_TIMEZONE

    def _get_scheduling_window_times(
        self, window: SchedulingWindow
    ) -> Tuple[time, time]:
        """
        Get start and end times for a scheduling window.

        Args:
            window: Scheduling window enum

        Returns:
            Tuple of (start_time, end_time)
        """
        return self.scheduling_windows.get(
            window, self.scheduling_windows[SchedulingWindow.BUSINESS_HOURS]
        )

    def calculate_next_send_time(
        self,
        patient: Patient,
        window: SchedulingWindow = SchedulingWindow.BUSINESS_HOURS,
        min_delay_minutes: Optional[int] = None,
    ) -> datetime:
        """
        Calculate next appropriate send time for a patient.

        Args:
            patient: Patient object
            window: Desired scheduling window
            min_delay_minutes: Minimum delay in minutes

        Returns:
            Next send datetime (UTC)
        """
        try:
            # Get patient timezone
            patient_tz_str = self._get_patient_timezone(patient)
            patient_tz = pytz.timezone(patient_tz_str)

            # Get current time in patient timezone
            now_utc = datetime.utcnow()
            now_patient = now_utc.replace(tzinfo=pytz.utc).astimezone(patient_tz)

            # Get window times
            start_time, end_time = self._get_scheduling_window_times(window)

            # Calculate minimum send time
            min_delay = min_delay_minutes or self.config.MIN_SCHEDULING_BUFFER_MINUTES
            min_send_time = now_patient + timedelta(minutes=min_delay)

            # If within window and after minimum delay, send soon
            if start_time <= min_send_time.time() <= end_time:
                send_time_patient = min_send_time
            else:
                # Schedule for next window
                if min_send_time.time() < start_time:
                    # Same day, at window start
                    send_time_patient = min_send_time.replace(
                        hour=start_time.hour,
                        minute=start_time.minute,
                        second=0,
                        microsecond=0,
                    )
                else:
                    # Next day, at window start
                    next_day = min_send_time + timedelta(days=1)
                    send_time_patient = next_day.replace(
                        hour=start_time.hour,
                        minute=start_time.minute,
                        second=0,
                        microsecond=0,
                    )

            # Convert back to UTC
            send_time_utc = send_time_patient.astimezone(pytz.utc).replace(tzinfo=None)

            logger.info(
                f"Calculated send time for patient {patient.id}: "
                f"{send_time_utc} UTC ({send_time_patient} {patient_tz_str})"
            )

            return send_time_utc

        except Exception as e:
            logger.error(f"Error calculating send time: {e}", exc_info=True)
            # Fallback: send in 30 minutes
            fallback_time = datetime.utcnow() + timedelta(
                minutes=self.config.FALLBACK_DELAY_MINUTES
            )
            logger.warning(f"Using fallback send time: {fallback_time}")
            return fallback_time

    def schedule_message_for_patient(
        self,
        patient_id: UUID,
        content: str,
        window: SchedulingWindow = SchedulingWindow.BUSINESS_HOURS,
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict[str, Any]] = None,
        min_delay_minutes: Optional[int] = None,
    ) -> Message:
        """
        Schedule a message for a patient in appropriate time window.

        Args:
            patient_id: Patient UUID
            content: Message content
            window: Desired scheduling window
            message_type: Type of message
            metadata: Optional metadata
            min_delay_minutes: Minimum delay in minutes

        Returns:
            Scheduled Message object

        Raises:
            NotFoundError: If patient not found
        """
        # Get patient
        patient = self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise NotFoundError(f"Patient {patient_id} not found")

        # Calculate send time
        scheduled_for = self.calculate_next_send_time(
            patient, window, min_delay_minutes
        )

        # Create scheduled message
        return self.message_service.schedule_message(
            patient_id=patient_id,
            content=content,
            scheduled_for=scheduled_for,
            message_type=message_type,
            message_metadata=metadata,
        )

    def get_due_messages(self, limit: int = 100) -> List[Message]:
        """
        Get messages that are due to be sent.

        Args:
            limit: Maximum number of messages

        Returns:
            List of due Message objects
        """
        now = datetime.utcnow()
        return self.message_service.get_scheduled_messages(now, limit=limit)

    def reschedule_message(
        self, message_id: UUID, new_time: datetime
    ) -> Optional[Message]:
        """
        Reschedule an existing message.

        Args:
            message_id: Message UUID
            new_time: New scheduled time

        Returns:
            Updated Message object or None
        """
        message = self.message_service.get_message(message_id)
        if not message:
            return None

        if message.status not in [MessageStatus.SCHEDULED, MessageStatus.PENDING]:
            logger.warning(
                f"Cannot reschedule message {message_id} with status {message.status}"
            )
            return None

        message.scheduled_for = new_time
        message.status = MessageStatus.SCHEDULED

        self.db.commit()
        self.db.refresh(message)

        return message
