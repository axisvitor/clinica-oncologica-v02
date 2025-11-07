"""
Real-time Metrics API Endpoint for Hormonia Healthcare System.

This module provides comprehensive metrics and monitoring endpoints including:
- Healthcare-specific KPIs (engagement, quiz completion, AI personalization impact)
- Real-time system performance metrics
- Patient outcome analytics
- AI humanization effectiveness metrics
- Quiz flow analytics with completion rates
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.dependencies import (
    get_db, get_current_user, get_doctor_user, get_admin_user,
    get_redis, get_request_context, RequestContext
)
from app.models.user import User, UserRole
from app.services.metrics_collector import MetricsCollectorService
from app.services.audit_service import AuditService
# from app.monitoring.health_endpoints import SystemHealthMonitor  # TODO: Implement SystemHealthMonitor class
import logging
import json
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/metrics", tags=["metrics"])


class MetricsSummary(BaseModel):
    """Healthcare metrics summary response."""
    engagement_rate: float = Field(description="Overall patient engagement rate (0-100%)")
    quiz_completion_rate: float = Field(description="Quiz completion rate (0-100%)")
    ai_personalization_impact: float = Field(description="AI personalization effectiveness (0-100%)")
    active_patients: int = Field(description="Number of active patients")
    daily_messages: int = Field(description="Messages sent in last 24 hours")
    system_health_score: float = Field(description="Overall system health (0-100%)")
    timestamp: datetime = Field(description="Metrics timestamp")


class EngagementMetrics(BaseModel):
    """Patient engagement metrics."""
    total_patients: int
    active_patients: int
    engagement_rate: float
    response_rate: float
    avg_response_time_hours: float
    daily_active_users: int
    weekly_active_users: int
    monthly_active_users: int
    engagement_trend: List[Dict[str, Any]]


class QuizMetrics(BaseModel):
    """Quiz performance metrics."""
    total_quizzes_sent: int
    completed_quizzes: int
    completion_rate: float
    avg_completion_time_minutes: float
    quiz_types: Dict[str, Dict[str, Any]]
    monthly_quiz_stats: Dict[str, Any]
    completion_trend: List[Dict[str, Any]]


class AIPersonalizationMetrics(BaseModel):
    """AI personalization effectiveness metrics."""
    total_messages_processed: int
    personalized_messages: int
    personalization_rate: float
    avg_personalization_score: float
    safety_interventions: int
    fallback_rate: float
    response_quality_score: float
    personalization_impact: List[Dict[str, Any]]


class SystemPerformanceMetrics(BaseModel):
    """System performance metrics."""
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    active_connections: int
    response_time_ms: float
    error_rate: float
    uptime_seconds: int
    throughput_rps: float


class RealTimeMetrics(BaseModel):
    """Real-time metrics container."""
    engagement: EngagementMetrics
    quiz: QuizMetrics
    ai_personalization: AIPersonalizationMetrics
    system_performance: SystemPerformanceMetrics
    alerts_count: int
    last_updated: datetime


# WebSocket connection manager for real-time metrics
class MetricsWebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, user: User):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Metrics WebSocket connected for user {user.id}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("Metrics WebSocket disconnected")

    async def broadcast_metrics(self, metrics: Dict[str, Any]):
        """Broadcast metrics to all connected clients."""
        if not self.active_connections:
            return

        message = json.dumps(metrics, default=str)
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting metrics: {e}")
                disconnected.append(connection)

        # Remove disconnected connections
        for connection in disconnected:
            self.disconnect(connection)


metrics_manager = MetricsWebSocketManager()


@router.get("/summary", response_model=MetricsSummary)
async def get_metrics_summary(
    current_user: User = Depends(get_doctor_user),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context)
):
    """
    Get high-level healthcare metrics summary.

    Returns key performance indicators for the healthcare system including
    engagement rates, quiz completion, and AI personalization effectiveness.
    """
    try:
        metrics_service = MetricsCollectorService(db)
        summary = await metrics_service.get_healthcare_summary()

        # Audit access
        audit_service = AuditService(db)
        audit_service.log_event(
            event_type="metrics_access",
            user_id=current_user.id,
            resource_type="metrics_summary",
            resource_id="healthcare_summary",
            details={"accessed_by_role": current_user.role.value},
            ip_address=context.ip_address,
            user_agent=context.user_agent
        )

        return MetricsSummary(**summary)

    except Exception as e:
        logger.error(f"Error retrieving metrics summary: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error retrieving metrics summary"
        )


@router.get("/realtime", response_model=RealTimeMetrics)
async def get_realtime_metrics(
    current_user: User = Depends(get_doctor_user),
    db: Session = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """
    Get comprehensive real-time metrics for dashboard.

    Returns detailed metrics including engagement, quiz performance,
    AI personalization, and system performance data.
    """
    try:
        metrics_service = MetricsCollectorService(db, redis_client)

        # Collect all metrics concurrently
        engagement_metrics = await metrics_service.get_engagement_metrics()
        quiz_metrics = await metrics_service.get_quiz_metrics()
        ai_metrics = await metrics_service.get_ai_personalization_metrics()
        system_metrics = await metrics_service.get_system_performance_metrics()
        alerts_count = await metrics_service.get_active_alerts_count()

        return RealTimeMetrics(
            engagement=EngagementMetrics(**engagement_metrics),
            quiz=QuizMetrics(**quiz_metrics),
            ai_personalization=AIPersonalizationMetrics(**ai_metrics),
            system_performance=SystemPerformanceMetrics(**system_metrics),
            alerts_count=alerts_count,
            last_updated=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error retrieving real-time metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error retrieving real-time metrics"
        )


@router.get("/engagement")
async def get_engagement_metrics(
    current_user: User = Depends(get_doctor_user),
    db: Session = Depends(get_db),
    period_days: int = Query(30, ge=1, le=365, description="Analysis period in days")
):
    """
    Get detailed patient engagement metrics.

    Provides comprehensive engagement analytics including response rates,
    active user counts, and engagement trends over time.
    """
    try:
        metrics_service = MetricsCollectorService(db)

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=period_days)

        engagement_data = await metrics_service.get_detailed_engagement_metrics(
            start_date=start_date,
            end_date=end_date,
            doctor_id=current_user.id if current_user.role != UserRole.ADMIN else None
        )

        return {
            "data": engagement_data,
            "period": f"{period_days} days",
            "generated_at": datetime.utcnow()
        }

    except Exception as e:
        logger.error(f"Error retrieving engagement metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error retrieving engagement metrics"
        )


@router.get("/quiz-performance")
async def get_quiz_performance(
    current_user: User = Depends(get_doctor_user),
    db: Session = Depends(get_db),
    quiz_type: Optional[str] = Query(None, description="Filter by quiz type"),
    period_days: int = Query(30, ge=1, le=365, description="Analysis period in days")
):
    """
    Get detailed quiz performance analytics.

    Provides completion rates, time analysis, and quiz type performance.
    """
    try:
        metrics_service = MetricsCollectorService(db)

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=period_days)

        quiz_data = await metrics_service.get_quiz_performance_metrics(
            start_date=start_date,
            end_date=end_date,
            doctor_id=current_user.id if current_user.role != UserRole.ADMIN else None
        )

        return {
            "data": quiz_data,
            "filters": {
                "quiz_type": quiz_type,
                "period_days": period_days
            },
            "generated_at": datetime.utcnow()
        }

    except Exception as e:
        logger.error(f"Error retrieving quiz performance: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error retrieving quiz performance"
        )


@router.get("/ai-personalization")
async def get_ai_personalization_metrics(
    current_user: User = Depends(get_doctor_user),
    db: Session = Depends(get_db),
    period_days: int = Query(30, ge=1, le=365, description="Analysis period in days")
):
    """
    Get AI personalization effectiveness metrics.

    Analyzes AI humanization impact, safety interventions, and quality scores.
    """
    try:
        metrics_service = MetricsCollectorService(db)

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=period_days)

        ai_data = await metrics_service.get_ai_personalization_analytics(
            start_date=start_date,
            end_date=end_date,
            doctor_id=current_user.id if current_user.role != UserRole.ADMIN else None
        )

        return {
            "data": ai_data,
            "period": f"{period_days} days",
            "ai_configuration": {
                "humanization_enabled": True,
                "safety_mode": True,
                "fallback_enabled": True
            },
            "generated_at": datetime.utcnow()
        }

    except Exception as e:
        logger.error(f"Error retrieving AI personalization metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error retrieving AI personalization metrics"
        )


@router.get("/system-health")
async def get_system_health(
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """
    Get comprehensive system health metrics (Admin only).

    Provides system performance, resource usage, and health indicators.
    """
    try:
        health_monitor = SystemHealthMonitor()
        metrics_service = MetricsCollectorService(db, redis_client)

        # Get system health data
        health_data = await health_monitor.get_comprehensive_health()
        performance_data = await metrics_service.get_system_performance_metrics()

        return {
            "health": health_data,
            "performance": performance_data,
            "timestamp": datetime.utcnow()
        }

    except Exception as e:
        logger.error(f"Error retrieving system health: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error retrieving system health"
        )


@router.get("/alerts")
async def get_active_alerts(
    current_user: User = Depends(get_doctor_user),
    db: Session = Depends(get_db),
    severity: Optional[str] = Query(None, description="Filter by severity (low, medium, high, critical)")
):
    """
    Get active system alerts and warnings.

    Returns current alerts based on configured thresholds and anomaly detection.
    """
    try:
        metrics_service = MetricsCollectorService(db)

        alerts = await metrics_service.get_active_alerts(
            severity_filter=severity,
            user_role=current_user.role
        )

        return {
            "alerts": alerts,
            "count": len(alerts),
            "filters": {"severity": severity},
            "generated_at": datetime.utcnow()
        }

    except Exception as e:
        logger.error(f"Error retrieving alerts: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error retrieving alerts"
        )


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: UUID,
    current_user: User = Depends(get_doctor_user),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context)
):
    """
    Acknowledge an active alert.

    Marks an alert as acknowledged by the current user.
    """
    try:
        metrics_service = MetricsCollectorService(db)

        result = await metrics_service.acknowledge_alert(
            alert_id=alert_id,
            user_id=current_user.id,
            ip_address=context.ip_address
        )

        if not result:
            raise HTTPException(
                status_code=404,
                detail="Alert not found or already acknowledged"
            )

        return {
            "message": "Alert acknowledged successfully",
            "alert_id": alert_id,
            "acknowledged_by": current_user.id,
            "acknowledged_at": datetime.utcnow()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acknowledging alert {alert_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error acknowledging alert"
        )


@router.websocket("/live")
async def metrics_websocket(
    websocket: WebSocket,
    db: Session = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """
    WebSocket endpoint for live metrics streaming.

    Provides real-time metrics updates for dashboard components.
    Authentication is handled via query parameters.
    """
    # Basic authentication check for WebSocket
    try:
        from app.dependencies import get_current_user_websocket
        user = await get_current_user_websocket(websocket)

        if not user or user.role not in {UserRole.DOCTOR, UserRole.ADMIN, UserRole.NURSE, UserRole.RESEARCHER}:
            await websocket.close(code=4001, reason="Unauthorized")
            return

    except Exception as e:
        logger.error(f"WebSocket authentication failed: {e}")
        await websocket.close(code=4001, reason="Authentication failed")
        return

    await metrics_manager.connect(websocket, user)
    metrics_service = MetricsCollectorService(db, redis_client)

    try:
        while True:
            # Send metrics update every 5 seconds
            try:
                # Get real-time metrics
                metrics_data = {
                    "engagement": await metrics_service.get_engagement_metrics(),
                    "quiz": await metrics_service.get_quiz_metrics(),
                    "ai_personalization": await metrics_service.get_ai_personalization_metrics(),
                    "system_performance": await metrics_service.get_system_performance_metrics(),
                    "alerts_count": await metrics_service.get_active_alerts_count(),
                    "timestamp": datetime.utcnow().isoformat()
                }

                await websocket.send_text(json.dumps(metrics_data, default=str))

            except Exception as e:
                logger.error(f"Error sending metrics via WebSocket: {e}")
                break

            await asyncio.sleep(5)  # Update every 5 seconds

    except WebSocketDisconnect:
        logger.info("Metrics WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        metrics_manager.disconnect(websocket)


@router.get("/export")
async def export_metrics(
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    start_date: datetime = Query(..., description="Start date for export"),
    end_date: datetime = Query(..., description="End date for export"),
    format: str = Query("json", description="Export format (json, csv)")
):
    """
    Export metrics data for analysis (Admin only).

    Exports comprehensive metrics data for specified date range.
    """
    try:
        if end_date <= start_date:
            raise HTTPException(
                status_code=400,
                detail="End date must be after start date"
            )

        if (end_date - start_date).days > 365:
            raise HTTPException(
                status_code=400,
                detail="Export period cannot exceed 365 days"
            )

        metrics_service = MetricsCollectorService(db)

        export_data = await metrics_service.export_metrics(
            start_date=start_date,
            end_date=end_date,
            format=format
        )

        # Audit export
        audit_service = AuditService(db)
        audit_service.log_event(
            event_type="metrics_export",
            user_id=current_user.id,
            resource_type="metrics_data",
            resource_id=f"export_{start_date.date()}_{end_date.date()}",
            details={
                "format": format,
                "period_days": (end_date - start_date).days,
                "export_size": len(str(export_data))
            }
        )

        return {
            "data": export_data,
            "metadata": {
                "start_date": start_date,
                "end_date": end_date,
                "format": format,
                "exported_at": datetime.utcnow(),
                "exported_by": current_user.id
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error exporting metrics"
        )
