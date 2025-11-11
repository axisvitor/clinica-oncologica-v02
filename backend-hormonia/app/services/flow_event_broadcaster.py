"""
DEPRECATED: This module has been moved to app.domain.flows.events

This file is kept for backward compatibility only.
Please update your imports to:
    from app.domain.flows.events import FlowEventBroadcaster
"""
import warnings

warnings.warn(
    "flow_event_broadcaster has been moved to app.domain.flows.events. "
    "Please update your imports.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from app.domain.flows.events import FlowEventBroadcaster

# Provide a singleton instance to preserve the old import style
flow_event_broadcaster = FlowEventBroadcaster()

__all__ = ["FlowEventBroadcaster", "flow_event_broadcaster"]
