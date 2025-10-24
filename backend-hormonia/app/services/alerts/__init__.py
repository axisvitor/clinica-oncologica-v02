"""
Unified Alert System - Public API.

This module provides a consolidated alert management system that replaces
the fragmented alert services with a unified, modular architecture.

Main Components:
- AlertManager: Core orchestrator for alert operations
- RuleEngine: Generic rule evaluation engine
- NotificationDispatcher: Multi-channel notification dispatch
- EscalationManager: Alert escalation management
- AlertProcessor: Alert processing pipeline
- DatabaseMonitor: Infrastructure health monitoring

Usage:
    >>> from app.services.alerts import (
    ...     get_alert_manager,
    ...     get_rule_engine,
    ...     get_notification_dispatcher,
    ... )
    >>>
    >>> # Initialize alert system
    >>> alert_manager = get_alert_manager()
    >>>
    >>> # Evaluate patient alerts
    >>> alerts = await alert_manager.evaluate_patient_alerts(
    ...     patient_id=patient_id,
    ...     context={
    ...         "last_inbound_message_at": last_message_time,
    ...         "quiz_responses_count": quiz_count,
    ...         "sentiment_scores": sentiment_scores,
    ...     }
    ... )
    >>>
    >>> # Process and notify
    >>> for alert in alerts:
    ...     result = await alert_manager.process_alert(alert)

Architecture:
    app/services/alerts/
    ├── __init__.py                    # This file (public API)
    ├── types.py                       # Shared types and enums
    ├── config.py                      # Configuration system
    ├── alert_manager.py               # Core orchestrator
    │
    ├── evaluation/                    # Alert evaluation
    │   ├── rule_engine.py            # Generic rule engine
    │   └── patient_rules.py          # Patient-specific rules
    │
    ├── notification/                  # Notification dispatch
    │   ├── dispatcher.py             # Multi-channel dispatcher
    │   ├── channels.py               # Channel implementations
    │   └── escalation.py             # Escalation logic
    │
    ├── processing/                    # Alert processing
    │   └── processor.py              # Processing pipeline
    │
    └── monitoring/                    # Infrastructure monitoring
        └── database_monitor.py       # Database health monitoring
"""

from .types import (
    # Enums
    AlertSeverity,
    AlertStatus,
    AlertRuleType,
    NotificationChannel,
    EscalationStrategy,
    # Models
    Alert,
    AlertRule,
    AlertEvaluation,
    NotificationTarget,
    NotificationResult,
    DispatchResult,
    EscalationRule,
    AlertStatistics,
    DashboardData,
    ChannelConfig,
    MonitoringThresholds,
)

from .config import (
    # Configuration
    AlertSystemConfig,
    RuleConfig,
    get_config,
    set_config,
    reset_config,
    # Channel configs
    EmailChannelConfig,
    WebSocketChannelConfig,
    WebhookChannelConfig,
    SlackChannelConfig,
    PagerDutyChannelConfig,
)

from .alert_manager import (
    AlertManager,
    get_alert_manager,
    set_alert_manager,
)

from .evaluation.rule_engine import (
    RuleEngine,
    get_rule_engine,
    set_rule_engine,
)

from .evaluation.patient_rules import (
    # Patient rule evaluators
    evaluate_no_response,
    evaluate_missed_quiz,
    evaluate_negative_sentiment,
    evaluate_treatment_adherence,
    evaluate_emergency_keywords,
    # Registry
    PATIENT_EVALUATORS,
    register_patient_evaluators,
)

from .notification.dispatcher import (
    NotificationDispatcher,
    ChannelHandler,
    get_notification_dispatcher,
    set_notification_dispatcher,
)

from .notification.channels import (
    # Channel handlers
    EmailChannelHandler,
    WebSocketChannelHandler,
    WebhookChannelHandler,
    DashboardChannelHandler,
    SlackChannelHandler,
    PagerDutyChannelHandler,
    SMSChannelHandler,
)

from .notification.escalation import (
    EscalationManager,
    Escalation,
    get_escalation_manager,
    set_escalation_manager,
)

from .processing.processor import (
    AlertProcessor,
    get_alert_processor,
    set_alert_processor,
)

from .monitoring.database_monitor import (
    DatabaseMonitor,
    get_database_monitor,
    set_database_monitor,
    start_monitoring,
)

from .adapter import (
    AlertManagerAdapter,
)

