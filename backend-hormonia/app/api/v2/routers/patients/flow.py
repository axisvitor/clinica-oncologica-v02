"""
Patients API v2 - Flow State Management

This module handles patient flow state operations:
- Activate patient (set flow_state to ACTIVE)
- Deactivate patient (set flow_state to PAUSED)
- Archive patient (set flow_state to CANCELLED with archived metadata)
- Get patient timeline (activity history)
- Get patient statistics (flow state analytics)

Flow States:
- ONBOARDING: Initial registration state
- ACTIVE: Patient actively receiving treatment
- PAUSED: Treatment temporarily paused
- COMPLETED: Treatment successfully completed
- CANCELLED: Treatment cancelled/archived

Migrated from: app/api/v2/routers/patients_flow.py
Lines: 57-416
"""

# Standard library imports
# NOTE: Removed 'from __future__ import annotations' to fix Pydantic/FastAPI
# OpenAPI schema generation issues with Query() and Depends() parameters
import logging
from datetime import datetime, timezone
from typing import Dict

# Third-party imports
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

# Local application imports
from app.core.exceptions import (
    ForbiddenError,
    PatientNotFoundError,
    ServiceUnavailableError,
    ValidationError,
)
from app.database import get_db
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.infrastructure.cache import invalidate_patient_cache
from app.models.patient import FlowState, Patient
from app.models.user import UserRole
from app.repositories.patient import PatientRepository
from app.services.enhanced_flow_engine import get_enhanced_flow_engine
from app.services.patient.flow_service import PatientFlowService
from app.utils.rate_limiter import limiter

from .base import (
    PatientStatsResponse,
    ensure_patient_access,
    ensure_uuid,
    extract_user_context,
    serialize_patient,
)

