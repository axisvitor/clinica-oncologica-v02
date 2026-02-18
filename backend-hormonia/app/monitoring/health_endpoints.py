"""
Health Check Endpoints
FastAPI endpoints for monitoring and health checks.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging

from app.database import get_async_db
from app.monitoring.infrastructure_monitor import infrastructure_monitor
from app.monitoring.service_health_monitor import service_health_monitor
from app.monitoring.capacity_planner import capacity_planner
from app.services.alerts import get_alert_manager, AlertSeverity
from app.config import settings
from app.utils.db_retry import reset_circuit_breaker, db_circuit_breaker
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/monitoring", tags=["monitoring"])


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint
    Returns overall system health status
    """
    try:
        health_summary = await infrastructure_monitor.get_health_summary()

        return {
            "status": "healthy"
            if health_summary["status"] == "healthy"
            else "degraded",
            "timestamp": now_sao_paulo().isoformat(),
            "service": "oncology-platform",
            "version": "1.0.0",
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Health check failed",
        )


@router.get("/health/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_async_db)) -> Dict[str, Any]:
    """
    Detailed health check with all subsystems
    """
    try:
        # Infrastructure health
        infrastructure_health = await infrastructure_monitor.get_health_summary()

        # Service health (V2 API - system is 100% V2)
        api_endpoints = [
            f"{settings.API_V2_STR}/monitoring/health",
            f"{settings.API_V2_STR}/patients",
            f"{settings.API_V2_STR}/quiz-extensions/health",
        ]

        service_results = await service_health_monitor.check_all_services(
            api_endpoints=api_endpoints,
            db_session=db,
            redis_url=str(settings.REDIS_URL)
            if hasattr(settings, "REDIS_URL")
            else None,
        )

        # Alert summary
        _am = get_alert_manager()
        alert_stats = _am.get_alert_statistics()
        alert_summary = {
            "total_alerts": alert_stats.total_alerts,
            "active_alerts": alert_stats.active_alerts,
            "by_severity": {k.value: v for k, v in alert_stats.by_severity.items()},
            "by_status": {k.value: v for k, v in alert_stats.by_status.items()},
        }

        return {
            "status": infrastructure_health["status"],
            "timestamp": now_sao_paulo().isoformat(),
            "infrastructure": {
                "cpu": infrastructure_health["resources"]["cpu"],
                "memory": infrastructure_health["resources"]["memory"],
                "disk": infrastructure_health["resources"]["disk"],
                "trends": infrastructure_health.get("trends", {}),
            },
            "services": {
                name: {
                    "status": result.status.value,
                    "response_time_ms": result.response_time_ms,
                    "last_check": result.checked_at.isoformat(),
                }
                for name, result in service_results.items()
            },
            "alerts": alert_summary,
        }

    except Exception as e:
        logger.error(f"Detailed health check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service health check failed"
        )


@router.get("/metrics/infrastructure")
async def get_infrastructure_metrics() -> Dict[str, Any]:
    """
    Get current infrastructure metrics
    """
    try:
        metrics = await infrastructure_monitor.resource_monitor.collect_metrics()

        return {
            "timestamp": metrics.timestamp.isoformat(),
            "cpu": {
                "percent": metrics.cpu_percent,
                "count": metrics.cpu_count,
                "per_core": metrics.cpu_per_core,
            },
            "memory": {
                "total_mb": metrics.memory_total / 1024 / 1024,
                "used_mb": metrics.memory_used / 1024 / 1024,
                "percent": metrics.memory_percent,
                "available_mb": metrics.memory_available / 1024 / 1024,
            },
            "disk": {
                "total_gb": metrics.disk_total / 1024 / 1024 / 1024,
                "used_gb": metrics.disk_used / 1024 / 1024 / 1024,
                "percent": metrics.disk_percent,
                "io": {
                    "read_bytes": metrics.disk_io_read_bytes,
                    "write_bytes": metrics.disk_io_write_bytes,
                },
            },
            "network": {
                "bytes_sent": metrics.network_bytes_sent,
                "bytes_recv": metrics.network_bytes_recv,
                "packets_sent": metrics.network_packets_sent,
                "packets_recv": metrics.network_packets_recv,
            },
            "status": metrics.status.value,
        }

    except Exception as e:
        logger.error(f"Failed to get infrastructure metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve infrastructure metrics"
        )


@router.get("/metrics/trends")
async def get_resource_trends(minutes: int = 30) -> Dict[str, Any]:
    """
    Get resource usage trends
    """
    try:
        trends = await infrastructure_monitor.resource_monitor.get_trends(minutes)

        return {
            "period_minutes": minutes,
            "timestamp": now_sao_paulo().isoformat(),
            "trends": trends,
        }

    except Exception as e:
        logger.error(f"Failed to get resource trends: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve resource trends"
        )


@router.get("/capacity/forecast")
async def get_capacity_forecast(resource_type: str = "cpu") -> Dict[str, Any]:
    """
    Get capacity forecast for a resource
    """
    try:
        forecast = await capacity_planner.generate_forecast(resource_type)

        if not forecast:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No data available for resource: {resource_type}",
            )

        return {
            "resource_type": forecast.resource_type,
            "current_value": forecast.current_value,
            "forecasts": {
                "1_hour": forecast.forecast_1h,
                "6_hours": forecast.forecast_6h,
                "24_hours": forecast.forecast_24h,
                "7_days": forecast.forecast_7d,
            },
            "trend": forecast.trend.value,
            "confidence_score": forecast.confidence_score,
            "timestamp": forecast.forecast_timestamp.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate forecast: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate capacity forecast"
        )


