"""
Physicians API v2 - Modular Router
Aggregates all physician-related endpoints from modular components.
"""

from fastapi import APIRouter
from .crud import list_physicians
from .crud import router as crud_router
from .statistics import router as statistics_router
from .availability import router as availability_router
from .patients import router as patients_router

# Create main router
router = APIRouter(prefix="/physicians")

# Include sub-routers
router.include_router(crud_router, tags=["physicians-crud"])
router.include_router(
    statistics_router, prefix="/{physician_id}", tags=["physicians-statistics"]
)
router.include_router(
    availability_router, prefix="/{physician_id}", tags=["physicians-availability"]
)
router.include_router(patients_router, tags=["physicians-patients"])

# Backward-compatible alias without trailing slash.
router.add_api_route("", list_physicians, methods=["GET"], include_in_schema=False)

__all__ = ["router"]
