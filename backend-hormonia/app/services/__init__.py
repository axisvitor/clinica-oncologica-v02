"""Service package exports with lazy loading.

This module intentionally avoids eager imports to prevent circular-import
cascades during worker/task bootstrap (Celery + AI clients + flow services).
Consumers can keep using `from app.services import <Symbol>`.
"""

from __future__ import annotations

from importlib import import_module
from typing import Dict, Tuple

_SERVICE_EXPORTS: Dict[str, Tuple[str, str]] = {
    # Core services
    "AuthService": ("app.services.auth", "AuthService"),
    "PasswordResetService": ("app.services.password_reset_service", "PasswordResetService"),
    "MessageService": ("app.domain.messaging.core", "MessageService"),
    "QuizTemplateService": ("app.services.quiz", "QuizTemplateService"),
    "QuizSessionService": ("app.services.quiz", "QuizSessionService"),
    "QuizResponseService": ("app.services.quiz", "QuizResponseService"),
    # Flow services
    "FlowEngine": ("app.services.flow", "FlowEngine"),
    "FlowTemplateService": ("app.services.flow_template", "FlowTemplateService"),
    "EnhancedFlowEngine": ("app.services.enhanced_flow_engine", "EnhancedFlowEngine"),
    "StateMachine": ("app.services.state_machine", "StateMachine"),
    # AI services
    "PatientContext": ("app.services.ai", "PatientContext"),
    # Alert services
    "AlertManager": ("app.services.alerts", "AlertManager"),
    "AlertProcessor": ("app.services.alerts", "AlertProcessor"),
    # Analytics services
    "AnalyticsService": ("app.domain.analytics.analytics_service", "AnalyticsService"),
    "FlowAnalyticsService": ("app.services.analytics", "FlowAnalyticsService"),
    "AdminStatsService": ("app.services.analytics", "AdminStatsService"),
    "DataAggregator": ("app.services.analytics", "DataAggregator"),
    "DataExtractionService": ("app.services.analytics", "DataExtractionService"),
    "EnhancedAnalyticsService": ("app.services.analytics", "EnhancedAnalyticsService"),
    "MedicoStatsService": ("app.services.analytics", "MedicoStatsService"),
    "MetricsCollector": ("app.services.analytics", "MetricsCollector"),
    "MetricsRedisStorage": ("app.services.analytics", "MetricsRedisStorage"),
    "PerformanceMetricsCollector": (
        "app.services.analytics",
        "PerformanceMetricsCollector",
    ),
    # Admin services
    "AdminUserService": ("app.services.admin", "AdminUserService"),
    "UserProvisioningService": ("app.services.admin", "UserProvisioningService"),
    # Integration services
    "HiveMindIntegrationService": (
        "app.services.hive_mind_integration",
        "HiveMindIntegrationService",
    ),
    "PlatformSynchronizationService": (
        "app.services.platform_synchronization",
        "PlatformSynchronizationService",
    ),
    "WebhookProcessor": ("app.services.webhook_processor", "WebhookProcessor"),
    # Messaging services
    "websocket_events": ("app.services.websocket_events", "websocket_events"),
    "UnifiedWebSocketConnectionManager": (
        "app.services.websocket",
        "UnifiedWebSocketConnectionManager",
    ),
    # Utility services
    "EnhancedTemplateLoader": (
        "app.services.template_loader_pkg",
        "EnhancedTemplateLoader",
    ),
    "LocalizationService": ("app.services.localization", "LocalizationService"),
    # Reporting services
    "ReportService": ("app.services.reporting", "ReportService"),
    "EnhancedReportsService": ("app.services.reporting", "EnhancedReportsService"),
    "QuizReportGenerator": ("app.services.reporting", "QuizReportGenerator"),
    # Monitoring services
    "PerformanceMonitoringService": (
        "app.services.performance_monitoring",
        "PerformanceMonitoringService",
    ),
    "FlowMonitoringService": ("app.services.flow_monitoring", "FlowMonitoringService"),
    "DataCorruptionDetector": ("app.services.data_corruption", "DataCorruptionDetector"),
    # Error handling services
    "ErrorRecoveryService": ("app.services.error_recovery", "ErrorRecoveryService"),
    "AutomatedRecoveryService": (
        "app.services.automated_recovery_pkg",
        "AutomatedRecoveryService",
    ),
    "CriticalErrorEscalationService": (
        "app.services.critical_error_escalation_pkg",
        "CriticalErrorEscalationService",
    ),
}

__all__ = sorted(_SERVICE_EXPORTS.keys())


def __getattr__(name: str):
    if name not in _SERVICE_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_path, attr_name = _SERVICE_EXPORTS[name]
    module = import_module(module_path)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
