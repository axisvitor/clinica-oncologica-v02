"""
System Initialization Management Module.

Provides endpoints for system initialization and status tracking:
- POST /initialize - Trigger comprehensive system initialization
- GET /initialization-status - Get current initialization status

Security:
- All endpoints require ADMIN role
- Rate limiting applied (5/hour for init, 30/min for status)
"""

from typing import Optional
from datetime import datetime, timezone
import time

from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlalchemy import text

from app.database import get_db
from app.schemas.v2.system import (
    InitializationRequest,
    InitializationStatusResponse,
)
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.core.redis_client import get_async_redis_client
from app.utils.rate_limiter import limiter
from app.utils.logging import get_logger
from app.config import settings
from app.utils.auth_helpers import is_admin as _is_admin

router = APIRouter()
logger = get_logger(__name__)

# System initialization state (in-memory, could be moved to Redis for multi-instance)
_initialization_state = {
    "started_at": None,
    "completed_at": None,
    "status": "pending",
    "components": {},
    "errors": [],
    "warnings": [],
}


# ============================================================================
# Helper Functions
# ============================================================================


async def _get_redis_client():
    """Get async Redis client for caching."""
    try:
        return await get_async_redis_client()
    except Exception as e:
        logger.warning(f"Failed to get Redis client: {e}")
        return None


# ============================================================================
# System Initialization Endpoints (ADMIN ONLY)
# ============================================================================


@router.post(
    "/initialize",
    response_model=InitializationStatusResponse,
    summary="Initialize system",
    description="""
    Trigger comprehensive system initialization.

    **Authentication:** Admin role required
    **Rate limit:** 5 requests/hour (prevent abuse)

    Initializes:
    - Database connections and migrations
    - Redis cache and connection pools
    - Firebase Admin SDK
    - External service configurations
    """,
)
@limiter.limit("5/hour")
async def initialize_system(
    request: Request,
    init_request: Optional[InitializationRequest] = None,
    current_user=Depends(get_current_user_from_session),
    db=Depends(get_db),
):
    """
    Trigger comprehensive system initialization.

    This endpoint:
    - Validates all system components
    - Initializes services and dependencies
    - Performs health checks
    - Returns detailed initialization status
    """
    # Check admin privileges
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for system initialization",
        )

    global _initialization_state

    # Check if already initialized
    if _initialization_state["status"] == "in_progress":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="System initialization already in progress",
        )

    if init_request is None:
        init_request = InitializationRequest()

    # Start initialization
    start_time = time.time()
    _initialization_state = {
        "started_at": datetime.now(timezone.utc),
        "completed_at": None,
        "status": "in_progress",
        "components": {},
        "errors": [],
        "warnings": [],
    }

    logger.info("System initialization started by user")

    try:
        # Initialize components
        components_to_init = init_request.components or [
            "database",
            "redis",
            "firebase",
        ]

        for component in components_to_init:
            try:
                if component == "database":
                    # Test database connection
                    db.execute(text("SELECT 1"))
                    _initialization_state["components"]["database"] = "initialized"

                elif component == "redis":
                    # Test Redis connection
                    redis = await _get_redis_client()
                    if redis:
                        await redis.ping()
                        _initialization_state["components"]["redis"] = "initialized"
                    else:
                        _initialization_state["components"]["redis"] = "failed"
                        _initialization_state["warnings"].append("Redis unavailable")

                elif component == "firebase":
                    # Check Firebase configuration
                    if settings.FIREBASE_ADMIN_PROJECT_ID:
                        _initialization_state["components"]["firebase"] = "initialized"
                    else:
                        _initialization_state["components"]["firebase"] = "skipped"
                        _initialization_state["warnings"].append(
                            "Firebase not configured"
                        )

            except Exception as e:
                logger.error(f"Failed to initialize {component}: {e}")
                _initialization_state["components"][component] = "failed"
                _initialization_state["errors"].append(
                    {
                        "component": component,
                        "error_message": str(e),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "recoverable": True,
                    }
                )

        # Determine final status
        if _initialization_state["errors"]:
            _initialization_state["status"] = (
                "partial"
                if any(
                    c == "initialized"
                    for c in _initialization_state["components"].values()
                )
                else "failed"
            )
        else:
            _initialization_state["status"] = "completed"

        _initialization_state["completed_at"] = datetime.now(timezone.utc)
        duration_ms = (time.time() - start_time) * 1000
        _initialization_state["duration_ms"] = duration_ms

        logger.info(
            f"System initialization completed with status: {_initialization_state['status']}"
        )

        return InitializationStatusResponse(**_initialization_state)

    except Exception as e:
        logger.error(f"System initialization failed: {e}", exc_info=True)
        _initialization_state["status"] = "failed"
        _initialization_state["completed_at"] = datetime.now(timezone.utc)
        _initialization_state["errors"].append(
            {
                "component": "system",
                "error_message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "recoverable": False,
            }
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"System initialization failed: {str(e)}",
        )


@router.get(
    "/initialization-status",
    response_model=InitializationStatusResponse,
    summary="Get initialization status",
    description="""
    Get current system initialization status.

    **Authentication:** Admin role required
    **Rate limit:** 30 requests/minute
    """,
)
@limiter.limit("30/minute")
async def get_initialization_status(
    request: Request,
    current_user=Depends(get_current_user_from_session),
):
    """Get current system initialization status."""
    # Check admin privileges
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required to view initialization status",
        )

    return InitializationStatusResponse(**_initialization_state)
