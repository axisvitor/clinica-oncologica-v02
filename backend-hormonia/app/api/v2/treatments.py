"""
Treatments API v2
Enhanced treatment endpoints with cursor pagination, field selection, and eager loading.
"""

from typing import Optional, List, Tuple, Dict
from datetime import date, datetime
from uuid import UUID
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, or_

from app.database import get_db
from app.models.treatment import Treatment, TreatmentStatus, TreatmentType
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.schemas.v2.treatment import (
    TreatmentV2Response,
    TreatmentV2List,
    TreatmentV2Create,
    TreatmentV2Update,
)
from app.schemas.v2.common import ErrorResponse
from .dependencies import (
    get_pagination_params,
    get_field_selection,
    get_eager_load_params,
    create_cursor,
    apply_field_selection,
)
from app.dependencies.auth_dependencies import get_current_user_from_session, get_redis_cache
from app.utils.rate_limiter import limiter
from fastapi import Cookie, Header

router = APIRouter()
logger = logging.getLogger(__name__)


async def _get_current_user_simple(
    session_cookie_id: str = Cookie(None, alias="session_id"),
    x_session_id: str = Header(None, alias="X-Session-ID"),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache)
):
    """Simplified session validation without ServiceProvider."""
    final_session_id = session_cookie_id or x_session_id
    if not final_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID not provided"
        )

    session_data = await redis_cache.get_session(final_session_id)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )

    firebase_uid = session_data.get("firebase_uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session data"
        )

    # Get user from cache or DB
    user_data = await redis_cache.get_user_by_uid(firebase_uid)
    if not user_data:
        # Query DB directly
        user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        user_data = {
            "id": str(user.id),
            "firebase_uid": user.firebase_uid,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
            "is_active": user.is_active
        }
        await redis_cache.cache_user_data(firebase_uid, user_data, ttl=900)

    if not user_data.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    return user_data


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


def _ensure_treatment_access(current_user, treatment_doctor_id):
    """Ensure user has access to this treatment."""
    if _is_admin(current_user):
        return

    _, user_id = _extract_user_context(current_user)
    user_uuid = _ensure_uuid(user_id)

    if user_uuid is None or treatment_doctor_id != user_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this treatment",
        )


def _serialize_treatment(treatment) -> Optional[dict]:
    """Serialize Treatment SQLAlchemy model to API-friendly dict."""
    if treatment is None:
        return None

    status_value = getattr(treatment, "status", None)
    if isinstance(status_value, TreatmentStatus):
        status_value = status_value.value

    treatment_type_value = getattr(treatment, "treatment_type", None)
    if isinstance(treatment_type_value, TreatmentType):
        treatment_type_value = treatment_type_value.value

    created_at = getattr(treatment, "created_at", None)
    updated_at = getattr(treatment, "updated_at", None)

    return {
        "id": str(getattr(treatment, "id")),
        "patient_id": str(getattr(treatment, "patient_id")) if getattr(treatment, "patient_id", None) else None,
        "doctor_id": str(getattr(treatment, "doctor_id")) if getattr(treatment, "doctor_id", None) else None,
        "treatment_type": treatment_type_value,
        "status": status_value,
        "start_date": getattr(treatment, "start_date", None),
        "end_date": getattr(treatment, "end_date", None),
        "planned_sessions": getattr(treatment, "planned_sessions", None),
        "completed_sessions": getattr(treatment, "completed_sessions", None),
        "diagnosis": getattr(treatment, "diagnosis", None),
        "protocol": getattr(treatment, "protocol", None),
        "notes": getattr(treatment, "notes", None),
        "is_active": getattr(treatment, "is_active", True),
        "created_at": created_at,
        "updated_at": updated_at,
    }


class TreatmentStatsResponse(BaseModel):
    total_treatments: int
    active_treatments: int
    completed_treatments: int
    planned_treatments: int
    by_status: Dict[str, int]
    by_type: Dict[str, int]
    completion_rate: float


