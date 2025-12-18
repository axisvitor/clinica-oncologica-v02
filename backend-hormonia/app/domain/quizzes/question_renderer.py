"""
Question Renderer Module for Monthly Quiz Service.

Handles question formatting, context building, and template rendering.
Responsibilities: Question formatting, humanization (if enabled),
context preparation, and question display logic.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID

from app.models.quiz import QuizTemplate
from app.schemas.monthly_quiz import MonthlyQuizAccessResponse
from app.config import is_ai_humanization_enabled
from app.services.question_humanizer import get_question_humanizer
import logging

logger = logging.getLogger(__name__)


class QuestionRenderer:
    """Manages question rendering and formatting for quiz display."""

    def __init__(self):
        self.humanizer = (
            get_question_humanizer() if is_ai_humanization_enabled() else None
        )

    def render_quiz_access_response(
        self,
        quiz_session_id: UUID,
        patient_name: str,
        template: QuizTemplate,
        current_question_index: int,
        expires_at: datetime,
        new_token: Optional[str] = None,
    ) -> MonthlyQuizAccessResponse:
        """
        Build a complete quiz access response with formatted questions.

        Args:
            quiz_session_id: Quiz session UUID
            patient_name: Name of the patient
            template: Quiz template with questions
            current_question_index: Current question index
            expires_at: Token expiration datetime
            new_token: Optional rotated token

        Returns:
            MonthlyQuizAccessResponse with formatted questions
        """
        # Build response
        response = MonthlyQuizAccessResponse(
            quiz_session_id=quiz_session_id,
            patient_name=patient_name,
            template_name=template.name,
            template_version=template.version,
            questions=template.questions,
            current_question_index=current_question_index,
            total_questions=len(template.questions),
            expires_at=expires_at,
        )

        # Add rotated token if provided
        if new_token:
            response.new_token = new_token  # type: ignore

        return response

    def humanize_question_text(
        self,
        question_text: str,
        patient_name: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Humanize question text using AI if enabled.

        Args:
            question_text: Original question text
            patient_name: Patient name for personalization
            context: Additional context for humanization

        Returns:
            Humanized question text or original if humanization disabled
        """
        if not self.humanizer or not is_ai_humanization_enabled():
            return question_text

        try:
            humanized = self.humanizer.humanize(
                text=question_text, patient_name=patient_name, context=context or {}
            )
            return humanized
        except Exception as e:
            logger.warning(f"Failed to humanize question text: {e}")
            return question_text

    def format_question(
        self, question: Dict[str, Any], patient_name: str, humanize: bool = False
    ) -> Dict[str, Any]:
        """
        Format a single question for display.

        Args:
            question: Question dictionary from template
            patient_name: Patient name for personalization
            humanize: Whether to apply AI humanization

        Returns:
            Formatted question dictionary
        """
        formatted_question = question.copy()

        # Humanize question text if enabled
        if humanize and "text" in formatted_question:
            formatted_question["text"] = self.humanize_question_text(
                formatted_question["text"],
                patient_name,
                context={
                    "question_id": formatted_question.get("id"),
                    "question_type": formatted_question.get("type"),
                },
            )

        # Format options if present
        if "options" in formatted_question and isinstance(
            formatted_question["options"], list
        ):
            formatted_question["options"] = self._format_options(
                formatted_question["options"], patient_name, humanize
            )

        return formatted_question

    def _format_options(
        self, options: List[Any], patient_name: str, humanize: bool = False
    ) -> List[Any]:
        """
        Format question options for display.

        Args:
            options: List of question options
            patient_name: Patient name for personalization
            humanize: Whether to apply AI humanization

        Returns:
            Formatted options list
        """
        formatted_options = []

        for option in options:
            if isinstance(option, dict):
                formatted_option = option.copy()

                # Humanize option text if enabled
                if humanize and "label" in formatted_option:
                    formatted_option["label"] = self.humanize_question_text(
                        formatted_option["label"],
                        patient_name,
                        context={"type": "option"},
                    )

                formatted_options.append(formatted_option)
            else:
                formatted_options.append(option)

        return formatted_options

    def build_question_context(
        self,
        template: QuizTemplate,
        current_question_index: int,
        patient_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build context for question rendering.

        Args:
            template: Quiz template
            current_question_index: Current question index
            patient_data: Optional patient data for context

        Returns:
            Context dictionary for rendering
        """
        total_questions = len(template.questions)
        current_question = (
            template.questions[current_question_index]
            if current_question_index < total_questions
            else None
        )

        context = {
            "template_name": template.name,
            "template_version": template.version,
            "current_question_index": current_question_index,
            "total_questions": total_questions,
            "progress_percentage": round(
                (current_question_index / total_questions) * 100, 2
            )
            if total_questions > 0
            else 0,
            "current_question": current_question,
            "is_first_question": current_question_index == 0,
            "is_last_question": current_question_index == total_questions - 1,
            "questions_remaining": total_questions - current_question_index,
        }

        # Add patient data if provided
        if patient_data:
            context["patient"] = patient_data

        return context

    def format_questions_batch(
        self, questions: List[Dict[str, Any]], patient_name: str, humanize: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Format multiple questions for display.

        Args:
            questions: List of question dictionaries
            patient_name: Patient name for personalization
            humanize: Whether to apply AI humanization

        Returns:
            List of formatted questions
        """
        return [
            self.format_question(question, patient_name, humanize)
            for question in questions
        ]

    def get_question_summary(self, template: QuizTemplate) -> Dict[str, Any]:
        """
        Generate summary information about quiz questions.

        Args:
            template: Quiz template

        Returns:
            Summary dictionary with question statistics
        """
        questions = template.questions
        total_questions = len(questions)

        question_types = {}
        for question in questions:
            q_type = question.get("type", "unknown")
            question_types[q_type] = question_types.get(q_type, 0) + 1

        return {
            "total_questions": total_questions,
            "question_types": question_types,
            "template_name": template.name,
            "template_version": template.version,
            "estimated_time_minutes": total_questions
            * 2,  # Estimate 2 minutes per question
        }
