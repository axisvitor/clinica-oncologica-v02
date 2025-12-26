from typing import Optional, List
from datetime import date, datetime, timedelta, timezone
from uuid import UUID
import logging
import json
import base64
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import joinedload
from sqlalchemy import and_, func, or_

from app.database import get_db
from app.models.appointment import Appointment, AppointmentStatus, AppointmentType
from app.models.patient import Patient
from app.models.user import UserRole
from app.schemas.v2.appointment import (
    AppointmentV2Response,
    AppointmentV2List,
    AppointmentV2Create,
    AppointmentV2Update,
)
from app.api.v2.dependencies import (
    get_pagination_params,
    get_field_selection,
    get_eager_load_params,
    apply_field_selection,
)
from app.api.v2.patients_utils import (
    _get_current_user_simple,
    _extract_user_context,
    _ensure_uuid,
)
from app.api.v2.utils.auth_helpers import is_admin
from app.dependencies.auth_dependencies import (
    get_current_user_from_session,
    get_redis_cache,
)
from app.utils.rate_limiter import limiter

router = APIRouter()
logger = logging.getLogger(__name__)


def _is_admin(current_user) -> bool:
    """Check if current user is admin."""
    return is_admin(current_user)


def _ensure_appointment_access(current_user, appointment: Appointment):
    if _is_admin(current_user):
        return
    _, user_id = _extract_user_context(current_user)
    user_uuid = _ensure_uuid(user_id)
    if user_uuid is None or appointment.practitioner_id != user_uuid:
        raise HTTPException(status_code=403, detail="Not enough permissions")


def _serialize_appointment(appointment: Appointment) -> Optional[dict]:
    if appointment is None:
        return None
    status_value = (
        appointment.status.value
        if isinstance(appointment.status, AppointmentStatus)
        else appointment.status
    )
    type_value = (
        appointment.appointment_type.value
        if isinstance(appointment.appointment_type, AppointmentType)
        else appointment.appointment_type
    )

    return {
        "id": str(appointment.id),
        "patient_id": str(appointment.patient_id),
        "practitioner_id": str(appointment.practitioner_id)
        if appointment.practitioner_id
        else None,
        "appointment_type": type_value,
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


class ConflictCheckResponse(BaseModel):
    has_conflict: bool
    conflicting_appointments: List[dict] = []


@router.get("", response_model=AppointmentV2List, summary="List appointments")
async def list_appointments(
    db=Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    pagination=Depends(get_pagination_params),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    redis_cache=Depends(get_redis_cache),
    search: Optional[str] = Query(None),
    patient_id: Optional[str] = Query(None),
    practitioner_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    appointment_type: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
):
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    cache_key = f"appointments:list:{cursor_data}:{limit}:{search}:{patient_id}:{practitioner_id}:{status_filter}:{appointment_type}:{date_from}:{date_to}"
    try:
        cached = await redis_cache.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as cache_err:
        logger.debug(f"Cache read failed (non-critical): {cache_err}")

    query = db.query(Appointment)
    if include:
        if "patient" in include:
            query = query.options(joinedload(Appointment.patient))
        if "practitioner" in include:
            query = query.options(joinedload(Appointment.practitioner))

    filters = []
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    if role_enum != UserRole.ADMIN:
        if not current_user_uuid:
            raise HTTPException(status_code=403)
        filters.append(Appointment.practitioner_id == current_user_uuid)

    if cursor_data and "id" in cursor_data:
        cid = UUID(cursor_data["id"])
        cdate = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))
        filters.append(
            or_(
                Appointment.created_at < cdate,
                and_(Appointment.created_at == cdate, Appointment.id > cid),
            )
        )

    if search:
        query = query.join(Patient)
        filters.append(Patient.name.ilike(f"%{search}%"))

    if patient_id:
        try:
            filters.append(Appointment.patient_id == UUID(patient_id))
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400, detail="Invalid patient_id UUID format"
            )

    if practitioner_id:
        try:
            filters.append(Appointment.practitioner_id == UUID(practitioner_id))
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400, detail="Invalid practitioner_id UUID format"
            )

    if status_filter:
        try:
            filters.append(
                Appointment.status
                == AppointmentStatus(status_filter.strip().lower()).value
            )
        except (ValueError, KeyError):
            raise HTTPException(
                status_code=400, detail=f"Invalid status: {status_filter}"
            )

    if appointment_type:
        try:
            filters.append(
                Appointment.appointment_type
                == AppointmentType(appointment_type.strip().lower()).value
            )
        except (ValueError, KeyError):
            raise HTTPException(
                status_code=400, detail=f"Invalid appointment_type: {appointment_type}"
            )

    if date_from:
        filters.append(func.date(Appointment.scheduled_at) >= date_from)
    if date_to:
        filters.append(func.date(Appointment.scheduled_at) <= date_to)

    if filters:
        query = query.filter(and_(*filters))

    total = None
    if not cursor_data:
        tq = db.query(func.count(Appointment.id))
        if filters:
            tq = tq.filter(and_(*filters))
        total = tq.scalar()

    query = query.order_by(Appointment.created_at.desc(), Appointment.id)
    appointments = query.limit(limit + 1).all()

    has_more = len(appointments) > limit
    if has_more:
        appointments = appointments[:limit]

    next_cursor = None
    if has_more and appointments:
        cd = {
            "id": str(appointments[-1].id),
            "created_at": appointments[-1].created_at.isoformat(),
        }
        next_cursor = base64.b64encode(json.dumps(cd).encode()).decode()

    resp_data = []
    for appt in appointments:
        ad = _serialize_appointment(appt)
        if include:
            if "patient" in include and appt.patient:
                ad["patient"] = {
                    "id": str(appt.patient.id),
                    "name": appt.patient.name,
                    "email": appt.patient.email,
                    "phone": appt.patient.phone,
                }
            if "practitioner" in include and appt.practitioner:
                ad["practitioner"] = {
                    "id": str(appt.practitioner.id),
                    "name": appt.practitioner.full_name,
                    "email": appt.practitioner.email,
                }
        if fields:
            ad = apply_field_selection(ad, fields)
        resp_data.append(ad)

    result = {
        "data": resp_data,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
    }

    try:
        await redis_cache.set(cache_key, json.dumps(result, default=str), ttl=120)
    except Exception as cache_err:
        logger.debug(f"Cache write failed (non-critical): {cache_err}")

    return result


