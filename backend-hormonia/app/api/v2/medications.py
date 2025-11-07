"""
Medications API v2
Enhanced medication endpoints with cursor pagination, field selection, and eager loading.
"""

from typing import Optional, List, Tuple, Dict
from datetime import date, datetime
from uuid import UUID
from decimal import Decimal
import logging
import json
import base64
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, or_

from app.database import get_db
from app.models.medication import Medication
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.models.treatment import Treatment
from app.schemas.v2.medication import (
    MedicationV2Response,
    MedicationV2List,
    MedicationV2Create,
    MedicationV2Update,
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


def _ensure_medication_access(current_user, medication_prescribed_by_id, patient_doctor_id):
    """
    Ensure user has access to this medication.
    Admins can access all. Doctors can access medications they prescribed or for their patients.
    """
    if _is_admin(current_user):
        return

    _, user_id = _extract_user_context(current_user)
    user_uuid = _ensure_uuid(user_id)

    if user_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unable to determine user permissions",
        )

    # Doctor can access if they prescribed it OR if it's for their patient
    if user_uuid != medication_prescribed_by_id and user_uuid != patient_doctor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this medication",
        )


def _serialize_medication(medication) -> Optional[dict]:
    """Serialize Medication SQLAlchemy model to API-friendly dict."""
    if medication is None:
        return None

    created_at = getattr(medication, "created_at", None)
    updated_at = getattr(medication, "updated_at", None)

    return {
        "id": str(getattr(medication, "id")),
        "patient_id": str(getattr(medication, "patient_id")),
        "prescribed_by_id": str(getattr(medication, "prescribed_by_id")) if getattr(medication, "prescribed_by_id", None) else None,
        "treatment_id": str(getattr(medication, "treatment_id")) if getattr(medication, "treatment_id", None) else None,
        "name": getattr(medication, "name"),
        "active_ingredient": getattr(medication, "active_ingredient", None),
        "dosage": getattr(medication, "dosage"),
        "frequency": getattr(medication, "frequency"),
        "route": getattr(medication, "route", None),
        "prescription_date": getattr(medication, "prescription_date"),
        "start_date": getattr(medication, "start_date"),
        "end_date": getattr(medication, "end_date", None),
        "quantity": float(getattr(medication, "quantity")) if getattr(medication, "quantity", None) else None,
        "refills_allowed": getattr(medication, "refills_allowed", 0),
        "refills_remaining": getattr(medication, "refills_remaining", 0),
        "instructions": getattr(medication, "instructions", None),
        "warnings": getattr(medication, "warnings", None),
        "side_effects": getattr(medication, "side_effects", None),
        "is_active": getattr(medication, "is_active", True),
        "discontinued_date": getattr(medication, "discontinued_date", None),
        "discontinuation_reason": getattr(medication, "discontinuation_reason", None),
        "created_at": created_at,
        "updated_at": updated_at,
    }


class MedicationStatsResponse(BaseModel):
    total_medications: int
    active_medications: int
    discontinued_medications: int
    by_route: Dict[str, int]


