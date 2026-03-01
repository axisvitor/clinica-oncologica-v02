from typing import Optional, List, Dict
from datetime import datetime
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
from app.models.medication import Medication
from app.models.patient import Patient
from app.models.user import UserRole
from app.schemas.v2.medication import (
    MedicationV2Response,
    MedicationV2List,
    MedicationV2Create,
    MedicationV2Update,
)
from app.api.v2.dependencies import apply_field_selection
from app.api.v2.dependencies import get_eager_load_params
from app.api.v2.dependencies import get_field_selection
from app.api.v2.dependencies import get_pagination_params
from app.api.v2.patients_utils import _ensure_uuid
from app.api.v2.patients_utils import _extract_user_context
from app.api.v2.patients_utils import _get_current_user_simple
from app.utils.auth_helpers import is_admin
from app.dependencies.auth_dependencies import (
    get_current_user_from_session,
    get_redis_cache,
)
from app.utils.timezone import now_sao_paulo

router = APIRouter()
logger = logging.getLogger(__name__)


def _ensure_medication_access(
    current_user, medication_prescribed_by_id, patient_doctor_id
):
    if is_admin(current_user):
        return
    _, user_id = _extract_user_context(current_user)
    user_uuid = _ensure_uuid(user_id)
    if user_uuid is None:
        raise HTTPException(status_code=403, detail="No permissions")
    if user_uuid != medication_prescribed_by_id and user_uuid != patient_doctor_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")


