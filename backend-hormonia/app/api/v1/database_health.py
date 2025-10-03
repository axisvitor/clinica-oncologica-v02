"""
Database health check and monitoring endpoints.

Provides comprehensive database health monitoring for load balancers,
connection pool status tracking, and performance metrics collection.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db, test_connection, get_pool_status, is_pool_healthy, connection_manager
from typing import Dict, Any
import time
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/database/health", response_model=Dict[str, Any])
async def database_health_check():
    """
    Comprehensive database health check for load balancers.

    Returns 200 if healthy, 503 if unhealthy.

    Checks:
    - Main connection (service role)
    - RLS connection
    - Connection pool status
    - Pool utilization

    Returns:
        Health status with connection details and pool metrics
    """
    start_time = time.time()

    try:
        # Test main connection (service role)
        main_health = test_connection(use_service_role=True)
        main_healthy = main_health.get("status") == "healthy"

        # Test RLS connection
        rls_health = test_connection(use_service_role=False)
        rls_healthy = rls_health.get("status") == "healthy"

        # Get pool status for both engines
        main_pool = get_pool_status(use_service_role=True)
        rls_pool = get_pool_status(use_service_role=False)

        # Calculate pool utilization percentages
        main_total_capacity = main_pool.get("pool_size", 0) + main_pool.get("overflow", 0)
        main_pool_utilization = (main_pool.get("checked_out", 0) / main_total_capacity * 100) if main_total_capacity > 0 else 0

        rls_total_capacity = rls_pool.get("pool_size", 0) + rls_pool.get("overflow", 0)
        rls_pool_utilization = (rls_pool.get("checked_out", 0) / rls_total_capacity * 100) if rls_total_capacity > 0 else 0

        # Determine overall health
        is_healthy = (
            main_healthy and
            rls_healthy and
            main_pool_utilization < 90 and
            rls_pool_utilization < 90
        )

        response_time = (time.time() - start_time) * 1000

        result = {
            "status": "healthy" if is_healthy else "degraded",
            "main_connection": {
                "status": "ok" if main_healthy else "failed",
                "details": main_health
            },
            "rls_connection": {
                "status": "ok" if rls_healthy else "failed",
                "details": rls_health
            },
            "pool_status": {
                "main": {
                    **main_pool,
                    "utilization_percent": round(main_pool_utilization, 2),
                    "healthy": main_pool_utilization < 90
                },
                "rls": {
                    **rls_pool,
                    "utilization_percent": round(rls_pool_utilization, 2),
                    "healthy": rls_pool_utilization < 90
                }
            },
            "response_time_ms": round(response_time, 2),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        if not is_healthy:
            logger.warning(f"Database health check degraded: {result}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=result
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database health check error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unhealthy",
                "error": str(e),
                "error_type": type(e).__name__,
                "response_time_ms": round((time.time() - start_time) * 1000, 2),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


@router.get("/database/pool-status", response_model=Dict[str, Any])
async def get_connection_pool_status():
    """
    Get detailed connection pool metrics for both engines.

    Returns:
        Detailed pool statistics for service role and RLS connections
    """
    try:
        main_pool = get_pool_status(use_service_role=True)
        rls_pool = get_pool_status(use_service_role=False)

        # Calculate additional metrics
        main_total = main_pool.get("pool_size", 0) + main_pool.get("overflow", 0)
        main_available = main_pool.get("checked_in", 0)
        main_utilization = (main_pool.get("checked_out", 0) / main_total * 100) if main_total > 0 else 0

        rls_total = rls_pool.get("pool_size", 0) + rls_pool.get("overflow", 0)
        rls_available = rls_pool.get("checked_in", 0)
        rls_utilization = (rls_pool.get("checked_out", 0) / rls_total * 100) if rls_total > 0 else 0

        return {
            "main_pool": {
                **main_pool,
                "total_capacity": main_total,
                "available_connections": main_available,
                "utilization_percent": round(main_utilization, 2),
                "health_status": "healthy" if main_utilization < 90 else "critical"
            },
            "rls_pool": {
                **rls_pool,
                "total_capacity": rls_total,
                "available_connections": rls_available,
                "utilization_percent": round(rls_utilization, 2),
                "health_status": "healthy" if rls_utilization < 90 else "critical"
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting pool status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to retrieve pool status",
                "details": str(e)
            }
        )


@router.get("/database/metrics", response_model=Dict[str, Any])
async def get_database_metrics():
    """
    Get database performance metrics for monitoring systems (Prometheus, etc.).

    Returns:
        Comprehensive database metrics including:
        - Connection pool statistics
        - Query performance metrics
        - Health indicators
    """
    try:
        # Import here to avoid circular dependencies
        from app.services.monitoring.database_monitor import DatabasePerformanceMonitor

        monitor = DatabasePerformanceMonitor()
        metrics = monitor.get_metrics()

        return {
            **metrics,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except ImportError:
        # Fallback if monitoring service not available
        logger.warning("DatabasePerformanceMonitor not available, returning basic metrics")
        return {
            "pool_status": {
                "main": get_pool_status(use_service_role=True),
                "rls": get_pool_status(use_service_role=False)
            },
            "health_checks": {
                "main": is_pool_healthy(use_service_role=True),
                "rls": is_pool_healthy(use_service_role=False)
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting database metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to retrieve database metrics",
                "details": str(e)
            }
        )


@router.get("/database/connection-test", response_model=Dict[str, Any])
async def test_database_connection(use_service_role: bool = True):
    """
    Test database connection with detailed diagnostics.

    Args:
        use_service_role: Test service role (True) or RLS (False) connection

    Returns:
        Connection test results with timing and context information
    """
    start_time = time.time()

    try:
        result = test_connection(use_service_role=use_service_role)
        response_time = (time.time() - start_time) * 1000

        return {
            **result,
            "test_duration_ms": round(response_time, 2),
            "connection_type": "service_role" if use_service_role else "rls_context"
        }
    except Exception as e:
        logger.error(f"Connection test failed: {e}", exc_info=True)
        return {
            "status": "failed",
            "error": str(e),
            "error_type": type(e).__name__,
            "test_duration_ms": round((time.time() - start_time) * 1000, 2),
            "connection_type": "service_role" if use_service_role else "rls_context",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }