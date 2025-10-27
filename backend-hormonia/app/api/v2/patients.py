"""
Patients API v2
Enhanced patient endpoints with cursor pagination, field selection, and eager loading.
"""

from typing import Optional, List, Tuple
import re
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func

from app.database import get_db
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.schemas.v2.patient import (
    PatientV2Response,
    PatientV2List,
    PatientV2Create,
    PatientV2Update,
)
from app.schemas.v2.common import ErrorResponse
from .dependencies import (
    get_pagination_params,
    get_field_selection,
    get_eager_load_params,
    create_cursor,
    apply_field_selection,
)
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.utils.rate_limiter import limiter

router = APIRouter()


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
    from uuid import UUID

    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _ensure_patient_access(current_user, patient_doctor_id):
    if _is_admin(current_user):
        return

    _, user_id = _extract_user_context(current_user)
    user_uuid = _ensure_uuid(user_id)

    if user_uuid is None or patient_doctor_id != user_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this patient",
        )


def _normalize_cpf(cpf: Optional[str]) -> Optional[str]:
    """
    Normalize CPF by removing non-digit characters.
    
    Args:
        cpf: CPF string with optional formatting (dots, dashes)
    
    Returns:
        CPF with only digits (max 11 chars) or None
    """
    if not cpf:
        return None
    # Remove all non-digit characters
    normalized = re.sub(r'[^0-9]', '', cpf)
    # Limit to 11 digits (CPF max length)
    return normalized[:11] if normalized else None


def _normalize_phone(phone: Optional[str]) -> Optional[str]:
    """
    Normalize phone by removing non-digit characters.
    
    Args:
        phone: Phone string with optional formatting
    
    Returns:
        Phone with only digits or None
    """
    if not phone:
        return None
    # Remove all non-digit characters (spaces, parentheses, dashes)
    normalized = re.sub(r'[^0-9+]', '', phone)
    return normalized if normalized else None


@router.get(
    "",
    response_model=PatientV2List,
    summary="List patients with pagination",
    description="Get paginated list of patients with optional field selection and eager loading"
)
async def list_patients(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    pagination = Depends(get_pagination_params),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    search: Optional[str] = Query(None, description="Search by name or email"),
):
    """
    List patients with cursor-based pagination.
    
    Features:
    - Cursor-based pagination (efficient for large datasets)
    - Field selection (?fields=id,name,email)
    - Eager loading (?include=doctor,quizzes)
    - Search by name or email
    - Filter by active status
    
    Example:
        GET /api/v2/patients?limit=20&fields=id,name,email&include=doctor
    """
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]
    
    # Build base query
    query = db.query(Patient)
    
    # Apply eager loading
    if include:
        if "doctor" in include:
            query = query.options(joinedload(Patient.doctor))
        if "quiz_sessions" in include or "quizzes" in include:
            query = query.options(joinedload(Patient.quiz_sessions))
    
    # Apply filters
    filters = []
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    # RBAC: Non-admin users can only see their own patients
    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to determine user permissions",
            )
        filters.append(Patient.doctor_id == current_user_uuid)

    if cursor_data and "id" in cursor_data:
        # Handle UUID comparison
        from uuid import UUID
        from datetime import datetime as dt
        cursor_id = UUID(cursor_data["id"]) if isinstance(cursor_data["id"], str) else cursor_data["id"]
        cursor_created_at = dt.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))
        
        # For descending order, we want records with created_at < cursor OR (created_at == cursor AND id > cursor_id)
        # This ensures proper pagination with tie-breaking
        filters.append(
            (Patient.created_at < cursor_created_at) |
            ((Patient.created_at == cursor_created_at) & (Patient.id > cursor_id))
        )
    
    if search:
        search_filter = f"%{search}%"
        filters.append(
            (Patient.name.ilike(search_filter)) | (Patient.email.ilike(search_filter))
        )
    
    if filters:
        query = query.filter(and_(*filters))

    total = None
    if not cursor_data:
        total_query = db.query(func.count(Patient.id))
        if filters:
            total_query = total_query.filter(and_(*filters))
        total = total_query.scalar()
    
    # Order and limit
    query = query.order_by(Patient.created_at.desc(), Patient.id)
    patients = query.limit(limit + 1).all()
    
    # Check if there are more results
    has_more = len(patients) > limit
    if has_more:
        patients = patients[:limit]
    
    # Create next cursor
    next_cursor = None
    if has_more and patients:
        import json
        import base64
        cursor_data = {
            "id": str(patients[-1].id),
            "created_at": patients[-1].created_at.isoformat()
        }
        next_cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()
    
    # Convert to response models
    patient_responses = []
    for patient in patients:
        patient_dict = {
            "id": str(patient.id),
            "name": patient.name,
            "email": patient.email,
            "phone": patient.phone,
            "birth_date": patient.birth_date,
            "cpf": patient.cpf,
            "doctor_id": str(patient.doctor_id),
            "created_at": patient.created_at,
            "updated_at": patient.updated_at,
        }
        
        # Add eager-loaded relationships
        if include:
            if "doctor" in include and patient.doctor:
                patient_dict["doctor"] = {
                    "id": str(patient.doctor.id),
                    "name": patient.doctor.name,
                    "email": patient.doctor.email,
                }
            if ("quiz_sessions" in include or "quizzes" in include) and hasattr(patient, "quiz_sessions"):
                patient_dict["quiz_sessions"] = [
                    {
                        "id": str(q.id),
                        "status": q.status,
                        "started_at": q.started_at,
                        "completed_at": q.completed_at,
                        "score": float(q.score) if q.score else None,
                        "passed": q.passed,
                    }
                    for q in patient.quiz_sessions
                ]
        
        # Apply field selection
        if fields:
            patient_dict = apply_field_selection(patient_dict, fields)
        
        patient_responses.append(patient_dict)
    
    return {
        "data": patient_responses,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
    }


