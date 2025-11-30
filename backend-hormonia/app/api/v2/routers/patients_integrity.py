"""
Patients Data Integrity and Validation API v2

This module provides endpoints for data integrity validation and management of patient records:
- CPF validation and uniqueness checks
- Email existence validation
- Soft delete operations (delete/restore)
- Deleted patient management

All validation endpoints ensure data consistency and prevent duplicates.
Soft delete operations preserve data for audit purposes while marking records as deleted.
"""

from typing import Any, Optional, List
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import func
import logging

from app.database import get_db
from app.models.patient import Patient
from app.models.user import UserRole
from app.schemas.patient import validate_cpf as validate_cpf_value
from app.schemas.v2.patient import PatientV2Response, PatientV2List
from app.api.v2.dependencies import get_pagination_params, get_field_selection, apply_field_selection
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.utils.rate_limiter import limiter

# Import helper functions from patients_utils
from app.api.v2.patients_utils import (
    _normalize_cpf,
    _extract_user_context,
    _ensure_uuid,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models for Validation Requests/Responses
# ============================================================================

class CPFValidationRequest(BaseModel):
    cpf: str


class EmailCheckResponse(BaseModel):
    email: EmailStr
    exists: bool


# ============================================================================
# CPF Validation Endpoint
# ============================================================================

@router.post(
    "/validate-cpf",
    summary="Validate CPF",
    description="Validate CPF format and length"
)
@limiter.limit("60/minute")
async def validate_cpf_endpoint(
    request: Request,
    payload: CPFValidationRequest
):
    """
    Validate CPF format and length.

    Checks:
    - CPF is provided
    - CPF format is valid (using validate_cpf_value)
    - CPF has exactly 11 digits after normalization

    Returns:
        dict: {"valid": bool, "message": str (optional)}

    Example:
        POST /api/v2/patients/validate-cpf
        Body: {"cpf": "123.456.789-00"}
        Response: {"valid": true}
    """
    if not payload.cpf:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CPF is required",
        )

    if not validate_cpf_value(payload.cpf):
        return {"valid": False, "message": "CPF inválido"}

    normalized = _normalize_cpf(payload.cpf)
    if normalized and len(normalized) != 11:
        return {"valid": False, "message": "CPF deve conter 11 dígitos"}

    return {"valid": True}


# ============================================================================
# Email Existence Check Endpoint
# ============================================================================

@router.get(
    "/check-email",
    response_model=EmailCheckResponse,
    summary="Check if patient email exists",
    description="Check if a patient with the given email already exists in the system"
)
@limiter.limit("60/minute")
async def check_email_exists(
    request: Request,
    email: EmailStr = Query(..., description="Email to validate"),
    db = Depends(get_db),
):
    """
    Check if a patient email already exists.

    Performs case-insensitive search for email in active (non-deleted) patients.

    Args:
        email: Email address to check
        db: Database session

    Returns:
        EmailCheckResponse: Contains email and exists boolean

    Example:
        GET /api/v2/patients/check-email?email=patient@example.com
        Response: {"email": "patient@example.com", "exists": true}
    """
    exists = (
        db.query(Patient)
        .filter(
            Patient.deleted_at.is_(None),
            func.lower(Patient.email) == email.lower(),
        )
        .first()
        is not None
    )
    return EmailCheckResponse(email=email, exists=exists)


# ============================================================================
# Soft Delete Operations
# ============================================================================

