"""
Appointments API v2
Enhanced appointment endpoints with cursor pagination, field selection, and eager loading.
"""

from typing import Optional, List, Tuple, Dict
from datetime import date, datetime, timedelta
from uuid import UUID
import logging
import json
import base64
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, or_

from app.database import get_db
from app.models.appointment import Appointment, AppointmentStatus, AppointmentType
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.schemas.v2.appointment import (
    AppointmentV2Response,
    AppointmentV2List,
    AppointmentV2Create,
    AppointmentV2Update,
)
from app.schemas.v2.common import ErrorResponse
from .dependencies import (
    get_pagination_params,
    get_field_selection,
    get_eager_load_params,
    create_cursor,
    apply_field_selection,
)
from app.api.v2.patients import _get_current_user_simple
from app.dependencies.auth_dependencies import get_current_user_from_session, get_redis_cache
from app.utils.rate_limiter import limiter
from fastapi import Cookie, Header
import asyncio

router = APIRouter()
logger = logging.getLogger(__name__)


def _extract_user_context(current_user) -> Tuple[Optional[UserRole], Optional[str]]:
    """Return (role, user_id as str) from current_user (model or dict)."""
    role = None
    user_id = None

    if isinstance(current_user, dict):
        role = current_user.get("role")
        user_id = current_user.get("id")
    else:
        user_id = getattr(current_user, "id", None)
        role = getattr(current_user, "role", None)

    if isinstance(role, UserRole):
        role_enum = role
    elif isinstance(role, str):
        try:
            role_enum = UserRole(role.lower())
        except ValueError:
            role_enum = None
    else:
        role_enum = None

    if user_id is not None:
        user_id = str(user_id)

    return role_enum, user_id


def _is_admin(current_user) -> bool:
    role_enum, _ = _extract_user_context(current_user)
    return role_enum == UserRole.ADMIN


def _ensure_uuid(value: Optional[str]):
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _ensure_appointment_access(current_user, appointment: Appointment):
    """Ensure current user has access to the appointment."""
    if _is_admin(current_user):
        return

    _, user_id = _extract_user_context(current_user)
    user_uuid = _ensure_uuid(user_id)

    # Doctors can only access their own appointments
    if user_uuid is None or appointment.practitioner_id != user_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this appointment",
        )


def _serialize_appointment(appointment: Appointment) -> Optional[dict]:
    """Serialize Appointment SQLAlchemy model to API-friendly dict."""
    if appointment is None:
        return None

    status_value = appointment.status
    if isinstance(status_value, AppointmentStatus):
        status_value = status_value.value

    appointment_type_value = appointment.appointment_type
    if isinstance(appointment_type_value, AppointmentType):
        appointment_type_value = appointment_type_value.value

    return {
        "id": str(appointment.id),
        "patient_id": str(appointment.patient_id),
        "practitioner_id": str(appointment.practitioner_id) if appointment.practitioner_id else None,
        "appointment_type": appointment_type_value,
        "status": status_value,
        "scheduled_at": appointment.scheduled_at,
        "duration_minutes": appointment.duration_minutes,
        "cancelled_at": appointment.cancelled_at,
        "completed_at": appointment.completed_at,
        "pre_appointment_notes": appointment.pre_appointment_notes,
        "post_appointment_notes": appointment.post_appointment_notes,
        "reminder_sent": appointment.reminder_sent,
        "confirmation_sent": appointment.confirmation_sent,
        "created_at": appointment.created_at,
        "updated_at": appointment.updated_at,
    }


class ConflictCheckRequest(BaseModel):
    """Request body for conflict detection."""
    practitioner_id: str
    scheduled_at: datetime
    duration_minutes: int = 30
    exclude_appointment_id: Optional[str] = None


class ConflictCheckResponse(BaseModel):
    """Response for conflict detection."""
    has_conflict: bool
    conflicting_appointments: List[dict] = []


