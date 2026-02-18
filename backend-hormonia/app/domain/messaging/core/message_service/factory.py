"""
Message Factory adapter for the legacy message_service package.

This keeps the message_service MessageFactory public API stable while
delegating to the canonical core MessageFactory implementation.
"""

from typing import List, Optional, Any, Dict
from uuid import UUID
from datetime import datetime
import logging

from sqlalchemy.orm import Session

from app.models.message import Message, MessageDirection, MessageType, MessageStatus
from app.schemas.quiz import QuizQuestion
from app.domain.messaging.core.message_factory import (
    MessageFactory as CoreMessageFactory,
    MessageTemplate as CoreMessageTemplate,
)
from app.domain.messaging.core.monthly_quiz_payload import (
    build_monthly_quiz_reminder_payload,
)

from .config import MessageTemplate


logger = logging.getLogger(__name__)


class MessageFactory:
    """Compatibility adapter around app.domain.messaging.core.message_factory."""

    def __init__(self, db: Session):
        self.db = db
        self._core_factory = CoreMessageFactory(db)
        self.monthly_quiz_templates = self._core_factory.monthly_quiz_templates

    def _sanitize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        sanitizer = getattr(self._core_factory, "sanitizer", None)
        if sanitizer is None:
            return context

        sanitize_method = getattr(sanitizer, "sanitize_template_context", None)
        if not callable(sanitize_method):
            return context

        try:
            return sanitize_method(context)
        except Exception:
            logger.debug("Template context sanitization failed; using raw context", exc_info=True)
            return context

    @staticmethod
    def _template_value(template_type: Optional[Any]) -> Optional[str]:
        if template_type is None:
            return None
        value = getattr(template_type, "value", template_type)
        return value if isinstance(value, str) else str(value)

    def _to_core_template(self, template_type: Optional[Any]) -> Optional[Any]:
        value = self._template_value(template_type)
        if not value:
            return None
        try:
            return CoreMessageTemplate(value)
        except Exception:
            return None

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

        Uses canonical factory first, then falls back to legacy model fields for
        compatibility (type/message_metadata and scheduled status handling).
        """
        if scheduled_for is None:
            try:
                return self._core_factory.create_outbound_message(
                    patient_id=patient_id,
                    content=content,
                    message_type=message_type,
                    metadata=metadata,
                    template_type=self._to_core_template(template_type),
                )
            except (AttributeError, TypeError, ValueError):
                logger.debug(
                    "Falling back to legacy outbound message creation path",
                    exc_info=True,
                )

        message_metadata = dict(metadata or {})
        template_value = self._template_value(template_type)
        if template_value:
            message_metadata["template_type"] = template_value

        message_data = {
            "patient_id": patient_id,
            "direction": MessageDirection.OUTBOUND,
            "type": message_type,
            "content": content,
            "message_metadata": message_metadata,
            "status": MessageStatus.PENDING,
        }
        if scheduled_for:
            message_data["scheduled_for"] = scheduled_for

        return self._core_factory._save_message(Message(**message_data))

    def create_quiz_question_message(
        self,
        patient_id: UUID,
        question: QuizQuestion,
        quiz_session_id: str,
        question_number: int,
        total_questions: int,
    ) -> Message:
        """Create quiz question message with legacy signature."""
        core_method = getattr(self._core_factory, "create_quiz_question_message", None)
        if callable(core_method):
            try:
                return core_method(
                    patient_id=patient_id,
                    question=question,
                    quiz_session_id=quiz_session_id,
                    question_number=question_number,
                    total_questions=total_questions,
                )
            except (AttributeError, TypeError, ValueError):
                logger.debug(
                    "Core quiz-question method unavailable, using compatibility path",
                    exc_info=True,
                )

        content = (
            f"Questão {question_number}/{total_questions}:\n\n"
            f"{self._sanitize_context({'question_text': question.question_text}).get('question_text', '')}"
        )
        if question.options:
            content += "\n\nOpções:"
            safe_options = self._sanitize_context({"options": question.options}).get(
                "options", question.options
            )
            for idx, option in enumerate(safe_options, 1):
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

    def create_quiz_introduction(
        self,
        patient_id: UUID,
        patient_name: str,
        session_id: str,
        first_question: Any,
        total_questions: int,
    ) -> Message:
        """
        Create a quiz introduction message with first-question preview.

        Legacy integrations call this method directly. Keep it as a stable adapter
        API while routing through the canonical message factory when possible.
        """
        core_method = getattr(self._core_factory, "create_quiz_introduction", None)
        if callable(core_method):
            try:
                return core_method(
                    patient_id=patient_id,
                    patient_name=patient_name,
                    session_id=session_id,
                    first_question=first_question,
                    total_questions=total_questions,
                )
            except (AttributeError, TypeError, ValueError):
                logger.debug(
                    "Core quiz-introduction method unavailable, using compatibility path",
                    exc_info=True,
                )

        if isinstance(first_question, dict):
            question_text = (
                first_question.get("question_text")
                or first_question.get("text")
                or "Como você está se sentindo hoje?"
            )
            question_options = first_question.get("options") or []
        else:
            question_text = (
                getattr(first_question, "question_text", None)
                or getattr(first_question, "text", None)
                or "Como você está se sentindo hoje?"
            )
            question_options = getattr(first_question, "options", []) or []

        safe_context = self._sanitize_context(
            {
                "patient_name": patient_name,
                "question_text": question_text,
            }
        )

        content = (
            f"Olá {safe_context['patient_name']}! 😊\n\n"
            f"Vamos começar seu check-in mensal.\n"
            f"São {max(int(total_questions or 0), 1)} perguntas rápidas.\n\n"
            f"*Pergunta 1:* {safe_context['question_text']}"
        )

        if question_options:
            content += "\n\n*Opções:*"
            for option in question_options:
                if isinstance(option, dict):
                    option_text = (
                        option.get("text")
                        or option.get("label")
                        or option.get("value")
                        or str(option)
                    )
                else:
                    option_text = str(option)
                content += f"\n• {option_text}"

        metadata = {
            "quiz_session_id": session_id,
            "message_type": "quiz_introduction",
            "first_question": safe_context["question_text"],
            "total_questions": max(int(total_questions or 0), 1),
            "template_type": MessageTemplate.QUIZ_INTRODUCTION.value,
        }

        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            message_type=MessageType.QUIZ_INTRO,
            metadata=metadata,
            template_type=MessageTemplate.QUIZ_INTRODUCTION,
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
        Create monthly quiz invitation with backward-compatible method name.

        Delegates to canonical invitation/link methods when available.
        """
        for method_name in (
            "create_monthly_quiz_invitation_message",
            "create_monthly_quiz_link_message",
        ):
            core_method = getattr(self._core_factory, method_name, None)
            if not callable(core_method):
                continue

            for kwargs in (
                {
                    "patient_id": patient_id,
                    "patient_name": patient_name,
                    "link": link,
                    "expiry_hours": expiry_hours,
                    "quiz_session_id": quiz_session_id,
                    "delivery_method": delivery_method,
                },
                {
                    "patient_id": patient_id,
                    "patient_name": patient_name,
                    "link_url": link,
                    "expiry_hours": expiry_hours,
                    "quiz_session_id": quiz_session_id,
                    "delivery_method": delivery_method,
                },
            ):
                try:
                    return core_method(**kwargs)
                except TypeError:
                    continue
                except (AttributeError, ValueError):
                    logger.debug(
                        "Core monthly invitation method failed, using compatibility path",
                        exc_info=True,
                    )
                    break

        safe_context = self._sanitize_context(
            {
                "patient_name": patient_name,
                "link": link,
                "expiry_hours": expiry_hours,
            }
        )
        content = self.monthly_quiz_templates["invitation"].format(**safe_context)
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
        """Create monthly quiz reminder message with legacy signature."""
        core_method = getattr(self._core_factory, "create_monthly_quiz_reminder_message", None)
        if callable(core_method):
            for kwargs in (
                {
                    "patient_id": patient_id,
                    "patient_name": patient_name,
                    "link": link,
                    "hours_remaining": hours_remaining,
                    "quiz_session_id": quiz_session_id,
                    "delivery_method": delivery_method,
                },
                {
                    "patient_id": patient_id,
                    "patient_name": patient_name,
                    "link_url": link,
                    "hours_remaining": hours_remaining,
                    "quiz_session_id": quiz_session_id,
                    "delivery_method": delivery_method,
                },
            ):
                try:
                    return core_method(**kwargs)
                except TypeError:
                    continue
                except (AttributeError, ValueError):
                    logger.debug(
                        "Core monthly reminder method failed, using compatibility path",
                        exc_info=True,
                    )
                    break

        content, metadata = build_monthly_quiz_reminder_payload(
            sanitize_context=self._sanitize_context,
            templates=self.monthly_quiz_templates,
            patient_name=patient_name,
            link=link,
            quiz_session_id=quiz_session_id,
            hours_remaining=hours_remaining,
            delivery_method=delivery_method,
            link_metadata_key="quiz_link",
        )

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
        """Create monthly quiz link expired message."""
        core_method = getattr(self._core_factory, "create_monthly_quiz_expired_message", None)
        if callable(core_method):
            try:
                return core_method(
                    patient_id=patient_id,
                    patient_name=patient_name,
                    quiz_session_id=quiz_session_id,
                    delivery_method=delivery_method,
                )
            except (AttributeError, TypeError, ValueError):
                logger.debug(
                    "Core monthly expired method failed, using compatibility path",
                    exc_info=True,
                )

        return self._create_monthly_quiz_status_message(
            patient_id=patient_id,
            patient_name=patient_name,
            quiz_session_id=quiz_session_id,
            delivery_method=delivery_method,
            template_key="expired",
            message_kind="monthly_quiz_expired",
            message_type=MessageType.MONTHLY_QUIZ_EXPIRED,
            template_type=MessageTemplate.MONTHLY_QUIZ_LINK_EXPIRED,
        )

    def create_monthly_quiz_completed_message(
        self,
        patient_id: UUID,
        patient_name: str,
        quiz_session_id: str,
        delivery_method: str = "whatsapp",
    ) -> Message:
        """Create monthly quiz completion confirmation message."""
        core_method = getattr(self._core_factory, "create_monthly_quiz_completed_message", None)
        if callable(core_method):
            try:
                return core_method(
                    patient_id=patient_id,
                    patient_name=patient_name,
                    quiz_session_id=quiz_session_id,
                    delivery_method=delivery_method,
                )
            except (AttributeError, TypeError, ValueError):
                logger.debug(
                    "Core monthly completed method failed, using compatibility path",
                    exc_info=True,
                )

        return self._create_monthly_quiz_status_message(
            patient_id=patient_id,
            patient_name=patient_name,
            quiz_session_id=quiz_session_id,
            delivery_method=delivery_method,
            template_key="completed",
            message_kind="monthly_quiz_completed",
            message_type=MessageType.MONTHLY_QUIZ_COMPLETED,
            template_type=MessageTemplate.MONTHLY_QUIZ_LINK_COMPLETED,
        )

    def _create_monthly_quiz_status_message(
        self,
        *,
        patient_id: UUID,
        patient_name: str,
        quiz_session_id: str,
        delivery_method: str,
        template_key: str,
        message_kind: str,
        message_type: MessageType,
        template_type: MessageTemplate,
    ) -> Message:
        """Build monthly-quiz status message payload for compatibility fallback paths."""
        safe_context = self._sanitize_context({"patient_name": patient_name})
        content = self.monthly_quiz_templates[template_key].format(**safe_context)
        metadata = {
            "quiz_session_id": quiz_session_id,
            "message_type": message_kind,
            "template_type": template_type.value,
            "delivery_method": delivery_method,
        }
        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            message_type=message_type,
            metadata=metadata,
            template_type=template_type,
        )

    def create_multi_channel_message(
        self,
        patient_id: UUID,
        content: str,
        channels: List[str],
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Message]:
        """Create messages for multiple delivery channels."""
        core_method = getattr(self._core_factory, "create_multi_channel_message", None)
        if callable(core_method):
            try:
                return core_method(
                    patient_id=patient_id,
                    content=content,
                    channels=channels,
                    message_type=message_type,
                    metadata=metadata,
                )
            except (AttributeError, TypeError, ValueError):
                logger.debug(
                    "Core multi-channel method failed, using compatibility path",
                    exc_info=True,
                )

        messages = []
        for channel in channels:
            channel_metadata = metadata.copy() if metadata else {}
            channel_metadata["delivery_method"] = channel

            adapted_content = content
            if channel == "sms":
                adapted_content = content[:157] + "..." if len(content) > 160 else content
            elif channel == "email":
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
        """Save message to database via canonical factory."""
        return self._core_factory._save_message(message)
