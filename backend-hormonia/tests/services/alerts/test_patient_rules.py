"""
Unit Tests for Patient Rules Evaluators.

Tests the patient-specific alert rule evaluators including:
- No Response detection
- Missed Quiz detection
- Negative Sentiment detection
- Treatment Adherence monitoring
- Emergency Keywords detection

Author: Backend Team
Date: 2025-01-20
"""

import pytest
from uuid import uuid4
from datetime import datetime, timedelta

from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive
from app.services.alerts import (
    AlertRule,
    AlertRuleType,
    AlertSeverity,
    evaluate_no_response,
    evaluate_missed_quiz,
    evaluate_negative_sentiment,
    evaluate_treatment_adherence,
    evaluate_emergency_keywords,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_patient_id():
    """Sample patient UUID."""
    return uuid4()


@pytest.fixture
def base_rule():
    """Base alert rule for testing."""
    return AlertRule(
        id=uuid4(),
        rule_type=AlertRuleType.NO_RESPONSE,
        name="Test Rule",
        description="Test rule description",
        severity=AlertSeverity.HIGH,
        enabled=True,
        conditions={},
        created_at=now_sao_paulo_naive(),
        updated_at=now_sao_paulo_naive(),
    )


# ============================================================================
# Test No Response Evaluator
# ============================================================================


class TestNoResponseEvaluator:
    """Test evaluate_no_response function."""

    @pytest.mark.asyncio
    async def test_no_response_triggered(self, base_rule, sample_patient_id):
        """Test alert triggered when patient hasn't responded."""
        # Setup rule
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.NO_RESPONSE
        rule.conditions = {"threshold_hours": 48}

        # Setup context - no response for 72 hours
        context = {
            "patient_id": sample_patient_id,
            "last_inbound_message_at": now_sao_paulo_naive() - timedelta(hours=72),
            "outbound_messages_since_response": 3,
            "patient_created_at": now_sao_paulo_naive() - timedelta(days=30),
        }

        # Execute
        evaluation = await evaluate_no_response(rule, context)

        # Assert
        assert evaluation.triggered is True
        assert evaluation.rule == rule
        assert "hasn't responded" in evaluation.reason.lower()
        assert evaluation.metadata["hours_since_response"] >= 72
        assert evaluation.metadata["outbound_messages_sent"] == 3

    @pytest.mark.asyncio
    async def test_no_response_not_triggered_recent_response(
        self, base_rule, sample_patient_id
    ):
        """Test alert not triggered when patient responded recently."""
        # Setup rule
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.NO_RESPONSE
        rule.conditions = {"threshold_hours": 48}

        # Setup context - responded 1 hour ago
        context = {
            "patient_id": sample_patient_id,
            "last_inbound_message_at": now_sao_paulo_naive() - timedelta(hours=1),
            "outbound_messages_since_response": 0,
            "patient_created_at": now_sao_paulo_naive() - timedelta(days=30),
        }

        # Execute
        evaluation = await evaluate_no_response(rule, context)

        # Assert
        assert evaluation.triggered is False
        assert "responded recently" in evaluation.reason.lower()

    @pytest.mark.asyncio
    async def test_no_response_not_triggered_no_outbound_messages(
        self, base_rule, sample_patient_id
    ):
        """Test alert not triggered when no outbound messages sent."""
        # Setup rule
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.NO_RESPONSE
        rule.conditions = {"threshold_hours": 48}

        # Setup context - no outbound messages
        context = {
            "patient_id": sample_patient_id,
            "last_inbound_message_at": now_sao_paulo_naive() - timedelta(hours=72),
            "outbound_messages_since_response": 0,  # No messages sent
            "patient_created_at": now_sao_paulo_naive() - timedelta(days=30),
        }

        # Execute
        evaluation = await evaluate_no_response(rule, context)

        # Assert
        assert evaluation.triggered is False

    @pytest.mark.asyncio
    async def test_no_response_uses_patient_creation_when_no_inbound(
        self, base_rule, sample_patient_id
    ):
        """Test uses patient creation date when no inbound messages."""
        # Setup rule
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.NO_RESPONSE
        rule.conditions = {"threshold_hours": 48}

        # Setup context - patient created 72 hours ago, no inbound messages
        creation_time = now_sao_paulo_naive() - timedelta(hours=72)
        context = {
            "patient_id": sample_patient_id,
            "last_inbound_message_at": None,
            "outbound_messages_since_response": 2,
            "patient_created_at": creation_time,
        }

        # Execute
        evaluation = await evaluate_no_response(rule, context)

        # Assert
        assert evaluation.triggered is True
        assert evaluation.metadata["hours_since_response"] >= 72

    @pytest.mark.asyncio
    async def test_no_response_custom_threshold(self, base_rule, sample_patient_id):
        """Test with custom threshold hours."""
        # Setup rule with 24 hour threshold
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.NO_RESPONSE
        rule.conditions = {"threshold_hours": 24}

        # Setup context - no response for 30 hours
        context = {
            "patient_id": sample_patient_id,
            "last_inbound_message_at": now_sao_paulo_naive() - timedelta(hours=30),
            "outbound_messages_since_response": 1,
            "patient_created_at": now_sao_paulo_naive() - timedelta(days=30),
        }

        # Execute
        evaluation = await evaluate_no_response(rule, context)

        # Assert
        assert evaluation.triggered is True


# ============================================================================
# Test Missed Quiz Evaluator
# ============================================================================


class TestMissedQuizEvaluator:
    """Test evaluate_missed_quiz function."""

    @pytest.mark.asyncio
    async def test_missed_quiz_triggered(self, base_rule, sample_patient_id):
        """Test alert triggered when patient missed quizzes."""
        # Setup rule
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.MISSED_QUIZ
        rule.conditions = {"max_missed": 1}

        # Setup context - expected 2, completed 0
        context = {
            "patient_id": sample_patient_id,
            "quiz_responses_count": 0,
            "expected_quiz_count": 2,
            "time_window_hours": 720,  # 30 days
        }

        # Execute
        evaluation = await evaluate_missed_quiz(rule, context)

        # Assert
        assert evaluation.triggered is True
        assert "missed" in evaluation.reason.lower()
        assert evaluation.metadata["missed_count"] == 2
        assert evaluation.metadata["expected_count"] == 2
        assert evaluation.metadata["completion_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_missed_quiz_not_triggered_all_completed(
        self, base_rule, sample_patient_id
    ):
        """Test alert not triggered when all quizzes completed."""
        # Setup rule
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.MISSED_QUIZ
        rule.conditions = {"max_missed": 1}

        # Setup context - expected 2, completed 2
        context = {
            "patient_id": sample_patient_id,
            "quiz_responses_count": 2,
            "expected_quiz_count": 2,
            "time_window_hours": 720,
        }

        # Execute
        evaluation = await evaluate_missed_quiz(rule, context)

        # Assert
        assert evaluation.triggered is False

    @pytest.mark.asyncio
    async def test_missed_quiz_partial_completion(self, base_rule, sample_patient_id):
        """Test with partial quiz completion."""
        # Setup rule - allow 1 miss
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.MISSED_QUIZ
        rule.conditions = {"max_missed": 1}

        # Setup context - expected 3, completed 2 (1 missed)
        context = {
            "patient_id": sample_patient_id,
            "quiz_responses_count": 2,
            "expected_quiz_count": 3,
            "time_window_hours": 720,
        }

        # Execute
        evaluation = await evaluate_missed_quiz(rule, context)

        # Assert - should not trigger (only 1 missed, within threshold)
        assert evaluation.triggered is False

    @pytest.mark.asyncio
    async def test_missed_quiz_exceeds_threshold(self, base_rule, sample_patient_id):
        """Test when missed count exceeds threshold."""
        # Setup rule - allow 1 miss
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.MISSED_QUIZ
        rule.conditions = {"max_missed": 1}

        # Setup context - expected 3, completed 0 (3 missed)
        context = {
            "patient_id": sample_patient_id,
            "quiz_responses_count": 0,
            "expected_quiz_count": 3,
            "time_window_hours": 720,
        }

        # Execute
        evaluation = await evaluate_missed_quiz(rule, context)

        # Assert - should trigger (3 missed > 1 threshold)
        assert evaluation.triggered is True
        assert evaluation.metadata["missed_count"] == 3


# ============================================================================
# Test Negative Sentiment Evaluator
# ============================================================================


class TestNegativeSentimentEvaluator:
    """Test evaluate_negative_sentiment function."""

    @pytest.mark.asyncio
    async def test_negative_sentiment_triggered(self, base_rule, sample_patient_id):
        """Test alert triggered for negative sentiment."""
        # Setup rule
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.NEGATIVE_SENTIMENT
        rule.conditions = {
            "threshold": -0.5,
            "min_messages": 3,
        }

        # Setup context - consistently negative sentiment
        context = {
            "patient_id": sample_patient_id,
            "sentiment_scores": [-0.8, -0.7, -0.9, -0.6],
            "recent_messages": [
                "estou muito triste",
                "não aguento mais",
                "tudo está ruim",
                "me sinto péssimo",
            ],
        }

        # Execute
        evaluation = await evaluate_negative_sentiment(rule, context)

        # Assert
        assert evaluation.triggered is True
        assert "negative sentiment" in evaluation.reason.lower()
        assert evaluation.metadata["average_sentiment"] < -0.5
        assert evaluation.metadata["message_count"] == 4

    @pytest.mark.asyncio
    async def test_negative_sentiment_not_triggered_positive(
        self, base_rule, sample_patient_id
    ):
        """Test alert not triggered for positive sentiment."""
        # Setup rule
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.NEGATIVE_SENTIMENT
        rule.conditions = {
            "threshold": -0.5,
            "min_messages": 3,
        }

        # Setup context - positive sentiment
        context = {
            "patient_id": sample_patient_id,
            "sentiment_scores": [0.8, 0.7, 0.6],
            "recent_messages": [
                "estou me sentindo bem",
                "obrigado pela ajuda",
                "está melhorando",
            ],
        }

        # Execute
        evaluation = await evaluate_negative_sentiment(rule, context)

        # Assert
        assert evaluation.triggered is False

    @pytest.mark.asyncio
    async def test_negative_sentiment_insufficient_messages(
        self, base_rule, sample_patient_id
    ):
        """Test not triggered with insufficient message count."""
        # Setup rule - requires 3 messages
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.NEGATIVE_SENTIMENT
        rule.conditions = {
            "threshold": -0.5,
            "min_messages": 3,
        }

        # Setup context - only 2 messages (insufficient)
        context = {
            "patient_id": sample_patient_id,
            "sentiment_scores": [-0.8, -0.7],
            "recent_messages": ["estou triste", "não está bom"],
        }

        # Execute
        evaluation = await evaluate_negative_sentiment(rule, context)

        # Assert - should not trigger (insufficient data)
        assert evaluation.triggered is False

    @pytest.mark.asyncio
    async def test_negative_sentiment_mixed_scores(self, base_rule, sample_patient_id):
        """Test with mixed positive and negative sentiment."""
        # Setup rule
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.NEGATIVE_SENTIMENT
        rule.conditions = {
            "threshold": -0.5,
            "min_messages": 3,
        }

        # Setup context - mixed sentiment, average neutral
        context = {
            "patient_id": sample_patient_id,
            "sentiment_scores": [-0.8, 0.5, -0.3, 0.6],
            "recent_messages": ["triste", "feliz", "ok", "ótimo"],
        }

        # Execute
        evaluation = await evaluate_negative_sentiment(rule, context)

        # Assert - average should be above threshold
        assert evaluation.triggered is False


# ============================================================================
# Test Treatment Adherence Evaluator
# ============================================================================


class TestTreatmentAdherenceEvaluator:
    """Test evaluate_treatment_adherence function."""

    @pytest.mark.asyncio
    async def test_treatment_adherence_triggered_low(
        self, base_rule, sample_patient_id
    ):
        """Test alert triggered for low adherence."""
        # Setup rule
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.TREATMENT_ADHERENCE
        rule.conditions = {
            "min_adherence_rate": 0.8,  # 80% minimum
        }

        # Setup context - 45% adherence (low)
        context = {
            "patient_id": sample_patient_id,
            "treatment_adherence_rate": 0.45,
            "doses_taken": 9,
            "doses_expected": 20,
            "last_dose_at": now_sao_paulo_naive() - timedelta(days=3),
        }

        # Execute
        evaluation = await evaluate_treatment_adherence(rule, context)

        # Assert
        assert evaluation.triggered is True
        assert "adherence" in evaluation.reason.lower()
        assert evaluation.metadata["adherence_rate"] == 0.45
        assert evaluation.metadata["doses_taken"] == 9
        assert evaluation.metadata["doses_expected"] == 20

    @pytest.mark.asyncio
    async def test_treatment_adherence_not_triggered_good(
        self, base_rule, sample_patient_id
    ):
        """Test alert not triggered for good adherence."""
        # Setup rule
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.TREATMENT_ADHERENCE
        rule.conditions = {
            "min_adherence_rate": 0.8,
        }

        # Setup context - 95% adherence (good)
        context = {
            "patient_id": sample_patient_id,
            "treatment_adherence_rate": 0.95,
            "doses_taken": 19,
            "doses_expected": 20,
            "last_dose_at": now_sao_paulo_naive() - timedelta(hours=12),
        }

        # Execute
        evaluation = await evaluate_treatment_adherence(rule, context)

        # Assert
        assert evaluation.triggered is False

    @pytest.mark.asyncio
    async def test_treatment_adherence_exact_threshold(
        self, base_rule, sample_patient_id
    ):
        """Test with adherence exactly at threshold."""
        # Setup rule
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.TREATMENT_ADHERENCE
        rule.conditions = {
            "min_adherence_rate": 0.8,
        }

        # Setup context - exactly 80% adherence
        context = {
            "patient_id": sample_patient_id,
            "treatment_adherence_rate": 0.8,
            "doses_taken": 16,
            "doses_expected": 20,
            "last_dose_at": now_sao_paulo_naive() - timedelta(hours=6),
        }

        # Execute
        evaluation = await evaluate_treatment_adherence(rule, context)

        # Assert - exactly at threshold should not trigger
        assert evaluation.triggered is False

    @pytest.mark.asyncio
    async def test_treatment_adherence_zero_rate(self, base_rule, sample_patient_id):
        """Test with zero adherence rate."""
        # Setup rule
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.TREATMENT_ADHERENCE
        rule.conditions = {
            "min_adherence_rate": 0.8,
        }

        # Setup context - 0% adherence
        context = {
            "patient_id": sample_patient_id,
            "treatment_adherence_rate": 0.0,
            "doses_taken": 0,
            "doses_expected": 20,
            "last_dose_at": None,
        }

        # Execute
        evaluation = await evaluate_treatment_adherence(rule, context)

        # Assert
        assert evaluation.triggered is True
        assert evaluation.metadata["adherence_rate"] == 0.0


# ============================================================================
# Test Emergency Keywords Evaluator
# ============================================================================


class TestEmergencyKeywordsEvaluator:
    """Test evaluate_emergency_keywords function."""

    @pytest.mark.asyncio
    async def test_emergency_keywords_triggered_pain(
        self, base_rule, sample_patient_id
    ):
        """Test alert triggered for pain keywords."""
        # Setup rule
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.EMERGENCY_KEYWORDS
        rule.conditions = {
            "keywords": ["dor", "sangue", "emergência", "socorro"],
            "case_sensitive": False,
        }

        # Setup context - message with pain keyword
        context = {
            "patient_id": sample_patient_id,
            "last_message_text": "estou com muita dor no peito",
            "last_message_at": now_sao_paulo_naive(),
        }

        # Execute
        evaluation = await evaluate_emergency_keywords(rule, context)

        # Assert
        assert evaluation.triggered is True
        assert (
            "emergency" in evaluation.reason.lower()
            or "keyword" in evaluation.reason.lower()
        )
        assert "dor" in evaluation.metadata["matched_keywords"]
        assert "dor no peito" in evaluation.metadata["message_snippet"].lower()

    @pytest.mark.asyncio
    async def test_emergency_keywords_triggered_blood(
        self, base_rule, sample_patient_id
    ):
        """Test alert triggered for blood keyword."""
        # Setup rule
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.EMERGENCY_KEYWORDS
        rule.conditions = {
            "keywords": ["dor", "sangue", "emergência", "socorro"],
            "case_sensitive": False,
        }

        # Setup context
        context = {
            "patient_id": sample_patient_id,
            "last_message_text": "estou vomitando sangue",
            "last_message_at": now_sao_paulo_naive(),
        }

        # Execute
        evaluation = await evaluate_emergency_keywords(rule, context)

        # Assert
        assert evaluation.triggered is True
        assert "sangue" in evaluation.metadata["matched_keywords"]

    @pytest.mark.asyncio
    async def test_emergency_keywords_not_triggered_normal(
        self, base_rule, sample_patient_id
    ):
        """Test alert not triggered for normal message."""
        # Setup rule
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.EMERGENCY_KEYWORDS
        rule.conditions = {
            "keywords": ["dor", "sangue", "emergência", "socorro"],
            "case_sensitive": False,
        }

        # Setup context - normal message
        context = {
            "patient_id": sample_patient_id,
            "last_message_text": "bom dia, como vai?",
            "last_message_at": now_sao_paulo_naive(),
        }

        # Execute
        evaluation = await evaluate_emergency_keywords(rule, context)

        # Assert
        assert evaluation.triggered is False

    @pytest.mark.asyncio
    async def test_emergency_keywords_multiple_matches(
        self, base_rule, sample_patient_id
    ):
        """Test with multiple keyword matches."""
        # Setup rule
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.EMERGENCY_KEYWORDS
        rule.conditions = {
            "keywords": ["dor", "sangue", "emergência", "socorro"],
            "case_sensitive": False,
        }

        # Setup context - multiple emergency keywords
        context = {
            "patient_id": sample_patient_id,
            "last_message_text": "socorro! muita dor e sangue, emergência!",
            "last_message_at": now_sao_paulo_naive(),
        }

        # Execute
        evaluation = await evaluate_emergency_keywords(rule, context)

        # Assert
        assert evaluation.triggered is True
        matched = evaluation.metadata["matched_keywords"]
        # Should match multiple keywords
        assert any(
            keyword in matched for keyword in ["dor", "sangue", "emergência", "socorro"]
        )

    @pytest.mark.asyncio
    async def test_emergency_keywords_case_sensitive(
        self, base_rule, sample_patient_id
    ):
        """Test case-sensitive keyword matching."""
        # Setup rule - case sensitive
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.EMERGENCY_KEYWORDS
        rule.conditions = {
            "keywords": ["DOR", "SANGUE"],
            "case_sensitive": True,
        }

        # Setup context - lowercase keywords
        context = {
            "patient_id": sample_patient_id,
            "last_message_text": "estou com dor",
            "last_message_at": now_sao_paulo_naive(),
        }

        # Execute
        evaluation = await evaluate_emergency_keywords(rule, context)

        # Assert - should not match (case mismatch)
        assert evaluation.triggered is False

    @pytest.mark.asyncio
    async def test_emergency_keywords_empty_message(self, base_rule, sample_patient_id):
        """Test with empty message."""
        # Setup rule
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.EMERGENCY_KEYWORDS
        rule.conditions = {
            "keywords": ["dor", "sangue"],
            "case_sensitive": False,
        }

        # Setup context - empty message
        context = {
            "patient_id": sample_patient_id,
            "last_message_text": "",
            "last_message_at": now_sao_paulo_naive(),
        }

        # Execute
        evaluation = await evaluate_emergency_keywords(rule, context)

        # Assert
        assert evaluation.triggered is False

    @pytest.mark.asyncio
    async def test_emergency_keywords_none_message(self, base_rule, sample_patient_id):
        """Test with None message."""
        # Setup rule
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.EMERGENCY_KEYWORDS
        rule.conditions = {
            "keywords": ["dor", "sangue"],
            "case_sensitive": False,
        }

        # Setup context - None message
        context = {
            "patient_id": sample_patient_id,
            "last_message_text": None,
            "last_message_at": now_sao_paulo_naive(),
        }

        # Execute
        evaluation = await evaluate_emergency_keywords(rule, context)

        # Assert
        assert evaluation.triggered is False


# ============================================================================
# Test Error Handling
# ============================================================================


class TestErrorHandling:
    """Test error handling and edge cases across all evaluators."""

    @pytest.mark.asyncio
    async def test_no_response_missing_context(self, base_rule):
        """Test no_response with missing context data."""
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.NO_RESPONSE
        rule.conditions = {"threshold_hours": 48}

        # Empty context
        context = {}

        # Should handle gracefully
        evaluation = await evaluate_no_response(rule, context)
        assert evaluation is not None

    @pytest.mark.asyncio
    async def test_missed_quiz_negative_counts(self, base_rule, sample_patient_id):
        """Test missed_quiz with negative counts."""
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.MISSED_QUIZ
        rule.conditions = {"max_missed": 1}

        context = {
            "patient_id": sample_patient_id,
            "quiz_responses_count": -1,
            "expected_quiz_count": -1,
        }

        # Should handle gracefully
        evaluation = await evaluate_missed_quiz(rule, context)
        assert evaluation is not None

    @pytest.mark.asyncio
    async def test_negative_sentiment_empty_scores(self, base_rule, sample_patient_id):
        """Test negative_sentiment with empty scores."""
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.NEGATIVE_SENTIMENT
        rule.conditions = {"threshold": -0.5, "min_messages": 3}

        context = {
            "patient_id": sample_patient_id,
            "sentiment_scores": [],
            "recent_messages": [],
        }

        # Should handle gracefully
        evaluation = await evaluate_negative_sentiment(rule, context)
        assert evaluation.triggered is False

    @pytest.mark.asyncio
    async def test_treatment_adherence_missing_rate(self, base_rule, sample_patient_id):
        """Test treatment_adherence with missing adherence rate."""
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.TREATMENT_ADHERENCE
        rule.conditions = {"min_adherence_rate": 0.8}

        context = {
            "patient_id": sample_patient_id,
            # Missing treatment_adherence_rate
        }

        # Should handle gracefully
        evaluation = await evaluate_treatment_adherence(rule, context)
        assert evaluation is not None

    @pytest.mark.asyncio
    async def test_emergency_keywords_missing_keywords(
        self, base_rule, sample_patient_id
    ):
        """Test emergency_keywords with missing keywords config."""
        rule = base_rule.copy()
        rule.rule_type = AlertRuleType.EMERGENCY_KEYWORDS
        rule.conditions = {}  # Missing keywords

        context = {
            "patient_id": sample_patient_id,
            "last_message_text": "socorro estou com dor",
        }

        # Should handle gracefully
        evaluation = await evaluate_emergency_keywords(rule, context)
        assert evaluation is not None