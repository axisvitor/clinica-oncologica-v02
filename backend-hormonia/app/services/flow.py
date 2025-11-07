"""
DEPRECATED: Flow Engine Integration Service.

This file has been refactored into modular components for better maintainability.
Please use the new location instead:

    from app.domain.flows.core import FlowService

Original 1,524-line service has been split into 6 focused modules:
- flow_service.py: Main orchestrator (~426 lines)
- state_machine.py: State transitions & validation (~269 lines)
- message_handler.py: Message sending & composition (~511 lines)
- scheduling.py: Flow scheduling & timing (~299 lines)
- template_manager.py: Template loading & rendering (~223 lines)
- analytics_tracker.py: Flow analytics & metrics (~326 lines)

This wrapper provides backward compatibility during migration.
"""
import warnings
import logging
from typing import Optional, Any, Tuple, List
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session

# Import the new modular implementation
from app.domain.flows.core import (
    FlowService as NewFlowService,
    FlowIntegrityService as NewFlowIntegrityService,
    get_flow_integration_service as new_get_flow_integration_service,
    SchedulerError
)

logger = logging.getLogger(__name__)

# Issue deprecation warning once at module load
warnings.warn(
    "app.services.flow module is deprecated and will be removed in a future version. "
    "Please update imports to use app.domain.flows.core instead:\n"
    "  from app.domain.flows.core import FlowService\n"
    "The service has been refactored into 6 focused modules for better maintainability.",
    DeprecationWarning,
    stacklevel=2
)


class FlowEngineIntegrationService:
    """
    DEPRECATED: Use app.domain.flows.core.FlowService instead.

    This is a backward compatibility wrapper that delegates all calls
    to the new modular implementation.

    Example migration:
        OLD:
            from app.services.flow import FlowEngineIntegrationService
            service = FlowEngineIntegrationService(db)

        NEW:
            from app.domain.flows.core import FlowService
            service = FlowService(db)
    """

    def __init__(self, *args, **kwargs):
        """Initialize with deprecation warning."""
        # Log deprecation at INFO level for visibility
        logger.info(
            "DEPRECATION: FlowEngineIntegrationService from app.services.flow is deprecated. "
            "Use app.domain.flows.core.FlowService instead."
        )

        # Initialize the new implementation
        self._impl = NewFlowService(*args, **kwargs)

        # Track deprecation for monitoring
        self._deprecation_logged = True

    def __getattr__(self, name):
        """Delegate all attribute access to new implementation."""
        return getattr(self._impl, name)

    # Explicitly proxy key methods for better IDE support
    async def process_daily_flows(self, limit: int = 1000) -> dict[str, Any]:
        """Process daily flows (delegated to new implementation)."""
        return await self._impl.process_daily_flows(limit)

    async def generate_personalized_message_preview(self,
                                                   patient_id: UUID,
                                                   flow_type: str,
                                                   day: int) -> dict[str, Any]:
        """Generate message preview (delegated to new implementation)."""
        return await self._impl.generate_personalized_message_preview(patient_id, flow_type, day)

    async def process_patient_response_with_flow_context(self,
                                                       patient_id: UUID,
                                                       response_text: str,
                                                       message_id: Optional[UUID] = None) -> dict[str, Any]:
        """Process patient response (delegated to new implementation)."""
        return await self._impl.process_patient_response_with_flow_context(
            patient_id, response_text, message_id
        )

    async def get_flow_processing_metrics(self,
                                        date_range: Optional[Tuple[datetime, datetime]] = None) -> dict[str, Any]:
        """Get metrics (delegated to new implementation)."""
        return await self._impl.get_flow_processing_metrics(date_range)

    async def health_check(self) -> dict[str, Any]:
        """Health check (delegated to new implementation)."""
        return await self._impl.health_check()


class FlowIntegrityService:
    """
    DEPRECATED: Use app.domain.flows.core.FlowIntegrityService instead.

    Backward compatibility wrapper for FlowIntegrityService.
    """

    def __init__(self, db: Session):
        logger.info(
            "DEPRECATION: FlowIntegrityService from app.services.flow is deprecated. "
            "Use app.domain.flows.core.FlowIntegrityService instead."
        )
        self._impl = NewFlowIntegrityService(db)

    def __getattr__(self, name):
        """Delegate all attribute access to new implementation."""
        return getattr(self._impl, name)

    async def validate_flow_consistency(self, flow_state) -> None:
        """Validate flow consistency (delegated to new implementation)."""
        return await self._impl.validate_flow_consistency(flow_state)

    async def prevent_invalid_transitions(self, patient_id: UUID, new_flow_type: str) -> None:
        """Prevent invalid transitions (delegated to new implementation)."""
        return await self._impl.prevent_invalid_transitions(patient_id, new_flow_type)

    async def validate_referential_integrity(self, flow_state) -> List[str]:
        """Validate referential integrity (delegated to new implementation)."""
        return await self._impl.validate_referential_integrity(flow_state)


def get_flow_integration_service(db: Session) -> FlowEngineIntegrationService:
    """
    DEPRECATED: Use app.domain.flows.core.get_flow_integration_service instead.

    Factory function for backward compatibility.

    Args:
        db: Database session

    Returns:
        FlowEngineIntegrationService instance (wrapped new implementation)
    """
    logger.info(
        "DEPRECATION: get_flow_integration_service from app.services.flow is deprecated. "
        "Use app.domain.flows.core.get_flow_integration_service instead."
    )
    return FlowEngineIntegrationService(db)


# Re-export exception for backward compatibility
__all__ = [
    'FlowEngineIntegrationService',
    'FlowIntegrityService',
    'get_flow_integration_service',
    'SchedulerError'
]
