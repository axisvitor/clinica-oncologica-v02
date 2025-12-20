"""
Patient Flow State Management API v2

This module handles patient flow state management operations including:
- Patient activation/deactivation (flow state transitions)
- Patient archival (soft retirement from active treatment)
- Patient timeline tracking (activity history)
- Patient statistics and reporting (flow state analytics)

Flow States:
- ONBOARDING: Initial registration state
- ACTIVE: Patient actively receiving treatment
- PAUSED: Treatment temporarily paused
- COMPLETED: Treatment successfully completed
- CANCELLED: Treatment cancelled/archived
"""

from typing import Dict
from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_db
from app.models.patient import Patient, FlowState
from app.models.user import UserRole
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.repositories.patient import PatientRepository
from app.services.patient.flow_service import PatientFlowService
from app.services.enhanced_flow_engine import get_enhanced_flow_engine
from app.utils.rate_limiter import limiter
from app.infrastructure.cache import invalidate_patient_cache

# Import utility functions from patients_utils module
from app.api.v2.patients_utils import (
    _ensure_uuid,
    _ensure_patient_access,
    _extract_user_context,
    _serialize_patient,
)

router = APIRouter()
logger = logging.getLogger(__name__)


class PatientStatsResponse(BaseModel):
    total_patients: int
    active_patients: int
    inactive_patients: int
    new_this_month: int
    by_status: Dict[str, int]


@router.post(
    "/{patient_id}/activate",
    response_model=dict,
    summary="Activate patient flow",
    description="Set patient flow_state to active (doctor/admin only)",
)
@limiter.limit("30/hour")
async def activate_patient(
    request: Request,
    patient_id: str,
    current_user=Depends(get_current_user_from_session),
    db=Depends(get_db),
):
    """
    Activate a patient's flow state.

    This endpoint transitions the patient to an ACTIVE flow state, allowing
    them to receive treatment and participate in the care workflow.

    Args:
        patient_id: UUID of the patient to activate
        current_user: Authenticated user (doctor or admin)
        db: Database session dependency

    Returns:
        Serialized patient data with updated flow_state

    Raises:
        HTTPException: 400 if patient_id format is invalid
        HTTPException: 404 if patient not found
        HTTPException: 403 if user lacks permissions
        HTTPException: 500 if activation fails
    """
    patient_uuid = _ensure_uuid(patient_id)
    if patient_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format",
        )

    repo = PatientRepository(db)
    patient = repo.get_by_id(patient_uuid)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    _ensure_patient_access(current_user, patient.doctor_id)

    # Use specialized flow service
    flow_engine = get_enhanced_flow_engine(db)
    flow_service = PatientFlowService(db, flow_engine)

    updated_patient = await flow_service.activate_patient(patient_uuid)
    if not updated_patient:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate patient",
        )

    invalidate_patient_cache(str(patient_uuid))
    return _serialize_patient(updated_patient)


@router.post(
    "/{patient_id}/deactivate",
    response_model=dict,
    summary="Deactivate patient flow",
    description="Pause/mark patient as inactive (doctor/admin only)",
)
@limiter.limit("30/hour")
async def deactivate_patient(
    request: Request,
    patient_id: str,
    current_user=Depends(get_current_user_from_session),
    db=Depends(get_db),
):
    """
    Deactivate a patient's flow state.

    This endpoint pauses the patient's treatment workflow, typically used
    when treatment is temporarily suspended or the patient is inactive.

    Args:
        patient_id: UUID of the patient to deactivate
        current_user: Authenticated user (doctor or admin)
        db: Database session dependency

    Returns:
        Serialized patient data with updated flow_state

    Raises:
        HTTPException: 400 if patient_id format is invalid
        HTTPException: 404 if patient not found
        HTTPException: 403 if user lacks permissions
        HTTPException: 500 if deactivation fails
    """
    patient_uuid = _ensure_uuid(patient_id)
    if patient_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format",
        )

    repo = PatientRepository(db)
    patient = repo.get_by_id(patient_uuid)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    _ensure_patient_access(current_user, patient.doctor_id)

    # Use specialized flow service
    flow_engine = get_enhanced_flow_engine(db)
    flow_service = PatientFlowService(db, flow_engine)

    updated_patient = await flow_service.pause_patient(patient_uuid)
    if not updated_patient:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate patient",
        )

    invalidate_patient_cache(str(patient_uuid))
    return _serialize_patient(updated_patient)


