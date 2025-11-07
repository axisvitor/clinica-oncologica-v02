"""
API v2 Router
Main router for API v2 endpoints.
"""

from fastapi import APIRouter
from .patients import router as patients_router
from .quiz import router as quiz_router
from .analytics import router as analytics_router
from .auth import router as auth_router
from .flows import router as flows_router
from .messages import router as messages_router
from .reports import router as reports_router
from .admin import router as admin_router

api_v2_router = APIRouter(prefix="/api/v2", tags=["v2"])

# Include sub-routers
api_v2_router.include_router(patients_router, prefix="/patients", tags=["patients-v2"])
api_v2_router.include_router(quiz_router, prefix="/quiz", tags=["quiz-v2"])
api_v2_router.include_router(analytics_router, prefix="/analytics", tags=["analytics-v2"])
api_v2_router.include_router(auth_router, prefix="/auth", tags=["auth-v2"])
api_v2_router.include_router(flows_router, prefix="/flows", tags=["flows-v2"])
api_v2_router.include_router(messages_router, prefix="/messages", tags=["messages-v2"])
api_v2_router.include_router(reports_router, prefix="/reports", tags=["reports-v2"])
api_v2_router.include_router(admin_router, prefix="/admin", tags=["admin-v2"])


@api_v2_router.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint for API v2.
    
    Returns:
        dict: API status and version
    """
    return {
        "status": "healthy",
        "version": "2.0.0",
        "api": "v2"
    }
