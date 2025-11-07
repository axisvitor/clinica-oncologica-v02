"""
Comprehensive Health Check and Performance Monitoring Endpoints
Enhanced health checks for production Railway deployment with detailed metrics
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
import psutil
import os
import logging
import time
from typing import Dict, Any, Optional

from app.database import get_db
from app.models.user import User
from app.models.patient import Patient
from app.models.message import Message
from app.models.alert import Alert

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request, db: Session = Depends(get_db)):
    """Comprehensive health check endpoint for Railway with detailed system status"""
    start_time = time.time()

    health_data = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.1.0",
        "service": "clinica-oncologica-api",
        "environment": os.getenv("ENVIRONMENT", "production"),
        "checks": {},
        "performance": {},
        "system": {}
    }

    # Database health check
    try:
        db_start = time.time()
        result = db.execute(text("SELECT 1 as health_check")).fetchone()
        db_time = (time.time() - db_start) * 1000

        health_data["checks"]["database"] = {
            "status": "healthy" if result and result[0] == 1 else "unhealthy",
            "response_time_ms": round(db_time, 2),
            "connection_pool_size": getattr(db.bind.pool, "size", "unknown"),
            "checked_out_connections": getattr(db.bind.pool, "checkedout", "unknown")
        }
    except Exception as e:
        health_data["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e),
            "response_time_ms": None
        }
        health_data["status"] = "degraded"

    # System metrics
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        health_data["system"] = {
            "cpu_percent": round(cpu_percent, 2),
            "memory_percent": round(memory.percent, 2),
            "memory_available_mb": round(memory.available / 1024 / 1024, 2),
            "memory_used_mb": round(memory.used / 1024 / 1024, 2),
            "disk_usage_percent": round(disk.percent, 2),
            "disk_free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
            "uptime_seconds": int(time.time() - psutil.boot_time())
        }

        # Alert if resources are high
        if cpu_percent > 80 or memory.percent > 85:
            health_data["status"] = "degraded"
        if cpu_percent > 95 or memory.percent > 95:
            health_data["status"] = "unhealthy"

    except Exception as e:
        health_data["system"] = {"error": str(e)}

    # Performance metrics
    total_time = (time.time() - start_time) * 1000
    health_data["performance"] = {
        "total_response_time_ms": round(total_time, 2),
        "request_id": getattr(request.state, "request_id", "unknown")
    }

    # Determine final status
    if health_data["status"] == "healthy":
        status_code = 200
    elif health_data["status"] == "degraded":
        status_code = 200  # Still operational
    else:
        status_code = 503  # Service unavailable

    return JSONResponse(content=health_data, status_code=status_code)


@router.get("/metrics")
async def metrics_endpoint(db: Session = Depends(get_db)):
    """Performance metrics endpoint for monitoring and observability"""
    try:
        start_time = time.time()
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "database": {},
            "application": {},
            "system": {}
        }

        # Database metrics
        try:
            # Basic counts
            user_count = db.query(User).count()
            patient_count = db.query(Patient).count()
            message_count_24h = db.query(Message).filter(
                Message.created_at >= datetime.utcnow() - timedelta(hours=24)
            ).count()
            alert_count_24h = db.query(Alert).filter(
                Alert.created_at >= datetime.utcnow() - timedelta(hours=24)
            ).count()

            # Database performance
            db_start = time.time()
            db.execute(text("SELECT 1"))
            db_response_time = (time.time() - db_start) * 1000

            metrics["database"] = {
                "response_time_ms": round(db_response_time, 2),
                "user_count": user_count,
                "patient_count": patient_count,
                "messages_last_24h": message_count_24h,
                "alerts_last_24h": alert_count_24h,
                "connection_pool_size": getattr(db.bind.pool, "size", "unknown"),
                "active_connections": getattr(db.bind.pool, "checkedout", "unknown")
            }

        except Exception as e:
            metrics["database"] = {"error": str(e)}

        # System metrics
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            network = psutil.net_io_counters()

            metrics["system"] = {
                "cpu_percent": round(cpu_percent, 2),
                "memory_percent": round(memory.percent, 2),
                "memory_used_mb": round(memory.used / 1024 / 1024, 2),
                "memory_available_mb": round(memory.available / 1024 / 1024, 2),
                "disk_usage_percent": round(disk.percent, 2),
                "disk_free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "network_bytes_sent": network.bytes_sent if network else 0,
                "network_bytes_recv": network.bytes_recv if network else 0,
                "process_count": len(psutil.pids()),
                "uptime_hours": round((time.time() - psutil.boot_time()) / 3600, 2)
            }

        except Exception as e:
            metrics["system"] = {"error": str(e)}

        # Application metrics
        total_time = (time.time() - start_time) * 1000
        metrics["application"] = {
            "response_time_ms": round(total_time, 2),
            "environment": os.getenv("ENVIRONMENT", "unknown"),
            "version": "2.1.0",
            "python_version": os.sys.version.split()[0],
            "pid": os.getpid(),
            "worker_id": os.getenv("WORKER_ID", "unknown")
        }

        return metrics

    except Exception as e:
        logger.error(f"Metrics endpoint failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to generate metrics",
                "details": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
