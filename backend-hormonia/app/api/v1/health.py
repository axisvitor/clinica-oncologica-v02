"""
Health monitoring API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any

from app.utils.health_monitoring import check_system_health, get_health_metrics
from app.utils.error_tracking import get_error_summary, clear_old_errors
from app.utils.logging import get_logger
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health", response_model=None)
async def basic_health_check() -> dict[str, Any]:
    """
    Basic health check endpoint.
    
    Returns a simple health status without detailed metrics.
    This endpoint is typically used by load balancers and monitoring systems.
    """
    return {
        "status": "healthy",
        "service": "hormonia-backend",
        "message": "Service is operational"
    }


@router.get("/health/detailed", response_model=None)
async def detailed_health_check() -> dict[str, Any]:
    """
    Detailed health check with comprehensive system metrics.
    
    Performs checks on:
    - System resources (CPU, memory, disk)
    - Database connectivity and performance
    - Redis connectivity and performance
    - External service connectivity
    - Application error rates
    
    Returns detailed metrics and component status.
    """
    try:
        health_data = await check_system_health()
        
        # Log health check request
        logger.info(
            "Detailed health check requested",
            extra={
                'event_type': 'health_check_request',
                'overall_status': health_data.get('status'),
                'components_checked': len(health_data.get('components', {}))
            }
        )
        
        return health_data
        
    except Exception as e:
        logger.error(
            f"Detailed health check failed: {str(e)}",
            extra={'event_type': 'health_check_error'},
            exc_info=True
        )
        
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Health check service unavailable"
        )


@router.get("/health/metrics", response_model=None)
async def get_system_metrics(current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """
    Get system metrics summary.
    
    Requires authentication. Returns collected metrics from the last health check.
    """
    try:
        metrics = get_health_metrics()
        
        logger.info(
            "System metrics requested",
            extra={
                'event_type': 'metrics_request',
                'user_id': str(current_user.id),
                'total_metrics': metrics.get('total_metrics', 0)
            }
        )
        
        return metrics
        
    except Exception as e:
        logger.error(
            f"Failed to get system metrics: {str(e)}",
            extra={'event_type': 'metrics_error', 'user_id': str(current_user.id)},
            exc_info=True
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system metrics"
        )


@router.get("/health/errors", response_model=None)
async def get_error_metrics(
    hours: int = 24,
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """
    Get error metrics and summary.
    
    Args:
        hours: Number of hours to look back for errors (default: 24)
    
    Returns error summary including counts, types, and recent occurrences.
    """
    try:
        if hours < 1 or hours > 168:  # Max 1 week
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hours parameter must be between 1 and 168"
            )
        
        error_summary = get_error_summary(hours=hours)
        
        logger.info(
            f"Error metrics requested for {hours} hours",
            extra={
                'event_type': 'error_metrics_request',
                'user_id': str(current_user.id),
                'hours': hours,
                'total_errors': error_summary.get('total_errors', 0)
            }
        )
        
        return error_summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get error metrics: {str(e)}",
            extra={'event_type': 'error_metrics_error', 'user_id': str(current_user.id)},
            exc_info=True
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve error metrics"
        )


@router.post("/health/errors/cleanup", response_model=None)
async def cleanup_old_errors(
    hours: int = 24,
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """
    Clean up old error records.
    
    Args:
        hours: Remove errors older than this many hours (default: 24)
    
    Returns count of cleaned up errors.
    """
    try:
        if hours < 1 or hours > 168:  # Max 1 week
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hours parameter must be between 1 and 168"
            )
        
        cleared_count = clear_old_errors(hours=hours)
        
        logger.info(
            f"Error cleanup completed: {cleared_count} errors removed",
            extra={
                'event_type': 'error_cleanup',
                'user_id': str(current_user.id),
                'hours': hours,
                'cleared_count': cleared_count
            }
        )
        
        return {
            'message': f'Successfully cleaned up {cleared_count} old error records',
            'cleared_count': cleared_count,
            'cutoff_hours': hours,
            'timestamp': get_logger(__name__).extra.get('timestamp', 'unknown')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to cleanup errors: {str(e)}",
            extra={'event_type': 'error_cleanup_error', 'user_id': str(current_user.id)},
            exc_info=True
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup error records"
        )


@router.get("/health/readiness", response_model=None)
async def readiness_check() -> dict[str, Any]:
    """
    Kubernetes-style readiness probe.
    
    Checks if the service is ready to receive traffic.
    This is a lightweight check that verifies core dependencies.
    """
    try:
        from app.utils.health_monitoring import health_monitor
        
        # Quick check of critical components
        await health_monitor._check_database_health()
        
        db_status = health_monitor.components.get('database')
        if db_status and db_status.status.value in ['critical', 'unhealthy']:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not ready"
            )
        
        return {
            "status": "ready",
            "service": "hormonia-backend",
            "message": "Service is ready to receive traffic"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Readiness check failed: {str(e)}",
            extra={'event_type': 'readiness_check_error'},
            exc_info=True
        )
        
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not ready"
        )


@router.get("/health/liveness", response_model=None)
async def liveness_check() -> dict[str, Any]:
    """
    Kubernetes-style liveness probe.

    Checks if the service is alive and should not be restarted.
    This is a very lightweight check.
    """
    return {
        "status": "alive",
        "service": "hormonia-backend",
        "message": "Service is alive"
    }


# Enhanced health checks for the new fallback systems
@router.get("/health/auth-system", response_model=None)
async def auth_system_health() -> dict[str, Any]:
    """
    Test authentication system components for the ServiceProvider fix.

    This endpoint specifically tests the simplified authentication system
    to ensure login functionality works.
    """
    from datetime import datetime

    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "database_session": {"status": "unknown"},
        "service_provider": {"status": "unknown"},
        "auth_service": {"status": "unknown"},
        "fallback_systems": {"status": "unknown"}
    }

    # Test database session creation
    try:
        from app.core.database_direct import get_direct_session, initialize_direct_database

        # Initialize direct database if needed
        initialize_direct_database()

        with get_direct_session() as db:
            from sqlalchemy import text
            result = db.execute(text("SELECT 1")).fetchone()
            results["database_session"] = {
                "status": "available",
                "test_query": result[0] if result else None
            }
    except Exception as e:
        logger.error(f"Database session test failed: {e}")
        results["database_session"] = {
            "status": "failed",
            "error": str(e)
        }

    # Test service provider creation
    if results["database_session"]["status"] == "available":
        try:
            from app.services_simple import SimplifiedServiceProvider
            from app.core.redis_unified import get_sync_redis
            from app.core.database_direct import get_direct_session

            # Get Redis
            redis_client = None
            try:
                redis_client = get_sync_redis()
            except Exception as redis_error:
                logger.warning(f"Redis initialization failed: {redis_error}")

            with get_direct_session() as db:
                provider = SimplifiedServiceProvider(db, redis_client)

                results["service_provider"] = {
                    "status": "available" if provider.is_initialized else "failed",
                    "initialized": provider.is_initialized,
                    "redis_available": redis_client is not None and redis_client.get_status().get("available", False)
                }

                # Test auth service
                if provider.is_initialized:
                    try:
                        auth_service = provider.auth_service
                        results["auth_service"] = {
                            "status": "available",
                            "type": type(auth_service).__name__
                        }
                    except Exception as auth_error:
                        logger.error(f"Auth service test failed: {auth_error}")
                        results["auth_service"] = {
                            "status": "failed",
                            "error": str(auth_error)
                        }
        except Exception as e:
            logger.error(f"Service provider test failed: {e}")
            results["service_provider"] = {
                "status": "failed",
                "error": str(e)
            }

    # Test fallback system status
    try:
        from app.dependencies_fallback import test_fallback_systems
        fallback_status = test_fallback_systems()
        results["fallback_systems"] = fallback_status
    except Exception as e:
        logger.error(f"Fallback systems test failed: {e}")
        results["fallback_systems"] = {
            "status": "failed",
            "error": str(e)
        }

    # Determine overall status
    auth_ready = (
        results["database_session"].get("status") == "available" and
        results["service_provider"].get("status") == "available" and
        results["auth_service"].get("status") == "available"
    )

    results["overall_status"] = "ready" if auth_ready else "degraded"
    results["login_should_work"] = auth_ready

    return results


@router.post("/health/reset-dependencies", response_model=None)
async def reset_dependency_system(current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """
    Reset the dependency system to try primary systems again.

    This endpoint forces the system to try the primary (complex) dependency
    systems again after they have been marked as failed. Requires authentication.
    """
    from datetime import datetime

    try:
        # Import the enhanced dependency system
        from app.dependencies_enhanced import get_dependency_manager, reset_dependency_system as reset_deps

        # Get status before reset
        manager = get_dependency_manager()
        status_before = manager.get_health_status()

        # Reset the system
        reset_deps()

        # Get status after reset
        status_after = manager.get_health_status()

        logger.info(
            f"Dependency system reset by user {current_user.email}",
            extra={
                'event_type': 'dependency_reset',
                'user_id': str(current_user.id),
                'status_before': status_before,
                'status_after': status_after
            }
        )

        return {
            "status": "success",
            "message": "Dependency system reset successfully",
            "timestamp": datetime.utcnow().isoformat(),
            "reset_by": current_user.email,
            "status_before": status_before,
            "status_after": status_after
        }

    except Exception as e:
        logger.error(
            f"Failed to reset dependency system: {e}",
            extra={
                'event_type': 'dependency_reset_error',
                'user_id': str(current_user.id)
            },
            exc_info=True
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset dependency system: {e}"
        )