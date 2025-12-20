"""
Question Presenter - Handles question delivery and personalization.

Manages question presentation, personalization, and template management.
"""

import logging
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.domain.agents.quiz.session_coordinator import QuizContext

from app.models.quiz import QuizTemplate
from app.models.message import Message, MessageType, MessageDirection, MessageStatus
from app.services.quiz import QuizTemplateService
from app.domain.messaging.delivery import MessageSender


class QuestionPresenter:
    """
    Presents quiz questions with intelligent personalization.

    Responsibilities:
    - Send quiz questions
    - Personalize question content
    - Apply AI-based personalization
    - Load and manage quiz templates
    - Create adaptive quizzes from templates
    - Determine question inclusion based on context
    """

    def __init__(
        self,
        db_session: Session,
        quiz_template_service: QuizTemplateService,
        message_sender: MessageSender,
        agent_id: str,
        gemini_client=None,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize question presenter."""
        self.db_session = db_session
        self.quiz_template_service = quiz_template_service
        self.message_sender = message_sender
        self.agent_id = agent_id
        self.gemini_client = gemini_client
        self.logger = logger or logging.getLogger(__name__)

        # Template cache
        self.quiz_templates: Dict[str, Dict[str, Any]] = {}

    async def send_quiz_question(
        self, context: "QuizContext", max_questions: int, stress_threshold: float
    ) -> Dict[str, Any]:
        """Send current quiz question with personalization."""
        try:
            if context.current_question_index >= len(context.template.questions):
                return {"success": False, "error": "No more questions"}

            question = context.template.questions[context.current_question_index]

            # Personalize question presentation
            question_content = await self.personalize_question(
                context, question, max_questions, stress_threshold
            )

            message = Message(
                patient_id=context.patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=question_content["content"],
                message_metadata={
                    "quiz_session_id": str(context.session.id),
                    "quiz_question_index": context.current_question_index,
                    "quiz_question_id": question["id"],
                    "message_type": "quiz_question",
                    "personalization_level": question_content["personalization_level"],
                    "generated_by": self.agent_id,
                },
                status=MessageStatus.PENDING,
                scheduled_for=datetime.now(timezone.utc),
            )

            self.db_session.add(message)
            self.db_session.commit()
            self.db_session.refresh(message)

            success = await self.message_sender.send_message(message)

            return {
                "success": success,
                "question_index": context.current_question_index,
                "question_id": question["id"],
            }

        except Exception as e:
            self.logger.error(f"Failed to send quiz question: {e}")
            return {"success": False, "error": str(e)}

    async def personalize_question(
        self,
        context: "QuizContext",
        question: Dict,
        max_questions: int,
        stress_threshold: float,
    ) -> Dict[str, Any]:
        """Personalize question based on context."""
        base_text = question["text"]
        personalization_level = "standard"

        try:
            # Add patient name for warmth
            if not any(
                name_word in base_text.lower() for name_word in ["você", "seu", "sua"]
            ):
                base_text = f"{context.patient_data.name}, {base_text.lower()}"
                personalization_level = "high"

            # Question number for progress tracking
            total_questions = min(len(context.template.questions), max_questions)
            progress_text = f"*Pergunta {context.current_question_index + 1} de {total_questions}:*\n\n"

            content = progress_text + base_text

            # Add options if available
            if question.get("options"):
                content += "\n\n*Opções:*"
                for option in question["options"]:
                    content += f"\n• {option['text']}"

            # Add supportive context for mood-related questions
            if (
                "humor" in question["text"].lower()
                or "sentindo" in question["text"].lower()
            ):
                if context.stress_level > stress_threshold:
                    content += "\n\n_Não se preocupe, não há resposta certa ou errada. Queremos apenas te conhecer melhor._"
                    personalization_level = "supportive"

            return {"content": content, "personalization_level": personalization_level}

        except Exception as e:
            self.logger.error(f"Question personalization failed: {e}")
            return {"content": base_text, "personalization_level": "standard"}

    async def load_quiz_templates(self) -> None:
        """Load available quiz templates."""
        try:
            templates, _ = self.quiz_template_service.get_templates(
                skip=0, limit=200, active_only=True
            )

            cached = 0
            for template in templates:
                try:
                    template_payload = template.dict()
                    template_name = template_payload.get("name")
                    if not template_name:
                        continue
                    self.quiz_templates[template_name] = template_payload
                    cached += 1
                except Exception as exc:
                    self.logger.warning(
                        "Could not cache quiz template '%s': %s",
                        getattr(template, "name", "unknown"),
                        exc,
                    )

            self.logger.info("Cached %s quiz templates from database", cached)

        except Exception as e:
            self.logger.error(f"Failed to load quiz templates from database: {e}")

    def get_quiz_template(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Get quiz template by name."""
        return self.quiz_templates.get(template_name)

    def get_questions_from_template(self, template_name: str) -> List[Dict[str, Any]]:
        """Extract questions from template."""
        template = self.get_quiz_template(template_name)
        if template and "questions" in template:
            return template["questions"]
        return []

    async def get_or_create_quiz_template(
        self, quiz_type: str, context: "QuizContext"
    ) -> Optional[QuizTemplate]:
        """Get or create quiz template based on type."""
        try:
            # Try to get existing template
            template_name = f"{quiz_type}_template"

            try:
                template_response = self.quiz_template_service.get_template_by_name(
                    template_name
                )
                return self.quiz_template_service.template_repository.get(
                    template_response.id
                )
            except Exception as e:
                self.logger.warning(
                    f"Failed to get quiz template '{template_name}': {e}", exc_info=True
                )

            # Create new template if needed - use existing logic from quiz_flow_integration.py
            # For now, return None to use default template creation
            return None

        except Exception as e:
            self.logger.error(f"Failed to get/create quiz template: {e}")
            return None

    async def create_adaptive_quiz_from_template(
        self, template_name: str, patient_context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create adaptive quiz based on template and patient context."""
        try:
            template = self.get_quiz_template(template_name)
            if not template:
                return None

            questions = self.get_questions_from_template(template_name)
            if not questions:
                return None

            # Apply personalization based on context
            personalized_questions = []

            for question in questions:
                # Check if question should be included based on context
                if self.should_include_question(question, patient_context):
                    personalized_question = await self.personalize_template_question(
                        question, patient_context
                    )
                    personalized_questions.append(personalized_question)

            return {
                "template_name": template_name,
                "original_questions": len(questions),
                "personalized_questions": len(personalized_questions),
                "questions": personalized_questions,
                "metadata": template.get("metadata", {}),
                "scoring": template.get("scoring", {}),
                "alerts": template.get("alerts", []),
            }

        except Exception as e:
            self.logger.error(
                f"Failed to create adaptive quiz from template {template_name}: {e}"
            )
            return None

    def should_include_question(
        self, question: Dict[str, Any], context: Dict[str, Any]
    ) -> bool:
        """Determine if question should be included based on context."""
        # Get question metadata
        metadata = question.get("metadata", {})
        importance = metadata.get("importance", "medium")
        category = metadata.get("category", "general")

        # Always include critical questions
        if importance == "critical":
            return True

        # Skip low importance questions if patient has low engagement
        engagement_score = context.get("engagement_score", 0.5)
        if importance == "low" and engagement_score < 0.4:
            return False

        # Context-specific filtering
        stress_level = context.get("stress_level", 0.0)
        if stress_level > 0.7 and category in ["detailed_symptoms", "lifestyle"]:
            return False  # Skip detailed questions if stressed

        return True

    async def personalize_template_question(
        self, question: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Personalize question based on patient context."""
        try:
            personalized_question = question.copy()

            # Replace patient name placeholders
            patient_name = context.get("patient_name", "Cliente")
            if "text" in personalized_question:
                personalized_question["text"] = (
                    personalized_question["text"]
                    .replace("{patient_name}", patient_name)
                    .replace("{name}", patient_name)
                )

            if "description" in personalized_question:
                personalized_question["description"] = (
                    personalized_question["description"]
                    .replace("{patient_name}", patient_name)
                    .replace("{name}", patient_name)
                )

            # Adjust question based on mood indicators
            mood_trend = context.get("mood_trend", 0.0)
            if mood_trend < -0.5:
                # Add supportive note for patients with mood decline
                supportive_note = " (Lembre-se: não há resposta certa ou errada, queremos apenas saber como você está)"
                if "description" in personalized_question:
                    personalized_question["description"] += supportive_note
                else:
                    personalized_question["description"] = supportive_note

            # Use AI for advanced personalization if available
            if self.gemini_client and context.get("use_ai_personalization", False):
                ai_personalized = await self.apply_ai_personalization(
                    personalized_question, context
                )
                if ai_personalized:
                    personalized_question = ai_personalized

            return personalized_question

        except Exception as e:
            self.logger.error(f"Failed to personalize question: {e}")
            return question  # Return original if personalization fails

    async def apply_ai_personalization(
        self, question: Dict[str, Any], context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Apply AI-based personalization to question."""
        try:
            # Prepare AI prompt
            ai_prompt = f"""
            Personalize esta pergunta de quiz médico para uma paciente de terapia hormonal:

            Pergunta original: {question.get("text", "")}
            Descrição: {question.get("description", "")}

            Contexto da paciente:
            - Nome: {context.get("patient_name", "Cliente")}
            - Tendência de humor: {context.get("mood_trend", 0)}
            - Nível de stress: {context.get("stress_level", 0)}
            - Nível de engajamento: {context.get("engagement_score", 0.5)}
            - Dia de tratamento: {context.get("current_day", 1)}

            Mantenha o tom acolhedor, empático e profissional.
            Mantenha a estrutura original da pergunta.
            Retorne apenas o texto personalizado da pergunta.
            """

            response = await self.gemini_client.generate_content(ai_prompt)

            if response and hasattr(response, "text"):
                personalized_text = response.text.strip()
                if personalized_text:
                    personalized_question = question.copy()
                    personalized_question["text"] = personalized_text
                    return personalized_question

        except Exception as e:
            self.logger.error(f"AI personalization failed: {e}")

        return None