async def _resolve_medication_for_mutation(
    *,
    medication_id: str,
    db: AsyncSession,
    current_user,
) -> tuple[UUID, Medication]:
    """Parse medication ID, load record and enforce RBAC for mutating operations."""
    try:
        mid = UUID(medication_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid medication_id UUID") from exc

    med_result = await db.execute(select(Medication).where(Medication.id == mid))
    med = med_result.scalar_one_or_none()
    if not med:
        raise HTTPException(status_code=404)

    patient_result = await db.execute(select(Patient).where(Patient.id == med.patient_id))
    patient = patient_result.scalar_one_or_none()
    if patient:
        _ensure_medication_access(current_user, med.prescribed_by_id, patient.doctor_id)

    return mid, med


def _serialize_medication(medication) -> Optional[dict]:
    if medication is None:
        return None
    return {
        "id": str(getattr(medication, "id")),
        "patient_id": str(getattr(medication, "patient_id")),
        "prescribed_by_id": str(getattr(medication, "prescribed_by_id"))
        if getattr(medication, "prescribed_by_id", None)
        else None,
        "treatment_id": str(getattr(medication, "treatment_id"))
        if getattr(medication, "treatment_id", None)
        else None,
        "name": getattr(medication, "name"),
        "active_ingredient": getattr(medication, "active_ingredient", None),
        "dosage": getattr(medication, "dosage"),
        "frequency": getattr(medication, "frequency"),
        "route": getattr(medication, "route", None),
        "prescription_date": getattr(medication, "prescription_date"),
        "start_date": getattr(medication, "start_date"),
        "end_date": getattr(medication, "end_date", None),
        "quantity": float(getattr(medication, "quantity"))
        if getattr(medication, "quantity", None)
        else None,
        "refills_allowed": getattr(medication, "refills_allowed", 0),
        "refills_remaining": getattr(medication, "refills_remaining", 0),
        "instructions": getattr(medication, "instructions", None),
        "warnings": getattr(medication, "warnings", None),
        "side_effects": getattr(medication, "side_effects", None),
        "is_active": getattr(medication, "is_active", True),
        "discontinued_date": getattr(medication, "discontinued_date", None),
        "discontinuation_reason": getattr(medication, "discontinuation_reason", None),
        "created_at": getattr(medication, "created_at", None),
        "updated_at": getattr(medication, "updated_at", None),
    }


class MedicationStatsResponse(BaseModel):
    total_medications: int
    active_medications: int
    discontinued_medications: int
    by_route: Dict[str, int]


@router.get("", response_model=MedicationV2List, summary="List medications")
async def list_medications(
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
    pagination=Depends(get_pagination_params),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    search: Optional[str] = Query(None),
    patient_id: Optional[str] = Query(None),
    prescribed_by_id: Optional[str] = Query(None),
    treatment_id: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    route: Optional[str] = Query(None),
):
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    role_enum, user_id = _extract_user_context(current_user)
    cache_key = f"medications:list:{user_id}:{cursor_data}:{limit}:{search}:{patient_id}:{prescribed_by_id}:{treatment_id}:{is_active}:{route}"

    try:
        cached = await redis_cache.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.debug(f"Cache read failed (non-critical): {e}")

    stmt = select(Medication)
    if include:
        if "patient" in include:
            stmt = stmt.options(selectinload(Medication.patient))
        if "prescribed_by" in include:
            stmt = stmt.options(selectinload(Medication.prescribed_by))
        if "treatment" in include:
            stmt = stmt.options(selectinload(Medication.treatment))

    filters = [Medication.deleted_at.is_(None)]
    current_user_uuid = _ensure_uuid(user_id)

    if role_enum != UserRole.ADMIN:
        if not current_user_uuid:
            raise HTTPException(status_code=403)
        filters.append(
            or_(
                Medication.prescribed_by_id == current_user_uuid,
                Medication.patient.has(Patient.doctor_id == current_user_uuid),
            )
        )

    if cursor_data and "id" in cursor_data:
        cid = UUID(cursor_data["id"])
        cdate = datetime.fromisoformat(cursor_data["created_at"])
        filters.append(
            or_(
                Medication.created_at < cdate,
                and_(Medication.created_at == cdate, Medication.id > cid),
            )
        )

    if search:
        filters.append(Medication.name.ilike(f"%{search}%"))
    if patient_id:
        try:
            filters.append(Medication.patient_id == UUID(patient_id))
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid patient_id UUID")
    if prescribed_by_id:
        try:
            filters.append(Medication.prescribed_by_id == UUID(prescribed_by_id))
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid prescribed_by_id UUID")
    if treatment_id:
        try:
            filters.append(Medication.treatment_id == UUID(treatment_id))
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid treatment_id UUID")
    if is_active is not None:
        filters.append(Medication.is_active == is_active)
    if route:
        filters.append(Medication.route.ilike(f"%{route.strip()}%"))

    stmt = stmt.where(and_(*filters))

    total = None
    if not cursor_data:
        count_result = await db.execute(
            select(func.count(Medication.id)).where(and_(*filters))
        )
        total = count_result.scalar()

    stmt = stmt.order_by(Medication.created_at.desc(), Medication.id)
    med_result = await db.execute(stmt.limit(limit + 1))
    medications = list(med_result.scalars().all())

    has_more = len(medications) > limit
    if has_more:
        medications = medications[:limit]

    next_cursor = None
    if has_more and medications:
        cd = {
            "id": str(medications[-1].id),
            "created_at": medications[-1].created_at.isoformat(),
        }
        import base64

        next_cursor = base64.b64encode(json.dumps(cd).encode()).decode()

    resp_data = []
    for m in medications:
        md = _serialize_medication(m)
        if include:
            if "patient" in include and m.patient:
                md["patient"] = {
                    "id": str(m.patient.id),
                    "name": m.patient.name,
                    "email": m.patient.email,
                }
            if "prescribed_by" in include and m.prescribed_by:
                md["prescribed_by"] = {
                    "id": str(m.prescribed_by.id),
                    "name": m.prescribed_by.full_name,
                    "email": m.prescribed_by.email,
                }
            if "treatment" in include and m.treatment:
                md["treatment"] = {
                    "id": str(m.treatment.id),
                    "treatment_type": m.treatment.treatment_type,
                    "status": m.treatment.status,
                    "start_date": m.treatment.start_date,
                }
        if fields:
            md = apply_field_selection(md, fields)
        resp_data.append(md)

    result = {
        "data": resp_data,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
    }
    try:
        await redis_cache.set(cache_key, json.dumps(result, default=str), ttl=300)
    except Exception as e:
        logger.debug(f"Cache write failed (non-critical): {e}")
    return result


@router.get("/active", response_model=MedicationV2List)
async def list_active_medications(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
    pagination=Depends(get_pagination_params),
    patient_id: Optional[str] = Query(None),
):
    # Reuse logic or simplified active query
    # For brevity, implementing similar logic:
    pagination["cursor_data"]
    limit = pagination["limit"]
    role_enum, user_id = _extract_user_context(current_user)

    filters = [Medication.deleted_at.is_(None), Medication.is_active]
    current_user_uuid = _ensure_uuid(user_id)

    if role_enum != UserRole.ADMIN:
        if not current_user_uuid:
            raise HTTPException(status_code=403)
        filters.append(
            or_(
                Medication.prescribed_by_id == current_user_uuid,
                Medication.patient.has(Patient.doctor_id == current_user_uuid),
            )
        )

    if patient_id:
        try:
            filters.append(Medication.patient_id == UUID(patient_id))
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid patient_id UUID")

    active_result = await db.execute(
        select(Medication)
        .where(and_(*filters))
        .order_by(Medication.created_at.desc(), Medication.id)
        .limit(limit + 1)
    )
    medications = list(active_result.scalars().all())

    has_more = len(medications) > limit
    if has_more:
        medications = medications[:limit]

    resp_data = [_serialize_medication(m) for m in medications]

    return {
        "data": resp_data,
        "has_more": has_more,
        "total": None,
        "next_cursor": None,
    }  # Simplified


@router.get("/search", response_model=List[MedicationV2Response])
async def search_medications(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
):
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)
    search_filters = [Medication.deleted_at.is_(None)]

    if role_enum != UserRole.ADMIN:
        if not current_user_uuid:
            raise HTTPException(status_code=403)
        search_filters.append(
            or_(
                Medication.prescribed_by_id == current_user_uuid,
                Medication.patient.has(Patient.doctor_id == current_user_uuid),
            )
        )

    search_filters.append(Medication.name.ilike(f"%{q}%"))
    search_result = await db.execute(
        select(Medication)
        .where(and_(*search_filters))
        .order_by(Medication.created_at.desc())
        .limit(limit)
    )
    medications = list(search_result.scalars().all())
    return [_serialize_medication(m) for m in medications]


