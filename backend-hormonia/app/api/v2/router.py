"""
API v2 Router
Main router for API v2 endpoints.
"""

from fastapi import APIRouter
from .patients import router as patients_router
from .quiz import router as quiz_router
from .analytics import router as analytics_router
from .enhanced_analytics import router as enhanced_analytics_router
from .auth import router as auth_router
from .flows import router as flows_router
from .messages import router as messages_router
from .enhanced_messages import router as enhanced_messages_router
from .reports import router as reports_router
from .admin import router as admin_router
from .webhooks import router as webhooks_router
from .ai import router as ai_router
from .enhanced_monitoring import router as enhanced_monitoring_router
from .enhanced_quiz import router as enhanced_quiz_router
from .enhanced_reports import router as enhanced_reports_router
from .alerts import router as alerts_router
from .templates import router as templates_router
from .ab_testing import router as ab_testing_router
from .platform_sync import router as platform_sync_router
from .tasks import router as tasks_router
from .upload import router as upload_router
from .localization import router as localization_router
from .dashboard import router as dashboard_router

api_v2_router = APIRouter(prefix="/api/v2", tags=["v2"])

# Include sub-routers
api_v2_router.include_router(patients_router, prefix="/patients", tags=["patients-v2"])
api_v2_router.include_router(quiz_router, prefix="/quiz", tags=["quiz-v2"])
api_v2_router.include_router(analytics_router, prefix="/analytics", tags=["analytics-v2"])
api_v2_router.include_router(enhanced_analytics_router, prefix="/enhanced-analytics", tags=["enhanced-analytics-v2"])
api_v2_router.include_router(auth_router, prefix="/auth", tags=["auth-v2"])
api_v2_router.include_router(flows_router, prefix="/flows", tags=["flows-v2"])
api_v2_router.include_router(messages_router, prefix="/messages", tags=["messages-v2"])
api_v2_router.include_router(enhanced_messages_router, prefix="/enhanced-messages", tags=["enhanced-messages-v2"])
api_v2_router.include_router(reports_router, prefix="/reports", tags=["reports-v2"])
api_v2_router.include_router(admin_router, prefix="/admin", tags=["admin-v2"])
api_v2_router.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks-v2"])
api_v2_router.include_router(ai_router, prefix="/ai", tags=["ai-v2"])

# Phase 5: Enhanced modules and Alerts
api_v2_router.include_router(enhanced_monitoring_router, prefix="/monitoring", tags=["enhanced-monitoring-v2"])
api_v2_router.include_router(enhanced_quiz_router, prefix="/enhanced-quiz", tags=["enhanced-quiz-v2"])
api_v2_router.include_router(enhanced_reports_router, prefix="/enhanced-reports", tags=["enhanced-reports-v2"])
api_v2_router.include_router(alerts_router, prefix="/alerts", tags=["alerts-v2"])

# Phase 6: Templates, A/B Testing, Platform Sync
api_v2_router.include_router(templates_router, prefix="/templates", tags=["templates-v2"])
api_v2_router.include_router(ab_testing_router, prefix="/ab-testing", tags=["ab-testing-v2"])
api_v2_router.include_router(platform_sync_router, prefix="/platform-sync", tags=["platform-sync-v2"])

# Phase 7: Tasks, Upload, Localization, Dashboard
api_v2_router.include_router(tasks_router, prefix="/tasks", tags=["tasks-v2"])
api_v2_router.include_router(upload_router, prefix="/upload", tags=["upload-v2"])
api_v2_router.include_router(localization_router, prefix="/localization", tags=["localization-v2"])
api_v2_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard-v2"])


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
