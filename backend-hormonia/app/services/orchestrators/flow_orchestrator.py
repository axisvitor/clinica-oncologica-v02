"""
BACKWARD COMPATIBILITY WRAPPER for FlowOrchestrator

⚠️  DEPRECATED: This module is deprecated and provided for backward compatibility only.
    Please update your imports to use the new domain-driven architecture:

    OLD: from app.services.orchestrators.flow_orchestrator import FlowOrchestrator
    NEW: from app.domain.flows import FlowOrchestrator

The original 1,767-line flow_orchestrator.py has been refactored into 8 focused
domain modules under app/domain/flows/ following Domain-Driven Design principles:

    app/domain/flows/
    ├── orchestrator.py              # Thin orchestrator (coordination)
    ├── state/                       # State management
    │   ├── state_manager.py         # State operations and caching
    │   └── state_validator.py       # State validation rules
    ├── messaging/                   # Message handling
    │   ├── message_composer.py      # AI-powered composition
    │   └── message_sender.py        # Delivery and scheduling
    ├── scheduling/                  # Scheduling logic
    │   ├── quiz_scheduler.py        # Quiz scheduling
    │   └── follow_up_scheduler.py   # Follow-up scheduling
    ├── templates/                   # Template management
    │   ├── renderer.py              # Template rendering
    │   └── context_builder.py       # Context creation
    ├── rules/                       # Business rules
    │   ├── engine.py                # Rule execution
    │   └── evaluator.py             # Condition evaluation
    ├── ab_testing/                  # A/B testing
    │   ├── manager.py               # Test management
    │   └── variant_selector.py      # Variant selection
    ├── analytics/                   # Analytics
    │   ├── collector.py             # Event collection
    │   └── metrics.py               # Metric computation
    └── error_handling/              # Error handling
        ├── handler.py               # Error handling
        └── recovery.py              # Recovery strategies

Benefits of the new architecture:
- Single Responsibility: Each module has one clear purpose
- Testability: Easier to unit test focused modules
- Maintainability: Smaller files (100-220 lines vs 1,767)
- Extensibility: Easy to add new features to specific modules
- Readability: Clear separation of concerns

Migration Guide:
1. Update imports: Use 'from app.domain.flows import FlowOrchestrator'
2. Functionality is identical - no API changes
3. All existing tests should pass without modification
4. Remove this file after migration is complete

Refactor Date: 2025-11-07
Original File: Backed up as flow_orchestrator_ORIGINAL_BACKUP.py
"""

import warnings
from typing import Dict, Any, List, Optional, Callable
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

# Import from new location
from app.domain.flows import (
    FlowOrchestrator as NewFlowOrchestrator,
    FlowExecutionContext,
    FlowExecutionResult,
    FlowExecutionState,
    FlowOperationType,
    create_flow_orchestrator as new_create_flow_orchestrator,
    get_flow_orchestrator as new_get_flow_orchestrator
)

# Re-export all types for backward compatibility
__all__ = [
    'FlowOrchestrator',
    'FlowExecutionContext',
    'FlowExecutionResult',
    'FlowExecutionState',
    'FlowOperationType',
    'create_flow_orchestrator',
    'get_flow_orchestrator'
]


class FlowOrchestrator:
    """
    DEPRECATED: Backward compatibility wrapper for FlowOrchestrator.

    This class wraps the new app.domain.flows.FlowOrchestrator and provides
    the same interface for existing code. All methods delegate to the new
    implementation.

    Please migrate to: from app.domain.flows import FlowOrchestrator
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize FlowOrchestrator (deprecated).

        Warns about deprecation and delegates to new implementation.
        """
        warnings.warn(
            "app.services.orchestrators.flow_orchestrator.FlowOrchestrator is deprecated. "
            "Use 'from app.domain.flows import FlowOrchestrator' instead. "
            "This wrapper will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2
        )

        # Create instance of new implementation
        self._impl = NewFlowOrchestrator(*args, **kwargs)

    def __getattr__(self, name):
        """
        Delegate all attribute access to new implementation.

        This allows the wrapper to be a transparent proxy that forwards
        all method calls and attribute access to the new FlowOrchestrator.
        """
        return getattr(self._impl, name)

    def __repr__(self):
        """String representation showing deprecation."""
        return (
            f"<FlowOrchestrator (DEPRECATED WRAPPER) - "
            f"Please use app.domain.flows.FlowOrchestrator>"
        )


def create_flow_orchestrator(
    db: Session,
    ai_service: Optional[Any] = None,
    quiz_service: Optional[Any] = None,
    whatsapp_service: Optional[Any] = None,
    template_loader: Optional[Any] = None,
    analytics_service: Optional[Any] = None,
    message_scheduler: Optional[Any] = None
) -> FlowOrchestrator:
    """
    DEPRECATED: Create FlowOrchestrator instance.

    Use: from app.domain.flows import create_flow_orchestrator

    This function wraps the new implementation for backward compatibility.
    """
    warnings.warn(
        "app.services.orchestrators.flow_orchestrator.create_flow_orchestrator is deprecated. "
        "Use 'from app.domain.flows import create_flow_orchestrator' instead.",
        DeprecationWarning,
        stacklevel=2
    )

    # Create new orchestrator and wrap it
    new_orchestrator = new_create_flow_orchestrator(
        db=db,
        ai_service=ai_service,
        quiz_service=quiz_service,
        whatsapp_service=whatsapp_service,
        template_loader=template_loader,
        analytics_service=analytics_service,
        message_scheduler=message_scheduler
    )

    # Return wrapped instance
    wrapper = FlowOrchestrator.__new__(FlowOrchestrator)
    wrapper._impl = new_orchestrator
    return wrapper


def get_flow_orchestrator(
    db: Session,
    cache_key: str = "default"
) -> FlowOrchestrator:
    """
    DEPRECATED: Get cached FlowOrchestrator instance.

    Use: from app.domain.flows import get_flow_orchestrator

    This function wraps the new implementation for backward compatibility.
    """
    warnings.warn(
        "app.services.orchestrators.flow_orchestrator.get_flow_orchestrator is deprecated. "
        "Use 'from app.domain.flows import get_flow_orchestrator' instead.",
        DeprecationWarning,
        stacklevel=2
    )

    # Get new orchestrator and wrap it
    new_orchestrator = new_get_flow_orchestrator(db, cache_key)

    # Return wrapped instance
    wrapper = FlowOrchestrator.__new__(FlowOrchestrator)
    wrapper._impl = new_orchestrator
    return wrapper


# Print deprecation notice when module is imported
def _show_deprecation_notice():
    """Show deprecation notice on module import."""
    import sys
    if 'pytest' not in sys.modules:  # Don't show during tests
        print(
            "\n⚠️  DEPRECATION WARNING ⚠️\n"
            "app.services.orchestrators.flow_orchestrator is deprecated.\n"
            "Please update your imports to:\n"
            "    from app.domain.flows import FlowOrchestrator\n"
            "See module docstring for full migration guide.\n"
        )


# Show notice on import (once per session)
_show_deprecation_notice()
