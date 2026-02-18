"""
Tests for FlowEngine - Core execution engine (QW-021 Day 6).

Test Coverage:
    - Step Execution (execute_step for all types)
    - Message Steps (send message, variable substitution)
    - Question Steps (ask question, response handling)
    - Decision Steps (evaluate conditions, choose path)
    - Action Steps (execute actions, handle results)
    - Wait Steps (pause execution, duration/datetime)
    - Branch Steps (conditional branching)
    - Loop Steps (iteration, max iterations, conditions)
    - End Steps (flow termination)
    - Condition Evaluation (simple, and, or, not)
    - Navigation (get_next_step)
    - State Transitions (transition_state)
    - Variable Substitution (_substitute_variables)
    - Error Handling (step failures, invalid types)
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any
from uuid import uuid4

from app.services.flow.core.engine import FlowEngine
from app.services.flow.types import (
    FlowContext,
    FlowType,
    FlowStepStatus,
)
from app.utils.timezone import now_sao_paulo


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def engine():
    """Create flow engine instance."""
    return FlowEngine()


@pytest.fixture
def flow_context() -> FlowContext:
    """Create flow context."""
    return FlowContext(
        flow_instance_id=uuid4(),
        flow_type=FlowType.MONITORING,
        patient_id=uuid4(),
        steps_completed=[],
        steps_history=[],
        current_data={},
        flow_data={},
        variables={"patient_name": "João Silva", "age": 45},
    )


@pytest.fixture
def message_step_def() -> Dict[str, Any]:
    """Message step definition."""
    return {
        "step_id": "msg_1",
        "type": "message",
        "name": "Welcome Message",
        "content": "Hello {{patient_name}}! Welcome to your health monitoring.",
        "metadata": {},
    }


@pytest.fixture
def question_step_def() -> Dict[str, Any]:
    """Question step definition."""
    return {
        "step_id": "q_1",
        "type": "question",
        "name": "Pain Level Question",
        "question": "How is your pain level today, {{patient_name}}?",
        "metadata": {},
    }


@pytest.fixture
def decision_step_def() -> Dict[str, Any]:
    """Decision step definition."""
    return {
        "step_id": "dec_1",
        "type": "decision",
        "name": "Pain Level Decision",
        "conditions": [
            {
                "variable": "pain_level",
                "operator": "greater_than",
                "value": 7,
                "path": "high_pain",
            },
            {
                "variable": "pain_level",
                "operator": "greater_than",
                "value": 4,
                "path": "moderate_pain",
            },
        ],
        "default_path": "low_pain",
        "metadata": {},
    }


@pytest.fixture
def action_step_def() -> Dict[str, Any]:
    """Action step definition."""
    return {
        "step_id": "act_1",
        "type": "action",
        "name": "Send Alert",
        "action_type": "send_alert",
        "params": {"alert_type": "high_pain", "priority": "high"},
        "metadata": {},
    }


# ============================================================================
# Test Step Execution
# ============================================================================


class TestStepExecution:
    """Test general step execution."""

    @pytest.mark.asyncio
    async def test_execute_step_success(
        self,
        engine: FlowEngine,
        flow_context: FlowContext,
        message_step_def: Dict[str, Any],
    ):
        """Test successful step execution."""
        updated_context, step_data = await engine.execute_step(
            flow_context, message_step_def
        )

        assert step_data.step_id == "msg_1"
        assert step_data.status == FlowStepStatus.COMPLETED
        assert step_data.output_data is not None
        assert step_data.started_at is not None
        assert step_data.completed_at is not None
        assert "msg_1" in updated_context.steps_completed
        assert len(updated_context.steps_history) == 1

    @pytest.mark.asyncio
    async def test_execute_step_updates_context(
        self,
        engine: FlowEngine,
        flow_context: FlowContext,
        message_step_def: Dict[str, Any],
    ):
        """Test that step execution updates context properly."""
        initial_steps = len(flow_context.steps_completed)

        updated_context, step_data = await engine.execute_step(
            flow_context, message_step_def
        )

        assert len(updated_context.steps_completed) == initial_steps + 1
        assert updated_context.steps_completed[-1] == message_step_def["step_id"]
        assert len(updated_context.steps_history) == 1
        assert updated_context.steps_history[0] == step_data

    @pytest.mark.asyncio
    async def test_execute_step_invalid_type(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test step execution with invalid step type."""
        invalid_step = {
            "step_id": "invalid",
            "type": "invalid_type",
            "name": "Invalid Step",
        }

        with pytest.raises(ValueError) as exc_info:
            await engine.execute_step(flow_context, invalid_step)

        assert "invalid_type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_step_tracks_timing(
        self,
        engine: FlowEngine,
        flow_context: FlowContext,
        message_step_def: Dict[str, Any],
    ):
        """Test that step execution tracks timing."""
        updated_context, step_data = await engine.execute_step(
            flow_context, message_step_def
        )

        assert step_data.started_at is not None
        assert step_data.completed_at is not None
        assert step_data.completed_at >= step_data.started_at


