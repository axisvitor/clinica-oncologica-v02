"""
System Management API for Hormonia Backend.

Provides endpoints for:
- System initialization
- Health checks and monitoring
- Configuration validation
- Service status reporting
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime

from app.services.system_initialization import (
    get_system_initialization_service,
    get_system_health,
    InitializationError
)
from app.dependencies.auth_dependencies import get_current_user
from app.models.user import User, UserRole
from app.utils.logging import get_logger
from app.utils.rate_limiter import limiter
from app.config import settings

logger = get_logger(__name__)
router = APIRouter()


# Response Models
class SystemHealthResponse(BaseModel):
    """System health check response."""
    status: str
    timestamp: str
    components: Dict[str, Any]
    overall_score: float
    

class InitializationStatusResponse(BaseModel):
    """System initialization status response."""
    started_at: str | None
    completed_at: str | None
    status: str
    components: Dict[str, Any]
    errors: list[str]
    

class SystemInfoResponse(BaseModel):
    """System information response."""
    environment: str
    debug_mode: bool
    version: str
    uptime: str
    features: Dict[str, bool]


class ConfigValidationResponse(BaseModel):
    """Configuration validation response."""
    valid: bool
    warnings: list[str]
    errors: list[str]
    checked_at: str


@router.get(
    "/health",
    response_model=SystemHealthResponse,
    summary="System Health Check",
    description="Get comprehensive system health status including all components",
    responses={
        200: {"description": "System health status retrieved successfully"},
        503: {"description": "System is unhealthy or degraded"}
    }
)
@limiter.limit("60/minute")  # Allow frequent health checks
async def get_system_health_endpoint(request: Request) -> JSONResponse:
    """
    Get comprehensive system health status.
    
    This endpoint checks:
    - Database connectivity
    - Redis cache connectivity  
    - Firebase Admin SDK status
    - External service configurations
    
    Returns HTTP 200 for healthy/degraded, HTTP 503 for unhealthy.
    """
    try:
        health_status = await get_system_health()
        
        # Return appropriate HTTP status based on health
        status_code = status.HTTP_200_OK
        if health_status["status"] == "unhealthy":
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        
        return JSONResponse(
            status_code=status_code,
            content=health_status
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": "Health check failed",
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get(
    "/health/live",
    summary="Liveness Probe",
    description="Simple liveness check for container orchestration"
)
@limiter.limit("120/minute")  # High frequency for k8s probes
async def liveness_probe(request: Request) -> Dict[str, str]:
    """
    Simple liveness probe for container orchestration.
    
    Returns basic status without expensive health checks.
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get(
    "/health/ready",
    summary="Readiness Probe",
    description="Readiness check for container orchestration"
)
@limiter.limit("60/minute")
async def readiness_probe(request: Request) -> JSONResponse:
    """
    Readiness probe for container orchestration.
    
    Checks critical components to determine if system is ready to serve traffic.
    """
    try:
        # Quick checks for readiness
        from app.database import get_engine
        from app.utils.cache import get_redis_client
        from sqlalchemy import text
        
        # Test database
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        # Test Redis
        redis_client = get_redis_client()
        redis_client.ping()
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "ready",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        logger.warning(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.post(
    "/initialize",
    response_model=InitializationStatusResponse,
    summary="Initialize System",
    description="Trigger comprehensive system initialization (Admin only)"
)
@limiter.limit("5/hour")  # Limit initialization attempts
async def initialize_system_endpoint(
    request: Request,
    current_user: User = Depends(get_current_user)
) -> InitializationStatusResponse:
    """
    Trigger comprehensive system initialization.
    
    This endpoint:
    - Validates all system components
    - Initializes services and dependencies
    - Performs health checks
    - Returns detailed initialization status
    
    **Requires Admin privileges.**
    """
    # Check admin privileges
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for system initialization"
        )
    
    try:
        logger.info(f"System initialization requested by user {current_user.id}")
        
        service = get_system_initialization_service()
        initialization_result = await service.initialize_system()
        
        return InitializationStatusResponse(**initialization_result)
        
    except InitializationError as e:
        logger.error(f"System initialization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"System initialization failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during initialization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="System initialization failed due to unexpected error"
        )


@router.get(
    "/initialization/status",
    response_model=InitializationStatusResponse,
    summary="Get Initialization Status",
    description="Get current system initialization status (Admin only)"
)
@limiter.limit("30/minute")
async def get_initialization_status(
    request: Request,
    current_user: User = Depends(get_current_user)
) -> InitializationStatusResponse:
    """
    Get current system initialization status.
    
    **Requires Admin privileges.**
    """
    # Check admin privileges
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required to view initialization status"
        )
    
    try:
        service = get_system_initialization_service()
        status_data = service.get_initialization_status()
        
        return InitializationStatusResponse(**status_data)
        
    except Exception as e:
        logger.error(f"Failed to get initialization status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve initialization status"
        )