@router.delete(
    "/{patient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete patient (soft delete)",
    description="Soft delete a patient record - marks as deleted without removing from database"
)
@limiter.limit("10/hour")
async def delete_patient(
    request: Request,
    patient_id: str,
    db = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """
    Soft delete a patient.

    This marks the patient as deleted (sets deleted_at timestamp) without
    removing the record from the database. This preserves data for audit
    purposes and allows restoration if needed.

    Args:
        patient_id: UUID of the patient to delete
        db: Database session
        current_user: Current authenticated user

    Raises:
        HTTPException: 400 if patient_id format is invalid
        HTTPException: 404 if patient not found or already deleted

    Returns:
        None (204 No Content)

    Example:
        DELETE /api/v2/patients/{patient_id}
        Response: 204 No Content
    """
    try:
        patient_uuid = UUID(patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format"
        )

    # Only get active patients (not already deleted)
    patient = db.query(Patient).filter(
        Patient.id == patient_uuid,
        Patient.deleted_at.is_(None)
    ).first()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active patient with id {patient_id} not found"
        )

    # Soft delete: set deleted_at timestamp
    patient.deleted_at = datetime.utcnow()
    db.commit()

    return None


@router.post(
    "/{patient_id}/restore",
    response_model=PatientV2Response,
    summary="Restore deleted patient",
    description="Restore a soft-deleted patient record"
)
@limiter.limit("10/hour")
async def restore_patient(
    request: Request,
    patient_id: str,
    db = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """
    Restore a soft-deleted patient.

    This removes the deleted_at timestamp, making the patient active again.
    Only deleted patients can be restored.

    Args:
        patient_id: UUID of the patient to restore
        db: Database session
        current_user: Current authenticated user

    Raises:
        HTTPException: 400 if patient_id format is invalid
        HTTPException: 404 if deleted patient not found

    Returns:
        PatientV2Response: The restored patient data

    Example:
        POST /api/v2/patients/{patient_id}/restore
        Response: PatientV2Response with restored patient data
    """
    try:
        patient_uuid = UUID(patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format"
        )

    # Only get deleted patients
    patient = db.query(Patient).filter(
        Patient.id == patient_uuid,
        Patient.deleted_at.isnot(None)
    ).first()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deleted patient with id {patient_id} not found"
        )

    # Restore: remove deleted_at timestamp
    patient.deleted_at = None
    db.commit()
    db.refresh(patient)

    return PatientV2Response.from_orm(patient)


# ============================================================================
# Deleted Patients Management
# ============================================================================

@router.get(
    "/deleted",
    response_model=PatientV2List,
    summary="List deleted patients",
    description="Get list of soft-deleted patients (ADMIN only)"
)
@limiter.limit("30/minute")
async def list_deleted_patients(
    request: Request,
    db = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    pagination = Depends(get_pagination_params),
    fields: Optional[List[str]] = Depends(get_field_selection),
):
    """
    List soft-deleted patients.

    Only administrators can view deleted patients.
    Supports pagination and field selection.

    Args:
        db: Database session
        current_user: Current authenticated user (must be ADMIN)
        pagination: Pagination parameters (page, limit, skip)
        fields: Optional list of fields to include in response

    Raises:
        HTTPException: 403 if user is not an administrator

    Returns:
        PatientV2List: Paginated list of deleted patients

    Example:
        GET /api/v2/patients/deleted?page=1&limit=20
        Response: PatientV2List with deleted patients
    """
    role_enum, user_id = _extract_user_context(current_user)

    # Only admins can view deleted patients
    if role_enum != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view deleted patients"
        )

    # Query deleted patients
    query = db.query(Patient).filter(Patient.deleted_at.isnot(None))

    # Get cursor data and limit from pagination
    cursor_data = pagination.get("cursor_data") if isinstance(pagination, dict) else None
    limit = pagination.get("limit", 20) if isinstance(pagination, dict) else getattr(pagination, "limit", 20)

    # Apply cursor-based pagination if cursor exists
    if cursor_data and "id" in cursor_data:
        cursor_id = UUID(cursor_data["id"]) if isinstance(cursor_data["id"], str) else cursor_data["id"]
        cursor_created_at = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))

        query = query.filter(
            (Patient.created_at < cursor_created_at) |
            ((Patient.created_at == cursor_created_at) & (Patient.id > cursor_id))
        )

    # Calculate total (only on first page)
    total = None
    if not cursor_data:
        total = query.count()

    # Order and limit
    query = query.order_by(Patient.deleted_at.desc(), Patient.id)
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
