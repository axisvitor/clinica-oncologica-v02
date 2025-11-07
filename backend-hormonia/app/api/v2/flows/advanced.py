"""
Flow Advanced Features
Handles rules engine, A/B testing, and utility operations
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException, status
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
    ABTestV2Create,
    ABTestV2Update,
    ABTestV2Response,
    ABTestV2List,
)
from ..dependencies import (
    get_pagination_params,
    get_eager_load_params,
)
from app.dependencies import (
    get_current_user,
    get_flow_management_service,
    get_patient_service,
    get_flow_service,
)
from app.dependencies.service_dependencies import get_flow_analytics_service
from app.dependencies.auth_dependencies import get_redis_cache
from app.services.flow_management import FlowManagementService
from app.services.flow_engine import FlowEngineIntegrationService
from app.services.patient import PatientService
from app.exceptions import (
    FlowStateNotFoundError,
    FlowOperationError,
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
CACHE_TTL_ANALYTICS = 900  # 15 minutes


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
# Rules Engine (4 endpoints)
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
# A/B Testing (6 endpoints)
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
# Utility Operations (7 endpoints)
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