@router.get(
    "",
    response_model=TreatmentV2List,
    summary="List treatments with pagination",
    description="Get paginated list of treatments with optional field selection and eager loading"
)
async def list_treatments(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
    pagination = Depends(get_pagination_params),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    search: Optional[str] = Query(None, description="Search by patient name"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    doctor_id: Optional[str] = Query(None, description="Filter by doctor ID (ADMIN only)"),
    treatment_type: Optional[str] = Query(None, description="Filter by treatment type"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by treatment status"),
    start_date_from: Optional[date] = Query(None, description="Filter treatments starting on or after this date"),
    start_date_to: Optional[date] = Query(None, description="Filter treatments starting on or before this date"),
):
    """
    List treatments with cursor-based pagination.

    Features:
    - Cursor-based pagination (efficient for large datasets)
    - Field selection (?fields=id,treatment_type,status)
    - Eager loading (?include=patient,doctor,medications)
    - Search by patient name
    - Filter by patient_id, doctor_id, treatment_type, status, date_range

    Example:
        GET /api/v2/treatments?limit=20&fields=id,treatment_type,status&include=patient
    """
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    # Check Redis cache for list
    cache_key = f"treatments:list:{current_user.get('id') if isinstance(current_user, dict) else current_user.id}:{patient_id}:{doctor_id}:{treatment_type}:{status_filter}:{start_date_from}:{start_date_to}:{search}:{cursor_data}:{limit}"
    cached_result = await redis_cache.get(cache_key)
    if cached_result:
        logger.info(f"Cache HIT for treatments list: {cache_key}")
        return cached_result

    # Build base query
    query = db.query(Treatment)

    # Apply eager loading
    if include:
        if "patient" in include:
            query = query.options(joinedload(Treatment.patient))
        if "doctor" in include:
            query = query.options(joinedload(Treatment.doctor))
        if "medications" in include:
            query = query.options(joinedload(Treatment.medications))

    # Apply filters
    filters = []
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    # Filter active treatments by default (is_active=True)
    filters.append(Treatment.is_active == True)

    # RBAC: Non-admin users can only see their own treatments
    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to determine user permissions",
            )
        filters.append(Treatment.doctor_id == current_user_uuid)

    if cursor_data and "id" in cursor_data:
        # Handle UUID comparison
        from datetime import datetime as dt
        cursor_id = UUID(cursor_data["id"]) if isinstance(cursor_data["id"], str) else cursor_data["id"]
        cursor_created_at = dt.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))

        # For descending order
        filters.append(
            (Treatment.created_at < cursor_created_at) |
            ((Treatment.created_at == cursor_created_at) & (Treatment.id > cursor_id))
        )

    # Search by patient name
    if search:
        query = query.join(Patient, Treatment.patient_id == Patient.id)
        search_filter = f"%{search}%"
        filters.append(Patient.name.ilike(search_filter))

    # Filter by patient_id
    if patient_id:
        patient_uuid = _ensure_uuid(patient_id)
        if patient_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid patient ID format"
            )
        filters.append(Treatment.patient_id == patient_uuid)

    # Filter by doctor_id (admin only)
    if doctor_id:
        if role_enum != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can filter by doctor_id"
            )
        doctor_uuid = _ensure_uuid(doctor_id)
        if doctor_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid doctor ID format"
            )
        filters.append(Treatment.doctor_id == doctor_uuid)

    # Filter by treatment_type
    if treatment_type:
        try:
            treatment_type_enum = TreatmentType(treatment_type.lower())
            filters.append(Treatment.treatment_type == treatment_type_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid treatment type. Valid types: {', '.join([t.value for t in TreatmentType])}"
            )

    # Filter by status
    if status_filter:
        try:
            status_enum = TreatmentStatus(status_filter.lower())
            filters.append(Treatment.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Valid statuses: {', '.join([s.value for s in TreatmentStatus])}"
            )

    # Filter by date range
    if start_date_from:
        filters.append(Treatment.start_date >= start_date_from)

    if start_date_to:
        filters.append(Treatment.start_date <= start_date_to)

    if filters:
        query = query.filter(and_(*filters))

    # Get total count (only on first page)
    total = None
    if not cursor_data:
        total_query = db.query(func.count(Treatment.id))
        if filters:
            total_query = total_query.filter(and_(*filters))
        total = total_query.scalar()

    # Order and limit
    query = query.order_by(Treatment.created_at.desc(), Treatment.id)
    treatments = query.limit(limit + 1).all()

    # Check if there are more results
    has_more = len(treatments) > limit
    if has_more:
        treatments = treatments[:limit]

    # Create next cursor
    next_cursor = None
    if has_more and treatments:
        import json
        import base64
        cursor_data = {
            "id": str(treatments[-1].id),
            "created_at": treatments[-1].created_at.isoformat()
        }
        next_cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()

    # Convert to response models
    treatment_responses = []
    for treatment in treatments:
        treatment_dict = _serialize_treatment(treatment)

        # Add eager-loaded relationships
        if include:
            if "patient" in include and treatment.patient:
                treatment_dict["patient"] = {
                    "id": str(treatment.patient.id),
                    "name": treatment.patient.name,
                    "email": treatment.patient.email,
                }
            if "doctor" in include and treatment.doctor:
                treatment_dict["doctor"] = {
                    "id": str(treatment.doctor.id),
                    "name": treatment.doctor.full_name,
                    "email": treatment.doctor.email,
                }
            if "medications" in include and hasattr(treatment, "medications"):
                treatment_dict["medications"] = [
                    {
                        "id": str(m.id),
                        "name": m.name,
                        "dosage": m.dosage,
                        "frequency": m.frequency,
                        "is_active": m.is_active,
                    }
                    for m in treatment.medications
                ]

        # Apply field selection
        if fields:
            treatment_dict = apply_field_selection(treatment_dict, fields)

        treatment_responses.append(treatment_dict)

    result = {
        "data": treatment_responses,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
    }

    # Cache the result for 5 minutes
    await redis_cache.set(cache_key, result, ttl=300)

    return result


