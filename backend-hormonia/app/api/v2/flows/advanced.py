"""
Flow Advanced Features
Handles rules engine and utility operations
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException, status, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_

from app.database import get_db
from app.models.user import User
from app.schemas.v2.flows import (
    FlowStateV2Response,
    FlowAdvanceV2Response,
    FlowRuleV2Create,
    FlowRuleV2Update,
    FlowRuleV2Response,
    FlowRuleV2List,
)
from ..dependencies import (
    get_pagination_params,
    get_eager_load_params,
)
from app.dependencies.auth_dependencies import get_current_user
from app.dependencies.service_dependencies import get_flow_management_service
from app.repositories.patient import PatientRepository
from app.dependencies.service_dependencies import (
    get_flow_analytics_service,
    get_flow_engine,
)
from app.dependencies.auth_dependencies import get_redis_cache
from app.services.flow_management import FlowManagementService
from app.services.enhanced_flow_engine import EnhancedFlowEngine
from app.exceptions import (
    FlowStateNotFoundError,
    FlowOperationError,
    flow_not_found_exception,
    flow_operation_exception,
    internal_server_exception,
)
from app.utils.rate_limiter import limiter
from app.utils.cursor import encode_cursor as _create_cursor
from app.utils.timezone import now_sao_paulo
from .cache import get_cached_or_compute as _get_cached_or_compute

router = APIRouter()
logger = logging.getLogger(__name__)

# Redis cache TTL constants (in seconds)
CACHE_TTL_ANALYTICS = 900  # 15 minutes


# ============================================================================
# Rules Engine (4 endpoints)
# ============================================================================


@router.post(
    "/rules",
    response_model=FlowRuleV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Create flow rule",
    description="Create conditional flow rule",
)
@limiter.limit("10/hour")
async def create_flow_rule(
    request: Request,
    rule_data: FlowRuleV2Create,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Create flow rule for conditional logic"""
    try:
        rule = await flow_management.create_flow_rule(
            rule_data=rule_data, created_by=current_user.id
        )
        return FlowRuleV2Response.from_orm(rule)
    except Exception as e:
        logger.error(f"Failed to create flow rule: {e}")
        raise flow_operation_exception("create_rule", str(e))


@router.get(
    "/rules",
    response_model=FlowRuleV2List,
    summary="List flow rules",
    description="Get paginated list of flow rules",
)
async def get_flow_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    pagination=Depends(get_pagination_params),
    flow_type: Optional[str] = Query(None),
    active_only: bool = Query(True),
):
    """List flow rules with cursor pagination"""
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    # Build query
    from app.models.flow import FlowRule

    query = db.query(FlowRule)

    # Apply filters
    filters = []
    if active_only:
        filters.append(FlowRule.is_active)
    if flow_type:
        filters.append(FlowRule.flow_type == flow_type)

    # Apply cursor
    if cursor_data and "id" in cursor_data:
        cursor_id = UUID(cursor_data["id"])
        cursor_created = datetime.fromisoformat(
            cursor_data["created_at"]
        )
        filters.append(
            (FlowRule.created_at < cursor_created)
            | ((FlowRule.created_at == cursor_created) & (FlowRule.id > cursor_id))
        )

    if filters:
        query = query.filter(and_(*filters))

    # Get total (only on first page)
    total = None
    if not cursor_data:
        total = query.count()

    # Order and limit
    query = query.order_by(FlowRule.created_at.desc(), FlowRule.id)
    rules = query.limit(limit + 1).all()

    # Check for more results
    has_more = len(rules) > limit
    if has_more:
        rules = rules[:limit]

    # Create next cursor
    next_cursor = None
    if has_more and rules:
        next_cursor = _create_cursor(rules[-1].id, rules[-1].created_at)

    return FlowRuleV2List(
        data=[FlowRuleV2Response.from_orm(r) for r in rules],
        next_cursor=next_cursor,
        has_more=has_more,
        total=total,
    )


