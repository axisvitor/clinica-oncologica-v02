from typing import Any
"""Services module exports."""

# ServiceProvider - Special import to avoid name conflict with package
import importlib.util
from pathlib import Path

# Get the services.py file (not this services package)
_services_file = Path(__file__).parent.parent / "services.py"
if _services_file.exists():
    # Load services.py module
    _spec = importlib.util.spec_from_file_location("_services_module", _services_file)
    _services_module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_services_module)

    # Import ServiceProvider from the services.py file
    ServiceProvider = _services_module.ServiceProvider

# Core Services
from .auth import AuthService
from app.domain.messaging.core import MessageService
from .quiz import (
    QuizTemplateService,
    QuizSessionService,
    QuizResponseService
)

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

# Backward compatibility: legacy imports still expect AlertService
AlertService = AlertManagerAdapter

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
    PerformanceMetricsCollector
)

# Admin Services
from .admin import (
    AdminUserService,
    UserProvisioningService
)

# Integration Services
from .hive_mind_integration import HiveMindIntegrationService  # Circular import resolved with lazy imports
from .platform_synchronization import PlatformSynchronizationService
from .webhook_processor import WebhookProcessor

# Messaging Services
from .websocket_events import websocket_events
from .websocket import UnifiedWebSocketConnectionManager

# Compatibility alias for legacy ConnectionManager name
ConnectionManager = UnifiedWebSocketConnectionManager

# Utility Services
from .template_loader import EnhancedTemplateLoader
from .localization import LocalizationService
from .audit_trail import AuditTrailService

# Reporting Services
from .reporting import (
    ReportService,
    EnhancedReportsService,
    QuizReportGenerator
)

# Monitoring Services
from .performance_monitoring import PerformanceMonitoringService
from .flow_monitoring import FlowMonitoringService
from .data_corruption_detector import DataCorruptionDetector

# Error Handling Services
from .error_recovery import ErrorRecoveryService
from .automated_recovery import AutomatedRecoveryService
from .critical_error_escalation import CriticalErrorEscalationService

# Note: ServiceProvider and get_service_provider are imported from app.services
# directly where needed to avoid circular imports. This module only exports
# the individual service classes.

__all__ = [
    # ServiceProvider (imported from services.py file)
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
    "AlertService",
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
    "ConnectionManager",
    
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
