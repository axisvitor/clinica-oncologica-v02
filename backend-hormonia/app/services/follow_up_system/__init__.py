"""
Follow-up Action System package.
Provides automatic follow-up message generation, escalation logic,
healthcare provider notifications, and conversation continuity.

This package is organized into the following modules:
- enums: Enumeration types for follow-up types, escalation levels, and notification channels
- models: Data models for actions, alerts, and conversation context
- generators: Response generation logic for empathetic messages and clarifications
- escalation: Escalation alert creation and management
- notifications: Provider notification delivery through multiple channels
- service: Main service orchestrating all follow-up functionality
"""
# Import enums
from .enums import (
    FollowUpType,
    EscalationLevel,
    NotificationChannel
)

# Import models
from .models import (
    FollowUpAction,
    EscalationAlert,
    ConversationContext,
    ProviderNotification
)

# Import main service
from .service import (
    FollowUpSystemService,
    get_follow_up_system_service
)

# Import sub-services for advanced usage
from .generators import ResponseGenerator
from .escalation import EscalationManager
from .notifications import NotificationService

__all__ = [
    # Enums
    "FollowUpType",
    "EscalationLevel",
    "NotificationChannel",

    # Models
    "FollowUpAction",
    "EscalationAlert",
    "ConversationContext",
    "ProviderNotification",

    # Main service
    "FollowUpSystemService",
    "get_follow_up_system_service",

    # Sub-services
    "ResponseGenerator",
    "EscalationManager",
    "NotificationService",
]