@router.get(
    "/statistics",
    response_model=TreatmentStatsResponse,
    summary="Get treatment statistics",
    description="Get treatment statistics including active, completed, and completion rate"
)
@limiter.limit("30/minute")
async def get_treatment_statistics(
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """
    Get treatment statistics.

    Returns:
    - Total treatments
    - Active treatments
    - Completed treatments
    - Planned treatments
    - Breakdown by status
    - Breakdown by type
    - Completion rate
    """
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    # Check cache
    cache_key = f"treatments:stats:{user_id}"
    cached_stats = await redis_cache.get(cache_key)
    if cached_stats:
        return cached_stats

    base_query = db.query(Treatment).filter(Treatment.is_active == True)

    # RBAC: Non-admin users can only see their own treatments
    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to determine user permissions",
            )
        base_query = base_query.filter(Treatment.doctor_id == current_user_uuid)

    total_treatments = base_query.count()
    active_treatments = base_query.filter(Treatment.status == TreatmentStatus.ACTIVE).count()
    completed_treatments = base_query.filter(Treatment.status == TreatmentStatus.COMPLETED).count()
    planned_treatments = base_query.filter(Treatment.status == TreatmentStatus.PLANNED).count()

    # Calculate completion rate
    completion_rate = 0.0
    if total_treatments > 0:
        completion_rate = round((completed_treatments / total_treatments) * 100, 2)

    # Breakdown by status
    by_status: Dict[str, int] = {}
    for status in TreatmentStatus:
        by_status[status.value] = base_query.filter(Treatment.status == status).count()

    # Breakdown by type
    by_type: Dict[str, int] = {}
    for treatment_type in TreatmentType:
        by_type[treatment_type.value] = base_query.filter(Treatment.treatment_type == treatment_type).count()

    stats = TreatmentStatsResponse(
        total_treatments=total_treatments,
        active_treatments=active_treatments,
        completed_treatments=completed_treatments,
        planned_treatments=planned_treatments,
        by_status=by_status,
        by_type=by_type,
        completion_rate=completion_rate,
    )

    # Cache for 5 minutes
    await redis_cache.set(cache_key, stats.dict(), ttl=300)

    return stats


