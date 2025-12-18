"""
Flow Core Module - Refactored Flow Service Components.

This module provides a clean, modular architecture for flow processing:

- FlowService: Main orchestrator (use this as primary entry point)
- StateMachine (FlowIntegrityService): State validation and transitions
- MessageHandler: Message creation and delivery
- FlowScheduler: Scheduling and timing logic
- TemplateManager: Template loading and fallbacks
- AnalyticsTracker: Metrics and response processing

Usage:
    from app.domain.flows.core import FlowService

    # Initialize service
    flow_service = FlowService(db)

    # Process daily flows
    results = await flow_service.process_daily_flows()

    # Generate message preview
    preview = await flow_service.generate_personalized_message_preview(
        patient_id, flow_type, day
    )

Legacy Compatibility:
    The original FlowEngineIntegrationService is aliased to FlowService
    for backward compatibility. Old imports will continue to work:

    from app.domain.flows.core import FlowEngineIntegrationService
"""

from .state_machine import FlowIntegrityService
from .message_handler import MessageHandler, SchedulerError
from .scheduling import FlowScheduler
from .message_template_loader import MessageTemplateLoader  # noqa: F401 - exported
from .analytics_tracker import AnalyticsTracker
from .flow_service import (
    FlowService,
    FlowEngineIntegrationService,  # Legacy alias
    get_flow_integration_service,
)

__all__ = [
    # Main service (primary entry point)
    "FlowService",
    # Specialized modules (for advanced usage)
    "FlowIntegrityService",
    "MessageHandler",
    "FlowScheduler",
    "TemplateManager",
    "AnalyticsTracker",
    # Factory function
    "get_flow_integration_service",
    # Legacy compatibility
    "FlowEngineIntegrationService",
    # Exceptions
    "SchedulerError",
]

# Module metadata
__version__ = "2.0.0"
__author__ = "Backend Hormonia Team"
__description__ = "Refactored flow service with domain-driven design"