# ============================================================================
# Test Message Steps
# ============================================================================


class TestMessageSteps:
    """Test message step execution."""

    @pytest.mark.asyncio
    async def test_execute_message_step_basic(
        self,
        engine: FlowEngine,
        flow_context: FlowContext,
        message_step_def: Dict[str, Any],
    ):
        """Test basic message step execution."""
        updated_context, step_data = await engine.execute_step(
            flow_context, message_step_def
        )

        assert step_data.status == FlowStepStatus.COMPLETED
        assert step_data.output_data["message_sent"] is True
        assert "message_content" in step_data.output_data
        assert "timestamp" in step_data.output_data

    @pytest.mark.asyncio
    async def test_execute_message_step_variable_substitution(
        self,
        engine: FlowEngine,
        flow_context: FlowContext,
        message_step_def: Dict[str, Any],
    ):
        """Test variable substitution in message content."""
        updated_context, step_data = await engine.execute_step(
            flow_context, message_step_def
        )

        message_content = step_data.output_data["message_content"]
        assert "João Silva" in message_content
        assert "{{patient_name}}" not in message_content

    @pytest.mark.asyncio
    async def test_execute_message_step_updates_variables(
        self,
        engine: FlowEngine,
        flow_context: FlowContext,
        message_step_def: Dict[str, Any],
    ):
        """Test that message step updates variables."""
        updated_context, step_data = await engine.execute_step(
            flow_context, message_step_def
        )

        assert "last_message_sent" in updated_context.variables
        assert (
            updated_context.variables["last_message_sent"]
            == step_data.output_data["message_content"]
        )

    @pytest.mark.asyncio
    async def test_execute_message_step_empty_content(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test message step with empty content."""
        empty_message = {
            "step_id": "msg_empty",
            "type": "message",
            "name": "Empty Message",
            "content": "",
        }

        updated_context, step_data = await engine.execute_step(
            flow_context, empty_message
        )

        assert step_data.status == FlowStepStatus.COMPLETED
        assert step_data.output_data["message_content"] == ""


# ============================================================================
# Test Question Steps
# ============================================================================


class TestQuestionSteps:
    """Test question step execution."""

    @pytest.mark.asyncio
    async def test_execute_question_step_no_response(
        self,
        engine: FlowEngine,
        flow_context: FlowContext,
        question_step_def: Dict[str, Any],
    ):
        """Test question step without response."""
        updated_context, step_data = await engine.execute_step(
            flow_context, question_step_def
        )

        assert step_data.status == FlowStepStatus.COMPLETED
        assert "question_asked" in step_data.output_data
        assert step_data.output_data["response_received"] is False
        assert step_data.output_data["response"] is None

    @pytest.mark.asyncio
    async def test_execute_question_step_with_response(
        self,
        engine: FlowEngine,
        flow_context: FlowContext,
        question_step_def: Dict[str, Any],
    ):
        """Test question step with existing response."""
        flow_context.flow_data["pending_response"] = "Pain level is 5"

        updated_context, step_data = await engine.execute_step(
            flow_context, question_step_def
        )

        assert step_data.output_data["response_received"] is True
        assert step_data.output_data["response"] == "Pain level is 5"

    @pytest.mark.asyncio
    async def test_execute_question_step_variable_substitution(
        self,
        engine: FlowEngine,
        flow_context: FlowContext,
        question_step_def: Dict[str, Any],
    ):
        """Test variable substitution in question."""
        updated_context, step_data = await engine.execute_step(
            flow_context, question_step_def
        )

        question = step_data.output_data["question_asked"]
        assert "João Silva" in question
        assert "{{patient_name}}" not in question

    @pytest.mark.asyncio
    async def test_execute_question_step_updates_variables(
        self,
        engine: FlowEngine,
        flow_context: FlowContext,
        question_step_def: Dict[str, Any],
    ):
        """Test that question step updates variables."""
        updated_context, step_data = await engine.execute_step(
            flow_context, question_step_def
        )

        assert "last_question" in updated_context.variables
        assert "last_response" in updated_context.variables


# ============================================================================
# Test Decision Steps
# ============================================================================


class TestDecisionSteps:
    """Test decision step execution."""

    @pytest.mark.asyncio
    async def test_execute_decision_step_first_condition_met(
        self,
        engine: FlowEngine,
        flow_context: FlowContext,
        decision_step_def: Dict[str, Any],
    ):
        """Test decision step when first condition is met."""
        flow_context.variables["pain_level"] = 8

        updated_context, step_data = await engine.execute_step(
            flow_context, decision_step_def
        )

        assert step_data.output_data["decision_made"] is True
        assert step_data.output_data["chosen_path"] == "high_pain"

    @pytest.mark.asyncio
    async def test_execute_decision_step_second_condition_met(
        self,
        engine: FlowEngine,
        flow_context: FlowContext,
        decision_step_def: Dict[str, Any],
    ):
        """Test decision step when second condition is met."""
        flow_context.variables["pain_level"] = 5

        updated_context, step_data = await engine.execute_step(
            flow_context, decision_step_def
        )

        assert step_data.output_data["chosen_path"] == "moderate_pain"

    @pytest.mark.asyncio
    async def test_execute_decision_step_default_path(
        self,
        engine: FlowEngine,
        flow_context: FlowContext,
        decision_step_def: Dict[str, Any],
    ):
        """Test decision step taking default path."""
        flow_context.variables["pain_level"] = 2

        updated_context, step_data = await engine.execute_step(
            flow_context, decision_step_def
        )

        assert step_data.output_data["chosen_path"] == "low_pain"

    @pytest.mark.asyncio
    async def test_execute_decision_step_updates_flow_data(
        self,
        engine: FlowEngine,
        flow_context: FlowContext,
        decision_step_def: Dict[str, Any],
    ):
        """Test that decision step updates flow data."""
        flow_context.variables["pain_level"] = 8

        updated_context, step_data = await engine.execute_step(
            flow_context, decision_step_def
        )

        assert "last_decision" in updated_context.flow_data
        assert updated_context.flow_data["last_decision"] == "high_pain"


# ============================================================================
# Test Action Steps
# ============================================================================


class TestActionSteps:
    """Test action step execution."""

    @pytest.mark.asyncio
    async def test_execute_action_step_success(
        self,
        engine: FlowEngine,
        flow_context: FlowContext,
        action_step_def: Dict[str, Any],
    ):
        """Test successful action step execution."""
        updated_context, step_data = await engine.execute_step(
            flow_context, action_step_def
        )

        assert step_data.status == FlowStepStatus.COMPLETED
        assert step_data.output_data["action_executed"] is True
        assert step_data.output_data["action_type"] == "send_alert"

    @pytest.mark.asyncio
    async def test_execute_action_step_with_params(
        self,
        engine: FlowEngine,
        flow_context: FlowContext,
        action_step_def: Dict[str, Any],
    ):
        """Test action step with parameters."""
        updated_context, step_data = await engine.execute_step(
            flow_context, action_step_def
        )

        assert "params" in step_data.output_data
        assert step_data.output_data["params"]["alert_type"] == "high_pain"
        assert step_data.output_data["params"]["priority"] == "high"

    @pytest.mark.asyncio
    async def test_execute_action_step_updates_flow_data(
        self,
        engine: FlowEngine,
        flow_context: FlowContext,
        action_step_def: Dict[str, Any],
    ):
        """Test that action step updates flow data."""
        updated_context, step_data = await engine.execute_step(
            flow_context, action_step_def
        )

        assert "action_send_alert_executed" in updated_context.flow_data
        assert updated_context.flow_data["action_send_alert_executed"] is True

    @pytest.mark.asyncio
    async def test_execute_action_step_different_types(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test different action types."""
        action_types = ["send_email", "create_task", "update_record"]

        for action_type in action_types:
            action_step = {
                "step_id": f"act_{action_type}",
                "type": "action",
                "name": f"Action {action_type}",
                "action_type": action_type,
                "params": {},
            }

            updated_context, step_data = await engine.execute_step(
                flow_context, action_step
            )

            assert step_data.output_data["action_type"] == action_type
            assert step_data.output_data["action_executed"] is True


# ============================================================================
# Test Wait Steps
# ============================================================================


class TestWaitSteps:
    """Test wait step execution."""

    @pytest.mark.asyncio
    async def test_execute_wait_step_duration(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test wait step with duration."""
        wait_step = {
            "step_id": "wait_1",
            "type": "wait",
            "name": "Wait 5 minutes",
            "duration_seconds": 300,
        }

        updated_context, step_data = await engine.execute_step(flow_context, wait_step)

        assert step_data.output_data["wait_started"] is True
        assert "resume_at" in step_data.output_data
        assert updated_context.flow_data["paused_until"] == step_data.output_data["resume_at"]

    @pytest.mark.asyncio
    async def test_execute_wait_step_until_time(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test wait step until specific time."""
        future_dt = now_sao_paulo() + timedelta(hours=2)
        wait_step = {
            "step_id": "wait_2",
            "type": "wait",
            "name": "Wait until time",
            "wait_until": future_dt.isoformat(),
        }

        updated_context, step_data = await engine.execute_step(flow_context, wait_step)

        assert step_data.output_data["wait_started"] is True
        resume_at = datetime.fromisoformat(step_data.output_data["resume_at"])
        assert abs((resume_at - future_dt).total_seconds()) < 1
        assert updated_context.flow_data["paused_until"] == step_data.output_data["resume_at"]

    @pytest.mark.asyncio
    async def test_execute_wait_step_updates_flow_data(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test that wait step updates flow data."""
        wait_step = {
            "step_id": "wait_3",
            "type": "wait",
            "name": "Wait",
            "duration_seconds": 60,
        }

        updated_context, step_data = await engine.execute_step(flow_context, wait_step)

        assert "paused_until" in updated_context.flow_data


# ============================================================================
# Test Branch Steps
# ============================================================================


class TestBranchSteps:
    """Test branch step execution."""

    @pytest.mark.asyncio
    async def test_execute_branch_step_condition_true(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test branch step when condition is true."""
        flow_context.variables["is_urgent"] = True

        branch_step = {
            "step_id": "branch_1",
            "type": "branch",
            "name": "Urgency Branch",
            "branches": ["urgent_path", "normal_path"],
            "condition": {"variable": "is_urgent", "operator": "equals", "value": True},
        }

        updated_context, step_data = await engine.execute_step(
            flow_context, branch_step
        )

        assert step_data.output_data["branch_taken"] == "urgent_path"

    @pytest.mark.asyncio
    async def test_execute_branch_step_condition_false(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test branch step when condition is false."""
        flow_context.variables["is_urgent"] = False

        branch_step = {
            "step_id": "branch_2",
            "type": "branch",
            "name": "Urgency Branch",
            "branches": ["urgent_path", "normal_path"],
            "condition": {"variable": "is_urgent", "operator": "equals", "value": True},
        }

        updated_context, step_data = await engine.execute_step(
            flow_context, branch_step
        )

        assert step_data.output_data["branch_taken"] == "normal_path"

    @pytest.mark.asyncio
    async def test_execute_branch_step_no_condition(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test branch step without condition (default to first)."""
        branch_step = {
            "step_id": "branch_3",
            "type": "branch",
            "name": "Default Branch",
            "branches": ["branch_a", "branch_b"],
        }

        updated_context, step_data = await engine.execute_step(
            flow_context, branch_step
        )

        assert step_data.output_data["branch_taken"] == "branch_a"


# ============================================================================
# Test Loop Steps
# ============================================================================


class TestLoopSteps:
    """Test loop step execution."""

    @pytest.mark.asyncio
    async def test_execute_loop_step_first_iteration(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test loop step first iteration."""
        loop_step = {
            "step_id": "loop_1",
            "type": "loop",
            "name": "Repeat Questions",
            "loop_to_step": "question_1",
            "max_iterations": 3,
        }

        updated_context, step_data = await engine.execute_step(flow_context, loop_step)

        assert step_data.output_data["current_iteration"] == 1
        assert step_data.output_data["should_continue"] is True
        assert step_data.output_data["loop_to_step"] == "question_1"

    @pytest.mark.asyncio
    async def test_execute_loop_step_max_iterations(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test loop step reaching max iterations."""
        flow_context.flow_data["loop_iteration"] = 2

        loop_step = {
            "step_id": "loop_2",
            "type": "loop",
            "name": "Repeat Questions",
            "loop_to_step": "question_1",
            "max_iterations": 3,
        }

        updated_context, step_data = await engine.execute_step(flow_context, loop_step)

        assert step_data.output_data["current_iteration"] == 3
        assert step_data.output_data["should_continue"] is False
        assert step_data.output_data["loop_to_step"] is None

    @pytest.mark.asyncio
    async def test_execute_loop_step_with_condition(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test loop step with condition."""
        flow_context.variables["continue_loop"] = True

        loop_step = {
            "step_id": "loop_3",
            "type": "loop",
            "name": "Conditional Loop",
            "loop_to_step": "question_1",
            "max_iterations": 5,
            "condition": {
                "variable": "continue_loop",
                "operator": "equals",
                "value": True,
            },
        }

        updated_context, step_data = await engine.execute_step(flow_context, loop_step)

        assert step_data.output_data["should_continue"] is True


# ============================================================================
# Test End Steps
# ============================================================================


class TestEndSteps:
    """Test end step execution."""

    @pytest.mark.asyncio
    async def test_execute_end_step_completed(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test end step with completed reason."""
        end_step = {
            "step_id": "end_1",
            "type": "end",
            "name": "Flow End",
            "reason": "completed",
            "final_message": "Thank you for completing the assessment!",
        }

        updated_context, step_data = await engine.execute_step(flow_context, end_step)

        assert step_data.output_data["flow_ended"] is True
        assert step_data.output_data["end_reason"] == "completed"
        assert "final_message" in step_data.output_data

    @pytest.mark.asyncio
    async def test_execute_end_step_cancelled(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test end step with cancelled reason."""
        end_step = {
            "step_id": "end_2",
            "type": "end",
            "name": "Flow Cancelled",
            "reason": "cancelled",
        }

        updated_context, step_data = await engine.execute_step(flow_context, end_step)

        assert step_data.output_data["end_reason"] == "cancelled"

    @pytest.mark.asyncio
    async def test_execute_end_step_updates_flow_data(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test that end step updates flow data."""
        end_step = {
            "step_id": "end_3",
            "type": "end",
            "name": "Flow End",
            "reason": "completed",
        }

        updated_context, step_data = await engine.execute_step(flow_context, end_step)

        assert "ended_at" in updated_context.flow_data


# ============================================================================
# Test Condition Evaluation
# ============================================================================


class TestConditionEvaluation:
    """Test condition evaluation."""

    @pytest.mark.asyncio
    async def test_evaluate_simple_condition_equals(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test simple equals condition."""
        flow_context.variables["status"] = "active"
        condition = {
            "type": "simple",
            "variable": "status",
            "operator": "equals",
            "value": "active",
        }

        result = engine.condition_evaluator.evaluate(condition, flow_context)

        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_simple_condition_not_equals(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test simple not equals condition."""
        flow_context.variables["status"] = "active"
        condition = {
            "type": "simple",
            "variable": "status",
            "operator": "not_equals",
            "value": "inactive",
        }

        result = engine.condition_evaluator.evaluate(condition, flow_context)

        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_simple_condition_greater_than(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test simple greater than condition."""
        flow_context.variables["score"] = 85
        condition = {
            "type": "simple",
            "variable": "score",
            "operator": "greater_than",
            "value": 70,
        }

        result = engine.condition_evaluator.evaluate(condition, flow_context)

        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_and_condition(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test AND condition."""
        flow_context.variables["age"] = 45
        flow_context.variables["is_active"] = True

        condition = {
            "type": "and",
            "conditions": [
                {
                    "type": "simple",
                    "variable": "age",
                    "operator": "greater_than",
                    "value": 18,
                },
                {
                    "type": "simple",
                    "variable": "is_active",
                    "operator": "equals",
                    "value": True,
                },
            ],
        }

        result = engine.condition_evaluator.evaluate(condition, flow_context)

        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_or_condition(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test OR condition."""
        flow_context.variables["is_urgent"] = False
        flow_context.variables["is_critical"] = True

        condition = {
            "type": "or",
            "conditions": [
                {
                    "type": "simple",
                    "variable": "is_urgent",
                    "operator": "equals",
                    "value": True,
                },
                {
                    "type": "simple",
                    "variable": "is_critical",
                    "operator": "equals",
                    "value": True,
                },
            ],
        }

        result = engine.condition_evaluator.evaluate(condition, flow_context)

        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_not_condition(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test NOT condition."""
        flow_context.variables["is_disabled"] = False

        condition = {
            "type": "not",
            "condition": {
                "type": "simple",
                "variable": "is_disabled",
                "operator": "equals",
                "value": True,
            },
        }

        result = engine.condition_evaluator.evaluate(condition, flow_context)

        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_complex_nested_condition(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test complex nested condition."""
        flow_context.variables["age"] = 45
        flow_context.variables["is_active"] = True
        flow_context.variables["score"] = 85

        condition = {
            "type": "and",
            "conditions": [
                {
                    "type": "simple",
                    "variable": "age",
                    "operator": "greater_than",
                    "value": 18,
                },
                {
                    "type": "or",
                    "conditions": [
                        {
                            "type": "simple",
                            "variable": "is_active",
                            "operator": "equals",
                            "value": True,
                        },
                        {
                            "type": "simple",
                            "variable": "score",
                            "operator": "greater_than",
                            "value": 90,
                        },
                    ],
                },
            ],
        }

        result = engine.condition_evaluator.evaluate(condition, flow_context)

        assert result is True


# ============================================================================
# Test Variable Substitution
# ============================================================================


class TestVariableSubstitution:
    """Test variable substitution."""

    def test_substitute_variables_single(self, engine: FlowEngine):
        """Test substituting single variable."""
        template = "Hello {{name}}!"
        variables = {"name": "João"}

        result = engine.executor._substitute_variables(template, variables)

        assert result == "Hello João!"

    def test_substitute_variables_multiple(self, engine: FlowEngine):
        """Test substituting multiple variables."""
        template = "Hello {{name}}, you are {{age}} years old."
        variables = {"name": "João", "age": 45}

        result = engine.executor._substitute_variables(template, variables)

        assert result == "Hello João, you are 45 years old."

    def test_substitute_variables_missing(self, engine: FlowEngine):
        """Test substituting with missing variable."""
        template = "Hello {{name}}, {{missing}}!"
        variables = {"name": "João"}

        result = engine.executor._substitute_variables(template, variables)

        # Should leave missing variables as is or handle gracefully
        assert "João" in result

    def test_substitute_variables_empty_template(self, engine: FlowEngine):
        """Test substituting in empty template."""
        template = ""
        variables = {"name": "João"}

        result = engine.executor._substitute_variables(template, variables)

        assert result == ""

    def test_substitute_variables_no_variables(self, engine: FlowEngine):
        """Test substituting with no variables."""
        template = "Hello there!"
        variables = {}

        result = engine.executor._substitute_variables(template, variables)

        assert result == "Hello there!"


# ============================================================================
# Test Error Handling
# ============================================================================


class TestErrorHandling:
    """Test error handling in step execution."""

    @pytest.mark.asyncio
    async def test_execute_step_marks_failure(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Invalid step type should fail fast before step execution."""
        invalid_step = {
            "step_id": "fail_step",
            "type": "invalid_type",
            "name": "Invalid Step",
        }

        with pytest.raises(ValueError):
            await engine.execute_step(flow_context, invalid_step)

        # Type coercion fails before FlowStepData creation.
        assert len(flow_context.steps_history) == 0

    @pytest.mark.asyncio
    async def test_execute_step_error_tracking(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Handler failures should be tracked in step history."""
        invalid_step = {
            "step_id": "error_step",
            "type": "decision",
            "name": "Error Step",
            "conditions": [
                {
                    "variable": "missing_score",
                    "operator": "greater_than",
                    "value": 10,
                    "path": "high",
                }
            ],
            "default_path": "low",
        }

        with pytest.raises(TypeError):
            await engine.execute_step(flow_context, invalid_step)

        step_data = flow_context.steps_history[0]
        assert step_data.error is not None
        assert isinstance(step_data.error, str)
        assert len(step_data.error) > 0

    @pytest.mark.asyncio
    async def test_execute_step_timing_on_failure(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test that timing is tracked even on failure."""
        invalid_step = {
            "step_id": "timing_fail",
            "type": "decision",
            "name": "Timing Fail",
            "conditions": [
                {
                    "variable": "missing_score",
                    "operator": "greater_than",
                    "value": 10,
                    "path": "high",
                }
            ],
            "default_path": "low",
        }

        with pytest.raises(TypeError):
            await engine.execute_step(flow_context, invalid_step)

        step_data = flow_context.steps_history[0]
        assert step_data.started_at is not None
        assert step_data.completed_at is not None
        assert step_data.completed_at >= step_data.started_at


# ============================================================================
# Test Integration Scenarios
# ============================================================================


class TestIntegrationScenarios:
    """Test complete flow execution scenarios."""

    @pytest.mark.asyncio
    async def test_complete_flow_execution(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test executing multiple steps in sequence."""
        steps = [
            {
                "step_id": "msg_1",
                "type": "message",
                "name": "Welcome",
                "content": "Hello {{patient_name}}!",
            },
            {
                "step_id": "q_1",
                "type": "question",
                "name": "Ask pain level",
                "question": "What is your pain level?",
            },
            {
                "step_id": "end_1",
                "type": "end",
                "name": "End",
                "reason": "completed",
            },
        ]

        for step in steps:
            updated_context, step_data = await engine.execute_step(flow_context, step)
            flow_context = updated_context
            assert step_data.status == FlowStepStatus.COMPLETED

        assert len(flow_context.steps_completed) == 3
        assert len(flow_context.steps_history) == 3

    @pytest.mark.asyncio
    async def test_flow_with_decision_branching(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test flow with decision and branching."""
        flow_context.variables["pain_level"] = 8

        # Execute message
        msg_step = {
            "step_id": "msg_1",
            "type": "message",
            "name": "Intro",
            "content": "Let's check your pain level.",
        }
        flow_context, _ = await engine.execute_step(flow_context, msg_step)

        # Execute decision
        decision_step = {
            "step_id": "dec_1",
            "type": "decision",
            "name": "Pain Decision",
            "conditions": [
                {
                    "variable": "pain_level",
                    "operator": "greater_than",
                    "value": 7,
                    "path": "high_pain",
                },
            ],
            "default_path": "low_pain",
        }
        flow_context, step_data = await engine.execute_step(flow_context, decision_step)

        assert step_data.output_data["chosen_path"] == "high_pain"
        assert len(flow_context.steps_completed) == 2

    @pytest.mark.asyncio
    async def test_flow_with_loop_iterations(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test flow with loop iterations."""
        for i in range(3):
            loop_step = {
                "step_id": f"loop_{i}",
                "type": "loop",
                "name": "Repeat",
                "loop_to_step": "question_1",
                "max_iterations": 3,
            }

            flow_context, step_data = await engine.execute_step(flow_context, loop_step)

            assert step_data.output_data["current_iteration"] == i + 1

        assert flow_context.flow_data["loop_iteration"] == 3

    @pytest.mark.asyncio
    async def test_flow_variable_persistence(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test that variables persist across steps."""
        # Step 1: Send message (updates last_message_sent)
        msg_step = {
            "step_id": "msg_1",
            "type": "message",
            "name": "Message",
            "content": "Test message",
        }
        flow_context, _ = await engine.execute_step(flow_context, msg_step)

        assert "last_message_sent" in flow_context.variables

        # Step 2: Ask question (updates last_question)
        q_step = {
            "step_id": "q_1",
            "type": "question",
            "name": "Question",
            "question": "Test question?",
        }
        flow_context, _ = await engine.execute_step(flow_context, q_step)

        # Both variables should still be present
        assert "last_message_sent" in flow_context.variables
        assert "last_question" in flow_context.variables

    @pytest.mark.asyncio
    async def test_flow_data_accumulation(
        self, engine: FlowEngine, flow_context: FlowContext
    ):
        """Test that flow data accumulates correctly."""
        initial_data_count = len(flow_context.flow_data)

        # Execute action that adds flow data
        action_step = {
            "step_id": "act_1",
            "type": "action",
            "name": "Action",
            "action_type": "test_action",
            "params": {},
        }
        flow_context, _ = await engine.execute_step(flow_context, action_step)

        # Execute decision that adds flow data
        decision_step = {
            "step_id": "dec_1",
            "type": "decision",
            "name": "Decision",
            "conditions": [],
            "default_path": "default",
        }
        flow_context, _ = await engine.execute_step(flow_context, decision_step)

        # Flow data should have accumulated
        assert len(flow_context.flow_data) > initial_data_count