@router.get(
    "/{patient_id}",
    response_model=PatientV2Response,
    summary="Get patient by ID",
    description="Get a single patient with optional field selection and eager loading"
)
async def get_patient(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
):
    """
    Get a single patient by ID.
    
    Features:
    - Field selection (?fields=id,name,email)
    - Eager loading (?include=doctor,quiz_sessions)
    
    Example:
        GET /api/v2/patients/123e4567-e89b-12d3-a456-426614174000?fields=id,name,email&include=doctor
    """
    from uuid import UUID
    
    try:
        patient_uuid = UUID(patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format"
        )
    
    query = db.query(Patient)
    
    # Apply eager loading
    if include:
        if "doctor" in include:
            query = query.options(joinedload(Patient.doctor))
        if "quiz_sessions" in include or "quizzes" in include:
            query = query.options(joinedload(Patient.quiz_sessions))
    
    patient = query.filter(Patient.id == patient_uuid).first()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with id {patient_id} not found"
        )

    _ensure_patient_access(current_user, patient.doctor_id)

    _ensure_patient_access(current_user, patient.doctor_id)
    
    # Build response
    patient_dict = {
        "id": str(patient.id),
        "name": patient.name,
        "email": patient.email,
        "phone": patient.phone,
        "birth_date": patient.birth_date,
        "cpf": patient.cpf,
        "doctor_id": str(patient.doctor_id),
        "created_at": patient.created_at,
        "updated_at": patient.updated_at,
    }
    
    # Add eager-loaded relationships
    if include:
        if "doctor" in include and patient.doctor:
            patient_dict["doctor"] = {
                "id": str(patient.doctor.id),
                "name": patient.doctor.name,
                "email": patient.doctor.email,
            }
        if ("quiz_sessions" in include or "quizzes" in include) and hasattr(patient, "quiz_sessions"):
            patient_dict["quiz_sessions"] = [
                {
                    "id": str(q.id),
                    "status": q.status,
                    "started_at": q.started_at,
                    "completed_at": q.completed_at,
                    "score": float(q.score) if q.score else None,
                    "passed": q.passed,
                }
                for q in patient.quiz_sessions
            ]
    
    # Apply field selection
    if fields:
        patient_dict = apply_field_selection(patient_dict, fields)
    
    return patient_dict


