"""
Analytics API endpoints.
Provides analytics data, dashboard metrics, and pattern detection.
"""
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional, Any
from uuid import UUID
from functools import wraps

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.database import get_db
from app.dependencies import get_current_user, verify_patient_access
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.models.message import Message, MessageDirection
from app.services.analytics import AnalyticsService, AnalyticsError
from app.models.analytics_models import TreatmentDistributionResponse
from app.schemas.report import (
    AnalyticsRequest,
    AnalyticsResponse,
    DashboardResponse
)
from app.schemas.common import ErrorResponse
from app.core.redis_unified import get_sync_redis
from app.core.date_utils import coerce_to_date, validate_date_range, set_default_date_range
from app.core.error_handler import error_handler
from app.core.monitoring_logging import monitoring_logger, monitoring_decorator
from app.services.analytics_cache import get_analytics_cache, cache_analytics_data
import json


logger = logging.getLogger(__name__)
router = APIRouter(tags=["analytics"])  # Prefix removed - set in router_registry.py

# Constants
DEFAULT_WEEKS_BACK = 4
DEFAULT_DAYS_BACK = 30
MAX_DAYS_BACK = 365
DAYS_PER_WEEK = 7


def handle_analytics_errors(operation_name: str):
    """Decorator to handle common analytics errors with integrated error handling."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                with monitoring_logger.context(operation=operation_name, endpoint=func.__name__):
                    return await func(*args, **kwargs)
            except AttributeError as e:
                # Handle role enum errors
                if "UserRole" in str(e) or "role" in str(e).lower():
                    await error_handler.handle_role_enum_error(
                        e, 
                        user_role=getattr(kwargs.get('current_user'), 'role', None),
                        endpoint=f"analytics.{func.__name__}"
                    )
                # Handle dependency injection errors
                elif "generator" in str(e) or "service" in str(e):
                    await error_handler.handle_dependency_injection_error(
                        e,
                        {
                            "operation": operation_name,
                            "endpoint": f"analytics.{func.__name__}",
                            "args": str(args)[:100]
                        }
                    )
                else:
                    await error_handler.handle_generic_error(
                        e,
                        error_type="ANALYTICS_ATTRIBUTE_ERROR",
                        context={"operation": operation_name, "endpoint": func.__name__}
                    )
            except ValueError as e:
                # Handle date parameter validation errors
                if "date" in str(e).lower():
                    await error_handler.handle_validation_error(
                        e,
                        field_name="date_parameter",
                        context={"operation": operation_name}
                    )
                else:
                    await error_handler.handle_validation_error(e, context={"operation": operation_name})
            except AnalyticsError as e:
                logger.error(f"{operation_name} failed: {e}")
                monitoring_logger.log_system_event(
                    event_type="analytics_service_error",
                    message=f"Analytics service error in {operation_name}: {e}",
                    level="ERROR",
                    context={"operation": operation_name, "error": str(e)}
                )
                raise HTTPException(status_code=500, detail=str(e))
            except HTTPException:
                raise
            except Exception as e:
                await error_handler.handle_generic_error(
                    e,
                    error_type="ANALYTICS_UNEXPECTED_ERROR",
                    context={"operation": operation_name, "endpoint": func.__name__},
                    user_message=f"Analytics operation '{operation_name}' failed. Please try again."
                )
        return wrapper
    return decorator


# verify_patient_access function removed - using dependency from app.dependencies instead


def build_engagement_response(patient_data, patterns: dict[str, Any], patient_id: UUID, days_back: int) -> dict[str, Any]:
    """Build engagement details response structure."""
    return {
        "patient_id": str(patient_id),
        "patient_name": patient_data.patient_name,
        "period_days": days_back,
        "engagement_metrics": {
            "total_messages_sent": patient_data.total_messages_sent,
            "total_messages_received": patient_data.total_messages_received,
            "response_rate": patient_data.response_rate,
            "avg_response_time_hours": patient_data.avg_response_time_hours,
            "quizzes_completed": patient_data.quizzes_completed,
            "quiz_completion_rate": patient_data.quiz_completion_rate
        },
        "trends": {
            "engagement_trend": patient_data.engagement_trend,
            "symptom_trend": patient_data.symptom_trend
        },
        "patterns": patterns.get("engagement_trends", {}),
        "anomalies": patterns.get("anomalies", [])
    }


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Get dashboard data",
    description="Get real-time dashboard data with quick stats and charts"
)
@handle_analytics_errors("dashboard data retrieval")
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> DashboardResponse:
    """Get dashboard data with real-time updates."""
    analytics_service = AnalyticsService(db)
    cache_service = get_analytics_cache()

    # Filter by doctor if user is not admin
    doctor_id = None if current_user.role == UserRole.ADMIN else current_user.id

    # Build cache key parameters
    cache_key_params = {
        "doctor_id": str(doctor_id) if doctor_id else "all",
        "endpoint": "dashboard"
    }

    # Try to get from cache first
    def generate_dashboard_data():
        return analytics_service.get_dashboard_data(doctor_id)

    dashboard_data = cache_service.get_or_set(
        "dashboard", 
        cache_key_params, 
        generate_dashboard_data
    )

    logger.info(f"Dashboard data retrieved for user {current_user.id}")
    return DashboardResponse(**dashboard_data) if isinstance(dashboard_data, dict) else dashboard_data


@router.get(
    "/treatment-distribution",
    response_model=TreatmentDistributionResponse,
    summary="Get treatment type distribution",
    description="Returns distribution of patients across different treatment types with counts, percentages, and chart colors"
)
@handle_analytics_errors("treatment distribution retrieval")
async def get_treatment_distribution(
    period: str = Query("30d", regex="^(7d|30d|90d|all)$", description="Time period for analysis"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> TreatmentDistributionResponse:
    """
    Get treatment type distribution for analytics charts.

    Returns chart-ready data with counts, percentages, and colors for visualization.
    Supports filtering by time period and automatically filters by doctor role.

    Cache: 5 minutes (Redis)
    """
    analytics_service = AnalyticsService(db)

    # Filter by doctor if user is not admin
    doctor_id = None if current_user.role == UserRole.ADMIN else current_user.id

    # Use analytics cache service
    cache_service = get_analytics_cache()
    cache_key_params = {
        "period": period,
        "doctor_id": str(doctor_id) if doctor_id else "all"
    }

    # Try to get from cache first
    def generate_treatment_distribution():
        result = analytics_service.get_treatment_distribution(period, doctor_id)
        return result

    result = cache_service.get_or_set(
        "treatment_distribution",
        cache_key_params,
        generate_treatment_distribution
    )

    # Create response
    response = TreatmentDistributionResponse(**result)

    logger.info(f"Treatment distribution retrieved for user {current_user.id}, period: {period}")
    return response


@router.post(
    "/",
    response_model=AnalyticsResponse,
    summary="Get analytics data",
    description="Get comprehensive analytics data for patients and system metrics"
)
@handle_analytics_errors("analytics data retrieval")
async def get_analytics(
    request: AnalyticsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> AnalyticsResponse:
    """Get comprehensive analytics data."""
    analytics_service = AnalyticsService(db)

    # Filter by doctor if user is not admin
    if current_user.role != UserRole.ADMIN and not request.doctor_id:
        request.doctor_id = current_user.id
    elif current_user.role != UserRole.ADMIN and request.doctor_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Cannot access other doctor's analytics"
        )

    analytics_data = analytics_service.get_analytics(request)

    logger.info(f"Analytics data retrieved for user {current_user.id}")
    return analytics_data


@router.get(
    "/patterns",
    response_model=None,
    summary="Detect patterns",
    description="Detect patterns and anomalies in patient data using trend analysis"
)
@handle_analytics_errors("pattern detection")
async def detect_patterns(
    patient_id: Optional[UUID] = Query(None, description="Optional patient ID to analyze specific patient"),
    days_back: int = Query(DEFAULT_DAYS_BACK, ge=1, le=MAX_DAYS_BACK, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Detect patterns in patient data using trend analysis."""
    analytics_service = AnalyticsService(db)

    # Check permissions for specific patient using manual validation
    if patient_id:
        from app.repositories.patient import PatientRepository
        patient_repo = PatientRepository(db)
        patient = patient_repo.get(patient_id)

        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        if current_user.role != UserRole.ADMIN and patient.doctor_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Access denied: Cannot access this patient's data"
            )

    patterns = analytics_service.detect_patterns(patient_id, days_back)

    logger.info(f"Pattern detection completed for user {current_user.id}")
    return patterns