@router.get("/{medication_id}", response_model=MedicationV2Response)
async def get_medication(
    medication_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
):
    try:
        mid = UUID(medication_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid medication_id UUID")

    get_stmt = select(Medication).where(
        Medication.id == mid, Medication.deleted_at.is_(None)
    )
    if include:
        if "patient" in include:
            get_stmt = get_stmt.options(selectinload(Medication.patient))
        if "prescribed_by" in include:
            get_stmt = get_stmt.options(selectinload(Medication.prescribed_by))
        if "treatment" in include:
            get_stmt = get_stmt.options(selectinload(Medication.treatment))

    med_get_result = await db.execute(get_stmt)
    medication = med_get_result.scalar_one_or_none()
    if not medication:
        raise HTTPException(status_code=404)

    patient_get_result = await db.execute(
        select(Patient).where(Patient.id == medication.patient_id)
    )
    patient = patient_get_result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404)
    _ensure_medication_access(
        current_user, medication.prescribed_by_id, patient.doctor_id
    )

    md = _serialize_medication(medication)
    if fields:
        md = apply_field_selection(md, fields)
    return md


@router.post("", response_model=MedicationV2Response, status_code=201)
async def create_medication(
    medication_data: MedicationV2Create,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(_get_current_user_simple),
    redis_cache=Depends(get_redis_cache),
):
    try:
        pid = UUID(medication_data.patient_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid patient_id UUID")

    # RBAC and Existence checks (Simplified for brevity, assuming Service or Repo helps, but permissions are critical here)
    # Ideally move RBAC to dependency or service decorator
    create_patient_result = await db.execute(select(Patient).where(Patient.id == pid))
    patient = create_patient_result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404)

    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)
    if role_enum != UserRole.ADMIN:
        if not current_user_uuid or current_user_uuid != patient.doctor_id:
            raise HTTPException(status_code=403)

    prescribed_by = current_user_uuid
    if medication_data.prescribed_by_id:
        try:
            prescribed_by = UUID(medication_data.prescribed_by_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid prescribed_by_id UUID")

    tid = None
    if medication_data.treatment_id:
        try:
            tid = UUID(medication_data.treatment_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid treatment_id UUID")

    try:
        create_data = medication_data.model_dump(
            exclude={"patient_id", "prescribed_by_id", "treatment_id"}
        )
        new_med = Medication(
            **create_data,
            patient_id=pid,
            prescribed_by_id=prescribed_by,
            treatment_id=tid,
        )
        db.add(new_med)
        await db.commit()
        await db.refresh(new_med)
    except Exception as e:
        logger.error(f"Error creating medication: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create medication")

    try:
        await redis_cache.delete_pattern(f"medications:list:{user_id}:*")
    except Exception as e:
        logger.debug(f"Cache invalidation failed (non-critical): {e}")

    return _serialize_medication(new_med)


@router.patch("/{medication_id}", response_model=MedicationV2Response)
async def update_medication(
    medication_id: str,
    medication_data: MedicationV2Update,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
):
    mid, _ = await _resolve_medication_for_mutation(
        medication_id=medication_id,
        db=db,
        current_user=current_user,
    )

    try:
        med_result = await db.execute(select(Medication).where(Medication.id == mid))
        updated = med_result.scalar_one_or_none()
        if not updated:
            raise HTTPException(status_code=404)

        update_data = medication_data.model_dump(exclude_unset=True)
        if "prescribed_by_id" in update_data and update_data["prescribed_by_id"]:
            update_data["prescribed_by_id"] = UUID(update_data["prescribed_by_id"])
        if "treatment_id" in update_data and update_data["treatment_id"]:
            update_data["treatment_id"] = UUID(update_data["treatment_id"])

        for key, value in update_data.items():
            setattr(updated, key, value)

        await db.commit()
        await db.refresh(updated)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating medication: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update medication")

    try:
        await redis_cache.delete(f"medication:{medication_id}:*")
    except Exception as e:
        logger.debug(f"Cache delete failed (non-critical): {e}")
    return _serialize_medication(updated)


@router.delete("/{medication_id}", status_code=204)
async def delete_medication(
    medication_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
):
    _, medication = await _resolve_medication_for_mutation(
        medication_id=medication_id,
        db=db,
        current_user=current_user,
    )

    try:
        medication.is_active = False
        medication.deleted_at = now_sao_paulo()
        await db.commit()
    except Exception as e:
        logger.error(f"Error deleting medication: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete medication")

    return None
