"""
Enhanced Monitoring API Endpoints.

Comprehensive monitoring endpoints for APM, database performance,
resource monitoring, business metrics, and real-time dashboard.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, status
from fastapi.responses import PlainTextResponse

from app.dependencies import get_current_user
from app.models.user import User
from app.monitoring.manager import get_monitoring_manager
from app.monitoring.config import get_monitoring_config


router = APIRouter()


@router.get("/monitoring/health")
async def get_monitoring_health():
    """Get monitoring system health status."""
    manager = get_monitoring_manager()
    return manager.get_health_status()


@router.get("/monitoring/metrics/overview")
async def get_metrics_overview(current_user: User = Depends(get_current_user)):
    """Get comprehensive metrics overview."""
    manager = get_monitoring_manager()
    return await manager.get_system_metrics()


# APM Endpoints
@router.get("/monitoring/apm/global")
async def get_apm_global_stats(current_user: User = Depends(get_current_user)):
    """Get global APM statistics."""
    manager = get_monitoring_manager()
    if not manager.apm_collector:
        raise HTTPException(status_code=503, detail="APM collector not available")

    return manager.apm_collector.get_global_stats()


@router.get("/monitoring/apm/endpoints")
async def get_apm_endpoints_stats(current_user: User = Depends(get_current_user)):
    """Get statistics for all endpoints."""
    manager = get_monitoring_manager()
    if not manager.apm_collector:
        raise HTTPException(status_code=503, detail="APM collector not available")

    return manager.apm_collector.get_all_endpoints_stats()


@router.get("/monitoring/apm/endpoint/{endpoint_path:path}")
async def get_apm_endpoint_stats(
    endpoint_path: str,
    current_user: User = Depends(get_current_user)
):
    """Get statistics for a specific endpoint."""
    manager = get_monitoring_manager()
    if not manager.apm_collector:
        raise HTTPException(status_code=503, detail="APM collector not available")

    return manager.apm_collector.get_endpoint_stats(endpoint_path)


# Database Monitoring Endpoints
@router.get("/monitoring/database/overview")
async def get_database_overview(current_user: User = Depends(get_current_user)):
    """Get database performance overview."""
    manager = get_monitoring_manager()
    if not manager.db_monitor:
        raise HTTPException(status_code=503, detail="Database monitor not available")

    query_stats = manager.db_monitor.get_query_stats()
    pool_stats = manager.db_monitor.get_connection_pool_stats()

    return {
        "query_statistics": query_stats,
        "connection_pool": pool_stats,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/monitoring/database/slow-queries")
async def get_slow_queries(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user)
):
    """Get slowest database queries."""
    manager = get_monitoring_manager()
    if not manager.db_monitor:
        raise HTTPException(status_code=503, detail="Database monitor not available")

    return {
        "slow_queries": manager.db_monitor.get_slow_queries(limit),
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/monitoring/database/tables")
async def get_table_stats(current_user: User = Depends(get_current_user)):
    """Get statistics by database table."""
    manager = get_monitoring_manager()
    if not manager.db_monitor:
        raise HTTPException(status_code=503, detail="Database monitor not available")

    return {
        "table_statistics": manager.db_monitor.get_table_stats(),
        "timestamp": datetime.utcnow().isoformat()
    }


# Resource Monitoring Endpoints
@router.get("/monitoring/resources/current")
async def get_current_resources(current_user: User = Depends(get_current_user)):
    """Get current resource usage."""
    manager = get_monitoring_manager()
    if not manager.resource_monitor:
        raise HTTPException(status_code=503, detail="Resource monitor not available")

    return manager.resource_monitor.get_current_stats()


@router.get("/monitoring/resources/historical")
async def get_historical_resources(
    minutes: int = Query(default=60, ge=1, le=1440),
    current_user: User = Depends(get_current_user)
):
    """Get historical resource usage."""
    manager = get_monitoring_manager()
    if not manager.resource_monitor:
        raise HTTPException(status_code=503, detail="Resource monitor not available")

    return manager.resource_monitor.get_historical_stats(minutes)


@router.get("/monitoring/resources/system-info")
async def get_system_info(current_user: User = Depends(get_current_user)):
    """Get static system information."""
    manager = get_monitoring_manager()
    if not manager.resource_monitor:
        raise HTTPException(status_code=503, detail="Resource monitor not available")

    return manager.resource_monitor.get_system_info()


# Business Metrics Endpoints
@router.get("/monitoring/business/summary")
async def get_business_metrics_summary(
    hours: int = Query(default=24, ge=1, le=168),
    current_user: User = Depends(get_current_user)
):
    """Get business metrics summary."""
    manager = get_monitoring_manager()
    if not manager.business_metrics:
        raise HTTPException(status_code=503, detail="Business metrics collector not available")

    return manager.business_metrics.get_all_metrics_summary(hours)


@router.get("/monitoring/business/patient/{patient_id}")
async def get_patient_metrics(
    patient_id: str,
    hours: int = Query(default=24, ge=1, le=168),
    current_user: User = Depends(get_current_user)
):
    """Get metrics for a specific patient."""
    manager = get_monitoring_manager()
    if not manager.business_metrics:
        raise HTTPException(status_code=503, detail="Business metrics collector not available")

    return manager.business_metrics.get_patient_metrics(patient_id, hours)


@router.get("/monitoring/business/metric/{metric_type}")
async def get_business_metric_stats(
    metric_type: str,
    hours: int = Query(default=24, ge=1, le=168),
    current_user: User = Depends(get_current_user)
):
    """Get statistics for a specific business metric type."""
    from app.monitoring.business_metrics import MetricType

    manager = get_monitoring_manager()
    if not manager.business_metrics:
        raise HTTPException(status_code=503, detail="Business metrics collector not available")

    try:
        metric_enum = MetricType(metric_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric type. Valid types: {[m.value for m in MetricType]}"
        )

    return manager.business_metrics.get_metric_stats(metric_enum, hours)


# Anomaly Detection Endpoints
@router.get("/monitoring/anomalies/recent")
async def get_recent_anomalies(
    hours: int = Query(default=24, ge=1, le=168),
    severity: Optional[str] = Query(default=None),
    metric: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user)
):
    """Get recent anomalies with optional filtering."""
    manager = get_monitoring_manager()
    if not manager.anomaly_detector:
        raise HTTPException(status_code=503, detail="Anomaly detector not available")

    return {
        "anomalies": manager.anomaly_detector.get_recent_anomalies(
            hours, severity, metric
        ),
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/monitoring/anomalies/summary")
async def get_anomalies_summary(
    hours: int = Query(default=24, ge=1, le=168),
    current_user: User = Depends(get_current_user)
):
    """Get anomalies summary."""
    manager = get_monitoring_manager()
    if not manager.anomaly_detector:
        raise HTTPException(status_code=503, detail="Anomaly detector not available")

    return manager.anomaly_detector.get_anomaly_summary(hours)


# Dashboard Endpoints
@router.get("/monitoring/dashboard/status")
async def get_dashboard_status(current_user: User = Depends(get_current_user)):
    """Get dashboard status."""
    manager = get_monitoring_manager()
    if not manager.dashboard:
        raise HTTPException(status_code=503, detail="Dashboard not available")

    return manager.dashboard.get_dashboard_status()


@router.websocket("/monitoring/dashboard/stream")
async def dashboard_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard updates."""
    manager = get_monitoring_manager()
    if not manager.dashboard:
        await websocket.close(code=1003, reason="Dashboard not available")
        return

    client_id = f"dashboard_{int(datetime.utcnow().timestamp() * 1000000)}"
    await manager.dashboard.handle_websocket_connection(websocket, client_id)


