"""
CRUD endpoints for physicians (list, get, create, update, delete).
"""

import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.models.user import User, UserRole
from app.models.patient import Patient, FlowState
from app.schemas.v2.physicians import (
    PhysicianResponse,
    PhysicianList,
    PhysicianUpdate,
    PhysicianStatus,
    WorkloadLevel,
    Specialty,
)
from app.api.v2.dependencies import (
    get_pagination_params,
    get_field_selection,
    get_eager_load_params,
    apply_field_selection,
)
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.utils.rate_limiter import limiter

from .base import (
    _extract_user_context,
    _is_admin,
    _calculate_workload_level,
    validate_physician_access,
)
from .services import PhysicianStatisticsService

router = APIRouter()
logger = logging.getLogger(__name__)


async def _run_sync(db: AsyncSession, operation):
    if hasattr(db, "run_sync"):
        return await db.run_sync(operation)
    sync_db = getattr(db, "_sync_session", db)
    return operation(sync_db)


async def _serialize_physician(
    physician: User,
    db: AsyncSession,
    include_statistics: bool = False,
) -> Dict[str, Any]:
    """
    Serialize physician User model to API response dict.

    Args:
        physician: User model instance
        db: Database session
        include_statistics: Whether to include detailed statistics

    Returns:
        Dictionary with physician data
    """
    # Count assigned patients (optimized single query)
    total_patients_result = await db.execute(
        select(func.count())
        .select_from(Patient)
        .filter(Patient.doctor_id == physician.id, Patient.deleted_at.is_(None))
    )
    total_patients = total_patients_result.scalar_one()

    active_patients_result = await db.execute(
        select(func.count())
        .select_from(Patient)
        .filter(
            Patient.doctor_id == physician.id,
            Patient.flow_state == FlowState.ACTIVE,
            Patient.deleted_at.is_(None),
        )
    )
    active_patients = active_patients_result.scalar_one()

    workload_level = _calculate_workload_level(total_patients)

    # Get specialties from canonical storage.
    specialties = (
        physician.get_specialties_data()
        if hasattr(physician, "get_specialties_data")
        else []
    )

    # Get status
    status_value = (
        PhysicianStatus.ACTIVE if physician.is_active else PhysicianStatus.INACTIVE
    )

    display_name = (
        physician.get_display_name()
        if hasattr(physician, "get_display_name")
        else physician.full_name
    )
    photo_url = (
        physician.get_photo_url()
        if hasattr(physician, "get_photo_url")
        else getattr(physician, "photo_url", None)
    )
    email_verified = (
        physician.get_email_verified()
        if hasattr(physician, "get_email_verified")
        else getattr(physician, "email_verified", False)
    )
    last_login = (
        physician.get_last_login()
        if hasattr(physician, "get_last_login")
        else getattr(physician, "last_login", None)
    )

    # Base response
    response = {
        "id": str(physician.id),
        "email": physician.email,
        "full_name": physician.full_name or display_name,
        "role": physician.role.value
        if hasattr(physician.role, "value")
        else str(physician.role),
        "is_active": physician.is_active,
        "email_verified": email_verified,
        "display_name": display_name,
        "photo_url": photo_url,
        "specialties": specialties,
        "status": status_value.value,
        "license_number": physician.get_license_number()
        if hasattr(physician, "get_license_number")
        else None,
        "phone": physician.get_phone() if hasattr(physician, "get_phone") else None,
        "bio": physician.get_bio() if hasattr(physician, "get_bio") else None,
        "assigned_patients_count": total_patients,
        "active_patients_count": active_patients,
        "workload_level": workload_level.value,
        "created_at": physician.created_at,
        "updated_at": physician.updated_at,
        "last_login": last_login,
    }

    # Add statistics if requested
    if include_statistics:
        statistics = await PhysicianStatisticsService(db).calculate_statistics(
            physician.id
        )
        response["statistics"] = statistics.model_dump()

    return response


