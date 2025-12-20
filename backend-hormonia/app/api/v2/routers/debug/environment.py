"""
Environment & System Information Debug Endpoints

Endpoints:
- GET /environment - Get safe environment information
"""

import os
import sys
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request

from app.database import get_db
from app.models.user import User
from app.utils.rate_limiter import limiter
from app.schemas.v2.debug import (
    EnvironmentInfo,
    EnvironmentVariable,
    DebugResponse,
)

from .common import (
    check_debug_enabled,
    get_admin_user,
    log_debug_operation,
    mask_sensitive_value,
    SAFE_ENV_VARS,
    DEBUG_ENDPOINTS_ENABLED,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Environment & System Diagnostics
# ============================================================================


@router.get(
    "/environment",
    response_model=DebugResponse,
    summary="Get environment information",
    description="""
    Get safe environment information (whitelist only).

    **ADMIN-ONLY** - Rate limited: 5 req/min

    Security:
    - Only whitelisted variables exposed
    - Sensitive values masked
    - Full audit trail
    """,
)
@limiter.limit("5/minute")
async def get_environment_info(
    request: Request, admin_user: User = Depends(get_admin_user), db=Depends(get_db)
):
    """
    Get environment information with masked sensitive values.

    Returns whitelisted environment variables only.
    Sensitive values are masked for security.
    """
    check_debug_enabled()

    try:
        # Collect safe environment variables
        env_vars = []
        for key in SAFE_ENV_VARS:
            value = os.getenv(key)
            if value is not None:
                masked_value, is_masked = mask_sensitive_value(key, value)
                env_vars.append(
                    EnvironmentVariable(
                        key=key, value=masked_value, is_set=True, is_masked=is_masked
                    )
                )
            else:
                env_vars.append(
                    EnvironmentVariable(
                        key=key, value="<not set>", is_set=False, is_masked=False
                    )
                )

        env_info = EnvironmentInfo(
            environment=os.getenv("ENVIRONMENT", "unknown"),
            debug_mode=DEBUG_ENDPOINTS_ENABLED,
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            variables=env_vars,
            timestamp=datetime.now(timezone.utc),
        )

        # Audit log
        await log_debug_operation(
            db=db,
            admin_user=admin_user,
            endpoint="/environment",
            parameters={},
            result_summary=f"Retrieved {len(env_vars)} environment variables",
            request=request,
        )

        return DebugResponse(
            success=True,
            data=env_info.dict(),
            audit_logged=True,
            timestamp=datetime.now(timezone.utc),
            warning="Debug mode active - disable in production",
        )

    except Exception as e:
        logger.error(f"Environment info error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve environment info: {str(e)}",
        )
