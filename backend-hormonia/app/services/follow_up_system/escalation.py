"""
Escalation logic for the Follow-up Action System.
Handles creation and management of escalation alerts for healthcare providers.
"""

import logging
from typing import Optional, List
from datetime import datetime, timezone
from uuid import UUID, uuid4

from .enums import EscalationLevel, NotificationChannel, FollowUpType
from .models import EscalationAlert, FollowUpAction
from app.services.response_processor import StructuredResponse
from app.services.analytics.data_extraction import ConcernLevel, MedicalConcernType

logger = logging.getLogger(__name__)


class EscalationManager:
    """Manages escalation alerts and notifications to healthcare providers."""

    def __init__(self, redis_store, active_alerts: dict):
        """
        Initialize escalation manager.

        Args:
            redis_store: Redis storage instance for persistence
            active_alerts: In-memory alert storage (fallback)
        """
        self.redis_store = redis_store
        self.active_alerts = active_alerts

    async def create_escalation_alert(
        self, patient_id: UUID, structured_response: StructuredResponse
    ) -> Optional[FollowUpAction]:
        """
        Create escalation alert for healthcare providers.

        Args:
            patient_id: Patient UUID
            structured_response: Processed response data

        Returns:
            FollowUpAction for escalation notification or None
        """
        try:
            # Determine escalation level
            escalation_level = self._determine_escalation_level(structured_response)

            if escalation_level == EscalationLevel.NONE:
                return None

            # Create escalation alert
            alert = EscalationAlert(
                alert_id=uuid4(),
                patient_id=patient_id,
                escalation_level=escalation_level,
                concern_type=self._get_primary_concern_type(
                    structured_response.medical_concerns
                ),
                description=self._create_alert_description(structured_response),
                original_message=structured_response.original_message,
                recommended_actions=self._generate_recommended_actions(
                    structured_response
                ),
                notification_channels=self._select_notification_channels(
                    escalation_level
                ),
                requires_immediate_response=(
                    escalation_level
                    in [EscalationLevel.CRITICAL, EscalationLevel.EMERGENCY]
                ),
            )

            # Store alert in Redis (with fallback to in-memory)
            stored = await self.redis_store.store_alert(alert)
            if not stored:
                # Fallback to in-memory
                self.active_alerts[alert.alert_id] = alert
                logger.debug(f"Stored alert in memory: {alert.alert_id}")
            else:
                logger.debug(f"Stored alert in Redis: {alert.alert_id}")

            # Create follow-up action for escalation
            action = FollowUpAction(
                action_id=uuid4(),
                patient_id=patient_id,
                follow_up_type=FollowUpType.ESCALATION_NOTIFICATION,
                priority="critical"
                if escalation_level == EscalationLevel.EMERGENCY
                else "high",
                scheduled_for=datetime.now(timezone.utc),  # Immediate
                parameters={
                    "alert_id": str(alert.alert_id),
                    "escalation_level": escalation_level.value,
                    "notification_channels": [
                        ch.value for ch in alert.notification_channels
                    ],
                    "requires_immediate_response": alert.requires_immediate_response,
                },
            )

            return action

        except Exception as e:
            logger.error(f"Failed to create escalation alert: {e}")
            return None

    def _determine_escalation_level(
        self, structured_response: StructuredResponse
    ) -> EscalationLevel:
        """
        Determine appropriate escalation level.

        Args:
            structured_response: Processed response data

        Returns:
            EscalationLevel for the response
        """
        concern_level = structured_response.concern_level
        medical_concerns = structured_response.medical_concerns

        # Emergency escalation
        emergency_keywords = ["emergency", "can't breathe", "chest pain", "suicide"]
        if any(
            keyword in structured_response.original_message.lower()
            for keyword in emergency_keywords
        ):
            return EscalationLevel.EMERGENCY

        # Critical escalation
        if concern_level == ConcernLevel.CRITICAL:
            return EscalationLevel.CRITICAL

        # High escalation
        if concern_level == ConcernLevel.HIGH or len(medical_concerns) > 2:
            return EscalationLevel.HIGH

        # Medium escalation
        if concern_level == ConcernLevel.MEDIUM or len(medical_concerns) > 0:
            return EscalationLevel.MEDIUM

        return EscalationLevel.NONE

    def _get_primary_concern_type(
        self, medical_concerns: List[str]
    ) -> MedicalConcernType:
        """
        Get primary concern type from list of concerns.

        Args:
            medical_concerns: List of medical concern texts

        Returns:
            Primary MedicalConcernType
        """
        if not medical_concerns:
            return MedicalConcernType.GENERAL_HEALTH

        # Import here to avoid circular dependency
        from .generators import ResponseGenerator

        generator = ResponseGenerator(None)

        # Use the first concern to determine type
        primary_concern = medical_concerns[0]
        return (
            generator.classify_concern_type(primary_concern)
            or MedicalConcernType.GENERAL_HEALTH
        )

    def _create_alert_description(self, structured_response: StructuredResponse) -> str:
        """
        Create description for escalation alert.

        Args:
            structured_response: Processed response data

        Returns:
            Alert description text
        """
        sentiment = structured_response.sentiment_analysis.get("sentiment", "neutral")
        concern_level = structured_response.concern_level.value

        description = f"Patient response with {concern_level} concern level and {sentiment} sentiment. "

        if structured_response.medical_concerns:
            concerns_text = ", ".join(structured_response.medical_concerns[:3])
            description += f"Medical concerns: {concerns_text}. "

        if structured_response.requires_attention:
            description += "Requires immediate attention. "

        return description.strip()

    def _generate_recommended_actions(
        self, structured_response: StructuredResponse
    ) -> List[str]:
        """
        Generate recommended actions for healthcare providers.

        Args:
            structured_response: Processed response data

        Returns:
            List of recommended actions (max 5)
        """
        actions = []

        concern_level = structured_response.concern_level
        medical_concerns = structured_response.medical_concerns

        if concern_level == ConcernLevel.CRITICAL:
            actions.extend(
                [
                    "Contact patient immediately",
                    "Assess need for emergency care",
                    "Document response in medical record",
                ]
            )
        elif concern_level == ConcernLevel.HIGH:
            actions.extend(
                [
                    "Review patient response within 2 hours",
                    "Consider scheduling urgent consultation",
                    "Evaluate medication adjustments",
                ]
            )
        elif concern_level == ConcernLevel.MEDIUM:
            actions.extend(
                [
                    "Review patient response within 24 hours",
                    "Consider follow-up call",
                    "Monitor for symptom progression",
                ]
            )

        # Add concern-specific actions
        if any("pain" in concern.lower() for concern in medical_concerns):
            actions.append("Assess pain management strategy")

        if any("medication" in concern.lower() for concern in medical_concerns):
            actions.append("Review medication compliance and side effects")

        if any(
            "emotional" in concern.lower() or "anxious" in concern.lower()
            for concern in medical_concerns
        ):
            actions.append("Consider mental health support referral")

        return actions[:5]  # Return max 5 actions

    def _select_notification_channels(
        self, escalation_level: EscalationLevel
    ) -> List[NotificationChannel]:
        """
        Select appropriate notification channels based on escalation level.

        Args:
            escalation_level: Level of escalation

        Returns:
            List of notification channels to use
        """
        if escalation_level == EscalationLevel.EMERGENCY:
            return [
                NotificationChannel.PHONE_CALL,
                NotificationChannel.SMS,
                NotificationChannel.DASHBOARD_ALERT,
                NotificationChannel.PUSH_NOTIFICATION,
            ]
        elif escalation_level == EscalationLevel.CRITICAL:
            return [
                NotificationChannel.SMS,
                NotificationChannel.DASHBOARD_ALERT,
                NotificationChannel.PUSH_NOTIFICATION,
                NotificationChannel.EMAIL,
            ]
        elif escalation_level == EscalationLevel.HIGH:
            return [
                NotificationChannel.DASHBOARD_ALERT,
                NotificationChannel.PUSH_NOTIFICATION,
                NotificationChannel.EMAIL,
            ]
        elif escalation_level == EscalationLevel.MEDIUM:
            return [NotificationChannel.DASHBOARD_ALERT, NotificationChannel.EMAIL]
        else:
            return [NotificationChannel.DASHBOARD_ALERT]
