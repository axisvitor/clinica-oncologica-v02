"""
Comprehensive Unit Tests for Quiz Score Calculator.

Tests cover:
- calculate_score() - session score aggregation
- calculate_question_score() - per-question scoring
- _score_multiple_choice() - partial credit scoring
- _score_numeric() - tolerance-based scoring
- calculate_session_statistics() - comprehensive stats
- calculate_percentile_rank() - ranking logic
- get_performance_category() - category thresholds
- Edge cases: empty responses, all correct, all wrong, partial
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from unittest.mock import MagicMock, patch
from uuid import uuid4, UUID

from app.domain.quizzes.score_calculator import ScoreCalculator
from app.models.quiz import QuizResponse, QuizSession


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def score_calculator(mock_db):
    """Create a ScoreCalculator instance with mock db."""
    return ScoreCalculator(mock_db)


@pytest.fixture
def sample_session_id() -> UUID:
    """Generate a sample session UUID."""
    return uuid4()


def create_mock_response(
    session_id: UUID,
    score: Optional[float] = None,
    response_value: Any = "test_answer",
    response_metadata: Optional[Dict[str, Any]] = None
) -> MagicMock:
    """Factory function to create mock QuizResponse objects."""
    mock_response = MagicMock(spec=QuizResponse)
    mock_response.quiz_session_id = session_id
    mock_response.response_value = response_value
    mock_response.response_metadata = response_metadata or {}
    if score is not None:
        mock_response.response_metadata = {"score": score}
    return mock_response


def create_mock_session(
    session_id: UUID,
    status: str = "completed",
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None
) -> MagicMock:
    """Factory function to create mock QuizSession objects."""
    mock_session = MagicMock(spec=QuizSession)
    mock_session.id = session_id
    mock_session.status = status
    mock_session.started_at = started_at or datetime.now(timezone.utc)
    mock_session.completed_at = completed_at
    return mock_session


# =============================================================================
# Tests for calculate_score()
# =============================================================================


class TestCalculateScore:
    """Tests for calculate_score() - session score aggregation."""

    @pytest.mark.asyncio
    async def test_calculate_score_with_multiple_scored_responses(
        self, score_calculator, mock_db, sample_session_id
    ):
        """Test score calculation with multiple scored responses."""
        responses = [
            create_mock_response(sample_session_id, score=100.0),
            create_mock_response(sample_session_id, score=80.0),
            create_mock_response(sample_session_id, score=60.0),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = responses

        result = await score_calculator.calculate_score(sample_session_id)

        assert result == 80.0  # (100 + 80 + 60) / 3 = 80

    @pytest.mark.asyncio
    async def test_calculate_score_with_no_responses(
        self, score_calculator, mock_db, sample_session_id
    ):
        """Test score calculation returns 0 when no responses exist."""
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = await score_calculator.calculate_score(sample_session_id)

        assert result == 0.0

    @pytest.mark.asyncio
    async def test_calculate_score_with_unscored_responses(
        self, score_calculator, mock_db, sample_session_id
    ):
        """Test score calculation ignores responses without scores."""
        responses = [
            create_mock_response(sample_session_id, score=100.0),
            create_mock_response(sample_session_id, score=None),  # No score
            create_mock_response(sample_session_id, score=50.0),
        ]
        # Handle response without score key
        responses[1].response_metadata = {}
        mock_db.query.return_value.filter.return_value.all.return_value = responses

        result = await score_calculator.calculate_score(sample_session_id)

        assert result == 75.0  # (100 + 50) / 2 = 75

    @pytest.mark.asyncio
    async def test_calculate_score_all_perfect(
        self, score_calculator, mock_db, sample_session_id
    ):
        """Test score calculation with all perfect scores."""
        responses = [
            create_mock_response(sample_session_id, score=100.0),
            create_mock_response(sample_session_id, score=100.0),
            create_mock_response(sample_session_id, score=100.0),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = responses

        result = await score_calculator.calculate_score(sample_session_id)

        assert result == 100.0

    @pytest.mark.asyncio
    async def test_calculate_score_all_zero(
        self, score_calculator, mock_db, sample_session_id
    ):
        """Test score calculation with all zero scores."""
        responses = [
            create_mock_response(sample_session_id, score=0.0),
            create_mock_response(sample_session_id, score=0.0),
            create_mock_response(sample_session_id, score=0.0),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = responses

        result = await score_calculator.calculate_score(sample_session_id)

        assert result == 0.0

    @pytest.mark.asyncio
    async def test_calculate_score_single_response(
        self, score_calculator, mock_db, sample_session_id
    ):
        """Test score calculation with single response."""
        responses = [create_mock_response(sample_session_id, score=75.0)]
        mock_db.query.return_value.filter.return_value.all.return_value = responses

        result = await score_calculator.calculate_score(sample_session_id)

        assert result == 75.0

    @pytest.mark.asyncio
    async def test_calculate_score_rounds_to_two_decimals(
        self, score_calculator, mock_db, sample_session_id
    ):
        """Test that score is rounded to 2 decimal places."""
        responses = [
            create_mock_response(sample_session_id, score=33.33),
            create_mock_response(sample_session_id, score=33.33),
            create_mock_response(sample_session_id, score=33.34),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = responses

        result = await score_calculator.calculate_score(sample_session_id)

        assert result == 33.33  # Rounded average

    @pytest.mark.asyncio
    async def test_calculate_score_with_null_metadata(
        self, score_calculator, mock_db, sample_session_id
    ):
        """Test score calculation handles null response_metadata."""
        response = MagicMock(spec=QuizResponse)
        response.quiz_session_id = sample_session_id
        response.response_metadata = None
        mock_db.query.return_value.filter.return_value.all.return_value = [response]

        result = await score_calculator.calculate_score(sample_session_id)

        assert result == 0.0


# =============================================================================
# Tests for calculate_question_score()
# =============================================================================


class TestCalculateQuestionScore:
    """Tests for calculate_question_score() - per-question scoring."""

    def test_single_choice_correct(self, score_calculator):
        """Test single choice question with correct answer."""
        result = score_calculator.calculate_question_score(
            response_value="A",
            correct_answer="A",
            question_type="single_choice"
        )
        assert result == 100.0

    def test_single_choice_incorrect(self, score_calculator):
        """Test single choice question with incorrect answer."""
        result = score_calculator.calculate_question_score(
            response_value="B",
            correct_answer="A",
            question_type="single_choice"
        )
        assert result == 0.0

    def test_boolean_correct(self, score_calculator):
        """Test boolean question with correct answer."""
        result = score_calculator.calculate_question_score(
            response_value=True,
            correct_answer=True,
            question_type="boolean"
        )
        assert result == 100.0

    def test_boolean_incorrect(self, score_calculator):
        """Test boolean question with incorrect answer."""
        result = score_calculator.calculate_question_score(
            response_value=False,
            correct_answer=True,
            question_type="boolean"
        )
        assert result == 0.0

    def test_no_correct_answer_with_response(self, score_calculator):
        """Test question without correct answer returns 100 if answered."""
        result = score_calculator.calculate_question_score(
            response_value="any answer",
            correct_answer=None,
            question_type="open_text"
        )
        assert result == 100.0

    def test_no_correct_answer_empty_response(self, score_calculator):
        """Test question without correct answer returns 0 if empty."""
        result = score_calculator.calculate_question_score(
            response_value="",
            correct_answer=None,
            question_type="open_text"
        )
        assert result == 0.0

    def test_no_correct_answer_none_response(self, score_calculator):
        """Test question without correct answer returns 0 if None."""
        result = score_calculator.calculate_question_score(
            response_value=None,
            correct_answer=None,
            question_type="open_text"
        )
        assert result == 0.0

    def test_unknown_question_type(self, score_calculator):
        """Test unknown question type returns 0."""
        result = score_calculator.calculate_question_score(
            response_value="answer",
            correct_answer="answer",
            question_type="unknown_type"
        )
        assert result == 0.0

    def test_multiple_choice_delegated(self, score_calculator):
        """Test multiple choice delegates to _score_multiple_choice."""
        with patch.object(
            score_calculator, "_score_multiple_choice", return_value=75.0
        ) as mock_method:
            result = score_calculator.calculate_question_score(
                response_value=["A", "B"],
                correct_answer=["A", "B", "C"],
                question_type="multiple_choice",
                scoring_rules={"partial_credit": True}
            )
            mock_method.assert_called_once()
            assert result == 75.0

    def test_numeric_delegated(self, score_calculator):
        """Test numeric question delegates to _score_numeric."""
        with patch.object(
            score_calculator, "_score_numeric", return_value=100.0
        ) as mock_method:
            result = score_calculator.calculate_question_score(
                response_value=42.0,
                correct_answer=42.0,
                question_type="numeric",
                scoring_rules={"tolerance": 0.1}
            )
            mock_method.assert_called_once()
            assert result == 100.0


# =============================================================================
# Tests for _score_multiple_choice()
# =============================================================================


class TestScoreMultipleChoice:
    """Tests for _score_multiple_choice() - partial credit scoring."""

    def test_all_correct_selections(self, score_calculator):
        """Test all correct options selected."""
        result = score_calculator._score_multiple_choice(
            response_value=["A", "B", "C"],
            correct_answer=["A", "B", "C"],
            scoring_rules=None
        )
        assert result == 100.0

    def test_all_correct_partial_credit(self, score_calculator):
        """Test all correct with partial credit enabled."""
        result = score_calculator._score_multiple_choice(
            response_value=["A", "B"],
            correct_answer=["A", "B"],
            scoring_rules={"partial_credit": True}
        )
        assert result == 100.0

    def test_some_correct_no_partial_credit(self, score_calculator):
        """Test partial selection without partial credit returns 0."""
        result = score_calculator._score_multiple_choice(
            response_value=["A"],
            correct_answer=["A", "B"],
            scoring_rules=None
        )
        assert result == 0.0

    def test_some_correct_with_partial_credit(self, score_calculator):
        """Test partial selection with partial credit gives partial score."""
        result = score_calculator._score_multiple_choice(
            response_value=["A"],
            correct_answer=["A", "B"],
            scoring_rules={"partial_credit": True}
        )
        assert result == 50.0  # 1/2 correct

    def test_two_of_three_correct_partial_credit(self, score_calculator):
        """Test 2 of 3 correct with partial credit."""
        result = score_calculator._score_multiple_choice(
            response_value=["A", "B"],
            correct_answer=["A", "B", "C"],
            scoring_rules={"partial_credit": True}
        )
        assert result == pytest.approx(66.67, rel=0.01)

    def test_all_wrong_selections(self, score_calculator):
        """Test all incorrect selections."""
        result = score_calculator._score_multiple_choice(
            response_value=["D", "E"],
            correct_answer=["A", "B", "C"],
            scoring_rules=None
        )
        assert result == 0.0

    def test_incorrect_with_penalty(self, score_calculator):
        """Test incorrect selections with penalty deduction."""
        result = score_calculator._score_multiple_choice(
            response_value=["A", "D"],  # 1 correct, 1 incorrect
            correct_answer=["A", "B"],
            scoring_rules={"partial_credit": True, "penalize_incorrect": True}
        )
        # 50 points for A, -25 points penalty for D
        assert result == 25.0

    def test_penalty_does_not_go_negative(self, score_calculator):
        """Test penalty score is capped at 0."""
        result = score_calculator._score_multiple_choice(
            response_value=["D", "E", "F", "G"],  # All wrong
            correct_answer=["A"],
            scoring_rules={"partial_credit": True, "penalize_incorrect": True}
        )
        assert result == 0.0

    def test_single_value_converted_to_list(self, score_calculator):
        """Test single value response is converted to list."""
        result = score_calculator._score_multiple_choice(
            response_value="A",  # String instead of list
            correct_answer=["A"],
            scoring_rules=None
        )
        assert result == 100.0

    def test_single_correct_converted_to_list(self, score_calculator):
        """Test single correct answer is converted to list."""
        result = score_calculator._score_multiple_choice(
            response_value=["A"],
            correct_answer="A",  # String instead of list
            scoring_rules=None
        )
        assert result == 100.0

    def test_empty_response(self, score_calculator):
        """Test empty response list."""
        result = score_calculator._score_multiple_choice(
            response_value=[],
            correct_answer=["A", "B"],
            scoring_rules=None
        )
        assert result == 0.0

    def test_empty_response_partial_credit(self, score_calculator):
        """Test empty response with partial credit."""
        result = score_calculator._score_multiple_choice(
            response_value=[],
            correct_answer=["A", "B"],
            scoring_rules={"partial_credit": True}
        )
        assert result == 0.0

    def test_score_capped_at_100(self, score_calculator):
        """Test score is capped at 100 (edge case protection)."""
        # This tests the max() clamp
        result = score_calculator._score_multiple_choice(
            response_value=["A", "B", "C"],
            correct_answer=["A", "B", "C"],
            scoring_rules={"partial_credit": True}
        )
        assert result <= 100.0


# =============================================================================
# Tests for _score_numeric()
# =============================================================================


class TestScoreNumeric:
    """Tests for _score_numeric() - tolerance-based scoring."""

    def test_exact_match_no_tolerance(self, score_calculator):
        """Test exact match without tolerance."""
        result = score_calculator._score_numeric(
            response_value=42.0,
            correct_answer=42.0,
            scoring_rules=None
        )
        assert result == 100.0

    def test_exact_match_integer(self, score_calculator):
        """Test exact match with integers."""
        result = score_calculator._score_numeric(
            response_value=42,
            correct_answer=42,
            scoring_rules=None
        )
        assert result == 100.0

    def test_no_match_no_tolerance(self, score_calculator):
        """Test no match without tolerance."""
        result = score_calculator._score_numeric(
            response_value=43.0,
            correct_answer=42.0,
            scoring_rules=None
        )
        assert result == 0.0

    def test_within_tolerance(self, score_calculator):
        """Test value within tolerance range."""
        result = score_calculator._score_numeric(
            response_value=42.5,
            correct_answer=42.0,
            scoring_rules={"tolerance": 1.0}
        )
        assert result == 100.0

    def test_at_tolerance_boundary(self, score_calculator):
        """Test value exactly at tolerance boundary."""
        result = score_calculator._score_numeric(
            response_value=43.0,
            correct_answer=42.0,
            scoring_rules={"tolerance": 1.0}
        )
        assert result == 100.0

    def test_outside_tolerance(self, score_calculator):
        """Test value outside tolerance range."""
        result = score_calculator._score_numeric(
            response_value=45.0,
            correct_answer=42.0,
            scoring_rules={"tolerance": 1.0}
        )
        assert result == 0.0

    def test_partial_credit_within_max_error(self, score_calculator):
        """Test partial credit for value within max_error."""
        result = score_calculator._score_numeric(
            response_value=44.0,  # 2 away from correct
            correct_answer=42.0,
            scoring_rules={
                "tolerance": 1.0,
                "partial_credit_numeric": True,
                "max_error": 4.0  # 2/4 error = 50% score
            }
        )
        assert result == 50.0

    def test_partial_credit_default_max_error(self, score_calculator):
        """Test partial credit with default max_error (tolerance * 2)."""
        result = score_calculator._score_numeric(
            response_value=43.0,  # 1 away from correct
            correct_answer=42.0,
            scoring_rules={
                "tolerance": 0.5,  # Default max_error = 1.0
                "partial_credit_numeric": True
            }
        )
        # error = 1, max_error = 1, score = 100 * (1 - 1/1) = 0
        # Actually since error > tolerance, it calculates partial credit
        assert result == 0.0

    def test_partial_credit_exceeds_max_error(self, score_calculator):
        """Test partial credit returns 0 when exceeding max_error."""
        result = score_calculator._score_numeric(
            response_value=50.0,
            correct_answer=42.0,
            scoring_rules={
                "tolerance": 1.0,
                "partial_credit_numeric": True,
                "max_error": 4.0
            }
        )
        assert result == 0.0

    def test_invalid_response_non_numeric(self, score_calculator):
        """Test invalid non-numeric response returns 0."""
        result = score_calculator._score_numeric(
            response_value="not a number",
            correct_answer=42.0,
            scoring_rules=None
        )
        assert result == 0.0

    def test_invalid_correct_answer_non_numeric(self, score_calculator):
        """Test invalid non-numeric correct answer returns 0."""
        result = score_calculator._score_numeric(
            response_value=42.0,
            correct_answer="not a number",
            scoring_rules=None
        )
        assert result == 0.0

    def test_none_response_value(self, score_calculator):
        """Test None response value returns 0."""
        result = score_calculator._score_numeric(
            response_value=None,
            correct_answer=42.0,
            scoring_rules=None
        )
        assert result == 0.0

    def test_string_numeric_conversion(self, score_calculator):
        """Test string numeric values are converted."""
        result = score_calculator._score_numeric(
            response_value="42.0",
            correct_answer="42",
            scoring_rules=None
        )
        assert result == 100.0

    def test_negative_numbers(self, score_calculator):
        """Test negative number comparison."""
        result = score_calculator._score_numeric(
            response_value=-5.0,
            correct_answer=-5.0,
            scoring_rules=None
        )
        assert result == 100.0

    def test_negative_with_tolerance(self, score_calculator):
        """Test negative numbers with tolerance."""
        result = score_calculator._score_numeric(
            response_value=-4.5,
            correct_answer=-5.0,
            scoring_rules={"tolerance": 1.0}
        )
        assert result == 100.0


# =============================================================================
# Tests for calculate_session_statistics()
# =============================================================================


class TestCalculateSessionStatistics:
    """Tests for calculate_session_statistics() - comprehensive stats."""

    def test_complete_session_statistics(
        self, score_calculator, mock_db, sample_session_id
    ):
        """Test complete session statistics calculation."""
        started = datetime.now(timezone.utc) - timedelta(minutes=30)
        completed = datetime.now(timezone.utc)

        responses = [
            create_mock_response(sample_session_id, score=100.0, response_value="A"),
            create_mock_response(sample_session_id, score=80.0, response_value="B"),
            create_mock_response(sample_session_id, score=60.0, response_value="C"),
        ]
        session = create_mock_session(
            sample_session_id,
            status="completed",
            started_at=started,
            completed_at=completed
        )

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.all.return_value = responses
        mock_query.filter.return_value.first.return_value = session

        result = score_calculator.calculate_session_statistics(sample_session_id)

        assert result["session_id"] == str(sample_session_id)
        assert result["total_questions"] == 3
        assert result["answered_questions"] == 3
        assert result["scored_questions"] == 3
        assert result["total_score"] == 240.0
        assert result["average_score"] == 80.0
        assert result["status"] == "completed"
        assert result["individual_scores"] == [100.0, 80.0, 60.0]
        assert result["completion_time_seconds"] is not None

    def test_empty_session_statistics(
        self, score_calculator, mock_db, sample_session_id
    ):
        """Test statistics for session with no responses."""
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.all.return_value = []
        mock_query.filter.return_value.first.return_value = None

        result = score_calculator.calculate_session_statistics(sample_session_id)

        assert result["total_questions"] == 0
        assert result["answered_questions"] == 0
        assert result["total_score"] == 0.0
        assert result["average_score"] == 0.0

    def test_session_not_found(
        self, score_calculator, mock_db, sample_session_id
    ):
        """Test statistics when session doesn't exist."""
        responses = [create_mock_response(sample_session_id, score=100.0)]

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.all.return_value = responses
        mock_query.filter.return_value.first.return_value = None

        result = score_calculator.calculate_session_statistics(sample_session_id)

        assert result["total_questions"] == 0
        assert result["average_score"] == 0.0

    def test_partial_scored_responses(
        self, score_calculator, mock_db, sample_session_id
    ):
        """Test statistics with some unscored responses."""
        responses = [
            create_mock_response(sample_session_id, score=100.0, response_value="A"),
            create_mock_response(sample_session_id, score=None, response_value="B"),
            create_mock_response(sample_session_id, score=50.0, response_value="C"),
        ]
        responses[1].response_metadata = {}
        session = create_mock_session(sample_session_id)

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.all.return_value = responses
        mock_query.filter.return_value.first.return_value = session

        result = score_calculator.calculate_session_statistics(sample_session_id)

        assert result["total_questions"] == 3
        assert result["scored_questions"] == 2
        assert result["average_score"] == 75.0  # (100 + 50) / 2

    def test_session_without_completion_time(
        self, score_calculator, mock_db, sample_session_id
    ):
        """Test statistics when session not completed."""
        responses = [create_mock_response(sample_session_id, score=50.0, response_value="A")]
        session = create_mock_session(
            sample_session_id,
            status="started",
            completed_at=None
        )

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.all.return_value = responses
        mock_query.filter.return_value.first.return_value = session

        result = score_calculator.calculate_session_statistics(sample_session_id)

        assert result["completion_time_seconds"] is None
        assert result["status"] == "started"

    def test_responses_with_empty_values(
        self, score_calculator, mock_db, sample_session_id
    ):
        """Test statistics counts only non-empty response values."""
        responses = [
            create_mock_response(sample_session_id, score=100.0, response_value="A"),
            create_mock_response(sample_session_id, score=0.0, response_value=""),
            create_mock_response(sample_session_id, score=0.0, response_value=None),
        ]
        session = create_mock_session(sample_session_id)

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.all.return_value = responses
        mock_query.filter.return_value.first.return_value = session

        result = score_calculator.calculate_session_statistics(sample_session_id)

        assert result["total_questions"] == 3
        assert result["answered_questions"] == 1  # Only "A" is truthy


