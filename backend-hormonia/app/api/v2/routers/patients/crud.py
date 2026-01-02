"""
Patients API v2 - CRUD Operations

This module handles core patient CRUD operations:
- List patients with advanced filtering and pagination
- Get patient by ID
- Create new patient with saga orchestration
- Update patient data
- Delete patient (soft delete)

Migrated from: app/api/v2/routers/patients.py
Lines: 50-372
"""

# Standard library imports
# NOTE: Removed 'from __future__ import annotations' to fix Pydantic/FastAPI
# OpenAPI schema generation issues with Query() and Depends() parameters
import logging
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

# Third-party imports
from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.orm import Session

# Local application imports
from app.api.v2.dependencies import (
    apply_field_selection,
    get_eager_load_params,
    get_field_selection,
    get_pagination_params,
)
from app.core.authorization import (
    require_doctor_or_admin,
    require_permission,
)
from app.core.exceptions import (
    BusinessRuleError,
    ForbiddenError,
    NotFoundError,
    PatientNotFoundError,
    ServiceUnavailableError,
    ValidationError,
)
from app.core.permissions import Permission
from app.database import get_db
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.models.user import UserRole
from app.repositories.patient import PatientRepository
from app.schemas.patient import PatientCreate, PatientUpdate as DomainPatientUpdate
from app.schemas.v2.patient import (
    PatientV2Create,
    PatientV2List,
    PatientV2Response,
    PatientV2Update,
)
from app.services.patient import PatientIntegrityService
from app.services.patient.crud_service import PatientCRUDService
from app.utils.rate_limiter import limiter

# Import shared utilities from base module
from .base import (
    ensure_patient_access,
    ensure_uuid,
    extract_user_context,
    serialize_patient,
    serialize_patient_with_includes,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/",
    response_model=PatientV2List,
    status_code=status.HTTP_200_OK,
    summary="List patients with pagination",
    description="Get paginated list of patients with optional field selection and eager loading",
)
@require_permission(Permission.PATIENT_READ)
@limiter.limit("120/minute")
async def list_patients(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    pagination=Depends(get_pagination_params),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    search: Optional[str] = Query(None, description="Search by name or email"),
    status_filter: Optional[str] = Query(
        None, alias="status", description="Filter by patient status/flow state"
    ),
    treatment_type: Optional[str] = Query(None, description="Filter by treatment type"),
    start_date_from: Optional[date] = Query(
        None,
        description="Filter patients with treatment_start_date on or after this date",
    ),
    start_date_to: Optional[date] = Query(
        None,
        description="Filter patients with treatment_start_date on or before this date",
    ),
    treatment_phase: Optional[str] = Query(
        None, description="Filter by treatment phase"
    ),
    has_active_flow: Optional[bool] = Query(
        None, description="Filter by active flow state"
    ),
    created_after: Optional[datetime] = Query(
        None, description="Filter patients created after this datetime"
    ),
    created_before: Optional[datetime] = Query(
        None, description="Filter patients created before this datetime"
    ),
    sort_by: Optional[str] = Query("created_at", description="Sort by field"),
    sort_order: Optional[str] = Query(
        "desc", pattern="^(asc|desc)$", description="Sort order"
    ),
):
    """
    List patients with advanced filtering and pagination.

    Args:
        request: FastAPI request object.
        db: Database session.
        current_user: Authenticated user from session.
        pagination: Pagination parameters (cursor, limit).
        fields: Optional list of fields to include in response.
        include: Optional list of relations to eager load.
        search: Search query for name or email.
        status_filter: Filter by patient flow state.
        treatment_type: Filter by treatment type.
        start_date_from: Filter by treatment start date (from).
        start_date_to: Filter by treatment start date (to).
        treatment_phase: Filter by treatment phase.
        has_active_flow: Filter by active flow state.
        created_after: Filter by creation date (after).
        created_before: Filter by creation date (before).
        sort_by: Field to sort by.
        sort_order: Sort order (asc/desc).

    Returns:
        PatientV2List with paginated patient data.

    Raises:
        ForbiddenError: 403 if unable to determine user context (non-admin).
        ServiceUnavailableError: 500 if internal server error occurs.
    """
    try:
        repo = PatientRepository(db)
        role_enum, user_id = await extract_user_context(current_user)
        current_user_uuid = await ensure_uuid(user_id)

        # Build filters
        filters = {
            "search": search,
            "status": status_filter,
            "treatment_type": treatment_type,
            "treatment_phase": treatment_phase,
            "start_date_from": start_date_from,
            "start_date_to": start_date_to,
            "has_active_flow": has_active_flow,
            "created_after": created_after,
            "created_before": created_before,
        }

        # RBAC: Non-admin users can only see their own patients
        if role_enum != UserRole.ADMIN:
            if not current_user_uuid:
                logger.warning("Unable to determine user context for non-admin user")
                raise ForbiddenError("Unable to determine user context")
            filters["doctor_id"] = current_user_uuid

        # Execute query via repository
        patients, has_more, next_cursor, total = repo.list_v2(
            filters=filters,
            cursor_data=pagination["cursor_data"],
            limit=pagination["limit"],
            sort_by=sort_by,
            sort_order=sort_order,
            eager_load=include,
        )

        # Serialize response
        patient_responses = []
        for patient in patients:
            patient_dict = await serialize_patient_with_includes(patient, include)

            if fields:
                patient_dict = apply_field_selection(patient_dict, fields)
            patient_responses.append(patient_dict)

        return {
            "data": patient_responses,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": total,
        }

    except (ForbiddenError, ValidationError, NotFoundError):
        raise
    except Exception as e:
        logger.error(f"Unexpected error listing patients: {e}", exc_info=True)
        raise ServiceUnavailableError("Internal server error")