@router.put(
    "/rules/{rule_id}",
    response_model=FlowRuleV2Response,
    summary="Update flow rule",
    description="Update existing flow rule",
)
@limiter.limit("20/hour")
async def update_flow_rule(
    request: Request,
    rule_id: UUID,
    rule_data: FlowRuleV2Update,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Update flow rule"""
    try:
        rule = await flow_management.update_flow_rule(
            rule_id=rule_id, rule_data=rule_data, updated_by=current_user.id
        )
        return FlowRuleV2Response.from_orm(rule)
    except FlowStateNotFoundError:
        raise flow_not_found_exception(f"rule_{rule_id}")
    except Exception as e:
        logger.error(f"Failed to update flow rule {rule_id}: {e}")
        raise flow_operation_exception("update_rule", str(e))


@router.delete(
    "/rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete flow rule",
    description="Delete a flow rule",
)
@limiter.limit("10/hour")
async def delete_flow_rule(
    request: Request,
    rule_id: UUID,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Delete flow rule"""
    try:
        await flow_management.delete_flow_rule(
            rule_id=rule_id, deleted_by=current_user.id
        )
        return None
    except FlowStateNotFoundError:
        raise flow_not_found_exception(f"rule_{rule_id}")
    except Exception as e:
        logger.error(f"Failed to delete flow rule {rule_id}: {e}")
        raise internal_server_exception("Failed to delete flow rule")


# ============================================================================
# Utility Operations (7 endpoints)
# ============================================================================


@router.post(
    "/preview-message",
    summary="Preview flow message",
    description="Preview AI-powered flow message without sending",
)
async def preview_flow_message(
    patient_id: UUID,
    template_id: UUID,
    day: int = Query(1, ge=1),
    current_user: User = Depends(get_current_user),
    flow_engine: EnhancedFlowEngine = Depends(get_flow_engine),
):
    """Preview flow message for healthcare providers"""
    try:
        # Using generate_flow_message which incorporates AI
        preview = await flow_engine.generate_flow_message(
            patient_id=patient_id, day=day
        )
        return {
            "success": True,
            "patient_id": str(patient_id),
            "template_id": str(template_id),
            "day": day,
            "preview": preview,
            "generated_at": now_sao_paulo().isoformat(),
        }
    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except Exception as e:
        logger.error(f"Failed to preview flow message: {e}")
        raise internal_server_exception("Failed to preview flow message")


@router.get(
    "/health/gemini",
    summary="Check Gemini health",
    description="Test Gemini AI integration health",
)
async def check_gemini_health(
    current_user: User = Depends(get_current_user),
    flow_engine: EnhancedFlowEngine = Depends(get_flow_engine),
):
    """Check Gemini AI integration health"""
    try:
        health_status = await flow_engine.health_check()
        gemini_status = health_status.get("gemini_client", False)
        return {
            "service": "gemini",
            "status": "healthy" if gemini_status else "unhealthy",
            "details": health_status,
            "checked_at": now_sao_paulo().isoformat(),
        }
    except Exception as e:
        logger.error(f"Gemini health check failed: {e}")
        return {
            "service": "gemini",
            "status": "unhealthy",
            "error": str(e),
            "checked_at": now_sao_paulo().isoformat(),
        }


@router.get(
    "/health/redis",
    summary="Check Redis health",
    description="Test Redis conversation memory health",
)
async def check_redis_health(
    current_user: User = Depends(get_current_user),
    flow_engine: EnhancedFlowEngine = Depends(get_flow_engine),
):
    """Check Redis health"""
    try:
        health_status = await flow_engine.health_check()
        redis_status = health_status.get(
            "template_cache", False
        )  # Using template cache as proxy for redis connectivity
        return {
            "service": "redis",
            "status": "healthy" if redis_status else "unhealthy",
            "details": health_status,
            "checked_at": now_sao_paulo().isoformat(),
        }
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            "service": "redis",
            "status": "unhealthy",
            "error": str(e),
            "checked_at": now_sao_paulo().isoformat(),
        }