@router.get("/capacity/analysis")
async def get_capacity_analysis(resource_type: str = "cpu") -> Dict[str, Any]:
    """
    Get capacity analysis and recommendations
    """
    try:
        analysis = await capacity_planner.analyze_capacity(resource_type)

        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No data available for resource: {resource_type}",
            )

        return {
            "resource_type": analysis.resource_type,
            "current_usage": analysis.current_usage,
            "current_capacity": analysis.current_capacity,
            "utilization_percent": analysis.utilization_percent,
            "projected_exhaustion": analysis.projected_exhaustion.isoformat()
            if analysis.projected_exhaustion
            else None,
            "days_until_exhaustion": analysis.days_until_exhaustion,
            "growth_rate_per_day": analysis.growth_rate_per_day,
            "recommendation": analysis.recommendation.value,
            "details": analysis.details,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to analyze capacity: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to analyze capacity"
        )


@router.get("/capacity/report")
async def get_capacity_report() -> Dict[str, Any]:
    """
    Get comprehensive capacity planning report
    """
    try:
        report = await capacity_planner.generate_capacity_report()
        return report

    except Exception as e:
        logger.error(f"Failed to generate capacity report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate capacity report"
        )


@router.get("/alerts")
async def get_alerts(
    severity: Optional[str] = None, status_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get alerts with optional filtering
    """
    try:
        _am = get_alert_manager()
        stats = _am.get_alert_statistics()

        # Build summary dict
        summary = {
            "total_alerts": stats.total_alerts,
            "active_alerts": stats.active_alerts,
            "by_severity": {k.value: v for k, v in stats.by_severity.items()},
            "by_status": {k.value: v for k, v in stats.by_status.items()},
        }

        return {
            "alerts": [],
            "total": stats.total_alerts,
            "summary": summary,
        }

    except Exception as e:
        logger.error(f"Failed to get alerts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve alerts"
        )


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, acknowledged_by: str) -> Dict[str, Any]:
    """
    Acknowledge an alert
    """
    try:
        from uuid import UUID as _UUID

        _am = get_alert_manager()
        alert = await _am.acknowledge_alert(
            alert_id=_UUID(alert_id),
            user_id=_UUID(acknowledged_by),
        )

        return {
            "success": True,
            "alert_id": str(alert.id),
            "acknowledged_by": acknowledged_by,
            "acknowledged_at": now_sao_paulo().isoformat(),
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to acknowledge alert: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to acknowledge alert"
        )


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str, resolved_by: str, resolution_note: Optional[str] = None
) -> Dict[str, Any]:
    """
    Resolve an alert
    """
    try:
        from uuid import UUID as _UUID

        _am = get_alert_manager()
        alert = await _am.resolve_alert(
            alert_id=_UUID(alert_id),
            resolution=resolution_note or "Resolved via monitoring endpoint",
            user_id=_UUID(resolved_by),
        )

        return {
            "success": True,
            "alert_id": str(alert.id),
            "resolved_by": resolved_by,
            "resolved_at": now_sao_paulo().isoformat(),
            "resolution_note": resolution_note,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve alert: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to resolve alert"
        )


@router.get("/services/uptime")
async def get_service_uptime(hours: int = 24) -> Dict[str, Any]:
    """
    Get service uptime report
    """
    try:
        uptime_report = await service_health_monitor.get_uptime_report(hours)

        return {
            "period_hours": hours,
            "timestamp": now_sao_paulo().isoformat(),
            "services": uptime_report,
        }

    except Exception as e:
        logger.error(f"Failed to get uptime report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve uptime report"
        )


@router.get("/services/sla")
async def get_sla_metrics(service_name: str, hours: int = 24) -> Dict[str, Any]:
    """
    Get SLA metrics for a service
    """
    try:
        sla_metrics = await service_health_monitor.calculate_sla_metrics(
            service_name, hours
        )

        if not sla_metrics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No SLA data available for service: {service_name}",
            )

        return {
            "service_name": sla_metrics.service_name,
            "period_hours": hours,
            "availability": {
                "target": sla_metrics.availability_target,
                "current": sla_metrics.current_availability,
                "met": sla_metrics.current_availability
                >= sla_metrics.availability_target,
            },
            "response_time": {
                "target_ms": sla_metrics.response_time_target_ms,
                "current_ms": sla_metrics.current_response_time,
                "met": sla_metrics.current_response_time
                <= sla_metrics.response_time_target_ms,
            },
            "error_rate": {
                "target": sla_metrics.error_rate_target,
                "current": sla_metrics.current_error_rate,
                "met": sla_metrics.current_error_rate <= sla_metrics.error_rate_target,
            },
            "sla_met": sla_metrics.sla_met,
            "period": {
                "start": sla_metrics.period_start.isoformat(),
                "end": sla_metrics.period_end.isoformat(),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get SLA metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve SLA metrics"
        )


@router.post("/circuit-breaker/reset")
async def reset_database_circuit_breaker() -> Dict[str, Any]:
    """
    Emergency endpoint to reset the database circuit breaker.
    Use this when the circuit breaker is stuck in OPEN state.
    """
    try:
        # Get current state before reset
        current_state = db_circuit_breaker.state
        failure_count = db_circuit_breaker.failure_count

        # Reset the circuit breaker
        reset_circuit_breaker()

        logger.info(
            f"Circuit breaker reset from {current_state} state with {failure_count} failures"
        )

        return {
            "success": True,
            "message": "Database circuit breaker has been reset",
            "previous_state": current_state,
            "previous_failure_count": failure_count,
            "current_state": "closed",
            "timestamp": now_sao_paulo().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to reset circuit breaker: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to reset circuit breaker"
        )


@router.get("/circuit-breaker/status")
async def get_circuit_breaker_status() -> Dict[str, Any]:
    """
    Get current status of the database circuit breaker.
    """
    try:
        return {
            "state": db_circuit_breaker.state,
            "failure_count": db_circuit_breaker.failure_count,
            "failure_threshold": db_circuit_breaker.failure_threshold,
            "recovery_timeout": db_circuit_breaker.recovery_timeout,
            "last_failure_time": db_circuit_breaker.last_failure_time,
            "is_healthy": db_circuit_breaker.state == "closed",
            "timestamp": now_sao_paulo().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get circuit breaker status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to get circuit breaker status"
        )