@router.get(
    "/",
    response_model=PhysicianList,
    summary="List physicians with filtering",
    description="Get paginated list of physicians with optional filtering and statistics.",
)
@limiter.limit("60/minute")
async def list_physicians(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
    pagination=Depends(get_pagination_params),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    specialty: Optional[Specialty] = Query(None, description="Filter by specialty"),
    status: Optional[PhysicianStatus] = Query(None, description="Filter by status"),
    workload: Optional[WorkloadLevel] = Query(
        None, description="Filter by workload level"
    ),
    min_patients: Optional[int] = Query(
        None, ge=0, description="Minimum patient count"
    ),
    max_patients: Optional[int] = Query(
        None, ge=0, description="Maximum patient count"
    ),
    search: Optional[str] = Query(None, description="Search by name or email"),
):
    """List physicians with cursor pagination and filtering."""
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    filters = [User.role.in_([UserRole.DOCTOR, UserRole.ADMIN])]

    # Apply RBAC
    role_enum, user_id = _extract_user_context(current_user)
    if role_enum != UserRole.ADMIN:
        filters.append(User.is_active)

    # Apply cursor pagination
    if cursor_data and "id" in cursor_data:
        cursor_id = (
            UUID(cursor_data["id"])
            if isinstance(cursor_data["id"], str)
            else cursor_data["id"]
        )
        cursor_created_at = datetime.fromisoformat(
            cursor_data["created_at"]
        )

        filters.append(
            (User.created_at < cursor_created_at)
            | ((User.created_at == cursor_created_at) & (User.id > cursor_id))
        )

    # Apply search filter
    if search:
        search_filter = f"%{search}%"
        filters.append(
            or_(
                User.full_name.ilike(search_filter),
                User.email.ilike(search_filter),
                User.display_name.ilike(search_filter),
            )
        )

    # Apply status filter
    if status == PhysicianStatus.INACTIVE:
        filters.append(User.is_active.is_(False))
    elif status == PhysicianStatus.ACTIVE:
        filters.append(User.is_active)

    stmt = select(User).filter(*filters)

    # Get total count (only on first page)
    total = None
    if not cursor_data:
        total_result = await db.execute(
            select(func.count())
            .select_from(User)
            .filter(*filters)
        )
        total = total_result.scalar_one()

    # Order and fetch
    ordered_stmt = stmt.order_by(User.created_at.desc(), User.id).limit(limit + 1)
    physicians_result = await db.execute(ordered_stmt)
    physicians = physicians_result.scalars().all()

    # Check for more results
    has_more = len(physicians) > limit
    if has_more:
        physicians = physicians[:limit]

    # Create next cursor
    next_cursor = None
    if has_more and physicians:
        import base64

        cursor_data = {
            "id": str(physicians[-1].id),
            "created_at": physicians[-1].created_at.isoformat(),
        }
        next_cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()

    # Serialize physicians
    include_statistics = bool(include and "statistics" in include)
    physician_responses = []

    for physician in physicians:
        physician_dict = await _serialize_physician(physician, db, include_statistics)

        # Apply field selection
        if fields:
            physician_dict = apply_field_selection(physician_dict, fields)

        physician_responses.append(physician_dict)

    # Apply post-query filters
    if specialty or workload or min_patients is not None or max_patients is not None:
        filtered_responses = []
        for p in physician_responses:
            if specialty and specialty.value not in p.get("specialties", []):
                continue
            if workload and p.get("workload_level") != workload.value:
                continue

            patient_count = p.get("assigned_patients_count", 0)
            if min_patients is not None and patient_count < min_patients:
                continue
            if max_patients is not None and patient_count > max_patients:
                continue

            filtered_responses.append(p)

        physician_responses = filtered_responses

    return {
        "data": physician_responses,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
    }


@router.get(
    "/{physician_id}",
    response_model=PhysicianResponse,
    summary="Get physician profile by ID",
)
@limiter.limit("60/minute")
async def get_physician(
    request: Request,
    physician_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
):
    """Get physician by ID with optional statistics."""
    try:
        physician_uuid = UUID(physician_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid physician ID format",
        )

    # Validate access
    physician = await validate_physician_access(
        physician_uuid,
        current_user,
        db,
        allow_patient_view=True,
    )

    # Serialize physician
    include_statistics = bool(include and "statistics" in include)
    physician_dict = await _serialize_physician(physician, db, include_statistics)

    # Apply field selection
    if fields:
        physician_dict = apply_field_selection(physician_dict, fields)

    return physician_dict


@router.patch(
    "/{physician_id}",
    response_model=PhysicianResponse,
    summary="Update physician information",
)
@limiter.limit("60/minute")
async def update_physician(
    request: Request,
    physician_id: str,
    update_data: PhysicianUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
):
    """Update physician information (Admin only)."""
    # RBAC: Admin only
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update physician information",
        )

    try:
        physician_uuid = UUID(physician_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid physician ID format",
        )

    # Fetch physician
    physician_result = await db.execute(
        select(User).filter(
            User.id == physician_uuid,
            User.role.in_([UserRole.DOCTOR, UserRole.ADMIN]),
        )
    )
    physician = physician_result.scalars().first()

    if not physician:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Physician with id {physician_id} not found",
        )

    # Apply updates
    update_dict = update_data.model_dump(exclude_unset=True)

    # Update direct User fields
    if "full_name" in update_dict:
        physician.full_name = update_dict["full_name"]

    if "is_active" in update_dict:
        physician.is_active = update_dict["is_active"]


    if "specialties" in update_dict:
        normalized_specialties = [
            s.value if isinstance(s, Specialty) else s
            for s in update_dict["specialties"]
        ]
        if hasattr(physician, "set_specialties_data"):
            physician.set_specialties_data(normalized_specialties)
        else:
            physician.specialties = normalized_specialties

    if "status" in update_dict:
        status_value = update_dict["status"]
        if isinstance(status_value, PhysicianStatus):
            status_value = status_value.value
        physician.is_active = status_value == PhysicianStatus.ACTIVE.value

    if "license_number" in update_dict:
        if hasattr(physician, "set_license_number"):
            physician.set_license_number(update_dict["license_number"])
        else:
            physician.license_number = update_dict["license_number"]

    if "phone" in update_dict:
        if hasattr(physician, "set_phone"):
            physician.set_phone(update_dict["phone"])
        else:
            physician.phone = update_dict["phone"]

    if "bio" in update_dict:
        if hasattr(physician, "set_bio"):
            physician.set_bio(update_dict["bio"])
        else:
            physician.bio = update_dict["bio"]


    # Commit changes
    await db.commit()
    await db.refresh(physician)

    # Invalidate cache
    await _run_sync(
        db,
        lambda sync_db: PhysicianStatisticsService(sync_db).invalidate_cache(
            physician_uuid
        )
    )

    # Return updated physician
    physician_dict = await _serialize_physician(physician, db, include_statistics=False)
    return physician_dict