@router.get(
    "",
    response_model=MedicationV2List,
    summary="List medications with pagination",
    description="Get paginated list of medications with optional field selection and eager loading"
)
async def list_medications(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
    pagination = Depends(get_pagination_params),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    search: Optional[str] = Query(None, description="Search by medication name"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    prescribed_by_id: Optional[str] = Query(None, description="Filter by prescriber ID"),
    treatment_id: Optional[str] = Query(None, description="Filter by treatment ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    route: Optional[str] = Query(None, description="Filter by route of administration"),
):
    """
    List medications with cursor-based pagination.

    Features:
    - Cursor-based pagination (efficient for large datasets)
    - Field selection (?fields=id,name,dosage)
    - Eager loading (?include=patient,prescribed_by,treatment)
    - Search by medication name
    - Filter by patient_id, prescribed_by_id, treatment_id, is_active, route
    - RBAC: Doctors see only medications they prescribed or for their patients

    Example:
        GET /api/v2/medications?limit=20&fields=id,name,dosage&include=patient
    """
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    # Build cache key
    role_enum, user_id = _extract_user_context(current_user)
    cache_key = f"medications:list:{user_id}:{cursor_data}:{limit}:{search}:{patient_id}:{prescribed_by_id}:{treatment_id}:{is_active}:{route}"

    # Try cache first
    cached_data = await redis_cache.get(cache_key)
    if cached_data:
        try:
            return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Failed to parse cached medications list: {e}")

    # Build base query
    query = db.query(Medication)

    # Apply eager loading
    if include:
        if "patient" in include:
            query = query.options(joinedload(Medication.patient))
        if "prescribed_by" in include:
            query = query.options(joinedload(Medication.prescribed_by))
        if "treatment" in include:
            query = query.options(joinedload(Medication.treatment))

    # Apply filters
    filters = []
    current_user_uuid = _ensure_uuid(user_id)

    # Filter out soft-deleted medications by default
    filters.append(Medication.deleted_at.is_(None))

    # RBAC: Non-admin users can only see medications they prescribed or for their patients
    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to determine user permissions",
            )
        # Show medications prescribed by this doctor OR for patients assigned to this doctor
        filters.append(
            or_(
                Medication.prescribed_by_id == current_user_uuid,
                Medication.patient.has(Patient.doctor_id == current_user_uuid)
            )
        )

    if cursor_data and "id" in cursor_data:
        cursor_id = UUID(cursor_data["id"]) if isinstance(cursor_data["id"], str) else cursor_data["id"]
        cursor_created_at = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))

        # For descending order, we want records with created_at < cursor OR (created_at == cursor AND id > cursor_id)
        filters.append(
            (Medication.created_at < cursor_created_at) |
            ((Medication.created_at == cursor_created_at) & (Medication.id > cursor_id))
        )

    if search:
        search_filter = f"%{search}%"
        filters.append(Medication.name.ilike(search_filter))

    if patient_id:
        try:
            patient_uuid = UUID(patient_id)
            filters.append(Medication.patient_id == patient_uuid)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid patient ID format"
            )

    if prescribed_by_id:
        try:
            prescriber_uuid = UUID(prescribed_by_id)
            filters.append(Medication.prescribed_by_id == prescriber_uuid)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid prescriber ID format"
            )

    if treatment_id:
        try:
            treatment_uuid = UUID(treatment_id)
            filters.append(Medication.treatment_id == treatment_uuid)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid treatment ID format"
            )

    if is_active is not None:
        filters.append(Medication.is_active == is_active)

    if route:
        filters.append(Medication.route.ilike(f"%{route.strip()}%"))

    if filters:
        query = query.filter(and_(*filters))

    total = None
    if not cursor_data:
        total_query = db.query(func.count(Medication.id))
        if filters:
            total_query = total_query.filter(and_(*filters))
        total = total_query.scalar()

    # Order and limit
    query = query.order_by(Medication.created_at.desc(), Medication.id)
    medications = query.limit(limit + 1).all()

    # Check if there are more results
    has_more = len(medications) > limit
    if has_more:
        medications = medications[:limit]

    # Create next cursor
    next_cursor = None
    if has_more and medications:
        cursor_data = {
            "id": str(medications[-1].id),
            "created_at": medications[-1].created_at.isoformat()
        }
        next_cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()

    # Convert to response models
    medication_responses = []
    for medication in medications:
        medication_dict = _serialize_medication(medication)

        # Add eager-loaded relationships
        if include:
            if "patient" in include and medication.patient:
                medication_dict["patient"] = {
                    "id": str(medication.patient.id),
                    "name": medication.patient.name,
                    "email": medication.patient.email,
                }
            if "prescribed_by" in include and medication.prescribed_by:
                medication_dict["prescribed_by"] = {
                    "id": str(medication.prescribed_by.id),
                    "name": medication.prescribed_by.name if hasattr(medication.prescribed_by, 'name') else medication.prescribed_by.full_name,
                    "email": medication.prescribed_by.email,
                }
            if "treatment" in include and medication.treatment:
                medication_dict["treatment"] = {
                    "id": str(medication.treatment.id),
                    "treatment_type": medication.treatment.treatment_type,
                    "status": medication.treatment.status,
                    "start_date": medication.treatment.start_date,
                }

        # Apply field selection
        if fields:
            medication_dict = apply_field_selection(medication_dict, fields)

        medication_responses.append(medication_dict)

    response_data = {
        "data": medication_responses,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
    }

    # Cache the response for 5 minutes
    try:
        await redis_cache.set(cache_key, json.dumps(response_data, default=str), ttl=300)
    except Exception as e:
        logger.warning(f"Failed to cache medications list: {e}")

    return response_data


