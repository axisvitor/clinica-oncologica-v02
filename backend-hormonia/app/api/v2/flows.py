"""
Flow management API v2
Enhanced flow endpoints with cursor pagination, field selection, and Redis caching.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func

from app.database import get_db
from app.models.user import User
from app.models.patient import Patient
from app.schemas.v2.flows import (
    # Templates
    FlowTemplateV2Response,
    FlowTemplateV2Create,
    FlowTemplateV2Update,
    FlowTemplateV2List,
    # Flow State
    FlowStateV2Response,
    FlowAdvanceV2Request,
    FlowAdvanceV2Response,
    FlowPauseV2Request,
    FlowPauseV2Response,
    FlowResumeV2Response,
    FlowHistoryV2Response,
    # Customization
    FlowCustomizationV2Request,
    FlowCustomizationV2Response,
    FlowCustomizationV2List,
    # Rules
    FlowRuleV2Create,
    FlowRuleV2Update,
    FlowRuleV2Response,
    FlowRuleV2List,
    # A/B Testing
    ABTestV2Create,
    ABTestV2Update,
    ABTestV2Response,
    ABTestV2List,
    ABTestResultsV2,
    # Analytics
    FlowMetricsV2Response,
    PatientEngagementV2Response,
    RiskAssessmentV2Response,
    FlowPerformanceV2Response,
    PatientJourneyV2Response,
    FlowInsightsV2Response,
)
from app.schemas.v2.common import ErrorResponse
from .dependencies import (
    get_pagination_params,
    get_field_selection,
    get_eager_load_params,
    apply_field_selection,
)
from app.dependencies import (
    get_current_user,
    validate_patient_access,
    get_flow_management_service,
    get_patient_service,
    get_flow_service,
)
from app.dependencies.service_dependencies import get_flow_analytics_service
from app.dependencies.auth_dependencies import get_redis_cache
from app.services.flow_management import FlowManagementService
from app.services.flow_analytics import FlowAnalyticsService
from app.services.flow_engine import FlowEngineIntegrationService
from app.services.patient import PatientService
from app.services.flow_dashboard import FlowDashboardService, DashboardTimeframe, get_flow_dashboard_service
from app.exceptions import (
    FlowStateNotFoundError,
    FlowOperationError,
    FlowStateConflictError,
    flow_not_found_exception,
    flow_operation_exception,
    internal_server_exception,
)
from app.utils.rate_limiter import limiter
import base64
import json

router = APIRouter()
logger = logging.getLogger(__name__)

# Redis cache TTL constants (in seconds)
CACHE_TTL_DASHBOARD = 900  # 15 minutes
CACHE_TTL_ANALYTICS = 900  # 15 minutes
CACHE_TTL_RISK = 600      # 10 minutes


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


async def _get_cached_or_compute(
    cache_key: str,
    compute_fn,
    redis_cache,
    ttl: int = CACHE_TTL_ANALYTICS
) -> Any:
    """Get from cache or compute and cache result"""
    # Try to get from cache
    cached = await redis_cache.get(cache_key)
    if cached is not None:
        return cached

    # Compute and cache
    result = await compute_fn()
    await redis_cache.set(cache_key, result, ttl=ttl)
    return result


# ============================================================================
# A. Flow State Operations (5 endpoints)
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
    patient: Patient = Depends(validate_patient_access),
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
    include: Optional[List[str]] = Depends(get_eager_load_params),
):
    """
    Get patient's current flow state.

    Supports eager loading:
    - ?include=patient,template
    """
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
    patient = await validate_patient_access(patient_id, current_user, patient_service)

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
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Pause patient flow with optional auto-resume"""
    # Validate patient access
    patient = await validate_patient_access(patient_id, current_user, patient_service)

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
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Resume a previously paused flow"""
    # Validate patient access
    patient = await validate_patient_access(patient_id, current_user, patient_service)

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
    patient_service: PatientService = Depends(get_patient_service),
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
    patient = await validate_patient_access(patient_id, current_user, patient_service)

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


# ============================================================================
# B. Analytics & Dashboard (7 endpoints)
# ============================================================================

@router.get(
    "/dashboard/overview",
    summary="Get dashboard overview",
    description="Get comprehensive dashboard with Redis caching (15min TTL)"
)
@limiter.limit("30/minute")
async def get_dashboard_overview(
    timeframe: DashboardTimeframe = Query(DashboardTimeframe.LAST_7_DAYS),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
):
    """Get flow dashboard overview with caching"""
    cache_key = f"flow:dashboard:overview:{timeframe.value}:{current_user.id}"

    async def compute():
        dashboard_service = get_flow_dashboard_service(db)
        overview_data = await dashboard_service.get_dashboard_overview(timeframe)
        return {
            "success": True,
            "timeframe": timeframe.value,
            "data": overview_data,
            "generated_at": datetime.utcnow().isoformat()
        }

    try:
        return await _get_cached_or_compute(cache_key, compute, redis_cache, CACHE_TTL_DASHBOARD)
    except Exception as e:
        logger.error(f"Failed to get dashboard overview: {e}")
        raise internal_server_exception("Failed to get dashboard overview")


@router.get(
    "/dashboard/flow-metrics",
    summary="Get flow metrics",
    description="Get detailed flow performance metrics with Redis caching"
)
@limiter.limit("30/minute")
async def get_flow_metrics(
    flow_type: Optional[str] = Query(None),
    timeframe: DashboardTimeframe = Query(DashboardTimeframe.LAST_30_DAYS),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
):
    """Get flow metrics with caching"""
    cache_key = f"flow:metrics:{flow_type or 'all'}:{timeframe.value}:{current_user.id}"

    async def compute():
        dashboard_service = get_flow_dashboard_service(db)
        metrics_data = await dashboard_service.get_flow_metrics(
            flow_type=flow_type,
            timeframe=timeframe
        )
        return {
            "success": True,
            "flow_type": flow_type,
            "timeframe": timeframe.value,
            "metrics": metrics_data,
            "generated_at": datetime.utcnow().isoformat()
        }

    try:
        return await _get_cached_or_compute(cache_key, compute, redis_cache, CACHE_TTL_DASHBOARD)
    except Exception as e:
        logger.error(f"Failed to get flow metrics: {e}")
        raise internal_server_exception("Failed to get flow metrics")


@router.get(
    "/dashboard/patient-engagement",
    summary="Get patient engagement metrics",
    description="Get engagement analytics with Redis caching"
)
@limiter.limit("30/minute")
async def get_patient_engagement_metrics(
    timeframe: DashboardTimeframe = Query(DashboardTimeframe.LAST_30_DAYS),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
):
    """Get patient engagement metrics with caching"""
    cache_key = f"flow:engagement:{timeframe.value}:{current_user.id}"

    async def compute():
        dashboard_service = get_flow_dashboard_service(db)
        engagement_data = await dashboard_service.get_patient_engagement_metrics(timeframe)
        return {
            "success": True,
            "timeframe": timeframe.value,
            "engagement_metrics": engagement_data,
            "generated_at": datetime.utcnow().isoformat()
        }

    try:
        return await _get_cached_or_compute(cache_key, compute, redis_cache, CACHE_TTL_DASHBOARD)
    except Exception as e:
        logger.error(f"Failed to get engagement metrics: {e}")
        raise internal_server_exception("Failed to get patient engagement metrics")


@router.get(
    "/analytics/risk-assessment",
    summary="Get risk assessment",
    description="Get patient risk analysis with Redis caching (10min TTL)"
)
@limiter.limit("20/minute")
async def get_risk_assessment(
    risk_level: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
):
    """Get patient risk assessment with caching"""
    cache_key = f"flow:risk:{risk_level or 'all'}:{limit}:{current_user.id}"

    async def compute():
        analytics_service = get_flow_analytics_service(db)
        risk_data = await analytics_service.analyze_patient_risk(
            risk_level=risk_level,
            limit=limit
        )
        return {
            "success": True,
            "risk_level_filter": risk_level or "all",
            "risk_assessments": risk_data,
            "total_patients": len(risk_data),
            "generated_at": datetime.utcnow().isoformat()
        }

    try:
        return await _get_cached_or_compute(cache_key, compute, redis_cache, CACHE_TTL_RISK)
    except Exception as e:
        logger.error(f"Failed to get risk assessment: {e}")
        raise internal_server_exception("Failed to get risk assessment")


@router.get(
    "/analytics/flow-performance",
    summary="Get flow performance analytics",
    description="Get comprehensive performance metrics with Redis caching"
)
@limiter.limit("30/minute")
async def get_flow_performance_analytics(
    flow_type: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
):
    """Get flow performance analytics with caching"""
    start_str = start_date.isoformat() if start_date else "none"
    end_str = end_date.isoformat() if end_date else "none"
    cache_key = f"flow:performance:{flow_type or 'all'}:{start_str}:{end_str}:{current_user.id}"

    async def compute():
        analytics_service = get_flow_analytics_service(db)
        analytics_data = await analytics_service.get_flow_performance_analytics(
            flow_type=flow_type,
            start_date=start_date,
            end_date=end_date
        )
        return analytics_data

    try:
        return await _get_cached_or_compute(cache_key, compute, redis_cache, CACHE_TTL_ANALYTICS)
    except Exception as e:
        logger.error(f"Failed to get flow performance analytics: {e}")
        raise internal_server_exception("Failed to get flow performance analytics")


@router.get(
    "/analytics/patient-journey",
    summary="Get patient journey analytics",
    description="Get patient journey insights"
)
async def get_patient_journey_analytics(
    patient_id: Optional[UUID] = Query(None),
    flow_type: Optional[str] = Query(None),
    timeframe: DashboardTimeframe = Query(DashboardTimeframe.LAST_30_DAYS),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get patient journey analytics"""
    try:
        analytics_service = get_flow_analytics_service(db)
        journey_data = await analytics_service.analyze_patient_journeys(
            patient_id=patient_id,
            flow_type=flow_type,
            timeframe=timeframe
        )
        return {
            "success": True,
            "patient_id": str(patient_id) if patient_id else None,
            "flow_type": flow_type,
            "timeframe": timeframe.value,
            "journey_analytics": journey_data,
            "generated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get patient journey analytics: {e}")
        raise internal_server_exception("Failed to get patient journey analytics")


