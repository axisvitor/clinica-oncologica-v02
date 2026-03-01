"""
Score Calculator Module for Monthly Quiz Service.

Handles score computation, result analysis, and scoring metrics.
Responsibilities: Score calculation, result aggregation, performance metrics,
and scoring rules enforcement.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.quiz import QuizResponse, QuizSession
import logging

logger = logging.getLogger(__name__)


class ScoreCalculator:
    """Calculates and analyzes quiz scores."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _has_answer_value(response_value: Any) -> bool:
        """Check whether a response should count as answered."""
        if response_value is None:
            return False
        if isinstance(response_value, str):
            return len(response_value.strip()) > 0
        if isinstance(response_value, (list, tuple, set, dict)):
            return len(response_value) > 0
        return True

    async def calculate_score(self, session_id: UUID) -> float:
        """
        Calculate score for a completed quiz session.

        Aggregates scores from all responses in the session where scores are available.
        Returns average score or 0 if no scored questions exist.

        Args:
            session_id: Quiz session UUID

        Returns:
            Calculated average score (0-100 scale)
        """
        # Query all responses for this session
        responses = (
            self.db.query(QuizResponse)
            .filter(QuizResponse.quiz_session_id == session_id)
            .all()
        )

        if not responses:
            return 0.0

        # Calculate score based on response_metadata
        total_score = 0.0
        scored_responses = 0

        for response in responses:
            metadata = response.response_metadata or {}
            if "score" in metadata and metadata["score"] is not None:
                total_score += float(metadata["score"])
                scored_responses += 1

        # Return average score if scored responses exist, otherwise 0
        return round(total_score / scored_responses, 2) if scored_responses > 0 else 0.0

    def calculate_question_score(
        self,
        response_value: Any,
        correct_answer: Any,
        question_type: str,
        scoring_rules: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Calculate score for a single question response.

        Args:
            response_value: User's response
            correct_answer: Correct answer (if applicable)
            question_type: Type of question
            scoring_rules: Optional custom scoring rules

        Returns:
            Score for this question (0-100)
        """
        if not correct_answer:
            # No correct answer defined, return default score
            return 100.0 if response_value else 0.0

        # Apply scoring rules based on question type
        if question_type == "single_choice":
            return 100.0 if response_value == correct_answer else 0.0
        elif question_type == "multiple_choice":
            return self._score_multiple_choice(
                response_value, correct_answer, scoring_rules
            )
        elif question_type == "numeric":
            return self._score_numeric(response_value, correct_answer, scoring_rules)
        elif question_type == "boolean":
            return 100.0 if response_value == correct_answer else 0.0
        else:
            # For open text and other types, manual scoring may be needed
            return 0.0

    def _score_multiple_choice(
        self,
        response_value: List[str],
        correct_answer: List[str],
        scoring_rules: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Score multiple choice question with partial credit.

        Args:
            response_value: User's selected options
            correct_answer: Correct options
            scoring_rules: Optional scoring rules

        Returns:
            Partial credit score (0-100)
        """
        if not isinstance(response_value, list):
            response_value = [response_value]
        if not isinstance(correct_answer, list):
            correct_answer = [correct_answer]

        correct_set = set(correct_answer)
        response_set = set(response_value)

        # Calculate correct and incorrect selections
        correct_selections = len(response_set & correct_set)
        incorrect_selections = len(response_set - correct_set)
        len(correct_set - response_set)

        # Apply partial credit scoring
        if scoring_rules and "partial_credit" in scoring_rules:
            points_per_correct = 100.0 / len(correct_set)
            score = correct_selections * points_per_correct

            # Deduct points for incorrect selections if configured
            if scoring_rules.get("penalize_incorrect", False):
                penalty_per_incorrect = points_per_correct * 0.5
                score -= incorrect_selections * penalty_per_incorrect

            return max(0.0, min(100.0, round(score, 2)))
        else:
            # All or nothing scoring
            return 100.0 if response_set == correct_set else 0.0

    def _score_numeric(
        self,
        response_value: float,
        correct_answer: float,
        scoring_rules: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Score numeric question with tolerance.

        Args:
            response_value: User's numeric response
            correct_answer: Correct numeric value
            scoring_rules: Optional scoring rules with tolerance

        Returns:
            Score based on accuracy (0-100)
        """
        try:
            response_val = float(response_value)
            correct_val = float(correct_answer)
        except (ValueError, TypeError):
            return 0.0

        # Check tolerance if specified
        if scoring_rules and "tolerance" in scoring_rules:
            tolerance = scoring_rules["tolerance"]
            if abs(response_val - correct_val) <= tolerance:
                return 100.0
            elif scoring_rules.get("partial_credit_numeric", False):
                # Partial credit based on distance from correct answer
                max_error = scoring_rules.get("max_error", tolerance * 2)
                error = abs(response_val - correct_val)
                if error > max_error:
                    return 0.0
                score = 100.0 * (1 - (error / max_error))
                return max(0.0, round(score, 2))
            else:
                return 0.0
        else:
            # Exact match required
            return 100.0 if response_val == correct_val else 0.0

    def calculate_session_statistics(self, session_id: UUID) -> Dict[str, Any]:
        """
        Calculate comprehensive statistics for a quiz session.

        Args:
            session_id: Quiz session UUID

        Returns:
            Dictionary with session statistics
        """
        responses = (
            self.db.query(QuizResponse)
            .filter(QuizResponse.quiz_session_id == session_id)
            .all()
        )

        session = (
            self.db.query(QuizSession).filter(QuizSession.id == session_id).first()
        )

        if not session or not responses:
            return {
                "total_questions": 0,
                "answered_questions": 0,
                "total_score": 0.0,
                "average_score": 0.0,
            }

        # Calculate statistics
        total_questions = len(responses)
        answered_questions = len(
            [r for r in responses if self._has_answer_value(r.response_value)]
        )

        scores = []
        for response in responses:
            metadata = response.response_metadata or {}
            if "score" in metadata and metadata["score"] is not None:
                scores.append(float(metadata["score"]))

        total_score = sum(scores) if scores else 0.0
        average_score = round(total_score / len(scores), 2) if scores else 0.0

        # Calculate completion time
        completion_time = None
        if session.completed_at and session.started_at:
            completion_time = (
                session.completed_at - session.started_at
            ).total_seconds()

        return {
            "session_id": str(session_id),
            "total_questions": total_questions,
            "answered_questions": answered_questions,
            "scored_questions": len(scores),
            "total_score": total_score,
            "average_score": average_score,
            "completion_time_seconds": completion_time,
            "status": session.status,
            "individual_scores": scores,
        }

    def calculate_percentile_rank(self, score: float, all_scores: List[float]) -> float:
        """
        Calculate percentile rank of a score among all scores.

        Args:
            score: The score to rank
            all_scores: List of all scores to compare against

        Returns:
            Percentile rank (0-100)
        """
        if not all_scores:
            return 0.0

        # Count scores below this score
        below_count = len([s for s in all_scores if s < score])
        percentile = (below_count / len(all_scores)) * 100

        return round(percentile, 2)

    def get_performance_category(self, score: float) -> str:
        """
        Categorize performance based on score.

        Args:
            score: Score value (0-100)

        Returns:
            Performance category string
        """
        if score >= 90:
            return "excellent"
        elif score >= 75:
            return "good"
        elif score >= 60:
            return "satisfactory"
        elif score >= 50:
            return "needs_improvement"
        else:
            return "poor"

    def calculate_aggregate_statistics(self, session_ids: List[UUID]) -> Dict[str, Any]:
        """
        Calculate aggregate statistics across multiple sessions.

        Args:
            session_ids: List of session UUIDs to analyze

        Returns:
            Aggregate statistics dictionary
        """
        all_scores = []
        all_completion_times = []

        for session_id in session_ids:
            stats = self.calculate_session_statistics(session_id)
            if stats["average_score"] > 0:
                all_scores.append(stats["average_score"])
            if stats["completion_time_seconds"]:
                all_completion_times.append(stats["completion_time_seconds"])

        if not all_scores:
            return {
                "total_sessions": len(session_ids),
                "average_score": 0.0,
                "median_score": 0.0,
                "min_score": 0.0,
                "max_score": 0.0,
            }

        all_scores.sort()
        median_score = all_scores[len(all_scores) // 2] if all_scores else 0.0

        avg_completion_time = (
            sum(all_completion_times) / len(all_completion_times)
            if all_completion_times
            else None
        )

        return {
            "total_sessions": len(session_ids),
            "sessions_with_scores": len(all_scores),
            "average_score": round(sum(all_scores) / len(all_scores), 2)
            if all_scores
            else 0.0,
            "median_score": median_score,
            "min_score": min(all_scores) if all_scores else 0.0,
            "max_score": max(all_scores) if all_scores else 0.0,
            "average_completion_time_seconds": avg_completion_time,
            "score_distribution": self._calculate_score_distribution(all_scores),
        }

    def _calculate_score_distribution(self, scores: List[float]) -> Dict[str, int]:
        """Calculate distribution of scores across performance categories."""
        distribution = {
            "excellent": 0,  # 90-100
            "good": 0,  # 75-89
            "satisfactory": 0,  # 60-74
            "needs_improvement": 0,  # 50-59
            "poor": 0,  # 0-49
        }

        for score in scores:
            category = self.get_performance_category(score)
            distribution[category] += 1

        return distribution