@router.get(
    "",
    response_model=AppointmentV2List,
    summary="List appointments with pagination",
    description="Get paginated list of appointments with optional field selection and eager loading"
)
async def list_appointments(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    pagination = Depends(get_pagination_params),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    redis_cache = Depends(get_redis_cache),
    search: Optional[str] = Query(None, description="Search by patient name"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    practitioner_id: Optional[str] = Query(None, description="Filter by practitioner ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by appointment status"),
    appointment_type: Optional[str] = Query(None, description="Filter by appointment type"),
    date_from: Optional[date] = Query(None, description="Filter appointments from this date"),
    date_to: Optional[date] = Query(None, description="Filter appointments to this date"),
):
    """
    List appointments with cursor-based pagination.

    Features:
    - Cursor-based pagination (efficient for large datasets)
    - Field selection (?fields=id,patient_id,status)
    - Eager loading (?include=patient,practitioner)
    - Search by patient name
    - Filter by patient, practitioner, status, type, date range
    - Redis caching for performance

    Example:
        GET /api/v2/appointments?limit=20&fields=id,patient_id,status&include=patient
    """
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    # Check cache for list endpoint
    cache_key = f"appointments:list:{cursor_data}:{limit}:{search}:{patient_id}:{practitioner_id}:{status_filter}:{appointment_type}:{date_from}:{date_to}"
    cached_data = await redis_cache.get(cache_key)

    if cached_data:
        logger.debug(f"Cache hit for appointments list: {cache_key}")
        return json.loads(cached_data)

    # Build base query
    query = db.query(Appointment)

    # Apply eager loading
    if include:
        if "patient" in include:
            query = query.options(joinedload(Appointment.patient))
        if "practitioner" in include:
            query = query.options(joinedload(Appointment.practitioner))

    # Apply filters
    filters = []
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    # RBAC: Non-admin users can only see their own appointments
    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to determine user permissions",
            )
        filters.append(Appointment.practitioner_id == current_user_uuid)

    if cursor_data and "id" in cursor_data:
        cursor_id = UUID(cursor_data["id"]) if isinstance(cursor_data["id"], str) else cursor_data["id"]
        cursor_created_at = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))

        filters.append(
            (Appointment.created_at < cursor_created_at) |
            ((Appointment.created_at == cursor_created_at) & (Appointment.id > cursor_id))
        )

    if search:
        # Search by patient name - need to join with patient table
        search_filter = f"%{search}%"
        query = query.join(Patient, Appointment.patient_id == Patient.id)
        filters.append(Patient.name.ilike(search_filter))

    if patient_id:
        try:
            patient_uuid = UUID(patient_id)
            filters.append(Appointment.patient_id == patient_uuid)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid patient ID format"
            )

    if practitioner_id:
        try:
            practitioner_uuid = UUID(practitioner_id)
            filters.append(Appointment.practitioner_id == practitioner_uuid)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid practitioner ID format"
            )

    if status_filter:
        status_value = status_filter.strip().lower()
        try:
            target_status = AppointmentStatus(status_value)
            filters.append(Appointment.status == target_status.value)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status filter. Use scheduled, confirmed, in_progress, completed, cancelled, or no_show."
            )

    if appointment_type:
        type_value = appointment_type.strip().lower()
        try:
            target_type = AppointmentType(type_value)
            filters.append(Appointment.appointment_type == target_type.value)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid appointment type. Use consultation, followup, treatment, exam, emergency, or telemedicine."
            )

    if date_from:
        filters.append(func.date(Appointment.scheduled_at) >= date_from)

    if date_to:
        filters.append(func.date(Appointment.scheduled_at) <= date_to)

    if filters:
        query = query.filter(and_(*filters))

    total = None
    if not cursor_data:
        total_query = db.query(func.count(Appointment.id))
        if filters:
            total_query = total_query.filter(and_(*filters))
        total = total_query.scalar()

    # Order and limit
    query = query.order_by(Appointment.created_at.desc(), Appointment.id)
    appointments = query.limit(limit + 1).all()

    # Check if there are more results
    has_more = len(appointments) > limit
    if has_more:
        appointments = appointments[:limit]

    # Create next cursor
    next_cursor = None
    if has_more and appointments:
        cursor_data = {
            "id": str(appointments[-1].id),
            "created_at": appointments[-1].created_at.isoformat()
        }
        next_cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()

    # Convert to response models
    appointment_responses = []
    for appointment in appointments:
        appointment_dict = _serialize_appointment(appointment)

        # Add eager-loaded relationships
        if include:
            if "patient" in include and appointment.patient:
                appointment_dict["patient"] = {
                    "id": str(appointment.patient.id),
                    "name": appointment.patient.name,
                    "email": appointment.patient.email,
                    "phone": appointment.patient.phone,
                }
            if "practitioner" in include and appointment.practitioner:
                appointment_dict["practitioner"] = {
                    "id": str(appointment.practitioner.id),
                    "name": appointment.practitioner.full_name,
                    "email": appointment.practitioner.email,
                }

        # Apply field selection
        if fields:
            appointment_dict = apply_field_selection(appointment_dict, fields)

        appointment_responses.append(appointment_dict)

    response_data = {
        "data": appointment_responses,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
    }

    # Cache the response for 2 minutes
    await redis_cache.set(cache_key, json.dumps(response_data, default=str), ttl=120)

    return response_data


