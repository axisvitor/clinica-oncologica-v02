"""
Flow Management API v2 - Modular Package
Enhanced flow endpoints with cursor pagination, field selection, and Redis caching.

Organized into 4 focused modules:
- state: Flow state operations (get, advance, pause, resume, history)
- analytics: Dashboard and analytics (metrics, engagement, risk, insights)
- templates: Template management and patient customizations
- advanced: Rules engine and utility operations
"""

from fastapi import APIRouter
from . import state, analytics, templates, advanced

# Create main router
router = APIRouter()

# Include all sub-routers with appropriate tags
router.include_router(state.router, tags=["flows-state"])
router.include_router(analytics.router, tags=["flows-analytics"])
router.include_router(templates.router, tags=["flows-templates"])
router.include_router(advanced.router, tags=["flows-advanced"])

# Export router for use in main API router
__all__ = ["router"]
