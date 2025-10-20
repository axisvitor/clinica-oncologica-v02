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
    ✅ manager.py (578 LOC) - Main orchestrator
    🔄 core/validator.py - Validation (pending)
    🔄 analytics/ - Analytics, monitoring, dashboard (pending)
    🔄 templates/ - Template management (pending)
    🔄 integrations/ - Quiz, AI integrations (pending)

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

Public API:
    Core Components:
        - FlowManager: Main orchestrator for flow operations
        - FlowEngine: Core execution logic for steps
        - FlowValidator: Flow and step validation (pending)

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

# Conditional imports for type checking
if TYPE_CHECKING:
    from .core.validator import FlowValidator
    from .core.error_handler import FlowErrorHandler
    from .core.event_broadcaster import FlowEventBroadcaster


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
        FlowManager instance (new) or legacy equivalent

    Example:
        >>> manager = get_flow_manager(db)
        >>> flow_id = await manager.start_flow(patient_id, FlowType.DAILY_CHECKIN)
    """
    config = get_flow_config()

    if config.is_consolidated_enabled():
        # Use new consolidated system
        return FlowManager(db, **kwargs)
    else:
        # Use legacy system (import only when needed)
        from app.services.flow_engine import FlowEngine as LegacyEngine
        import warnings

        if config.feature_flags.show_legacy_deprecation_warnings:
            warnings.warn(
                "Using legacy flow system. "
                "Enable USE_CONSOLIDATED_FLOWS=True to use new system (QW-021).",
                DeprecationWarning,
                stacklevel=2,
            )

        return LegacyEngine(db)


# ============================================================================
# Public Exports
# ============================================================================

__all__ = [
    # Main Components
    "FlowManager",
    "FlowEngine",
    "get_flow_manager",
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

__version__ = "2.0.0-alpha"  # QW-021 consolidation in progress
__consolidation__ = "QW-021"
__status__ = "Week 2 - Foundation + Core Implementation"
__progress__ = "35-40%"  # ~2,151 LOC / ~6,500 target
