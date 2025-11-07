"""
Flow Analytics & Dashboard
Handles analytics dashboards, metrics, engagement, risk assessment, and AI insights
"""

import logging
from typing import Optional, Any
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.dependencies import get_current_user
from app.dependencies.service_dependencies import get_flow_analytics_service
from app.dependencies.auth_dependencies import get_redis_cache
from app.services.flow_analytics import FlowAnalyticsService
from app.services.flow_dashboard import FlowDashboardService, DashboardTimeframe, get_flow_dashboard_service
from app.exceptions import internal_server_exception
from app.utils.rate_limiter import limiter

router = APIRouter()
logger = logging.getLogger(__name__)

# Redis cache TTL constants (in seconds)
CACHE_TTL_DASHBOARD = 900  # 15 minutes
CACHE_TTL_ANALYTICS = 900  # 15 minutes
CACHE_TTL_RISK = 600      # 10 minutes


# ============================================================================
# Helper Functions
# ============================================================================

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
# Analytics & Dashboard (7 endpoints)
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
