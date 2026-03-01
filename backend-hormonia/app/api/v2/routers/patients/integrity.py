"""
Patients API v2 - Data Integrity and Validation

This module handles patient data integrity operations:
- CPF validation and uniqueness checks
- Email existence validation
- Restore deleted patients
- Deleted patient management

All validation endpoints ensure data consistency and prevent duplicates.

Migrated from: app/api/v2/routers/patients_integrity.py
Lines: 60-381
"""

# Standard library imports
# NOTE: Removed 'from __future__ import annotations' to fix Pydantic/FastAPI
# OpenAPI schema generation issues with Query() and Depends() parameters
import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

# Third-party imports
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

# Local application imports
from app.api.v2.dependencies import (
    apply_field_selection,
    get_field_selection,
    get_pagination_params,
)
from app.core.authorization import require_permission
from app.core.permissions import Permission
from app.database import get_async_db
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.models.patient import Patient
from app.models.user import UserRole
from app.repositories.patient import PatientRepository
from app.schemas.validators.cpf import is_valid_cpf
from app.schemas.v2.patient import PatientV2List, PatientV2Response
from app.services.patient.crud_service import PatientCRUDService
from app.utils.rate_limiter import limiter

from .base import (
    CPFValidationRequest,
    EmailCheckResponse,
    ensure_patient_access,
    extract_user_context,
    normalize_cpf,
)

logger = logging.getLogger(__name__)
router = APIRouter()


async def _run_sync(db: AsyncSession, operation):
    if hasattr(db, "run_sync"):
        return await db.run_sync(operation)
    sync_db = getattr(db, "_sync_session", db)
    return operation(sync_db)


@router.post(
    "/validate-cpf",
    summary="Validate CPF",
    description="Validate CPF format and length",
)
@limiter.limit("60/minute")
async def validate_cpf_endpoint(request: Request, payload: CPFValidationRequest):
    """
    Validate CPF format and length.

    Checks:
    - CPF is provided
    - CPF format is valid (using canonical validator)
    - CPF has exactly 11 digits after normalization
    """
    if not payload.cpf:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CPF is required",
        )

    if not is_valid_cpf(payload.cpf, allow_none=False):
        return {"valid": False, "message": "CPF inválido"}

    normalized = await normalize_cpf(payload.cpf)
    if normalized and len(normalized) != 11:
        return {"valid": False, "message": "CPF deve conter 11 dígitos"}

    return {"valid": True}


@router.get(
    "/check-email",
    response_model=EmailCheckResponse,
    summary="Check if patient email exists",
    description="Check if a patient with the given email already exists in the system",
)
@require_permission(Permission.PATIENT_CREATE)
@limiter.limit("60/minute")
async def check_email_exists(
    request: Request,
    email: EmailStr = Query(..., description="Email to validate"),
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
):
    """
    Check if a patient email already exists.

    Performs case-insensitive search for email in active (non-deleted) patients.
    """
    # LGPD: Use email_hash for lookup (plaintext column removed in migration 030)
    from app.services.encryption import get_lgpd_encryption_service

    service = get_lgpd_encryption_service()
    email_hash = service.hash_email(email.lower())

    result = await db.execute(
        select(Patient.id).filter(
            Patient.deleted_at.is_(None),
            Patient.email_hash == email_hash,
        ).limit(1)
    )
    exists = result.scalar_one_or_none() is not None
    return EmailCheckResponse(email=email, exists=exists)


@router.post(
    "/{patient_id}/restore",
    response_model=PatientV2Response,
    summary="Restore deleted patient",
    description="Restore a soft-deleted patient record",
)
@require_permission(Permission.PATIENT_DELETE)
@limiter.limit("10/hour")
async def restore_patient(
    request: Request,
    patient_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
):
    """
    Restore a soft-deleted patient.

    This removes the deleted_at timestamp, making the patient active again.
    Only deleted patients can be restored.
    """
    try:
        patient_uuid = UUID(patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid patient ID format"
        )

    patient = await _run_sync(
        db,
        lambda sync_db: PatientRepository(sync_db).get_by_id_including_deleted(patient_uuid)
    )

    if not patient or patient.deleted_at is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deleted patient with id {patient_id} not found",
        )

    await ensure_patient_access(current_user, patient.doctor_id)

    restored = await _run_sync(
        db,
        lambda sync_db: PatientCRUDService(
            sync_db,
            PatientRepository(sync_db),
        ).restore_patient(patient_uuid)
    )
    if not restored:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restore patient",
        )

    refreshed = await _run_sync(
        db,
        lambda sync_db: PatientRepository(sync_db).get_by_id(patient_uuid)
    )
    if not refreshed:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load restored patient",
        )

    return PatientV2Response.from_orm(refreshed)


@router.get(
    "/deleted",
    response_model=PatientV2List,
    summary="List deleted patients",
    description="Get list of soft-deleted patients (ADMIN only)",
)
@limiter.limit("30/minute")
async def list_deleted_patients(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
    pagination=Depends(get_pagination_params),
    fields: Optional[List[str]] = Depends(get_field_selection),
):
    """
    List soft-deleted patients.

    Only administrators can view deleted patients.
    Supports pagination and field selection.
    """
    role_enum, user_id = await extract_user_context(current_user)

    # Only admins can view deleted patients
    if role_enum != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view deleted patients",
        )

    stmt = select(Patient).filter(Patient.deleted_at.isnot(None))

    # Get cursor data and limit from pagination
    cursor_data = (
        pagination.get("cursor_data") if isinstance(pagination, dict) else None
    )
    limit = (
        pagination.get("limit", 20)
        if isinstance(pagination, dict)
        else getattr(pagination, "limit", 20)
    )

    # Apply cursor-based pagination if cursor exists
    if cursor_data and "id" in cursor_data:
        cursor_id = (
            UUID(cursor_data["id"])
            if isinstance(cursor_data["id"], str)
            else cursor_data["id"]
        )
        cursor_created_at = datetime.fromisoformat(
            cursor_data["created_at"]
        )

        stmt = stmt.filter(
            (Patient.created_at < cursor_created_at)
            | ((Patient.created_at == cursor_created_at) & (Patient.id > cursor_id))
        )

    # Calculate total (only on first page)
    total = None
    if not cursor_data:
        total_result = await db.execute(
            select(func.count()).select_from(Patient).filter(Patient.deleted_at.isnot(None))
        )
        total = total_result.scalar_one()

    # Order and limit
    stmt = stmt.order_by(Patient.deleted_at.desc(), Patient.id).limit(limit + 1)
    patients_result = await db.execute(stmt)
    patients = patients_result.scalars().all()

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
            "created_at": patients[-1].created_at.isoformat(),
        }
        next_cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()

    # Apply field selection
    patient_data = []
    for patient in patients:
        patient_dict = PatientV2Response.from_orm(patient).dict()
        if fields:
            patient_dict = apply_field_selection(patient_dict, fields)
        patient_data.append(patient_dict)

    return {
        "data": patient_data,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
    }
