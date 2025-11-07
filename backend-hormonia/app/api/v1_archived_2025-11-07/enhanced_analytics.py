"""
Enhanced Analytics Dashboard API with comprehensive metrics and real-time data.
Provides advanced analytics for patient management, messaging, and system performance.
"""
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any, Union
import logging
from uuid import UUID
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc
from pydantic import BaseModel, Field, validator
import pandas as pd
import json
from io import StringIO, BytesIO

from app.dependencies import get_db, get_current_user, get_analytics_service
from app.models.user import User
from app.services.analytics import AnalyticsService
from app.utils.logging import get_logger
from app.utils.unified_cache import cache_response

logger = get_logger(__name__)
router = APIRouter()

class TimeRange(str, Enum):
    """Time range options for analytics."""
    LAST_7_DAYS = "7d"
    LAST_30_DAYS = "30d"
    LAST_90_DAYS = "90d"
    LAST_6_MONTHS = "6m"
    LAST_YEAR = "1y"
    CUSTOM = "custom"

class MetricType(str, Enum):
    """Metric type categories."""
    PATIENTS = "patients"
    MESSAGES = "messages"
    QUIZ = "quiz"
    FLOWS = "flows"
    SYSTEM = "system"
    ENGAGEMENT = "engagement"
    OUTCOMES = "outcomes"

