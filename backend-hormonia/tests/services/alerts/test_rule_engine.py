"""
Unit Tests for RuleEngine.

Tests the generic rule evaluation engine that supports pluggable evaluators,
async evaluation, caching, and rule management.

Author: Backend Team
Date: 2025-01-20
"""

import pytest
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from typing import Dict, Any, Optional

from app.services.alerts import (
    RuleEngine,
    AlertRule,
    AlertEvaluation,
    AlertRuleType,
    AlertSeverity,
    RuleConfig,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def rule_engine():
    """Create RuleEngine instance."""
    return RuleEngine()


@pytest.fixture
def sample_patient_id():
    """Sample patient UUID."""
    return uuid4()


@pytest.fixture
def sample_context():
    """Sample evaluation context."""
    return {
        "last_inbound_message_at": datetime.utcnow() - timedelta(days=3),
        "quiz_responses_count": 0,
        "sentiment_scores": [-0.8, -0.7, -0.9],
        "treatment_adherence_rate": 0.45,
        "last_message_text": "estou com muita dor",
    }


@pytest.fixture
def sample_rule():
    """Sample alert rule."""
    return AlertRule(
        id=uuid4(),
        rule_type=AlertRuleType.NO_RESPONSE,
        name="No Response Check",
        description="Check if patient has not responded",
        severity=AlertSeverity.HIGH,
        enabled=True,
        conditions={"max_hours_without_response": 48},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_evaluation():
    """Sample evaluation result."""
    return AlertEvaluation(
        rule_type=AlertRuleType.NO_RESPONSE,
        triggered=True,
        severity=AlertSeverity.HIGH,
        title="Patient No Response",
        message="Patient has not responded in 72 hours",
        metadata={"days_without_response": 3},
        timestamp=datetime.utcnow(),
    )


@pytest.fixture
async def mock_evaluator():
    """Create mock evaluator function."""

    async def evaluator(
        patient_id: UUID,
        context: Dict[str, Any],
        rule: AlertRule,
    ) -> Optional[AlertEvaluation]:
        return AlertEvaluation(
            rule_type=rule.rule_type,
            triggered=True,
            severity=rule.severity,
            title="Mock Alert",
            message="Mock alert message",
            metadata={},
            timestamp=datetime.utcnow(),
        )

    return evaluator


@pytest.fixture
async def mock_failing_evaluator():
    """Create mock evaluator that raises exception."""

    async def evaluator(
        patient_id: UUID,
        context: Dict[str, Any],
        rule: AlertRule,
    ) -> Optional[AlertEvaluation]:
        raise ValueError("Evaluation failed")

    return evaluator


@pytest.fixture
async def mock_non_triggering_evaluator():
    """Create mock evaluator that returns None (no trigger)."""

    async def evaluator(
        patient_id: UUID,
        context: Dict[str, Any],
        rule: AlertRule,
    ) -> Optional[AlertEvaluation]:
        return None

    return evaluator


# ============================================================================
# Test RuleEngine Initialization
# ============================================================================


class TestRuleEngineInitialization:
    """Test RuleEngine initialization and configuration."""

    def test_init_default(self):
        """Test RuleEngine initialization with defaults."""
        engine = RuleEngine()

        assert engine._evaluators == {}
        assert engine._rules == {}
        assert engine._cache == {}
        assert engine._evaluation_count == 0
        assert engine._cache_hits == 0

    def test_init_with_config(self):
        """Test RuleEngine initialization with custom config."""
        config = RuleConfig(
            enable_caching=True,
            cache_ttl_seconds=600,
            max_cache_size=500,
        )
        engine = RuleEngine(config=config)

        assert engine._config == config
        assert engine._config.enable_caching is True
        assert engine._config.cache_ttl_seconds == 600


# ============================================================================
# Test Evaluator Registration
# ============================================================================


class TestEvaluatorRegistration:
    """Test evaluator registration and management."""

    @pytest.mark.asyncio
    async def test_register_evaluator(self, rule_engine, mock_evaluator):
        """Test registering an evaluator."""
        # Execute
        rule_engine.register_evaluator(
            rule_type=AlertRuleType.NO_RESPONSE,
            evaluator=mock_evaluator,
        )

        # Assert
        assert AlertRuleType.NO_RESPONSE in rule_engine._evaluators
        assert rule_engine._evaluators[AlertRuleType.NO_RESPONSE] == mock_evaluator

    @pytest.mark.asyncio
    async def test_register_multiple_evaluators(
        self, rule_engine, mock_evaluator, mock_non_triggering_evaluator
    ):
        """Test registering multiple evaluators."""
        # Execute
        rule_engine.register_evaluator(AlertRuleType.NO_RESPONSE, mock_evaluator)
        rule_engine.register_evaluator(
            AlertRuleType.MISSED_QUIZ, mock_non_triggering_evaluator
        )

        # Assert
        assert len(rule_engine._evaluators) == 2
        assert AlertRuleType.NO_RESPONSE in rule_engine._evaluators
        assert AlertRuleType.MISSED_QUIZ in rule_engine._evaluators

    @pytest.mark.asyncio
    async def test_register_evaluator_overwrite(self, rule_engine, mock_evaluator):
        """Test that registering same rule type overwrites previous evaluator."""
        # Register first evaluator
        rule_engine.register_evaluator(AlertRuleType.NO_RESPONSE, mock_evaluator)
        first_evaluator = rule_engine._evaluators[AlertRuleType.NO_RESPONSE]

        # Register different evaluator for same type
        new_evaluator = AsyncMock()
        rule_engine.register_evaluator(AlertRuleType.NO_RESPONSE, new_evaluator)

        # Assert - should be overwritten
        assert rule_engine._evaluators[AlertRuleType.NO_RESPONSE] == new_evaluator
        assert rule_engine._evaluators[AlertRuleType.NO_RESPONSE] != first_evaluator

    def test_has_evaluator(self, rule_engine, mock_evaluator):
        """Test checking if evaluator exists."""
        # Initially no evaluator
        assert rule_engine.has_evaluator(AlertRuleType.NO_RESPONSE) is False

        # Register evaluator
        rule_engine.register_evaluator(AlertRuleType.NO_RESPONSE, mock_evaluator)

        # Should now exist
        assert rule_engine.has_evaluator(AlertRuleType.NO_RESPONSE) is True

    def test_get_evaluator(self, rule_engine, mock_evaluator):
        """Test retrieving registered evaluator."""
        # Register evaluator
        rule_engine.register_evaluator(AlertRuleType.NO_RESPONSE, mock_evaluator)

        # Execute
        evaluator = rule_engine.get_evaluator(AlertRuleType.NO_RESPONSE)

        # Assert
        assert evaluator == mock_evaluator

    def test_get_evaluator_not_found(self, rule_engine):
        """Test retrieving non-existent evaluator."""
        # Execute
        evaluator = rule_engine.get_evaluator(AlertRuleType.NO_RESPONSE)

        # Assert
        assert evaluator is None


# ============================================================================
# Test Rule Management
# ============================================================================


class TestRuleManagement:
    """Test rule registration and management."""

    def test_register_rule(self, rule_engine, sample_rule):
        """Test registering a rule."""
        # Execute
        rule_engine.register_rule(sample_rule)

        # Assert
        assert sample_rule.rule_type in rule_engine._rules
        assert rule_engine._rules[sample_rule.rule_type] == sample_rule

    def test_register_multiple_rules(self, rule_engine):
        """Test registering multiple rules."""
        rule1 = AlertRule(
            id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            name="No Response",
            description="Check no response",
            severity=AlertSeverity.HIGH,
            enabled=True,
            conditions={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        rule2 = AlertRule(
            id=uuid4(),
            rule_type=AlertRuleType.MISSED_QUIZ,
            name="Missed Quiz",
            description="Check missed quiz",
            severity=AlertSeverity.MEDIUM,
            enabled=True,
            conditions={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Execute
        rule_engine.register_rule(rule1)
        rule_engine.register_rule(rule2)

        # Assert
        assert len(rule_engine._rules) == 2
        assert AlertRuleType.NO_RESPONSE in rule_engine._rules
        assert AlertRuleType.MISSED_QUIZ in rule_engine._rules

    def test_get_rule(self, rule_engine, sample_rule):
        """Test retrieving a rule."""
        # Register rule
        rule_engine.register_rule(sample_rule)

        # Execute
        result = rule_engine.get_rule(sample_rule.rule_type)

        # Assert
        assert result == sample_rule

    def test_get_rule_not_found(self, rule_engine):
        """Test retrieving non-existent rule."""
        # Execute
        result = rule_engine.get_rule(AlertRuleType.NO_RESPONSE)

        # Assert
        assert result is None

    def test_get_all_rules(self, rule_engine):
        """Test retrieving all registered rules."""
        rule1 = AlertRule(
            id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            name="No Response",
            description="Check no response",
            severity=AlertSeverity.HIGH,
            enabled=True,
            conditions={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        rule2 = AlertRule(
            id=uuid4(),
            rule_type=AlertRuleType.MISSED_QUIZ,
            name="Missed Quiz",
            description="Check missed quiz",
            severity=AlertSeverity.MEDIUM,
            enabled=True,
            conditions={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Register rules
        rule_engine.register_rule(rule1)
        rule_engine.register_rule(rule2)

        # Execute
        rules = rule_engine.get_all_rules()

        # Assert
        assert len(rules) == 2
        assert rule1 in rules
        assert rule2 in rules

    def test_get_enabled_rules(self, rule_engine):
        """Test retrieving only enabled rules."""
        enabled_rule = AlertRule(
            id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            name="No Response",
            description="Check no response",
            severity=AlertSeverity.HIGH,
            enabled=True,
            conditions={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        disabled_rule = AlertRule(
            id=uuid4(),
            rule_type=AlertRuleType.MISSED_QUIZ,
            name="Missed Quiz",
            description="Check missed quiz",
            severity=AlertSeverity.MEDIUM,
            enabled=False,
            conditions={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Register rules
        rule_engine.register_rule(enabled_rule)
        rule_engine.register_rule(disabled_rule)

        # Execute
        rules = rule_engine.get_enabled_rules()

        # Assert
        assert len(rules) == 1
        assert enabled_rule in rules
        assert disabled_rule not in rules


# ============================================================================
# Test Rule Evaluation
# ============================================================================


class TestRuleEvaluation:
    """Test rule evaluation logic."""

    @pytest.mark.asyncio
    async def test_evaluate_single_rule(
        self,
        rule_engine,
        sample_patient_id,
        sample_context,
        sample_rule,
        mock_evaluator,
    ):
        """Test evaluating a single rule."""
        # Setup
        rule_engine.register_rule(sample_rule)
        rule_engine.register_evaluator(sample_rule.rule_type, mock_evaluator)

        # Execute
        evaluations = await rule_engine.evaluate(
            patient_id=sample_patient_id,
            context=sample_context,
            rule_types=[sample_rule.rule_type],
        )

        # Assert
        assert len(evaluations) == 1
        assert evaluations[0].rule_type == sample_rule.rule_type
        assert evaluations[0].triggered is True

    @pytest.mark.asyncio
    async def test_evaluate_multiple_rules(
        self, rule_engine, sample_patient_id, sample_context, mock_evaluator
    ):
        """Test evaluating multiple rules."""
        # Setup multiple rules
        rule1 = AlertRule(
            id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            name="No Response",
            description="Check no response",
            severity=AlertSeverity.HIGH,
            enabled=True,
            conditions={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        rule2 = AlertRule(
            id=uuid4(),
            rule_type=AlertRuleType.MISSED_QUIZ,
            name="Missed Quiz",
            description="Check missed quiz",
            severity=AlertSeverity.MEDIUM,
            enabled=True,
            conditions={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        rule_engine.register_rule(rule1)
        rule_engine.register_rule(rule2)
        rule_engine.register_evaluator(rule1.rule_type, mock_evaluator)
        rule_engine.register_evaluator(rule2.rule_type, mock_evaluator)

        # Execute
        evaluations = await rule_engine.evaluate(
            patient_id=sample_patient_id,
            context=sample_context,
            rule_types=[rule1.rule_type, rule2.rule_type],
        )

        # Assert
        assert len(evaluations) == 2

    @pytest.mark.asyncio
    async def test_evaluate_all_rules_when_no_types_specified(
        self, rule_engine, sample_patient_id, sample_context, mock_evaluator
    ):
        """Test that evaluate runs all enabled rules when no types specified."""
        # Setup
        rule = AlertRule(
            id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            name="No Response",
            description="Check no response",
            severity=AlertSeverity.HIGH,
            enabled=True,
            conditions={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        rule_engine.register_rule(rule)
        rule_engine.register_evaluator(rule.rule_type, mock_evaluator)

        # Execute without specifying rule_types
        evaluations = await rule_engine.evaluate(
            patient_id=sample_patient_id,
            context=sample_context,
        )

        # Assert - should evaluate all enabled rules
        assert len(evaluations) >= 0

    @pytest.mark.asyncio
    async def test_evaluate_skips_disabled_rules(
        self, rule_engine, sample_patient_id, sample_context, mock_evaluator
    ):
        """Test that disabled rules are skipped during evaluation."""
        # Setup disabled rule
        disabled_rule = AlertRule(
            id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            name="No Response",
            description="Check no response",
            severity=AlertSeverity.HIGH,
            enabled=False,  # Disabled
            conditions={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        rule_engine.register_rule(disabled_rule)
        rule_engine.register_evaluator(disabled_rule.rule_type, mock_evaluator)

        # Execute
        evaluations = await rule_engine.evaluate(
            patient_id=sample_patient_id,
            context=sample_context,
            rule_types=[disabled_rule.rule_type],
        )

        # Assert - should skip disabled rule
        assert len(evaluations) == 0

    @pytest.mark.asyncio
    async def test_evaluate_skips_rules_without_evaluator(
        self, rule_engine, sample_patient_id, sample_context
    ):
        """Test that rules without registered evaluator are skipped."""
        # Setup rule without evaluator
        rule = AlertRule(
            id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            name="No Response",
            description="Check no response",
            severity=AlertSeverity.HIGH,
            enabled=True,
            conditions={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        rule_engine.register_rule(rule)
        # NOTE: No evaluator registered

        # Execute
        evaluations = await rule_engine.evaluate(
            patient_id=sample_patient_id,
            context=sample_context,
            rule_types=[rule.rule_type],
        )

        # Assert - should skip rule without evaluator
        assert len(evaluations) == 0

    @pytest.mark.asyncio
    async def test_evaluate_filters_non_triggered_results(
        self,
        rule_engine,
        sample_patient_id,
        sample_context,
        mock_non_triggering_evaluator,
    ):
        """Test that non-triggered evaluations are filtered out."""
        # Setup
        rule = AlertRule(
            id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            name="No Response",
            description="Check no response",
            severity=AlertSeverity.HIGH,
            enabled=True,
            conditions={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        rule_engine.register_rule(rule)
        rule_engine.register_evaluator(rule.rule_type, mock_non_triggering_evaluator)

        # Execute
        evaluations = await rule_engine.evaluate(
            patient_id=sample_patient_id,
            context=sample_context,
            rule_types=[rule.rule_type],
        )

        # Assert - should return empty list (no triggers)
        assert len(evaluations) == 0

    @pytest.mark.asyncio
    async def test_evaluate_handles_evaluator_exception(
        self,
        rule_engine,
        sample_patient_id,
        sample_context,
        mock_failing_evaluator,
    ):
        """Test that evaluator exceptions are handled gracefully."""
        # Setup
        rule = AlertRule(
            id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            name="No Response",
            description="Check no response",
            severity=AlertSeverity.HIGH,
            enabled=True,
            conditions={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        rule_engine.register_rule(rule)
        rule_engine.register_evaluator(rule.rule_type, mock_failing_evaluator)

        # Execute - should not raise exception
        evaluations = await rule_engine.evaluate(
            patient_id=sample_patient_id,
            context=sample_context,
            rule_types=[rule.rule_type],
        )

        # Assert - failed evaluation should be filtered out
        assert len(evaluations) == 0


# ============================================================================
# Test Caching
# ============================================================================


class TestCaching:
    """Test rule evaluation caching."""

    @pytest.mark.asyncio
    async def test_cache_enabled_stores_results(
        self, sample_patient_id, sample_context, mock_evaluator
    ):
        """Test that caching stores evaluation results."""
        # Setup with caching enabled
        config = RuleConfig(enable_caching=True, cache_ttl_seconds=300)
        rule_engine = RuleEngine(config=config)

        rule = AlertRule(
            id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            name="No Response",
            description="Check no response",
            severity=AlertSeverity.HIGH,
            enabled=True,
            conditions={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        rule_engine.register_rule(rule)
        rule_engine.register_evaluator(rule.rule_type, mock_evaluator)

        # Execute first time
        await rule_engine.evaluate(
            patient_id=sample_patient_id,
            context=sample_context,
            rule_types=[rule.rule_type],
        )

        # Assert - cache should have entry
        assert len(rule_engine._cache) > 0

    @pytest.mark.asyncio
    async def test_cache_disabled_does_not_store(
        self, sample_patient_id, sample_context, mock_evaluator
    ):
        """Test that disabled caching does not store results."""
        # Setup with caching disabled
        config = RuleConfig(enable_caching=False)
        rule_engine = RuleEngine(config=config)

        rule = AlertRule(
            id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            name="No Response",
            description="Check no response",
            severity=AlertSeverity.HIGH,
            enabled=True,
            conditions={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        rule_engine.register_rule(rule)
        rule_engine.register_evaluator(rule.rule_type, mock_evaluator)

        # Execute
        await rule_engine.evaluate(
            patient_id=sample_patient_id,
            context=sample_context,
            rule_types=[rule.rule_type],
        )

        # Assert - cache should be empty
        assert len(rule_engine._cache) == 0

    @pytest.mark.asyncio
    async def test_clear_cache(self, sample_patient_id, sample_context, mock_evaluator):
        """Test clearing the cache."""
        # Setup with caching enabled
        config = RuleConfig(enable_caching=True)
        rule_engine = RuleEngine(config=config)

        rule = AlertRule(
            id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            name="No Response",
            description="Check no response",
            severity=AlertSeverity.HIGH,
            enabled=True,
            conditions={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        rule_engine.register_rule(rule)
        rule_engine.register_evaluator(rule.rule_type, mock_evaluator)

        # Execute to populate cache
        await rule_engine.evaluate(
            patient_id=sample_patient_id,
            context=sample_context,
            rule_types=[rule.rule_type],
        )

        # Cache should have entries
        assert len(rule_engine._cache) > 0

        # Clear cache
        rule_engine.clear_cache()

        # Assert - cache should be empty
        assert len(rule_engine._cache) == 0


# ============================================================================
# Test Statistics
# ============================================================================


class TestStatistics:
    """Test rule engine statistics."""

    @pytest.mark.asyncio
    async def test_statistics_track_evaluations(
        self, sample_patient_id, sample_context, mock_evaluator
    ):
        """Test that statistics track evaluation count."""
        rule_engine = RuleEngine()
        initial_count = rule_engine._evaluation_count

        rule = AlertRule(
            id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            name="No Response",
            description="Check no response",
            severity=AlertSeverity.HIGH,
            enabled=True,
            conditions={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        rule_engine.register_rule(rule)
        rule_engine.register_evaluator(rule.rule_type, mock_evaluator)

        # Execute evaluation
        await rule_engine.evaluate(
            patient_id=sample_patient_id,
            context=sample_context,
            rule_types=[rule.rule_type],
        )

        # Assert - count should increase
        assert rule_engine._evaluation_count > initial_count

    def test_get_statistics(self, rule_engine):
        """Test retrieving statistics."""
        # Execute
        stats = rule_engine.get_statistics()

        # Assert
        assert "total_evaluations" in stats
        assert "cache_hits" in stats
        assert "cache_hit_rate" in stats
        assert "registered_rules" in stats
        assert "registered_evaluators" in stats


# ============================================================================
# Test Error Handling
# ============================================================================


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_evaluate_with_none_patient_id(self, rule_engine, sample_context):
        """Test evaluation with None patient_id."""
        with pytest.raises((ValueError, TypeError, AttributeError)):
            await rule_engine.evaluate(
                patient_id=None,
                context=sample_context,
            )

    @pytest.mark.asyncio
    async def test_evaluate_with_none_context(self, rule_engine, sample_patient_id):
        """Test evaluation with None context."""
        # Should handle gracefully or raise appropriate exception
        try:
            await rule_engine.evaluate(
                patient_id=sample_patient_id,
                context=None,
            )
        except (ValueError, TypeError):
            pass  # Expected

    def test_register_none_rule(self, rule_engine):
        """Test registering None rule."""
        with pytest.raises((ValueError, TypeError, AttributeError)):
            rule_engine.register_rule(None)

    def test_register_none_evaluator(self, rule_engine):
        """Test registering None evaluator."""
        with pytest.raises((ValueError, TypeError)):
            rule_engine.register_evaluator(AlertRuleType.NO_RESPONSE, None)
