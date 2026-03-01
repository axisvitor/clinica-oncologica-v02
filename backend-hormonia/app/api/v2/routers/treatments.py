from typing import Optional, List, Dict
from datetime import date, datetime
from uuid import UUID
import logging
import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import and_, func, or_

from app.core.database.async_engine import get_async_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.treatment import Treatment, TreatmentStatus, TreatmentType
from app.models.patient import Patient
from app.models.user import UserRole
from app.schemas.v2.treatment import (
    TreatmentV2Response,
    TreatmentV2List,
    TreatmentV2Create,
    TreatmentV2Update,
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
from app.utils.auth_helpers import is_admin
from app.dependencies.auth_dependencies import (
    get_current_user_from_session,
    get_redis_cache,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _ensure_treatment_access(current_user, doctor_id):
    if is_admin(current_user):
        return
    _, user_id = _extract_user_context(current_user)
    user_uuid = _ensure_uuid(user_id)
    if user_uuid is None or doctor_id != user_uuid:
        raise HTTPException(status_code=403, detail="Not enough permissions")


def _serialize_treatment(treatment) -> Optional[dict]:
    if treatment is None:
        return None
    status_val = (
        treatment.status.value
        if isinstance(treatment.status, TreatmentStatus)
        else treatment.status
    )
    type_val = (
        treatment.treatment_type.value
        if isinstance(treatment.treatment_type, TreatmentType)
        else treatment.treatment_type
    )

    return {
        "id": str(treatment.id),
        "patient_id": str(treatment.patient_id) if treatment.patient_id else None,
        "doctor_id": str(treatment.doctor_id) if treatment.doctor_id else None,
        "treatment_type": type_val,
        "status": status_val,
        "start_date": treatment.start_date,
        "end_date": treatment.end_date,
        "planned_sessions": treatment.planned_sessions,
        "completed_sessions": treatment.completed_sessions,
        "diagnosis": treatment.diagnosis,
        "protocol": treatment.protocol,
        "notes": treatment.notes,
        "is_active": getattr(treatment, "is_active", True),
        "created_at": treatment.created_at,
        "updated_at": treatment.updated_at,
    }


class TreatmentStatsResponse(BaseModel):
    total_treatments: int
    active_treatments: int
    completed_treatments: int
    planned_treatments: int
    by_status: Dict[str, int]
    by_type: Dict[str, int]
    completion_rate: float


@router.get("", response_model=TreatmentV2List, summary="List treatments")
async def list_treatments(
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
    pagination=Depends(get_pagination_params),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    search: Optional[str] = Query(None),
    patient_id: Optional[str] = Query(None),
    doctor_id: Optional[str] = Query(None),
    treatment_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    start_date_from: Optional[date] = Query(None),
    start_date_to: Optional[date] = Query(None),
):
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    # Simplified cache key for brevity
    cache_key = f"treatments:list:{_extract_user_context(current_user)[1]}:{patient_id}:{doctor_id}:{treatment_type}:{status_filter}:{limit}:{cursor_data}"
    try:
        cached = await redis_cache.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.debug(f"Cache read failed (non-critical): {e}")

    stmt = select(Treatment)
    if include:
        if "patient" in include:
            stmt = stmt.options(selectinload(Treatment.patient))
        if "doctor" in include:
            stmt = stmt.options(selectinload(Treatment.doctor))
        if "medications" in include:
            stmt = stmt.options(selectinload(Treatment.medications))

    filters = [Treatment.is_active]
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    if role_enum != UserRole.ADMIN:
        if not current_user_uuid:
            raise HTTPException(status_code=403)
        filters.append(Treatment.doctor_id == current_user_uuid)

    if cursor_data and "id" in cursor_data:
        cid = UUID(cursor_data["id"])
        cdate = datetime.fromisoformat(cursor_data["created_at"])
        filters.append(
            or_(
                Treatment.created_at < cdate,
                and_(Treatment.created_at == cdate, Treatment.id > cid),
            )
        )

    if search:
        stmt = stmt.join(Patient)
        filters.append(Patient.name.ilike(f"%{search}%"))

    if patient_id:
        try:
            filters.append(Treatment.patient_id == UUID(patient_id))
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid patient_id UUID")

    if doctor_id:
        if role_enum != UserRole.ADMIN:
            raise HTTPException(status_code=403)
        try:
            filters.append(Treatment.doctor_id == UUID(doctor_id))
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid doctor_id UUID")

    if treatment_type:
        try:
            filters.append(
                Treatment.treatment_type == TreatmentType(treatment_type.lower())
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid treatment_type")

    if status_filter:
        try:
            filters.append(Treatment.status == TreatmentStatus(status_filter.lower()))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")

    if start_date_from:
        filters.append(Treatment.start_date >= start_date_from)
    if start_date_to:
        filters.append(Treatment.start_date <= start_date_to)

    stmt = stmt.where(and_(*filters))

    total = None
    if not cursor_data:
        count_stmt = select(func.count(Treatment.id)).where(and_(*filters))
        total_result = await db.execute(count_stmt)
        total = total_result.scalar()

    stmt = stmt.order_by(Treatment.created_at.desc(), Treatment.id)
    treatments_result = await db.execute(stmt.limit(limit + 1))
    treatments = list(treatments_result.scalars().all())

    has_more = len(treatments) > limit
    if has_more:
        treatments = treatments[:limit]

    next_cursor = None
    if has_more and treatments:
        cd = {
            "id": str(treatments[-1].id),
            "created_at": treatments[-1].created_at.isoformat(),
        }
        import base64

        next_cursor = base64.b64encode(json.dumps(cd).encode()).decode()

    resp_data = []
    for t in treatments:
        td = _serialize_treatment(t)
        if include:
            if "patient" in include and t.patient:
                td["patient"] = {
                    "id": str(t.patient.id),
                    "name": t.patient.name,
                    "email": t.patient.email,
                }
            if "doctor" in include and t.doctor:
                td["doctor"] = {
                    "id": str(t.doctor.id),
                    "name": t.doctor.full_name,
                    "email": t.doctor.email,
                }
            if "medications" in include and hasattr(t, "medications"):
                td["medications"] = [
                    {"id": str(m.id), "name": m.name, "dosage": m.dosage}
                    for m in t.medications
                ]
        if fields:
            td = apply_field_selection(td, fields)
        resp_data.append(td)

    result = {
        "data": resp_data,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
    }
    try:
        await redis_cache.set(cache_key, json.dumps(result, default=str), ttl=120)
    except Exception as e:
        logger.debug(f"Cache write failed (non-critical): {e}")
    return result


@router.get("/statistics", response_model=TreatmentStatsResponse)
async def get_treatment_statistics(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
):
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    base_filters = [Treatment.is_active]
    if role_enum != UserRole.ADMIN:
        if not current_user_uuid:
            raise HTTPException(status_code=403)
        base_filters.append(Treatment.doctor_id == current_user_uuid)

    async def _count(extra_filter=None):
        f = list(base_filters)
        if extra_filter is not None:
            f.append(extra_filter)
        res = await db.execute(
            select(func.count(Treatment.id)).where(and_(*f))
        )
        return res.scalar() or 0

    total = await _count()
    active = await _count(Treatment.status == TreatmentStatus.ACTIVE)
    completed = await _count(Treatment.status == TreatmentStatus.COMPLETED)
    planned = await _count(Treatment.status == TreatmentStatus.PLANNED)

    rate = round((completed / total) * 100, 2) if total > 0 else 0.0

    by_status = {}
    for s in TreatmentStatus:
        by_status[s.value] = await _count(Treatment.status == s)

    by_type = {}
    for t in TreatmentType:
        by_type[t.value] = await _count(Treatment.treatment_type == t)

    return {
        "total_treatments": total,
        "active_treatments": active,
        "completed_treatments": completed,
        "planned_treatments": planned,
        "by_status": by_status,
        "by_type": by_type,
        "completion_rate": rate,
    }


@router.get("/{treatment_id}", response_model=TreatmentV2Response)
async def get_treatment(
    treatment_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
):
    try:
        tid = UUID(treatment_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid treatment_id UUID")

    get_stmt = select(Treatment).where(Treatment.id == tid, Treatment.is_active)
    if include:
        if "patient" in include:
            get_stmt = get_stmt.options(selectinload(Treatment.patient))
        if "doctor" in include:
            get_stmt = get_stmt.options(selectinload(Treatment.doctor))
        if "medications" in include:
            get_stmt = get_stmt.options(selectinload(Treatment.medications))

    treatment_get_result = await db.execute(get_stmt)
    treatment = treatment_get_result.scalar_one_or_none()
    if not treatment:
        raise HTTPException(status_code=404)
    _ensure_treatment_access(current_user, treatment.doctor_id)

    td = _serialize_treatment(treatment)
    # Add include data logic similar to list...
    # Simplified for brevity
    if fields:
        td = apply_field_selection(td, fields)
    return td


@router.post("", response_model=TreatmentV2Response, status_code=201)
async def create_treatment(
    treatment_data: TreatmentV2Create,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(_get_current_user_simple),
    redis_cache=Depends(get_redis_cache),
):
    try:
        pid = UUID(treatment_data.patient_id)
        did = UUID(treatment_data.doctor_id) if treatment_data.doctor_id else None
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid UUID")

    # Verify Patient (Service could do this if we move it)
    create_patient_result = await db.execute(select(Patient).where(Patient.id == pid))
    patient = create_patient_result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)
    if not did:
        did = current_user_uuid

    if role_enum != UserRole.ADMIN:
        if not current_user_uuid or current_user_uuid != did:
            raise HTTPException(status_code=403, detail="Permissions")

    try:
        create_data = treatment_data.model_dump(exclude={"treatment_type", "status"})
        create_data["patient_id"] = pid
        create_data["doctor_id"] = did
        create_data["treatment_type"] = TreatmentType(treatment_data.treatment_type.lower())
        if treatment_data.status:
            create_data["status"] = TreatmentStatus(treatment_data.status.lower())
        else:
            create_data["status"] = TreatmentStatus.PLANNED

        new_treatment = Treatment(**create_data)
        db.add(new_treatment)
        await db.commit()
        await db.refresh(new_treatment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error creating treatment: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create treatment")

    try:
        await redis_cache.delete_pattern(f"treatments:list:{user_id}:*")
    except Exception as e:
        logger.debug(f"Cache invalidation failed (non-critical): {e}")

    return _serialize_treatment(new_treatment)


@router.patch("/{treatment_id}", response_model=TreatmentV2Response)
async def update_treatment(
    treatment_id: str,
    treatment_data: TreatmentV2Update,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
):
    try:
        tid = UUID(treatment_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid treatment_id UUID")

    treatment_result = await db.execute(select(Treatment).where(Treatment.id == tid))
    t = treatment_result.scalar_one_or_none()
    if not t or not t.is_active:
        raise HTTPException(status_code=404)
    _ensure_treatment_access(current_user, t.doctor_id)

    try:
        update_data = treatment_data.model_dump(exclude_unset=True)
        if "doctor_id" in update_data and update_data["doctor_id"]:
            update_data["doctor_id"] = UUID(update_data["doctor_id"])
        if "treatment_type" in update_data:
            update_data["treatment_type"] = TreatmentType(
                update_data["treatment_type"].lower()
            )
        if "status" in update_data:
            update_data["status"] = TreatmentStatus(update_data["status"].lower())

        for key, value in update_data.items():
            setattr(t, key, value)

        await db.commit()
        await db.refresh(t)
        updated = t
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error updating treatment: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update treatment")

    try:
        await redis_cache.delete(f"treatment:{treatment_id}")
    except Exception as e:
        logger.debug(f"Cache delete failed (non-critical): {e}")
    return _serialize_treatment(updated)


@router.delete("/{treatment_id}", status_code=204)
async def delete_treatment(
    treatment_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
):
    try:
        tid = UUID(treatment_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid treatment_id UUID")

    treatment_result = await db.execute(select(Treatment).where(Treatment.id == tid))
    t = treatment_result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404)
    _ensure_treatment_access(current_user, t.doctor_id)

    try:
        t.is_active = False
        t.status = TreatmentStatus.CANCELLED
        await db.commit()
    except Exception as e:
        logger.error(f"Error deleting treatment: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500)

    return None


@router.patch("/{treatment_id}/activate", response_model=TreatmentV2Response)
async def activate_treatment(
    treatment_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
):
    try:
        tid = UUID(treatment_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid treatment_id UUID")

    treatment_result = await db.execute(select(Treatment).where(Treatment.id == tid))
    t = treatment_result.scalar_one_or_none()
    if not t or not t.is_active:
        raise HTTPException(status_code=404)
    _ensure_treatment_access(current_user, t.doctor_id)

    try:
        t.status = TreatmentStatus.ACTIVE
        await db.commit()
        await db.refresh(t)
        updated = t
    except Exception as e:
        logger.error(f"Error activating treatment: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to activate treatment")

    return _serialize_treatment(updated)