class AggregationLevel(str, Enum):
    """Data aggregation levels."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

class DashboardMetrics(BaseModel):
    """Main dashboard metrics overview."""
    # Patient metrics
    total_patients: int
    active_patients: int
    new_patients_today: int
    new_patients_this_week: int
    patients_by_status: Dict[str, int]
    patients_by_treatment_type: Dict[str, int]

    # Messaging metrics
    messages_sent_today: int
    messages_received_today: int
    total_conversations: int
    avg_response_time_hours: float
    message_delivery_rate: float

    # Quiz metrics
    active_quiz_sessions: int
    completed_quizzes_today: int
    avg_quiz_completion_rate: float
    pending_quiz_responses: int

    # Flow metrics
    active_flows: int
    completed_flows_today: int
    avg_flow_completion_time_days: float

    # System metrics
    system_health_score: float
    api_response_time_ms: float
    error_rate_24h: float
    uptime_percentage: float

    # Alerts and notifications
    active_alerts: int
    critical_alerts: int
    notifications_sent_today: int

class PatientAnalytics(BaseModel):
    """Patient-focused analytics."""
    demographics: Dict[str, Any]
    enrollment_trends: List[Dict[str, Any]]
    treatment_distribution: Dict[str, int]
    geographic_distribution: Dict[str, int]
    retention_metrics: Dict[str, float]
    outcome_metrics: Dict[str, float]
    risk_stratification: Dict[str, int]

class EngagementAnalytics(BaseModel):
    """Patient engagement analytics."""
    overall_engagement_score: float
    engagement_by_treatment_type: Dict[str, float]
    message_response_rates: Dict[str, float]
    quiz_participation_rates: Dict[str, float]
    flow_completion_rates: Dict[str, float]
    activity_patterns: List[Dict[str, Any]]
    engagement_trends: List[Dict[str, Any]]
    drop_off_analysis: Dict[str, Any]

class OutcomeAnalytics(BaseModel):
    """Treatment outcome analytics."""
    overall_outcomes: Dict[str, float]
    outcomes_by_treatment: Dict[str, Dict[str, float]]
    symptom_trends: List[Dict[str, Any]]
    quality_of_life_metrics: Dict[str, float]
    adherence_rates: Dict[str, float]
    satisfaction_scores: Dict[str, float]
    predictive_insights: List[Dict[str, Any]]

class SystemPerformanceMetrics(BaseModel):
    """System performance analytics."""
    api_performance: Dict[str, float]
    database_performance: Dict[str, float]
    message_queue_metrics: Dict[str, int]
    cache_performance: Dict[str, float]
    error_analytics: Dict[str, Any]
    resource_utilization: Dict[str, float]
    scalability_metrics: Dict[str, Any]

class RealtimeMetrics(BaseModel):
    """Real-time system metrics."""
    active_sessions: int
    current_api_requests_per_minute: int
    message_queue_depth: int
    websocket_connections: int
    database_connections: int
    cache_hit_rate: float
    memory_usage_percentage: float
    cpu_usage_percentage: float

@router.get(
    "/dashboard",
    response_model=DashboardMetrics,
    summary="Get Dashboard Metrics",
    description="""
    Retrieve comprehensive dashboard metrics for the main analytics overview.

    This endpoint provides real-time metrics including:
    - Patient statistics and trends
    - Messaging performance
    - Quiz completion rates
    - Flow progress analytics
    - System health indicators
    - Alert summaries

    **Caching**: Results cached for 5 minutes for performance.
    **Rate Limit**: 30 requests per minute per user.
    """,
    responses={
        200: {
            "description": "Dashboard metrics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "total_patients": 1250,
                        "active_patients": 980,
                        "new_patients_today": 15,
                        "messages_sent_today": 320,
                        "avg_response_time_hours": 2.5,
                        "system_health_score": 98.5,
                        "active_alerts": 3
                    }
                }
            }
        }
    }
)
@cache_response(seconds=300)  # 5-minute cache
async def get_dashboard_metrics(
    time_range: TimeRange = Query(TimeRange.LAST_30_DAYS, description="Time range for metrics"),
    include_predictions: bool = Query(False, description="Include predictive analytics"),
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
) -> DashboardMetrics:
    """Get comprehensive dashboard metrics."""
    try:
        metrics = await analytics_service.get_dashboard_metrics(
            current_user, time_range, include_predictions=include_predictions
        )

        logger.info(
            f"Dashboard metrics retrieved for time range: {time_range}",
            extra={
                "event_type": "dashboard_metrics_viewed",
                "user_id": str(current_user.id),
                "time_range": time_range,
                "total_patients": metrics.total_patients
            }
        )

        return metrics

    except Exception as e:
        logger.error(f"Error retrieving dashboard metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard metrics"
        )

@router.get(
    "/patients",
    response_model=PatientAnalytics,
    summary="Get Patient Analytics",
    description="""
    Retrieve comprehensive patient analytics including demographics, trends, and outcomes.

    Provides detailed insights into:
    - Patient demographics and distribution
    - Enrollment and retention trends
    - Treatment type analytics
    - Geographic distribution
    - Risk stratification
    - Outcome metrics
    """,
    responses={
        200: {
            "description": "Patient analytics retrieved successfully"
        }
    }
)
async def get_patient_analytics(
    time_range: TimeRange = Query(TimeRange.LAST_90_DAYS, description="Analysis time range"),
    treatment_type: Optional[str] = Query(None, description="Filter by treatment type"),
    include_demographics: bool = Query(True, description="Include demographic analysis"),
    include_outcomes: bool = Query(True, description="Include outcome metrics"),
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
) -> PatientAnalytics:
    """Get comprehensive patient analytics."""
    try:
        analytics = await analytics_service.get_patient_analytics(
            current_user,
            time_range=time_range,
            treatment_type=treatment_type,
            include_demographics=include_demographics,
            include_outcomes=include_outcomes
        )

        logger.info(
            f"Patient analytics retrieved for time range: {time_range}",
            extra={
                "event_type": "patient_analytics_viewed",
                "user_id": str(current_user.id),
                "time_range": time_range,
                "treatment_type": treatment_type
            }
        )

        return analytics

    except Exception as e:
        logger.error(f"Error retrieving patient analytics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve patient analytics"
        )

@router.get(
    "/engagement",
    response_model=EngagementAnalytics,
    summary="Get Engagement Analytics",
    description="""
    Retrieve patient engagement analytics with detailed participation metrics.

    Analyzes:
    - Overall engagement scores
    - Message response patterns
    - Quiz participation rates
    - Flow completion analytics
    - Activity trends
    - Drop-off points
    """,
    responses={
        200: {
            "description": "Engagement analytics retrieved successfully"
        }
    }
)
async def get_engagement_analytics(
    time_range: TimeRange = Query(TimeRange.LAST_30_DAYS, description="Analysis time range"),
    aggregation: AggregationLevel = Query(AggregationLevel.DAILY, description="Data aggregation level"),
    patient_cohort: Optional[str] = Query(None, description="Patient cohort filter"),
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
) -> EngagementAnalytics:
    """Get patient engagement analytics."""
    try:
        analytics = await analytics_service.get_engagement_analytics(
            current_user,
            time_range=time_range,
            aggregation=aggregation,
            patient_cohort=patient_cohort
        )

        logger.info(
            f"Engagement analytics retrieved: {time_range} aggregated {aggregation}",
            extra={
                "event_type": "engagement_analytics_viewed",
                "user_id": str(current_user.id),
                "time_range": time_range,
                "aggregation": aggregation,
                "overall_score": analytics.overall_engagement_score
            }
        )

        return analytics

    except Exception as e:
        logger.error(f"Error retrieving engagement analytics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve engagement analytics"
        )

@router.get(
    "/outcomes",
    response_model=OutcomeAnalytics,
    summary="Get Outcome Analytics",
    description="""
    Retrieve treatment outcome analytics with predictive insights.

    Provides analysis of:
    - Treatment effectiveness metrics
    - Symptom trend analysis
    - Quality of life improvements
    - Medication adherence rates
    - Patient satisfaction scores
    - Predictive outcome models
    """,
    responses={
        200: {
            "description": "Outcome analytics retrieved successfully"
        }
    }
)
async def get_outcome_analytics(
    time_range: TimeRange = Query(TimeRange.LAST_6_MONTHS, description="Analysis time range"),
    treatment_type: Optional[str] = Query(None, description="Filter by treatment type"),
    include_predictions: bool = Query(True, description="Include predictive insights"),
    confidence_threshold: float = Query(0.7, ge=0.0, le=1.0, description="Prediction confidence threshold"),
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
) -> OutcomeAnalytics:
    """Get treatment outcome analytics."""
    try:
        analytics = await analytics_service.get_outcome_analytics(
            current_user,
            time_range=time_range,
            treatment_type=treatment_type,
            include_predictions=include_predictions,
            confidence_threshold=confidence_threshold
        )

        logger.info(
            f"Outcome analytics retrieved for time range: {time_range}",
            extra={
                "event_type": "outcome_analytics_viewed",
                "user_id": str(current_user.id),
                "time_range": time_range,
                "treatment_type": treatment_type,
                "include_predictions": include_predictions
            }
        )

        return analytics

    except Exception as e:
        logger.error(f"Error retrieving outcome analytics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve outcome analytics"
        )

@router.get(
    "/system/performance",
    response_model=SystemPerformanceMetrics,
    summary="Get System Performance Metrics",
    description="""
    Retrieve comprehensive system performance analytics.

    Monitors:
    - API response times and throughput
    - Database performance metrics
    - Message queue statistics
    - Cache performance
    - Error rates and patterns
    - Resource utilization
    - Scalability indicators
    """,
    responses={
        200: {
            "description": "System performance metrics retrieved successfully"
        }
    }
)
async def get_system_performance(
    time_range: TimeRange = Query(TimeRange.LAST_7_DAYS, description="Analysis time range"),
    include_detailed_errors: bool = Query(False, description="Include detailed error analysis"),
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
) -> SystemPerformanceMetrics:
    """Get system performance metrics."""
    try:
        # Check if user has admin privileges for system metrics
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required for system performance metrics"
            )

        metrics = await analytics_service.get_system_performance_metrics(
            time_range=time_range,
            include_detailed_errors=include_detailed_errors
        )

        logger.info(
            f"System performance metrics retrieved for time range: {time_range}",
            extra={
                "event_type": "system_performance_viewed",
                "user_id": str(current_user.id),
                "time_range": time_range,
                "include_detailed_errors": include_detailed_errors
            }
        )

        return metrics

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving system performance metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system performance metrics"
        )

@router.get(
    "/realtime",
    response_model=RealtimeMetrics,
    summary="Get Real-time Metrics",
    description="""
    Retrieve real-time system metrics for live monitoring.

    Provides current status of:
    - Active user sessions
    - API request rates
    - Message queue status
    - WebSocket connections
    - Resource utilization
    - System health indicators

    **Update Frequency**: Updates every 30 seconds.
    """,
    responses={
        200: {
            "description": "Real-time metrics retrieved successfully"
        }
    }
)
async def get_realtime_metrics(
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
) -> RealtimeMetrics:
    """Get real-time system metrics."""
    try:
        metrics = await analytics_service.get_realtime_metrics()

        # Don't log every real-time request to avoid noise
        # Only log if there are concerning metrics
        if metrics.memory_usage_percentage > 80 or metrics.cpu_usage_percentage > 80:
            logger.warning(
                f"High resource utilization detected: CPU {metrics.cpu_usage_percentage}%, Memory {metrics.memory_usage_percentage}%",
                extra={
                    "event_type": "high_resource_utilization",
                    "cpu_usage": metrics.cpu_usage_percentage,
                    "memory_usage": metrics.memory_usage_percentage,
                    "user_id": str(current_user.id)
                }
            )

        return metrics

    except Exception as e:
        logger.error(f"Error retrieving real-time metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve real-time metrics"
        )

@router.get(
    "/export/{metric_type}",
    summary="Export Analytics Data",
    description="""
    Export analytics data in various formats (CSV, JSON, Excel).

    Supports exporting:
    - Patient analytics
    - Engagement metrics
    - Outcome data
    - System performance logs
    - Custom metric combinations

    **Formats**: CSV, JSON, Excel
    **Rate Limit**: 5 exports per hour per user.
    """,
    responses={
        200: {
            "description": "Data exported successfully",
            "content": {
                "application/json": {"example": "JSON data"},
                "text/csv": {"example": "CSV data"},
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {"example": "Excel data"}
            }
        }
    }
)
async def export_analytics_data(
    metric_type: MetricType,
    format: str = Query("csv", regex="^(csv|json|excel)$", description="Export format"),
    time_range: TimeRange = Query(TimeRange.LAST_30_DAYS, description="Data time range"),
    start_date: Optional[date] = Query(None, description="Custom start date"),
    end_date: Optional[date] = Query(None, description="Custom end date"),
    filters: Optional[str] = Query(None, description="Additional filters (JSON)"),
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
) -> StreamingResponse:
    """Export analytics data in specified format."""
    try:
        # Parse filters if provided
        filter_dict = {}
        if filters:
            try:
                filter_dict = json.loads(filters)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid filters JSON format"
                )

        # Get data
        data = await analytics_service.export_analytics_data(
            current_user,
            metric_type=metric_type,
            time_range=time_range,
            start_date=start_date,
            end_date=end_date,
            filters=filter_dict
        )

        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{metric_type}_analytics_{timestamp}"

        # Convert to requested format
        if format == "json":
            content = json.dumps(data, indent=2, default=str)
            media_type = "application/json"
            filename += ".json"

        elif format == "excel":
            # Convert to Excel
            df = pd.DataFrame(data)
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name=metric_type.title())
            buffer.seek(0)

            return StreamingResponse(
                BytesIO(buffer.read()),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={filename}.xlsx"}
            )

        else:  # CSV format
            df = pd.DataFrame(data)
            buffer = StringIO()
            df.to_csv(buffer, index=False)
            content = buffer.getvalue()
            media_type = "text/csv"
            filename += ".csv"

        logger.info(
            f"Analytics data exported: {metric_type} in {format} format",
            extra={
                "event_type": "analytics_data_exported",
                "user_id": str(current_user.id),
                "metric_type": metric_type,
                "format": format,
                "time_range": time_range,
                "record_count": len(data) if isinstance(data, list) else 1
            }
        )

        return StreamingResponse(
            StringIO(content),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting analytics data: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export analytics data"
        )

@router.get(
    "/trends/{metric_type}",
    response_model=List[Dict[str, Any]],
    summary="Get Metric Trends",
    description="""
    Retrieve trend analysis for specific metrics over time.

    Provides time-series data with:
    - Historical trends
    - Seasonal patterns
    - Anomaly detection
    - Forecast projections
    - Comparative analysis
    """,
    responses={
        200: {
            "description": "Trend data retrieved successfully"
        }
    }
)
async def get_metric_trends(
    metric_type: MetricType,
    time_range: TimeRange = Query(TimeRange.LAST_90_DAYS, description="Analysis time range"),
    aggregation: AggregationLevel = Query(AggregationLevel.DAILY, description="Data aggregation level"),
    include_forecast: bool = Query(False, description="Include forecast predictions"),
    forecast_days: int = Query(30, ge=1, le=365, description="Forecast period in days"),
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
) -> List[Dict[str, Any]]:
    """Get trend analysis for specific metrics."""
    try:
        trends = await analytics_service.get_metric_trends(
            current_user,
            metric_type=metric_type,
            time_range=time_range,
            aggregation=aggregation,
            include_forecast=include_forecast,
            forecast_days=forecast_days
        )

        logger.info(
            f"Metric trends retrieved: {metric_type} for {time_range}",
            extra={
                "event_type": "metric_trends_viewed",
                "user_id": str(current_user.id),
                "metric_type": metric_type,
                "time_range": time_range,
                "aggregation": aggregation,
                "data_points": len(trends)
            }
        )

        return trends

    except Exception as e:
        logger.error(f"Error retrieving metric trends: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve metric trends"
        )