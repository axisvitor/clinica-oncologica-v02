"""
API v2 Router
Main router for API v2 endpoints.
"""

import os
import logging
from fastapi import APIRouter
from .routers.patients import router as patients_crud_router
from .routers.auth import router as auth_router
from .routers.users import router as users_router
from .routers.notifications import router as notifications_router
from .routers.patients_import import router as patients_import_router
from .routers.patients_flow import router as patients_flow_router
from .routers.patients_integrity import router as patients_integrity_router
from .routers.appointments import router as appointments_router
from .routers.treatments import router as treatments_router
from .routers.medications import router as medications_router
from .routers.quiz_sessions import router as quiz_router
from .routers.analytics import router as analytics_router
from .routers.enhanced_analytics import router as enhanced_analytics_router
from .routers.flows import router as flows_router
from .routers.messages import router as messages_router
from .routers.enhanced_messages import router as enhanced_messages_router
from .routers.reports import router as reports_router
from .routers.admin import router as admin_router
from .routers.webhooks import router as webhooks_router
from .routers.ai import router as ai_router
from .routers.enhanced_monitoring import router as enhanced_monitoring_router
from .routers.enhanced_quiz import router as enhanced_quiz_router
from .routers.enhanced_reports import router as enhanced_reports_router
from .routers.alerts import router as alerts_router
from .routers.flow_templates import router as flow_templates_router
from .routers.quiz_templates import router as quiz_templates_router
from .routers.template_versions import router as template_versions_router
from .routers.template_admin import router as template_admin_router
from .routers.ab_testing import router as ab_testing_router
from .routers.platform_sync import router as platform_sync_router
from .routers.tasks import router as tasks_router
from .routers.upload import router as upload_router
from .routers.localization import router as localization_router
from .routers.dashboard import router as dashboard_router
from .routers.physicians import router as physicians_router
from .routers.admin_extensions import router as admin_extensions_router
from .routers.docs import router as docs_router
from .routers.roles import router as roles_router
from .routers.system import router as system_router
from .routers.performance import router as performance_router
from .routers.health import router as health_router
from .routers.quiz_responses import router as quiz_responses_router
from .routers.quiz_alerts import router as quiz_alerts_router
from .routers.monthly_quiz_management import router as monthly_quiz_management_router
from .routers.monthly_quiz_operations import router as monthly_quiz_operations_router
from .routers.debug import router as debug_router

logger = logging.getLogger(__name__)
api_v2_router = APIRouter(prefix="/api/v2", tags=["v2"])


# Include sub-routers
# Phase 1: Core Clinical Modules - Patients (Refactored into 4 focused modules - Sprint 1)
api_v2_router.include_router(patients_crud_router, prefix="/patients", tags=["patients-crud-v2"])
api_v2_router.include_router(patients_import_router, prefix="/patients", tags=["patients-import-v2"])
api_v2_router.include_router(patients_flow_router, prefix="/patients", tags=["patients-flow-v2"])
api_v2_router.include_router(patients_integrity_router, prefix="/patients", tags=["patients-integrity-v2"])
api_v2_router.include_router(appointments_router, prefix="/appointments", tags=["appointments-v2"])
api_v2_router.include_router(treatments_router, prefix="/treatments", tags=["treatments-v2"])
api_v2_router.include_router(medications_router, prefix="/medications", tags=["medications-v2"])

# Phase 2: Quiz and Analytics
api_v2_router.include_router(quiz_router, prefix="/quiz", tags=["quiz-v2"])
api_v2_router.include_router(analytics_router, prefix="/analytics", tags=["analytics-v2"])
api_v2_router.include_router(enhanced_analytics_router, prefix="/enhanced-analytics", tags=["enhanced-analytics-v2"])
# Auth & Users (Decomposed)
api_v2_router.include_router(auth_router, prefix="/auth", tags=["auth-v2"])
api_v2_router.include_router(users_router, prefix="/auth", tags=["users-v2"]) # Legacy path support for /me, /preferences
api_v2_router.include_router(notifications_router, prefix="/notifications", tags=["notifications-v2"])
api_v2_router.include_router(notifications_router, prefix="/auth/notifications", tags=["notifications-v2-legacy"]) # Legacy path
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

