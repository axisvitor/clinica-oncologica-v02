"""
PhysicianAvailabilityService - Manage physician availability and schedules.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, time, date, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus

logger = logging.getLogger(__name__)


class PhysicianAvailabilityService:
    """
    Service for managing physician availability and scheduling.

    Features:
    - Check available time slots
    - Get schedule for date range
    - Calculate busy periods
    """

    def __init__(self, db: Session):
        """
        Initialize availability service.

        Args:
            db: Database session
        """
        self.db = db

    def get_available_slots(
        self,
        physician_id: UUID,
        start_date: date,
        end_date: date,
        slot_duration_minutes: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Get available time slots for a physician within a date range.

        Args:
            physician_id: Physician UUID
            start_date: Start date for availability
            end_date: End date for availability
            slot_duration_minutes: Duration of each slot in minutes

        Returns:
            List of available time slots with metadata
        """
        # Get existing appointments in the range
        self.db.query(Appointment).filter(
            Appointment.practitioner_id == physician_id,
            Appointment.scheduled_at >= datetime.combine(start_date, time.min),
            Appointment.scheduled_at <= datetime.combine(end_date, time.max),
            Appointment.status.in_(
                [
                    AppointmentStatus.SCHEDULED.value,
                    AppointmentStatus.CONFIRMED.value,
                    AppointmentStatus.IN_PROGRESS.value,
                ]
            ),
        ).order_by(Appointment.scheduled_at).all()

        # TODO: Implement slot generation logic based on working hours
        # This would typically come from physician preferences/settings
        available_slots = []

        return available_slots

    def get_schedule(
        self, physician_id: UUID, start_date: date, end_date: date
    ) -> Dict[str, Any]:
        """
        Get physician's complete schedule for a date range.

        Args:
            physician_id: Physician UUID
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary with schedule information
        """
        appointments = (
            self.db.query(Appointment)
            .filter(
                Appointment.practitioner_id == physician_id,
                Appointment.scheduled_at >= datetime.combine(start_date, time.min),
                Appointment.scheduled_at <= datetime.combine(end_date, time.max),
            )
            .order_by(Appointment.scheduled_at)
            .all()
        )

        return {
            "physician_id": str(physician_id),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "appointments": [
                {
                    "id": str(appt.id),
                    "scheduled_at": appt.scheduled_at.isoformat(),
                    "status": appt.status,
                    "patient_id": str(appt.patient_id) if appt.patient_id else None,
                }
                for appt in appointments
            ],
            "total_appointments": len(appointments),
        }

    def is_available(
        self,
        physician_id: UUID,
        requested_datetime: datetime,
        duration_minutes: int = 30,
    ) -> bool:
        """
        Check if physician is available at a specific datetime.

        Args:
            physician_id: Physician UUID
            requested_datetime: Requested appointment datetime
            duration_minutes: Appointment duration in minutes

        Returns:
            True if physician is available
        """
        end_time = requested_datetime + timedelta(minutes=duration_minutes)

        # Check for overlapping appointments
        overlapping = (
            self.db.query(Appointment)
            .filter(
                Appointment.practitioner_id == physician_id,
                Appointment.status.in_(
                    [
                        AppointmentStatus.SCHEDULED.value,
                        AppointmentStatus.CONFIRMED.value,
                        AppointmentStatus.IN_PROGRESS.value,
                    ]
                ),
                or_(
                    # Appointment starts during requested slot
                    and_(
                        Appointment.scheduled_at >= requested_datetime,
                        Appointment.scheduled_at < end_time,
                    ),
                    # Appointment ends during requested slot
                    and_(
                        Appointment.scheduled_at < requested_datetime,
                        Appointment.scheduled_at >= end_time,
                    ),
                ),
            )
            .first()
        )

        return overlapping is None

    def get_next_available_slot(
        self,
        physician_id: UUID,
        after_datetime: Optional[datetime] = None,
        duration_minutes: int = 30,
        max_days_ahead: int = 30,
    ) -> Optional[datetime]:
        """
        Find the next available appointment slot.

        Args:
            physician_id: Physician UUID
            after_datetime: Start searching after this datetime
            duration_minutes: Required appointment duration
            max_days_ahead: Maximum days to search ahead

        Returns:
            Next available datetime or None
        """
        if after_datetime is None:
            after_datetime = datetime.now(timezone.utc)

        # TODO: Implement logic to find next available slot
        # This would integrate with physician working hours/preferences

        return None