@router.get(
    "/conflicts",
    response_model=ConflictCheckResponse,
    summary="Check for scheduling conflicts",
    description="Check if a practitioner has conflicting appointments at the specified time"
)
async def check_conflicts(
    practitioner_id: str = Query(..., description="Practitioner UUID"),
    scheduled_at: datetime = Query(..., description="Proposed appointment time"),
    duration_minutes: int = Query(30, ge=15, le=480, description="Appointment duration"),
    exclude_appointment_id: Optional[str] = Query(None, description="Exclude this appointment from conflict check"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """
    Check for scheduling conflicts.

    Checks if the practitioner has any appointments that overlap with the
    specified time window. Useful for preventing double-booking.

    Example:
        GET /api/v2/appointments/conflicts?practitioner_id=123&scheduled_at=2025-11-10T10:00:00Z&duration_minutes=30
    """
    # Validate practitioner_id
    try:
        practitioner_uuid = UUID(practitioner_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid practitioner ID format"
        )

    # Calculate appointment end time
    appointment_end = scheduled_at + timedelta(minutes=duration_minutes)

    # Build conflict query
    query = db.query(Appointment).filter(
        Appointment.practitioner_id == practitioner_uuid,
        Appointment.status.in_([
            AppointmentStatus.SCHEDULED.value,
            AppointmentStatus.CONFIRMED.value,
            AppointmentStatus.IN_PROGRESS.value
        ]),
        Appointment.scheduled_at.isnot(None)
    )

    # Exclude current appointment if editing
    if exclude_appointment_id:
        try:
            exclude_uuid = UUID(exclude_appointment_id)
            query = query.filter(Appointment.id != exclude_uuid)
        except ValueError:
            pass

    # Check for overlapping appointments
    conflicts = []
    for appt in query.all():
        if appt.scheduled_at and appt.duration_minutes:
            appt_end = appt.scheduled_at + timedelta(minutes=appt.duration_minutes)

            # Check if appointments overlap
            if (scheduled_at < appt_end and appointment_end > appt.scheduled_at):
                conflicts.append({
                    "id": str(appt.id),
                    "patient_id": str(appt.patient_id),
                    "scheduled_at": appt.scheduled_at.isoformat(),
                    "duration_minutes": appt.duration_minutes,
                    "status": appt.status,
                })

    return ConflictCheckResponse(
        has_conflict=len(conflicts) > 0,
        conflicting_appointments=conflicts
    )


@router.get(
    "/{appointment_id}",
    response_model=AppointmentV2Response,
    summary="Get appointment by ID",
    description="Get a single appointment with optional field selection and eager loading"
)
async def get_appointment(
    appointment_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    redis_cache = Depends(get_redis_cache),
):
    """
    Get a single appointment by ID.

    Features:
    - Field selection (?fields=id,patient_id,status)
    - Eager loading (?include=patient,practitioner)
    - Redis caching for performance

    Example:
        GET /api/v2/appointments/123e4567-e89b-12d3-a456-426614174000?include=patient,practitioner
    """
    # Check cache
    cache_key = f"appointment:{appointment_id}:{fields}:{include}"
    cached_data = await redis_cache.get(cache_key)

    if cached_data:
        logger.debug(f"Cache hit for appointment: {appointment_id}")
        return json.loads(cached_data)

    try:
        appointment_uuid = UUID(appointment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid appointment ID format"
        )

    query = db.query(Appointment)

    # Apply eager loading
    if include:
        if "patient" in include:
            query = query.options(joinedload(Appointment.patient))
        if "practitioner" in include:
            query = query.options(joinedload(Appointment.practitioner))

    appointment = query.filter(Appointment.id == appointment_uuid).first()

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with id {appointment_id} not found"
        )

    _ensure_appointment_access(current_user, appointment)

    # Build response
    appointment_dict = _serialize_appointment(appointment)

    # Add eager-loaded relationships
    if include:
        if "patient" in include and appointment.patient:
            appointment_dict["patient"] = {
                "id": str(appointment.patient.id),
                "name": appointment.patient.name,
                "email": appointment.patient.email,
                "phone": appointment.patient.phone,
            }
        if "practitioner" in include and appointment.practitioner:
            appointment_dict["practitioner"] = {
                "id": str(appointment.practitioner.id),
                "name": appointment.practitioner.full_name,
                "email": appointment.practitioner.email,
            }

    # Apply field selection
    if fields:
        appointment_dict = apply_field_selection(appointment_dict, fields)

    # Cache for 5 minutes
    await redis_cache.set(cache_key, json.dumps(appointment_dict, default=str), ttl=300)

    return appointment_dict


@router.post(
    "",
    response_model=AppointmentV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Create new appointment",
    description="Create a new appointment with conflict detection"
)
@limiter.limit("30/hour")
async def create_appointment(
    request: Request,
    appointment_data: AppointmentV2Create,
    db: Session = Depends(get_db),
    current_user = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache),
):
    """
    Create a new appointment.

    Features:
    - Automatic conflict detection
    - Validates patient and practitioner exist
    - RBAC enforcement (doctors can only create their own appointments)

    Validates:
    - Patient exists
    - Practitioner exists (if specified)
    - No scheduling conflicts
    """
    # Convert IDs to UUID
    try:
        patient_uuid = UUID(appointment_data.patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format"
        )

    practitioner_uuid = None
    if appointment_data.practitioner_id:
        try:
            practitioner_uuid = UUID(appointment_data.practitioner_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid practitioner ID format"
            )

    # Check if patient exists
    patient = db.query(Patient).filter(Patient.id == patient_uuid).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with id {appointment_data.patient_id} not found"
        )

    # Check if practitioner exists (if specified)
    if practitioner_uuid:
        practitioner = db.query(User).filter(User.id == practitioner_uuid).first()
        if not practitioner:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Practitioner with id {appointment_data.practitioner_id} not found"
            )

    # RBAC: Non-admin users can only create appointments for themselves
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    if role_enum != UserRole.ADMIN:
        if not practitioner_uuid or current_user_uuid != practitioner_uuid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Doctors can only create appointments for themselves"
            )

    # Check for scheduling conflicts
    if practitioner_uuid and appointment_data.scheduled_at:
        appointment_end = appointment_data.scheduled_at + timedelta(minutes=appointment_data.duration_minutes)

        conflicts = db.query(Appointment).filter(
            Appointment.practitioner_id == practitioner_uuid,
            Appointment.status.in_([
                AppointmentStatus.SCHEDULED.value,
                AppointmentStatus.CONFIRMED.value,
                AppointmentStatus.IN_PROGRESS.value
            ]),
            Appointment.scheduled_at.isnot(None)
        ).all()

        for conflict in conflicts:
            if conflict.scheduled_at and conflict.duration_minutes:
                conflict_end = conflict.scheduled_at + timedelta(minutes=conflict.duration_minutes)
                if (appointment_data.scheduled_at < conflict_end and appointment_end > conflict.scheduled_at):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Scheduling conflict detected with appointment {conflict.id}"
                    )

    # Create appointment
    new_appointment = Appointment(
        patient_id=patient_uuid,
        practitioner_id=practitioner_uuid,
        appointment_type=appointment_data.appointment_type,
        status=appointment_data.status or AppointmentStatus.SCHEDULED.value,
        scheduled_at=appointment_data.scheduled_at,
        duration_minutes=appointment_data.duration_minutes,
        pre_appointment_notes=appointment_data.pre_appointment_notes,
    )

    db.add(new_appointment)
    db.commit()
    db.refresh(new_appointment)

    # Invalidate cache
    await redis_cache.delete(f"appointments:list:*")

    return _serialize_appointment(new_appointment)


