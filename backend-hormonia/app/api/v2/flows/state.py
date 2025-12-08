"""
Flow State Operations
Handles flow state management: get, advance, pause, resume, history
"""

import logging
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session, joinedload

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
from ..dependencies import (
    get_pagination_params,
    get_eager_load_params,
)
from app.dependencies import (
    get_current_user,
    validate_patient_access,
    get_flow_management_service,
)
from app.services.flow_management import FlowManagementService
from app.exceptions import (
    FlowStateNotFoundError,
    FlowOperationError,
    FlowStateConflictError,
    flow_not_found_exception,
    flow_operation_exception,
    internal_server_exception,
)
import base64
import json

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================

def _create_cursor(item_id: str, created_at: datetime) -> str:
    """Create cursor for pagination"""
    cursor_data = {
        "id": str(item_id),
        "created_at": created_at.isoformat()
    }
    return base64.b64encode(json.dumps(cursor_data).encode()).decode()


# ============================================================================
# Flow State Operations (5 endpoints)
# ============================================================================

@router.get(
    "/{patient_id}/state",
    response_model=FlowStateV2Response,
    summary="Get flow state",
    description="Get patient's current flow state with optional eager loading"
)
async def get_flow_state(
    patient_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
    include: Optional[List[str]] = Depends(get_eager_load_params),
):
    """
    Get patient's current flow state.

    Supports eager loading:
    - ?include=patient,template
    """
    repo = PatientRepository(db)
    patient = repo.get_by_id(patient_id)
    if not patient:
        raise flow_not_found_exception(str(patient_id))
    
    if patient.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this patient"
        )

    try:
        flow_state = await flow_management.get_patient_flow_state(patient_id)

        # Eager load relationships if requested
        if include:
            query = db.query(flow_state.__class__)
            if "patient" in include:
                query = query.options(joinedload(flow_state.__class__.patient))
            if "template" in include:
                query = query.options(joinedload(flow_state.__class__.template))

            flow_state = query.filter_by(id=flow_state.id).first()

        return flow_state

    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except Exception as e:
        logger.exception(f"Error getting flow state for patient {patient_id}")
        raise internal_server_exception("Failed to get flow state")


@router.post(
    "/{patient_id}/advance",
    response_model=FlowAdvanceV2Response,
    summary="Advance flow",
    description="Manually advance patient flow to next step or specific day"
)
async def advance_patient_flow(
    patient_id: UUID,
    request: FlowAdvanceV2Request,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Advance patient flow with optional force to specific day"""
    # Validate patient access
    repo = PatientRepository(db)
    patient = repo.get_by_id(patient_id)
    if not patient:
        raise flow_not_found_exception(str(patient_id))
    
    if patient.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this patient"
        )

    try:
        advancement = await flow_management.advance_patient_flow(
            patient_id=patient_id,
            force_day=request.force_day
        )

        return FlowAdvanceV2Response(
            success=True,
            patient_id=str(patient_id),
            previous_step=advancement.get("previous_step", 0),
            current_step=advancement.get("current_step", 0),
            next_actions=advancement.get("next_actions", []),
            message=advancement.get("message", "Flow advanced successfully")
        )

    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except FlowOperationError as e:
        raise flow_operation_exception("advance_flow", str(e))
    except Exception as e:
        logger.exception(f"Error advancing flow for patient {patient_id}")
        raise internal_server_exception("Failed to advance flow")


@router.post(
    "/{patient_id}/pause",
    response_model=FlowPauseV2Response,
    summary="Pause flow",
    description="Pause patient flow with optional auto-resume duration"
)
async def pause_patient_flow(
    patient_id: UUID,
    request: Optional[FlowPauseV2Request] = None,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Pause patient flow with optional auto-resume"""
    # Validate patient access
    repo = PatientRepository(db)
    patient = repo.get_by_id(patient_id)
    if not patient:
        raise flow_not_found_exception(str(patient_id))
    
    if patient.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this patient"
        )

    try:
        reason = request.reason if request else "Manual pause"
        duration_hours = request.duration_hours if request else None

        pause_result = await flow_management.pause_patient_flow(
            patient_id=patient_id,
            reason=reason,
            duration_hours=duration_hours,
            user_id=current_user.id
        )

        return FlowPauseV2Response(
            success=True,
            patient_id=str(patient_id),
            paused_at=pause_result.get("paused_at", datetime.utcnow()),
            reason=reason,
            auto_resume_at=pause_result.get("auto_resume_at"),
            message=pause_result.get("message", "Flow paused successfully")
        )

    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except FlowStateConflictError as e:
        raise flow_operation_exception("pause_flow", str(e))
    except Exception as e:
        logger.exception(f"Error pausing flow for patient {patient_id}")
        raise internal_server_exception("Failed to pause flow")


