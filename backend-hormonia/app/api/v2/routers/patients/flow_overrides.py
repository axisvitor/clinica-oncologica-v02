"""
Patients API v2 - Flow Overrides

GET/PUT endpoints for per-patient flow day overrides.
Merges global template days with patient-specific overrides,
annotating each day with its source and editability.

Endpoints:
  GET  /{patient_id}/flow-overrides  — merged day list
  PUT  /{patient_id}/flow-overrides  — replace future-day overrides
"""

# NOTE: Removed 'from __future__ import annotations' to fix Pydantic/FastAPI
# OpenAPI schema generation issues with Query() and Depends() parameters
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v2.routers.flow_templates import _project_steps_to_day_configs
from app.core.authorization import require_doctor_or_admin
from app.database import get_async_db
from app.dependencies.auth_dependencies import (
    GenericRedisCache,
    get_current_user_from_session,
    get_generic_cache,
)
from app.models.flow import (
    FlowTemplateVersion,
    PatientFlowOverride,
    PatientFlowState,
)
from app.schemas.v2.patient_overrides import (
    MergedDayItem,
    MergedDayListResponse,
    OverrideDayUpdateRequest,
)
from app.utils.rate_limiter import limiter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["patient-flow-overrides"])


# ── Helpers ──────────────────────────────────────────────────────


async def _get_active_flow_state(
    patient_id: UUID,
    db: AsyncSession,
) -> PatientFlowState:
    """Return the most recent active flow state or raise 404."""
    result = await db.execute(
        select(PatientFlowState)
        .where(
            PatientFlowState.patient_id == patient_id,
            PatientFlowState.status == "active",
        )
        .order_by(PatientFlowState.started_at.desc())
        .limit(1)
    )
    flow_state = result.scalar_one_or_none()
    if flow_state is None:
        raise HTTPException(
            status_code=404,
            detail="No active flow state found for this patient",
        )
    return flow_state


async def _build_merged_days(
    flow_state: PatientFlowState,
    db: AsyncSession,
) -> MergedDayListResponse:
    """Build the merged global + override day list for a flow state."""
    # 1. Load template steps
    template_result = await db.execute(
        select(FlowTemplateVersion).where(
            FlowTemplateVersion.id == flow_state.flow_template_version_id,
        )
    )
    template_version = template_result.scalar_one_or_none()
    steps = template_version.steps if template_version else []

    # 2. Project to day configs
    global_days = _project_steps_to_day_configs(steps or [])

    # 3. Load overrides
    override_result = await db.execute(
        select(PatientFlowOverride).where(
            PatientFlowOverride.patient_flow_state_id == flow_state.id,
        )
    )
    overrides = override_result.scalars().all()
    override_lookup = {o.day_number: o for o in overrides}

    # 4. Current flow day
    step_data = flow_state.step_data or {}
    current_flow_day = int(step_data.get("current_flow_day", 0))

    # 5. Merge global days with overrides
    merged: list[MergedDayItem] = []
    seen_day_numbers: set[int] = set()

    for gd in global_days:
        day_num = gd.day_number
        seen_day_numbers.add(day_num)
        editable = day_num > current_flow_day

        if day_num in override_lookup:
            ov = override_lookup[day_num]
            merged.append(
                MergedDayItem(
                    day_number=day_num,
                    content=ov.content,
                    message_type=ov.message_type,
                    expects_response=ov.expects_response,
                    skip=ov.skip,
                    source="override",
                    editable=editable,
                )
            )
        else:
            merged.append(
                MergedDayItem(
                    day_number=day_num,
                    content=gd.content,
                    message_type=gd.message_type,
                    expects_response=gd.expects_response,
                    skip=False,
                    source="global",
                    editable=editable,
                )
            )

    # 6. Append extra override-only days (not in global template)
    for day_num, ov in override_lookup.items():
        if day_num not in seen_day_numbers:
            merged.append(
                MergedDayItem(
                    day_number=day_num,
                    content=ov.content,
                    message_type=ov.message_type,
                    expects_response=ov.expects_response,
                    skip=ov.skip,
                    source="override",
                    editable=day_num > current_flow_day,
                )
            )

    # 7. Sort by day_number
    merged.sort(key=lambda d: d.day_number)

    return MergedDayListResponse(
        patient_id=flow_state.patient_id,
        flow_state_id=flow_state.id,
        current_flow_day=current_flow_day,
        days=merged,
    )


# ── Endpoints ────────────────────────────────────────────────────


@router.get(
    "/{patient_id}/flow-overrides",
    response_model=MergedDayListResponse,
    summary="Get merged flow day list",
    description=(
        "Returns the full merged day list (global template + patient overrides) "
        "with source annotation and editability per day."
    ),
)
@require_doctor_or_admin()
@limiter.limit("30/minute")
async def get_flow_overrides(
    request: Request,
    patient_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
):
    """
    Get merged flow day list for a patient.

    Returns each day annotated with:
    - ``source``: "global" (from template) or "override" (patient-specific)
    - ``editable``: whether the physician can still modify this day

    Raises:
        HTTPException 404: No active flow state for this patient.
    """
    flow_state = await _get_active_flow_state(patient_id, db)
    return await _build_merged_days(flow_state, db)


@router.put(
    "/{patient_id}/flow-overrides",
    response_model=MergedDayListResponse,
    summary="Replace patient flow overrides",
    description=(
        "Replace all future-day overrides for a patient. "
        "Returns the updated merged day list."
    ),
)
@require_doctor_or_admin()
@limiter.limit("10/minute")
async def put_flow_overrides(
    request: Request,
    patient_id: UUID,
    body: OverrideDayUpdateRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
    cache: GenericRedisCache = Depends(get_generic_cache),
):
    """
    Replace all overrides for a patient's active flow state.

    Only future days (day_number > current_flow_day) can be overridden.
    Uses a DELETE + INSERT transaction to atomically replace overrides.

    Raises:
        HTTPException 404: No active flow state.
        HTTPException 400: Attempt to override a past/current day.
    """
    flow_state = await _get_active_flow_state(patient_id, db)

    step_data = flow_state.step_data or {}
    current_flow_day = int(step_data.get("current_flow_day", 0))

    # Validate: all days must be in the future
    for day in body.days:
        if day.day_number <= current_flow_day:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot override day {day.day_number}: "
                    f"already sent (current day is {current_flow_day})"
                ),
            )

    # Transaction: DELETE existing + INSERT new
    await db.execute(
        delete(PatientFlowOverride).where(
            PatientFlowOverride.patient_flow_state_id == flow_state.id,
        )
    )

    for day in body.days:
        db.add(
            PatientFlowOverride(
                patient_flow_state_id=flow_state.id,
                day_number=day.day_number,
                content=day.content,
                message_type=day.message_type,
                expects_response=day.expects_response,
                skip=day.skip,
                created_by=current_user.id,
            )
        )

    await db.flush()

    # Cache invalidation
    try:
        await cache.delete_pattern(f"flow_override:{flow_state.id}:*")
    except Exception:
        logger.warning(
            "Failed to invalidate flow_override cache for state %s",
            flow_state.id,
        )

    # Structured log
    logger.info(
        "Flow overrides saved",
        extra={
            "patient_id": str(patient_id),
            "flow_state_id": str(flow_state.id),
            "override_count": len(body.days),
        },
    )

    # Return updated merged view
    return await _build_merged_days(flow_state, db)