@router.get(
    "/active",
    response_model=MedicationV2List,
    summary="List active medications",
    description="Get all active medications (is_active=true) with pagination"
)
@limiter.limit("120/minute")
async def list_active_medications(
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
    pagination = Depends(get_pagination_params),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
):
    """
    List only active medications.

    This is a convenience endpoint that filters medications by is_active=true.
    Useful for displaying current medication lists for patients.
    """
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    # Build cache key
    role_enum, user_id = _extract_user_context(current_user)
    cache_key = f"medications:active:{user_id}:{patient_id}:{cursor_data}:{limit}"

    # Try cache first
    cached_data = await redis_cache.get(cache_key)
    if cached_data:
        try:
            return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Failed to parse cached active medications: {e}")

    # Build query
    query = db.query(Medication)

    # Apply filters
    filters = [
        Medication.deleted_at.is_(None),
        Medication.is_active == True
    ]

    current_user_uuid = _ensure_uuid(user_id)

    # RBAC: Non-admin users can only see medications they prescribed or for their patients
    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to determine user permissions",
            )
        filters.append(
            or_(
                Medication.prescribed_by_id == current_user_uuid,
                Medication.patient.has(Patient.doctor_id == current_user_uuid)
            )
        )

    if patient_id:
        try:
            patient_uuid = UUID(patient_id)
            filters.append(Medication.patient_id == patient_uuid)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid patient ID format"
            )

    if cursor_data and "id" in cursor_data:
        cursor_id = UUID(cursor_data["id"]) if isinstance(cursor_data["id"], str) else cursor_data["id"]
        cursor_created_at = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))

        filters.append(
            (Medication.created_at < cursor_created_at) |
            ((Medication.created_at == cursor_created_at) & (Medication.id > cursor_id))
        )

    query = query.filter(and_(*filters))

    total = None
    if not cursor_data:
        total = db.query(func.count(Medication.id)).filter(and_(*filters)).scalar()

    # Order and limit
    query = query.order_by(Medication.created_at.desc(), Medication.id)
    medications = query.limit(limit + 1).all()

    # Check if there are more results
    has_more = len(medications) > limit
    if has_more:
        medications = medications[:limit]

    # Create next cursor
    next_cursor = None
    if has_more and medications:
        cursor_data = {
            "id": str(medications[-1].id),
            "created_at": medications[-1].created_at.isoformat()
        }
        next_cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()

    # Convert to response models
    medication_responses = [_serialize_medication(med) for med in medications]

    response_data = {
        "data": medication_responses,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
    }

    # Cache the response for 5 minutes
    try:
        await redis_cache.set(cache_key, json.dumps(response_data, default=str), ttl=300)
    except Exception as e:
        logger.warning(f"Failed to cache active medications: {e}")

    return response_data


@router.get(
    "/search",
    response_model=List[MedicationV2Response],
    summary="Search medications",
    description="Search medications by name (doctor/admin only)",
)
@limiter.limit("120/minute")
async def search_medications(
    request: Request,
    q: str = Query(..., min_length=1, description="Search term"),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    query = db.query(Medication).filter(Medication.deleted_at.is_(None))

    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to determine user permissions",
            )
        query = query.filter(
            or_(
                Medication.prescribed_by_id == current_user_uuid,
                Medication.patient.has(Patient.doctor_id == current_user_uuid)
            )
        )

    search_filter = f"%{q}%"
    medications = (
        query.filter(Medication.name.ilike(search_filter))
        .order_by(Medication.created_at.desc())
        .limit(limit)
        .all()
    )

    return [_serialize_medication(medication) for medication in medications]


