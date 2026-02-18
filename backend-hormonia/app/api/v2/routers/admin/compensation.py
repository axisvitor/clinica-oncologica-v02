"""
Admin compensation endpoints.

Provides visibility and manual controls for saga compensation failures.
"""

import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import cast, String
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.redis_manager import get_sync_redis_client as get_redis_client
from app.database import get_db
from app.utils.request_context import get_request_context, RequestContext
from app.models.enums import SagaStatus
from app.models.patient import Patient
from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.models.user import User
from app.orchestration.saga_orchestrator.compensation import SagaCompensator
from app.orchestration.saga_orchestrator.exceptions import SagaCompensationError
from app.repositories.patient import PatientRepository

from .dependencies import get_admin_user
from .utils import _log_admin_action
from app.utils.timezone import now_sao_paulo

router = APIRouter()
logger = logging.getLogger(__name__)


def _extract_failed_steps(execution_log: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    failed_steps: List[Dict[str, Any]] = []
    for entry in execution_log or []:
        if entry.get("status") == "compensation_failed":
            failed_steps.append(
                {"step": entry.get("step"), "error": entry.get("message") or ""}
            )
    return failed_steps


def _clear_quarantine(patient: Patient) -> None:
    if not patient.patient_data:
        return

    for key in ("quarantine", "quarantine_reason", "quarantine_at", "saga_id"):
        patient.patient_data.pop(key, None)
    flag_modified(patient, "patient_data")


@router.get(
    "/compensation-failures",
    summary="List compensation failures",
    description="List failed sagas with quarantined patients for manual follow-up.",
)
async def list_compensation_failures(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    dialect = getattr(getattr(db, "bind", None), "dialect", None)
    dialect_name = dialect.name if dialect else ""

    quarantine_filter = (
        Patient.patient_data["quarantine"].astext == "true"
        if dialect_name != "sqlite"
        else cast(Patient.patient_data, String).like('%"quarantine": true%')
    )

    base_query = (
        db.query(PatientOnboardingSaga, Patient)
        .join(Patient, Patient.id == PatientOnboardingSaga.patient_id)
        .filter(PatientOnboardingSaga.status == SagaStatus.FAILED)
        .filter(quarantine_filter)
    )

    total = base_query.count()
    offset = (page - 1) * limit
    rows = (
        base_query.order_by(PatientOnboardingSaga.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = []
    for saga, patient in rows:
        failed_steps = _extract_failed_steps(saga.execution_log or [])
        error_details = saga.error_message or (
            failed_steps[0]["error"] if failed_steps else "Compensation failure"
        )
        timestamp = saga.failed_at or saga.updated_at or saga.created_at
        items.append(
            {
                "saga_id": str(saga.id),
                "patient_id": str(saga.patient_id) if saga.patient_id else None,
                "patient_name": patient.name if patient else None,
                "timestamp": timestamp.isoformat() if timestamp else None,
                "error_details": error_details,
                "failed_steps": failed_steps,
                "status": saga.status.value
                if hasattr(saga.status, "value")
                else str(saga.status),
            }
        )

    pages = math.ceil(total / limit) if limit else 1
    return {
        "data": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


@router.post(
    "/compensation-failures/{saga_id}/retry",
    summary="Retry saga compensation",
    description="Manually retry compensation steps for a failed saga.",
)
async def retry_compensation(
    saga_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
) -> Dict[str, Any]:
    saga = (
        db.query(PatientOnboardingSaga)
        .filter(PatientOnboardingSaga.id == saga_id)
        .first()
    )
    if not saga:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Saga not found"
        )
    if saga.status != SagaStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Saga is not in FAILED state",
        )

    # Manual retry: rerun compensation and unquarantine if the rollback completes.
    compensator = SagaCompensator(
        db=db,
        patient_repo=PatientRepository(db),
        redis_client=get_redis_client(),
    )

    try:
        await compensator.compensate_saga(saga)
    except SagaCompensationError as exc:
        logger.error(
            f"Compensation retry failed for saga {saga_id}: {exc}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(
            f"Unexpected retry error for saga {saga_id}: {exc}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error retrying compensation",
        )

    saga.status = SagaStatus.COMPENSATED
    saga.error_message = None
    saga.error_type = None
    saga.failed_at = None

    patient = None
    if saga.patient_id:
        patient = (
            db.query(Patient).filter(Patient.id == saga.patient_id).first()
        )
    if patient:
        _clear_quarantine(patient)

    db.commit()

    await _log_admin_action(
        db,
        "retry_compensation",
        admin_user,
        context,
        additional_data={"saga_id": str(saga_id)},
    )

    return {"success": True, "message": "Compensation retry completed"}


@router.post(
    "/compensation-failures/{saga_id}/cleanup",
    summary="Cleanup saga artifacts",
    description="Soft delete patient data and mark saga as cleaned up.",
)
async def cleanup_compensation(
    saga_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
) -> Dict[str, Any]:
    saga = (
        db.query(PatientOnboardingSaga)
        .filter(PatientOnboardingSaga.id == saga_id)
        .first()
    )
    if not saga:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Saga not found"
        )

    patient = None
    if saga.patient_id:
        patient = (
            db.query(Patient).filter(Patient.id == saga.patient_id).first()
        )

    # Manual cleanup: soft delete patient and mark saga for auditability.
    if patient:
        patient.deleted_at = now_sao_paulo()
        _clear_quarantine(patient)

    saga.status = SagaStatus.CLEANED_UP
    db.commit()

    await _log_admin_action(
        db,
        "cleanup_compensation",
        admin_user,
        context,
        additional_data={
            "saga_id": str(saga_id),
            "patient_id": str(saga.patient_id) if saga.patient_id else None,
        },
    )

    return {"message": "Compensation cleanup completed"}