@router.get("/conflicts", response_model=ConflictCheckResponse)
async def check_conflicts(
    practitioner_id: str = Query(...),
    scheduled_at: datetime = Query(...),
    duration_minutes: int = Query(30, ge=15, le=480),
    exclude_appointment_id: Optional[str] = Query(None),
    db=Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    try:
        practitioner_uuid = UUID(practitioner_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400, detail="Invalid practitioner_id UUID format"
        )

    end_time = scheduled_at + timedelta(minutes=duration_minutes)

    from app.repositories.appointment import AppointmentRepository

    repo = AppointmentRepository(db)

    exclude_uuid = None
    if exclude_appointment_id:
        try:
            exclude_uuid = UUID(exclude_appointment_id)
        except (ValueError, TypeError):
            logger.debug(
                f"Invalid exclude_appointment_id, ignoring: {exclude_appointment_id}"
            )

    conflicts_list = repo.find_conflicts(
        practitioner_uuid, scheduled_at, end_time, exclude_uuid
    )

    conflicts = []
    for appt in conflicts_list:
        conflicts.append(
            {
                "id": str(appt.id),
                "patient_id": str(appt.patient_id),
                "scheduled_at": appt.scheduled_at.isoformat(),
                "duration_minutes": appt.duration_minutes,
                "status": appt.status,
            }
        )

    return {"has_conflict": len(conflicts) > 0, "conflicting_appointments": conflicts}


@router.get("/{appointment_id}", response_model=AppointmentV2Response)
async def get_appointment(
    appointment_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    redis_cache=Depends(get_redis_cache),
):
    try:
        aid = UUID(appointment_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400, detail="Invalid appointment_id UUID format"
        )

    query = db.query(Appointment)
    if include:
        if "patient" in include:
            query = query.options(joinedload(Appointment.patient))
        if "practitioner" in include:
            query = query.options(joinedload(Appointment.practitioner))

    appt = query.filter(Appointment.id == aid).first()
    if not appt:
        raise HTTPException(status_code=404)
    _ensure_appointment_access(current_user, appt)

    ad = _serialize_appointment(appt)
    if include:
        if "patient" in include and appt.patient:
            ad["patient"] = {
                "id": str(appt.patient.id),
                "name": appt.patient.name,
                "email": appt.patient.email,
                "phone": appt.patient.phone,
            }
        if "practitioner" in include and appt.practitioner:
            ad["practitioner"] = {
                "id": str(appt.practitioner.id),
                "name": appt.practitioner.full_name,
                "email": appt.practitioner.email,
            }
    if fields:
        ad = apply_field_selection(ad, fields)
    return ad


@router.post("", response_model=AppointmentV2Response, status_code=201)
@limiter.limit("30/hour")
async def create_appointment(
    request: Request,
    appointment_data: AppointmentV2Create,
    db=Depends(get_db),
    current_user=Depends(_get_current_user_simple),
    redis_cache=Depends(get_redis_cache),
):
    # Initialize Service
    from app.services.appointment_service import AppointmentService
    from app.repositories.appointment import AppointmentRepository

    repo = AppointmentRepository(db)
    service = AppointmentService(db, repo)

    # Validate basic existence
    try:
        UUID(appointment_data.patient_id)
        prid = (
            UUID(appointment_data.practitioner_id)
            if appointment_data.practitioner_id
            else None
        )
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400, detail="Invalid patient_id or practitioner_id UUID format"
        )

    # RBAC
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    if not prid:
        prid = current_user_uuid
        # Update input model if possible, or just pass to service
        # But AppointmentV2Create is immutable by default usually? No, Pydantic models.
        # Let's rely on Service to handle 'None' practitioner if logical, but service expects it in data?
        # Actually, I updated Service to handle None practitioner in data.practitioner_id
        # But wait, I manually set it in Service create_data.

    if role_enum != UserRole.ADMIN:
        if not current_user_uuid or (prid and current_user_uuid != prid):
            raise HTTPException(
                status_code=403, detail="Doctors can only create their own appointments"
            )

    # Ensure practitioner is set in data passed to service if implied
    if not appointment_data.practitioner_id and prid:
        appointment_data.practitioner_id = str(prid)

    try:
        new_appt = service.create_appointment(appointment_data)
    except ValueError as e:
        logger.warning(f"Appointment creation conflict: {e}")
        raise HTTPException(status_code=409, detail="Appointment scheduling conflict detected")
    except Exception as e:
        logger.error(f"Error creating appointment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create appointment")

    try:
        await redis_cache.delete("appointments:list:*")
    except Exception as cache_err:
        logger.debug(f"Cache invalidation failed (non-critical): {cache_err}")

    return _serialize_appointment(new_appt)


