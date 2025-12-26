"""
Flow Core Module - Domain Services for Flow Processing.

This module provides a clean, modular architecture for patient treatment
flow processing with domain-driven design principles.

Architecture:
    - FlowService: Main orchestrator (primary entry point)
    - FlowIntegrityService: State validation and transitions
    - MessageHandler: Message creation and delivery
    - FlowScheduler: Scheduling and timing logic
    - MessageTemplateLoader: Template loading and fallbacks
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
    FlowEngineIntegrationService is aliased to FlowService for backward
    compatibility. Old imports will continue to work:

    from app.domain.flows.core import FlowEngineIntegrationService
"""

from __future__ import annotations

from .analytics_tracker import AnalyticsTracker
from .flow_service import (
    FlowEngineIntegrationService,
    FlowService,
    get_flow_integration_service,
)
from .message_handler import MessageHandler, SchedulerError
from .message_template_loader import MessageTemplateLoader
from .scheduling import FlowScheduler
from .state_machine import FlowIntegrityService

__all__ = [
    # Main service (primary entry point)
    "FlowService",
    # Specialized domain services
    "FlowIntegrityService",
    "MessageHandler",
    "FlowScheduler",
    "MessageTemplateLoader",
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
__description__ = "Domain services for patient treatment flow processing"
