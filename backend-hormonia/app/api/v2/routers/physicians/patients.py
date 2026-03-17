"""
Physician patient list endpoint.

GET /api/v2/physicians/patients — Returns enriched patient list for
the physician dashboard with flow state, phase, and alert counts.

Decision D018: Dedicated endpoint rather than enriching risk-assessments.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.dependencies.auth_dependencies import get_current_user_from_session, get_generic_cache
from app.models.alert import Alert
from app.models.flow import FlowKind, FlowTemplateVersion, PatientFlowState
from app.models.patient import Patient
from app.models.user import UserRole
from app.schemas.v2.physician_patients import (
    PhysicianPatientItem,
    PhysicianPatientListResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/patients",
    response_model=PhysicianPatientListResponse,
    summary="List physician's patients with flow data",
    description="Returns a paginated list of patients for the logged-in physician, "
    "enriched with flow phase, current day, last interaction, and unacknowledged alert count.",
)
async def list_physician_patients(
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_generic_cache),
    search: Optional[str] = Query(None, description="Search by patient name (ILIKE)"),
    flow_phase: Optional[str] = Query(
        None, description="Filter by flow phase: onboarding, daily_follow_up, quiz_mensal"
    ),
    flow_status: Optional[str] = Query(
        None, description="Filter by flow status: active, paused, completed"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
):
    """List patients with enriched flow data for the physician dashboard."""

    # --- Extract user_id and build cache key ---
    user_id = current_user.id if hasattr(current_user, "id") else current_user.get("id")
    cache_key = f"physician:patients:user:{user_id}:page:{page}:size:{size}:search:{search}:phase:{flow_phase}:status:{flow_status}"

    # Try cache first
    try:
        cached_data = await redis_cache.get(cache_key)
        if cached_data is not None:
            logger.debug(f"Cache hit for physician patients: {cache_key}")
            return cached_data
    except Exception:
        logger.debug("Redis cache read failed, falling through to DB")

    # --- Build the latest-flow-state-per-patient subquery ---
    # Rank flow states by started_at DESC to get the most recent per patient
    latest_flow_sq = (
        select(
            PatientFlowState.patient_id,
            PatientFlowState.current_step,
            PatientFlowState.status.label("flow_status"),
            PatientFlowState.last_interaction_at,
            PatientFlowState.flow_template_version_id,
            PatientFlowState.step_data,
            func.row_number()
            .over(
                partition_by=PatientFlowState.patient_id,
                order_by=PatientFlowState.started_at.desc(),
            )
            .label("rn"),
        )
    ).subquery("latest_flow")

    # --- Alert count subquery ---
    alert_count_sq = (
        select(
            Alert.patient_id,
            func.count(Alert.id).label("unack_count"),
        )
        .where(Alert.acknowledged == False)  # noqa: E712
        .group_by(Alert.patient_id)
    ).subquery("alert_counts")

    # --- Main query ---
    query = (
        select(
            Patient.id,
            Patient.name,
            Patient.treatment_type,
            latest_flow_sq.c.flow_status,
            latest_flow_sq.c.current_step,
            latest_flow_sq.c.last_interaction_at,
            latest_flow_sq.c.step_data,
            FlowKind.kind_key.label("flow_phase"),
            func.coalesce(alert_count_sq.c.unack_count, 0).label(
                "unacknowledged_alerts_count"
            ),
        )
        .outerjoin(
            latest_flow_sq,
            and_(
                Patient.id == latest_flow_sq.c.patient_id,
                latest_flow_sq.c.rn == 1,
            ),
        )
        .outerjoin(
            FlowTemplateVersion,
            latest_flow_sq.c.flow_template_version_id == FlowTemplateVersion.id,
        )
        .outerjoin(FlowKind, FlowTemplateVersion.flow_kind_id == FlowKind.id)
        .outerjoin(alert_count_sq, Patient.id == alert_count_sq.c.patient_id)
    )

    # --- Filters ---
    # Doctor sees only their patients; admin sees all
    user_role = getattr(current_user, "role", None)
    is_admin = False
    if user_role:
        role_val = user_role.value if hasattr(user_role, "value") else str(user_role)
        is_admin = role_val.lower() in ("admin", "superadmin")

    if not is_admin:
        query = query.where(Patient.doctor_id == current_user.id)

    if search:
        query = query.where(Patient.name.ilike(f"%{search}%"))

    if flow_phase:
        query = query.where(FlowKind.kind_key == flow_phase)

    if flow_status:
        query = query.where(latest_flow_sq.c.flow_status == flow_status)

    # --- Count total (before pagination) ---
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # --- Pagination + ordering ---
    query = query.order_by(
        # Patients with more alerts first, then by name
        func.coalesce(alert_count_sq.c.unack_count, 0).desc(),
        Patient.name.asc(),
    )
    offset = (page - 1) * size
    query = query.offset(offset).limit(size)

    # --- Execute ---
    result = await db.execute(query)
    rows = result.all()

    # --- Map rows to response items ---
    items = []
    for row in rows:
        # Extract current_flow_day from step_data JSONB
        step_data = row.step_data if row.step_data else {}
        current_day = 0
        if isinstance(step_data, dict):
            raw_day = step_data.get("current_flow_day")
            if raw_day is not None:
                try:
                    current_day = int(raw_day)
                except (TypeError, ValueError):
                    current_day = 0
        if current_day == 0 and row.current_step:
            current_day = int(row.current_step)

        items.append(
            PhysicianPatientItem(
                id=row.id,
                name=row.name,
                flow_phase=row.flow_phase,
                flow_current_day=current_day,
                flow_status=row.flow_status,
                last_interaction=row.last_interaction_at,
                unacknowledged_alerts_count=row.unacknowledged_alerts_count,
                treatment_type=row.treatment_type,
            )
        )

    response = PhysicianPatientListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
    )

    # Cache the serialized response
    try:
        await redis_cache.set(cache_key, response.model_dump(), ttl=60)
    except Exception:
        logger.debug("Redis cache write failed, continuing without cache")

    return response
