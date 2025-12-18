from typing import Optional, Any
from uuid import UUID
from datetime import datetime, timedelta


from app.repositories.appointment import AppointmentRepository
from app.models.appointment import Appointment, AppointmentStatus, AppointmentType
from app.schemas.v2.appointment import AppointmentV2Create, AppointmentV2Update
from app.utils.db_retry import with_db_retry


class AppointmentService:
    def __init__(self, db: Any, repository: AppointmentRepository):
        self.db = db
        self.repository = repository

    @with_db_retry()
    def create_appointment(self, data: AppointmentV2Create) -> Appointment:
        # Convert IDs
        practitioner_uuid = UUID(data.practitioner_id) if data.practitioner_id else None

        # Conflict check
        if practitioner_uuid and data.scheduled_at:
            if self._check_conflict(
                practitioner_uuid, data.scheduled_at, data.duration_minutes
            ):
                raise ValueError("Scheduling conflict detected")

        # Create
        create_data = data.dict(
            exclude={"patient_id", "practitioner_id", "status", "appointment_type"}
        )
        create_data["patient_id"] = UUID(data.patient_id)
        if practitioner_uuid:
            create_data["practitioner_id"] = practitioner_uuid

        if data.status:
            create_data["status"] = AppointmentStatus(data.status.lower())
        else:
            create_data["status"] = AppointmentStatus.SCHEDULED

        if data.appointment_type:
            create_data["appointment_type"] = AppointmentType(
                data.appointment_type.lower()
            )

        new_appt = Appointment(**create_data)
        self.db.add(new_appt)
        self.db.commit()
        self.db.refresh(new_appt)

        return new_appt

    @with_db_retry()
    def update_appointment(
        self, id: UUID, data: AppointmentV2Update
    ) -> Optional[Appointment]:
        appt = self.repository.get_by_id(id)
        if not appt:
            return None

        update_data = data.dict(exclude_unset=True)

        # Conflict check if rescheduling
        if "scheduled_at" in update_data or "duration_minutes" in update_data:
            new_start = update_data.get("scheduled_at", appt.scheduled_at)
            new_duration = update_data.get("duration_minutes", appt.duration_minutes)

            # Get practitioner ID from update or existing
            practitioner_id = None
            if "practitioner_id" in update_data and update_data["practitioner_id"]:
                practitioner_id = UUID(update_data["practitioner_id"])
            else:
                practitioner_id = appt.practitioner_id

            if new_start and new_duration and practitioner_id:
                if self._check_conflict(
                    practitioner_id, new_start, new_duration, exclude_id=id
                ):
                    raise ValueError("Scheduling conflict detected")

        # Status transition validation
        if "status" in update_data:
            new_status_str = update_data["status"]
            new_status = AppointmentStatus(new_status_str.lower())
            self._validate_status_transition(appt.status, new_status)
            update_data["status"] = new_status

            # Auto-timestamps
            if new_status == AppointmentStatus.COMPLETED:
                update_data["completed_at"] = datetime.utcnow()
            elif new_status == AppointmentStatus.CANCELLED:
                update_data["cancelled_at"] = datetime.utcnow()

        # Type conversion
        if "appointment_type" in update_data:
            update_data["appointment_type"] = AppointmentType(
                update_data["appointment_type"].lower()
            )
        if "practitioner_id" in update_data and update_data["practitioner_id"]:
            update_data["practitioner_id"] = UUID(update_data["practitioner_id"])

        # Update
        for k, v in update_data.items():
            setattr(appt, k, v)

        self.db.commit()
        self.db.refresh(appt)
        return appt

    @with_db_retry()
    def cancel_appointment(self, id: UUID) -> Optional[Appointment]:
        appt = self.repository.get_by_id(id)
        if not appt:
            return None

        # Check current status
        current_status = appt.status
        # Handle enum or string
        if hasattr(current_status, "value"):
            current_status = current_status.value

        allowed = [AppointmentStatus.SCHEDULED.value, AppointmentStatus.CONFIRMED.value]

        if current_status not in allowed:
            raise ValueError(f"Cannot cancel appointment with status {current_status}")

        appt.status = AppointmentStatus.CANCELLED
        appt.cancelled_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(appt)
        return appt

    @with_db_retry()
    def complete_appointment(
        self, id: UUID, notes: Optional[str] = None
    ) -> Optional[Appointment]:
        appt = self.repository.get_by_id(id)
        if not appt:
            return None

        current_status = appt.status
        if hasattr(current_status, "value"):
            current_status = current_status.value

        if current_status != AppointmentStatus.IN_PROGRESS.value:
            raise ValueError(
                f"Cannot complete appointment with status {current_status}. Must be in_progress."
            )

        appt.status = AppointmentStatus.COMPLETED
        appt.completed_at = datetime.utcnow()
        if notes:
            appt.post_appointment_notes = notes

        self.db.commit()
        self.db.refresh(appt)
        return appt

    def _check_conflict(
        self,
        practitioner_id: UUID,
        start: datetime,
        duration: int,
        exclude_id: Optional[UUID] = None,
    ) -> bool:
        end = start + timedelta(minutes=duration)
        conflicts = self.repository.find_conflicts(
            practitioner_id, start, end, exclude_id
        )
        return len(conflicts) > 0

    def _validate_status_transition(self, old_status, new_status):
        old_val = old_status.value if hasattr(old_status, "value") else old_status
        new_val = new_status.value if hasattr(new_status, "value") else new_status

        valid_transitions = {
            AppointmentStatus.SCHEDULED.value: [
                AppointmentStatus.CONFIRMED.value,
                AppointmentStatus.CANCELLED.value,
            ],
            AppointmentStatus.CONFIRMED.value: [
                AppointmentStatus.IN_PROGRESS.value,
                AppointmentStatus.CANCELLED.value,
                AppointmentStatus.NO_SHOW.value,
            ],
            AppointmentStatus.IN_PROGRESS.value: [AppointmentStatus.COMPLETED.value],
            AppointmentStatus.COMPLETED.value: [],
            AppointmentStatus.CANCELLED.value: [],
            AppointmentStatus.NO_SHOW.value: [],
        }

        if new_val != old_val and new_val not in valid_transitions.get(old_val, []):
            raise ValueError(f"Invalid status transition from {old_val} to {new_val}")
