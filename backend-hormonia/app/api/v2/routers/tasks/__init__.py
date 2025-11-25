"""
Tasks API Router - Combines all task endpoints.

This module provides the main router that combines all task-related endpoints:
- CRUD operations (list, get, create)
- Task operations (cancel, retry)
- Monitoring (logs, statistics, queue status)
- Bulk operations (bulk cancel, cleanup)
"""

from fastapi import APIRouter

from .endpoints import (
    crud_router,
    operations_router,
    monitoring_router,
    bulk_router,
)

# Create main router
router = APIRouter()

# Include all endpoint routers
router.include_router(crud_router, tags=["Tasks - CRUD"])
router.include_router(operations_router, tags=["Tasks - Operations"])
router.include_router(monitoring_router, tags=["Tasks - Monitoring"])
router.include_router(bulk_router, tags=["Tasks - Bulk Operations"])

__all__ = ["router"]