# Metrics Export Endpoints
@router.get("/monitoring/export/prometheus", response_class=PlainTextResponse)
async def get_prometheus_metrics():
    """Get metrics in Prometheus format."""
    manager = get_monitoring_manager()
    if not manager.metrics_exporter:
        raise HTTPException(status_code=503, detail="Metrics exporter not available")

    return manager.metrics_exporter.get_prometheus_metrics()


@router.post("/monitoring/export/grafana/query")
async def query_grafana_metrics(
    request_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Query metrics for Grafana."""
    manager = get_monitoring_manager()
    if not manager.metrics_exporter:
        raise HTTPException(status_code=503, detail="Metrics exporter not available")

    targets = request_data.get("targets", [])
    from_time = datetime.fromisoformat(request_data.get("from", datetime.utcnow().isoformat()))
    to_time = datetime.fromisoformat(request_data.get("to", datetime.utcnow().isoformat()))
    max_data_points = request_data.get("maxDataPoints", 1000)

    return await manager.metrics_exporter.query_grafana_metrics(
        targets, from_time, to_time, max_data_points
    )


# Configuration and Management Endpoints
@router.get("/monitoring/config")
async def get_monitoring_config_endpoint(current_user: User = Depends(get_current_user)):
    """Get monitoring configuration."""
    config = get_monitoring_config()
    return config.dict()


@router.post("/monitoring/actions/reset-stats")
async def reset_monitoring_stats(current_user: User = Depends(get_current_user)):
    """Reset all monitoring statistics."""
    manager = get_monitoring_manager()
    await manager.reset_all_stats()

    return {
        "message": "All monitoring statistics have been reset",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/monitoring/actions/start")
async def start_monitoring_services(current_user: User = Depends(get_current_user)):
    """Start monitoring services."""
    manager = get_monitoring_manager()

    if manager._started:
        return {
            "message": "Monitoring services are already running",
            "timestamp": datetime.utcnow().isoformat()
        }

    await manager.start()

    return {
        "message": "Monitoring services started successfully",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/monitoring/actions/stop")
async def stop_monitoring_services(current_user: User = Depends(get_current_user)):
    """Stop monitoring services."""
    manager = get_monitoring_manager()

    if not manager._started:
        return {
            "message": "Monitoring services are not running",
            "timestamp": datetime.utcnow().isoformat()
        }

    await manager.stop()

    return {
        "message": "Monitoring services stopped successfully",
        "timestamp": datetime.utcnow().isoformat()
    }


# Alert Endpoints
@router.get("/monitoring/alerts/active")
async def get_active_alerts(current_user: User = Depends(get_current_user)):
    """Get currently active monitoring alerts."""
    manager = get_monitoring_manager()

    # Collect alerts from various sources
    alerts = []

    # APM alerts
    if manager.apm_collector:
        apm_stats = manager.apm_collector.get_global_stats()
        if apm_stats.get("error_rate", 0) > 5:
            alerts.append({
                "type": "apm",
                "severity": "high" if apm_stats["error_rate"] > 10 else "medium",
                "message": f"High error rate: {apm_stats['error_rate']:.1f}%",
                "value": apm_stats["error_rate"],
                "threshold": 5.0,
                "timestamp": datetime.utcnow().isoformat()
            })

    # Resource alerts
    if manager.resource_monitor:
        resource_stats = manager.resource_monitor.get_current_stats()
        cpu_percent = resource_stats.get("cpu", {}).get("percent", 0)
        memory_percent = resource_stats.get("memory", {}).get("percent", 0)

        if cpu_percent > 80:
            alerts.append({
                "type": "resource",
                "severity": "critical" if cpu_percent > 95 else "high",
                "message": f"High CPU usage: {cpu_percent:.1f}%",
                "value": cpu_percent,
                "threshold": 80.0,
                "timestamp": datetime.utcnow().isoformat()
            })

        if memory_percent > 85:
            alerts.append({
                "type": "resource",
                "severity": "critical" if memory_percent > 95 else "high",
                "message": f"High memory usage: {memory_percent:.1f}%",
                "value": memory_percent,
                "threshold": 85.0,
                "timestamp": datetime.utcnow().isoformat()
            })

    return {
        "alerts": alerts,
        "count": len(alerts),
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/monitoring/performance/overview")
async def get_performance_overview_enhanced(current_user: User = Depends(get_current_user)):
    """Get enhanced performance overview with monitoring data."""
    manager = get_monitoring_manager()

    overview = {
        "timestamp": datetime.utcnow().isoformat(),
        "system_health": manager.get_health_status(),
        "performance_score": 100
    }

    # Calculate performance score
    score_deductions = []

    # APM performance
    if manager.apm_collector:
        apm_stats = manager.apm_collector.get_global_stats()
        overview["apm"] = apm_stats

        if apm_stats.get("error_rate", 0) > 5:
            deduction = min(20, apm_stats["error_rate"] * 2)
            overview["performance_score"] -= deduction
            score_deductions.append(f"High error rate: -{deduction:.0f}")

        if apm_stats.get("p95", 0) > 2000:  # 2 seconds
            deduction = min(15, (apm_stats["p95"] - 2000) / 100)
            overview["performance_score"] -= deduction
            score_deductions.append(f"Slow response time: -{deduction:.0f}")

    # Database performance
    if manager.db_monitor:
        db_stats = manager.db_monitor.get_query_stats()
        pool_stats = manager.db_monitor.get_connection_pool_stats()
        overview["database"] = {"query_stats": db_stats, "pool_stats": pool_stats}

        if db_stats.get("slow_query_percentage", 0) > 10:
            deduction = min(15, db_stats["slow_query_percentage"])
            overview["performance_score"] -= deduction
            score_deductions.append(f"Slow queries: -{deduction:.0f}")

    # Resource performance
    if manager.resource_monitor:
        resource_stats = manager.resource_monitor.get_current_stats()
        overview["resources"] = resource_stats

        cpu_percent = resource_stats.get("cpu", {}).get("percent", 0)
        memory_percent = resource_stats.get("memory", {}).get("percent", 0)

        if cpu_percent > 80:
            deduction = min(15, (cpu_percent - 80) / 2)
            overview["performance_score"] -= deduction
            score_deductions.append(f"High CPU: -{deduction:.0f}")

        if memory_percent > 85:
            deduction = min(15, (memory_percent - 85) / 2)
            overview["performance_score"] -= deduction
            score_deductions.append(f"High memory: -{deduction:.0f}")

    overview["performance_score"] = max(0, overview["performance_score"])
    overview["score_deductions"] = score_deductions

    # Performance status
    if overview["performance_score"] >= 90:
        overview["status"] = "excellent"
    elif overview["performance_score"] >= 75:
        overview["status"] = "good"
    elif overview["performance_score"] >= 60:
        overview["status"] = "degraded"
    else:
        overview["status"] = "critical"

    return overview