"""
Quiz Question Humanizer Integration
Integrates intelligent humanization into quiz questions for better patient experience
"""

from __future__ import annotations

import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional
from uuid import UUID
from app.services.question_humanizer import get_question_humanizer
from app.config import is_ai_humanization_enabled
from app.models.patient import Patient

logger = logging.getLogger(__name__)

# Module-level executor removed - now using centralized executor manager
# Use get_cpu_executor() for humanization tasks


def get_humanizer_executor():
    """Get the shared CPU executor for humanization tasks."""
    from app.core.executors import get_cpu_executor
    return get_cpu_executor()


class QuizQuestionHumanizerIntegration:
    """
    Integration layer for applying intelligent humanization to quiz questions.
    """

    def __init__(self, db: Any):
        self.db = db
        self.question_humanizer = get_question_humanizer()

    async def humanize_quiz_questions(
        self,
        questions: List[Dict[str, Any]],
        patient_id: UUID,
        quiz_type: str = "monthly",
    ) -> List[Dict[str, Any]]:
        """
        Humanize a list of quiz questions with intelligent variation.

        Args:
            questions: List of question dictionaries
            patient_id: Patient UUID
            quiz_type: Type of quiz

        Returns:
            List of questions with humanized text
        """
        if not is_ai_humanization_enabled():
            return questions

        # Get patient for context
        patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            logger.warning(f"Patient {patient_id} not found - skipping humanization")
            return questions

        humanized_questions = []

        for question in questions:
            try:
                # Determine if this question can be humanized
                question_id = question.get("id", "")
                question_text = question.get("text", "")
                question_type = self._determine_quiz_question_type(question)

                # Check if it's a scored question that needs consistency
                if self._is_scored_question(question):
                    # Keep scored questions consistent
                    humanized_questions.append(question)
                    logger.debug(f"Scored question {question_id} kept consistent")
                    continue

                # Apply humanization
                humanized_text = await self.question_humanizer.humanize_question(
                    question=question_text,
                    question_type=question_type,
                    patient=patient,
                    context={
                        "quiz_type": quiz_type,
                        "question_id": question_id,
                        "question_metadata": question.get("metadata", {}),
                    },
                )

                # Create humanized question
                humanized_question = question.copy()
                humanized_question["text"] = humanized_text
                humanized_question["original_text"] = question_text
                humanized_question["humanized"] = True
                humanized_questions.append(humanized_question)

                logger.info(f"Question {question_id} humanized successfully")

            except Exception as e:
                logger.error(f"Failed to humanize question: {e}")
                # Fallback to original
                humanized_questions.append(question)

        return humanized_questions

    def humanize_single_question(
        self,
        question: Dict[str, Any],
        patient: Patient,
        quiz_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Humanize a single quiz question synchronously.

        Args:
            question: Question dictionary
            patient: Patient object
            quiz_context: Additional context

        Returns:
            Humanized question dictionary
        """
        if not is_ai_humanization_enabled():
            return question

        try:
            question_text = question.get("text", "")
            question_type = self._determine_quiz_question_type(question)

            # Check if it's a scored question
            if self._is_scored_question(question):
                return question

            async def _humanize():
                return await self.question_humanizer.humanize_question(
                    question=question_text,
                    question_type=question_type,
                    patient=patient,
                    context=quiz_context,
                )

            try:
                asyncio.get_running_loop()
            except RuntimeError:
                humanized_text = asyncio.run(_humanize())
            else:
                # Use centralized CPU executor for humanization work
                humanized_text = get_humanizer_executor().submit(
                    lambda: asyncio.run(_humanize())
                ).result()

            # Return humanized question
            humanized_question = question.copy()
            humanized_question["text"] = humanized_text
            humanized_question["original_text"] = question_text
            humanized_question["humanized"] = True

            return humanized_question

        except Exception as e:
            logger.error(f"Failed to humanize single question: {e}")
            return question

    def _determine_quiz_question_type(self, question: Dict[str, Any]) -> str:
        """
        Determine the type of quiz question for selective humanization.

        Args:
            question: Question dictionary

        Returns:
            Question type identifier
        """
        question_text = question.get("text", "").lower()
        question.get("id", "").lower()
        question_type = question.get("type", "").lower()

        # Check question type field
        if question_type in ["scale", "rating", "numeric"]:
            return "symptom_tracking"  # Needs consistency for scoring

        # Analyze question text for patterns
        if any(word in question_text for word in ["medicação", "medicamento", "dose"]):
            return "medication_verification"

        if any(word in question_text for word in ["como você está", "como se sente"]):
            return "daily_checkin"

        if any(word in question_text for word in ["dor", "náusea", "fadiga"]):
            return "symptom_tracking"

        if any(word in question_text for word in ["humor", "ansiedade", "tristeza"]):
            return "mood_assessment"

        if any(
            word in question_text
            for word in ["sugestões", "comentários", "observações"]
        ):
            return "feedback_request"

        # Default to general wellbeing
        return "general_wellbeing"

    def _is_scored_question(self, question: Dict[str, Any]) -> bool:
        """
        Check if question requires scoring consistency.

        Args:
            question: Question dictionary

        Returns:
            True if question needs exact wording for scoring
        """
        question_type = question.get("type", "").lower()
        question_id = question.get("id", "").lower()

        # Scored question types that need consistency
        scored_types = ["scale", "rating", "numeric", "likert"]
        if question_type in scored_types:
            return True

        # Check for scoring patterns in ID
        scoring_patterns = ["score_", "scale_", "rating_", "level_"]
        if any(pattern in question_id for pattern in scoring_patterns):
            return True

        # Check if question has validation rules that depend on exact values
        validation_rules = question.get("validation_rules", [])
        if validation_rules and any(
            rule.get("type") == "exact_match" for rule in validation_rules
        ):
            return True

        return False


# Module-level sentinel to prevent duplicate patching
_QUIZ_HUMANIZER_PATCHED = False


def integrate_humanization_into_quiz_service():
    """
    Patch to integrate humanization into existing quiz service (idempotent).
    Should be called during system initialization.
    """
    global _QUIZ_HUMANIZER_PATCHED

    # Return early if already patched
    if _QUIZ_HUMANIZER_PATCHED:
        return True

    from app.services.quiz import QuizSessionService

    if not hasattr(QuizSessionService, "_enrich_session_response"):
        logger.warning(
            "Quiz humanization patch skipped: _enrich_session_response not found on QuizSessionService"
        )
        return False

    # Save original method
    original_enrich = QuizSessionService._enrich_session_response

    def enhanced_enrich_session_response(self, session):
        """Enhanced version with question humanization."""
        # Get original enriched response
        response = original_enrich(self, session)

        # Apply humanization to questions if available
        if hasattr(session, "quiz_template") and session.quiz_template:
            try:
                # Get patient for context
                patient = session.patient if hasattr(session, "patient") else None
                if patient and is_ai_humanization_enabled():
                    integrator = QuizQuestionHumanizerIntegration(self.db)

                    # Humanize template questions
                    if session.quiz_template.questions:
                        humanized_questions = []
                        for question in session.quiz_template.questions:
                            humanized = integrator.humanize_single_question(
                                question=question,
                                patient=patient,
                                quiz_context={"session_id": session.id},
                            )
                            humanized_questions.append(humanized)

                        # Update response with humanized questions
                        response.humanized_questions = humanized_questions

            except Exception as e:
                logger.error(f"Failed to integrate humanization: {e}")

        return response

    # Apply patch
    QuizSessionService._enrich_session_response = enhanced_enrich_session_response

    _QUIZ_HUMANIZER_PATCHED = True
    logger.info("Quiz humanization integration successfully patched")
    return True


# Auto-integrate disabled - patch causes issues with instance methods
# To enable humanization, call integrate_humanization_into_quiz_service() explicitly
# after proper refactoring to support instance method patching
# if __name__ != "__main__":
#     try:
#         integrate_humanization_into_quiz_service()
#     except Exception as e:
#         logger.error(f"Failed to auto-integrate quiz humanization: {e}")
