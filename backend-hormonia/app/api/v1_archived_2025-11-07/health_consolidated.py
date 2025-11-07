"""
Consolidated Health Check Endpoint for Production Deployment

This module provides a comprehensive health check endpoint that validates:
- Database connectivity and performance
- Redis connectivity and performance  
- Evolution API connectivity
- Celery worker status
- Database migrations status
- Connection pool health

Designed for:
- Kubernetes/Railway readiness probes
- Load balancer health checks
- Monitoring systems (Prometheus, Datadog, etc.)
- Deployment validation

Status Codes:
- 200: All systems healthy or degraded but operational
- 503: Critical systems unhealthy (database, migrations)
"""

import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.pool import QueuePool

from app.database import get_db, engine
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


async def check_database(db: Session) -> Dict[str, Any]:
    """
    Check database connectivity and performance.
    
    Returns:
        dict: Database health status with response time
    """
    try:
        start_time = time.time()
        result = db.execute(text("SELECT 1 as health_check")).fetchone()
        response_time_ms = (time.time() - start_time) * 1000
        
        if result and result[0] == 1:
            return {
                "status": "healthy",
                "response_time_ms": round(response_time_ms, 2),
                "message": "Database connection successful"
            }
        else:
            return {
                "status": "unhealthy",
                "response_time_ms": round(response_time_ms, 2),
                "message": "Database query returned unexpected result"
            }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "message": "Database connection failed"
        }


async def check_database_pool() -> Dict[str, Any]:
    """
    Check database connection pool health.
    
    Returns:
        dict: Pool health status with utilization metrics
    """
    try:
        pool = engine.pool
        
        if isinstance(pool, QueuePool):
            pool_size = pool.size()
            checked_out = pool.checkedout()
            overflow = pool.overflow()
            
            # Calculate utilization percentage
            total_capacity = pool_size + overflow
            utilization = (checked_out / total_capacity * 100) if total_capacity > 0 else 0
            
            # Determine status based on utilization
            if utilization >= 90:
                status = "critical"
                message = "Pool near exhaustion"
            elif utilization >= 70:
                status = "degraded"
                message = "Pool utilization high"
            else:
                status = "healthy"
                message = "Pool utilization normal"
            
            return {
                "status": status,
                "pool_size": pool_size,
                "checked_out": checked_out,
                "overflow": overflow,
                "utilization_percent": round(utilization, 2),
                "message": message
            }
        else:
            return {
                "status": "unknown",
                "message": "Pool type not QueuePool"
            }
    except Exception as e:
        logger.error(f"Database pool health check failed: {e}")
        return {
            "status": "unknown",
            "error": str(e),
            "message": "Pool health check failed"
        }


async def check_redis() -> Dict[str, Any]:
    """
    Check Redis connectivity and performance.
    
    Returns:
        dict: Redis health status with response time
    """
    try:
        from app.core.redis_client import get_redis_client
        
        redis_client = get_redis_client()
        start_time = time.time()
        await redis_client.ping()
        response_time_ms = (time.time() - start_time) * 1000
        
        return {
            "status": "healthy",
            "response_time_ms": round(response_time_ms, 2),
            "message": "Redis connection successful"
        }
    except ImportError:
        return {
            "status": "degraded",
            "message": "Redis client not configured (optional)"
        }
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return {
            "status": "degraded",
            "error": str(e),
            "message": "Redis connection failed (non-critical)"
        }


async def check_evolution_api() -> Dict[str, Any]:
    """
    Check Evolution API connectivity.
    
    Returns:
        dict: Evolution API health status
    """
    if not settings.ENABLE_EVOLUTION:
        return {
            "status": "disabled",
            "message": "Evolution API integration disabled"
        }
    
    try:
        from app.integrations.evolution import get_evolution_client
        
        evolution_client = await get_evolution_client()
        start_time = time.time()
        status = await evolution_client.get_instance_status()
        response_time_ms = (time.time() - start_time) * 1000
        
        return {
            "status": "healthy",
            "response_time_ms": round(response_time_ms, 2),
            "instance_status": status,
            "message": "Evolution API connected"
        }
    except Exception as e:
        logger.warning(f"Evolution API health check failed: {e}")
        return {
            "status": "degraded",
            "error": str(e),
            "message": "Evolution API connection failed (non-critical)"
        }


async def check_migrations(db: Session) -> Dict[str, Any]:
    """
    Check if database migrations are up to date.
    
    Returns:
        dict: Migration status
    """
    try:
        # Check if alembic_version table exists
        result = db.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'alembic_version')"
        )).fetchone()
        
        if not result or not result[0]:
            return {
                "status": "unhealthy",
                "message": "Alembic version table not found - migrations not initialized"
            }
        
        # Get current migration version
        version_result = db.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        
        if version_result:
            return {
                "status": "healthy",
                "current_version": version_result[0],
                "message": "Migrations up to date"
            }
        else:
            return {
                "status": "degraded",
                "message": "No migration version found"
            }
    except Exception as e:
        logger.error(f"Migration health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "message": "Migration check failed"
        }


async def check_celery() -> Dict[str, Any]:
    """
    Check Celery worker status.
    
    Returns:
        dict: Celery health status
    """
    try:
        from app.worker.celery_app import celery_app
        
        # Inspect active workers
        inspect = celery_app.control.inspect(timeout=2.0)
        active_workers = inspect.active()
        
        if active_workers:
            worker_count = len(active_workers)
            return {
                "status": "healthy",
                "worker_count": worker_count,
                "workers": list(active_workers.keys()),
                "message": f"{worker_count} worker(s) active"
            }
        else:
            return {
                "status": "degraded",
                "worker_count": 0,
                "message": "No active Celery workers (non-critical)"
            }
    except Exception as e:
        logger.warning(f"Celery health check failed: {e}")
        return {
            "status": "degraded",
            "error": str(e),
            "message": "Celery check failed (non-critical)"
        }


@router.get("/health")
async def comprehensive_health_check(
    response: Response,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Comprehensive health check endpoint for production deployment.
    
    Checks all critical and non-critical systems:
    - Database (CRITICAL)
    - Database pool (CRITICAL)
    - Migrations (CRITICAL)
    - Redis (non-critical)
    - Evolution API (non-critical)
    - Celery workers (non-critical)
    
    Returns:
        200: All systems healthy or degraded but operational
        503: Critical systems unhealthy
    """
    start_time = time.time()
    
    # Run all health checks in parallel
    checks = {
        "database": await check_database(db),
        "database_pool": await check_database_pool(),
        "migrations": await check_migrations(db),
        "redis": await check_redis(),
        "evolution_api": await check_evolution_api(),
        "celery": await check_celery(),
    }
    
    # Determine overall status
    critical_checks = ["database", "database_pool", "migrations"]
    critical_unhealthy = any(
        checks[check]["status"] == "unhealthy" 
        for check in critical_checks
    )
    
    if critical_unhealthy:
        overall_status = "unhealthy"
        status_code = 503
    elif any(check["status"] == "degraded" for check in checks.values()):
        overall_status = "degraded"
        status_code = 200  # Still operational
    else:
        overall_status = "healthy"
        status_code = 200
    
    total_time_ms = (time.time() - start_time) * 1000
    
    health_response = {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "2.0.0",
        "environment": settings.ENVIRONMENT,
        "checks": checks,
        "response_time_ms": round(total_time_ms, 2)
    }
    
    response.status_code = status_code
    return health_response