__all__ = [
    # ===== TYPES =====
    # Enums
    "AlertSeverity",
    "AlertStatus",
    "AlertRuleType",
    "NotificationChannel",
    "EscalationStrategy",
    # Models
    "Alert",
    "AlertRule",
    "AlertEvaluation",
    "NotificationTarget",
    "NotificationResult",
    "DispatchResult",
    "EscalationRule",
    "AlertStatistics",
    "DashboardData",
    "ChannelConfig",
    "MonitoringThresholds",
    # ===== CONFIG =====
    "AlertSystemConfig",
    "RuleConfig",
    "get_config",
    "set_config",
    "reset_config",
    "EmailChannelConfig",
    "WebSocketChannelConfig",
    "WebhookChannelConfig",
    "SlackChannelConfig",
    "PagerDutyChannelConfig",
    # ===== CORE COMPONENTS =====
    "AlertManager",
    "get_alert_manager",
    "set_alert_manager",
    "RuleEngine",
    "get_rule_engine",
    "set_rule_engine",
    # ===== EVALUATION =====
    "evaluate_no_response",
    "evaluate_missed_quiz",
    "evaluate_negative_sentiment",
    "evaluate_treatment_adherence",
    "evaluate_emergency_keywords",
    "PATIENT_EVALUATORS",
    "register_patient_evaluators",
    # ===== NOTIFICATION =====
    "NotificationDispatcher",
    "ChannelHandler",
    "get_notification_dispatcher",
    "set_notification_dispatcher",
    # Channel handlers
    "EmailChannelHandler",
    "WebSocketChannelHandler",
    "WebhookChannelHandler",
    "DashboardChannelHandler",
    "SlackChannelHandler",
    "PagerDutyChannelHandler",
    "SMSChannelHandler",
    # Escalation
    "EscalationManager",
    "Escalation",
    "get_escalation_manager",
    "set_escalation_manager",
    # ===== PROCESSING =====
    "AlertProcessor",
    "get_alert_processor",
    "set_alert_processor",
    # ===== MONITORING =====
    "DatabaseMonitor",
    "get_database_monitor",
    "set_database_monitor",
    "start_monitoring",
    # ===== ADAPTER (MIGRATION BRIDGE) =====
    "AlertManagerAdapter",
]

# Package metadata
__version__ = "1.0.0"
__author__ = "Clínica Oncológica Development Team"
__description__ = "Unified Alert Management System"


def initialize_alert_system(
    config: AlertSystemConfig = None,
) -> AlertManager:
    """
    Initialize the complete alert system with all components.

    This is a convenience function that sets up:
    - AlertManager with all dependencies
    - RuleEngine with patient evaluators
    - NotificationDispatcher with channel handlers
    - EscalationManager
    - AlertProcessor
    - DatabaseMonitor

    Args:
        config: Optional custom configuration

    Returns:
        Configured AlertManager instance

    Example:
        >>> from app.services.alerts import initialize_alert_system
        >>>
        >>> alert_manager = initialize_alert_system()
        >>>
        >>> # System is ready to use
        >>> alerts = await alert_manager.evaluate_patient_alerts(...)
    """
    # Set config if provided
    if config:
        set_config(config)

    # Initialize components
    rule_engine = get_rule_engine()
    processor = get_alert_processor()
    dispatcher = get_notification_dispatcher()
    escalation_mgr = get_escalation_manager()
    db_monitor = get_database_monitor()

    # Register patient evaluators
    register_patient_evaluators(rule_engine)

    # Register default channel handlers
    _register_default_channels(dispatcher)

    # Create AlertManager with dependencies
    alert_manager = AlertManager(
        rule_engine=rule_engine,
        processor=processor,
        dispatcher=dispatcher,
    )

    # Set as global instance
    set_alert_manager(alert_manager)

    # Connect database monitor to alert manager
    db_monitor.alert_manager = alert_manager

    return alert_manager


def _register_default_channels(dispatcher: NotificationDispatcher) -> None:
    """Register default notification channels."""
    # Email
    email_handler = EmailChannelHandler()
    dispatcher.register_channel(NotificationChannel.EMAIL, email_handler)

    # WebSocket
    websocket_handler = WebSocketChannelHandler()
    dispatcher.register_channel(NotificationChannel.WEBSOCKET, websocket_handler)

    # Webhook
    webhook_handler = WebhookChannelHandler()
    dispatcher.register_channel(NotificationChannel.WEBHOOK, webhook_handler)

    # Dashboard
    dashboard_handler = DashboardChannelHandler()
    dispatcher.register_channel(NotificationChannel.DASHBOARD, dashboard_handler)

    # Stubs (for future implementation)
    slack_handler = SlackChannelHandler()
    dispatcher.register_channel(NotificationChannel.SLACK, slack_handler)

    pagerduty_handler = PagerDutyChannelHandler()
    dispatcher.register_channel(NotificationChannel.PAGERDUTY, pagerduty_handler)

    sms_handler = SMSChannelHandler()
    dispatcher.register_channel(NotificationChannel.SMS, sms_handler)
