"""
Quiz Engine - Evaluation, Scoring, and Analytics (QW-023).

Consolidates:
    - quiz_response_evaluator.py
    - quiz_response_utils.py
    - quiz_metrics.py
    - quiz_report_generator.py

Total: 4 files → 1 file
"""

from __future__ import annotations

# Standard library imports
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

# Third-party imports
from sqlalchemy.ext.asyncio import AsyncSession

# Local application imports
from app.models.quiz import QuizResponse, QuizSession, QuizTemplate
from app.repositories.quiz import QuizResponseRepository, QuizSessionRepository
from app.schemas.quiz import QuizQuestion, QuestionType


class QuizEvaluator:
    """
    Service for evaluating quiz responses.

    Handles evaluation of different question types including
    multiple choice, text, and scale responses.

    Attributes:
        db: Database session.
        response_repo: Quiz response repository.
    """

    def __init__(
        self,
        db: AsyncSession,
        repository: Optional[QuizResponseRepository] = None,
    ):
        self.db = db
        self.response_repo = repository or QuizResponseRepository(db)
        self._logger = logging.getLogger(__name__)

    def evaluate_response(
        self, response: QuizResponse, question: QuizQuestion
    ) -> Dict[str, Any]:
        """Evaluate a quiz response."""
        if question.type == QuestionType.MULTIPLE_CHOICE:
            return self._evaluate_multiple_choice(response, question)
        elif question.type == QuestionType.TEXT:
            return self._evaluate_text(response, question)
        elif question.type == QuestionType.SCALE:
            return self._evaluate_scale(response, question)
        return {"is_correct": False, "score": 0}

    def _evaluate_multiple_choice(
        self, response: QuizResponse, question: QuizQuestion
    ) -> Dict[str, Any]:
        """Evaluate multiple choice response."""
        correct_option_ids = [opt.id for opt in question.options if opt.is_correct]
        response_value = response.response_value

        if isinstance(response_value, list):
            is_correct = set(response_value) == set(correct_option_ids)
        else:
            is_correct = response_value in correct_option_ids

        return {
            "is_correct": is_correct,
            "score": 1.0 if is_correct else 0.0,
            "correct_options": correct_option_ids,
        }

    def _evaluate_text(
        self, response: QuizResponse, question: QuizQuestion
    ) -> Dict[str, Any]:
        """Evaluate text response."""
        return {"is_correct": True, "score": 1.0, "requires_review": True}

    def _evaluate_scale(
        self, response: QuizResponse, question: QuizQuestion
    ) -> Dict[str, Any]:
        """Evaluate scale response."""
        return {
            "is_correct": True,
            "score": 1.0,
            "scale_value": response.response_value,
        }


class QuizScorer:
    """
    Service for scoring quiz sessions.

    Calculates total scores, percentages, and correct answer
    counts for completed quiz sessions.

    Attributes:
        db: Database session.
        evaluator: Quiz evaluator for response scoring.
    """

    def __init__(
        self,
        db: AsyncSession,
        evaluator: Optional[QuizEvaluator] = None,
    ):
        self.db = db
        self.evaluator = evaluator or QuizEvaluator(db)
        self._logger = logging.getLogger(__name__)

    def calculate_session_score(
        self, session: QuizSession, template: QuizTemplate
    ) -> Dict[str, Any]:
        """Calculate total score for a quiz session."""
        responses = session.responses
        questions = template.questions

        total_questions = len(questions)
        total_score = 0.0
        correct_answers = 0

        for response in responses:
            question = next(
                (q for q in questions if q.id == response.question_id), None
            )
            if question:
                evaluation = self.evaluator.evaluate_response(response, question)
                total_score += evaluation.get("score", 0.0)
                if evaluation.get("is_correct"):
                    correct_answers += 1

        return {
            "total_questions": total_questions,
            "total_score": total_score,
            "correct_answers": correct_answers,
            "percentage": (correct_answers / total_questions * 100)
            if total_questions > 0
            else 0,
        }


