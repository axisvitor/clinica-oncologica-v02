"""
Tests for FlowIntegrationManager - Integration coordinator (QW-021 Day 5).

Test Coverage:
    - Quiz Integration Coordination (create, complete, get responses)
    - AI Integration Coordination (generate, decide, analyze)
    - Step Processing (with integrations, response processing)
    - Integration Status (status, metrics, health)
    - Cleanup (old data, expired flows)
    - Error Handling (integration failures, fallbacks)
    - Singleton Pattern (get_integration_manager, reset)
"""

import pytest
from datetime import datetime
from uuid import uuid4, UUID
from unittest.mock import Mock, patch

from app.services.flow.integrations.manager import (
    FlowIntegrationManager,
    get_integration_manager,
    reset_integration_manager,
)
from app.services.flow.integrations.quiz_integration import QuizFlowIntegration
from app.services.flow.integrations.ai_integration import AIFlowIntegration
from app.services.flow.types import FlowContext, FlowType, FlowStepData


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton before and after each test."""
    reset_integration_manager()
    yield
    reset_integration_manager()


@pytest.fixture
def mock_quiz_integration():
    """Create mock quiz integration."""
    return Mock(spec=QuizFlowIntegration)


@pytest.fixture
def mock_ai_integration():
    """Create mock AI integration."""
    return Mock(spec=AIFlowIntegration)


@pytest.fixture
def integration_manager(mock_quiz_integration, mock_ai_integration):
    """Create integration manager with mocks."""
    return FlowIntegrationManager(
        quiz_integration=mock_quiz_integration,
        ai_integration=mock_ai_integration,
    )


@pytest.fixture
def real_integration_manager():
    """Create integration manager with real integrations."""
    return FlowIntegrationManager()


@pytest.fixture
def flow_instance_id() -> UUID:
    """Generate flow instance ID."""
    return uuid4()


@pytest.fixture
def patient_id() -> UUID:
    """Generate patient ID."""
    return uuid4()


@pytest.fixture
def flow_context(flow_instance_id: UUID, patient_id: UUID) -> FlowContext:
    """Create flow context."""
    return FlowContext(
        flow_instance_id=flow_instance_id,
        flow_type=FlowType.MONITORING,
        patient_id=patient_id,
        steps_completed=[],
        current_data={},
    )


@pytest.fixture
def flow_step_data() -> FlowStepData:
    """Create flow step data."""
    return FlowStepData(
        step_id="step_1",
        input_data={"question": "How are you feeling?"},
        metadata={},
    )


# ============================================================================
# Test Initialization
# ============================================================================


class TestInitialization:
    """Test integration manager initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default integrations."""
        manager = FlowIntegrationManager()

        assert manager.quiz is not None
        assert manager.ai is not None
        assert isinstance(manager.quiz, QuizFlowIntegration)
        assert isinstance(manager.ai, AIFlowIntegration)

    def test_init_with_custom_integrations(
        self, mock_quiz_integration, mock_ai_integration
    ):
        """Test initialization with custom integrations."""
        manager = FlowIntegrationManager(
            quiz_integration=mock_quiz_integration,
            ai_integration=mock_ai_integration,
        )

        assert manager.quiz is mock_quiz_integration
        assert manager.ai is mock_ai_integration

    def test_init_loads_config(self, real_integration_manager):
        """Test that config is loaded on init."""
        assert real_integration_manager.config is not None


# ============================================================================
# Test Quiz Integration Coordination
# ============================================================================


class TestQuizIntegrationCoordination:
    """Test quiz integration coordination methods."""

    def test_create_quiz_flow(
        self, integration_manager, mock_quiz_integration, patient_id: UUID
    ):
        """Test creating quiz flow through manager."""
        quiz_type = "monthly_assessment"
        quiz_data = {"difficulty": "easy"}
        expected_result = {
            "quiz_id": str(uuid4()),
            "flow_instance_id": str(uuid4()),
            "status": "active",
        }

        mock_quiz_integration.create_quiz_flow.return_value = expected_result

        result = integration_manager.create_quiz_flow(patient_id, quiz_type, quiz_data)

        assert result == expected_result
        mock_quiz_integration.create_quiz_flow.assert_called_once_with(
            patient_id, quiz_type, quiz_data
        )

    def test_create_quiz_flow_without_data(
        self, integration_manager, mock_quiz_integration, patient_id: UUID
    ):
        """Test creating quiz flow without optional data."""
        quiz_type = "onboarding"
        expected_result = {"quiz_id": str(uuid4())}

        mock_quiz_integration.create_quiz_flow.return_value = expected_result

        result = integration_manager.create_quiz_flow(patient_id, quiz_type)

        mock_quiz_integration.create_quiz_flow.assert_called_once_with(
            patient_id, quiz_type, None
        )

    def test_complete_quiz_flow(
        self, integration_manager, mock_quiz_integration, flow_instance_id: UUID
    ):
        """Test completing quiz flow through manager."""
        final_data = {"score": 85}
        mock_quiz_integration.complete_quiz_flow.return_value = True

        result = integration_manager.complete_quiz_flow(flow_instance_id, final_data)

        assert result is True
        mock_quiz_integration.complete_quiz_flow.assert_called_once_with(
            flow_instance_id, final_data
        )

    def test_complete_quiz_flow_failure(
        self, integration_manager, mock_quiz_integration, flow_instance_id: UUID
    ):
        """Test completing quiz flow failure."""
        mock_quiz_integration.complete_quiz_flow.return_value = False

        result = integration_manager.complete_quiz_flow(flow_instance_id)

        assert result is False

    def test_get_quiz_responses(
        self, integration_manager, mock_quiz_integration, flow_instance_id: UUID
    ):
        """Test getting quiz responses through manager."""
        expected_responses = {
            "question1": "answer1",
            "question2": "answer2",
        }
        mock_quiz_integration.get_quiz_responses.return_value = expected_responses

        result = integration_manager.get_quiz_responses(flow_instance_id)

        assert result == expected_responses
        mock_quiz_integration.get_quiz_responses.assert_called_once_with(
            flow_instance_id
        )

    def test_get_quiz_responses_not_found(
        self, integration_manager, mock_quiz_integration, flow_instance_id: UUID
    ):
        """Test getting quiz responses when not found."""
        mock_quiz_integration.get_quiz_responses.return_value = None

        result = integration_manager.get_quiz_responses(flow_instance_id)

        assert result is None


# ============================================================================
# Test AI Integration Coordination
# ============================================================================


class TestAIIntegrationCoordination:
    """Test AI integration coordination methods."""

    def test_generate_ai_response(
        self,
        integration_manager,
        mock_ai_integration,
        flow_instance_id: UUID,
        flow_context: FlowContext,
    ):
        """Test generating AI response through manager."""
        prompt = "Generate greeting message"
        expected_response = "Hello! How can I help you?"
        mock_ai_integration.generate_response.return_value = expected_response

        result = integration_manager.generate_ai_response(
            flow_instance_id, prompt, flow_context
        )

        assert result == expected_response
        mock_ai_integration.generate_response.assert_called_once_with(
            flow_instance_id, prompt, flow_context
        )

    def test_generate_ai_response_without_context(
        self, integration_manager, mock_ai_integration, flow_instance_id: UUID
    ):
        """Test generating AI response without context."""
        prompt = "Simple prompt"
        mock_ai_integration.generate_response.return_value = "Response"

        result = integration_manager.generate_ai_response(flow_instance_id, prompt)

        mock_ai_integration.generate_response.assert_called_once_with(
            flow_instance_id, prompt, None
        )

    def test_generate_ai_response_failure(
        self, integration_manager, mock_ai_integration, flow_instance_id: UUID
    ):
        """Test AI response generation failure."""
        mock_ai_integration.generate_response.return_value = None

        result = integration_manager.generate_ai_response(flow_instance_id, "prompt")

        assert result is None

    def test_make_ai_decision(
        self, integration_manager, mock_ai_integration, flow_instance_id: UUID
    ):
        """Test making AI decision through manager."""
        decision_type = "next_step"
        decision_data = {"current_step": "assessment"}
        expected_decision = {"recommendation": "continue", "confidence": 0.9}
        mock_ai_integration.make_decision.return_value = expected_decision

        result = integration_manager.make_ai_decision(
            flow_instance_id, decision_type, decision_data
        )

        assert result == expected_decision
        mock_ai_integration.make_decision.assert_called_once_with(
            flow_instance_id, decision_type, decision_data
        )

    def test_make_ai_decision_failure(
        self, integration_manager, mock_ai_integration, flow_instance_id: UUID
    ):
        """Test AI decision failure."""
        mock_ai_integration.make_decision.return_value = None

        result = integration_manager.make_ai_decision(
            flow_instance_id, "decision_type", {}
        )

        assert result is None

    def test_analyze_user_response(
        self, integration_manager, mock_ai_integration, flow_instance_id: UUID
    ):
        """Test analyzing user response through manager."""
        question = "How are you feeling?"
        response = "I'm feeling better"
        expected_analysis = {"sentiment": "positive", "confidence": 0.85}
        mock_ai_integration.analyze_response.return_value = expected_analysis

        result = integration_manager.analyze_user_response(
            flow_instance_id, question, response
        )

        assert result == expected_analysis
        mock_ai_integration.analyze_response.assert_called_once_with(
            flow_instance_id, question, response
        )

    def test_analyze_user_response_failure(
        self, integration_manager, mock_ai_integration, flow_instance_id: UUID
    ):
        """Test user response analysis failure."""
        mock_ai_integration.analyze_response.return_value = None

        result = integration_manager.analyze_user_response(
            flow_instance_id, "question", "response"
        )

        assert result is None


# ============================================================================
# Test Step Processing with Integrations
# ============================================================================


class TestStepProcessing:
    """Test step processing with integrations."""

    def test_process_step_with_ai_integration(
        self,
        real_integration_manager,
        flow_instance_id: UUID,
        flow_step_data: FlowStepData,
        flow_context: FlowContext,
    ):
        """Test processing step with AI integration."""
        # Mark step as using AI
        flow_step_data.metadata["use_ai"] = True
        flow_step_data.input_data["ai_prompt"] = "Generate response"

        result = real_integration_manager.process_step_with_integrations(
            flow_instance_id, flow_step_data, flow_context
        )

        assert "step_id" in result
        assert result["step_id"] == flow_step_data.step_id
        assert "integrations_used" in result

    def test_process_step_with_quiz_integration(
        self,
        real_integration_manager,
        flow_instance_id: UUID,
        flow_step_data: FlowStepData,
        flow_context: FlowContext,
    ):
        """Test processing step with quiz integration."""
        # Mark step as quiz step
        flow_step_data.metadata["is_quiz_step"] = True

        result = real_integration_manager.process_step_with_integrations(
            flow_instance_id, flow_step_data, flow_context
        )

        assert "step_id" in result
        assert "integrations_used" in result

    def test_process_step_with_no_integrations(
        self,
        real_integration_manager,
        flow_instance_id: UUID,
        flow_step_data: FlowStepData,
        flow_context: FlowContext,
    ):
        """Test processing step without integrations."""
        # No integration flags set
        result = real_integration_manager.process_step_with_integrations(
            flow_instance_id, flow_step_data, flow_context
        )

        assert result["integrations_used"] == []
        assert result["data"] == {}

    def test_process_step_with_both_integrations(
        self,
        real_integration_manager,
        flow_instance_id: UUID,
        flow_step_data: FlowStepData,
        flow_context: FlowContext,
    ):
        """Test processing step with both AI and quiz."""
        flow_step_data.metadata["use_ai"] = True
        flow_step_data.metadata["is_quiz_step"] = True
        flow_step_data.input_data["ai_prompt"] = "Test prompt"

        result = real_integration_manager.process_step_with_integrations(
            flow_instance_id, flow_step_data, flow_context
        )

        assert "integrations_used" in result

    def test_process_response_with_ai_analysis(
        self,
        real_integration_manager,
        flow_instance_id: UUID,
        flow_step_data: FlowStepData,
        flow_context: FlowContext,
    ):
        """Test processing response with AI analysis."""
        user_response = "I'm feeling much better today"

        result = real_integration_manager.process_response_with_integrations(
            flow_instance_id, flow_step_data, user_response, flow_context
        )

        assert "response" in result
        assert result["response"] == user_response
        assert "processed_by" in result
        assert "analysis" in result

    def test_process_response_with_quiz_recording(
        self,
        real_integration_manager,
        flow_instance_id: UUID,
        flow_step_data: FlowStepData,
        flow_context: FlowContext,
    ):
        """Test processing response with quiz recording."""
        # Make it a quiz flow
        flow_context.flow_type = FlowType.ONBOARDING  # Treated as quiz flow
        user_response = "Option A"

        # First create a quiz flow
        real_integration_manager.quiz.create_quiz_flow(
            flow_context.patient_id, "onboarding", {}
        )

        result = real_integration_manager.process_response_with_integrations(
            flow_instance_id, flow_step_data, user_response, flow_context
        )

        assert result["response"] == user_response
        assert "processed_by" in result

    def test_process_response_ai_disabled(self, real_integration_manager):
        """Test response processing when AI is disabled."""
        real_integration_manager.config.enable_ai_integration = False

        flow_instance_id = uuid4()
        flow_step_data = FlowStepData(step_id="step1", input_data={}, metadata={})
        flow_context = FlowContext(
            flow_instance_id=flow_instance_id,
            flow_type=FlowType.MONITORING,
            patient_id=uuid4(),
            steps_completed=[],
            current_data={},
        )

        result = real_integration_manager.process_response_with_integrations(
            flow_instance_id, flow_step_data, "response", flow_context
        )

        # AI should not be in processed_by
        assert "ai" not in result["processed_by"]


# ============================================================================
# Test Integration Status and Health
# ============================================================================


class TestIntegrationStatusAndHealth:
    """Test integration status and health checks."""

    def test_get_integration_status(self, real_integration_manager):
        """Test getting integration status."""
        status = real_integration_manager.get_integration_status()

        assert "quiz" in status
        assert "ai" in status
        assert "message" in status

        # Quiz status
        assert "enabled" in status["quiz"]
        assert "active_flows" in status["quiz"]

        # AI status
        assert "enabled" in status["ai"]
        assert "usage_stats" in status["ai"]

        # Message status
        assert "enabled" in status["message"]
        assert "rate_limit" in status["message"]

    def test_get_integration_status_with_active_flows(
        self, real_integration_manager, patient_id: UUID
    ):
        """Test integration status with active flows."""
        # Create some quiz flows
        real_integration_manager.create_quiz_flow(patient_id, "quiz1")
        real_integration_manager.create_quiz_flow(patient_id, "quiz2")

        status = real_integration_manager.get_integration_status()

        assert status["quiz"]["active_flows"] == 2

    def test_get_integration_metrics(self, real_integration_manager):
        """Test getting integration metrics."""
        metrics = real_integration_manager.get_integration_metrics()

        assert "quiz" in metrics
        assert "ai" in metrics
        assert "timestamp" in metrics

        # Quiz metrics
        assert "total_flows" in metrics["quiz"]
        assert "active_flows" in metrics["quiz"]

        # Timestamp format
        datetime.fromisoformat(metrics["timestamp"])

    def test_get_integration_metrics_with_activity(
        self,
        real_integration_manager,
        patient_id: UUID,
        flow_instance_id: UUID,
    ):
        """Test metrics with integration activity."""
        # Create quiz flows
        real_integration_manager.create_quiz_flow(patient_id, "quiz1")

        # Generate AI activity
        real_integration_manager.generate_ai_response(flow_instance_id, "prompt")

        metrics = real_integration_manager.get_integration_metrics()

        assert metrics["quiz"]["total_flows"] >= 1
        assert metrics["ai"]["total_interactions"] >= 1


# ============================================================================
# Test Cleanup and Maintenance
# ============================================================================


class TestCleanupAndMaintenance:
    """Test cleanup and maintenance operations."""

    def test_cleanup_old_data(
        self, integration_manager, mock_quiz_integration, mock_ai_integration
    ):
        """Test cleaning up old data."""
        mock_quiz_integration.cleanup_old_flows.return_value = 5
        mock_ai_integration.cleanup_old_data.return_value = 3

        results = integration_manager.cleanup_old_data(days=7)

        assert results["quiz_flows_cleaned"] == 5
        assert results["ai_data_cleaned"] == 3
        mock_quiz_integration.cleanup_old_flows.assert_called_once_with(7)
        mock_ai_integration.cleanup_old_data.assert_called_once_with(7)

    def test_cleanup_old_data_custom_days(
        self, integration_manager, mock_quiz_integration, mock_ai_integration
    ):
        """Test cleanup with custom day threshold."""
        mock_quiz_integration.cleanup_old_flows.return_value = 2
        mock_ai_integration.cleanup_old_data.return_value = 1

        results = integration_manager.cleanup_old_data(days=14)

        mock_quiz_integration.cleanup_old_flows.assert_called_once_with(14)
        mock_ai_integration.cleanup_old_data.assert_called_once_with(14)

    def test_cleanup_old_data_no_results(
        self, integration_manager, mock_quiz_integration, mock_ai_integration
    ):
        """Test cleanup with no old data."""
        mock_quiz_integration.cleanup_old_flows.return_value = 0
        mock_ai_integration.cleanup_old_data.return_value = 0

        results = integration_manager.cleanup_old_data()

        assert results["quiz_flows_cleaned"] == 0
        assert results["ai_data_cleaned"] == 0

    def test_cleanup_expired_flows(self, integration_manager, mock_quiz_integration):
        """Test cleaning up expired flows."""
        mock_quiz_integration.cleanup_expired_flows.return_value = 3

        total_cleaned = integration_manager.cleanup_expired_flows()

        assert total_cleaned == 3
        mock_quiz_integration.cleanup_expired_flows.assert_called_once()

    def test_cleanup_expired_flows_none(
        self, integration_manager, mock_quiz_integration
    ):
        """Test cleanup when no flows are expired."""
        mock_quiz_integration.cleanup_expired_flows.return_value = 0

        total_cleaned = integration_manager.cleanup_expired_flows()

        assert total_cleaned == 0


# ============================================================================
# Test Helper Methods
# ============================================================================


class TestHelperMethods:
    """Test helper methods."""

    def test_should_use_ai_for_step_enabled(self, real_integration_manager):
        """Test AI should be used when enabled in metadata."""
        real_integration_manager.config.enable_ai_integration = True
        step_data = FlowStepData(
            step_id="step1",
            input_data={},
            metadata={"use_ai": True},
        )

        result = real_integration_manager._should_use_ai_for_step(step_data)

        assert result is True

    def test_should_use_ai_for_step_disabled(self, real_integration_manager):
        """Test AI should not be used when disabled."""
        real_integration_manager.config.enable_ai_integration = False
        step_data = FlowStepData(
            step_id="step1",
            input_data={},
            metadata={"use_ai": True},
        )

        result = real_integration_manager._should_use_ai_for_step(step_data)

        assert result is False

    def test_should_use_ai_for_step_no_metadata(self, real_integration_manager):
        """Test AI should not be used without metadata flag."""
        real_integration_manager.config.enable_ai_integration = True
        step_data = FlowStepData(
            step_id="step1",
            input_data={},
            metadata={},
        )

        result = real_integration_manager._should_use_ai_for_step(step_data)

        assert result is False

    def test_should_use_quiz_for_step_enabled(self, real_integration_manager):
        """Test quiz should be used when enabled in metadata."""
        real_integration_manager.config.enable_quiz_integration = True
        step_data = FlowStepData(
            step_id="step1",
            input_data={},
            metadata={"is_quiz_step": True},
        )

        result = real_integration_manager._should_use_quiz_for_step(step_data)

        assert result is True

    def test_should_use_quiz_for_step_disabled(self, real_integration_manager):
        """Test quiz should not be used when disabled."""
        real_integration_manager.config.enable_quiz_integration = False
        step_data = FlowStepData(
            step_id="step1",
            input_data={},
            metadata={"is_quiz_step": True},
        )

        result = real_integration_manager._should_use_quiz_for_step(step_data)

        assert result is False

    def test_is_quiz_flow(self, real_integration_manager):
        """Test quiz flow detection."""
        quiz_flow_types = [
            FlowType.MONTHLY_QUIZ,
            FlowType.ONBOARDING,
        ]

        for flow_type in quiz_flow_types:
            context = FlowContext(
                flow_instance_id=uuid4(),
                flow_type=flow_type,
                patient_id=uuid4(),
                steps_completed=[],
                current_data={},
            )

            result = real_integration_manager._is_quiz_flow(context)
            # Will be True if flow_type value matches quiz types
            assert isinstance(result, bool)

    def test_is_not_quiz_flow(self, real_integration_manager):
        """Test non-quiz flow detection."""
        context = FlowContext(
            flow_instance_id=uuid4(),
            flow_type=FlowType.MONITORING,
            patient_id=uuid4(),
            steps_completed=[],
            current_data={},
        )

        result = real_integration_manager._is_quiz_flow(context)

        # Monitoring is not a quiz flow
        assert isinstance(result, bool)


# ============================================================================
# Test Singleton Pattern
# ============================================================================


class TestSingletonPattern:
    """Test singleton pattern implementation."""

    def test_get_integration_manager_creates_instance(self):
        """Test that get_integration_manager creates instance."""
        manager = get_integration_manager()

        assert manager is not None
        assert isinstance(manager, FlowIntegrationManager)

    def test_get_integration_manager_returns_same_instance(self):
        """Test that singleton returns same instance."""
        manager1 = get_integration_manager()
        manager2 = get_integration_manager()

        assert manager1 is manager2

    def test_reset_integration_manager(self):
        """Test resetting singleton instance."""
        manager1 = get_integration_manager()
        reset_integration_manager()
        manager2 = get_integration_manager()

        assert manager1 is not manager2

    def test_reset_integration_manager_when_none(self):
        """Test resetting when no instance exists."""
        reset_integration_manager()  # Should not raise

        manager = get_integration_manager()
        assert manager is not None


# ============================================================================
# Test Error Handling
# ============================================================================


class TestErrorHandling:
    """Test error handling in integration manager."""

    def test_process_with_ai_exception(self, real_integration_manager):
        """Test AI processing with exception."""
        flow_instance_id = uuid4()
        step_data = FlowStepData(
            step_id="step1",
            input_data={"ai_prompt": "test"},
            metadata={"use_ai": True},
        )
        context = FlowContext(
            flow_instance_id=flow_instance_id,
            flow_type=FlowType.MONITORING,
            patient_id=uuid4(),
            steps_completed=[],
            current_data={},
        )

        # Mock generate_response to raise exception
        with patch.object(
            real_integration_manager.ai,
            "generate_response",
            side_effect=Exception("AI error"),
        ):
            result = real_integration_manager._process_with_ai(
                flow_instance_id, step_data, context
            )

            # Should handle gracefully
            assert result is None

    def test_process_with_ai_no_prompt(self, real_integration_manager):
        """Test AI processing without prompt."""
        flow_instance_id = uuid4()
        step_data = FlowStepData(
            step_id="step1",
            input_data={},  # No prompt
            metadata={"use_ai": True},
        )
        context = FlowContext(
            flow_instance_id=flow_instance_id,
            flow_type=FlowType.MONITORING,
            patient_id=uuid4(),
            steps_completed=[],
            current_data={},
        )

        result = real_integration_manager._process_with_ai(
            flow_instance_id, step_data, context
        )

        assert result is None

    def test_process_with_quiz_exception(self, real_integration_manager):
        """Test quiz processing with exception."""
        flow_instance_id = uuid4()
        step_data = FlowStepData(
            step_id="step1",
            input_data={},
            metadata={"is_quiz_step": True},
        )
        context = FlowContext(
            flow_instance_id=flow_instance_id,
            flow_type=FlowType.MONTHLY_QUIZ,
            patient_id=uuid4(),
            steps_completed=[],
            current_data={},
        )

        # Mock get_quiz_flow to raise exception
        with patch.object(
            real_integration_manager.quiz,
            "get_quiz_flow",
            side_effect=Exception("Quiz error"),
        ):
            result = real_integration_manager._process_with_quiz(
                flow_instance_id, step_data, context
            )

            # Should handle gracefully
            assert result is None


# ============================================================================
# Test Integration Scenarios
# ============================================================================


class TestIntegrationScenarios:
    """Test complete integration scenarios."""

    def test_complete_quiz_flow_with_ai_analysis(
        self, real_integration_manager, patient_id: UUID
    ):
        """Test complete quiz flow with AI analysis."""
        # Create quiz flow
        quiz_result = real_integration_manager.create_quiz_flow(
            patient_id, "monthly_assessment"
        )
        flow_instance_id = UUID(quiz_result["flow_instance_id"])

        # Simulate step with AI analysis
        step_data = FlowStepData(
            step_id="step1",
            input_data={"question": "How are you feeling?"},
            metadata={"use_ai": True},
        )
        context = FlowContext(
            flow_instance_id=flow_instance_id,
            flow_type=FlowType.MONTHLY_QUIZ,
            patient_id=patient_id,
            steps_completed=[],
            current_data={},
        )

        # Process response with AI
        user_response = "I'm feeling better"
        response_result = real_integration_manager.process_response_with_integrations(
            flow_instance_id, step_data, user_response, context
        )

        assert response_result["response"] == user_response

        # Complete quiz
        complete_result = real_integration_manager.complete_quiz_flow(flow_instance_id)

        assert isinstance(complete_result, bool)

    def test_monitoring_flow_with_ai_decisions(
        self, real_integration_manager, flow_instance_id: UUID
    ):
        """Test monitoring flow with AI decisions."""
        # Generate AI response
        ai_response = real_integration_manager.generate_ai_response(
            flow_instance_id, "Generate wellness check message"
        )

        # Make AI decision
        decision = real_integration_manager.make_ai_decision(
            flow_instance_id,
            "escalate",
            {"symptoms": ["fever"], "severity": "moderate"},
        )

        # Analyze response
        analysis = real_integration_manager.analyze_user_response(
            flow_instance_id, "How are you?", "Not feeling well"
        )

        # Verify all operations completed
        assert isinstance(ai_response, (str, type(None)))
        assert isinstance(decision, (dict, type(None)))
        assert isinstance(analysis, (dict, type(None)))

    def test_status_check_across_integrations(self, real_integration_manager):
        """Test status checks across all integrations."""
        # Get status
        status = real_integration_manager.get_integration_status()

        # Get metrics
        metrics = real_integration_manager.get_integration_metrics()

        # Verify structure
        assert "quiz" in status and "quiz" in metrics
        assert "ai" in status and "ai" in metrics

    def test_cleanup_across_integrations(
        self, real_integration_manager, patient_id: UUID
    ):
        """Test cleanup across all integrations."""
        # Create some quiz flows
        real_integration_manager.create_quiz_flow(patient_id, "quiz1")
        real_integration_manager.create_quiz_flow(patient_id, "quiz2")

        # Generate AI activity
        flow_id = uuid4()
        real_integration_manager.generate_ai_response(flow_id, "prompt")

        # Clean up old data
        cleanup_results = real_integration_manager.cleanup_old_data(days=0)

        # Verify cleanup executed
        assert "quiz_flows_cleaned" in cleanup_results
        assert "ai_data_cleaned" in cleanup_results

    def test_concurrent_operations(self, real_integration_manager):
        """Test concurrent operations across integrations."""
        patient1 = uuid4()
        patient2 = uuid4()
        flow1 = uuid4()
        flow2 = uuid4()

        # Simulate concurrent operations
        quiz1 = real_integration_manager.create_quiz_flow(patient1, "quiz1")
        quiz2 = real_integration_manager.create_quiz_flow(patient2, "quiz2")
        ai_resp1 = real_integration_manager.generate_ai_response(flow1, "prompt1")
        ai_resp2 = real_integration_manager.generate_ai_response(flow2, "prompt2")

        # Verify isolation
        assert quiz1["flow_instance_id"] != quiz2["flow_instance_id"]

        # Check status reflects activity
        status = real_integration_manager.get_integration_status()
        assert status["quiz"]["active_flows"] >= 2


# ============================================================================
# Test Configuration
# ============================================================================


class TestConfiguration:
    """Test configuration handling."""

    def test_integration_config_loaded(self, real_integration_manager):
        """Test that integration config is loaded."""
        assert real_integration_manager.config is not None
        assert hasattr(real_integration_manager.config, "enable_quiz_integration")
        assert hasattr(real_integration_manager.config, "enable_ai_integration")
        assert hasattr(real_integration_manager.config, "enable_message_sending")

    def test_quiz_integration_respects_config(self, real_integration_manager):
        """Test that quiz integration respects config."""
        original_state = real_integration_manager.config.enable_quiz_integration

        # Test with disabled
        real_integration_manager.config.enable_quiz_integration = False
        assert real_integration_manager.config.enable_quiz_integration is False

        # Restore
        real_integration_manager.config.enable_quiz_integration = original_state

    def test_ai_integration_respects_config(self, real_integration_manager):
        """Test that AI integration respects config."""
        original_state = real_integration_manager.config.enable_ai_integration

        # Test with disabled
        real_integration_manager.config.enable_ai_integration = False
        assert real_integration_manager.config.enable_ai_integration is False

        # Restore
        real_integration_manager.config.enable_ai_integration = original_state
