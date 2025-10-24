"""
Tests for AIFlowIntegration - AI service integration (QW-021 Day 5).

Test Coverage:
    - Response Generation (generate_response, personalized messages)
    - Decision Making (make_decision, evaluate_condition)
    - Analysis (analyze_response, extract_symptoms)
    - Recommendations (next_step, interventions)
    - Interaction Tracking (AI interactions, decisions)
    - Statistics (usage stats)
    - Cleanup (old data cleanup)
    - Error Handling (AI failures, disabled integration)
    - Configuration (enable/disable AI)
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any, List
from uuid import uuid4, UUID
from unittest.mock import Mock, patch

from app.services.flow.integrations.ai_integration import AIFlowIntegration
from app.services.flow.types import FlowContext, FlowType
from app.services.flow.config import get_flow_config


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def ai_integration():
    """Create AI integration instance."""
    return AIFlowIntegration()


@pytest.fixture
def flow_instance_id() -> UUID:
    """Generate flow instance ID."""
    return uuid4()


@pytest.fixture
def patient_data() -> Dict[str, Any]:
    """Sample patient data."""
    return {
        "id": str(uuid4()),
        "name": "João Silva",
        "age": 45,
        "condition": "breast_cancer",
        "treatment_stage": "chemotherapy",
    }


@pytest.fixture
def flow_context(flow_instance_id: UUID) -> FlowContext:
    """Create flow context."""
    return FlowContext(
        flow_instance_id=flow_instance_id,
        flow_type=FlowType.MONITORING,
        patient_id=uuid4(),
        steps_completed=[],
        current_data={},
    )


# ============================================================================
# Test Response Generation
# ============================================================================


class TestResponseGeneration:
    """Test AI response generation."""

    def test_generate_response_success(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test successful response generation."""
        prompt = "How are you feeling today?"

        response = ai_integration.generate_response(flow_instance_id, prompt)

        assert response is not None
        assert isinstance(response, str)
        assert len(response) > 0

        # Verify interaction was tracked
        interactions = ai_integration.get_ai_interactions(flow_instance_id)
        assert len(interactions) == 1
        assert interactions[0]["type"] == "generate_response"

    def test_generate_response_with_context(
        self,
        ai_integration: AIFlowIntegration,
        flow_instance_id: UUID,
        flow_context: FlowContext,
    ):
        """Test response generation with context."""
        prompt = "Generate a personalized message"

        response = ai_integration.generate_response(
            flow_instance_id, prompt, flow_context
        )

        assert response is not None
        assert isinstance(response, str)

    def test_generate_response_ai_disabled(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test response generation when AI is disabled."""
        ai_integration.config.enable_ai_integration = False

        response = ai_integration.generate_response(flow_instance_id, "test prompt")

        assert response is None

    def test_generate_personalized_message_greeting(
        self,
        ai_integration: AIFlowIntegration,
        flow_instance_id: UUID,
        patient_data: Dict[str, Any],
    ):
        """Test personalized greeting generation."""
        message = ai_integration.generate_personalized_message(
            flow_instance_id, patient_data, "greeting"
        )

        assert message is not None
        assert isinstance(message, str)

    def test_generate_personalized_message_reminder(
        self,
        ai_integration: AIFlowIntegration,
        flow_instance_id: UUID,
        patient_data: Dict[str, Any],
    ):
        """Test personalized reminder generation."""
        message = ai_integration.generate_personalized_message(
            flow_instance_id, patient_data, "reminder"
        )

        assert message is not None

    def test_generate_personalized_message_encouragement(
        self,
        ai_integration: AIFlowIntegration,
        flow_instance_id: UUID,
        patient_data: Dict[str, Any],
    ):
        """Test personalized encouragement generation."""
        message = ai_integration.generate_personalized_message(
            flow_instance_id, patient_data, "encouragement"
        )

        assert message is not None

    def test_generate_personalized_message_follow_up(
        self,
        ai_integration: AIFlowIntegration,
        flow_instance_id: UUID,
        patient_data: Dict[str, Any],
    ):
        """Test personalized follow-up generation."""
        message = ai_integration.generate_personalized_message(
            flow_instance_id, patient_data, "follow_up"
        )

        assert message is not None

    def test_generate_personalized_message_unknown_type(
        self,
        ai_integration: AIFlowIntegration,
        flow_instance_id: UUID,
        patient_data: Dict[str, Any],
    ):
        """Test personalized message with unknown type."""
        message = ai_integration.generate_personalized_message(
            flow_instance_id, patient_data, "unknown_type"
        )

        assert message is not None

    def test_generate_personalized_message_ai_disabled(
        self,
        ai_integration: AIFlowIntegration,
        flow_instance_id: UUID,
        patient_data: Dict[str, Any],
    ):
        """Test personalized message when AI disabled."""
        ai_integration.config.enable_ai_integration = False

        message = ai_integration.generate_personalized_message(
            flow_instance_id, patient_data, "greeting"
        )

        assert message is None


# ============================================================================
# Test Decision Making
# ============================================================================


class TestDecisionMaking:
    """Test AI decision-making capabilities."""

    def test_make_decision_success(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test successful AI decision."""
        decision_type = "next_step"
        decision_data = {"current_step": "assessment", "patient_score": 8}

        decision = ai_integration.make_decision(
            flow_instance_id, decision_type, decision_data
        )

        assert decision is not None
        assert isinstance(decision, dict)
        assert "decision_type" in decision
        assert "recommendation" in decision
        assert "confidence" in decision
        assert decision["decision_type"] == decision_type

        # Verify decision was tracked
        decisions = ai_integration.get_ai_decisions(flow_instance_id)
        assert len(decisions) == 1
        assert decisions[0]["type"] == decision_type

    def test_make_decision_intervention(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test intervention decision."""
        decision_type = "intervention_needed"
        decision_data = {"symptoms": ["nausea", "fatigue"], "severity": "moderate"}

        decision = ai_integration.make_decision(
            flow_instance_id, decision_type, decision_data
        )

        assert decision is not None
        assert decision["decision_type"] == decision_type

    def test_make_decision_escalation(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test escalation decision."""
        decision_type = "escalate_to_doctor"
        decision_data = {"urgency": "high", "symptoms": ["severe_pain"]}

        decision = ai_integration.make_decision(
            flow_instance_id, decision_type, decision_data
        )

        assert decision is not None

    def test_make_decision_ai_disabled(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test decision when AI is disabled."""
        ai_integration.config.enable_ai_integration = False

        decision = ai_integration.make_decision(flow_instance_id, "test_decision", {})

        assert decision is None

    def test_evaluate_condition_success(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test successful condition evaluation."""
        condition = "patient_score > 7"
        context_data = {"patient_score": 8}

        result = ai_integration.evaluate_condition(
            flow_instance_id, condition, context_data
        )

        assert result is not None
        assert isinstance(result, bool)

        # Verify interaction was tracked
        interactions = ai_integration.get_ai_interactions(flow_instance_id)
        assert len(interactions) == 1
        assert interactions[0]["type"] == "evaluate_condition"

    def test_evaluate_condition_complex(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test complex condition evaluation."""
        condition = "symptoms_severe AND treatment_day > 5"
        context_data = {"symptoms_severe": True, "treatment_day": 7}

        result = ai_integration.evaluate_condition(
            flow_instance_id, condition, context_data
        )

        assert result is not None

    def test_evaluate_condition_ai_disabled(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test condition evaluation when AI disabled."""
        ai_integration.config.enable_ai_integration = False

        result = ai_integration.evaluate_condition(
            flow_instance_id, "test_condition", {}
        )

        assert result is None


# ============================================================================
# Test Analysis
# ============================================================================


class TestAnalysis:
    """Test AI analysis capabilities."""

    def test_analyze_response_success(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test successful response analysis."""
        question = "How are you feeling today?"
        response = "I'm feeling much better, thank you!"

        analysis = ai_integration.analyze_response(flow_instance_id, question, response)

        assert analysis is not None
        assert isinstance(analysis, dict)
        assert "sentiment" in analysis
        assert "confidence" in analysis
        assert "key_points" in analysis
        assert "concerns" in analysis
        assert "follow_up_needed" in analysis

        # Verify interaction was tracked
        interactions = ai_integration.get_ai_interactions(flow_instance_id)
        assert len(interactions) == 1
        assert interactions[0]["type"] == "analyze_response"

    def test_analyze_response_negative_sentiment(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test analysis of negative response."""
        question = "Are you experiencing any side effects?"
        response = "Yes, I have severe nausea and headaches"

        analysis = ai_integration.analyze_response(flow_instance_id, question, response)

        assert analysis is not None

    def test_analyze_response_ai_disabled(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test response analysis when AI disabled."""
        ai_integration.config.enable_ai_integration = False

        analysis = ai_integration.analyze_response(
            flow_instance_id, "question", "response"
        )

        assert analysis is None

    def test_extract_symptoms_success(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test successful symptom extraction."""
        text = "I have been experiencing nausea, fatigue, and headaches"

        symptoms = ai_integration.extract_symptoms(flow_instance_id, text)

        assert isinstance(symptoms, list)

        # Verify interaction was tracked
        interactions = ai_integration.get_ai_interactions(flow_instance_id)
        assert len(interactions) == 1
        assert interactions[0]["type"] == "extract_symptoms"

    def test_extract_symptoms_no_symptoms(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test symptom extraction with no symptoms."""
        text = "Everything is fine, no problems"

        symptoms = ai_integration.extract_symptoms(flow_instance_id, text)

        assert isinstance(symptoms, list)

    def test_extract_symptoms_ai_disabled(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test symptom extraction when AI disabled."""
        ai_integration.config.enable_ai_integration = False

        symptoms = ai_integration.extract_symptoms(flow_instance_id, "test text")

        assert symptoms == []


# ============================================================================
# Test Recommendations
# ============================================================================


class TestRecommendations:
    """Test AI recommendation capabilities."""

    def test_get_next_step_recommendation_success(
        self,
        ai_integration: AIFlowIntegration,
        flow_instance_id: UUID,
        flow_context: FlowContext,
    ):
        """Test successful next step recommendation."""
        recommendation = ai_integration.get_next_step_recommendation(
            flow_instance_id, flow_context
        )

        assert recommendation is not None
        assert isinstance(recommendation, str)

    def test_get_next_step_recommendation_with_history(
        self,
        ai_integration: AIFlowIntegration,
        flow_instance_id: UUID,
        flow_context: FlowContext,
    ):
        """Test recommendation with step history."""
        flow_context.steps_completed = ["step1", "step2", "step3"]

        recommendation = ai_integration.get_next_step_recommendation(
            flow_instance_id, flow_context
        )

        assert recommendation is not None

    def test_get_next_step_recommendation_ai_disabled(
        self,
        ai_integration: AIFlowIntegration,
        flow_instance_id: UUID,
        flow_context: FlowContext,
    ):
        """Test recommendation when AI disabled."""
        ai_integration.config.enable_ai_integration = False

        recommendation = ai_integration.get_next_step_recommendation(
            flow_instance_id, flow_context
        )

        assert recommendation is None

    def test_suggest_interventions_success(
        self,
        ai_integration: AIFlowIntegration,
        flow_instance_id: UUID,
        patient_data: Dict[str, Any],
    ):
        """Test successful intervention suggestions."""
        recent_responses = [
            {"question": "Pain level?", "answer": "8/10"},
            {"question": "Nausea?", "answer": "severe"},
        ]

        interventions = ai_integration.suggest_interventions(
            flow_instance_id, patient_data, recent_responses
        )

        assert isinstance(interventions, list)

    def test_suggest_interventions_no_concerns(
        self,
        ai_integration: AIFlowIntegration,
        flow_instance_id: UUID,
        patient_data: Dict[str, Any],
    ):
        """Test interventions with no concerns."""
        recent_responses = [
            {"question": "Pain level?", "answer": "0/10"},
            {"question": "Energy level?", "answer": "good"},
        ]

        interventions = ai_integration.suggest_interventions(
            flow_instance_id, patient_data, recent_responses
        )

        assert isinstance(interventions, list)

    def test_suggest_interventions_ai_disabled(
        self,
        ai_integration: AIFlowIntegration,
        flow_instance_id: UUID,
        patient_data: Dict[str, Any],
    ):
        """Test interventions when AI disabled."""
        ai_integration.config.enable_ai_integration = False

        interventions = ai_integration.suggest_interventions(
            flow_instance_id, patient_data, []
        )

        assert interventions == []


# ============================================================================
# Test Interaction Tracking
# ============================================================================


class TestInteractionTracking:
    """Test AI interaction tracking."""

    def test_track_multiple_interactions(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test tracking multiple interactions."""
        # Generate multiple interactions
        ai_integration.generate_response(flow_instance_id, "prompt1")
        ai_integration.generate_response(flow_instance_id, "prompt2")
        ai_integration.evaluate_condition(flow_instance_id, "cond1", {})

        interactions = ai_integration.get_ai_interactions(flow_instance_id)

        assert len(interactions) == 3
        assert interactions[0]["type"] == "generate_response"
        assert interactions[1]["type"] == "generate_response"
        assert interactions[2]["type"] == "evaluate_condition"

    def test_track_multiple_decisions(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test tracking multiple decisions."""
        # Make multiple decisions
        ai_integration.make_decision(flow_instance_id, "decision1", {})
        ai_integration.make_decision(flow_instance_id, "decision2", {})

        decisions = ai_integration.get_ai_decisions(flow_instance_id)

        assert len(decisions) == 2
        assert decisions[0]["type"] == "decision1"
        assert decisions[1]["type"] == "decision2"

    def test_interaction_limit(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test interaction history limit (100 max)."""
        # Generate 150 interactions
        for i in range(150):
            ai_integration.generate_response(flow_instance_id, f"prompt{i}")

        interactions = ai_integration.get_ai_interactions(flow_instance_id)

        # Should be limited to 100
        assert len(interactions) <= 100

    def test_decision_limit(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test decision history limit (50 max)."""
        # Make 75 decisions
        for i in range(75):
            ai_integration.make_decision(flow_instance_id, f"decision{i}", {})

        decisions = ai_integration.get_ai_decisions(flow_instance_id)

        # Should be limited to 50
        assert len(decisions) <= 50

    def test_interaction_truncation(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test that long inputs/outputs are truncated."""
        long_prompt = "x" * 1000

        ai_integration.generate_response(flow_instance_id, long_prompt)

        interactions = ai_integration.get_ai_interactions(flow_instance_id)
        assert len(interactions[0]["input"]) <= 500
        assert len(interactions[0]["output"]) <= 500

    def test_get_interactions_empty(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test getting interactions for flow with no history."""
        interactions = ai_integration.get_ai_interactions(flow_instance_id)

        assert interactions == []

    def test_get_decisions_empty(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test getting decisions for flow with no history."""
        decisions = ai_integration.get_ai_decisions(flow_instance_id)

        assert decisions == []

    def test_multiple_flows_isolation(self, ai_integration: AIFlowIntegration):
        """Test that flows are isolated in tracking."""
        flow1 = uuid4()
        flow2 = uuid4()

        ai_integration.generate_response(flow1, "prompt1")
        ai_integration.generate_response(flow2, "prompt2")

        interactions1 = ai_integration.get_ai_interactions(flow1)
        interactions2 = ai_integration.get_ai_interactions(flow2)

        assert len(interactions1) == 1
        assert len(interactions2) == 1
        assert interactions1 != interactions2


# ============================================================================
# Test Statistics
# ============================================================================


class TestStatistics:
    """Test AI usage statistics."""

    def test_usage_stats_empty(self, ai_integration: AIFlowIntegration):
        """Test usage stats with no activity."""
        stats = ai_integration.get_ai_usage_stats()

        assert isinstance(stats, dict)
        assert stats["total_flows_with_ai"] == 0
        assert stats["total_interactions"] == 0
        assert stats["total_decisions"] == 0
        assert "enabled" in stats

    def test_usage_stats_with_interactions(self, ai_integration: AIFlowIntegration):
        """Test usage stats with interactions."""
        flow1 = uuid4()
        flow2 = uuid4()

        # Generate interactions
        ai_integration.generate_response(flow1, "prompt1")
        ai_integration.generate_response(flow1, "prompt2")
        ai_integration.generate_response(flow2, "prompt3")

        stats = ai_integration.get_ai_usage_stats()

        assert stats["total_flows_with_ai"] == 2
        assert stats["total_interactions"] == 3
        assert stats["total_decisions"] == 0

    def test_usage_stats_with_decisions(self, ai_integration: AIFlowIntegration):
        """Test usage stats with decisions."""
        flow1 = uuid4()

        ai_integration.make_decision(flow1, "decision1", {})
        ai_integration.make_decision(flow1, "decision2", {})

        stats = ai_integration.get_ai_usage_stats()

        assert stats["total_flows_with_ai"] == 0  # No interactions
        assert stats["total_interactions"] == 0
        assert stats["total_decisions"] == 2

    def test_usage_stats_with_both(self, ai_integration: AIFlowIntegration):
        """Test usage stats with both interactions and decisions."""
        flow1 = uuid4()

        ai_integration.generate_response(flow1, "prompt")
        ai_integration.make_decision(flow1, "decision", {})

        stats = ai_integration.get_ai_usage_stats()

        assert stats["total_flows_with_ai"] == 1
        assert stats["total_interactions"] == 1
        assert stats["total_decisions"] == 1

    def test_usage_stats_enabled_status(self, ai_integration: AIFlowIntegration):
        """Test that stats reflect enabled status."""
        stats = ai_integration.get_ai_usage_stats()
        assert stats["enabled"] == ai_integration.config.enable_ai_integration


# ============================================================================
# Test Cleanup
# ============================================================================


class TestCleanup:
    """Test AI data cleanup."""

    def test_cleanup_old_interactions(self, ai_integration: AIFlowIntegration):
        """Test cleanup of old interactions."""
        flow_id = uuid4()

        # Add interaction
        ai_integration._record_ai_interaction(
            flow_id,
            "test",
            "input",
            "output",
        )

        # Manually set old timestamp
        old_timestamp = (datetime.utcnow() - timedelta(days=10)).isoformat()
        ai_integration._ai_interactions[flow_id][0]["timestamp"] = old_timestamp

        # Cleanup
        cleaned = ai_integration.cleanup_old_data(days=7)

        assert cleaned == 1
        assert flow_id not in ai_integration._ai_interactions

    def test_cleanup_old_decisions(self, ai_integration: AIFlowIntegration):
        """Test cleanup of old decisions."""
        flow_id = uuid4()

        # Add decision
        ai_integration._record_ai_decision(
            flow_id,
            "test_decision",
            {},
            {},
        )

        # Manually set old timestamp
        old_timestamp = (datetime.utcnow() - timedelta(days=10)).isoformat()
        ai_integration._ai_decisions[flow_id][0]["timestamp"] = old_timestamp

        # Cleanup
        cleaned = ai_integration.cleanup_old_data(days=7)

        assert cleaned == 1
        assert flow_id not in ai_integration._ai_decisions

    def test_cleanup_keeps_recent(self, ai_integration: AIFlowIntegration):
        """Test that recent data is kept."""
        flow_id = uuid4()

        # Add recent interaction
        ai_integration.generate_response(flow_id, "prompt")

        # Cleanup
        cleaned = ai_integration.cleanup_old_data(days=7)

        assert cleaned == 0
        assert flow_id in ai_integration._ai_interactions

    def test_cleanup_mixed_data(self, ai_integration: AIFlowIntegration):
        """Test cleanup with mixed old and recent data."""
        old_flow = uuid4()
        recent_flow = uuid4()

        # Add old interaction
        ai_integration._record_ai_interaction(
            old_flow,
            "test",
            "input",
            "output",
        )
        old_timestamp = (datetime.utcnow() - timedelta(days=10)).isoformat()
        ai_integration._ai_interactions[old_flow][0]["timestamp"] = old_timestamp

        # Add recent interaction
        ai_integration.generate_response(recent_flow, "prompt")

        # Cleanup
        cleaned = ai_integration.cleanup_old_data(days=7)

        assert cleaned == 1
        assert old_flow not in ai_integration._ai_interactions
        assert recent_flow in ai_integration._ai_interactions

    def test_cleanup_custom_days(self, ai_integration: AIFlowIntegration):
        """Test cleanup with custom day threshold."""
        flow_id = uuid4()

        # Add interaction 5 days old
        ai_integration._record_ai_interaction(
            flow_id,
            "test",
            "input",
            "output",
        )
        timestamp = (datetime.utcnow() - timedelta(days=5)).isoformat()
        ai_integration._ai_interactions[flow_id][0]["timestamp"] = timestamp

        # Cleanup with 3 day threshold - should clean
        cleaned = ai_integration.cleanup_old_data(days=3)
        assert cleaned == 1

    def test_cleanup_no_data(self, ai_integration: AIFlowIntegration):
        """Test cleanup with no data."""
        cleaned = ai_integration.cleanup_old_data(days=7)

        assert cleaned == 0


# ============================================================================
# Test Error Handling
# ============================================================================


class TestErrorHandling:
    """Test AI error handling."""

    def test_generate_response_exception(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test response generation with exception."""
        # Force exception by mocking internal method
        with patch.object(
            ai_integration,
            "_record_ai_interaction",
            side_effect=Exception("Mock error"),
        ):
            response = ai_integration.generate_response(flow_instance_id, "prompt")

            # Should handle gracefully
            assert response is None

    def test_make_decision_exception(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test decision making with exception."""
        with patch.object(
            ai_integration,
            "_record_ai_decision",
            side_effect=Exception("Mock error"),
        ):
            decision = ai_integration.make_decision(flow_instance_id, "decision", {})

            # Should handle gracefully
            assert decision is None

    def test_analyze_response_exception(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test response analysis with exception."""
        with patch.object(
            ai_integration,
            "_record_ai_interaction",
            side_effect=Exception("Mock error"),
        ):
            analysis = ai_integration.analyze_response(
                flow_instance_id, "question", "response"
            )

            # Should handle gracefully
            assert analysis is None

    def test_extract_symptoms_exception(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test symptom extraction with exception."""
        with patch.object(
            ai_integration,
            "_record_ai_interaction",
            side_effect=Exception("Mock error"),
        ):
            symptoms = ai_integration.extract_symptoms(flow_instance_id, "text")

            # Should handle gracefully
            assert symptoms == []

    def test_get_next_step_recommendation_exception(
        self,
        ai_integration: AIFlowIntegration,
        flow_instance_id: UUID,
        flow_context: FlowContext,
    ):
        """Test recommendation with exception."""
        with patch.object(
            ai_integration,
            "_build_recommendation_prompt",
            side_effect=Exception("Mock error"),
        ):
            recommendation = ai_integration.get_next_step_recommendation(
                flow_instance_id, flow_context
            )

            # Should handle gracefully
            assert recommendation is None

    def test_suggest_interventions_exception(
        self,
        ai_integration: AIFlowIntegration,
        flow_instance_id: UUID,
        patient_data: Dict[str, Any],
    ):
        """Test interventions with exception."""
        # Force an exception by passing invalid data
        with patch.object(
            ai_integration.config,
            "enable_ai_integration",
            True,
        ):
            # Should handle any exceptions gracefully
            interventions = ai_integration.suggest_interventions(
                flow_instance_id, patient_data, []
            )

            assert isinstance(interventions, list)


# ============================================================================
# Test Configuration
# ============================================================================


class TestConfiguration:
    """Test AI configuration handling."""

    def test_ai_enabled_by_default(self):
        """Test that AI is enabled by default."""
        integration = AIFlowIntegration()

        assert integration.config.enable_ai_integration in [True, False]

    def test_toggle_ai_integration(self, ai_integration: AIFlowIntegration):
        """Test toggling AI integration."""
        original_state = ai_integration.config.enable_ai_integration

        # Toggle
        ai_integration.config.enable_ai_integration = not original_state

        assert ai_integration.config.enable_ai_integration != original_state

        # Restore
        ai_integration.config.enable_ai_integration = original_state

    def test_operations_respect_config(
        self, ai_integration: AIFlowIntegration, flow_instance_id: UUID
    ):
        """Test that operations respect configuration."""
        # Disable AI
        ai_integration.config.enable_ai_integration = False

        # All operations should return None or empty
        assert ai_integration.generate_response(flow_instance_id, "prompt") is None
        assert (
            ai_integration.generate_personalized_message(
                flow_instance_id, {}, "greeting"
            )
            is None
        )
        assert ai_integration.make_decision(flow_instance_id, "decision", {}) is None
        assert ai_integration.evaluate_condition(flow_instance_id, "cond", {}) is None
        assert ai_integration.analyze_response(flow_instance_id, "q", "a") is None
        assert ai_integration.extract_symptoms(flow_instance_id, "text") == []


# ============================================================================
# Test Integration Scenarios
# ============================================================================


class TestIntegrationScenarios:
    """Test complete AI integration scenarios."""

    def test_complete_patient_interaction_flow(
        self,
        ai_integration: AIFlowIntegration,
        flow_instance_id: UUID,
        patient_data: Dict[str, Any],
    ):
        """Test complete patient interaction with AI."""
        # 1. Generate greeting
        greeting = ai_integration.generate_personalized_message(
            flow_instance_id, patient_data, "greeting"
        )
        assert greeting is not None

        # 2. Analyze patient response
        patient_response = "I'm feeling better but still have some nausea"
        analysis = ai_integration.analyze_response(
            flow_instance_id, "How are you feeling?", patient_response
        )
        assert analysis is not None

        # 3. Extract symptoms
        symptoms = ai_integration.extract_symptoms(flow_instance_id, patient_response)
        assert isinstance(symptoms, list)

        # 4. Make decision based on analysis
        decision = ai_integration.make_decision(
            flow_instance_id,
            "next_step",
            {"symptoms": symptoms, "sentiment": analysis.get("sentiment")},
        )
        assert decision is not None

        # 5. Suggest interventions if needed
        interventions = ai_integration.suggest_interventions(
            flow_instance_id,
            patient_data,
            [{"question": "How are you?", "answer": patient_response}],
        )
        assert isinstance(interventions, list)

        # Verify all interactions were tracked
        interactions = ai_integration.get_ai_interactions(flow_instance_id)
        decisions = ai_integration.get_ai_decisions(flow_instance_id)
        assert len(interactions) >= 3  # greeting, analysis, symptoms
        assert len(decisions) >= 1  # next_step decision

    def test_symptom_monitoring_flow(
        self,
        ai_integration: AIFlowIntegration,
        flow_instance_id: UUID,
        patient_data: Dict[str, Any],
    ):
        """Test symptom monitoring flow with AI."""
        # Patient reports symptoms
        symptom_text = "I have severe headaches and nausea"

        # Extract symptoms
        symptoms = ai_integration.extract_symptoms(flow_instance_id, symptom_text)

        # Analyze severity
        analysis = ai_integration.analyze_response(
            flow_instance_id, "What symptoms are you experiencing?", symptom_text
        )
        assert analysis is not None

        # Make escalation decision
        decision = ai_integration.make_decision(
            flow_instance_id,
            "escalate_to_doctor",
            {"symptoms": symptoms, "severity": "high"},
        )
        assert decision is not None

        # Get intervention suggestions
        interventions = ai_integration.suggest_interventions(
            flow_instance_id, patient_data, [{"symptoms": symptom_text}]
        )
        assert isinstance(interventions, list)

    def test_multi_step_decision_flow(
        self,
        ai_integration: AIFlowIntegration,
        flow_instance_id: UUID,
        flow_context: FlowContext,
    ):
        """Test multi-step decision making."""
        # Step 1: Evaluate condition
        condition_result = ai_integration.evaluate_condition(
            flow_instance_id, "patient_engaged", {"last_response_time": "2024-01-20"}
        )
        assert condition_result is not None

        # Step 2: Make decision based on condition
        decision = ai_integration.make_decision(
            flow_instance_id,
            "engagement_level",
            {"condition_result": condition_result},
        )
        assert decision is not None

        # Step 3: Get recommendation for next step
        recommendation = ai_integration.get_next_step_recommendation(
            flow_instance_id, flow_context
        )
        assert recommendation is not None

        # Verify complete tracking
        interactions = ai_integration.get_ai_interactions(flow_instance_id)
        decisions = ai_integration.get_ai_decisions(flow_instance_id)
        assert len(interactions) >= 1
        assert len(decisions) >= 2

    def test_personalized_message_generation_flow(
        self,
        ai_integration: AIFlowIntegration,
        flow_instance_id: UUID,
        patient_data: Dict[str, Any],
    ):
        """Test complete personalized messaging flow."""
        message_types = ["greeting", "reminder", "encouragement", "follow_up"]

        for msg_type in message_types:
            message = ai_integration.generate_personalized_message(
                flow_instance_id, patient_data, msg_type
            )
            assert message is not None

        # Verify all messages were tracked
        interactions = ai_integration.get_ai_interactions(flow_instance_id)
        assert len(interactions) == len(message_types)

    def test_concurrent_flows(self, ai_integration: AIFlowIntegration):
        """Test AI handling multiple concurrent flows."""
        flow1 = uuid4()
        flow2 = uuid4()
        flow3 = uuid4()

        # Generate activity on multiple flows
        ai_integration.generate_response(flow1, "prompt1")
        ai_integration.make_decision(flow2, "decision1", {})
        ai_integration.generate_response(flow3, "prompt3")
        ai_integration.make_decision(flow1, "decision1", {})

        # Verify isolation
        interactions1 = ai_integration.get_ai_interactions(flow1)
        interactions2 = ai_integration.get_ai_interactions(flow2)
        interactions3 = ai_integration.get_ai_interactions(flow3)

        decisions1 = ai_integration.get_ai_decisions(flow1)
        decisions2 = ai_integration.get_ai_decisions(flow2)

        assert len(interactions1) == 1
        assert len(interactions2) == 0
        assert len(interactions3) == 1
        assert len(decisions1) == 1
        assert len(decisions2) == 1

        # Verify stats
        stats = ai_integration.get_ai_usage_stats()
        assert stats["total_flows_with_ai"] == 2  # flow1 and flow3
        assert stats["total_interactions"] == 2
        assert stats["total_decisions"] == 2