@router.get(
    "/{patient_id}",
    response_model=PatientV2Response,
    status_code=status.HTTP_200_OK,
    summary="Get patient by ID",
    description="Retrieve a single patient by their unique ID with optional field selection and eager loading",
)
@require_permission(Permission.PATIENT_READ)
@limiter.limit("120/minute")
async def get_patient(
    request: Request,
    patient_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
):
    """
    Get a single patient by ID.

    Args:
        request: FastAPI request object.
        patient_id: Patient UUID as string.
        db: Database session.
        current_user: Authenticated user from session.
        fields: Optional list of fields to include in response.
        include: Optional list of relations to eager load.

    Returns:
        PatientV2Response with patient data.

    Raises:
        ValidationError: 422 if patient ID format is invalid.
        ForbiddenError: 403 if user lacks permissions to access patient.
        PatientNotFoundError: 404 if patient not found.
        ServiceUnavailableError: 500 if internal server error occurs.
    """
    try:
        patient_uuid = UUID(patient_id)
    except ValueError as e:
        logger.warning(f"Invalid patient ID format: {patient_id}", extra={"error": str(e)})
        raise ValidationError("Invalid patient ID format", field="patient_id")

    try:
        repo = PatientRepository(db)
        patient = repo.get_by_id(patient_uuid, eager_load=True)

        if not patient:
            logger.warning(f"Patient not found: {patient_id}")
            raise PatientNotFoundError(patient_id)

        await ensure_patient_access(current_user, patient.doctor_id)

        # Serialize
        patient_dict = await serialize_patient_with_includes(patient, include)

        if fields:
            patient_dict = apply_field_selection(patient_dict, fields)

        return patient_dict

    except (ForbiddenError, ValidationError, NotFoundError, PatientNotFoundError):
        raise
    except Exception as e:
        logger.error(f"Unexpected error retrieving patient {patient_id}: {e}", exc_info=True)
        raise ServiceUnavailableError("Internal server error")