@router.patch(
    "/{appointment_id}",
    response_model=AppointmentV2Response,
    summary="Update appointment",
    description="Update appointment information (partial update)"
)
@limiter.limit("30/hour")
async def update_appointment(
    request: Request,
    appointment_id: str,
    appointment_data: AppointmentV2Update,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """
    Update an appointment (partial update).

    Features:
    - Partial update (only provided fields are updated)
    - Conflict detection for rescheduling
    - Status transition validation

    Only provided fields will be updated.
    """
    try:
        appointment_uuid = UUID(appointment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid appointment ID format"
        )

    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_uuid
    ).first()

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with id {appointment_id} not found"
        )

    _ensure_appointment_access(current_user, appointment)

    # Update only provided fields
    update_data = appointment_data.dict(exclude_unset=True)

    # Validate status transitions
    if "status" in update_data:
        old_status = appointment.status
        new_status = update_data["status"]

        # Define valid transitions
        valid_transitions = {
            AppointmentStatus.SCHEDULED.value: [AppointmentStatus.CONFIRMED.value, AppointmentStatus.CANCELLED.value],
            AppointmentStatus.CONFIRMED.value: [AppointmentStatus.IN_PROGRESS.value, AppointmentStatus.CANCELLED.value, AppointmentStatus.NO_SHOW.value],
            AppointmentStatus.IN_PROGRESS.value: [AppointmentStatus.COMPLETED.value],
            AppointmentStatus.COMPLETED.value: [],  # Cannot change completed status
            AppointmentStatus.CANCELLED.value: [],  # Cannot change cancelled status
            AppointmentStatus.NO_SHOW.value: [],    # Cannot change no-show status
        }

        if new_status != old_status and new_status not in valid_transitions.get(old_status, []):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status transition from {old_status} to {new_status}"
            )

        # Set timestamps for status changes
        if new_status == AppointmentStatus.COMPLETED.value:
            update_data["completed_at"] = datetime.utcnow()
        elif new_status == AppointmentStatus.CANCELLED.value:
            update_data["cancelled_at"] = datetime.utcnow()

    # Check for conflicts if rescheduling
    if "scheduled_at" in update_data or "duration_minutes" in update_data:
        new_scheduled_at = update_data.get("scheduled_at", appointment.scheduled_at)
        new_duration = update_data.get("duration_minutes", appointment.duration_minutes)

        if new_scheduled_at and new_duration:
            appointment_end = new_scheduled_at + timedelta(minutes=new_duration)

            conflicts = db.query(Appointment).filter(
                Appointment.practitioner_id == appointment.practitioner_id,
                Appointment.id != appointment.id,
                Appointment.status.in_([
                    AppointmentStatus.SCHEDULED.value,
                    AppointmentStatus.CONFIRMED.value,
                    AppointmentStatus.IN_PROGRESS.value
                ]),
                Appointment.scheduled_at.isnot(None)
            ).all()

            for conflict in conflicts:
                if conflict.scheduled_at and conflict.duration_minutes:
                    conflict_end = conflict.scheduled_at + timedelta(minutes=conflict.duration_minutes)
                    if (new_scheduled_at < conflict_end and appointment_end > conflict.scheduled_at):
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=f"Scheduling conflict detected with appointment {conflict.id}"
                        )

    # Convert practitioner_id to UUID if provided
    if "practitioner_id" in update_data and update_data["practitioner_id"]:
        try:
            new_practitioner_uuid = UUID(update_data["practitioner_id"])

            # Check if practitioner exists
            practitioner = db.query(User).filter(User.id == new_practitioner_uuid).first()
            if not practitioner:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Practitioner not found"
                )

            update_data["practitioner_id"] = new_practitioner_uuid
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid practitioner ID format"
            )

    for field, value in update_data.items():
        setattr(appointment, field, value)

    db.commit()
    db.refresh(appointment)

    # Invalidate cache
    await redis_cache.delete(f"appointment:{appointment_id}:*")
    await redis_cache.delete(f"appointments:list:*")

    return _serialize_appointment(appointment)


