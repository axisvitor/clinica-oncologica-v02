"""
Patient CRUD Operations API v2
Core CRUD endpoints for patient management with enhanced features.

This module provides:
- List patients with cursor pagination, field selection, and eager loading
- Search patients by name or email
- Get single patient by ID
- Create new patient with validation and Saga orchestration
- Update patient information (partial updates)
"""

from typing import Optional, List
from datetime import date
from uuid import UUID
import json
import base64
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func

from app.database import get_db
from app.models.patient import Patient, FlowState
from app.models.user import User, UserRole
from app.repositories.patient import PatientRepository
from app.services.flow_engine import FlowEngine
from app.services.patient import PatientService, PatientIntegrityService
from app.schemas.patient import PatientCreate
from app.schemas.v2.patient import (
    PatientV2Response,
    PatientV2List,
    PatientV2Create,
    PatientV2Update,
)
from .dependencies import (
    get_pagination_params,
    get_field_selection,
    get_eager_load_params,
    apply_field_selection,
)
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.utils.rate_limiter import limiter

# Import utility functions from patients_utils
from .patients_utils import (
    _get_current_user_simple,
    _extract_user_context,
    _ensure_uuid,
    _ensure_patient_access,
    _normalize_cpf,
    _normalize_phone,
    _serialize_patient,
)

router = APIRouter()
logger = logging.getLogger(__name__)


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
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by patient status/flow state"),
    treatment_type: Optional[str] = Query(None, description="Filter by treatment type"),
    start_date_from: Optional[date] = Query(None, description="Filter patients with treatment_start_date on or after this date"),
    start_date_to: Optional[date] = Query(None, description="Filter patients with treatment_start_date on or before this date"),
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

    # Filter out soft-deleted patients by default
    filters.append(Patient.deleted_at.is_(None))

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

    if status_filter:
        status_value = status_filter.strip().lower()
        status_aliases = {
            "inactive": FlowState.CANCELLED,
            "canceled": FlowState.CANCELLED,
            "cancelled": FlowState.CANCELLED,
        }
        target_state = status_aliases.get(status_value)
        if target_state is None:
            try:
                target_state = FlowState(status_value)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid status filter. Use active, paused, completed, cancelled or inactive."
                )
        filters.append(Patient.flow_state == target_state)

    if treatment_type:
        filters.append(Patient.treatment_type.ilike(f"%{treatment_type.strip()}%"))

    if start_date_from:
        filters.append(Patient.treatment_start_date >= start_date_from)

    if start_date_to:
        filters.append(Patient.treatment_start_date <= start_date_to)

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
        cursor_data = {
            "id": str(patients[-1].id),
            "created_at": patients[-1].created_at.isoformat()
        }
        next_cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()

    # Convert to response models
    patient_responses = []
    for patient in patients:
        patient_dict = _serialize_patient(patient)

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
    "/search",
    response_model=List[PatientV2Response],
    summary="Search patients",
    description="Search patients by name or email (doctor/admin only)",
)
@limiter.limit("120/minute")
async def search_patients(
    q: str = Query(..., min_length=1, description="Search term"),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    query = db.query(Patient).filter(Patient.deleted_at.is_(None))

    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to determine user permissions",
            )
        query = query.filter(Patient.doctor_id == current_user_uuid)

    search_filter = f"%{q}%"
    patients = (
        query.filter(
            (Patient.name.ilike(search_filter)) | (Patient.email.ilike(search_filter))
        )
        .order_by(Patient.created_at.desc())
        .limit(limit)
        .all()
    )

    return [_serialize_patient(patient) for patient in patients]


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

    patient = query.filter(
        Patient.id == patient_uuid,
        Patient.deleted_at.is_(None)
    ).first()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with id {patient_id} not found"
        )

    _ensure_patient_access(current_user, patient.doctor_id)

    _ensure_patient_access(current_user, patient.doctor_id)

    # Build response
    patient_dict = _serialize_patient(patient)

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
    current_user = Depends(_get_current_user_simple),
):
    """
    Create a new patient.

    Validates:
    - Doctor exists
    - Email is unique (if provided)
    - CPF is unique (if provided)
    - Phone is unique
    """
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
        existing_email = db.query(Patient).filter(
            Patient.email == patient_data.email,
            Patient.deleted_at.is_(None)
        ).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Patient with email {patient_data.email} already exists"
            )

    # Check CPF uniqueness (if provided)
    if normalized_cpf:
        existing_cpf = db.query(Patient).filter(
            Patient.cpf == normalized_cpf,
            Patient.deleted_at.is_(None)
        ).first()
        if existing_cpf:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Patient with CPF already exists"
            )

    # Check phone uniqueness (required field)
    if normalized_phone:
        existing_phone = db.query(Patient).filter(
            Patient.phone == normalized_phone,
            Patient.deleted_at.is_(None)
        ).first()
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Patient with phone already exists"
            )

    # Use service layer (Saga + welcome WhatsApp + auto flow) for creation
    # Ensure phone matches PatientCreate validator (E.164 starting with '+')
    e164_phone = normalized_phone if (normalized_phone and normalized_phone.startswith('+')) else (f"+{normalized_phone}" if normalized_phone else None)
    if not e164_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number is required"
        )

    # Instantiate services directly (thread-safe per-request pattern)
    patient_repo = PatientRepository(db)
    integrity_service = PatientIntegrityService(db, patient_repo)
    flow_engine = FlowEngine(db)

    # Create SagaOrchestrator using the same DB session to maintain consistency
    saga_orchestrator = None
    try:
        from app.coordination.saga_orchestrator import SagaOrchestrator
        from app.core.redis_client import get_redis_client
        from app.integrations.evolution import EvolutionClient

        saga_orchestrator = SagaOrchestrator(
            db=db,
            redis=get_redis_client(),
            evolution_client=EvolutionClient()
        )
    except Exception as e:
        logger.warning(f"Failed to initialize SagaOrchestrator: {e}. Patient will be created without Saga.")

    service = PatientService(
        db=db,
        patient_repository=patient_repo,
        integrity_service=integrity_service,
        flow_engine=flow_engine,
        saga_orchestrator=saga_orchestrator
    )

    created = await service.create_patient(
        patient_data=PatientCreate(
            phone=e164_phone,
            name=patient_data.name,
            email=patient_data.email,
            birth_date=patient_data.birth_date,
            cpf=normalized_cpf,
            treatment_type=patient_data.treatment_type,
            treatment_start_date=patient_data.treatment_start_date,
            doctor_notes=patient_data.doctor_notes,
            diagnosis=patient_data.diagnosis,
            treatment_phase=patient_data.treatment_phase,
        ),
        doctor_id=doctor_uuid,
        current_user=current_user,
    )

    # Return formatted response from created entity
    return _serialize_patient(created)


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
    try:
        patient_uuid = UUID(patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format"
        )

    patient = db.query(Patient).filter(
        Patient.id == patient_uuid,
        Patient.deleted_at.is_(None)
    ).first()

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
                Patient.id != patient.id,
                Patient.deleted_at.is_(None)
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
                Patient.id != patient.id,
                Patient.deleted_at.is_(None)
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
    return _serialize_patient(patient)
