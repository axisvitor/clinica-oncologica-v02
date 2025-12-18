"""
Enums for the Follow-up Action System.
Defines types, levels, and channels used throughout the follow-up system.
"""

from enum import Enum


class FollowUpType(str, Enum):
    """Types of follow-up actions."""

    EMPATHETIC_RESPONSE = "empathetic_response"
    MEDICAL_CLARIFICATION = "medical_clarification"
    ESCALATION_NOTIFICATION = "escalation_notification"
    PROVIDER_ALERT = "provider_alert"
    APPOINTMENT_SCHEDULING = "appointment_scheduling"
    MEDICATION_GUIDANCE = "medication_guidance"
    EMOTIONAL_SUPPORT = "emotional_support"
    TREATMENT_ENCOURAGEMENT = "treatment_encouragement"
    INFORMATION_REQUEST = "information_request"
    CONVERSATION_CONTINUATION = "conversation_continuation"


class EscalationLevel(str, Enum):
    """Escalation levels for healthcare provider notifications."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class NotificationChannel(str, Enum):
    """Channels for healthcare provider notifications."""

    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    DASHBOARD_ALERT = "dashboard_alert"
    PUSH_NOTIFICATION = "push_notification"
    PHONE_CALL = "phone_call"
