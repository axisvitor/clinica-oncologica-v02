"""
Flow Services Module - Canonical Production Flow System.

This module provides the public API for the canonical production flow system.
Canonical system: production (flow_core.py / EnhancedFlowEngine / PatientFlowService).

The QW-021 consolidation package (core/, errors/, execution/, integrations/,
validation/) has been fully deleted as part of Phase 5 flow consolidation.
All flow operations now route through the production system exclusively.

Public API:
    Types:
        - FlowType, FlowStatus, FlowStepType, etc. (enums)
        - FlowContext, FlowTemplate, FlowEvent (models)

    Configuration:
        - get_flow_config(): Global configuration accessor
        - FlowFeatureFlags: Patient-type routing flags for FlowDispatcher

    Analytics:
        - FlowAnalytics: Main analytics service
        - FlowMetricsCollector: Metrics collection
        - FlowEventBroadcaster: Event broadcasting
        - FlowMonitor: Health monitoring

    Templates:
        - FlowTemplateManager: Template management
        - FlowTemplateValidator: Template validation
        - FlowTemplateRepository: Template storage

Example Usage:
    >>> from app.services.flow import FlowType, FlowFeatureFlags
    >>> from app.services.flow.config import get_flow_config
    >>> from app.services.dispatcher import FlowDispatcher
    >>>
    >>> # Use the canonical production engine directly
    >>> from app.services.enhanced_flow_engine import EnhancedFlowEngine
    >>> engine = EnhancedFlowEngine(db)
    >>> await engine.advance_patient_flow(patient_id)
    >>>
    >>> # Route enrollment via FlowDispatcher
    >>> dispatcher = FlowDispatcher(db)
    >>> flow_state = await dispatcher.initialize_flow(patient)
"""

# Import configuration (always available)
from .config import (
    get_flow_config,
    reset_flow_config,
    FlowConfig,
    FlowFeatureFlags,
    FlowExecutionConfig,
    FlowTemplateConfig,
    FlowAnalyticsConfig,
    FlowIntegrationConfig,
    FlowErrorHandlingConfig,
)

# Import types (always available)
from .types import (
    # Enums
    FlowType,
    FlowStatus,
    FlowStepType,
    FlowStepStatus,
    FlowTransitionType,
    FlowPriority,
    FlowEventType,
    # Models
    FlowContext,
    FlowTemplate,
    FlowStepData,
    FlowEvent,
    FlowValidationResult,
    FlowMetrics,
    # Type Aliases
    FlowID,
    StepID,
    TemplateID,
)

# Import analytics components
from .analytics import (
    FlowAnalytics,
    FlowMetricsCollector,
    FlowEventBroadcaster,
    FlowMonitor,
    get_flow_analytics,
)

# Import template components
from .templates import (
    FlowTemplateManager,
    FlowTemplateValidator,
    FlowTemplateRepository,
    get_template_manager,
)


# ============================================================================
# Public Exports
# ============================================================================

__all__ = [
    # Analytics
    "FlowAnalytics",
    "FlowMetricsCollector",
    "FlowEventBroadcaster",
    "FlowMonitor",
    "get_flow_analytics",
    # Templates
    "FlowTemplateManager",
    "FlowTemplateValidator",
    "FlowTemplateRepository",
    "get_template_manager",
    # Configuration
    "FlowConfig",
    "get_flow_config",
    "reset_flow_config",
    "FlowFeatureFlags",
    "FlowExecutionConfig",
    "FlowTemplateConfig",
    "FlowAnalyticsConfig",
    "FlowIntegrationConfig",
    "FlowErrorHandlingConfig",
    # Enums
    "FlowType",
    "FlowStatus",
    "FlowStepType",
    "FlowStepStatus",
    "FlowTransitionType",
    "FlowPriority",
    "FlowEventType",
    # Models
    "FlowContext",
    "FlowTemplate",
    "FlowStepData",
    "FlowEvent",
    "FlowValidationResult",
    "FlowMetrics",
    # Type Aliases
    "FlowID",
    "StepID",
    "TemplateID",
]

__version__ = "3.0.0"
__status__ = "Production — canonical system: flow_core.py / EnhancedFlowEngine"
__progress__ = "100%"  # QW-021 package fully deleted; production system is sole canonical
