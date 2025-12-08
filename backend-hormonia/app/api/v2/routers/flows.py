import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status, Request

from app.database import get_db
from app.models.user import User
from app.models.patient import Patient
from app.schemas.v2.flows import (
    FlowStateV2Response, FlowAdvanceV2Request, FlowAdvanceV2Response,
    FlowPauseV2Request, FlowPauseV2Response, FlowResumeV2Response,
    FlowHistoryV2Response, FlowTemplateV2List
)
from app.dependencies import (
    get_current_user, validate_patient_access, 
    get_flow_management_service
)
from app.dependencies.service_dependencies import get_flow_analytics_service
from app.services.flow_dashboard import get_flow_dashboard_service
from app.services.enhanced_flow_engine import EnhancedFlowEngine
from app.services.flow_service import FlowService
from app.api.v2.dependencies import get_pagination_params, get_eager_load_params
from app.utils.rate_limiter import limiter

logger = logging.getLogger(__name__)
router = APIRouter()

def get_flow_service_dependency(
    db = Depends(get_db),
    flow_management=Depends(get_flow_management_service),
    flow_analytics=Depends(get_flow_analytics_service),
    flow_dashboard=Depends(get_flow_dashboard_service),
) -> FlowService:
    # Instantiate flow engine directly
    flow_engine = EnhancedFlowEngine(db)
    return FlowService(db, flow_management, flow_analytics, flow_dashboard, flow_engine)

@router.get("/{patient_id}/state")
# @router.get("/{patient_id}/state", response_model=FlowStateV2Response)
async def get_flow_state(
    patient_id: UUID,
    patient: Patient = Depends(validate_patient_access),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    service = Depends(get_flow_service_dependency)
):
    return await service.get_flow_state(patient_id, include)

@router.post("/{patient_id}/advance", response_model=FlowAdvanceV2Response)
async def advance_patient_flow(
    patient_id: UUID,
    request: FlowAdvanceV2Request,
    patient: Patient = Depends(validate_patient_access),
    service: FlowService = Depends(get_flow_service_dependency)
):
    return await service.advance_patient_flow(patient_id, request.force_day)

@router.post("/{patient_id}/pause", response_model=FlowPauseV2Response)
async def pause_patient_flow(
    patient_id: UUID,
    request: Optional[FlowPauseV2Request] = None,
    current_user: User = Depends(get_current_user),
    patient: Patient = Depends(validate_patient_access),
    service: FlowService = Depends(get_flow_service_dependency)
):
    reason = request.reason if request else "Manual pause"
    duration = request.duration_hours if request else None
    return await service.pause_patient_flow(patient_id, reason, duration, current_user.id)

@router.post("/{patient_id}/resume", response_model=FlowResumeV2Response)
async def resume_patient_flow(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    patient: Patient = Depends(validate_patient_access),
    service: FlowService = Depends(get_flow_service_dependency)
):
    return await service.resume_patient_flow(patient_id, current_user.id)

@router.get("/{patient_id}/history", response_model=FlowHistoryV2Response)
async def get_patient_flow_history(
    patient_id: UUID,
    pagination = Depends(get_pagination_params),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    patient: Patient = Depends(validate_patient_access),
    service: FlowService = Depends(get_flow_service_dependency)
):
    return await service.get_patient_flow_history(patient_id, pagination, include)

@router.post("/start", response_model=FlowStateV2Response, status_code=status.HTTP_201_CREATED)
async def start_flow(
    patient_id: UUID = Query(...),
    flow_type: str = Query(...),
    current_user: User = Depends(get_current_user),
    service: FlowService = Depends(get_flow_service_dependency)
):
    return await service.start_patient_flow(patient_id, flow_type, current_user.id)

@router.post("/{patient_id}/response", response_model=FlowAdvanceV2Response)
async def process_patient_response(
    patient_id: UUID,
    response_text: str = Query(...),
    response_metadata: Optional[Dict[str, Any]] = None,
    patient: Patient = Depends(validate_patient_access),
    service: FlowService = Depends(get_flow_service_dependency)
):
    return await service.process_patient_response(patient_id, response_text, response_metadata or {})