@router.patch(
    "/{appointment_id}/cancel",
    response_model=AppointmentV2Response,
    summary="Cancel appointment",
    description="Cancel an appointment and record cancellation time"
)
@limiter.limit("30/hour")
async def cancel_appointment(
    request: Request,
    appointment_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """
    Cancel an appointment.

    Sets status to CANCELLED and records cancellation timestamp.
    Can only cancel appointments in SCHEDULED or CONFIRMED status.
    """
    try:
        appointment_uuid = UUID(appointment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid appointment ID format"
        )

    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_uuid
    ).first()

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with id {appointment_id} not found"
        )

    _ensure_appointment_access(current_user, appointment)

    # Can only cancel scheduled or confirmed appointments
    if appointment.status not in [AppointmentStatus.SCHEDULED.value, AppointmentStatus.CONFIRMED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel appointment with status {appointment.status}"
        )

    appointment.status = AppointmentStatus.CANCELLED.value
    appointment.cancelled_at = datetime.utcnow()

    db.commit()
    db.refresh(appointment)

    # Invalidate cache
    await redis_cache.delete(f"appointment:{appointment_id}:*")
    await redis_cache.delete(f"appointments:list:*")

    return _serialize_appointment(appointment)


@router.patch(
    "/{appointment_id}/complete",
    response_model=AppointmentV2Response,
    summary="Complete appointment",
    description="Mark appointment as completed and record completion time"
)
@limiter.limit("30/hour")
async def complete_appointment(
    request: Request,
    appointment_id: str,
    post_appointment_notes: Optional[str] = Query(None, description="Notes after appointment completion"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """
    Complete an appointment.

    Sets status to COMPLETED and records completion timestamp.
    Can only complete appointments in IN_PROGRESS status.
    Optionally add post-appointment notes.
    """
    try:
        appointment_uuid = UUID(appointment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid appointment ID format"
        )

    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_uuid
    ).first()

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with id {appointment_id} not found"
        )

    _ensure_appointment_access(current_user, appointment)

    # Can only complete in-progress appointments
    if appointment.status != AppointmentStatus.IN_PROGRESS.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot complete appointment with status {appointment.status}. Must be in_progress."
        )

    appointment.status = AppointmentStatus.COMPLETED.value
    appointment.completed_at = datetime.utcnow()

    if post_appointment_notes:
        appointment.post_appointment_notes = post_appointment_notes

    db.commit()
    db.refresh(appointment)

    # Invalidate cache
    await redis_cache.delete(f"appointment:{appointment_id}:*")
    await redis_cache.delete(f"appointments:list:*")

    return _serialize_appointment(appointment)


@router.delete(
    "/{appointment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete appointment",
    description="Delete an appointment (sets status to cancelled)"
)
@limiter.limit("10/hour")
async def delete_appointment(
    request: Request,
    appointment_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """
    Delete an appointment.

    This is a soft delete that sets the status to CANCELLED.
    """
    try:
        appointment_uuid = UUID(appointment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid appointment ID format"
        )

    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_uuid
    ).first()

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with id {appointment_id} not found"
        )

    _ensure_appointment_access(current_user, appointment)

    # Soft delete: set status to cancelled
    appointment.status = AppointmentStatus.CANCELLED.value
    appointment.cancelled_at = datetime.utcnow()

    db.commit()

    # Invalidate cache
    await redis_cache.delete(f"appointment:{appointment_id}:*")
    await redis_cache.delete(f"appointments:list:*")

    return None
