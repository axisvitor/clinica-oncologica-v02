"""
Production Health Check Endpoints
Simple health checks for Railway deployment
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
import psutil
import os
import logging

from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/health")
async def health_check():
    """Basic health check endpoint for Railway"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "service": "clinica-oncologica-api",
        "environment": os.getenv("ENVIRONMENT", "development")
    }

@router.get("/readiness")
async def readiness_check(db: Session = Depends(get_db)):
    """Readiness probe for Railway"""
    try:
        # Check database connectivity
        db.execute("SELECT 1")

        return {
            "status": "ready",
            "timestamp": datetime.now().isoformat(),
            "checks": {
                "database": "healthy"
            }
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@router.get("/liveness")
async def liveness_check():
    """Liveness probe for Railway"""
    try:
        # Basic system checks
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()

        return {
            "status": "alive",
            "timestamp": datetime.now().isoformat(),
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_mb": memory.available // (1024 * 1024)
            }
        }
    except Exception as e:
        logger.error(f"Liveness check failed: {e}")
        return JSONResponse(
            status_code=200,  # Always return 200 for liveness unless completely broken
            content={
                "status": "alive",
                "timestamp": datetime.now().isoformat(),
                "warning": str(e)
            }
        )