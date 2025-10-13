"""
Patient management endpoints for Hormonia Backend System.
"""
from datetime import date
from typing import List, Optional
from uuid import UUID
import logging

import math

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.dependencies import get_current_user, get_db, get_patient_service
from app.models.patient import FlowState
from app.models.user import User, UserRole
from app.schemas.patient import PatientCreate, PatientUpdate, PatientResponse, PatientListResponse
from app.services.patient import PatientService
from app.middleware.rls_middleware import (
    get_jwt_token, get_user_context, require_authentication,
    optional_authentication, rls_middleware
)
from app.core.database import get_db, RLSError, RLSAccessDeniedError
from app.utils.unified_cache import (
    cache_patient_data,
    get_cached_patient_data,
    invalidate_patient_cache,
    get_unified_cache_manager as get_cache_manager
)
from app.middleware.cache_middleware import invalidate_http_cache_for_path

router = APIRouter()


def _role_value(user: User) -> str:
    """Return normalized role string for the given user."""
    role = getattr(user, "role", None)
    if isinstance(role, UserRole):
        return role.value
    return str(role or "").lower()


def _can_manage_patient(patient, user: User) -> bool:
    """
    Determine if the current user can manage (update/delete/state-change) the patient.

    - Treating doctor always has access.
    - Admin users have system-wide access, including unassigned patients.
    """
    if patient is None or user is None:
        return False

    if patient.doctor_id == user.id:
        return True

    if _role_value(user) == UserRole.ADMIN.value:
        return True

    return False


@router.get(
    "", 
    response_model=PatientListResponse,
    summary="List Patients",
    description="""
    Retrieve a paginated list of patients assigned to the authenticated healthcare provider.
    
    This endpoint returns patients with their basic information, treatment status,
    and current flow state. Results are filtered by the authenticated user's permissions.
    
    **Pagination**: Use `page` and `size` query parameters to navigate through results.
    **Filtering**: Optional filters include `status`, `treatment_type`, `search`, `start_date_from` and `start_date_to`.
    """,
    responses={
        200: {
            "description": "Patients retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "name": "Jane Doe",
                                "phone": "+1234567890",
                                "email": "jane@example.com",
                                "treatment_type": "hormone_therapy",
                                "current_day": 15,
                                "flow_state": "active",
                                "created_at": "2024-01-01T00:00:00Z"
                            }
                        ],
                        "total": 1,
                        "page": 1,
                        "limit": 20,
                        "pages": 1,
                        "has_more": False,
                        "has_previous": False
                    }
                }
            }
        },
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"}
    }
)
async def list_patients(
    request: Request,
    page: int = Query(1, ge=1, description="Current page number"),
    size: int = Query(20, ge=1, le=100, description="Number of records per page"),
    search: Optional[str] = Query(None, description="Search by patient name, email, or phone number"),
    status: Optional[FlowState] = Query(None, description="Filter by patient flow status"),
    treatment_type: Optional[str] = Query(None, description="Filter by treatment type"),
    start_date_from: Optional[date] = Query(None, description="Include patients with treatment start date on or after this date"),
    start_date_to: Optional[date] = Query(None, description="Include patients with treatment start date on or before this date"),
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    user_context: dict = Depends(require_authentication),
    jwt_token: Optional[str] = Depends(get_jwt_token),
):
    """List patients with pagination and optional filtering."""
    
    # Log request details for debugging
    logger.info(f"List patients request - User: {current_user.id}, Page: {page}, Size: {size}, Search: {search}")
    
    # Additional validation to catch problematic requests
    if size > 100:
        logger.warning(f"Invalid size parameter: {size} from user {current_user.id}. Clamping to 100.")
        size = 100
    
    try:
        # Get RLS-aware database session
        from app.core.database import get_db
        db_generator = get_db(jwt_token=jwt_token, user_id=user_context.get('user_id'))
        db = next(db_generator)
        try:
            # Use the existing patient_service from dependency injection
            patients, total = patient_service.list_patients(
                doctor_id=current_user.id,
                page=page,
                size=size,
                search=search,
                flow_state=status,
                treatment_type=treatment_type,
                start_date_from=start_date_from,
                start_date_to=start_date_to,
            )
        finally:
            db.close()
    except RLSError as e:
        logger.error(f"RLS error in list_patients: {e}")
        raise rls_middleware.handle_rls_error(e, user_context)
    except RequestValidationError as e:
        logger.error(f"Validation error in list_patients: {e}")
        raise HTTPException(
            status_code=422,
            detail=f"Invalid request parameters: {e.errors()}"
        )
    except Exception as e:
        logger.error(f"Error listing patients: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve patients"
        )

    pages = math.ceil(total / size) if total else 0
    has_more = page * size < total
    has_previous = page > 1 and total > 0

    return PatientListResponse(
        data=[PatientResponse.from_orm(p) for p in patients],
        total=total,
        page=page,
        limit=size,
        pages=pages,
        has_more=has_more,
        has_previous=has_previous,
    )