# =============================================================================
# Tests for calculate_percentile_rank()
# =============================================================================


class TestCalculatePercentileRank:
    """Tests for calculate_percentile_rank() - ranking logic."""

    def test_highest_score(self, score_calculator):
        """Test highest score percentile."""
        result = score_calculator.calculate_percentile_rank(
            score=100.0,
            all_scores=[50.0, 60.0, 70.0, 80.0, 90.0]
        )
        assert result == 100.0  # Higher than all 5 scores

    def test_lowest_score(self, score_calculator):
        """Test lowest score percentile."""
        result = score_calculator.calculate_percentile_rank(
            score=10.0,
            all_scores=[50.0, 60.0, 70.0, 80.0, 90.0]
        )
        assert result == 0.0  # Lower than all scores

    def test_middle_score(self, score_calculator):
        """Test middle score percentile."""
        result = score_calculator.calculate_percentile_rank(
            score=70.0,
            all_scores=[50.0, 60.0, 70.0, 80.0, 90.0]
        )
        assert result == 40.0  # Better than 2 out of 5 (40%)

    def test_empty_scores_list(self, score_calculator):
        """Test percentile with empty comparison list."""
        result = score_calculator.calculate_percentile_rank(
            score=75.0,
            all_scores=[]
        )
        assert result == 0.0

    def test_single_score_list(self, score_calculator):
        """Test percentile with single comparison score."""
        result = score_calculator.calculate_percentile_rank(
            score=80.0,
            all_scores=[70.0]
        )
        assert result == 100.0  # Better than 1 out of 1

    def test_equal_scores(self, score_calculator):
        """Test percentile with equal scores."""
        result = score_calculator.calculate_percentile_rank(
            score=70.0,
            all_scores=[70.0, 70.0, 70.0]
        )
        assert result == 0.0  # Not strictly better than any

    def test_percentile_rounded(self, score_calculator):
        """Test percentile is rounded to 2 decimal places."""
        result = score_calculator.calculate_percentile_rank(
            score=75.0,
            all_scores=[50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        )
        # Better than 3 out of 6 = 50%
        assert result == 50.0

    def test_large_score_list(self, score_calculator):
        """Test percentile with large list."""
        all_scores = list(range(0, 101, 1))  # 0, 1, 2, ..., 100
        result = score_calculator.calculate_percentile_rank(
            score=50.0,
            all_scores=all_scores
        )
        # Better than 50 scores (0-49), total 101 scores
        assert result == pytest.approx(49.5, rel=0.01)


# =============================================================================
# Tests for get_performance_category()
# =============================================================================


class TestGetPerformanceCategory:
    """Tests for get_performance_category() - category thresholds."""

    def test_excellent_score_100(self, score_calculator):
        """Test 100 score returns excellent."""
        result = score_calculator.get_performance_category(100.0)
        assert result == "excellent"

    def test_excellent_score_90(self, score_calculator):
        """Test 90 score returns excellent."""
        result = score_calculator.get_performance_category(90.0)
        assert result == "excellent"

    def test_excellent_score_95(self, score_calculator):
        """Test 95 score returns excellent."""
        result = score_calculator.get_performance_category(95.0)
        assert result == "excellent"

    def test_good_score_89(self, score_calculator):
        """Test 89 score returns good."""
        result = score_calculator.get_performance_category(89.0)
        assert result == "good"

    def test_good_score_75(self, score_calculator):
        """Test 75 score returns good."""
        result = score_calculator.get_performance_category(75.0)
        assert result == "good"

    def test_good_score_80(self, score_calculator):
        """Test 80 score returns good."""
        result = score_calculator.get_performance_category(80.0)
        assert result == "good"

    def test_satisfactory_score_74(self, score_calculator):
        """Test 74 score returns satisfactory."""
        result = score_calculator.get_performance_category(74.0)
        assert result == "satisfactory"

    def test_satisfactory_score_60(self, score_calculator):
        """Test 60 score returns satisfactory."""
        result = score_calculator.get_performance_category(60.0)
        assert result == "satisfactory"

    def test_satisfactory_score_65(self, score_calculator):
        """Test 65 score returns satisfactory."""
        result = score_calculator.get_performance_category(65.0)
        assert result == "satisfactory"

    def test_needs_improvement_score_59(self, score_calculator):
        """Test 59 score returns needs_improvement."""
        result = score_calculator.get_performance_category(59.0)
        assert result == "needs_improvement"

    def test_needs_improvement_score_50(self, score_calculator):
        """Test 50 score returns needs_improvement."""
        result = score_calculator.get_performance_category(50.0)
        assert result == "needs_improvement"

    def test_needs_improvement_score_55(self, score_calculator):
        """Test 55 score returns needs_improvement."""
        result = score_calculator.get_performance_category(55.0)
        assert result == "needs_improvement"

    def test_poor_score_49(self, score_calculator):
        """Test 49 score returns poor."""
        result = score_calculator.get_performance_category(49.0)
        assert result == "poor"

    def test_poor_score_0(self, score_calculator):
        """Test 0 score returns poor."""
        result = score_calculator.get_performance_category(0.0)
        assert result == "poor"

    def test_poor_score_25(self, score_calculator):
        """Test 25 score returns poor."""
        result = score_calculator.get_performance_category(25.0)
        assert result == "poor"

    def test_boundary_excellent_good(self, score_calculator):
        """Test boundary between excellent and good."""
        assert score_calculator.get_performance_category(90.0) == "excellent"
        assert score_calculator.get_performance_category(89.99) == "good"

    def test_boundary_good_satisfactory(self, score_calculator):
        """Test boundary between good and satisfactory."""
        assert score_calculator.get_performance_category(75.0) == "good"
        assert score_calculator.get_performance_category(74.99) == "satisfactory"

    def test_boundary_satisfactory_needs_improvement(self, score_calculator):
        """Test boundary between satisfactory and needs_improvement."""
        assert score_calculator.get_performance_category(60.0) == "satisfactory"
        assert score_calculator.get_performance_category(59.99) == "needs_improvement"

    def test_boundary_needs_improvement_poor(self, score_calculator):
        """Test boundary between needs_improvement and poor."""
        assert score_calculator.get_performance_category(50.0) == "needs_improvement"
        assert score_calculator.get_performance_category(49.99) == "poor"


# =============================================================================
# Tests for calculate_aggregate_statistics()
# =============================================================================


class TestCalculateAggregateStatistics:
    """Tests for calculate_aggregate_statistics() - multiple sessions."""

    def test_aggregate_multiple_sessions(self, score_calculator):
        """Test aggregate statistics across multiple sessions."""
        session_ids = [uuid4(), uuid4(), uuid4()]

        with patch.object(
            score_calculator,
            "calculate_session_statistics"
        ) as mock_stats:
            mock_stats.side_effect = [
                {"average_score": 80.0, "completion_time_seconds": 1800},
                {"average_score": 70.0, "completion_time_seconds": 1500},
                {"average_score": 90.0, "completion_time_seconds": 2000},
            ]

            result = score_calculator.calculate_aggregate_statistics(session_ids)

            assert result["total_sessions"] == 3
            assert result["sessions_with_scores"] == 3
            assert result["average_score"] == 80.0  # (80 + 70 + 90) / 3
            assert result["min_score"] == 70.0
            assert result["max_score"] == 90.0
            assert result["median_score"] == 80.0

    def test_aggregate_empty_sessions(self, score_calculator):
        """Test aggregate with no sessions."""
        result = score_calculator.calculate_aggregate_statistics([])

        assert result["total_sessions"] == 0
        assert result["average_score"] == 0.0
        assert result["median_score"] == 0.0

    def test_aggregate_sessions_without_scores(self, score_calculator):
        """Test aggregate when sessions have no scores."""
        session_ids = [uuid4(), uuid4()]

        with patch.object(
            score_calculator,
            "calculate_session_statistics"
        ) as mock_stats:
            mock_stats.side_effect = [
                {"average_score": 0.0, "completion_time_seconds": None},
                {"average_score": 0.0, "completion_time_seconds": None},
            ]

            result = score_calculator.calculate_aggregate_statistics(session_ids)

            assert result["total_sessions"] == 2
            assert result["average_score"] == 0.0

    def test_aggregate_score_distribution(self, score_calculator):
        """Test score distribution calculation."""
        session_ids = [uuid4() for _ in range(5)]

        with patch.object(
            score_calculator,
            "calculate_session_statistics"
        ) as mock_stats:
            mock_stats.side_effect = [
                {"average_score": 95.0, "completion_time_seconds": 1000},  # excellent
                {"average_score": 80.0, "completion_time_seconds": 1000},  # good
                {"average_score": 65.0, "completion_time_seconds": 1000},  # satisfactory
                {"average_score": 55.0, "completion_time_seconds": 1000},  # needs_improvement
                {"average_score": 40.0, "completion_time_seconds": 1000},  # poor
            ]

            result = score_calculator.calculate_aggregate_statistics(session_ids)

            assert result["score_distribution"]["excellent"] == 1
            assert result["score_distribution"]["good"] == 1
            assert result["score_distribution"]["satisfactory"] == 1
            assert result["score_distribution"]["needs_improvement"] == 1
            assert result["score_distribution"]["poor"] == 1


# =============================================================================
# Tests for _calculate_score_distribution()
# =============================================================================


class TestCalculateScoreDistribution:
    """Tests for _calculate_score_distribution() helper."""

    def test_distribution_all_categories(self, score_calculator):
        """Test distribution with scores in all categories."""
        scores = [95.0, 85.0, 70.0, 55.0, 30.0]
        result = score_calculator._calculate_score_distribution(scores)

        assert result["excellent"] == 1
        assert result["good"] == 1
        assert result["satisfactory"] == 1
        assert result["needs_improvement"] == 1
        assert result["poor"] == 1

    def test_distribution_empty_list(self, score_calculator):
        """Test distribution with empty list."""
        result = score_calculator._calculate_score_distribution([])

        assert result["excellent"] == 0
        assert result["good"] == 0
        assert result["satisfactory"] == 0
        assert result["needs_improvement"] == 0
        assert result["poor"] == 0

    def test_distribution_all_excellent(self, score_calculator):
        """Test distribution with all excellent scores."""
        scores = [100.0, 95.0, 92.0, 90.0]
        result = score_calculator._calculate_score_distribution(scores)

        assert result["excellent"] == 4
        assert result["good"] == 0
        assert result["satisfactory"] == 0
        assert result["needs_improvement"] == 0
        assert result["poor"] == 0

    def test_distribution_all_poor(self, score_calculator):
        """Test distribution with all poor scores."""
        scores = [10.0, 20.0, 30.0, 40.0]
        result = score_calculator._calculate_score_distribution(scores)

        assert result["excellent"] == 0
        assert result["good"] == 0
        assert result["satisfactory"] == 0
        assert result["needs_improvement"] == 0
        assert result["poor"] == 4


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Edge case tests for ScoreCalculator."""

    def test_floating_point_precision(self, score_calculator):
        """Test handling of floating point precision issues."""
        result = score_calculator._score_numeric(
            response_value=0.1 + 0.2,  # 0.30000000000000004 in Python
            correct_answer=0.3,
            scoring_rules={"tolerance": 0.0001}
        )
        assert result == 100.0

    def test_very_large_score_values(self, score_calculator):
        """Test handling of very large score values."""
        result = score_calculator._score_numeric(
            response_value=1e10,
            correct_answer=1e10,
            scoring_rules=None
        )
        assert result == 100.0

    def test_very_small_score_values(self, score_calculator):
        """Test handling of very small score values."""
        result = score_calculator._score_numeric(
            response_value=1e-10,
            correct_answer=1e-10,
            scoring_rules=None
        )
        assert result == 100.0

    def test_unicode_response_values(self, score_calculator):
        """Test handling of unicode response values."""
        result = score_calculator.calculate_question_score(
            response_value="resposta",
            correct_answer="resposta",
            question_type="single_choice"
        )
        assert result == 100.0

    def test_special_characters_in_response(self, score_calculator):
        """Test handling of special characters."""
        result = score_calculator.calculate_question_score(
            response_value="<script>alert('xss')</script>",
            correct_answer="<script>alert('xss')</script>",
            question_type="single_choice"
        )
        assert result == 100.0

    def test_whitespace_handling(self, score_calculator):
        """Test whitespace is preserved in comparison."""
        result = score_calculator.calculate_question_score(
            response_value="  A  ",
            correct_answer="A",
            question_type="single_choice"
        )
        assert result == 0.0  # Whitespace matters

    def test_case_sensitivity(self, score_calculator):
        """Test case sensitivity in comparisons."""
        result = score_calculator.calculate_question_score(
            response_value="a",
            correct_answer="A",
            question_type="single_choice"
        )
        assert result == 0.0  # Case matters

    def test_mixed_type_comparison(self, score_calculator):
        """Test comparison of mixed types."""
        result = score_calculator.calculate_question_score(
            response_value="1",
            correct_answer=1,
            question_type="single_choice"
        )
        assert result == 0.0  # Type matters for single_choice

    @pytest.mark.asyncio
    async def test_concurrent_score_calculation(
        self, score_calculator, mock_db, sample_session_id
    ):
        """Test score calculation is thread-safe."""
        import asyncio

        responses = [create_mock_response(sample_session_id, score=75.0)]
        mock_db.query.return_value.filter.return_value.all.return_value = responses

        # Run multiple calculations concurrently
        tasks = [
            score_calculator.calculate_score(sample_session_id)
            for _ in range(10)
        ]
        results = await asyncio.gather(*tasks)

        # All results should be identical
        assert all(r == 75.0 for r in results)
