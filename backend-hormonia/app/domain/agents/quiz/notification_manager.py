"""
Notification Manager - Handles all quiz-related messaging and notifications.

Manages message composition, personalization, and delivery for quiz interactions.
"""

from __future__ import annotations

# Standard library imports
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

# Third-party imports
from sqlalchemy.orm import Session

# Local application imports
from app.domain.messaging.delivery import MessageSender
from app.models.message import (
    Message,
    MessageDirection,
    MessageStatus,
    MessageType,
)

if TYPE_CHECKING:
    from app.domain.agents.quiz.session_coordinator import QuizContext


class QuizAdaptationType(Enum):
    """Types of quiz adaptations."""

    REDUCE_COMPLEXITY = "reduce_complexity"
    INCREASE_SUPPORT = "increase_support"
    FOCUS_ON_MOOD = "focus_on_mood"
    SKIP_SENSITIVE = "skip_sensitive"
    ADD_CLARIFICATION = "add_clarification"
    ACCELERATE_COMPLETION = "accelerate_completion"


class NotificationManager:
    """
    Manages all quiz notifications and messages.

    Handles personalized message composition and delivery for
    quiz interactions, including introductions, completions,
    clarifications, and adaptations.

    Attributes:
        db_session: Database session.
        message_sender: Message delivery service.
        agent_id: ID of owning agent.
    """

    def __init__(
        self,
        db_session: Session,
        message_sender: MessageSender,
        agent_id: str,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize notification manager.

        Args:
            db_session: Database session.
            message_sender: Message delivery service.
            agent_id: Agent identifier.
            logger: Logger instance.
        """
        self.db_session = db_session
        self.message_sender = message_sender
        self.agent_id = agent_id
        self._logger = logger or logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def send_quiz_introduction(
        self, context: "QuizContext", max_questions: int, stress_threshold: float
    ):
        """Send personalized quiz introduction."""
        try:
            patient_name = context.patient_data.name

            # Personalize introduction based on context
            if context.mood_indicators.get("trend", 0) < -0.5:
                intro_tone = "supportive"
                intro_text = f"Olá {patient_name}! 💜 Sei que às vezes os dias podem ser desafiadores. Preparei algumas perguntas bem rápidas para entender melhor como você está. Vamos juntas?"
            elif context.stress_level > stress_threshold:
                intro_tone = "gentle"
                intro_text = f"Oi {patient_name}! 🌸 Vamos fazer um check-up rápido e tranquilo? São apenas algumas perguntas para eu entender como você está se sentindo."
            else:
                intro_tone = "encouraging"
                intro_text = f"Olá {patient_name}! 😊 É hora do nosso check-up mensal! Preparei algumas perguntas importantes para acompanhar seu progresso. Vamos começar?"

            # Add context-aware elements
            if context.knowledge_context.get("patterns"):
                recent_patterns = context.knowledge_context["patterns"][-2:]
                for pattern in recent_patterns:
                    if "improvement" in pattern.get("pattern_type", ""):
                        intro_text += " Fico feliz em ver seu progresso! 💪"
                        break

            # Add question count
            question_count = min(len(context.template.questions), max_questions)
            intro_text += f"\n\n*São {question_count} perguntas rápidas.*"

            # Send message
            message = Message(
                patient_id=context.patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=intro_text,
                message_metadata={
                    "quiz_session_id": str(context.session.id),
                    "message_type": "quiz_introduction",
                    "intro_tone": intro_tone,
                    "generated_by": self.agent_id,
                    "swarm_context": True,
                },
                status=MessageStatus.PENDING,
                scheduled_for=datetime.now(timezone.utc),
            )

            self.db_session.add(message)
            self.db_session.commit()
            self.db_session.refresh(message)

            await self.message_sender.send_message(message)

        except Exception as e:
            self._logger.error(f"Failed to send quiz introduction: {e}")

    async def send_completion_message(self, context: "QuizContext"):
        """Send personalized completion message."""
        try:
            patient_name = context.patient_data.name

            # Personalize based on session performance
            if context.engagement_score > 0.8:
                completion_message = f"Parabéns {patient_name}! 🎉 Você completou o check-up com excelência! Suas respostas foram registradas e nossa equipe analisará tudo com cuidado."
            elif len(context.adaptation_history) > 0:
                completion_message = f"Obrigada {patient_name}! 💜 Sei que algumas perguntas podem ser desafiadoras, mas você foi muito bem! Suas respostas são muito valiosas para seu cuidado."
            else:
                completion_message = f"Muito obrigada {patient_name}! 😊 Você completou seu check-up mensal. Suas respostas ajudam nossa equipe a cuidar melhor de você."

            completion_message += "\n\nSe precisar de algo, estarei sempre aqui! 🌸"

            message = Message(
                patient_id=context.patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=completion_message,
                message_metadata={
                    "quiz_session_id": str(context.session.id),
                    "message_type": "quiz_completion",
                    "generated_by": self.agent_id,
                    "session_summary": {
                        "questions_completed": len(context.responses_so_far),
                        "adaptations_made": len(context.adaptation_history),
                        "engagement_score": context.engagement_score,
                    },
                },
                status=MessageStatus.PENDING,
                scheduled_for=datetime.now(timezone.utc),
            )

            self.db_session.add(message)
            self.db_session.commit()

            await self.message_sender.send_message(message)

        except Exception as e:
            self._logger.error(f"Failed to send completion message: {e}")

    async def send_clarification_message(
        self, context: "QuizContext", error_message: str
    ):
        """Send clarification message for unclear response."""
        try:
            clarification = f"Desculpe {context.patient_data.name}, {error_message}\n\nVamos tentar novamente? 😊"

            message = Message(
                patient_id=context.patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=clarification,
                message_metadata={
                    "quiz_session_id": str(context.session.id),
                    "message_type": "quiz_clarification",
                    "generated_by": self.agent_id,
                },
                status=MessageStatus.PENDING,
                scheduled_for=datetime.now(timezone.utc),
            )

            self.db_session.add(message)
            self.db_session.commit()

            await self.message_sender.send_message(message)

        except Exception as e:
            self._logger.error(f"Failed to send clarification message: {e}")

    async def send_adaptation_message(
        self, context: "QuizContext", adaptation: QuizAdaptationType
    ):
        """Send adaptation message based on adaptation type."""
        adaptation_message = None

        if adaptation == QuizAdaptationType.REDUCE_COMPLEXITY:
            adaptation_message = "Vamos simplificar um pouco. Responda apenas com o que vier à mente primeiro. 💜"

        elif adaptation == QuizAdaptationType.INCREASE_SUPPORT:
            adaptation_message = f"{context.patient_data.name}, você está indo muito bem! Vamos continuar juntas. 🌸"

        elif adaptation == QuizAdaptationType.FOCUS_ON_MOOD:
            adaptation_message = "Percebi que pode estar sendo um momento difícil. Não se preocupe, não há resposta errada. 🤗"

        elif adaptation == QuizAdaptationType.ADD_CLARIFICATION:
            adaptation_message = "Para me ajudar a entender melhor, que tal responder de forma bem simples? Pode ser só uma palavra mesmo. 😊"

        # Send adaptation message if needed
        if adaptation_message:
            message = Message(
                patient_id=context.patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=adaptation_message,
                message_metadata={
                    "quiz_session_id": str(context.session.id),
                    "message_type": "quiz_adaptation",
                    "adaptation_type": adaptation.value,
                    "generated_by": self.agent_id,
                },
                status=MessageStatus.PENDING,
                scheduled_for=datetime.now(timezone.utc),
            )

            self.db_session.add(message)
            self.db_session.commit()

            await self.message_sender.send_message(message)

    def get_adaptation_reason(
        self, context: "QuizContext", adaptation: QuizAdaptationType
    ) -> str:
        """Get reason for adaptation."""
        if adaptation == QuizAdaptationType.REDUCE_COMPLEXITY:
            return f"High stress level detected: {context.stress_level:.2f}"
        elif adaptation == QuizAdaptationType.INCREASE_SUPPORT:
            return f"Low engagement score: {context.engagement_score:.2f}"
        elif adaptation == QuizAdaptationType.FOCUS_ON_MOOD:
            return f"Mood distress detected: {context.mood_indicators.get('distress', 0):.2f}"
        else:
            return "Response clarity improvement needed"
