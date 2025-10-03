"""
API endpoints for monitoring and alerting system.
"""
from datetime import datetime, timedelta
from typing import List, Optional, Any
from uuid import UUID
import redis.asyncio as redis

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_redis, get_current_user
from app.services.flow_monitoring import FlowMonitoringService
from app.services.critical_error_escalation import CriticalErrorEscalationService
from app.services.performance_monitoring import PerformanceMonitoringService
from app.services.automated_recovery import AutomatedRecoveryService
from app.schemas.common import PaginatedResponse
from app.models.user import User

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/health", response_model=None)
async def get_system_health(
    db: Session = Depends(get_db),
    redis: Optional[redis.Redis] = Depends(get_redis),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Get overall system health status."""
    try:
        # Initialize monitoring service
        from app.repositories.flow import FlowRepository
        from app.services.data_corruption_detector import DataCorruptionDetector
        
        flow_repo = FlowRepository(db)
        corruption_detector = DataCorruptionDetector(db, redis)
        
        monitoring_service = FlowMonitoringService(
            db=db,
            redis=redis,
            flow_repository=flow_repo,
            corruption_detector=corruption_detector
        )
        
        health_status = await monitoring_service.get_system_health()
        return health_status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting system health: {str(e)}")


@router.get("/metrics", response_model=None)
async def get_performance_metrics(
    db: Session = Depends(get_db),
    redis: Optional[redis.Redis] = Depends(get_redis),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Get current performance metrics."""
    try:
        from app.repositories.flow import FlowRepository
        
        flow_repo = FlowRepository(db)
        performance_service = PerformanceMonitoringService(
            db=db,
            redis=redis,
            flow_repository=flow_repo
        )
        
        metrics = await performance_service.collect_performance_metrics()
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'metrics': [
                {
                    'metric_type': m.metric_type.value,
                    'value': m.value,
                    'component': m.component,
                    'metadata': m.metadata
                }
                for m in metrics
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting performance metrics: {str(e)}")


@router.get("/alerts", response_model=None)
async def get_active_alerts(
    db: Session = Depends(get_db),
    redis: Optional[redis.Redis] = Depends(get_redis),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    component: Optional[str] = Query(None, description="Filter by component"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Get active alerts."""
    try:
        from app.repositories.flow import FlowRepository
        from app.services.data_corruption_detector import DataCorruptionDetector
        
        flow_repo = FlowRepository(db)
        corruption_detector = DataCorruptionDetector(db, redis)
        
        monitoring_service = FlowMonitoringService(
            db=db,
            redis=redis,
            flow_repository=flow_repo,
            corruption_detector=corruption_detector
        )
        
        alerts = await monitoring_service.get_active_alerts()
        
        # Apply filters
        if severity:
            alerts = [a for a in alerts if a.severity.value == severity]
        
        if component:
            alerts = [a for a in alerts if a.component == component]
        
        # Apply limit
        alerts = alerts[:limit]
        
        return {
            'alerts': [
                {
                    'id': alert.id,
                    'severity': alert.severity.value,
                    'title': alert.title,
                    'message': alert.message,
                    'component': alert.component,
                    'metric_value': alert.metric_value,
                    'threshold': alert.threshold,
                    'created_at': alert.created_at.isoformat(),
                    'resolved_at': alert.resolved_at.isoformat() if alert.resolved_at else None,
                    'metadata': alert.metadata
                }
                for alert in alerts
            ],
            'total_count': len(alerts),
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting active alerts: {str(e)}")


@router.post("/alerts/{alert_id}/resolve", response_model=None)
async def resolve_alert(
    alert_id: str,
    resolution_note: str,
    db: Session = Depends(get_db),
    redis: Optional[redis.Redis] = Depends(get_redis),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Resolve an active alert."""
    try:
        from app.repositories.flow import FlowRepository
        from app.services.data_corruption_detector import DataCorruptionDetector
        
        flow_repo = FlowRepository(db)
        corruption_detector = DataCorruptionDetector(db, redis)
        
        monitoring_service = FlowMonitoringService(
            db=db,
            redis=redis,
            flow_repository=flow_repo,
            corruption_detector=corruption_detector
        )
        
        success = await monitoring_service.resolve_alert(alert_id, resolution_note)
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {
            'success': True,
            'message': f'Alert {alert_id} resolved successfully',
            'resolved_by': current_user.email,
            'resolved_at': datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resolving alert: {str(e)}")


@router.get("/bottlenecks", response_model=None)
async def get_performance_bottlenecks(
    db: Session = Depends(get_db),
    redis: Optional[redis.Redis] = Depends(get_redis),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Get detected performance bottlenecks."""
    try:
        from app.repositories.flow import FlowRepository
        
        flow_repo = FlowRepository(db)
        performance_service = PerformanceMonitoringService(
            db=db,
            redis=redis,
            flow_repository=flow_repo
        )
        
        bottlenecks = await performance_service.detect_bottlenecks()
        
        # Apply severity filter
        if severity:
            bottlenecks = [b for b in bottlenecks if b.severity == severity]
        
        return {
            'bottlenecks': [
                {
                    'bottleneck_type': b.bottleneck_type.value,
                    'severity': b.severity,
                    'description': b.description,
                    'affected_components': b.affected_components,
                    'recommendations': b.recommendations,
                    'detected_at': b.detected_at.isoformat()
                }
                for b in bottlenecks
            ],
            'total_count': len(bottlenecks),
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting bottlenecks: {str(e)}")


@router.get("/performance/report", response_model=None)
async def get_performance_report(
    db: Session = Depends(get_db),
    redis: Optional[redis.Redis] = Depends(get_redis),
    hours: int = Query(24, ge=1, le=168, description="Time range in hours"),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Get comprehensive performance report."""
    try:
        from app.repositories.flow import FlowRepository
        
        flow_repo = FlowRepository(db)
        performance_service = PerformanceMonitoringService(
            db=db,
            redis=redis,
            flow_repository=flow_repo
        )
        
        time_range = timedelta(hours=hours)
        report = await performance_service.get_performance_report(time_range)
        
        return report
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating performance report: {str(e)}")


@router.get("/performance/dashboard", response_model=None)
async def get_performance_dashboard(
    db: Session = Depends(get_db),
    redis: Optional[redis.Redis] = Depends(get_redis),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Get real-time performance dashboard data."""
    try:
        from app.repositories.flow import FlowRepository
        
        flow_repo = FlowRepository(db)
        performance_service = PerformanceMonitoringService(
            db=db,
            redis=redis,
            flow_repository=flow_repo
        )
        
        dashboard_data = await performance_service.get_real_time_performance_dashboard()
        
        return dashboard_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting performance dashboard: {str(e)}")


@router.get("/escalations", response_model=None)
async def get_active_escalations(
    db: Session = Depends(get_db),
    redis: Optional[redis.Redis] = Depends(get_redis),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Get active escalations."""
    try:
        from app.repositories.flow import FlowRepository
        from app.services.data_corruption_detector import DataCorruptionDetector
        from app.services.websocket_events import WebSocketEventService
        
        flow_repo = FlowRepository(db)
        corruption_detector = DataCorruptionDetector(db, redis)
        websocket_service = WebSocketEventService(redis)
        
        monitoring_service = FlowMonitoringService(
            db=db,
            redis=redis,
            flow_repository=flow_repo,
            corruption_detector=corruption_detector
        )
        
        escalation_service = CriticalErrorEscalationService(
            db=db,
            redis=redis,
            monitoring_service=monitoring_service,
            websocket_service=websocket_service
        )
        
        escalations = await escalation_service.get_active_escalations()
        
        return {
            'escalations': escalations,
            'total_count': len(escalations),
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting escalations: {str(e)}")


@router.post("/escalations/{escalation_id}/acknowledge", response_model=None)
async def acknowledge_escalation(
    escalation_id: str,
    db: Session = Depends(get_db),
    redis: Optional[redis.Redis] = Depends(get_redis),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Acknowledge an escalation."""
    try:
        from app.repositories.flow import FlowRepository
        from app.services.data_corruption_detector import DataCorruptionDetector
        from app.services.websocket_events import WebSocketEventService
        
        flow_repo = FlowRepository(db)
        corruption_detector = DataCorruptionDetector(db, redis)
        websocket_service = WebSocketEventService(redis)
        
        monitoring_service = FlowMonitoringService(
            db=db,
            redis=redis,
            flow_repository=flow_repo,
            corruption_detector=corruption_detector
        )
        
        escalation_service = CriticalErrorEscalationService(
            db=db,
            redis=redis,
            monitoring_service=monitoring_service,
            websocket_service=websocket_service
        )
        
        success = await escalation_service.acknowledge_escalation(escalation_id, current_user.email)
        
        if not success:
            raise HTTPException(status_code=404, detail="Escalation not found")
        
        return {
            'success': True,
            'message': f'Escalation {escalation_id} acknowledged successfully',
            'acknowledged_by': current_user.email,
            'acknowledged_at': datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error acknowledging escalation: {str(e)}")


@router.post("/escalations/{escalation_id}/resolve", response_model=None)
async def resolve_escalation(
    escalation_id: str,
    resolution_note: str,
    db: Session = Depends(get_db),
    redis: Optional[redis.Redis] = Depends(get_redis),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Resolve an escalation."""
    try:
        from app.repositories.flow import FlowRepository
        from app.services.data_corruption_detector import DataCorruptionDetector
        from app.services.websocket_events import WebSocketEventService
        
        flow_repo = FlowRepository(db)
        corruption_detector = DataCorruptionDetector(db, redis)
        websocket_service = WebSocketEventService(redis)
        
        monitoring_service = FlowMonitoringService(
            db=db,
            redis=redis,
            flow_repository=flow_repo,
            corruption_detector=corruption_detector
        )
        
        escalation_service = CriticalErrorEscalationService(
            db=db,
            redis=redis,
            monitoring_service=monitoring_service,
            websocket_service=websocket_service
        )
        
        success = await escalation_service.resolve_escalation(escalation_id, current_user.email, resolution_note)
        
        if not success:
            raise HTTPException(status_code=404, detail="Escalation not found")
        
        return {
            'success': True,
            'message': f'Escalation {escalation_id} resolved successfully',
            'resolved_by': current_user.email,
            'resolved_at': datetime.utcnow().isoformat(),
            'resolution_note': resolution_note
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resolving escalation: {str(e)}")


@router.post("/recovery/run", response_model=None)
async def run_automated_recovery(
    db: Session = Depends(get_db),
    redis: Optional[redis.Redis] = Depends(get_redis),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Manually trigger automated recovery cycle."""
    try:
        from app.repositories.flow import FlowRepository
        from app.services.data_corruption_detector import DataCorruptionDetector
        from app.services.error_recovery import ErrorRecoveryService
        from app.services.manual_correction import ManualCorrectionService
        from app.services.websocket_events import WebSocketEventService
        
        flow_repo = FlowRepository(db)
        corruption_detector = DataCorruptionDetector(db, redis)
        websocket_service = WebSocketEventService(redis)
        
        monitoring_service = FlowMonitoringService(
            db=db,
            redis=redis,
            flow_repository=flow_repo,
            corruption_detector=corruption_detector
        )
        
        error_recovery_service = ErrorRecoveryService(db, redis)
        manual_correction_service = ManualCorrectionService(db, redis, flow_repo)
        
        recovery_service = AutomatedRecoveryService(
            db=db,
            redis=redis,
            monitoring_service=monitoring_service,
            error_recovery_service=error_recovery_service,
            corruption_detector=corruption_detector,
            manual_correction_service=manual_correction_service,
            flow_repository=flow_repo
        )
        
        recovery_results = await recovery_service.run_automated_recovery_cycle()
        
        return {
            'success': True,
            'message': 'Automated recovery cycle completed',
            'triggered_by': current_user.email,
            'results': recovery_results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running automated recovery: {str(e)}")


@router.get("/health-checks", response_model=None)
async def run_health_checks(
    db: Session = Depends(get_db),
    redis: Optional[redis.Redis] = Depends(get_redis),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Run comprehensive health checks."""
    try:
        from app.repositories.flow import FlowRepository
        from app.services.data_corruption_detector import DataCorruptionDetector
        
        flow_repo = FlowRepository(db)
        corruption_detector = DataCorruptionDetector(db, redis)
        
        monitoring_service = FlowMonitoringService(
            db=db,
            redis=redis,
            flow_repository=flow_repo,
            corruption_detector=corruption_detector
        )
        
        health_checks = await monitoring_service.run_health_checks()
        
        return health_checks
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running health checks: {str(e)}")


@router.post("/escalation-triggers/check", response_model=None)
async def check_escalation_triggers(
    db: Session = Depends(get_db),
    redis: Optional[redis.Redis] = Depends(get_redis),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Manually check for escalation triggers."""
    try:
        from app.repositories.flow import FlowRepository
        from app.services.data_corruption_detector import DataCorruptionDetector
        from app.services.websocket_events import WebSocketEventService
        
        flow_repo = FlowRepository(db)
        corruption_detector = DataCorruptionDetector(db, redis)
        websocket_service = WebSocketEventService(redis)
        
        monitoring_service = FlowMonitoringService(
            db=db,
            redis=redis,
            flow_repository=flow_repo,
            corruption_detector=corruption_detector
        )
        
        escalation_service = CriticalErrorEscalationService(
            db=db,
            redis=redis,
            monitoring_service=monitoring_service,
            websocket_service=websocket_service
        )
        
        triggers = await escalation_service.check_escalation_triggers()
        
        return {
            'triggers_found': len(triggers),
            'triggers': triggers,
            'checked_by': current_user.email,
            'checked_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking escalation triggers: {str(e)}")