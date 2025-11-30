"""
Analytics API v2 - Modular Structure
Refactored analytics endpoints organized by domain.
"""

from fastapi import APIRouter
from .base import router as base_router
from .patient_analytics import router as patient_router
from .quiz_analytics import router as quiz_router
from .dashboard_analytics import router as dashboard_router

# Main analytics router that aggregates all sub-routers
router = APIRouter()

# Include all sub-routers
router.include_router(base_router, tags=["analytics-base"])
router.include_router(patient_router, tags=["analytics-patients"])
router.include_router(quiz_router, tags=["analytics-quizzes"])
router.include_router(dashboard_router, tags=["analytics-dashboard"])

__all__ = ["router"]
