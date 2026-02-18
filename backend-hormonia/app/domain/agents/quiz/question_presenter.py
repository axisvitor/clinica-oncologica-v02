"""
Question Presenter - Handles question delivery and personalization.

Manages question presentation, personalization, and template management.
"""

from __future__ import annotations

# Standard library imports
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

# Third-party imports
from sqlalchemy.orm import Session

# Local application imports
from app.domain.messaging.delivery.idempotent_sender import IdempotentMessageSender
from app.models.quiz import QuizTemplate
from app.services.quiz import QuizTemplateService
from app.services.ai.guardrails import OutputKind
from .message_service import QuizMessageService

if TYPE_CHECKING:
    from app.domain.agents.quiz.types import QuizContext


class QuestionPresenter:
    """
    Presents quiz questions with intelligent personalization.

    Handles question delivery with context-aware personalization,
    template management, and AI-enhanced question adaptation.

    Attributes:
        db_session: Database session.
        quiz_template_service: Template service.
        message_sender: Message delivery service.
        agent_id: ID of owning agent.
        gemini_client: AI client for personalization.
        quiz_templates: Cached quiz templates.
    """

    def __init__(
        self,
        db_session: Session,
        quiz_template_service: QuizTemplateService,
        message_sender: IdempotentMessageSender,
        agent_id: str,
        gemini_client=None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize question presenter.

        Args:
            db_session: Database session.
            quiz_template_service: Quiz template service.
            message_sender: Message delivery service.
            agent_id: Agent identifier.
            gemini_client: Gemini AI client.
            logger: Logger instance.
        """
        self.db_session = db_session
        self.quiz_template_service = quiz_template_service
        self.message_sender = message_sender
        self.agent_id = agent_id
        self.gemini_client = gemini_client
        self._logger = logger or logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.message_service = QuizMessageService(
            db_session=db_session,
            message_sender=message_sender,
            logger=self._logger,
        )

        # Template cache
        self.quiz_templates: Dict[str, Dict[str, Any]] = {}

    async def send_quiz_question(
        self, context: "QuizContext", max_questions: int, stress_threshold: float
    ) -> Dict[str, Any]:
        """Send current quiz question with personalization."""
        try:
            template = getattr(context, "template", None)
            questions = getattr(template, "questions", None) if template else None
            if not isinstance(questions, list) or not questions:
                return {"success": False, "error": "Quiz template unavailable"}

            if context.current_question >= len(questions):
                return {"success": False, "error": "No more questions"}

            question = questions[context.current_question]
            session_id = getattr(getattr(context, "session", None), "id", None)
            if session_id is None:
                return {"success": False, "error": "Quiz session unavailable"}

            # Personalize question presentation
            question_content = await self.personalize_question(
                context, question, max_questions, stress_threshold
            )

            _, success = await self.message_service.create_and_send_text(
                patient_id=context.patient_id,
                content=question_content["content"],
                message_metadata={
                    "quiz_session_id": str(session_id),
                    "quiz_question_index": context.current_question,
                    "quiz_question_id": question.get("id"),
                    "message_type": "quiz_question",
                    "personalization_level": question_content["personalization_level"],
                    "generated_by": self.agent_id,
                },
            )

            return {
                "success": success,
                "question_index": context.current_question,
                "question_id": question.get("id"),
            }

        except Exception as e:
            self._logger.error(f"Failed to send quiz question: {e}")
            return {"success": False, "error": str(e)}

    async def personalize_question(
        self,
        context: "QuizContext",
        question: Dict,
        max_questions: int,
        stress_threshold: float,
    ) -> Dict[str, Any]:
        """Personalize question based on context."""
        base_text = question.get("text", "Como você está se sentindo hoje?")
        personalization_level = "standard"

        try:
            patient_name = getattr(getattr(context, "patient_data", None), "name", "")
            question_text = question.get("text", base_text)
            # Add patient name for warmth
            if not any(
                name_word in base_text.lower() for name_word in ["você", "seu", "sua"]
            ) and patient_name:
                base_text = f"{patient_name}, {base_text.lower()}"
                personalization_level = "high"

            # Question number for progress tracking
            template = getattr(context, "template", None)
            questions = getattr(template, "questions", None) if template else None
            total_questions = min(len(questions), max_questions) if questions else 1
            progress_text = (
                f"*Pergunta {context.current_question + 1} de {total_questions}:*\n\n"
            )

            content = progress_text + base_text

            # Add options if available
            if question.get("options"):
                content += "\n\n*Opções:*"
                for option in question["options"]:
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

            # Add supportive context for mood-related questions
            if (
                "humor" in question_text.lower()
                or "sentindo" in question_text.lower()
            ):
                if context.stress_level > stress_threshold:
                    content += "\n\n_Não se preocupe, não há resposta certa ou errada. Queremos apenas te conhecer melhor._"
                    personalization_level = "supportive"

            return {"content": content, "personalization_level": personalization_level}

        except Exception as e:
            self._logger.error(f"Question personalization failed: {e}")
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
                    self._logger.warning(
                        "Could not cache quiz template '%s': %s",
                        getattr(template, "name", "unknown"),
                        exc,
                    )

            self._logger.info("Cached %s quiz templates from database", cached)

        except Exception as e:
            self._logger.error(f"Failed to load quiz templates from database: {e}")

    def get_quiz_template(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Get quiz template by name."""
        return self.quiz_templates.get(template_name)

    def get_questions_from_template(self, template_name: str) -> List[Dict[str, Any]]:
        """Extract questions from template."""
        template = self.get_quiz_template(template_name)
        if template and "questions" in template:
            return template["questions"]
        return []

    @staticmethod
    def _extract_template_name(template_obj: Any) -> Optional[str]:
        """Extract template name from ORM, schema, or dict payload."""
        if template_obj is None:
            return None
        if isinstance(template_obj, dict):
            name = template_obj.get("name")
            return str(name) if name else None
        name = getattr(template_obj, "name", None)
        return str(name) if name else None

    def _build_template_candidates(self, quiz_type: str) -> List[str]:
        """Build ordered template-name candidates for a quiz type."""
        candidates: List[str] = []
        normalized = str(quiz_type or "").strip()

        # Prefer configured monthly default when available.
        try:
            from app.core.monthly_quiz_config import get_monthly_quiz_config

            default_template = (
                get_monthly_quiz_config().MONTHLY_QUIZ_DEFAULT_TEMPLATE or ""
            ).strip()
            if default_template:
                candidates.append(default_template)
        except Exception:
            # Keep behavior resilient if config is unavailable in non-prod contexts.
            pass

        if normalized:
            candidates.extend([f"{normalized}_template", normalized])

        # De-duplicate while preserving order.
        seen = set()
        return [
            candidate
            for candidate in candidates
            if candidate and not (candidate in seen or seen.add(candidate))
        ]

    async def get_or_create_quiz_template(
        self, quiz_type: str, context: "QuizContext"
    ) -> Optional[QuizTemplate]:
        """Get an active quiz template, using safe fallbacks when needed."""
        try:
            existing_template = getattr(context, "template", None)
            if existing_template is not None:
                return existing_template

            # 1) Try expected names for the requested quiz type.
            for template_name in self._build_template_candidates(quiz_type):
                template = self.quiz_template_service.get_template_by_name(template_name)
                if template:
                    return template

            # 2) Fall back to cached template names loaded at startup.
            for cached_name in list(self.quiz_templates.keys()):
                template = self.quiz_template_service.get_template_by_name(cached_name)
                if template:
                    return template

            # 3) Last-resort: first active template from database.
            templates, _ = self.quiz_template_service.get_templates(
                skip=0, limit=1, active_only=True
            )
            if templates:
                fallback_name = self._extract_template_name(templates[0])
                if fallback_name:
                    template = self.quiz_template_service.get_template_by_name(
                        fallback_name
                    )
                    if template:
                        return template

            self._logger.error(
                "No active quiz template found for quiz_type='%s'", quiz_type
            )
            return None

        except Exception as e:
            self._logger.error(f"Failed to get/create quiz template: {e}")
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
            self._logger.error(
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
            self._logger.error(f"Failed to personalize question: {e}")
            raise

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
            Regras de saída (obrigatório):
            - Retorne apenas o texto final da pergunta
            - Não inclua explicações, raciocínios ou meta-comentários
            - Não mencione prompt, instruções, políticas ou sistema
            - Não use markdown, listas, cabeçalhos ou blocos de código
            - Não envolva a resposta em aspas
            - Escreva apenas em português do Brasil
            """

            response = await self.gemini_client.generate_content(
                ai_prompt,
                output_kind=OutputKind.MESSAGE,
            )
            if not response:
                raise ValueError("AI returned empty quiz question")

            if hasattr(response, "text"):
                personalized_text = response.text.strip()
            else:
                personalized_text = str(response).strip()

            if personalized_text:
                personalized_question = question.copy()
                personalized_question["text"] = personalized_text
                return personalized_question

        except Exception as e:
            self._logger.error(f"AI personalization failed: {e}")
            raise
