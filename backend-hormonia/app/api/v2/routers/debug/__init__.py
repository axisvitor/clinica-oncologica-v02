"""
Debug & Diagnostics API v2 - Modular Router Package
ADMIN-ONLY endpoints for system diagnostics and troubleshooting.

SECURITY:
- DISABLED by default in production (ENABLE_DEBUG_ENDPOINTS=false)
- ADMIN role required for all endpoints
- Rate limited to 5 requests/minute
- All operations audit logged
- Sensitive data masked/sanitized
- Time-boxed debug sessions (1 hour max)

WARNING: NEVER enable in production!
"""

from fastapi import APIRouter

from .environment import router as environment_router
from .database import router as database_router
from .auth import router as auth_router
from .common import SAFE_ENV_VARS, mask_sensitive_value, sanitize_sql_query

# Main debug router
router = APIRouter()

# Include sub-routers
router.include_router(environment_router, tags=["debug-environment"])
router.include_router(database_router, tags=["debug-database"])
router.include_router(auth_router, prefix="/auth", tags=["debug-auth"])

__all__ = [
    "router",
    "SAFE_ENV_VARS",
    "mask_sensitive_value",
    "sanitize_sql_query",
]
