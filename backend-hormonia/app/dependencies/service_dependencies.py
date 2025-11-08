"""Service Dependencies - Clean Domain Separation with Thread-Safe Session Management

REFACTORED: 2025-10-07
- All service dependencies now use get_thread_safe_service_provider()
- Ensures per-request session isolation (no session cross-talk)
- Fixes critical thread-safety violation in production multi-worker deployments

See: docs/deployment/SERVICE_DI_REFACTOR.md
"""
from fastapi import Depends
from sqlalchemy.orm import Session
from typing import Optional, Generator
import redis.asyncio as redis

from app.database import get_db
from app.services import ServiceProvider
from typing import Generator
from app.services.unified_cache import UnifiedCacheService

# =============================================================================
# THREAD-SAFE SERVICE PROVIDER (Lazy Import to Avoid Circular Dependency)
# =============================================================================

class _ThreadSafeProviderDependency:
    """
    Callable class for lazy importing get_thread_safe_service_provider.
    Prevents circular import by deferring the import until call time.
    """
    def __call__(self) -> Generator:
        from app.dependencies import get_thread_safe_service_provider
        yield from get_thread_safe_service_provider()

# Create singleton instance
_get_provider_dep = _ThreadSafeProviderDependency()

# =============================================================================
# DATABASE & EXTERNAL SERVICE DEPENDENCIES
# =============================================================================

# Database dependency
get_database = get_db

# Supabase client dependency - REMOVED (migrated to AWS RDS PostgreSQL)
# All database access now uses SQLAlchemy directly via get_db()
# Authentication uses Firebase Admin SDK (not Supabase Auth)

# Redis dependency (THREAD-SAFE: Uses per-request ServiceProvider)
async def get_redis(services: ServiceProvider = Depends(_get_provider_dep)) -> Optional[redis.Redis]:
    """
    Get Redis client instance from thread-safe ServiceProvider.

    Thread-safety: Each request gets its own ServiceProvider instance with
    isolated Redis client (if stateful operations are needed).

    Returns:
        Redis client or None if not configured
    """
    return services.redis_client

# =============================================================================
# DOMAIN SERVICE DEPENDENCIES (Using Clean Architecture)
# =============================================================================

# Patient Domain Services (THREAD-SAFE: Per-request session isolation)
def get_patient_service(services: ServiceProvider = Depends(_get_provider_dep)):
    """
    Get PatientService with thread-safe per-request database session.

    Thread-safety: Each request gets its own ServiceProvider with isolated session.
    No session cross-talk between concurrent requests.

    Returns:
        PatientService instance with request-scoped dependencies
    """
    return services.patient_service

def get_patient_repository(db: Session = Depends(get_db)):
    from app.repositories.patient import PatientRepository
    return PatientRepository(db)

# Flow Domain Services (THREAD-SAFE: Per-request session isolation)
def get_flow_service(services: ServiceProvider = Depends(_get_provider_dep)):
    """Get FlowEngineIntegrationService with thread-safe session."""
    return services.flow_service

def get_flow_state_repository(db: Session = Depends(get_db)):
    from app.repositories.flow import FlowStateRepository
    return FlowStateRepository(db)

def get_flow_analytics_service(db: Session = Depends(get_db)):
    from app.services.flow_analytics import FlowAnalyticsService
    return FlowAnalyticsService(db)

# Quiz Domain Services (THREAD-SAFE: Per-request session isolation)
def get_quiz_service(services: ServiceProvider = Depends(_get_provider_dep)):
    """Get QuizService with thread-safe session."""
    return services.quiz_service

def get_quiz_template_service(services: ServiceProvider = Depends(_get_provider_dep)):
    """Get QuizTemplateService with thread-safe session."""
    return services.quiz_service.template_service

def get_quiz_response_service(services: ServiceProvider = Depends(_get_provider_dep)):
    """Get QuizResponseService with thread-safe session."""
    return services.quiz_service.response_service

def get_quiz_session_service(services: ServiceProvider = Depends(_get_provider_dep)):
    """Get QuizSessionService with thread-safe session."""
    return services.quiz_service.session_service

def get_quiz_analytics_service(services: ServiceProvider = Depends(_get_provider_dep)):
    """Get QuizAnalyticsService with thread-safe session."""
    return services.quiz_service.analytics_service

# Message Domain Services (THREAD-SAFE)
def get_message_service(services: ServiceProvider = Depends(_get_provider_dep)):
    """Get MessageService with thread-safe session."""
    return services.message_service

def get_auth_service(services: ServiceProvider = Depends(_get_provider_dep)):
    """Get AuthService with thread-safe session."""
    return services.auth_service

# Analytics Domain Services (THREAD-SAFE)
def get_analytics_service(services: ServiceProvider = Depends(_get_provider_dep)):
    """Get AnalyticsService with thread-safe session."""
    return services.analytics_service

# Report Domain Services (THREAD-SAFE)
def get_report_service(services: ServiceProvider = Depends(_get_provider_dep)):
    """Get ReportService with thread-safe session."""
    return services.report_service

# Notification Domain Services (THREAD-SAFE)
def get_notification_service(services: ServiceProvider = Depends(_get_provider_dep)):
    """Get NotificationService with thread-safe session."""
    return services.notification_service

# File Domain Services (THREAD-SAFE)
def get_file_service(services: ServiceProvider = Depends(_get_provider_dep)):
    """Get FileService with thread-safe session."""
    return services.file_service

# Monthly Quiz Domain Services (THREAD-SAFE)
def get_monthly_quiz_service(services: ServiceProvider = Depends(_get_provider_dep)):
    """Get MonthlyQuizService with thread-safe session."""
    return services.monthly_quiz_service

# Metrics Domain Services (THREAD-SAFE)
def get_metrics_collector_service(services: ServiceProvider = Depends(_get_provider_dep)):
    """Get MetricsCollectorService with thread-safe session."""
    return services.metrics_collector_service

def get_metrics_redis_storage(services: ServiceProvider = Depends(_get_provider_dep)):
    """Get MetricsRedisStorage with thread-safe session."""
    return services.metrics_redis_storage

# =============================================================================
# ENHANCED SERVICE DEPENDENCIES (For advanced features)
# =============================================================================

async def get_cache_service():
    """Get cache service instance"""
    
    return CacheService()

async def get_websocket_manager_instance():
    """Get unified WebSocket manager instance"""
    from app.services.websocket import get_websocket_manager
    return get_websocket_manager()

# =============================================================================
# FLOW MANAGEMENT SERVICES (Specific to flow domain)
# =============================================================================

def get_flow_management_service(
    flow_repo=Depends(get_flow_state_repository),
    flow_engine=Depends(get_flow_service)
):
    """Get flow management service instance"""
    from app.services.flow_management import FlowManagementService
    return FlowManagementService(flow_repo, flow_engine)
