"""
Admin flow control endpoints for manual recovery operations.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.async_engine import get_async_db
from app.models.flow import PatientFlowState
from app.models.patient import Patient
from app.models.user import User
from app.schemas.v2.admin_extensions import (
    FailedFlowOperation,
    FailedFlowOperationsResponse,
    FlowOpsAdvanceResponse,
    FlowOpsResetResponse,
    FlowOpsUnstickResponse,
)
from app.services.audit import AuditService
from app.services.flow.management.advancement import advance_day_atomic
from app.utils.rate_limiter import limiter
from app.utils.request_context import RequestContext, get_request_context
from app.utils.timezone import now_sao_paulo

from .dependencies import get_admin_user, log_admin_extension_action

router = APIRouter()

RESET_FIELDS = [
    "awaiting_response",
    "context_mismatch_count",
    "pending_response_context",
]
UNSTICK_FIELDS = [
    "awaiting_response",
    "recovery_attempts",
    "last_recovery_at",
    "context_mismatch_count",
]


async def _get_active_flow(
    db: AsyncSession, patient_id: UUID
) -> PatientFlowState | None:
    result = await db.execute(
        select(PatientFlowState)
        .join(Patient)
        .where(
            PatientFlowState.patient_id == patient_id,
            PatientFlowState.completed_at.is_(None),
            Patient.deleted_at.is_(None),
        )
        .order_by(PatientFlowState.started_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _clear_step_fields(
    flow_state: PatientFlowState, fields: list[str]
) -> dict[str, Any]:
    step_data = dict(flow_state.step_data or {})
    for field in fields:
        step_data.pop(field, None)
    flow_state.step_data = step_data
    flow_state.last_interaction_at = now_sao_paulo()
    flow_state.version = (flow_state.version or 0) + 1
    return step_data


def _flow_kind_for(flow_state: PatientFlowState) -> str:
    step_data = flow_state.step_data or {}
    flow_kind = step_data.get("flow_kind")
    if isinstance(flow_kind, str) and flow_kind.strip():
        return flow_kind
    return "onboarding"


def _current_flow_day(flow_state: PatientFlowState) -> int:
    try:
        return max(int(flow_state.current_day or 0), 1)
    except (TypeError, ValueError):
        return 1


def _map_failed_operation(
    flow_state: PatientFlowState, patient_name: str | None
) -> FailedFlowOperation:
    step_data = dict(flow_state.step_data or {})
    delivery_failures = list(step_data.get("delivery_failures") or [])

    if delivery_failures:
        failure_type = "delivery_failure"
        failure_details = {
            "delivery_failures": delivery_failures,
            "permanently_failed_at": step_data.get("permanently_failed_at"),
        }
    else:
        failure_type = "mismatch_reset"
        failure_details = {
            "last_mismatch_reset_at": step_data.get("last_mismatch_reset_at"),
            "context_mismatch_count": step_data.get("context_mismatch_count"),
        }

    return FailedFlowOperation(
        flow_state_id=flow_state.id,
        patient_id=flow_state.patient_id,
        patient_name=patient_name,
        current_step=flow_state.current_step,
        failure_type=failure_type,
        failure_details=failure_details,
        updated_at=flow_state.updated_at,
    )


@router.post(
    "/{patient_id}/reset",
    response_model=FlowOpsResetResponse,
    summary="Reset a patient flow",
)
@limiter.limit("30/minute")
async def reset_flow(
    request: Request,
    patient_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    admin_user: User | dict[str, Any] = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    flow_state = await _get_active_flow(db, patient_id)
    if flow_state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active flow not found",
        )

    _clear_step_fields(flow_state, RESET_FIELDS)
    await db.commit()

    await log_admin_extension_action(
        AuditService(db),
        "flow_reset",
        admin_user,
        context,
        additional_data={
            "patient_id": str(patient_id),
            "flow_state_id": str(flow_state.id),
            "cleared_fields": RESET_FIELDS,
        },
    )

    return FlowOpsResetResponse(
        patient_id=patient_id,
        flow_state_id=flow_state.id,
        cleared_fields=RESET_FIELDS,
    )


@router.post(
    "/{patient_id}/advance",
    response_model=FlowOpsAdvanceResponse,
    summary="Advance a patient flow to the next day",
)
@limiter.limit("30/minute")
async def advance_flow(
    request: Request,
    patient_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    admin_user: User | dict[str, Any] = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    flow_state = await _get_active_flow(db, patient_id)
    if flow_state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active flow not found",
        )

    current_day = _current_flow_day(flow_state)
    new_day = current_day + 1
    current_step_data = dict(flow_state.step_data or {})

    await advance_day_atomic(
        db=db,
        flow_state=flow_state,
        patient_id=patient_id,
        day_number=current_day,
        flow_kind=_flow_kind_for(flow_state),
        message_index=int(current_step_data.get("current_day_message_index") or 0),
    )

    updated_step_data = dict(flow_state.step_data or {})
    updated_step_data["current_flow_day"] = new_day
    updated_step_data["current_day_message_index"] = 0
    updated_step_data["awaiting_response"] = False
    updated_step_data["day_complete"] = False
    updated_step_data["flow_kind"] = _flow_kind_for(flow_state)
    updated_step_data["last_advancement"] = now_sao_paulo().isoformat()
    updated_step_data.pop("pending_response_context", None)

    flow_state.current_step = new_day
    flow_state.step_data = updated_step_data
    flow_state.last_interaction_at = now_sao_paulo()
    flow_state.version = (flow_state.version or 0) + 1
    await db.commit()

    await log_admin_extension_action(
        AuditService(db),
        "flow_advance",
        admin_user,
        context,
        additional_data={
            "patient_id": str(patient_id),
            "flow_state_id": str(flow_state.id),
            "new_day": new_day,
        },
    )

    return FlowOpsAdvanceResponse(
        patient_id=patient_id,
        flow_state_id=flow_state.id,
        new_day=new_day,
    )


@router.post(
    "/{patient_id}/unstick",
    response_model=FlowOpsUnstickResponse,
    summary="Clear stuck state from a patient flow",
)
@limiter.limit("30/minute")
async def unstick_flow(
    request: Request,
    patient_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    admin_user: User | dict[str, Any] = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    flow_state = await _get_active_flow(db, patient_id)
    if flow_state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active flow not found",
        )

    _clear_step_fields(flow_state, UNSTICK_FIELDS)
    await db.commit()

    await log_admin_extension_action(
        AuditService(db),
        "flow_unstick",
        admin_user,
        context,
        additional_data={
            "patient_id": str(patient_id),
            "flow_state_id": str(flow_state.id),
            "cleared_fields": UNSTICK_FIELDS,
        },
    )

    return FlowOpsUnstickResponse(
        patient_id=patient_id,
        flow_state_id=flow_state.id,
        cleared_fields=UNSTICK_FIELDS,
    )


@router.get(
    "/failed",
    response_model=FailedFlowOperationsResponse,
    summary="List failed flow operations",
)
@limiter.limit("60/minute")
async def list_failed_flow_operations(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_db),
    admin_user: User | dict[str, Any] = Depends(get_admin_user),
):
    del request, admin_user

    failed_filters = (
        Patient.deleted_at.is_(None),
        or_(
            PatientFlowState.step_data.has_key("delivery_failures"),
            PatientFlowState.step_data.has_key("last_mismatch_reset_at"),
        ),
    )

    total_result = await db.execute(
        select(func.count(PatientFlowState.id))
        .select_from(PatientFlowState)
        .join(Patient)
        .where(*failed_filters)
    )
    total = total_result.scalar() or 0

    rows_result = await db.execute(
        select(PatientFlowState, Patient.name)
        .join(Patient)
        .where(*failed_filters)
        .order_by(PatientFlowState.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = rows_result.all()

    items = [_map_failed_operation(flow_state, patient_name) for flow_state, patient_name in rows]

    return FailedFlowOperationsResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


__all__ = ["router"]
