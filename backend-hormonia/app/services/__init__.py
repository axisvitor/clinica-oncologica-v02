"""Services module exports.

This module provides the central service layer for the Hormonia Backend System.

Service Architecture:
--------------------
- ServiceProvider: Thread-safe, request-scoped dependency injection container
  located in app/service_provider.py. Each HTTP request gets its own
  ServiceProvider instance with isolated database session and Redis client.

- Individual services are lazy-loaded through ServiceProvider properties
  to optimize memory usage and startup time.

Thread Safety:
-------------
The ServiceProvider uses request-scoping (one instance per FastAPI request)
rather than thread-local storage. This ensures:
- No shared state between concurrent requests
- Proper database session isolation
- Clean resource lifecycle management

Usage:
-----
    # In route handlers or dependencies:
    from app.service_provider import ServiceProvider
    # OR for backwards compatibility:
    from app.services import ServiceProvider

    def get_patient(services: ServiceProvider = Depends(get_thread_safe_service_provider)):
        return services.patient_service.get_patient(patient_id)
"""

# ServiceProvider - Import from dedicated module (avoids package/module shadowing)
# This import is safe because app.service_provider uses lazy imports internally
from app.service_provider import ServiceProvider

# Core Services
from .auth import AuthService
from app.domain.messaging.core import MessageService
from .quiz import QuizTemplateService, QuizSessionService, QuizResponseService

# Flow Services
from .flow import FlowEngine  # Consolidated Flow Engine
from .flow_template import FlowTemplateService
from .enhanced_flow_engine import EnhancedFlowEngine
from .state_machine import StateMachine

# AI Services
from .ai import AIHumanizer, SentimentAnalyzer, PatientContext

# Alert & Notification Services (unified architecture)
from .alerts import (
    AlertManager,
    AlertManagerAdapter,
    AlertProcessor,
)


# Analytics Services
from app.domain.analytics.analytics_service import AnalyticsService
from .analytics import (
    FlowAnalyticsService,
    ABTestingAnalyticsService,
    AdminStatsService,
    DataAggregator,
    DataExtractionService,
    EnhancedAnalyticsService,
    MedicoStatsService,
    MetricsCollector,
    MetricsRedisStorage,
    PerformanceMetricsCollector,
)

# Admin Services
from .admin import AdminUserService, UserProvisioningService

# Integration Services
from .hive_mind_integration import (
    HiveMindIntegrationService,
)  # Circular import resolved with lazy imports
from .platform_synchronization import PlatformSynchronizationService
from .webhook_processor import WebhookProcessor

# Messaging Services
from .websocket_events import websocket_events
from .websocket import UnifiedWebSocketConnectionManager


# Utility Services
from .template_loader import EnhancedTemplateLoader
from .localization import LocalizationService
from .audit_trail import AuditTrailService

# Reporting Services
from .reporting import ReportService, EnhancedReportsService, QuizReportGenerator

# Monitoring Services
from .performance_monitoring import PerformanceMonitoringService
from .flow_monitoring import FlowMonitoringService
from .data_corruption import DataCorruptionDetector

# Error Handling Services
from .error_recovery import ErrorRecoveryService
from .automated_recovery import AutomatedRecoveryService
from .critical_error_escalation import CriticalErrorEscalationService

# Note: ServiceProvider is now in app.service_provider module
# It is re-exported here for backwards compatibility

__all__ = [
    # ServiceProvider (re-exported from app.service_provider)
    "ServiceProvider",
    # Core Services
    "AuthService",
    "PatientService",
    "MessageService",
    "QuizTemplateService",
    "QuizSessionService",
    "QuizResponseService",
    # Flow Services
    "FlowEngine",
    "FlowTemplateService",
    "EnhancedFlowEngine",
    "StateMachine",
    # AI Services
    "AIHumanizer",
    "SentimentAnalyzer",
    "PatientContext",
    # Alert Services
    "AlertManager",
    "AlertManagerAdapter",
    "AlertProcessor",
    # Analytics Services
    "AnalyticsService",
    "FlowAnalyticsService",
    "ABTestingAnalyticsService",
    "AdminStatsService",
    "DataAggregator",
    "DataExtractionService",
    "EnhancedAnalyticsService",
    "MedicoStatsService",
    "MetricsCollector",
    "MetricsRedisStorage",
    "PerformanceMetricsCollector",
    # Admin Services
    "AdminUserService",
    "UserProvisioningService",
    # Integration Services
    "HiveMindIntegrationService",  # Circular import resolved with lazy imports
    "PlatformSynchronizationService",
    "WebhookProcessor",
    # Messaging Services
    "websocket_events",
    "UnifiedWebSocketConnectionManager",
    # Utility Services
    "EnhancedTemplateLoader",
    "LocalizationService",
    "AuditTrailService",
    # Reporting Services
    "ReportService",
    "EnhancedReportsService",
    "QuizReportGenerator",
    # Monitoring Services
    "PerformanceMonitoringService",
    "FlowMonitoringService",
    "DataCorruptionDetector",
    # Error Handling Services
    "ErrorRecoveryService",
    "AutomatedRecoveryService",
    "CriticalErrorEscalationService",
]