@router.post("/{patient_id}/pause", response_model=PatientResponse)
async def pause_patient(
    patient_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    user_context: dict = Depends(require_authentication),
    jwt_token: Optional[str] = Depends(get_jwt_token),
):
    """Pause patient flow."""
    try:
        # Get RLS-aware database session
        from app.core.database import get_db
        db_generator = get_db(jwt_token=jwt_token, user_id=user_context.get('user_id'))
        db = next(db_generator)
        try:
            # Use the existing patient_service from dependency injection
            patient = patient_service.get_patient(patient_id)
            if not patient:
                raise HTTPException(
                    status_code=404,
                    detail="Patient not found"
                )

            # Check if current user is the patient's doctor
            if patient.doctor_id != current_user.id:
                raise HTTPException(
                    status_code=403,
                    detail="Not authorized to pause this patient"
                )

            paused_patient = await patient_service.pause_patient(patient_id)
            if not paused_patient:
                raise HTTPException(
                    status_code=400,
                    detail="Failed to pause patient"
                )

            return PatientResponse.from_orm(paused_patient)
        finally:
            db.close()

    except RLSError as e:
        logger.error(f"RLS error in pause_patient: {e}")
        raise rls_middleware.handle_rls_error(e, user_context)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pausing patient: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to pause patient"
        )


@router.get("/{patient_id}/timeline", response_model=None)
async def get_patient_timeline(
    patient_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    user_context: dict = Depends(require_authentication),
    jwt_token: Optional[str] = Depends(get_jwt_token),
):
    """Get patient timeline with caching."""
    try:
        # Get RLS-aware database session
        from app.core.database import get_db
        db_generator = get_db(jwt_token=jwt_token, user_id=user_context.get('user_id'))
        db = next(db_generator)
        try:
            # Try to get from cache first
            cached_data = get_cached_patient_data(str(patient_id))
            if cached_data:
                patient = cached_data
            else:
                patient = patient_service.get_patient(patient_id)
                if not patient:
                    raise HTTPException(
                        status_code=404,
                        detail="Patient not found"
                    )
                # Cache patient data for future requests
                cache_patient_data(str(patient_id), patient.__dict__, ttl=3600)

            # Check if current user is the patient's doctor
            patient_dict = patient if isinstance(patient, dict) else patient.__dict__
            if patient_dict.get("doctor_id") != current_user.id:
                raise HTTPException(
                    status_code=403,
                    detail="Not authorized to access this patient's timeline"
                )
        finally:
            db.close()

    except RLSError as e:
        logger.error(f"RLS error in get_patient_timeline: {e}")
        raise rls_middleware.handle_rls_error(e, user_context)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting patient timeline: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve patient timeline"
        )

    # This would typically include messages, quiz responses, alerts, etc.
    # For now, return basic patient info
    return {
        "patient_id": patient_id,
        "timeline": [
            {
                "date": patient_dict.get("created_at"),
                "event": "Patient created",
                "details": f"Patient {patient_dict.get('name')} was added to the system"
            }
        ]
    }


@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Get Patient by ID",
    description="Retrieve a specific patient by their ID"
)
async def get_patient(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service)
):
    """Get a specific patient by ID."""
    patient = patient_service.get_patient(patient_id)
    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found"
        )

    # Check if current user is the patient's doctor
    if patient.doctor_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to access this patient"
        )

    return PatientResponse.from_orm(patient)