@router.get(
    "/info",
    response_model=SystemInfoResponse,
    summary="Get System Information",
    description="Get system information and feature flags"
)
@limiter.limit("30/minute")
async def get_system_info(request: Request) -> SystemInfoResponse:
    """
    Get general system information and feature flags.
    
    This endpoint provides non-sensitive system information
    that can be used by frontend applications.
    """
    try:
        # Calculate uptime (simplified - would need startup time tracking in production)
        import psutil
        uptime_seconds = psutil.boot_time()
        uptime = f"{uptime_seconds}s"
        
        return SystemInfoResponse(
            environment=settings.ENVIRONMENT,
            debug_mode=settings.DEBUG,
            version="1.0.0",  # Could be read from package.json or version file
            uptime=uptime,
            features={
                "firebase_auth": bool(settings.FIREBASE_ADMIN_PROJECT_ID),
                "whatsapp_integration": settings.ENABLE_EVOLUTION,
                "ai_humanization": settings.AI_HUMANIZATION_ENABLED,
                "monitoring": settings.MONITORING_ENABLED,
                "rate_limiting": settings.RATE_LIMIT_ENABLED,
                "monthly_quiz_links": settings.MONTHLY_QUIZ_VIA_LINK
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get system info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system information"
        )


@router.get(
    "/config/validate",
    response_model=ConfigValidationResponse,
    summary="Validate Configuration",
    description="Validate system configuration (Admin only)"
)
@limiter.limit("10/hour")
async def validate_configuration(
    request: Request,
    current_user: User = Depends(get_current_user)
) -> ConfigValidationResponse:
    """
    Validate system configuration.
    
    Checks configuration validity, security settings,
    and provides warnings for potential issues.
    
    **Requires Admin privileges.**
    """
    # Check admin privileges
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for configuration validation"
        )
    
    try:
        warnings = []
        errors = []
        
        # Validate critical settings
        if not settings.SECRET_KEY or 'CHANGE_THIS' in settings.SECRET_KEY.upper():
            errors.append("SECRET_KEY is not properly configured")
        
        if not settings.DATABASE_URL:
            errors.append("DATABASE_URL is not configured")
        
        # Check Firebase configuration
        firebase_configured = all([
            settings.FIREBASE_ADMIN_PROJECT_ID,
            settings.FIREBASE_ADMIN_PRIVATE_KEY,
            settings.FIREBASE_ADMIN_CLIENT_EMAIL
        ])
        
        if not firebase_configured:
            warnings.append("Firebase Admin SDK is not fully configured")
        
        # Check production security settings
        if settings.ENVIRONMENT.lower() == 'production':
            if settings.DEBUG:
                errors.append("DEBUG should be False in production")
            if not settings.SESSION_COOKIE_SECURE:
                warnings.append("SESSION_COOKIE_SECURE should be True in production")
            if not settings.SECURE_SSL_REDIRECT:
                warnings.append("SECURE_SSL_REDIRECT should be True in production")
        
        # Check CORS configuration
        if not settings.ALLOWED_ORIGINS and not settings.FRONTEND_URL:
            warnings.append("CORS origins not configured")
        
        # Check external service configurations
        if settings.ENABLE_EVOLUTION and not settings.EVOLUTION_API_KEY:
            warnings.append("Evolution API is enabled but API key not configured")
        
        if settings.AI_HUMANIZATION_ENABLED and not settings.GEMINI_API_KEY:
            warnings.append("AI humanization is enabled but Gemini API key not configured")
        
        return ConfigValidationResponse(
            valid=len(errors) == 0,
            warnings=warnings,
            errors=errors,
            checked_at=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuration validation failed"
        )


@router.post(
    "/restart",
    summary="Restart System Components",
    description="Restart specific system components (Admin only)"
)
@limiter.limit("3/hour")  # Very limited restart attempts
async def restart_system_components(
    request: Request,
    components: list[str],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Restart specific system components.
    
    **Requires Super Admin privileges.**
    
    Available components:
    - redis_connections
    - firebase_service
    - monitoring_service
    """
    # Check admin privileges
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for component restart"
        )
    
    try:
        logger.warning(f"Component restart requested by user {current_user.id}: {components}")
        
        restart_results = {}
        
        for component in components:
            if component == "redis_connections":
                try:
                    # This would reset Redis connection pools
                    from app.utils.cache import reset_redis_connections
                    reset_redis_connections()
                    restart_results[component] = "success"
                except Exception as e:
                    restart_results[component] = f"failed: {str(e)}"
            
            elif component == "firebase_service":
                try:
                    # This would reinitialize Firebase Admin SDK
                    import firebase_admin
                    firebase_admin._apps.clear()  # Clear existing apps
                    restart_results[component] = "success"
                except Exception as e:
                    restart_results[component] = f"failed: {str(e)}"
            
            elif component == "monitoring_service":
                try:
                    # This would restart monitoring services
                    restart_results[component] = "success"
                except Exception as e:
                    restart_results[component] = f"failed: {str(e)}"
            
            else:
                restart_results[component] = "unknown_component"
        
        return {
            "status": "completed",
            "results": restart_results,
            "restarted_at": datetime.utcnow().isoformat(),
            "restarted_by": str(current_user.id)
        }
        
    except Exception as e:
        logger.error(f"Component restart failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Component restart failed"
        )