@router.patch("/{appointment_id}", response_model=AppointmentV2Response)
async def update_appointment(
    appointment_id: str,
    appointment_data: AppointmentV2Update,
    db=Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
):
    try:
        aid = UUID(appointment_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400, detail="Invalid appointment_id UUID format"
        )

    # Initialize Service
    from app.services.appointment_service import AppointmentService
    from app.repositories.appointment import AppointmentRepository

    repo = AppointmentRepository(db)
    service = AppointmentService(db, repo)

    appt = repo.get_by_id(aid)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    _ensure_appointment_access(current_user, appt)

    # Update via Service
    try:
        updated_appt = service.update_appointment(aid, appointment_data)
    except ValueError as e:
        logger.warning(f"Appointment update conflict: {e}")
        raise HTTPException(status_code=400, detail="Invalid appointment update or scheduling conflict")
    except Exception as e:
        logger.error(f"Error updating appointment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update appointment")

    try:
        await redis_cache.delete(f"appointment:{appointment_id}:*")
        await redis_cache.delete("appointments:list:*")
    except Exception as cache_err:
        logger.debug(f"Cache invalidation failed (non-critical): {cache_err}")

    return _serialize_appointment(updated_appt)


@router.patch("/{appointment_id}/cancel", response_model=AppointmentV2Response)
async def cancel_appointment(
    appointment_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    try:
        aid = UUID(appointment_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400, detail="Invalid appointment_id UUID format"
        )
    appt = db.query(Appointment).get(aid)
    if not appt:
        raise HTTPException(status_code=404)
    _ensure_appointment_access(current_user, appt)

    appt.status = AppointmentStatus.CANCELLED.value
    appt.cancelled_at = datetime.now(timezone.utc)
    db.commit()
    return _serialize_appointment(appt)


@router.patch("/{appointment_id}/complete", response_model=AppointmentV2Response)
async def complete_appointment(
    appointment_id: str,
    post_appointment_notes: Optional[str] = Query(None),
    db=Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    try:
        aid = UUID(appointment_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400, detail="Invalid appointment_id UUID format"
        )
    appt = db.query(Appointment).get(aid)
    if not appt:
        raise HTTPException(status_code=404)
    _ensure_appointment_access(current_user, appt)

    appt.status = AppointmentStatus.COMPLETED.value
    appt.completed_at = datetime.now(timezone.utc)
    if post_appointment_notes:
        appt.post_appointment_notes = post_appointment_notes
    db.commit()
    return _serialize_appointment(appt)


@router.delete("/{appointment_id}", status_code=204)
async def delete_appointment(
    appointment_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    try:
        aid = UUID(appointment_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400, detail="Invalid appointment_id UUID format"
        )
    appt = db.query(Appointment).get(aid)
    if not appt:
        raise HTTPException(status_code=404)
    _ensure_appointment_access(current_user, appt)
    db.delete(appt)
    db.commit()
    return None
