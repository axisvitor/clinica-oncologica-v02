"""
Flow Services Module - Consolidated Flow Management System (QW-021).

This module provides a unified, consolidated flow management system with
clear separation of concerns and improved architecture.

Consolidation Progress:
    Target: 30 files (15,000 LOC) → 6-8 files (6,500-8,000 LOC)
    Current Phase: Week 2 - Implementation (Foundation + Core)
    Status: Foundation Complete ✅, Core In Progress 🔄

Consolidated Components (Current):
    ✅ types.py (510 LOC) - Type system (enums, models)
    ✅ config.py (458 LOC) - Configuration system
    ✅ core/engine.py (605 LOC) - Flow execution engine
    ✅ core/validator.py (430 LOC) - Validation logic
    ✅ core/error_handler.py (385 LOC) - Error handling
    ✅ manager.py (578 LOC) - Main orchestrator
    ✅ adapter.py (420 LOC) - Backward compatibility
    ✅ analytics/ (2,587 LOC) - Analytics, metrics, monitoring, events
    ✅ templates/ (1,928 LOC) - Template management, validation, storage
    ✅ integrations/ (1,704 LOC) - Quiz, AI, and service integrations

Legacy Files (To Be Deprecated):
    This consolidates functionality from:
    - orchestrators/flow_orchestrator.py (1,767 LOC)
    - flow.py (1,524 LOC)
    - flow_error_handler.py (1,444 LOC)
    - flow_engine.py (1,359 LOC)
    - quiz_flow_integration.py (1,261 LOC)
    - enhanced_flow_engine.py (450 LOC)
    - flow_core.py (670 LOC)
    - flow_analytics.py (735 LOC)
    - flow_dashboard.py (797 LOC)
    - flow_data_integrity.py (855 LOC)
    - flow_engine_ai_integration.py (259 LOC)
    - flow_event_broadcaster.py (506 LOC)
    - flow_integrity.py (474 LOC)
    - flow_management.py (438 LOC)
    - flow_monitoring.py (738 LOC)
    - flow_template.py (343 LOC)
    - flow_validation.py (527 LOC)
    - quiz_flow_integration_service.py (371 LOC)
    Total: 18 files, ~14,518 LOC

    Consolidated To: 8 modules (~9,605 LOC)
    Reduction: ~5,000 LOC (~34% reduction)

Public API:
    Core Components:
        - FlowManager: Main orchestrator for flow operations
        - FlowEngine: Core execution logic for steps
        - FlowValidator: Flow and step validation
        - FlowErrorHandler: Error handling and recovery

    Analytics:
        - FlowAnalytics: Main analytics service
        - FlowMetricsCollector: Metrics collection
        - FlowEventBroadcaster: Event broadcasting
        - FlowMonitor: Health monitoring

    Templates:
        - FlowTemplateManager: Template management
        - FlowTemplateValidator: Template validation
        - FlowTemplateRepository: Template storage

    Integrations:
        - FlowIntegrationManager: Integration coordinator
        - QuizFlowIntegration: Quiz service integration
        - AIFlowIntegration: AI service integration

    Types:
        - FlowType, FlowStatus, FlowStepType, etc. (enums)
        - FlowContext, FlowTemplate, FlowEvent (models)

    Configuration:
        - get_flow_config(): Global configuration accessor
        - FlowFeatureFlags: Migration feature flags

Example Usage:
    >>> from app.services.flow import FlowManager, FlowType
    >>> from app.services.flow.config import get_flow_config
    >>>
    >>> # Check if consolidated system is enabled
    >>> config = get_flow_config()
    >>> if config.is_consolidated_enabled():
    ...     # Use new consolidated system
    ...     manager = FlowManager(db)
    ...     flow_id = await manager.start_flow(
    ...         patient_id=patient_id,
    ...         flow_type=FlowType.DAILY_CHECKIN
    ...     )
    ...     await manager.advance_flow(flow_id)
    ... else:
    ...     # Use legacy system (fallback)
    ...     from app.services.flow_engine import FlowEngine
    ...     engine = FlowEngine(db)

Migration Strategy:
    1. Feature flag: USE_CONSOLIDATED_FLOWS (default: False)
    2. Gradual rollout: 0% → 10% → 50% → 100%
    3. Backward compatibility via adapter pattern
    4. Legacy deprecation warnings
    5. Cleanup after 2-4 weeks of stable operation

Version History:
    - v1.0: Legacy system (30 files, 15,000 LOC)
    - v2.0: Consolidated system (QW-021) - IN PROGRESS
"""

