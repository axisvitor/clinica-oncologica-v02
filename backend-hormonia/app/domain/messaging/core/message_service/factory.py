"""
Message Factory - Template-based Message Creation (QW-022).

This module provides factory methods for creating standardized messages.
Consolidated from: app/services/message_factory.py
"""

from typing import List, Optional, Any, Dict
from uuid import UUID
from datetime import datetime
import logging

from sqlalchemy.orm import Session

from app.models.message import Message, MessageDirection, MessageType, MessageStatus
from app.schemas.quiz import QuizQuestion

from .config import MessageTemplate
from .templates import MessageTemplates


logger = logging.getLogger(__name__)


class MessageFactory:
    """
    Factory class for creating standardized messages.
    Eliminates code duplication across services.

    Consolidated from: app/services/message_factory.py
    """

    def __init__(self, db: Session):
        """
        Initialize MessageFactory.

        Args:
            db: Database session
        """
        self.db = db
        self.monthly_quiz_templates = MessageTemplates.MONTHLY_QUIZ_TEMPLATES

    def create_outbound_message(
        self,
        patient_id: UUID,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict[str, Any]] = None,
        template_type: Optional[MessageTemplate] = None,
        scheduled_for: Optional[datetime] = None,
    ) -> Message:
        """
        Create an outbound message.

        Args:
            patient_id: Patient UUID
            content: Message content
            message_type: Type of message
            metadata: Optional metadata
            template_type: Optional template type
            scheduled_for: Optional scheduled time

        Returns:
            Created Message object
        """
        message_data = {
            "patient_id": patient_id,
            "direction": MessageDirection.OUTBOUND,
            "type": message_type,
            "content": content,
            "message_metadata": metadata or {},
            "status": MessageStatus.PENDING
            if not scheduled_for
            else MessageStatus.SCHEDULED,
        }

        if template_type:
            message_data["message_metadata"]["template_type"] = template_type.value

        if scheduled_for:
            message_data["scheduled_for"] = scheduled_for

        message = Message(**message_data)
        return self._save_message(message)

    def create_quiz_question_message(
        self,
        patient_id: UUID,
        question: QuizQuestion,
        quiz_session_id: str,
        question_number: int,
        total_questions: int,
    ) -> Message:
        """
        Create quiz question message.

        Args:
            patient_id: Patient UUID
            question: Quiz question object
            quiz_session_id: Quiz session ID
            question_number: Current question number
            total_questions: Total number of questions

        Returns:
            Created Message object
        """
        content = (
            f"Questão {question_number}/{total_questions}:\n\n{question.question_text}"
        )

        if question.options:
            content += "\n\nOpções:"
            for idx, option in enumerate(question.options, 1):
                content += f"\n{idx}. {option}"

        metadata = {
            "quiz_session_id": quiz_session_id,
            "question_id": str(question.id) if hasattr(question, "id") else None,
            "question_number": question_number,
            "total_questions": total_questions,
            "template_type": MessageTemplate.QUIZ_QUESTION.value,
        }

        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            message_type=MessageType.QUIZ_QUESTION,
            metadata=metadata,
            template_type=MessageTemplate.QUIZ_QUESTION,
        )

    def create_monthly_quiz_invitation_message(
        self,
        patient_id: UUID,
        patient_name: str,
        link: str,
        expiry_hours: int,
        quiz_session_id: str,
        delivery_method: str = "whatsapp",
    ) -> Message:
        """
        Create monthly quiz link invitation message.

        Args:
            patient_id: Patient UUID
            patient_name: Patient name
            link: Quiz link
            expiry_hours: Link expiry in hours
            quiz_session_id: Quiz session ID
            delivery_method: Delivery channel

        Returns:
            Created Message object
        """
        content = self.monthly_quiz_templates["invitation"].format(
            patient_name=patient_name, link=link, expiry_hours=expiry_hours
        )

        metadata = {
            "quiz_session_id": quiz_session_id,
            "quiz_link": link,
            "expiry_hours": expiry_hours,
            "message_type": "monthly_quiz_invitation",
            "template_type": MessageTemplate.MONTHLY_QUIZ_LINK_INVITATION.value,
            "delivery_method": delivery_method,
        }

        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            message_type=MessageType.MONTHLY_QUIZ_LINK,
            metadata=metadata,
            template_type=MessageTemplate.MONTHLY_QUIZ_LINK_INVITATION,
        )

    def create_monthly_quiz_reminder_message(
        self,
        patient_id: UUID,
        patient_name: str,
        link: str,
        hours_remaining: int,
        quiz_session_id: str,
        delivery_method: str = "whatsapp",
    ) -> Message:
        """
        Create monthly quiz reminder message.

        Args:
            patient_id: Patient UUID
            patient_name: Patient name
            link: Quiz link
            hours_remaining: Hours until expiry
            quiz_session_id: Quiz session ID
            delivery_method: Delivery channel

        Returns:
            Created Message object
        """
        content = self.monthly_quiz_templates["reminder"].format(
            patient_name=patient_name, link=link, hours_remaining=hours_remaining
        )

        metadata = {
            "quiz_session_id": quiz_session_id,
            "quiz_link": link,
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
        content = self.monthly_quiz_templates["expired"].format(
            patient_name=patient_name
        )

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
        content = self.monthly_quiz_templates["completed"].format(
            patient_name=patient_name
        )

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