logger = logging.getLogger(__name__)
router = APIRouter()


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
    db: Session = Depends(get_db),
):
    """
    Activate a patient's flow state.

    This endpoint transitions the patient to an ACTIVE flow state, allowing
    them to receive treatment and participate in the care workflow.
    """
    patient_uuid = await ensure_uuid(patient_id)
    if patient_uuid is None:
        raise ValidationError("Invalid patient ID format", field="patient_id")

    repo = PatientRepository(db)
    patient = repo.get_by_id(patient_uuid)
    if not patient:
        raise PatientNotFoundError(patient_id)

    await ensure_patient_access(current_user, patient.doctor_id)

    # Use specialized flow service
    flow_engine = get_enhanced_flow_engine(db)
    flow_service = PatientFlowService(db, flow_engine)

    updated_patient = await flow_service.activate_patient(patient_uuid)
    if not updated_patient:
        raise ServiceUnavailableError("Failed to activate patient")

    invalidate_patient_cache(str(patient_uuid))
    return await serialize_patient(updated_patient)


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
    db: Session = Depends(get_db),
):
    """
    Deactivate a patient's flow state.

    This endpoint pauses the patient's treatment workflow, typically used
    when treatment is temporarily suspended or the patient is inactive.
    """
    patient_uuid = await ensure_uuid(patient_id)
    if patient_uuid is None:
        raise ValidationError("Invalid patient ID format", field="patient_id")

    repo = PatientRepository(db)
    patient = repo.get_by_id(patient_uuid)
    if not patient:
        raise PatientNotFoundError(patient_id)

    await ensure_patient_access(current_user, patient.doctor_id)

    # Use specialized flow service
    flow_engine = get_enhanced_flow_engine(db)
    flow_service = PatientFlowService(db, flow_engine)

    updated_patient = await flow_service.pause_patient(patient_uuid)
    if not updated_patient:
        raise ServiceUnavailableError("Failed to deactivate patient")

    invalidate_patient_cache(str(patient_uuid))
    return await serialize_patient(updated_patient)


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
    db: Session = Depends(get_db),
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
    """
    patient_uuid = await ensure_uuid(patient_id)
    if patient_uuid is None:
        raise ValidationError("Invalid patient ID format", field="patient_id")

    # Get patient
    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_uuid, Patient.deleted_at.is_(None))
        .first()
    )

    if not patient:
        raise PatientNotFoundError(patient_id)

    # Check access
    await ensure_patient_access(current_user, patient.doctor_id)

    # Update patient flow state to CANCELLED
    patient.flow_state = FlowState.CANCELLED

    # Add archived flag to metadata
    if patient.patient_data is None:
        patient.patient_data = {}

    patient.patient_data["archived"] = True
    patient.patient_data["archived_at"] = datetime.now(timezone.utc).isoformat()

    # Get user info for metadata
    role_enum, user_id = await extract_user_context(current_user)
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
        raise ServiceUnavailableError(f"Failed to archive patient: {str(e)}")

    # Invalidate cache
    invalidate_patient_cache(str(patient_uuid))

    # Return updated patient
    return await serialize_patient(patient)


@router.get(
    "/{patient_id}/timeline",
    summary="Get patient timeline",
    description="Return a comprehensive patient timeline with all activity events",
)
@limiter.limit("60/minute")
async def get_patient_timeline(
    request: Request,
    patient_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    """
    Get patient timeline of events.

    Returns a chronological list of significant events in the patient's
    treatment journey, including:
    - Patient creation
    - Flow state changes (activate, deactivate, archive)
    - Saga status changes
    - Message events
    - Quiz completions
    """
    patient_uuid = await ensure_uuid(patient_id)
    if patient_uuid is None:
        raise ValidationError("Invalid patient ID format", field="patient_id")

    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_uuid, Patient.deleted_at.is_(None))
        .first()
    )

    if not patient:
        raise PatientNotFoundError(patient_id)

    await ensure_patient_access(current_user, patient.doctor_id)

    events = []

    # 1. Patient created event
    events.append({
        "date": patient.created_at,
        "event": "patient_created",
        "details": f"Paciente {patient.name} foi cadastrado",
        "metadata": {
            "doctor_id": str(patient.doctor_id) if patient.doctor_id else None,
            "treatment_type": patient.treatment_type,
        },
    })

    # 2. Current flow state
    events.append({
        "date": patient.updated_at or patient.created_at,
        "event": "flow_state_current",
        "details": f"Estado atual do fluxo: {patient.flow_state.value if patient.flow_state else 'N/A'}",
        "metadata": {
            "flow_state": patient.flow_state.value if patient.flow_state else None,
        },
    })

    # 3. Saga events (if any)
    try:
        from app.models.patient_onboarding_saga import PatientOnboardingSaga

        sagas = (
            db.query(PatientOnboardingSaga)
            .filter(PatientOnboardingSaga.patient_id == patient_uuid)
            .order_by(PatientOnboardingSaga.created_at.desc())
            .limit(5)
            .all()
        )

        for saga in sagas:
            # Saga started
            events.append({
                "date": saga.started_at or saga.created_at,
                "event": "saga_started",
                "details": "Saga de onboarding iniciada",
                "metadata": {
                    "saga_id": str(saga.id),
                    "status": saga.status.value if saga.status else None,
                },
            })

            # Saga completed/failed
            if saga.completed_at:
                events.append({
                    "date": saga.completed_at,
                    "event": "saga_completed",
                    "details": "Onboarding concluído com sucesso",
                    "metadata": {
                        "saga_id": str(saga.id),
                        "duration_seconds": saga._calculate_duration(),
                    },
                })
            elif saga.failed_at:
                events.append({
                    "date": saga.failed_at,
                    "event": "saga_failed",
                    "details": f"Onboarding falhou: {saga.error_message or 'Erro desconhecido'}",
                    "metadata": {
                        "saga_id": str(saga.id),
                        "error_type": saga.error_type,
                        "retry_count": saga.retry_count,
                    },
                })

            # Add execution log entries as events
            if saga.execution_log:
                for log_entry in saga.execution_log:
                    events.append({
                        "date": log_entry.get("timestamp", saga.created_at),
                        "event": f"saga_step_{log_entry.get('step', 0)}",
                        "details": f"Step {log_entry.get('step')}: {log_entry.get('action')} - {log_entry.get('status')}",
                        "metadata": log_entry,
                    })

    except Exception as e:
        logger.warning(f"Could not fetch saga events for patient {patient_id}: {e}")

    # 4. Check for archived status in metadata
    if patient.patient_data and patient.patient_data.get("archived"):
        archived_at = patient.patient_data.get("archived_at")
        events.append({
            "date": archived_at or patient.updated_at,
            "event": "patient_archived",
            "details": "Paciente foi arquivado",
            "metadata": {
                "archived_by": patient.patient_data.get("archived_by"),
            },
        })

    # Sort events by date (most recent first)
    events.sort(key=lambda x: x["date"] if x["date"] else datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    return {
        "patient_id": patient_id,
        "patient_name": patient.name,
        "current_flow_state": patient.flow_state.value if patient.flow_state else None,
        "events": events,
        "total_events": len(events),
    }


@router.get(
    "/{patient_id}/saga-status",
    summary="Get patient saga status",
    description="Return the current onboarding saga status for a patient",
)
@limiter.limit("60/minute")
async def get_patient_saga_status(
    request: Request,
    patient_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    """
    Get patient onboarding saga status.

    Returns the current status of the patient's onboarding saga including:
    - Current step in the saga
    - Execution history
    - Error information if failed
    - Retry status
    """
    patient_uuid = await ensure_uuid(patient_id)
    if patient_uuid is None:
        raise ValidationError("Invalid patient ID format", field="patient_id")

    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_uuid, Patient.deleted_at.is_(None))
        .first()
    )

    if not patient:
        raise PatientNotFoundError(patient_id)

    await ensure_patient_access(current_user, patient.doctor_id)

    # Query saga status
    try:
        from app.models.patient_onboarding_saga import PatientOnboardingSaga

        saga = (
            db.query(PatientOnboardingSaga)
            .filter(PatientOnboardingSaga.patient_id == patient_uuid)
            .order_by(PatientOnboardingSaga.created_at.desc())
            .first()
        )

        if not saga:
            return {
                "patient_id": patient_id,
                "has_saga": False,
                "message": "No onboarding saga found for this patient",
            }

        return {
            "patient_id": patient_id,
            "has_saga": True,
            "saga": saga.get_execution_summary(),
        }

    except Exception as e:
        logger.error(f"Error fetching saga status for patient {patient_id}: {e}")
        raise ServiceUnavailableError(f"Error fetching saga status: {str(e)}")


@router.get(
    "/stats",
    response_model=PatientStatsResponse,
    summary="Get patient statistics summary",
)
@limiter.limit("30/minute")
async def get_patient_stats(
    request: Request,
    db: Session = Depends(get_db),
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
    """
    role_enum, user_id = await extract_user_context(current_user)
    current_user_uuid = await ensure_uuid(user_id)

    base_query = db.query(Patient).filter(Patient.deleted_at.is_(None))
    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None:
            raise ForbiddenError("Unable to determine user permissions")
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
