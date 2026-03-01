from .operations import (
    FLOW_ADVANCE_BLOCKED_CODE,
    FLOW_ADVANCE_BLOCKED_MESSAGE,
    FLOW_ADVANCE_BLOCKED_REASON,
    NotFoundError,
    ValidationError,
    FlowCoreOperationsMixin,
)
from .template_binding import FlowCoreTemplateBindingMixin
from .transitions import FlowCoreTransitionsMixin


class FlowCore(
    FlowCoreTransitionsMixin,
    FlowCoreTemplateBindingMixin,
    FlowCoreOperationsMixin,
):
    """Composed flow core service preserving legacy contract."""


__all__ = [
    "FLOW_ADVANCE_BLOCKED_CODE",
    "FLOW_ADVANCE_BLOCKED_MESSAGE",
    "FLOW_ADVANCE_BLOCKED_REASON",
    "FlowCore",
    "NotFoundError",
    "ValidationError",
]