class QuizAnalyzer:
    """
    Service for quiz analytics and insights.

    Provides analytical data for patient quiz performance
    including completion rates and average scores.

    Attributes:
        db: Database session.
        session_repo: Quiz session repository.
    """

    def __init__(
        self,
        db: AsyncSession,
        repository: Optional[QuizSessionRepository] = None,
    ):
        self.db = db
        self.session_repo = repository or QuizSessionRepository(db)
        self._logger = logging.getLogger(__name__)

    def get_patient_analytics(self, patient_id: UUID) -> Dict[str, Any]:
        """Get analytics for a patient."""
        sessions = self.session_repo.get_by_patient(patient_id)

        return {
            "total_quizzes": len(sessions),
            "completed_quizzes": len([s for s in sessions if s.status == "completed"]),
            "average_score": self._calculate_average_score(sessions),
        }

    def _calculate_average_score(self, sessions: List[QuizSession]) -> float:
        """Calculate average score across sessions."""
        if not sessions:
            return 0.0
        scores = [s.score for s in sessions if s.score is not None]
        return sum(scores) / len(scores) if scores else 0.0


class ResponseUtils:
    """Utilities for response processing."""

    @staticmethod
    def normalize_response_value(value: Any, question_type: QuestionType) -> Any:
        """Normalize response value based on question type."""
        if question_type == QuestionType.MULTIPLE_CHOICE:
            if isinstance(value, str):
                return [value]
            return value
        elif question_type == QuestionType.SCALE:
            return int(value) if value else 0
        return str(value)

    @staticmethod
    def validate_response_format(value: Any, question: QuizQuestion) -> bool:
        """Validate response format matches question type."""
        if question.type == QuestionType.MULTIPLE_CHOICE:
            return isinstance(value, (str, list))
        elif question.type == QuestionType.SCALE:
            return isinstance(value, (int, float))
        return True


class QuizMetricsCollector:
    """
    Service for collecting quiz metrics.

    Collects and calculates metrics for quiz sessions
    including duration and completion rates.

    Attributes:
        db: Database session.
        session_repo: Quiz session repository.
    """

    def __init__(
        self,
        db: AsyncSession,
        repository: Optional[QuizSessionRepository] = None,
    ):
        self.db = db
        self.session_repo = repository or QuizSessionRepository(db)
        self._logger = logging.getLogger(__name__)

    def collect_metrics(self, session_id: UUID) -> Dict[str, Any]:
        """Collect metrics for a quiz session."""
        session = self.session_repo.get(session_id)
        if not session:
            return {}

        return {
            "session_id": str(session_id),
            "duration_seconds": (
                session.completed_at - session.started_at
            ).total_seconds()
            if session.completed_at
            else None,
            "response_count": len(session.responses),
            "completion_rate": self._calculate_completion_rate(session),
        }

    def _calculate_completion_rate(self, session: QuizSession) -> float:
        """Calculate completion rate."""
        total_questions = len(session.template.questions) if session.template else 0
        answered_questions = len(session.responses)
        return (
            (answered_questions / total_questions * 100) if total_questions > 0 else 0.0
        )


class QuizReportGenerator:
    """
    Service for generating quiz reports.

    Generates comprehensive reports for quiz sessions
    including scores and completion data.

    Attributes:
        db: Database session.
        scorer: Quiz scorer for score calculation.
        analyzer: Quiz analyzer for analytics.
    """

    def __init__(
        self,
        db: AsyncSession,
        scorer: Optional[QuizScorer] = None,
        analyzer: Optional[QuizAnalyzer] = None,
    ):
        self.db = db
        self.scorer = scorer or QuizScorer(db)
        self.analyzer = analyzer or QuizAnalyzer(db)
        self._logger = logging.getLogger(__name__)

    def generate_session_report(self, session_id: UUID) -> Dict[str, Any]:
        """Generate comprehensive report for a quiz session."""
        session = (
            self.db.query(QuizSession).filter(QuizSession.id == session_id).first()
        )
        if not session:
            return {}

        score_data = self.scorer.calculate_session_score(session, session.template)

        return {
            "session_id": str(session_id),
            "patient_id": str(session.patient_id),
            "template_name": session.template.name,
            "score_data": score_data,
            "completed_at": session.completed_at.isoformat()
            if session.completed_at
            else None,
            "status": session.status,
        }


def get_quiz_evaluator(db: Any) -> QuizEvaluator:
    """Get QuizEvaluator instance."""
    return QuizEvaluator(db)


def get_quiz_scorer(db: Any) -> QuizScorer:
    """Get QuizScorer instance."""
    return QuizScorer(db)