@router.post(
    "/analytics/generate-insights",
    summary="Generate AI insights",
    description="Generate AI-powered insights from flow analytics"
)
@limiter.limit("10/minute")
async def generate_flow_insights(
    flow_type: Optional[str] = Query(None),
    analysis_depth: str = Query("standard", regex="^(basic|standard|detailed)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate AI-powered insights"""
    try:
        analytics_service = get_flow_analytics_service(db)
        insights = await analytics_service.generate_ai_insights(
            flow_type=flow_type,
            analysis_depth=analysis_depth
        )
        return {
            "success": True,
            "flow_type": flow_type,
            "analysis_depth": analysis_depth,
            "insights": insights,
            "generated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to generate flow insights: {e}")
        raise internal_server_exception("Failed to generate flow insights")


# ============================================================================
# C. Template Management (5 endpoints)
# ============================================================================

@router.get(
    "/templates",
    response_model=FlowTemplateV2List,
    summary="List flow templates",
    description="Get paginated list of flow templates with cursor pagination"
)
async def get_flow_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    pagination = Depends(get_pagination_params),
    flow_type: Optional[str] = Query(None),
    active_only: bool = Query(True),
    include: Optional[List[str]] = Depends(get_eager_load_params),
):
    """
    List flow templates with cursor pagination.

    Supports:
    - Cursor pagination
    - Filter by flow_type
    - Filter by active status
    """
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    # Build query
    from app.models.flow import FlowTemplate
    query = db.query(FlowTemplate)

    # Apply filters
    filters = []
    if active_only:
        filters.append(FlowTemplate.is_active == True)
    if flow_type:
        filters.append(FlowTemplate.flow_type == flow_type)

    # Apply cursor
    if cursor_data and "id" in cursor_data:
        cursor_id = UUID(cursor_data["id"])
        cursor_created = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))
        filters.append(
            (FlowTemplate.created_at < cursor_created) |
            ((FlowTemplate.created_at == cursor_created) & (FlowTemplate.id > cursor_id))
        )

    if filters:
        query = query.filter(and_(*filters))

    # Get total (only on first page)
    total = None
    if not cursor_data:
        total = query.count()

    # Order and limit
    query = query.order_by(FlowTemplate.created_at.desc(), FlowTemplate.id)
    templates = query.limit(limit + 1).all()

    # Check for more results
    has_more = len(templates) > limit
    if has_more:
        templates = templates[:limit]

    # Create next cursor
    next_cursor = None
    if has_more and templates:
        next_cursor = _create_cursor(templates[-1].id, templates[-1].created_at)

    return FlowTemplateV2List(
        data=[FlowTemplateV2Response.from_orm(t) for t in templates],
        next_cursor=next_cursor,
        has_more=has_more,
        total=total
    )