@router.get(
    "/{treatment_id}",
    response_model=TreatmentV2Response,
    summary="Get treatment by ID",
    description="Get a single treatment with optional field selection and eager loading"
)
async def get_treatment(
    treatment_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
):
    """
    Get a single treatment by ID.

    Features:
    - Field selection (?fields=id,treatment_type,status)
    - Eager loading (?include=patient,doctor,medications)
    - Redis caching

    Example:
        GET /api/v2/treatments/123e4567-e89b-12d3-a456-426614174000?fields=id,treatment_type,status&include=patient
    """
    try:
        treatment_uuid = UUID(treatment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid treatment ID format"
        )

    # Check cache
    cache_key = f"treatment:{treatment_id}"
    cached_treatment = await redis_cache.get(cache_key)
    if cached_treatment:
        logger.info(f"Cache HIT for treatment: {treatment_id}")
        # Apply field selection if needed
        if fields:
            cached_treatment = apply_field_selection(cached_treatment, fields)
        return cached_treatment

    query = db.query(Treatment)

    # Apply eager loading
    if include:
        if "patient" in include:
            query = query.options(joinedload(Treatment.patient))
        if "doctor" in include:
            query = query.options(joinedload(Treatment.doctor))
        if "medications" in include:
            query = query.options(joinedload(Treatment.medications))

    treatment = query.filter(
        Treatment.id == treatment_uuid,
        Treatment.is_active == True
    ).first()

    if not treatment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Treatment with id {treatment_id} not found"
        )

    _ensure_treatment_access(current_user, treatment.doctor_id)

    # Build response
    treatment_dict = _serialize_treatment(treatment)

    # Add eager-loaded relationships
    if include:
        if "patient" in include and treatment.patient:
            treatment_dict["patient"] = {
                "id": str(treatment.patient.id),
                "name": treatment.patient.name,
                "email": treatment.patient.email,
            }
        if "doctor" in include and treatment.doctor:
            treatment_dict["doctor"] = {
                "id": str(treatment.doctor.id),
                "name": treatment.doctor.full_name,
                "email": treatment.doctor.email,
            }
        if "medications" in include and hasattr(treatment, "medications"):
            treatment_dict["medications"] = [
                {
                    "id": str(m.id),
                    "name": m.name,
                    "dosage": m.dosage,
                    "frequency": m.frequency,
                    "is_active": m.is_active,
                }
                for m in treatment.medications
            ]

    # Cache for 10 minutes
    await redis_cache.set(cache_key, treatment_dict, ttl=600)

    # Apply field selection
    if fields:
        treatment_dict = apply_field_selection(treatment_dict, fields)

    return treatment_dict


@router.post(
    "",
    response_model=TreatmentV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Create new treatment",
    description="Create a new treatment record (ADMIN/DOCTOR only)"
)
@limiter.limit("20/hour")
async def create_treatment(
    request: Request,
    treatment_data: TreatmentV2Create,
    db: Session = Depends(get_db),
    current_user = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache),
):
    """
    Create a new treatment.

    Validates:
    - Patient exists
    - Doctor exists (if provided)
    - Treatment type is valid
    - Status is valid
    - Dates are valid
    """
    # Validate patient_id
    try:
        patient_uuid = UUID(treatment_data.patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format"
        )

    # Check if patient exists
    patient = db.query(Patient).filter(Patient.id == patient_uuid).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with id {treatment_data.patient_id} not found"
        )

    # Validate doctor_id (optional)
    doctor_uuid = None
    if treatment_data.doctor_id:
        try:
            doctor_uuid = UUID(treatment_data.doctor_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid doctor ID format"
            )

        doctor = db.query(User).filter(User.id == doctor_uuid).first()
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Doctor with id {treatment_data.doctor_id} not found"
            )
    else:
        # Use current user as doctor
        role_enum, user_id = _extract_user_context(current_user)
        doctor_uuid = _ensure_uuid(user_id)

    # RBAC: Non-admin doctors can only create treatments for themselves
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)
    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None or current_user_uuid != doctor_uuid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Doctors can only create treatments for themselves"
            )

    # Validate treatment_type enum
    try:
        treatment_type_enum = TreatmentType(treatment_data.treatment_type.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid treatment type. Valid types: {', '.join([t.value for t in TreatmentType])}"
        )

    # Validate status enum
    try:
        status_enum = TreatmentStatus(treatment_data.status.lower() if treatment_data.status else "planned")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Valid statuses: {', '.join([s.value for s in TreatmentStatus])}"
        )

    # Create treatment
    new_treatment = Treatment(
        patient_id=patient_uuid,
        doctor_id=doctor_uuid,
        treatment_type=treatment_type_enum,
        status=status_enum,
        start_date=treatment_data.start_date,
        end_date=treatment_data.end_date,
        planned_sessions=treatment_data.planned_sessions,
        completed_sessions=treatment_data.completed_sessions,
        diagnosis=treatment_data.diagnosis,
        protocol=treatment_data.protocol,
        notes=treatment_data.notes,
        is_active=treatment_data.is_active,
    )

    db.add(new_treatment)
    db.commit()
    db.refresh(new_treatment)

    # Invalidate cache
    cache_key = f"treatments:list:{user_id}:*"
    await redis_cache.delete_pattern(cache_key)

    # Return formatted response
    return _serialize_treatment(new_treatment)