from typing import TYPE_CHECKING

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

# Import core components (implementation)
from .manager import FlowManager
from .core.engine import FlowEngine
from .adapter import FlowManagerAdapter, get_enhanced_flow_engine

# Import core components
from .core.validator import FlowValidator
from .core.error_handler import FlowErrorHandler

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

# Import integration components
from .integrations import (
    FlowIntegrationManager,
    QuizFlowIntegration,
    AIFlowIntegration,
    get_integration_manager,
)


# ============================================================================
# Factory Functions (for gradual migration)
# ============================================================================


def get_flow_manager(db, **kwargs):
    """
    Get flow manager instance.

    Factory function that respects feature flags and provides
    backward compatibility during migration.

    Args:
        db: Database session
        **kwargs: Additional configuration

    Returns:
        FlowManager instance (new) or FlowManagerAdapter (compatibility)

    Example:
        >>> manager = get_flow_manager(db)
        >>> flow_id = await manager.start_flow(patient_id, FlowType.DAILY_CHECKIN)
    """
    config = get_flow_config()

    if config.is_consolidated_enabled():
        # Use new consolidated system
        return FlowManager(db, **kwargs)
    else:
        # Use adapter for backward compatibility
        import warnings

        if config.feature_flags.show_legacy_deprecation_warnings:
            warnings.warn(
                "Using legacy flow system via adapter. "
                "Enable USE_CONSOLIDATED_FLOWS=True to use new system (QW-021).",
                DeprecationWarning,
                stacklevel=2,
            )

        return FlowManagerAdapter(db, show_warnings=False)


# ============================================================================
# Backward Compatibility Aliases
# ============================================================================

# Alias for legacy FlowEngineIntegrationService
# This maintains compatibility with code that imports:
# from app.services.flow import FlowEngineIntegrationService
# The actual class exists in app.services.flow module (legacy file)
# We import it here for backward compatibility
import sys

if "app.services.flow" in sys.modules:
    # If flow.py is already loaded, import from it
    try:
        from app.services import flow as _flow_module

        if hasattr(_flow_module, "FlowEngineIntegrationService"):
            FlowEngineIntegrationService = _flow_module.FlowEngineIntegrationService
        else:
            # Fallback to FlowIntegrationManager
            FlowEngineIntegrationService = FlowIntegrationManager
    except (ImportError, AttributeError):
        # Fallback to FlowIntegrationManager
        FlowEngineIntegrationService = FlowIntegrationManager
else:
    # Not loaded yet, use FlowIntegrationManager as alias
    FlowEngineIntegrationService = FlowIntegrationManager

# ============================================================================
# Public Exports
# ============================================================================

__all__ = [
    # Main Components
    "FlowManager",
    "FlowEngine",
    "FlowValidator",
    "FlowErrorHandler",
    "FlowManagerAdapter",
    "get_flow_manager",
    "get_enhanced_flow_engine",
    # Legacy Compatibility
    "FlowEngineIntegrationService",
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
    # Integrations
    "FlowIntegrationManager",
    "QuizFlowIntegration",
    "AIFlowIntegration",
    "get_integration_manager",
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

__version__ = "2.0.0-beta"  # QW-021 consolidation in progress
__consolidation__ = "QW-021"
__status__ = "Week 2 - Implementation Complete (Analytics, Templates, Integrations)"
__progress__ = "95%"  # ~9,605 LOC consolidated (Target: 6,500-8,000 LOC)
