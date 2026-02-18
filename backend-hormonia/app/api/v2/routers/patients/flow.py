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
from datetime import date, datetime, time
from typing import Any, Dict, List, Optional

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
from app.utils.timezone import SAO_PAULO_TZ, now_sao_paulo

from .base import (
    PatientStatsResponse,
    ensure_patient_access,
    ensure_uuid,
    extract_user_context,
    serialize_patient,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _normalize_datetime(dt: Any) -> datetime:
    """Helper to normalize mixed datetime/string types for sorting."""
    if dt is None:
        return datetime.min.replace(tzinfo=SAO_PAULO_TZ)
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=SAO_PAULO_TZ)
        return dt
    if isinstance(dt, str):
        try:
            # Handle ISO strings with offsets.
            normalized = dt.replace("Z", "+00:00") if dt.endswith("Z") else dt
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=SAO_PAULO_TZ)
            return parsed
        except (ValueError, TypeError):
            return datetime.min.replace(tzinfo=SAO_PAULO_TZ)
    return datetime.min.replace(tzinfo=SAO_PAULO_TZ)


def _format_event_datetime(value: Any) -> Optional[str]:
    """Normalize event timestamps to ISO strings for API responses."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=SAO_PAULO_TZ)
        return value.isoformat()
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=SAO_PAULO_TZ).isoformat()
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return None
        normalized = trimmed.replace("Z", "+00:00") if trimmed.endswith("Z") else trimmed
        try:
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=SAO_PAULO_TZ)
            return parsed.isoformat()
        except (ValueError, TypeError):
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    parsed = datetime.strptime(normalized, fmt).replace(tzinfo=SAO_PAULO_TZ)
                    return parsed.isoformat()
                except ValueError:
                    continue
            return None
    return None


def _build_timeline_event(
    patient_id: str,
    event_key: str,
    title: str,
    description: str,
    date_value: Any,
    metadata: Optional[Dict[str, Any]] = None,
    event_type: str = "system",
) -> Dict[str, Any]:
    """Build a normalized timeline event payload."""
    safe_metadata = dict(metadata or {})
    timestamp = _format_event_datetime(date_value)
    event_id_parts = [event_key, patient_id]
    saga_id = safe_metadata.get("saga_id")
    if saga_id:
        event_id_parts.append(str(saga_id))
    step = safe_metadata.get("step")
    if step is not None:
        event_id_parts.append(str(step))
    if timestamp:
        event_id_parts.append(timestamp)
    event_id = safe_metadata.get("id") or "-".join(event_id_parts)

    return {
        "id": event_id,
        "patient_id": patient_id,
        "type": event_type,
        "title": title,
        "description": description,
        "timestamp": timestamp,
        "metadata": safe_metadata,
    }


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
    patient.patient_data["archived_at"] = now_sao_paulo().isoformat()

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
    events.append(
        _build_timeline_event(
            patient_id=str(patient_uuid),
            event_key="patient_created",
            title="Paciente cadastrado",
            description=f"Paciente {patient.name} foi cadastrado",
            date_value=patient.created_at,
            metadata={
                "doctor_id": str(patient.doctor_id) if patient.doctor_id else None,
                "treatment_type": patient.treatment_type,
            },
            event_type="flow_change",
        )
    )

    # 2. Current flow state
    events.append(
        _build_timeline_event(
            patient_id=str(patient_uuid),
            event_key="flow_state_current",
            title="Estado do fluxo",
            description=f"Estado atual do fluxo: {patient.flow_state.value if patient.flow_state else 'N/A'}",
            date_value=patient.updated_at or patient.created_at,
            metadata={
                "flow_state": patient.flow_state.value if patient.flow_state else None,
            },
            event_type="flow_change",
        )
    )

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
            events.append(
                _build_timeline_event(
                    patient_id=str(patient_uuid),
                    event_key="saga_started",
                    title="Saga iniciada",
                    description="Saga de onboarding iniciada",
                    date_value=saga.started_at or saga.created_at,
                    metadata={
                        "saga_id": str(saga.id),
                        "status": saga.status.value if saga.status else None,
                    },
                    event_type="flow_change",
                )
            )

            # Saga completed/failed
            if saga.completed_at:
                events.append(
                    _build_timeline_event(
                        patient_id=str(patient_uuid),
                        event_key="saga_completed",
                        title="Saga concluída",
                        description="Onboarding concluído com sucesso",
                        date_value=saga.completed_at,
                        metadata={
                            "saga_id": str(saga.id),
                            "duration_seconds": saga._calculate_duration(),
                        },
                        event_type="flow_change",
                    )
                )
            elif saga.failed_at:
                events.append(
                    _build_timeline_event(
                        patient_id=str(patient_uuid),
                        event_key="saga_failed",
                        title="Saga falhou",
                        description=f"Onboarding falhou: {saga.error_message or 'Erro desconhecido'}",
                        date_value=saga.failed_at,
                        metadata={
                            "saga_id": str(saga.id),
                            "error_type": saga.error_type,
                            "retry_count": saga.retry_count,
                        },
                        event_type="flow_change",
                    )
                )

            # Add execution log entries as events
            if saga.execution_log:
                for log_entry in saga.execution_log:
                    step_value = log_entry.get("step")
                    events.append(
                        _build_timeline_event(
                            patient_id=str(patient_uuid),
                            event_key=f"saga_step_{step_value or 0}",
                            title=f"Etapa {step_value or 0}",
                            description=f"Step {step_value}: {log_entry.get('action')} - {log_entry.get('status')}",
                            date_value=log_entry.get("timestamp", saga.created_at),
                            metadata=log_entry,
                            event_type="flow_change",
                        )
                    )

    except Exception as e:
        logger.warning(f"Could not fetch saga events for patient {patient_id}: {e}")

    # 4. Check for archived status in metadata
    if patient.patient_data and patient.patient_data.get("archived"):
        archived_at = patient.patient_data.get("archived_at")
        events.append(
            _build_timeline_event(
                patient_id=str(patient_uuid),
                event_key="patient_archived",
                title="Paciente arquivado",
                description="Paciente foi arquivado",
                date_value=archived_at or patient.updated_at,
                metadata={
                    "archived_by": patient.patient_data.get("archived_by"),
                },
                event_type="flow_change",
            )
        )

    # Sort events by date (most recent first)
    events.sort(
        key=lambda x: _normalize_datetime(x.get("timestamp")),
        reverse=True,
    )

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

    start_of_month = now_sao_paulo().replace(
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
