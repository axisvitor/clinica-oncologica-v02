import logging
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.database import get_db
from app.models.user import User
from app.models.patient import Patient
from app.schemas.v2.flows import (
    FlowStateV2Response,
    FlowAdvanceV2Request,
    FlowAdvanceV2Response,
    FlowPauseV2Request,
    FlowPauseV2Response,
    FlowResumeV2Response,
    FlowHistoryV2Response,
)
from app.dependencies import (
    get_current_user,
    validate_patient_access,
    get_flow_management_service,
)
from app.dependencies.service_dependencies import get_flow_analytics_service
from app.services.flow_dashboard import get_flow_dashboard_service
from app.services.enhanced_flow_engine import EnhancedFlowEngine
from app.services.flow_service import FlowService
from app.api.v2.dependencies import get_pagination_params, get_eager_load_params

logger = logging.getLogger(__name__)
router = APIRouter()


def get_flow_service_dependency(
    db=Depends(get_db),
    flow_management=Depends(get_flow_management_service),
    flow_analytics=Depends(get_flow_analytics_service),
    flow_dashboard=Depends(get_flow_dashboard_service),
) -> FlowService:
    # Instantiate flow engine directly
    flow_engine = EnhancedFlowEngine(db)
    return FlowService(db, flow_management, flow_analytics, flow_dashboard, flow_engine)


# Static routes must come before parameterized routes
@router.get("/analytics", summary="Get flow analytics and statistics")
async def get_flow_analytics(
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get aggregated flow analytics for dashboard display.

    Returns:
    - Total flows count (active, paused, completed)
    - Weekly/monthly trends
    - Average response times
    - Completion rates
    """
    from sqlalchemy import func
    from app.models.patient import Patient
    from app.models.user import UserRole
    from datetime import datetime, timedelta, timezone

    user_role = current_user.role
    user_id = current_user.id

    # Build base query
    query = db.query(Patient.flow_state, func.count(Patient.id).label("count"))

    # Filter by doctor if not admin
    if user_role != UserRole.ADMIN:
        query = query.filter(Patient.doctor_id == user_id)

    results = query.group_by(Patient.flow_state).all()

    # Build status counts
    status_counts = {
        "active": 0,
        "paused": 0,
        "completed": 0,
        "onboarding": 0,
        "cancelled": 0,
    }

    for flow_state, count in results:
        if flow_state:
            state_value = flow_state.value if hasattr(flow_state, 'value') else str(flow_state)
            if state_value in status_counts:
                status_counts[state_value] = count

    total = sum(status_counts.values())
    active_count = status_counts["active"]
    completed_count = status_counts["completed"]

    # Calculate completion rate
    completion_rate = round((completed_count / total * 100) if total > 0 else 0, 1)

    # Get 7-day trend (simplified)
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_query = db.query(func.count(Patient.id)).filter(
        Patient.created_at >= seven_days_ago
    )
    if user_role != UserRole.ADMIN:
        recent_query = recent_query.filter(Patient.doctor_id == user_id)
    new_patients_7d = recent_query.scalar() or 0

    return {
        "total_flows": total,
        "active_flows": active_count,
        "paused_flows": status_counts["paused"],
        "completed_flows": completed_count,
        "onboarding_flows": status_counts["onboarding"],
        "completion_rate": completion_rate,
        "new_patients_7d": new_patients_7d,
        "status_distribution": status_counts,
        "avg_response_time_minutes": 0,  # TODO: Calculate from quiz responses
        "weekly_trend": [],  # TODO: Add weekly data points
    }


@router.get("/{patient_id}/state")
# @router.get("/{patient_id}/state", response_model=FlowStateV2Response)
async def get_flow_state(
    patient_id: UUID,
    patient: Patient = Depends(validate_patient_access),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    service=Depends(get_flow_service_dependency),
):
    return await service.get_flow_state(patient_id, include)


@router.post("/{patient_id}/advance", response_model=FlowAdvanceV2Response)
async def advance_patient_flow(
    patient_id: UUID,
    request: FlowAdvanceV2Request,
    patient: Patient = Depends(validate_patient_access),
    service: FlowService = Depends(get_flow_service_dependency),
):
    return await service.advance_patient_flow(patient_id, request.force_day)


@router.post("/{patient_id}/pause", response_model=FlowPauseV2Response)
async def pause_patient_flow(
    patient_id: UUID,
    request: Optional[FlowPauseV2Request] = None,
    current_user: User = Depends(get_current_user),
    patient: Patient = Depends(validate_patient_access),
    service: FlowService = Depends(get_flow_service_dependency),
):
    reason = request.reason if request else "Manual pause"
    duration = request.duration_hours if request else None
    return await service.pause_patient_flow(
        patient_id, reason, duration, current_user.id
    )


@router.post("/{patient_id}/resume", response_model=FlowResumeV2Response)
async def resume_patient_flow(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    patient: Patient = Depends(validate_patient_access),
    service: FlowService = Depends(get_flow_service_dependency),
):
    return await service.resume_patient_flow(patient_id, current_user.id)


@router.get("/{patient_id}/history", response_model=FlowHistoryV2Response)
async def get_patient_flow_history(
    patient_id: UUID,
    pagination=Depends(get_pagination_params),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    patient: Patient = Depends(validate_patient_access),
    service: FlowService = Depends(get_flow_service_dependency),
):
    return await service.get_patient_flow_history(patient_id, pagination, include)


@router.post(
    "/start", response_model=FlowStateV2Response, status_code=status.HTTP_201_CREATED
)
async def start_flow(
    patient_id: UUID = Query(...),
    flow_type: str = Query(...),
    current_user: User = Depends(get_current_user),
    service: FlowService = Depends(get_flow_service_dependency),
):
    return await service.start_patient_flow(patient_id, flow_type, current_user.id)



@router.post("/{patient_id}/response", response_model=FlowAdvanceV2Response)
async def process_patient_response(
    patient_id: UUID,
    response_text: str = Query(...),
    response_metadata: Optional[Dict[str, Any]] = None,
    patient: Patient = Depends(validate_patient_access),
    service: FlowService = Depends(get_flow_service_dependency),
):
    return await service.process_patient_response(
        patient_id, response_text, response_metadata or {}
    )