@router.get(
    "/{medication_id}",
    response_model=MedicationV2Response,
    summary="Get medication by ID",
    description="Get a single medication with optional field selection and eager loading"
)
async def get_medication(
    medication_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
):
    """
    Get a single medication by ID.

    Features:
    - Field selection (?fields=id,name,dosage)
    - Eager loading (?include=patient,prescribed_by,treatment)
    - Redis caching

    Example:
        GET /api/v2/medications/123e4567-e89b-12d3-a456-426614174000?fields=id,name,dosage&include=patient
    """
    try:
        medication_uuid = UUID(medication_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid medication ID format"
        )

    # Try cache first
    role_enum, user_id = _extract_user_context(current_user)
    cache_key = f"medication:{medication_id}:{user_id}"
    cached_data = await redis_cache.get(cache_key)
    if cached_data:
        try:
            return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Failed to parse cached medication: {e}")

    query = db.query(Medication)

    # Apply eager loading
    if include:
        if "patient" in include:
            query = query.options(joinedload(Medication.patient))
        if "prescribed_by" in include:
            query = query.options(joinedload(Medication.prescribed_by))
        if "treatment" in include:
            query = query.options(joinedload(Medication.treatment))

    medication = query.filter(
        Medication.id == medication_uuid,
        Medication.deleted_at.is_(None)
    ).first()

    if not medication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medication with id {medication_id} not found"
        )

    # Get patient for access control
    patient = db.query(Patient).filter(Patient.id == medication.patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found for this medication"
        )

    _ensure_medication_access(current_user, medication.prescribed_by_id, patient.doctor_id)

    # Build response
    medication_dict = _serialize_medication(medication)

    # Add eager-loaded relationships
    if include:
        if "patient" in include and medication.patient:
            medication_dict["patient"] = {
                "id": str(medication.patient.id),
                "name": medication.patient.name,
                "email": medication.patient.email,
            }
        if "prescribed_by" in include and medication.prescribed_by:
            medication_dict["prescribed_by"] = {
                "id": str(medication.prescribed_by.id),
                "name": medication.prescribed_by.name if hasattr(medication.prescribed_by, 'name') else medication.prescribed_by.full_name,
                "email": medication.prescribed_by.email,
            }
        if "treatment" in include and medication.treatment:
            medication_dict["treatment"] = {
                "id": str(medication.treatment.id),
                "treatment_type": medication.treatment.treatment_type,
                "status": medication.treatment.status,
                "start_date": medication.treatment.start_date,
            }

    # Apply field selection
    if fields:
        medication_dict = apply_field_selection(medication_dict, fields)

    # Cache the response for 5 minutes
    try:
        await redis_cache.set(cache_key, json.dumps(medication_dict, default=str), ttl=300)
    except Exception as e:
        logger.warning(f"Failed to cache medication: {e}")

    return medication_dict


@router.post(
    "",
    response_model=MedicationV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Create new medication",
    description="Create a new medication record (ADMIN/DOCTOR only)"
)
@limiter.limit("30/hour")
async def create_medication(
    request: Request,
    medication_data: MedicationV2Create,
    db: Session = Depends(get_db),
    current_user = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache),
):
    """
    Create a new medication.

    Validates:
    - Patient exists
    - Prescriber exists (if provided)
    - Treatment exists (if provided)
    - Date validations (end_date >= start_date)
    - Refills validation (refills_remaining <= refills_allowed)
    """
    # Convert patient_id to UUID
    try:
        patient_uuid = UUID(medication_data.patient_id)
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
            detail=f"Patient with id {medication_data.patient_id} not found"
        )

    # RBAC: Non-admin doctors can only create medications for their patients
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None or current_user_uuid != patient.doctor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Doctors can only create medications for their own patients"
            )

    # Validate prescriber if provided
    prescribed_by_uuid = None
    if medication_data.prescribed_by_id:
        try:
            prescribed_by_uuid = UUID(medication_data.prescribed_by_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid prescriber ID format"
            )

        prescriber = db.query(User).filter(User.id == prescribed_by_uuid).first()
        if not prescriber:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prescriber with id {medication_data.prescribed_by_id} not found"
            )
    else:
        # Default to current user as prescriber
        prescribed_by_uuid = current_user_uuid

    # Validate treatment if provided
    treatment_uuid = None
    if medication_data.treatment_id:
        try:
            treatment_uuid = UUID(medication_data.treatment_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid treatment ID format"
            )

        treatment = db.query(Treatment).filter(Treatment.id == treatment_uuid).first()
        if not treatment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Treatment with id {medication_data.treatment_id} not found"
            )

    # Create medication
    new_medication = Medication(
        patient_id=patient_uuid,
        prescribed_by_id=prescribed_by_uuid,
        treatment_id=treatment_uuid,
        name=medication_data.name,
        active_ingredient=medication_data.active_ingredient,
        dosage=medication_data.dosage,
        frequency=medication_data.frequency,
        route=medication_data.route,
        prescription_date=medication_data.prescription_date,
        start_date=medication_data.start_date,
        end_date=medication_data.end_date,
        quantity=medication_data.quantity,
        refills_allowed=medication_data.refills_allowed,
        refills_remaining=medication_data.refills_remaining,
        instructions=medication_data.instructions,
        warnings=medication_data.warnings,
        side_effects=medication_data.side_effects,
        is_active=medication_data.is_active,
        discontinued_date=medication_data.discontinued_date,
        discontinuation_reason=medication_data.discontinuation_reason,
    )

    db.add(new_medication)

    try:
        db.commit()
        db.refresh(new_medication)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create medication: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create medication: {str(e)}"
        )

    # Invalidate cache
    try:
        await redis_cache.delete(f"medications:list:{user_id}:*")
        await redis_cache.delete(f"medications:active:{user_id}:*")
    except Exception as e:
        logger.warning(f"Failed to invalidate cache: {e}")

    # Return formatted response from created entity
    return _serialize_medication(new_medication)


