"""
Follow-up Action System package.
Provides automatic follow-up message generation, escalation logic,
healthcare provider notifications, and conversation continuity.

Modular architecture:
- context/: Conversation context management and patient context building
- generators/: Follow-up message generation (empathy, medical concerns)
- scheduling/: Action scheduling (messages, escalations, provider alerts)
- execution/: Action execution logic
- enums: Enumeration types for follow-up types, escalation levels, and notification channels
- models: Data models for actions, alerts, and conversation context
- escalation: Escalation alert creation and management
- notifications: Provider notification delivery through multiple channels
- service: Main orchestrator coordinating all components
"""

# Import enums
from .enums import FollowUpType, EscalationLevel, NotificationChannel

# Import models
from .models import (
    FollowUpAction,
    EscalationAlert,
    ConversationContext,
    ProviderNotification,
)

# Import main service
from .service import FollowUpSystemService, get_follow_up_system_service

# Import public sub-services
from .generators import ResponseGenerator
from .escalation import EscalationManager
from .notifications import NotificationService

# Import new modular components
from .context import ContextManager, ContextBuilder
from .generators import EmpathyGenerator, MedicalConcernGenerator, BaseGenerator
from .scheduling import ActionScheduler, FollowUpMessageScheduler, EscalationScheduler
from .execution import ActionExecutor, MessageExecutor

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
    # Public sub-services
    "ResponseGenerator",
    "EscalationManager",
    "NotificationService",
    # New modular components
    "ContextManager",
    "ContextBuilder",
    "EmpathyGenerator",
    "MedicalConcernGenerator",
    "BaseGenerator",
    "ActionScheduler",
    "FollowUpMessageScheduler",
    "EscalationScheduler",
    "ActionExecutor",
    "MessageExecutor",
]