@router.post(
    "/",
    response_model=PatientV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Create new patient",
    description="Create a new patient with saga orchestration, WhatsApp registration, and idempotency support",
)
@require_doctor_or_admin()
@limiter.limit("1000/hour")  # TEMPORARILY INCREASED FOR TESTING (was 20/hour)
async def create_patient(
    request: Request,
    patient_data: PatientV2Create,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    """
    Create a new patient with full saga orchestration.

    Args:
        request: FastAPI request object.
        patient_data: Patient creation data.
        db: Database session.
        current_user: Authenticated user from session.
        x_idempotency_key: Optional idempotency key for duplicate request prevention.

    Returns:
        PatientV2Response with created patient data.

    Raises:
        ValidationError: 422 if doctor ID format is invalid.
        ForbiddenError: 403 if doctor tries to create patient for another doctor.
        BusinessRuleError: 400 if creation fails.
    """
    # QW-004: Database-level idempotency key support for duplicate request prevention
    if x_idempotency_key:
        repo = PatientRepository(db)
        existing = repo.get_by_idempotency_key(x_idempotency_key)
        if existing:
            logger.info(
                f"Idempotency key {x_idempotency_key} already processed (DB), returning existing patient"
            )
            return await serialize_patient(existing)

        # QW-006: Redis cache fallback for fast idempotency checks (secondary layer)
        from app.core.redis_client import get_redis_client

        redis = get_redis_client()
        if redis:
            try:
                cache_key = f"idempotency:patient:create:{x_idempotency_key}"
                cached_result = redis.get(cache_key)
                if cached_result:
                    import json

                    logger.info(
                        f"Idempotency key {x_idempotency_key} found in Redis cache"
                    )
                    return json.loads(cached_result)
            except Exception as redis_err:
                logger.debug(
                    f"Idempotency cache check failed (non-critical): {redis_err}"
                )

    try:
        # Handle both UUID and string types
        if isinstance(patient_data.doctor_id, UUID):
            doctor_uuid = patient_data.doctor_id
        else:
            doctor_uuid = UUID(str(patient_data.doctor_id))
    except (ValueError, AttributeError):
        raise ValidationError("Invalid doctor ID format", field="doctor_id")

    # Authorization: Doctors can only create patients for themselves
    role_enum, user_id = await extract_user_context(current_user)
    current_user_uuid = await ensure_uuid(user_id)
    if role_enum != UserRole.ADMIN:
        if not current_user_uuid or current_user_uuid != doctor_uuid:
            raise ForbiddenError("Doctors can only create patients for themselves")

    # Initialize coordinator via factory
    from app.services.patient.onboarding_factory import get_onboarding_coordinator
    from app.orchestration.saga_orchestrator import SagaOrchestrator
    from app.core.redis_client import get_redis_client
    from app.integrations.evolution import EvolutionClient

    saga_orchestrator = SagaOrchestrator(
        db=db, redis_client=get_redis_client(), evolution_client=EvolutionClient()
    )

    coordinator = get_onboarding_coordinator(db, saga_orchestrator)

    try:
        # Create using specialized Onboarding Coordinator
        created = await coordinator.create_patient(
            patient_data=PatientCreate(
                phone=patient_data.phone,
                name=patient_data.name,
                email=patient_data.email,
                birth_date=patient_data.birth_date,
                cpf=patient_data.cpf,
                treatment_type=patient_data.treatment_type,
                treatment_start_date=patient_data.treatment_start_date,
                doctor_notes=patient_data.doctor_notes,
                diagnosis=patient_data.diagnosis,
                treatment_phase=patient_data.treatment_phase,
                timezone=patient_data.timezone,
            ),
            doctor_id=doctor_uuid,
            current_user=current_user,
            idempotency_key=x_idempotency_key,  # QW-004: Pass idempotency key to coordinator
        )
        result = await serialize_patient(created)

        # QW-006: Store result with idempotency key in Redis (TTL: 24 hours) as secondary cache
        if x_idempotency_key:
            from app.core.redis_client import get_redis_client

            redis = get_redis_client()
            if redis:
                try:
                    import json

                    cache_key = f"idempotency:patient:create:{x_idempotency_key}"
                    redis.setex(cache_key, 86400, json.dumps(result, default=str))
                except Exception as redis_err:
                    logger.debug(
                        f"Idempotency cache store failed (non-critical): {redis_err}"
                    )

        return result

    except (ForbiddenError, ValidationError, NotFoundError, BusinessRuleError):
        raise
    except Exception as e:
        if hasattr(e, "status_code"):
            raise e
        logger.error(f"Error creating patient: {e}", exc_info=True)
        raise BusinessRuleError("Failed to create patient")


@router.patch(
    "/{patient_id}", response_model=PatientV2Response, summary="Update patient"
)
@require_permission(Permission.PATIENT_UPDATE)
@limiter.limit("30/hour")
async def update_patient(
    request: Request,
    patient_id: str,
    patient_data: PatientV2Update,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    """
    Update patient data.

    Features:
    - Partial updates (only provided fields are updated)
    - Data integrity validation
    - RBAC: Doctors cannot reassign patients to other doctors
    - Uses CRUD service layer for business logic

    Raises:
        ValidationError: 422 if patient ID format is invalid or data validation fails.
        PatientNotFoundError: 404 if patient not found.
        ForbiddenError: 403 if doctor tries to reassign patient.
        ServiceUnavailableError: 500 if update fails.
    """
    try:
        # Handle both UUID and string types
        if isinstance(patient_id, UUID):
            patient_uuid = patient_id
        else:
            patient_uuid = UUID(str(patient_id))
    except (ValueError, AttributeError):
        raise ValidationError("Invalid patient ID", field="patient_id")

    # Initialize services
    repo = PatientRepository(db)
    crud_service = PatientCRUDService(db, repo)
    integrity_service = PatientIntegrityService(db, repo)

    # Check existence and permissions
    patient = repo.get_by_id(patient_uuid, eager_load=False)
    if not patient:
        raise PatientNotFoundError(str(patient_uuid))

    await ensure_patient_access(current_user, patient.doctor_id)

    # Validate update data
    update_dict = patient_data.dict(exclude_unset=True)

    if update_dict:
        try:
            validated = integrity_service.validate_patient_data(
                patient_data=patient_data,
                doctor_id=patient.doctor_id,
                patient_id=patient_uuid,
                is_update=True,
            )
            # Use validated data
            for k, v in validated.items():
                if k != "validation_errors" and v is not None:
                    if hasattr(patient_data, k):
                        setattr(patient_data, k, v)
        except Exception as e:
            logger.error(f"Error validating patient data: {e}", exc_info=True)
            raise ValidationError("Invalid patient data")

    # Handle doctor reassignment check
    if patient_data.doctor_id:
        role_enum, user_id = await extract_user_context(current_user)
        if role_enum != UserRole.ADMIN:
            if str(patient_data.doctor_id) != str(patient.doctor_id):
                raise ForbiddenError("Doctors cannot reassign patients")

    # Delegate to CRUD service
    domain_update = DomainPatientUpdate(**patient_data.dict(exclude_unset=True))
    updated_patient = crud_service.update_patient(patient_uuid, domain_update)

    if not updated_patient:
        raise ServiceUnavailableError("Failed to update patient")

    return await serialize_patient(updated_patient)


@router.delete("/{patient_id}", summary="Soft delete patient")
@limiter.limit("10/hour")  # Strict rate limit for deletions
async def delete_patient(
    request: Request,  # Required for rate limiter
    patient_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    """
    Soft delete a patient.

    The patient is marked as deleted but not removed from the database.
    This preserves data for audit purposes.

    Raises:
        ValidationError: 422 if patient ID format is invalid.
        PatientNotFoundError: 404 if patient not found.
        ServiceUnavailableError: 500 if deletion fails.
    """
    try:
        # Handle both UUID and string types
        if isinstance(patient_id, UUID):
            pid = patient_id
        else:
            pid = UUID(str(patient_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Invalid patient_id UUID", field="patient_id")

    # Initialize CRUD service
    repo = PatientRepository(db)
    service = PatientCRUDService(db, repo)

    # Check existence
    patient = repo.get_by_id(pid)
    if not patient:
        raise PatientNotFoundError(str(pid))

    success = service.delete_patient(pid)
    if not success:
        raise ServiceUnavailableError("Failed to delete patient")

    return {"message": "Patient soft deleted"}