@router.post(
    "/{patient_id}/archive",
    response_model=dict,
    summary="Archive patient",
    description="Archive a patient (similar to deactivate but with archived status) (ADMIN/DOCTOR only)",
)
@limiter.limit("30/hour")
async def archive_patient(
    request: Request,
    patient_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    """
    Archive a patient.

    Similar to deactivate but sets the patient flow_state to CANCELLED and
    adds an archived flag to metadata for future filtering and reporting.

    Archived patients:
    - Are marked as CANCELLED in flow_state
    - Have metadata.archived = true
    - Can be distinguished from regular cancelled patients
    - Can still be viewed and restored if needed

    Args:
        request: FastAPI request object
        patient_id: UUID of the patient to archive
        db: Database session
        current_user: Authenticated user (doctor or admin)

    Returns:
        Serialized patient data with archived metadata

    Raises:
        HTTPException: 400 if patient_id format is invalid
        HTTPException: 404 if patient not found
        HTTPException: 403 if user lacks permissions
        HTTPException: 500 if archive operation fails
    """
    patient_uuid = _ensure_uuid(patient_id)
    if patient_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format",
        )

    # Get patient
    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_uuid, Patient.deleted_at.is_(None))
        .first()
    )

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # Check access
    _ensure_patient_access(current_user, patient.doctor_id)

    # Update patient flow state to CANCELLED
    patient.flow_state = FlowState.CANCELLED

    # Add archived flag to metadata
    if patient.patient_data is None:
        patient.patient_data = {}

    patient.patient_data["archived"] = True
    patient.patient_data["archived_at"] = datetime.now(timezone.utc).isoformat()

    # Get user info for metadata
    role_enum, user_id = _extract_user_context(current_user)
    if user_id:
        patient.patient_data["archived_by"] = str(user_id)

    # Mark the patient_data as modified to trigger SQLAlchemy update
    flag_modified(patient, "patient_data")

    # Commit changes
    try:
        db.commit()
        db.refresh(patient)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to archive patient {patient_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to archive patient: {str(e)}",
        )

    # Invalidate cache
    invalidate_patient_cache(str(patient_uuid))

    # Return updated patient
    return _serialize_patient(patient)


@router.get(
    "/{patient_id}/timeline",
    summary="Get patient timeline",
    description="Return a lightweight patient timeline for activity feeds",
)
@limiter.limit("60/minute")
async def get_patient_timeline(
    request: Request,
    patient_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    """
    Get patient timeline of events.

    Returns a chronological list of significant events in the patient's
    treatment journey, useful for activity feeds and status tracking.

    Args:
        patient_id: UUID of the patient
        db: Database session
        current_user: Authenticated user

    Returns:
        Dictionary with patient_id and list of timeline events

    Raises:
        HTTPException: 400 if patient_id format is invalid
        HTTPException: 404 if patient not found
        HTTPException: 403 if user lacks permissions
    """
    patient_uuid = _ensure_uuid(patient_id)
    if patient_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format",
        )

    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_uuid, Patient.deleted_at.is_(None))
        .first()
    )

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    _ensure_patient_access(current_user, patient.doctor_id)

    created_event = {
        "date": patient.created_at,
        "event": "patient_created",
        "details": f"Paciente {patient.name} foi cadastrado",
        "metadata": {
            "doctor_id": str(patient.doctor_id) if patient.doctor_id else None,
            "treatment_type": patient.treatment_type,
        },
    }

    return {
        "patient_id": patient_id,
        "events": [created_event],
    }


@router.get(
    "/stats",
    response_model=PatientStatsResponse,
    summary="Get patient statistics summary",
)
@limiter.limit("30/minute")
async def get_patient_stats(
    request: Request,
    db=Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    """
    Get comprehensive patient statistics.

    Provides aggregated statistics about patients including:
    - Total patient count
    - Active/inactive patient counts
    - New patients this month
    - Breakdown by flow state

    Non-admin users only see statistics for their own patients.

    Args:
        db: Database session
        current_user: Authenticated user

    Returns:
        PatientStatsResponse with aggregated statistics

    Raises:
        HTTPException: 403 if unable to determine user permissions
    """
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    base_query = db.query(Patient).filter(Patient.deleted_at.is_(None))
    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to determine user permissions",
            )
        base_query = base_query.filter(Patient.doctor_id == current_user_uuid)

    total_patients = base_query.count()
    active_patients = base_query.filter(Patient.flow_state == FlowState.ACTIVE).count()
    inactive_patients = base_query.filter(
        Patient.flow_state == FlowState.CANCELLED
    ).count()

    start_of_month = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    new_this_month = base_query.filter(Patient.created_at >= start_of_month).count()

    by_status: Dict[str, int] = {}
    for state in FlowState:
        by_status[state.value] = base_query.filter(Patient.flow_state == state).count()

    return PatientStatsResponse(
        total_patients=total_patients,
        active_patients=active_patients,
        inactive_patients=inactive_patients,
        new_this_month=new_this_month,
        by_status=by_status,
    )
