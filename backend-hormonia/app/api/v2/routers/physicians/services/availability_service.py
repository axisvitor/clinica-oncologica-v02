"""
PhysicianAvailabilityService - Manage physician availability and schedules.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, time, date, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment, AppointmentStatus
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class PhysicianAvailabilityService:
    """
    Service for managing physician availability and scheduling.

    Features:
    - Check available time slots
    - Get schedule for date range
    - Calculate busy periods
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize availability service.

        Args:
            db: Database session
        """
        self.db = db

    async def get_available_slots(
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
        booked_result = await self.db.execute(
            select(Appointment)
            .where(
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
            )
            .order_by(Appointment.scheduled_at)
        )
        booked_appointments = booked_result.scalars().all()

        # Build a set of booked start times for O(1) overlap checking
        booked_starts = set()
        for appt in booked_appointments:
            appt_time = appt.scheduled_at
            if appt_time is not None:
                if appt_time.tzinfo is None:
                    appt_time = appt_time.replace(tzinfo=timezone.utc)
                booked_starts.add(appt_time)

        # Default working hours for v1.1 — no DB model exists yet.
        # Future: load from physician preferences/settings table.
        WORK_START = time(8, 0)
        WORK_END = time(17, 0)
        WORK_DAYS = {0, 1, 2, 3, 4}  # Monday=0 through Friday=4

        # Generate slots by iterating each day in the date range
        available_slots = []
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() in WORK_DAYS:
                slot_start = datetime.combine(current_date, WORK_START).replace(tzinfo=timezone.utc)
                end_of_day = datetime.combine(current_date, WORK_END).replace(tzinfo=timezone.utc)
                while slot_start + timedelta(minutes=slot_duration_minutes) <= end_of_day:
                    slot_end = slot_start + timedelta(minutes=slot_duration_minutes)
                    # A slot is unavailable if any booked appointment starts within [slot_start, slot_end)
                    is_booked = any(
                        slot_start <= appt_start < slot_end
                        for appt_start in booked_starts
                    )
                    if not is_booked:
                        available_slots.append({
                            "start": slot_start.isoformat(),
                            "end": slot_end.isoformat(),
                            "duration_minutes": slot_duration_minutes,
                        })
                    slot_start += timedelta(minutes=slot_duration_minutes)
            current_date += timedelta(days=1)

        return available_slots

    async def get_schedule(
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
        appointments_result = await self.db.execute(
            select(Appointment)
            .where(
                Appointment.practitioner_id == physician_id,
                Appointment.scheduled_at >= datetime.combine(start_date, time.min),
                Appointment.scheduled_at <= datetime.combine(end_date, time.max),
            )
            .order_by(Appointment.scheduled_at)
        )
        appointments = appointments_result.scalars().all()

        return {
            "physician_id": str(physician_id),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "appointments": [
                {
                    "id": str(appt.id),
                    "scheduled_at": appt.scheduled_at.isoformat(),
                    "status": appt.status,
                    "patient_id": (
                        str(patient_id)
                        if (patient_id := getattr(appt, "patient_id", None)) is not None
                        else None
                    ),
                }
                for appt in appointments
            ],
            "total_appointments": len(appointments),
        }

    async def is_available(
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
        overlapping_result = await self.db.execute(
            select(Appointment.id).where(
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
            .limit(1)
        )
        overlapping = overlapping_result.scalar_one_or_none()

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
            after_datetime = now_sao_paulo()

        # TODO: Implement logic to find next available slot
        # This would integrate with physician working hours/preferences

        return None