@router.get(
    "/engagement",
    response_model=None,
    summary="Get engagement metrics over a period",
    description="Aggregate engagement metrics for date range (used by frontend dashboard)"
)
@handle_analytics_errors("engagement range retrieval")
async def get_engagement_range(
    start_date: Optional[str] = Query(None, description="Start date (ISO datetime or date string)"),
    end_date: Optional[str] = Query(None, description="End date (ISO datetime or date string)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Return engagement series and summary for the date range for current doctor or admin."""
    analytics_service = AnalyticsService(db)
    cache_service = get_analytics_cache()

    # Convert string date parameters to date objects with error handling
    try:
        start_date_obj = coerce_to_date(start_date)
        end_date_obj = coerce_to_date(end_date)
        
        # Validate date range
        start_date_obj, end_date_obj = validate_date_range(start_date_obj, end_date_obj)
        
        # Set defaults if needed (last 7 days)
        start_date_obj, end_date_obj = set_default_date_range(start_date_obj, end_date_obj, 7)
        
    except ValueError as e:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid date format: {e}"
        )

    # determine filter
    doctor_id = None if current_user.role == UserRole.ADMIN else current_user.id

    # Build cache key parameters
    cache_key_params = {
        "start_date": start_date_obj.isoformat(),
        "end_date": end_date_obj.isoformat(),
        "doctor_id": str(doctor_id) if doctor_id else "all"
    }

    # Try to get from cache first
    def generate_engagement_data():
        # Build daily series similar to _get_engagement_chart_data
        series = []
        current = start_date_obj
        while current <= end_date_obj:
            # messages sent (outbound)
            q_out = db.query(Message).join(Patient).filter(
                and_(
                    Message.created_at >= current,
                    Message.created_at < current + timedelta(days=1),
                    Message.direction == MessageDirection.OUTBOUND
                )
            )
            # responses received (inbound)
            q_in = db.query(Message).join(Patient).filter(
                and_(
                    Message.created_at >= current,
                    Message.created_at < current + timedelta(days=1),
                    Message.direction == MessageDirection.INBOUND
                )
            )
            if doctor_id:
                q_out = q_out.filter(Patient.doctor_id == doctor_id)
                q_in = q_in.filter(Patient.doctor_id == doctor_id)
            sent = q_out.count()
            recv = q_in.count()
            series.append({
                "date": current.isoformat(),
                "messages_sent": sent,
                "responses_received": recv,
                "response_rate": round((recv / sent) * 100, 2) if sent else 0.0
            })
            current += timedelta(days=1)

        messages_sent = sum(d["messages_sent"] for d in series)
        responses_received = sum(d["responses_received"] for d in series)
        response_rate = round((responses_received / messages_sent) * 100, 2) if messages_sent else 0.0

        return {
            "period": {
                "start_date": start_date_obj.isoformat(),
                "end_date": end_date_obj.isoformat()
            },
            "series": series,
            "summary": {
                "messages_sent": messages_sent,
                "responses_received": responses_received,
                "response_rate": response_rate
            }
        }

    return cache_service.get_or_set(
        "engagement_chart",
        cache_key_params,
        generate_engagement_data
    )

@router.get(
    "/patients",
    response_model=None,
    summary="Get patient analytics for period",
    description="Return patient-level analytics list for date range (used by frontend)"
)
@handle_analytics_errors("patients analytics retrieval")
async def get_patients_analytics(
    start_date: Optional[str] = Query(None, description="Start date (ISO datetime or date string)"),
    end_date: Optional[str] = Query(None, description="End date (ISO datetime or date string)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    analytics_service = AnalyticsService(db)

    # Convert string date parameters to date objects with error handling
    try:
        start_date_obj = coerce_to_date(start_date)
        end_date_obj = coerce_to_date(end_date)
        
        # Validate date range
        start_date_obj, end_date_obj = validate_date_range(start_date_obj, end_date_obj)
        
        # Set defaults if needed (last 7 days)
        start_date_obj, end_date_obj = set_default_date_range(start_date_obj, end_date_obj, 7)
        
    except ValueError as e:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid date format: {e}"
        )

    # apply doctor filter
    doctor_id = None if current_user.role == UserRole.ADMIN else current_user.id

    # Build AnalyticsRequest for all patients of doctor
    request = AnalyticsRequest(
        doctor_id=doctor_id,
        start_date=start_date_obj,
        end_date=end_date_obj,
        metrics=["engagement", "quiz", "alerts"]
    )
    result = analytics_service.get_analytics(request)

    # Shape minimal response for frontend usage
    return {
        "period": {
            "start_date": start_date_obj.isoformat(),
            "end_date": end_date_obj.isoformat()
        },
        "items": [pa.model_dump() for pa in result.patient_analytics],
        "total": len(result.patient_analytics)
    }



@router.get(
    "/patient/{patient_id}/engagement",
    response_model=None,
    summary="Get patient engagement metrics",
    description="Get detailed engagement metrics for a specific patient"
)
@handle_analytics_errors("patient engagement retrieval")
async def get_patient_engagement(
    patient_id: UUID,
    days_back: int = Query(DEFAULT_DAYS_BACK, ge=1, le=MAX_DAYS_BACK, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Get detailed engagement metrics for a specific patient."""
    # Check permissions using manual validation
    from app.repositories.patient import PatientRepository
    patient_repo = PatientRepository(db)
    patient = patient_repo.get(patient_id)

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if current_user.role != UserRole.ADMIN and patient.doctor_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Cannot access this patient's data"
        )

    analytics_service = AnalyticsService(db)

    # Get patient analytics with engagement focus
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days_back)

    request = AnalyticsRequest(
        patient_ids=[patient_id],
        start_date=start_date,
        end_date=end_date,
        metrics=["engagement", "quiz", "alerts"]
    )

    analytics_data = analytics_service.get_analytics(request)

    if not analytics_data.patient_analytics:
        raise HTTPException(status_code=404, detail="Patient not found or no data available")

    patient_data = analytics_data.patient_analytics[0]

    # Get additional engagement details
    patterns = analytics_service.detect_patterns(patient_id, days_back)

    engagement_details = build_engagement_response(patient_data, patterns, patient_id, days_back)

    logger.info(f"Patient engagement data retrieved for patient {patient_id}")
    return engagement_details


@router.get(
    "/system/health",
    response_model=None,
    summary="Get system health metrics",
    description="Get system health and performance metrics"
)
@handle_analytics_errors("system health retrieval")
async def get_system_health(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Get system health and performance metrics."""
    # Only admins can access system health
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Admin privileges required"
        )

    analytics_service = AnalyticsService(db)

    # Get system analytics
    system_analytics = analytics_service._get_system_analytics(None, None)

    # Get additional health metrics
    health_metrics = {
        "system_status": "healthy",  # Would implement actual health checks
        "database_status": "connected",
        "redis_status": "connected",
        "external_services": {
            "evolution_api": "connected",
            "openai_api": "connected"
        },
        "performance_metrics": {
            "avg_response_time_ms": system_analytics.avg_response_time_ms,
            "system_uptime_hours": system_analytics.system_uptime_hours,
            "active_connections": 10,  # Would implement actual monitoring
            "memory_usage_percent": 65.5,
            "cpu_usage_percent": 45.2
        },
        "system_analytics": system_analytics,
        "last_updated": datetime.utcnow().isoformat()
    }

    logger.info(f"System health metrics retrieved by admin {current_user.id}")
    return health_metrics


@router.get(
    "/trends/weekly",
    response_model=None,
    summary="Get weekly trends",
    description="Get weekly trend analysis for key metrics"
)
@handle_analytics_errors("weekly trends retrieval")
async def get_weekly_trends(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get weekly trend analysis for key metrics."""
    analytics_service = AnalyticsService(db)

    # Get data for the last few weeks
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(weeks=DEFAULT_WEEKS_BACK)

    # Filter by doctor if not admin
    doctor_id = None if current_user.role == UserRole.ADMIN else current_user.id

    # Get all data for the period at once
    request = AnalyticsRequest(
        doctor_id=doctor_id,
        start_date=start_date,
        end_date=end_date,
        metrics=["engagement", "quiz", "alerts"]
    )

    all_analytics = analytics_service.get_analytics(request)

    # Group data by week
    weekly_trends = {
        "period": f"{start_date} to {end_date}",
        "weeks": []
    }

    # Calculate weekly buckets
    for week in range(DEFAULT_WEEKS_BACK):
        week_end = end_date - timedelta(weeks=week)
        week_start = week_end - timedelta(days=DAYS_PER_WEEK - 1)

        # Filter analytics data for this week
        week_patients = [
            p for p in all_analytics.patient_analytics
            if week_start <= datetime.fromisoformat(p.last_activity_date).date() <= week_end
        ]

        # Aggregate weekly metrics
        total_messages = sum(p.total_messages_sent + p.total_messages_received for p in week_patients)
        total_quizzes = sum(p.quizzes_completed for p in week_patients)
        total_alerts = sum(p.total_alerts for p in week_patients)

        weekly_trends["weeks"].append({
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "metrics": {
                "total_messages": total_messages,
                "total_quizzes": total_quizzes,
                "total_alerts": total_alerts,
                "active_patients": len(week_patients)
            }
        })

    # Reverse to show oldest to newest
    weekly_trends["weeks"].reverse()

    logger.info(f"Weekly trends retrieved for user {current_user.id}")
    return weekly_trends