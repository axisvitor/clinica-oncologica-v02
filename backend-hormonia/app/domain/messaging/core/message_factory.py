"""
Message Factory Service
Centralizes message creation patterns to eliminate code duplication.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from uuid import UUID
from enum import Enum

from sqlalchemy.orm import Session

from app.models.message import Message, MessageDirection, MessageType, MessageStatus
from app.utils.template_sanitizer import get_template_sanitizer


class MessageTemplate(Enum):
    """Pre-defined message templates"""

    QUIZ_INTRODUCTION = "quiz_introduction"
    QUIZ_QUESTION = "quiz_question"
    QUIZ_COMPLETION = "quiz_completion"
    QUIZ_CLARIFICATION = "quiz_clarification"
    QUIZ_PAUSED = "quiz_paused"
    FLOW_MESSAGE = "flow_message"
    ALERT_MESSAGE = "alert_message"
    REMINDER = "reminder"
    FOLLOW_UP = "follow_up"
    # Monthly quiz link templates
    MONTHLY_QUIZ_LINK_INVITATION = "monthly_quiz_link_invitation"
    MONTHLY_QUIZ_LINK_REMINDER = "monthly_quiz_link_reminder"
    MONTHLY_QUIZ_LINK_EXPIRED = "monthly_quiz_link_expired"
    MONTHLY_QUIZ_LINK_COMPLETED = "monthly_quiz_link_completed"


class MessageFactory:
    """
    Factory class for creating standardized messages.
    Eliminates code duplication across services.
    """

    def __init__(self, db: Session):
        """
        Initialize MessageFactory.

        Args:
            db: Database session
        """
        self.db = db
        self.sanitizer = get_template_sanitizer()

        # Message templates for monthly quiz links
        self.monthly_quiz_templates = {
            "invitation": (
                "Olá {patient_name}! 😊\n\n"
                "Chegou o momento do seu questionário mensal de bem-estar!\n\n"
                "Acesse pelo link: {link}\n\n"
                "➡️ Válido por {expiry_hours} horas\n\n"
                "Sua participação é muito importante para acompanharmos seu progresso."
            ),
            "reminder": (
                "Oi {patient_name}! 💬\n\n"
                "Lembrete: você ainda não respondeu ao questionário mensal.\n\n"
                "Por favor, acesse: {link}\n\n"
                "⏳ Expira em {hours_remaining} horas\n\n"
                "Contamos com você!"
            ),
            "expired": (
                "Olá {patient_name}! ⏰\n\n"
                "O link do seu questionário expirou.\n\n"
                "Um novo link será enviado em breve. Fique atenta(o)!"
            ),
            "completed": (
                "Obrigada, {patient_name}! 🙌\n\n"
                "Recebemos suas respostas do questionário mensal.\n\n"
                "Nossa equipe médica irá analisá-las em breve.\n\n"
                "Continue cuidando bem da sua saúde! 🌷"
            ),
        }

    def create_outbound_message(
        self,
        patient_id: UUID,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict[str, Any]] = None,
        template_type: Optional[MessageTemplate] = None,
        **kwargs,
    ) -> Message:
        """
        Create a standardized outbound message.

        Args:
            patient_id: Patient UUID
            content: Message content
            message_type: Type of message
            metadata: Optional metadata
            template_type: Optional template type for categorization
            **kwargs: Additional fields

        Returns:
            Created Message object (saved to DB)
        """
        msg_metadata = metadata or {}
        if template_type:
            msg_metadata["template_type"] = template_type.value

        message = Message(
            patient_id=patient_id,
            content=content,
            message_type=message_type,
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.PENDING,
            metadata=msg_metadata,
            created_at=datetime.now(timezone.utc),
            **kwargs,
        )

        return self._save_message(message)

    def create_monthly_quiz_link_message(
        self,
        patient_id: UUID,
        patient_name: str,
        link_url: str,
        quiz_session_id: str,
        expiry_hours: int = 72,
        delivery_method: str = "whatsapp",
    ) -> Message:
        """
        Create monthly quiz link invitation message.

        Args:
            patient_id: Patient UUID
            patient_name: Patient name
            link_url: Quiz link URL
            quiz_session_id: Quiz session ID
            expiry_hours: Token expiry hours
            delivery_method: Delivery channel

        Returns:
            Created Message object
        """
        # Sanitize user input before template rendering
        safe_context = self.sanitizer.sanitize_template_context({
            "patient_name": patient_name,
            "link": link_url,
            "expiry_hours": expiry_hours
        })
        content = self.monthly_quiz_templates["invitation"].format(**safe_context)

        metadata = {
            "quiz_session_id": quiz_session_id,
            "link_url": link_url,
            "expiry_hours": expiry_hours,
            "message_type": "monthly_quiz_invitation",
            "template_type": MessageTemplate.MONTHLY_QUIZ_LINK_INVITATION.value,
            "delivery_method": delivery_method,
        }

        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            message_type=MessageType.MONTHLY_QUIZ_INVITATION,
            metadata=metadata,
            template_type=MessageTemplate.MONTHLY_QUIZ_LINK_INVITATION,
        )

    def create_monthly_quiz_reminder_message(
        self,
        patient_id: UUID,
        patient_name: str,
        link_url: str,
        quiz_session_id: str,
        hours_remaining: int,
        delivery_method: str = "whatsapp",
    ) -> Message:
        """
        Create monthly quiz reminder message.

        Args:
            patient_id: Patient UUID
            patient_name: Patient name
            link_url: Quiz link URL
            quiz_session_id: Quiz session ID
            hours_remaining: Hours until expiry
            delivery_method: Delivery channel

        Returns:
            Created Message object
        """
        # Sanitize user input before template rendering
        safe_context = self.sanitizer.sanitize_template_context({
            "patient_name": patient_name,
            "link": link_url,
            "hours_remaining": hours_remaining
        })
        content = self.monthly_quiz_templates["reminder"].format(**safe_context)

        metadata = {
            "quiz_session_id": quiz_session_id,
            "link_url": link_url,
            "hours_remaining": hours_remaining,
            "message_type": "monthly_quiz_reminder",
            "template_type": MessageTemplate.MONTHLY_QUIZ_LINK_REMINDER.value,
            "delivery_method": delivery_method,
        }

        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            message_type=MessageType.MONTHLY_QUIZ_REMINDER,
            metadata=metadata,
            template_type=MessageTemplate.MONTHLY_QUIZ_LINK_REMINDER,
        )

    def create_monthly_quiz_expired_message(
        self,
        patient_id: UUID,
        patient_name: str,
        quiz_session_id: str,
        delivery_method: str = "whatsapp",
    ) -> Message:
        """
        Create monthly quiz link expired message.

        Args:
            patient_id: Patient UUID
            patient_name: Patient name
            quiz_session_id: Quiz session ID
            delivery_method: Delivery channel

        Returns:
            Created Message object
        """
        # Sanitize user input before template rendering
        safe_context = self.sanitizer.sanitize_template_context({
            "patient_name": patient_name
        })
        content = self.monthly_quiz_templates["expired"].format(**safe_context)

        metadata = {
            "quiz_session_id": quiz_session_id,
            "message_type": "monthly_quiz_expired",
            "template_type": MessageTemplate.MONTHLY_QUIZ_LINK_EXPIRED.value,
            "delivery_method": delivery_method,
        }

        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            message_type=MessageType.MONTHLY_QUIZ_EXPIRED,
            metadata=metadata,
            template_type=MessageTemplate.MONTHLY_QUIZ_LINK_EXPIRED,
        )

    def create_monthly_quiz_completed_message(
        self,
        patient_id: UUID,
        patient_name: str,
        quiz_session_id: str,
        delivery_method: str = "whatsapp",
    ) -> Message:
        """
        Create monthly quiz completion confirmation message.

        Args:
            patient_id: Patient UUID
            patient_name: Patient name
            quiz_session_id: Quiz session ID
            delivery_method: Delivery channel

        Returns:
            Created Message object
        """
        # Sanitize user input before template rendering
        safe_context = self.sanitizer.sanitize_template_context({
            "patient_name": patient_name
        })
        content = self.monthly_quiz_templates["completed"].format(**safe_context)

        metadata = {
            "quiz_session_id": quiz_session_id,
            "message_type": "monthly_quiz_completed",
            "template_type": MessageTemplate.MONTHLY_QUIZ_LINK_COMPLETED.value,
            "delivery_method": delivery_method,
        }

        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            message_type=MessageType.MONTHLY_QUIZ_COMPLETED,
            metadata=metadata,
            template_type=MessageTemplate.MONTHLY_QUIZ_LINK_COMPLETED,
        )

    def create_multi_channel_message(
        self,
        patient_id: UUID,
        content: str,
        channels: List[str],
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Message]:
        """
        Create message for multiple delivery channels.

        Args:
            patient_id: Patient UUID
            content: Message content
            channels: List of delivery channels (whatsapp, email, sms)
            message_type: Type of message
            metadata: Optional metadata

        Returns:
            List of created Message objects (one per channel)
        """
        messages = []

        for channel in channels:
            channel_metadata = metadata.copy() if metadata else {}
            channel_metadata["delivery_method"] = channel

            # Adapt content for channel if needed
            adapted_content = content
            if channel == "sms":
                # Truncate for SMS (160 chars)
                adapted_content = (
                    content[:157] + "..." if len(content) > 160 else content
                )
            elif channel == "email":
                # Could wrap in HTML template for email
                channel_metadata["email_format"] = "html"

            message = self.create_outbound_message(
                patient_id=patient_id,
                content=adapted_content,
                message_type=message_type,
                metadata=channel_metadata,
            )
            messages.append(message)

        return messages

    def _save_message(self, message: Message) -> Message:
        """
        Save message to database.

        Args:
            message: Message to save

        Returns:
            Saved Message object
        """
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message


def get_message_factory(db: Session) -> MessageFactory:
    """
    Get MessageFactory instance.

    Args:
        db: Database session

    Returns:
        MessageFactory instance
    """
    return MessageFactory(db)