@router.patch(
    "/{medication_id}",
    response_model=MedicationV2Response,
    summary="Update medication",
    description="Update medication information (partial update) (ADMIN/DOCTOR only)"
)
@limiter.limit("30/hour")
async def update_medication(
    request: Request,
    medication_id: str,
    medication_data: MedicationV2Update,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """
    Update a medication (partial update).

    Only provided fields will be updated.
    """
    try:
        medication_uuid = UUID(medication_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid medication ID format"
        )

    medication = db.query(Medication).filter(
        Medication.id == medication_uuid,
        Medication.deleted_at.is_(None)
    ).first()

    if not medication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medication with id {medication_id} not found"
        )

    # Get patient for access control
    patient = db.query(Patient).filter(Patient.id == medication.patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found for this medication"
        )

    _ensure_medication_access(current_user, medication.prescribed_by_id, patient.doctor_id)

    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    # Update only provided fields
    update_data = medication_data.dict(exclude_unset=True)

    # Validate prescriber if provided
    if "prescribed_by_id" in update_data and update_data["prescribed_by_id"]:
        try:
            prescriber_uuid = UUID(update_data["prescribed_by_id"])
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid prescriber ID format"
            )

        prescriber = db.query(User).filter(User.id == prescriber_uuid).first()
        if not prescriber:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prescriber not found"
            )
        update_data["prescribed_by_id"] = prescriber_uuid

    # Validate treatment if provided
    if "treatment_id" in update_data and update_data["treatment_id"]:
        try:
            treatment_uuid = UUID(update_data["treatment_id"])
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid treatment ID format"
            )

        treatment = db.query(Treatment).filter(Treatment.id == treatment_uuid).first()
        if not treatment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Treatment not found"
            )
        update_data["treatment_id"] = treatment_uuid

    for field, value in update_data.items():
        setattr(medication, field, value)

    try:
        db.commit()
        db.refresh(medication)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update medication: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update medication: {str(e)}"
        )

    # Invalidate cache
    try:
        await redis_cache.delete(f"medication:{medication_id}:*")
        await redis_cache.delete(f"medications:list:{user_id}:*")
        await redis_cache.delete(f"medications:active:{user_id}:*")
    except Exception as e:
        logger.warning(f"Failed to invalidate cache: {e}")

    # Return formatted response
    return _serialize_medication(medication)


@router.delete(
    "/{medication_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete medication (soft delete)",
    description="Soft delete a medication record - marks as deleted without removing from database"
)
@limiter.limit("10/hour")
async def delete_medication(
    request: Request,
    medication_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """
    Soft delete a medication.

    This marks the medication as deleted (sets deleted_at timestamp and is_active=false)
    without removing the record from the database. This preserves data for audit
    purposes and allows restoration if needed.
    """
    try:
        medication_uuid = UUID(medication_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid medication ID format"
        )

    # Only get active medications (not already deleted)
    medication = db.query(Medication).filter(
        Medication.id == medication_uuid,
        Medication.deleted_at.is_(None)
    ).first()

    if not medication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active medication with id {medication_id} not found"
        )

    # Get patient for access control
    patient = db.query(Patient).filter(Patient.id == medication.patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found for this medication"
        )

    _ensure_medication_access(current_user, medication.prescribed_by_id, patient.doctor_id)

    # Soft delete: set deleted_at timestamp and mark as inactive
    medication.deleted_at = datetime.utcnow()
    medication.is_active = False

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete medication: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete medication: {str(e)}"
        )

    # Invalidate cache
    role_enum, user_id = _extract_user_context(current_user)
    try:
        await redis_cache.delete(f"medication:{medication_id}:*")
        await redis_cache.delete(f"medications:list:{user_id}:*")
        await redis_cache.delete(f"medications:active:{user_id}:*")
    except Exception as e:
        logger.warning(f"Failed to invalidate cache: {e}")

    return None


