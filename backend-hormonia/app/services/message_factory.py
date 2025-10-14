"""
Message Factory Service
Centralizes message creation patterns to eliminate code duplication.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from enum import Enum

from sqlalchemy.orm import Session

from app.models.message import Message, MessageDirection, MessageType, MessageStatus
from app.models.quiz import QuizTemplate
from app.schemas.quiz import QuizQuestion


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

        # Message templates for monthly quiz links
        self.monthly_quiz_templates = {
            'invitation': (
                "Olá {patient_name}! 😊\n\n"
                "Chegou o momento do seu questionário mensal de bem-estar!\n\n"
                "Acesse pelo link: {link}\n\n"
                "➡️ Válido por {expiry_hours} horas\n\n"
                "Sua participação é muito importante para acompanharmos seu progresso."
            ),
            'reminder': (
                "Oi {patient_name}! 💬\n\n"
                "Lembrete: você ainda não respondeu ao questionário mensal.\n\n"
                "Por favor, acesse: {link}\n\n"
                "⏳ Expira em {hours_remaining} horas\n\n"
                "Contamos com você!"
            ),
            'expired': (
                "Olá {patient_name}! ⏰\n\n"
                "O link do seu questionário expirou.\n\n"
                "Um novo link será enviado em breve. Fique atenta(o)!"
            ),
            'completed': (
                "Obrigada, {patient_name}! 🙌\n\n"
                "Recebemos suas respostas do questionário mensal.\n\n"
                "Nossa equipe médica irá analisá-las em breve.\n\n"
                "Continue cuidando bem da sua saúde! 🌷"
            )
        }


        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            message_type=MessageType.MONTHLY_QUIZ_REMINDER,
            metadata=metadata,
            template_type=MessageTemplate.MONTHLY_QUIZ_LINK_REMINDER
        )

    def create_monthly_quiz_expired_message(
        self,
        patient_id: UUID,
        patient_name: str,
        quiz_session_id: str,
        delivery_method: str = "whatsapp"
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
        content = self.monthly_quiz_templates['expired'].format(
            patient_name=patient_name
        )

        metadata = {
            "quiz_session_id": quiz_session_id,
            "message_type": "monthly_quiz_expired",
            "template_type": MessageTemplate.MONTHLY_QUIZ_LINK_EXPIRED.value,
            "delivery_method": delivery_method
        }

        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            message_type=MessageType.MONTHLY_QUIZ_EXPIRED,
            metadata=metadata,
            template_type=MessageTemplate.MONTHLY_QUIZ_LINK_EXPIRED
        )

    def create_monthly_quiz_completed_message(
        self,
        patient_id: UUID,
        patient_name: str,
        quiz_session_id: str,
        delivery_method: str = "whatsapp"
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
        content = self.monthly_quiz_templates['completed'].format(
            patient_name=patient_name
        )

        metadata = {
            "quiz_session_id": quiz_session_id,
            "message_type": "monthly_quiz_completed",
            "template_type": MessageTemplate.MONTHLY_QUIZ_LINK_COMPLETED.value,
            "delivery_method": delivery_method
        }

        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            message_type=MessageType.MONTHLY_QUIZ_COMPLETED,
            metadata=metadata,
            template_type=MessageTemplate.MONTHLY_QUIZ_LINK_COMPLETED
        )

    def create_multi_channel_message(
        self,
        patient_id: UUID,
        content: str,
        channels: List[str],
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict[str, Any]] = None
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
            channel_metadata['delivery_method'] = channel

            # Adapt content for channel if needed
            adapted_content = content
            if channel == "sms":
                # Truncate for SMS (160 chars)
                adapted_content = content[:157] + "..." if len(content) > 160 else content
            elif channel == "email":
                # Could wrap in HTML template for email
                channel_metadata['email_format'] = 'html'

            message = self.create_outbound_message(
                patient_id=patient_id,
                content=adapted_content,
                message_type=message_type,
                metadata=channel_metadata
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