# Phase 6: Templates (Refactored into 4 focused modules - Sprint 1), A/B Testing, Platform Sync
api_v2_router.include_router(flow_templates_router, prefix="/templates", tags=["flow-templates-v2"])
api_v2_router.include_router(quiz_templates_router, prefix="/templates", tags=["quiz-templates-v2"])
api_v2_router.include_router(template_versions_router, prefix="/templates", tags=["template-versions-v2"])
api_v2_router.include_router(template_admin_router, prefix="/templates", tags=["template-admin-v2"])
api_v2_router.include_router(ab_testing_router, prefix="/ab-testing", tags=["ab-testing-v2"])
api_v2_router.include_router(platform_sync_router, prefix="/platform-sync", tags=["platform-sync-v2"])

# Phase 7: Tasks, Upload, Localization, Dashboard
api_v2_router.include_router(tasks_router, prefix="/tasks", tags=["tasks-v2"])
api_v2_router.include_router(upload_router, prefix="/upload", tags=["upload-v2"])
api_v2_router.include_router(localization_router, prefix="/localization", tags=["localization-v2"])
api_v2_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard-v2"])

# Phase 8: Docs, Physicians, Admin Extensions
api_v2_router.include_router(docs_router, prefix="/docs", tags=["docs-v2"])
api_v2_router.include_router(physicians_router, prefix="/physicians", tags=["physicians-v2"])
api_v2_router.include_router(admin_extensions_router, prefix="/admin-extensions", tags=["admin-extensions-v2"])

# Phase 9: Roles & Permissions, System Management, Performance Monitoring, Quiz Extensions
api_v2_router.include_router(roles_router, prefix="/roles", tags=["roles-v2"])
api_v2_router.include_router(system_router, prefix="/system", tags=["system-v2"])
api_v2_router.include_router(performance_router, prefix="/performance", tags=["performance-v2"])
api_v2_router.include_router(health_router, tags=["health-v2"])  # Health router has its own /health prefix

# Quiz Extensions - Refactored into 4 focused modules (Sprint 1)
api_v2_router.include_router(quiz_responses_router, prefix="/quiz-extensions", tags=["quiz-responses-v2"])
api_v2_router.include_router(quiz_alerts_router, prefix="/quiz-extensions", tags=["quiz-alerts-v2"])
api_v2_router.include_router(monthly_quiz_management_router, prefix="/quiz-extensions", tags=["monthly-quiz-v2"])
api_v2_router.include_router(monthly_quiz_operations_router, prefix="/quiz-extensions", tags=["monthly-quiz-ops-v2"])

# Monthly Quiz Public Access - Alias for Frontend Compatibility
# Frontend expects /monthly-quiz-public/*, so we register the operations router again with this prefix
api_v2_router.include_router(monthly_quiz_operations_router, prefix="/monthly-quiz-public", tags=["monthly-quiz-public-v2"])
# Frontend also expects /monthly-quiz/* for some operations (mapped to quiz-extensions)
api_v2_router.include_router(monthly_quiz_operations_router, prefix="/monthly-quiz", tags=["monthly-quiz-compat-v2"])

# Phase 10: Complete V2 Migration - Critical Clinical Modules Added
# ✅ Appointments, Treatments, and Medications modules now implemented
# All critical V1 endpoints now have V2 equivalents

# Phase 9: Debug & Diagnostics (CONDITIONAL - disabled in production by default)
# ⚠️ SECURITY WARNING: Only register debug endpoints if explicitly enabled
# NEVER set ENABLE_DEBUG_ENDPOINTS=true in production!
DEBUG_ENDPOINTS_ENABLED = os.getenv("ENABLE_DEBUG_ENDPOINTS", "false").lower() == "true"

if DEBUG_ENDPOINTS_ENABLED:
    api_v2_router.include_router(debug_router, prefix="/debug", tags=["debug-v2"])
    logger.warning(
        "⚠️  DEBUG ENDPOINTS ENABLED - This should NEVER be enabled in production!\n"
        "   Debug endpoints provide administrative diagnostic tools with:\n"
        "   - Environment variable inspection (masked)\n"
        "   - Database diagnostics and query testing\n"
        "   - Authentication flow debugging\n"
        "   - Permission testing and auth simulation\n"
        "   Set ENABLE_DEBUG_ENDPOINTS=false to disable.\n"
        "   All debug operations are ADMIN-ONLY and fully audit logged."
    )
else:
    logger.info("Debug endpoints disabled (production mode)")


# Note: Comprehensive health check endpoints now available at /api/v2/health/*
# See health router for full health monitoring system