@router.get(
    "/",
    response_model=List[FlowStateV2Response],
    summary="List all flows",
    description="Get paginated list of all flows with cursor pagination",
)
async def list_flows(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    pagination=Depends(get_pagination_params),
    include: Optional[List[str]] = Depends(get_eager_load_params),
):
    """List all flows for current user's patients"""
    try:
        cursor_data = pagination["cursor_data"]
        limit = pagination["limit"]

        # Build query
        from app.models.flow import FlowState as FlowStateModel

        query = db.query(FlowStateModel)

        # Apply eager loading
        if include:
            if "patient" in include:
                query = query.options(joinedload(FlowStateModel.patient))
            if "template" in include:
                query = query.options(joinedload(FlowStateModel.template))

        # Apply cursor
        if cursor_data and "id" in cursor_data:
            cursor_id = UUID(cursor_data["id"])
            cursor_created = datetime.fromisoformat(
                cursor_data["created_at"]
            )
            query = query.filter(
                (FlowStateModel.created_at < cursor_created)
                | (
                    (FlowStateModel.created_at == cursor_created)
                    & (FlowStateModel.id > cursor_id)
                )
            )

        # Order and limit
        query = query.order_by(FlowStateModel.created_at.desc(), FlowStateModel.id)
        flows = query.limit(limit + 1).all()

        # Check for more results
        has_more = len(flows) > limit
        if has_more:
            flows = flows[:limit]

        return [FlowStateV2Response.from_orm(f) for f in flows]

    except Exception as e:
        logger.error(f"Error listing flows for user {current_user.id}: {e}")
        raise internal_server_exception("Failed to list flows")


@router.post(
    "/start",
    response_model=FlowStateV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Start flow",
    description="Start a new flow for a patient",
)
async def start_flow(
    patient_id: UUID = Query(...),
    flow_type: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Start a new flow for a patient"""
    # Verify patient exists and user has access
    repo = PatientRepository(db)
    patient = repo.get_by_id(patient_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id} not found",
        )

    if patient.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to start flow for this patient",
        )

    try:
        flow_state = await flow_management.start_patient_flow(
            patient_id=patient_id, flow_type=flow_type
        )
        return FlowStateV2Response.from_orm(flow_state)
    except FlowOperationError as e:
        raise flow_operation_exception("start_flow", str(e))
    except Exception as e:
        logger.error(f"Error starting flow for patient {patient_id}: {e}")
        raise internal_server_exception("Failed to start flow")


@router.post(
    "/{patient_id}/response",
    response_model=FlowAdvanceV2Response,
    summary="Process patient response",
    description="Process patient's response and advance flow accordingly",
)
async def process_patient_response(
    patient_id: UUID,
    response_text: str = Query(...),
    response_metadata: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Process a patient's response"""
    # Verify patient exists and user has access
    repo = PatientRepository(db)
    patient = repo.get_by_id(patient_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id} not found",
        )

    if patient.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to process responses for this patient",
        )

    try:
        advancement = await flow_management.process_patient_response(
            patient_id=patient_id,
            response_text=response_text,
            response_metadata=response_metadata or {},
        )

        return FlowAdvanceV2Response(
            success=True,
            patient_id=str(patient_id),
            previous_step=advancement.get("previous_step", 0),
            current_step=advancement.get("current_step", 0),
            next_actions=advancement.get("next_actions", []),
            message=advancement.get("message", "Response processed successfully"),
        )
    except FlowOperationError as e:
        raise flow_operation_exception("process_response", str(e))
    except Exception as e:
        logger.error(f"Error processing response for patient {patient_id}: {e}")
        raise internal_server_exception("Failed to process patient response")


@router.get(
    "/analytics",
    summary="Get analytics summary",
    description="Get overall flow analytics with Redis caching",
)
@limiter.limit("30/minute")
async def get_analytics_summary(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    redis_cache=Depends(get_redis_cache),
):
    """Get comprehensive analytics summary with caching"""
    cache_key = f"flow:analytics:summary:{current_user.id}"

    async def compute():
        analytics_service = get_flow_analytics_service(db)
        analytics_data = await analytics_service.get_comprehensive_analytics(
            user_id=current_user.id
        )
        return analytics_data

    try:
        return await _get_cached_or_compute(
            cache_key, compute, redis_cache, CACHE_TTL_ANALYTICS
        )
    except Exception as e:
        logger.error(f"Error getting analytics summary for user {current_user.id}: {e}")
        raise internal_server_exception("Failed to get analytics summary")