@router.patch(
    "/{treatment_id}",
    response_model=TreatmentV2Response,
    summary="Update treatment",
    description="Update treatment information (partial update) (ADMIN/DOCTOR only)"
)
@limiter.limit("30/hour")
async def update_treatment(
    request: Request,
    treatment_id: str,
    treatment_data: TreatmentV2Update,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """
    Update a treatment (partial update).

    Only provided fields will be updated.
    """
    try:
        treatment_uuid = UUID(treatment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid treatment ID format"
        )

    treatment = db.query(Treatment).filter(
        Treatment.id == treatment_uuid,
        Treatment.is_active == True
    ).first()

    if not treatment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Treatment with id {treatment_id} not found"
        )

    _ensure_treatment_access(current_user, treatment.doctor_id)

    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    # Update only provided fields
    update_data = treatment_data.dict(exclude_unset=True)

    # Validate doctor_id if provided
    if "doctor_id" in update_data:
        if update_data["doctor_id"]:
            try:
                new_doctor_uuid = UUID(update_data["doctor_id"])
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid doctor ID format"
                )
            if role_enum != UserRole.ADMIN:
                if current_user_uuid is None or current_user_uuid != new_doctor_uuid:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Doctors cannot reassign treatments to other doctors"
                    )
            update_data["doctor_id"] = new_doctor_uuid
        else:
            # Prevent doctors from clearing doctor assignment
            if role_enum != UserRole.ADMIN:
                update_data.pop("doctor_id")

    # Validate treatment_type if provided
    if "treatment_type" in update_data and update_data["treatment_type"]:
        try:
            treatment_type_enum = TreatmentType(update_data["treatment_type"].lower())
            update_data["treatment_type"] = treatment_type_enum
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid treatment type. Valid types: {', '.join([t.value for t in TreatmentType])}"
            )

    # Validate status if provided
    if "status" in update_data and update_data["status"]:
        try:
            status_enum = TreatmentStatus(update_data["status"].lower())
            update_data["status"] = status_enum
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Valid statuses: {', '.join([s.value for s in TreatmentStatus])}"
            )

    for field, value in update_data.items():
        setattr(treatment, field, value)

    db.commit()
    db.refresh(treatment)

    # Invalidate cache
    cache_key = f"treatment:{treatment_id}"
    await redis_cache.delete(cache_key)
    cache_list_key = f"treatments:list:{user_id}:*"
    await redis_cache.delete_pattern(cache_list_key)

    # Return formatted response
    return _serialize_treatment(treatment)


@router.delete(
    "/{treatment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete treatment (soft delete)",
    description="Soft delete a treatment record - marks as inactive"
)
@limiter.limit("10/hour")
async def delete_treatment(
    request: Request,
    treatment_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """
    Soft delete a treatment.

    This marks the treatment as inactive (sets is_active=False) without
    removing the record from the database. This preserves data for audit
    purposes and allows restoration if needed.
    """
    try:
        treatment_uuid = UUID(treatment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid treatment ID format"
        )

    # Only get active treatments
    treatment = db.query(Treatment).filter(
        Treatment.id == treatment_uuid,
        Treatment.is_active == True
    ).first()

    if not treatment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active treatment with id {treatment_id} not found"
        )

    _ensure_treatment_access(current_user, treatment.doctor_id)

    # Soft delete: set is_active to False
    treatment.is_active = False
    treatment.status = TreatmentStatus.CANCELLED
    db.commit()

    # Invalidate cache
    role_enum, user_id = _extract_user_context(current_user)
    cache_key = f"treatment:{treatment_id}"
    await redis_cache.delete(cache_key)
    cache_list_key = f"treatments:list:{user_id}:*"
    await redis_cache.delete_pattern(cache_list_key)

    return None