@router.post(
    "",
    response_model=PatientResponse,
    status_code=201,
    summary="Create Patient",
    description="Create a new patient"
)
async def create_patient(
    patient_data: PatientCreate,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service)
):
    """Create a new patient."""
    try:
        patient = await patient_service.create_patient(
            patient_data=patient_data,
            doctor_id=current_user.id,
            current_user=current_user
        )
        return PatientResponse.from_orm(patient)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.put(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Update Patient",
    description="Update an existing patient"
)
async def update_patient(
    patient_id: UUID,
    patient_data: PatientUpdate,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service)
):
    """Update an existing patient."""
    patient = patient_service.get_patient(patient_id)
    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found"
        )

    if not _can_manage_patient(patient, current_user):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to update this patient"
        )

    try:
        updated_patient = patient_service.update_patient(
            patient_id=patient_id,
            **patient_data.dict(exclude_unset=True)
        )

        # Invalidate cache after update
        invalidate_patient_cache(str(patient_id))

        return PatientResponse.from_orm(updated_patient)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.delete(
    "/{patient_id}",
    status_code=204,
    summary="Delete Patient",
    description="Delete a patient (soft delete)"
)
async def delete_patient(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service)
):
    """Delete a patient (soft delete)."""
    patient = patient_service.get_patient(patient_id)
    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found"
        )

    if not _can_manage_patient(patient, current_user):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to delete this patient"
        )

    patient_service.delete_patient(patient_id)

    # Invalidate cache after deletion
    invalidate_patient_cache(str(patient_id))


@router.post(
    "/{patient_id}/activate",
    response_model=PatientResponse,
    summary="Activate Patient",
    description="Activate a patient's treatment flow"
)
async def activate_patient(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service)
):
    """Activate a patient's treatment flow."""
    patient = patient_service.get_patient(patient_id)
    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found"
        )

    if not _can_manage_patient(patient, current_user):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to activate this patient"
        )

    try:
        updated_patient = patient_service.activate_patient(patient_id)

        # Invalidate cache after activation
        invalidate_patient_cache(str(patient_id))

        return PatientResponse.from_orm(updated_patient)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.post(
    "/{patient_id}/deactivate",
    response_model=PatientResponse,
    summary="Deactivate Patient",
    description="Deactivate a patient's treatment flow"
)
async def deactivate_patient(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service)
):
    """Deactivate a patient's treatment flow."""
    patient = patient_service.get_patient(patient_id)
    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found"
        )

    if not _can_manage_patient(patient, current_user):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to deactivate this patient"
        )

    try:
        updated_patient = patient_service.deactivate_patient(patient_id)

        # Invalidate cache after deactivation
        invalidate_patient_cache(str(patient_id))

        return PatientResponse.from_orm(updated_patient)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.post("/cache/invalidate/{patient_id}", status_code=204)
async def invalidate_patient_cache_endpoint(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Invalidate cache entries for a specific patient (admin only).
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only administrators can invalidate cache"
        )

    # Invalidate patient-specific caches
    invalidate_patient_cache(str(patient_id))

    # Invalidate related cache patterns
    cache_manager = get_cache_manager()
    cache_manager.invalidate_pattern(f"patient_by_id:*:{patient_id}*", namespace="cache")
    cache_manager.invalidate_pattern(f"*:{patient_id}*", namespace="patients")

    # Invalidate HTTP response cache
    invalidate_http_cache_for_path(f"/api/v1/patients/{patient_id}")

    logger.info("Cache invalidated for patient %s by admin %s", patient_id, current_user.email)
    return None


@router.post("/cache/invalidate-all", status_code=204)
async def invalidate_all_patient_caches(
    current_user: User = Depends(get_current_user),
):
    """
    Invalidate all patient caches (Admin only).

    This endpoint allows administrators to clear all cached patient data
    across the system. Use with caution as it may impact performance.
    """
    # Check if user has admin role
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only administrators can invalidate cache"
        )

    # Invalidate all patient-related caches
    cache_manager = get_cache_manager()
    patient_count = cache_manager.invalidate_namespace("patients")
    cache_count = cache_manager.invalidate_pattern("patient_*", namespace="cache")
    http_cache_count = invalidate_http_cache_for_path("/api/v1/patients")

    total_invalidated = patient_count + cache_count + http_cache_count

    logger.info(
        f"All patient caches invalidated by admin {current_user.email}: "
        f"{total_invalidated} entries cleared"
    )

    return None