@router.post(
    "/templates",
    response_model=FlowTemplateV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Create flow template",
    description="Create a new flow template"
)
@limiter.limit("10/hour")
async def create_flow_template(
    template_data: FlowTemplateV2Create,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Create new flow template"""
    try:
        template = await flow_management.create_flow_template(
            template_data=template_data,
            created_by=current_user.id
        )
        return FlowTemplateV2Response.from_orm(template)
    except Exception as e:
        logger.error(f"Failed to create flow template: {e}")
        raise flow_operation_exception("create_template", str(e))


@router.get(
    "/templates/{template_id}",
    response_model=FlowTemplateV2Response,
    summary="Get flow template",
    description="Get specific flow template by ID"
)
async def get_flow_template(
    template_id: UUID,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Get specific flow template"""
    try:
        template = await flow_management.get_flow_template(template_id)
        return FlowTemplateV2Response.from_orm(template)
    except FlowStateNotFoundError:
        raise flow_not_found_exception(f"template_{template_id}")
    except Exception as e:
        logger.error(f"Failed to get flow template {template_id}: {e}")
        raise internal_server_exception("Failed to get flow template")


@router.put(
    "/templates/{template_id}",
    response_model=FlowTemplateV2Response,
    summary="Update flow template",
    description="Update existing flow template"
)
@limiter.limit("20/hour")
async def update_flow_template(
    template_id: UUID,
    template_data: FlowTemplateV2Update,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Update flow template"""
    try:
        template = await flow_management.update_flow_template(
            template_id=template_id,
            template_data=template_data,
            updated_by=current_user.id
        )
        return FlowTemplateV2Response.from_orm(template)
    except FlowStateNotFoundError:
        raise flow_not_found_exception(f"template_{template_id}")
    except Exception as e:
        logger.error(f"Failed to update flow template {template_id}: {e}")
        raise flow_operation_exception("update_template", str(e))


@router.delete(
    "/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete flow template",
    description="Soft delete a flow template"
)
@limiter.limit("10/hour")
async def delete_flow_template(
    template_id: UUID,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Soft delete flow template"""
    try:
        await flow_management.delete_flow_template(
            template_id=template_id,
            deleted_by=current_user.id
        )
        return None
    except FlowStateNotFoundError:
        raise flow_not_found_exception(f"template_{template_id}")
    except Exception as e:
        logger.error(f"Failed to delete flow template {template_id}: {e}")
        raise internal_server_exception("Failed to delete flow template")


# ============================================================================
# D. Customization (4 endpoints)
# ============================================================================

@router.post(
    "/{patient_id}/customize",
    response_model=FlowCustomizationV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Customize patient flow",
    description="Create patient-specific flow customization"
)
async def customize_patient_flow(
    patient_id: UUID,
    customization_data: FlowCustomizationV2Request,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Create patient-specific flow customization"""
    # Validate patient access
    patient = await validate_patient_access(patient_id, current_user, patient_service)

    try:
        customization = await flow_management.customize_patient_flow(
            patient_id=patient_id,
            customization_data=customization_data,
            customized_by=current_user.id
        )
        return FlowCustomizationV2Response.from_orm(customization)
    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except Exception as e:
        logger.error(f"Failed to customize flow for patient {patient_id}: {e}")
        raise flow_operation_exception("customize_flow", str(e))


@router.get(
    "/{patient_id}/customization",
    response_model=FlowCustomizationV2Response,
    summary="Get flow customization",
    description="Get patient's flow customization settings"
)
async def get_patient_flow_customization(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Get patient flow customization"""
    # Validate patient access
    patient = await validate_patient_access(patient_id, current_user, patient_service)

    try:
        customization = await flow_management.get_patient_flow_customization(patient_id)
        return FlowCustomizationV2Response.from_orm(customization)
    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except Exception as e:
        logger.error(f"Failed to get flow customization for patient {patient_id}: {e}")
        raise internal_server_exception("Failed to get flow customization")


@router.put(
    "/{patient_id}/customization",
    response_model=FlowCustomizationV2Response,
    summary="Update flow customization",
    description="Update patient's flow customization"
)
async def update_patient_flow_customization(
    patient_id: UUID,
    customization_data: FlowCustomizationV2Request,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Update patient flow customization"""
    # Validate patient access
    patient = await validate_patient_access(patient_id, current_user, patient_service)

    try:
        customization = await flow_management.update_patient_flow_customization(
            patient_id=patient_id,
            customization_data=customization_data,
            updated_by=current_user.id
        )
        return FlowCustomizationV2Response.from_orm(customization)
    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except Exception as e:
        logger.error(f"Failed to update flow customization for patient {patient_id}: {e}")
        raise flow_operation_exception("update_customization", str(e))


@router.delete(
    "/{patient_id}/customization",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove flow customization",
    description="Remove patient's flow customization"
)
async def remove_patient_flow_customization(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Remove patient flow customization"""
    # Validate patient access
    patient = await validate_patient_access(patient_id, current_user, patient_service)

    try:
        await flow_management.remove_patient_flow_customization(
            patient_id=patient_id,
            removed_by=current_user.id
        )
        return None
    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except Exception as e:
        logger.error(f"Failed to remove flow customization for patient {patient_id}: {e}")
        raise internal_server_exception("Failed to remove flow customization")


# ============================================================================
# E. Rules Engine (4 endpoints)
# ============================================================================

@router.post(
    "/rules",
    response_model=FlowRuleV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Create flow rule",
    description="Create conditional flow rule"
)
@limiter.limit("10/hour")
async def create_flow_rule(
    rule_data: FlowRuleV2Create,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Create flow rule for conditional logic"""
    try:
        rule = await flow_management.create_flow_rule(
            rule_data=rule_data,
            created_by=current_user.id
        )
        return FlowRuleV2Response.from_orm(rule)
    except Exception as e:
        logger.error(f"Failed to create flow rule: {e}")
        raise flow_operation_exception("create_rule", str(e))


@router.get(
    "/rules",
    response_model=FlowRuleV2List,
    summary="List flow rules",
    description="Get paginated list of flow rules"
)
async def get_flow_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    pagination = Depends(get_pagination_params),
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
        filters.append(FlowRule.is_active == True)
    if flow_type:
        filters.append(FlowRule.flow_type == flow_type)

    # Apply cursor
    if cursor_data and "id" in cursor_data:
        cursor_id = UUID(cursor_data["id"])
        cursor_created = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))
        filters.append(
            (FlowRule.created_at < cursor_created) |
            ((FlowRule.created_at == cursor_created) & (FlowRule.id > cursor_id))
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
        total=total
    )


@router.put(
    "/rules/{rule_id}",
    response_model=FlowRuleV2Response,
    summary="Update flow rule",
    description="Update existing flow rule"
)
@limiter.limit("20/hour")
async def update_flow_rule(
    rule_id: UUID,
    rule_data: FlowRuleV2Update,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Update flow rule"""
    try:
        rule = await flow_management.update_flow_rule(
            rule_id=rule_id,
            rule_data=rule_data,
            updated_by=current_user.id
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
    description="Delete a flow rule"
)
@limiter.limit("10/hour")
async def delete_flow_rule(
    rule_id: UUID,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Delete flow rule"""
    try:
        await flow_management.delete_flow_rule(
            rule_id=rule_id,
            deleted_by=current_user.id
        )
        return None
    except FlowStateNotFoundError:
        raise flow_not_found_exception(f"rule_{rule_id}")
    except Exception as e:
        logger.error(f"Failed to delete flow rule {rule_id}: {e}")
        raise internal_server_exception("Failed to delete flow rule")


# ============================================================================
# F. A/B Testing (6 endpoints)
# ============================================================================

@router.post(
    "/ab-tests",
    response_model=ABTestV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Create A/B test",
    description="Create new A/B test configuration"
)
@limiter.limit("5/hour")
async def create_ab_test(
    test_config: ABTestV2Create,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Create A/B test configuration"""
    try:
        ab_test = await flow_management.create_ab_test(
            test_config=test_config,
            created_by=current_user.id
        )
        return ABTestV2Response.from_orm(ab_test)
    except Exception as e:
        logger.error(f"Failed to create A/B test: {e}")
        raise flow_operation_exception("create_ab_test", str(e))


@router.get(
    "/ab-tests",
    response_model=ABTestV2List,
    summary="List A/B tests",
    description="Get paginated list of A/B tests"
)
async def get_ab_tests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    pagination = Depends(get_pagination_params),
    active_only: bool = Query(True),
):
    """List A/B tests with cursor pagination"""
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    # Build query
    from app.models.flow import ABTest
    query = db.query(ABTest)

    # Apply filters
    filters = []
    if active_only:
        from app.schemas.v2.flows import ABTestStatusV2
        filters.append(ABTest.status == ABTestStatusV2.ACTIVE)

    # Apply cursor
    if cursor_data and "id" in cursor_data:
        cursor_id = UUID(cursor_data["id"])
        cursor_created = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))
        filters.append(
            (ABTest.created_at < cursor_created) |
            ((ABTest.created_at == cursor_created) & (ABTest.id > cursor_id))
        )

    if filters:
        query = query.filter(and_(*filters))

    # Get total (only on first page)
    total = None
    if not cursor_data:
        total = query.count()

    # Order and limit
    query = query.order_by(ABTest.created_at.desc(), ABTest.id)
    tests = query.limit(limit + 1).all()

    # Check for more results
    has_more = len(tests) > limit
    if has_more:
        tests = tests[:limit]

    # Create next cursor
    next_cursor = None
    if has_more and tests:
        next_cursor = _create_cursor(tests[-1].id, tests[-1].created_at)

    return ABTestV2List(
        data=[ABTestV2Response.from_orm(t) for t in tests],
        next_cursor=next_cursor,
        has_more=has_more,
        total=total
    )


@router.get(
    "/ab-tests/{test_id}",
    response_model=ABTestV2Response,
    summary="Get A/B test",
    description="Get specific A/B test details"
)
async def get_ab_test(
    test_id: UUID,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Get specific A/B test"""
    try:
        ab_test = await flow_management.get_ab_test(test_id)
        return ABTestV2Response.from_orm(ab_test)
    except FlowStateNotFoundError:
        raise flow_not_found_exception(f"ab_test_{test_id}")
    except Exception as e:
        logger.error(f"Failed to get A/B test {test_id}: {e}")
        raise internal_server_exception("Failed to get A/B test")


@router.put(
    "/ab-tests/{test_id}",
    response_model=ABTestV2Response,
    summary="Update A/B test",
    description="Update A/B test configuration"
)
@limiter.limit("10/hour")
async def update_ab_test(
    test_id: UUID,
    test_config: ABTestV2Update,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Update A/B test"""
    try:
        ab_test = await flow_management.update_ab_test(
            test_id=test_id,
            test_config=test_config,
            updated_by=current_user.id
        )
        return ABTestV2Response.from_orm(ab_test)
    except FlowStateNotFoundError:
        raise flow_not_found_exception(f"ab_test_{test_id}")
    except Exception as e:
        logger.error(f"Failed to update A/B test {test_id}: {e}")
        raise flow_operation_exception("update_ab_test", str(e))


@router.post(
    "/ab-tests/{test_id}/stop",
    summary="Stop A/B test",
    description="Stop an active A/B test"
)
@limiter.limit("10/hour")
async def stop_ab_test(
    test_id: UUID,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Stop A/B test"""
    try:
        results = await flow_management.stop_ab_test(
            test_id=test_id,
            stopped_by=current_user.id
        )
        return {
            "success": True,
            "message": "A/B test stopped successfully",
            "final_results": results
        }
    except FlowStateNotFoundError:
        raise flow_not_found_exception(f"ab_test_{test_id}")
    except Exception as e:
        logger.error(f"Failed to stop A/B test {test_id}: {e}")
        raise internal_server_exception("Failed to stop A/B test")


@router.get(
    "/ab-tests/{test_id}/results",
    summary="Get A/B test results",
    description="Get comprehensive A/B test results and analytics"
)
async def get_ab_test_results(
    test_id: UUID,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Get A/B test results"""
    try:
        results = await flow_management.get_ab_test_results(test_id)
        return {
            "success": True,
            "test_id": str(test_id),
            "results": results,
            "generated_at": datetime.utcnow().isoformat()
        }
    except FlowStateNotFoundError:
        raise flow_not_found_exception(f"ab_test_{test_id}")
    except Exception as e:
        logger.error(f"Failed to get A/B test results {test_id}: {e}")
        raise internal_server_exception("Failed to get A/B test results")


# ============================================================================
# G. Utility (7 endpoints)
# ============================================================================

@router.post(
    "/preview-message",
    summary="Preview flow message",
    description="Preview AI-powered flow message without sending"
)
async def preview_flow_message(
    patient_id: UUID,
    template_id: UUID,
    day: int = Query(1, ge=1),
    current_user: User = Depends(get_current_user),
    flow_service: FlowEngineIntegrationService = Depends(get_flow_service),
):
    """Preview flow message for healthcare providers"""
    try:
        preview = await flow_service.preview_flow_message(
            patient_id=patient_id,
            template_id=template_id,
            day=day
        )
        return {
            "success": True,
            "patient_id": str(patient_id),
            "template_id": str(template_id),
            "day": day,
            "preview": preview,
            "generated_at": datetime.utcnow().isoformat()
        }
    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except Exception as e:
        logger.error(f"Failed to preview flow message: {e}")
        raise internal_server_exception("Failed to preview flow message")


@router.get(
    "/health/gemini",
    summary="Check Gemini health",
    description="Test Gemini AI integration health"
)
async def check_gemini_health(
    current_user: User = Depends(get_current_user),
    flow_service: FlowEngineIntegrationService = Depends(get_flow_service),
):
    """Check Gemini AI integration health"""
    try:
        health_status = await flow_service.check_gemini_health()
        return {
            "service": "gemini",
            "status": "healthy" if health_status else "unhealthy",
            "details": health_status,
            "checked_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Gemini health check failed: {e}")
        return {
            "service": "gemini",
            "status": "unhealthy",
            "error": str(e),
            "checked_at": datetime.utcnow().isoformat()
        }


@router.get(
    "/health/redis",
    summary="Check Redis health",
    description="Test Redis conversation memory health"
)
async def check_redis_health(
    current_user: User = Depends(get_current_user),
    flow_service: FlowEngineIntegrationService = Depends(get_flow_service),
):
    """Check Redis health"""
    try:
        health_status = await flow_service.check_redis_health()
        return {
            "service": "redis",
            "status": "healthy" if health_status else "unhealthy",
            "details": health_status,
            "checked_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            "service": "redis",
            "status": "unhealthy",
            "error": str(e),
            "checked_at": datetime.utcnow().isoformat()
        }


@router.get(
    "",
    response_model=List[FlowStateV2Response],
    summary="List all flows",
    description="Get paginated list of all flows with cursor pagination"
)
async def list_flows(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    pagination = Depends(get_pagination_params),
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
            cursor_created = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))
            query = query.filter(
                (FlowStateModel.created_at < cursor_created) |
                ((FlowStateModel.created_at == cursor_created) & (FlowStateModel.id > cursor_id))
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
    description="Start a new flow for a patient"
)
async def start_flow(
    patient_id: UUID = Query(...),
    flow_type: str = Query(...),
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Start a new flow for a patient"""
    # Verify patient exists and user has access
    patient = patient_service.get_patient(patient_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id} not found"
        )

    if patient.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to start flow for this patient"
        )

    try:
        flow_state = await flow_management.start_patient_flow(
            patient_id=patient_id,
            flow_type=flow_type
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
    description="Process patient's response and advance flow accordingly"
)
async def process_patient_response(
    patient_id: UUID,
    response_text: str = Query(...),
    response_metadata: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Process a patient's response"""
    # Verify patient exists and user has access
    patient = patient_service.get_patient(patient_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id} not found"
        )

    if patient.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to process responses for this patient"
        )

    try:
        advancement = await flow_management.process_patient_response(
            patient_id=patient_id,
            response_text=response_text,
            response_metadata=response_metadata or {}
        )

        return FlowAdvanceV2Response(
            success=True,
            patient_id=str(patient_id),
            previous_step=advancement.get("previous_step", 0),
            current_step=advancement.get("current_step", 0),
            next_actions=advancement.get("next_actions", []),
            message=advancement.get("message", "Response processed successfully")
        )
    except FlowOperationError as e:
        raise flow_operation_exception("process_response", str(e))
    except Exception as e:
        logger.error(f"Error processing response for patient {patient_id}: {e}")
        raise internal_server_exception("Failed to process patient response")


@router.get(
    "/analytics",
    summary="Get analytics summary",
    description="Get overall flow analytics with Redis caching"
)
@limiter.limit("30/minute")
async def get_analytics_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
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
        return await _get_cached_or_compute(cache_key, compute, redis_cache, CACHE_TTL_ANALYTICS)
    except Exception as e:
        logger.error(f"Error getting analytics summary for user {current_user.id}: {e}")
        raise internal_server_exception("Failed to get analytics summary")
