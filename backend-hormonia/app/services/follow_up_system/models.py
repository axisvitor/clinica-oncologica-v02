"""
Data models for the Follow-up Action System.
Contains dataclasses for actions, alerts, and conversation context.
"""

from typing import List, Optional, Any
from datetime import datetime, timezone
from uuid import UUID

from .enums import FollowUpType, EscalationLevel, NotificationChannel
from app.services.analytics.data_extraction import MedicalConcernType


class FollowUpAction:
    """Follow-up action to be executed."""

    def __init__(
        self,
        action_id: UUID,
        patient_id: UUID,
        follow_up_type: FollowUpType,
        priority: str,
        scheduled_for: datetime,
        parameters: dict[str, Any],
        created_by: str = "system",
    ):
        self.action_id = action_id
        self.patient_id = patient_id
        self.follow_up_type = follow_up_type
        self.priority = priority
        self.scheduled_for = scheduled_for
        self.parameters = parameters
        self.created_by = created_by
        self.created_at = datetime.now(timezone.utc)
        self.executed_at: Optional[datetime] = None
        self.execution_result: Optional[dict[str, Any]] = None
        self.status = "pending"


class EscalationAlert:
    """Healthcare provider escalation alert."""

    def __init__(
        self,
        alert_id: UUID,
        patient_id: UUID,
        escalation_level: EscalationLevel,
        concern_type: MedicalConcernType,
        description: str,
        original_message: str,
        recommended_actions: List[str],
        notification_channels: List[NotificationChannel],
        requires_immediate_response: bool = False,
    ):
        self.alert_id = alert_id
        self.patient_id = patient_id
        self.escalation_level = escalation_level
        self.concern_type = concern_type
        self.description = description
        self.original_message = original_message
        self.recommended_actions = recommended_actions
        self.notification_channels = notification_channels
        self.requires_immediate_response = requires_immediate_response
        self.created_at = datetime.now(timezone.utc)
        self.acknowledged_at: Optional[datetime] = None
        self.resolved_at: Optional[datetime] = None
        self.assigned_to: Optional[str] = None


class ConversationContext:
    """Context for maintaining conversation continuity."""

    def __init__(
        self,
        patient_id: UUID,
        conversation_history: List[dict[str, Any]],
        current_topic: Optional[str],
        emotional_state: Optional[str],
        medical_context: dict[str, Any],
        preferences: dict[str, Any],
    ):
        self.patient_id = patient_id
        self.conversation_history = conversation_history
        self.current_topic = current_topic
        self.emotional_state = emotional_state
        self.medical_context = medical_context
        self.preferences = preferences
        self.last_updated = datetime.now(timezone.utc)


class ProviderNotification:
    """Healthcare provider notification data."""

    def __init__(
        self,
        notification_id: UUID,
        patient_id: UUID,
        notification_type: str,
        content: dict[str, Any],
        channels: List[NotificationChannel],
        priority: str,
    ):
        self.notification_id = notification_id
        self.patient_id = patient_id
        self.notification_type = notification_type
        self.content = content
        self.channels = channels
        self.priority = priority
        self.created_at = datetime.now(timezone.utc)
        self.sent_at: Optional[datetime] = None
        self.status = "pending"