@router.post(
    "",
    response_model=PatientV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Create new patient",
    description="Create a new patient record (ADMIN/DOCTOR only)"
)
@limiter.limit("20/hour")
async def create_patient(
    request: Request,
    patient_data: PatientV2Create,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """
    Create a new patient.
    
    Validates:
    - Doctor exists
    - Email is unique (if provided)
    - CPF is unique (if provided)
    - Phone is unique
    """
    from uuid import UUID
    
    # Convert doctor_id to UUID
    try:
        doctor_uuid = UUID(patient_data.doctor_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid doctor ID format"
        )
    
    # Check if doctor exists
    doctor = db.query(User).filter(User.id == doctor_uuid).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Doctor with id {patient_data.doctor_id} not found"
        )
    
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)
    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None or current_user_uuid != doctor_uuid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Doctors can only create patients for themselves"
            )

    # Normalize CPF and Phone before validation
    normalized_cpf = _normalize_cpf(patient_data.cpf)
    normalized_phone = _normalize_phone(patient_data.phone)
    
    # Validate CPF length after normalization
    if normalized_cpf and len(normalized_cpf) != 11:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CPF must have exactly 11 digits, got {len(normalized_cpf)}"
        )
    
    # Check email uniqueness (if provided)
    if patient_data.email:
        existing_email = db.query(Patient).filter(Patient.email == patient_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Patient with email {patient_data.email} already exists"
            )
    
    # Check CPF uniqueness (if provided)
    if normalized_cpf:
        existing_cpf = db.query(Patient).filter(Patient.cpf == normalized_cpf).first()
        if existing_cpf:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Patient with CPF already exists"
            )
    
    # Check phone uniqueness (required field)
    if normalized_phone:
        existing_phone = db.query(Patient).filter(Patient.phone == normalized_phone).first()
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Patient with phone already exists"
            )
    
    # Create patient with normalized data
    patient_dict = patient_data.dict()
    patient_dict["doctor_id"] = doctor_uuid
    patient_dict["cpf"] = normalized_cpf
    patient_dict["phone"] = normalized_phone
    new_patient = Patient(**patient_dict)
    db.add(new_patient)
    db.commit()
    db.refresh(new_patient)
    
    # Return formatted response
    return {
        "id": str(new_patient.id),
        "name": new_patient.name,
        "email": new_patient.email,
        "phone": new_patient.phone,
        "birth_date": new_patient.birth_date,
        "cpf": new_patient.cpf,
        "doctor_id": str(new_patient.doctor_id),
        "created_at": new_patient.created_at,
        "updated_at": new_patient.updated_at,
    }


@router.patch(
    "/{patient_id}",
    response_model=PatientV2Response,
    summary="Update patient",
    description="Update patient information (partial update) (ADMIN/DOCTOR only)"
)
@limiter.limit("30/hour")
async def update_patient(
    request: Request,
    patient_id: str,
    patient_data: PatientV2Update,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """
    Update a patient (partial update).
    
    Only provided fields will be updated.
    """
    from uuid import UUID
    
    try:
        patient_uuid = UUID(patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format"
        )
    
    patient = db.query(Patient).filter(Patient.id == patient_uuid).first()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with id {patient_id} not found"
        )

    _ensure_patient_access(current_user, patient.doctor_id)
    
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    # Update only provided fields
    update_data = patient_data.dict(exclude_unset=True)
    
    # Normalize CPF and Phone if provided
    if "cpf" in update_data and update_data["cpf"]:
        normalized_cpf = _normalize_cpf(update_data["cpf"])
        if normalized_cpf and len(normalized_cpf) != 11:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CPF must have exactly 11 digits, got {len(normalized_cpf)}"
            )
        update_data["cpf"] = normalized_cpf
        
        # Check CPF uniqueness (exclude current patient)
        if normalized_cpf:
            existing_cpf = db.query(Patient).filter(
                Patient.cpf == normalized_cpf,
                Patient.id != patient.id
            ).first()
            if existing_cpf:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Patient with CPF already exists"
                )
    
    if "phone" in update_data and update_data["phone"]:
        normalized_phone = _normalize_phone(update_data["phone"])
        update_data["phone"] = normalized_phone
        
        # Check phone uniqueness (exclude current patient)
        if normalized_phone:
            existing_phone = db.query(Patient).filter(
                Patient.phone == normalized_phone,
                Patient.id != patient.id
            ).first()
            if existing_phone:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Patient with phone already exists"
                )
    
    # Convert doctor_id to UUID if provided
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
                        detail="Doctors cannot reassign patients to other doctors"
                    )
            update_data["doctor_id"] = new_doctor_uuid
        else:
            # Prevent doctors from clearing doctor assignment
            if role_enum != UserRole.ADMIN:
                update_data.pop("doctor_id")
    
    for field, value in update_data.items():
        setattr(patient, field, value)
    
    db.commit()
    db.refresh(patient)
    
    # Return formatted response
    return {
        "id": str(patient.id),
        "name": patient.name,
        "email": patient.email,
        "phone": patient.phone,
        "birth_date": patient.birth_date,
        "cpf": patient.cpf,
        "doctor_id": str(patient.doctor_id),
        "created_at": patient.created_at,
        "updated_at": patient.updated_at,
    }


@router.delete(
    "/{patient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete patient",
    description="Delete a patient record (ADMIN/DOCTOR only)"
)
@limiter.limit("10/hour")
async def delete_patient(
    request: Request,
    patient_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """
    Delete a patient.
    
    Note: This performs a hard delete. Consider implementing soft delete
    by adding an is_active or deleted_at field to the Patient model.
    """
    from uuid import UUID
    
    try:
        patient_uuid = UUID(patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format"
        )
    
    patient = db.query(Patient).filter(Patient.id == patient_uuid).first()
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with id {patient_id} not found"
        )
    
    db.delete(patient)
    db.commit()
    
    return None
