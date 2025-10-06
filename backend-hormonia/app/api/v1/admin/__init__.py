"""
Admin API module for user management and administrative operations.
"""

from fastapi import APIRouter
from .users import router as users_router
from .audit_management import router as audit_router
from .system_stats import router as system_stats_router

# Create admin router
admin_router = APIRouter()

# Include user management routes
admin_router.include_router(
    users_router,
    prefix="/users",
    tags=["Admin - User Management"]
)

# Include audit management routes
admin_router.include_router(
    audit_router,
    prefix="/audit",
    tags=["Admin - Audit Management"]
)

# Include system statistics routes (for dashboard metrics)
admin_router.include_router(
    system_stats_router,
    tags=["Admin - System Statistics"]
)