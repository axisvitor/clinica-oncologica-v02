"""
Enhanced Message Management API v2

Advanced messaging features with template management, scheduling, analytics,
A/B testing, and performance tracking. Extends base messages v2 functionality.

This module aggregates all enhanced messaging sub-routers into a single router.
"""

from fastapi import APIRouter

from .templates import router as templates_router
from .scheduling import router as scheduling_router
from .ab_testing import router as ab_testing_router
from .analytics import router as analytics_router
from .bulk import router as bulk_router
from .dependencies import _render_template

# Create main router
router = APIRouter()

# Include all sub-routers
router.include_router(templates_router, tags=["Templates"])
router.include_router(scheduling_router, tags=["Scheduling"])
router.include_router(ab_testing_router, tags=["A/B Testing"])
router.include_router(analytics_router, tags=["Analytics"])
router.include_router(bulk_router, tags=["Bulk Operations"])

__all__ = ["router", "_render_template"]
