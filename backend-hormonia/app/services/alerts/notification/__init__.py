from typing import Any
"""
Alert notification submodule.

Provides multi-channel notification dispatch, channel handlers,
and escalation management for alert notifications.
"""

from .dispatcher import (
    NotificationDispatcher,
    ChannelHandler,
    get_notification_dispatcher,
    set_notification_dispatcher,
)

from .channels import (
    EmailChannelHandler,
    WebSocketChannelHandler,
    WebhookChannelHandler,
    DashboardChannelHandler,
    SlackChannelHandler,
    PagerDutyChannelHandler,
    SMSChannelHandler,
)

from .escalation import (
    EscalationManager,
    Escalation,
    get_escalation_manager,
    set_escalation_manager,
)

__all__ = [
    # Dispatcher
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
]