@router.patch(
    "/{medication_id}/discontinue",
    response_model=MedicationV2Response,
    summary="Discontinue medication",
    description="Discontinue a medication (set is_active=false with reason)"
)
@limiter.limit("30/hour")
async def discontinue_medication(
    request: Request,
    medication_id: str,
    reason: str = Query(..., min_length=1, description="Reason for discontinuation"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """
    Discontinue a medication.

    This sets is_active=false, discontinued_date=today, and records the reason.
    Unlike delete, this explicitly marks the medication as discontinued in medical records.
    """
    try:
        medication_uuid = UUID(medication_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid medication ID format"
        )

    medication = db.query(Medication).filter(
        Medication.id == medication_uuid,
        Medication.deleted_at.is_(None)
    ).first()

    if not medication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medication with id {medication_id} not found"
        )

    # Get patient for access control
    patient = db.query(Patient).filter(Patient.id == medication.patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found for this medication"
        )

    _ensure_medication_access(current_user, medication.prescribed_by_id, patient.doctor_id)

    # Discontinue medication
    medication.is_active = False
    medication.discontinued_date = date.today()
    medication.discontinuation_reason = reason

    try:
        db.commit()
        db.refresh(medication)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to discontinue medication: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to discontinue medication: {str(e)}"
        )

    # Invalidate cache
    role_enum, user_id = _extract_user_context(current_user)
    try:
        await redis_cache.delete(f"medication:{medication_id}:*")
        await redis_cache.delete(f"medications:list:{user_id}:*")
        await redis_cache.delete(f"medications:active:{user_id}:*")
    except Exception as e:
        logger.warning(f"Failed to invalidate cache: {e}")

    return _serialize_medication(medication)


@router.patch(
    "/{medication_id}/refill",
    response_model=MedicationV2Response,
    summary="Record medication refill",
    description="Record a medication refill (decrease refills_remaining)"
)
@limiter.limit("30/hour")
async def refill_medication(
    request: Request,
    medication_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """
    Record a medication refill.

    This decreases refills_remaining by 1. If refills_remaining is already 0,
    it returns an error.
    """
    try:
        medication_uuid = UUID(medication_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid medication ID format"
        )

    medication = db.query(Medication).filter(
        Medication.id == medication_uuid,
        Medication.deleted_at.is_(None)
    ).first()

    if not medication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medication with id {medication_id} not found"
        )

    # Get patient for access control
    patient = db.query(Patient).filter(Patient.id == medication.patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found for this medication"
        )

    _ensure_medication_access(current_user, medication.prescribed_by_id, patient.doctor_id)

    # Check if refills are available
    if medication.refills_remaining <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No refills remaining for this medication"
        )

    # Record refill
    medication.refills_remaining -= 1

    try:
        db.commit()
        db.refresh(medication)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to record refill: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record refill: {str(e)}"
        )

    # Invalidate cache
    role_enum, user_id = _extract_user_context(current_user)
    try:
        await redis_cache.delete(f"medication:{medication_id}:*")
        await redis_cache.delete(f"medications:list:{user_id}:*")
    except Exception as e:
        logger.warning(f"Failed to invalidate cache: {e}")

    return _serialize_medication(medication)


@router.get(
    "/stats",
    response_model=MedicationStatsResponse,
    summary="Get medication statistics summary",
)
@limiter.limit("30/minute")
async def get_medication_stats(
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """
    Get medication statistics.

    Returns:
    - Total medications
    - Active medications
    - Discontinued medications
    - Breakdown by route of administration
    """
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    base_query = db.query(Medication).filter(Medication.deleted_at.is_(None))

    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to determine user permissions",
            )
        base_query = base_query.filter(
            or_(
                Medication.prescribed_by_id == current_user_uuid,
                Medication.patient.has(Patient.doctor_id == current_user_uuid)
            )
        )

    total_medications = base_query.count()
    active_medications = base_query.filter(Medication.is_active == True).count()
    discontinued_medications = base_query.filter(Medication.is_active == False).count()

    # Count by route
    by_route: Dict[str, int] = {}
    route_results = db.query(
        Medication.route,
        func.count(Medication.id).label('count')
    ).filter(
        Medication.deleted_at.is_(None)
    ).group_by(Medication.route).all()

    for route, count in route_results:
        route_name = route if route else "unspecified"
        by_route[route_name] = count

    return MedicationStatsResponse(
        total_medications=total_medications,
        active_medications=active_medications,
        discontinued_medications=discontinued_medications,
        by_route=by_route,
    )