@router.patch(
    "/{treatment_id}/activate",
    response_model=TreatmentV2Response,
    summary="Activate treatment",
    description="Change treatment status from planned to active (ADMIN/DOCTOR only)"
)
@limiter.limit("30/hour")
async def activate_treatment(
    request: Request,
    treatment_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """
    Activate a treatment.

    Changes status from PLANNED to ACTIVE.
    """
    try:
        treatment_uuid = UUID(treatment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid treatment ID format"
        )

    treatment = db.query(Treatment).filter(
        Treatment.id == treatment_uuid,
        Treatment.is_active == True
    ).first()

    if not treatment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Treatment with id {treatment_id} not found"
        )

    _ensure_treatment_access(current_user, treatment.doctor_id)

    # Validate current status
    if treatment.status != TreatmentStatus.PLANNED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot activate treatment with status {treatment.status.value}. Only planned treatments can be activated."
        )

    # Update status to active
    treatment.status = TreatmentStatus.ACTIVE
    db.commit()
    db.refresh(treatment)

    # Invalidate cache
    role_enum, user_id = _extract_user_context(current_user)
    cache_key = f"treatment:{treatment_id}"
    await redis_cache.delete(cache_key)
    cache_list_key = f"treatments:list:{user_id}:*"
    await redis_cache.delete_pattern(cache_list_key)

    return _serialize_treatment(treatment)


@router.patch(
    "/{treatment_id}/complete",
    response_model=TreatmentV2Response,
    summary="Complete treatment",
    description="Mark treatment as completed (ADMIN/DOCTOR only)"
)
@limiter.limit("30/hour")
async def complete_treatment(
    request: Request,
    treatment_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """
    Complete a treatment.

    Changes status to COMPLETED and sets end_date to today if not set.
    """
    try:
        treatment_uuid = UUID(treatment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid treatment ID format"
        )

    treatment = db.query(Treatment).filter(
        Treatment.id == treatment_uuid,
        Treatment.is_active == True
    ).first()

    if not treatment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Treatment with id {treatment_id} not found"
        )

    _ensure_treatment_access(current_user, treatment.doctor_id)

    # Validate current status
    if treatment.status == TreatmentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Treatment is already completed"
        )

    # Update status to completed
    treatment.status = TreatmentStatus.COMPLETED

    # Set end_date to today if not set
    if not treatment.end_date:
        treatment.end_date = date.today()

    db.commit()
    db.refresh(treatment)

    # Invalidate cache
    role_enum, user_id = _extract_user_context(current_user)
    cache_key = f"treatment:{treatment_id}"
    await redis_cache.delete(cache_key)
    cache_list_key = f"treatments:list:{user_id}:*"
    await redis_cache.delete_pattern(cache_list_key)

    return _serialize_treatment(treatment)


@router.patch(
    "/{treatment_id}/suspend",
    response_model=TreatmentV2Response,
    summary="Suspend treatment",
    description="Suspend an active treatment (ADMIN/DOCTOR only)"
)
@limiter.limit("30/hour")
async def suspend_treatment(
    request: Request,
    treatment_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """
    Suspend a treatment.

    Changes status to SUSPENDED.
    """
    try:
        treatment_uuid = UUID(treatment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid treatment ID format"
        )

    treatment = db.query(Treatment).filter(
        Treatment.id == treatment_uuid,
        Treatment.is_active == True
    ).first()

    if not treatment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Treatment with id {treatment_id} not found"
        )

    _ensure_treatment_access(current_user, treatment.doctor_id)

    # Validate current status
    if treatment.status == TreatmentStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Treatment is already suspended"
        )

    if treatment.status == TreatmentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot suspend a completed treatment"
        )

    # Update status to suspended
    treatment.status = TreatmentStatus.SUSPENDED
    db.commit()
    db.refresh(treatment)

    # Invalidate cache
    role_enum, user_id = _extract_user_context(current_user)
    cache_key = f"treatment:{treatment_id}"
    await redis_cache.delete(cache_key)
    cache_list_key = f"treatments:list:{user_id}:*"
    await redis_cache.delete_pattern(cache_list_key)

    return _serialize_treatment(treatment)