@router.post(
    "/{patient_id}/resume",
    response_model=FlowResumeV2Response,
    summary="Resume flow",
    description="Resume a paused patient flow"
)
async def resume_patient_flow(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Resume a previously paused flow"""
    # Validate patient access
    repo = PatientRepository(db)
    patient = repo.get_by_id(patient_id)
    if not patient:
        raise flow_not_found_exception(str(patient_id))
    
    if patient.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this patient"
        )

    try:
        resume_result = await flow_management.resume_patient_flow(
            patient_id=patient_id,
            user_id=current_user.id
        )

        return FlowResumeV2Response(
            success=True,
            patient_id=str(patient_id),
            resumed_at=resume_result.get("resumed_at", datetime.utcnow()),
            paused_duration_hours=resume_result.get("paused_duration_hours", 0.0),
            next_message_at=resume_result.get("next_message_at"),
            message=resume_result.get("message", "Flow resumed successfully")
        )

    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except FlowStateConflictError as e:
        raise flow_operation_exception("resume_flow", str(e))
    except Exception as e:
        logger.exception(f"Error resuming flow for patient {patient_id}")
        raise internal_server_exception("Failed to resume flow")


@router.get(
    "/{patient_id}/history",
    response_model=FlowHistoryV2Response,
    summary="Get flow history",
    description="Get paginated flow history for a patient"
)
async def get_patient_flow_history(
    patient_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
    pagination = Depends(get_pagination_params),
    include: Optional[List[str]] = Depends(get_eager_load_params),
):
    """
    Get patient flow history with cursor pagination.

    Supports eager loading:
    - ?include=patient,template
    """
    # Validate patient access
    repo = PatientRepository(db)
    patient = repo.get_by_id(patient_id)
    if not patient:
        raise flow_not_found_exception(str(patient_id))
    
    if patient.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this patient"
        )

    try:
        cursor_data = pagination["cursor_data"]
        limit = pagination["limit"]

        # Build query
        from app.models.flow import FlowState as FlowStateModel
        query = db.query(FlowStateModel).filter(
            FlowStateModel.patient_id == patient_id
        )

        # Apply eager loading
        if include:
            if "patient" in include:
                query = query.options(joinedload(FlowStateModel.patient))
            if "template" in include:
                query = query.options(joinedload(FlowStateModel.template))

        # Apply cursor pagination
        if cursor_data and "id" in cursor_data:
            cursor_id = UUID(cursor_data["id"])
            cursor_created = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))
            query = query.filter(
                (FlowStateModel.created_at < cursor_created) |
                ((FlowStateModel.created_at == cursor_created) & (FlowStateModel.id > cursor_id))
            )

        # Get total count (only on first page)
        total = None
        if not cursor_data:
            total = query.count()

        # Order and limit
        query = query.order_by(FlowStateModel.created_at.desc(), FlowStateModel.id)
        flow_states = query.limit(limit + 1).all()

        # Check if there are more results
        has_more = len(flow_states) > limit
        if has_more:
            flow_states = flow_states[:limit]

        # Create next cursor
        next_cursor = None
        if has_more and flow_states:
            next_cursor = _create_cursor(flow_states[-1].id, flow_states[-1].created_at)

        # Get current flow
        current_flow = await flow_management.get_patient_flow_state(patient_id)

        return FlowHistoryV2Response(
            patient_id=str(patient_id),
            data=[FlowStateV2Response.from_orm(fs) for fs in flow_states],
            next_cursor=next_cursor,
            has_more=has_more,
            total=total,
            current_flow=FlowStateV2Response.from_orm(current_flow) if current_flow else None
        )

    except Exception as e:
        logger.exception(f"Error getting flow history for patient {patient_id}")
        raise internal_server_exception("Failed to get flow history")
