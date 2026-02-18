"""
Unit Tests for FlowTemplateValidator - QW-021 Flow Services Consolidation.

Tests template validation including structure, steps, transitions, graph validation,
and business rules for the consolidated flow template system.

Part 1: Structure and Basic Validation Tests
"""

import pytest

from app.services.flow.templates.validator import FlowTemplateValidator
from app.services.flow.types import (
    FlowTemplate,
    FlowType,
)


@pytest.fixture
def validator():
    """Create FlowTemplateValidator instance."""
    return FlowTemplateValidator()


@pytest.fixture
def valid_template():
    """Create valid flow template for testing."""
    return FlowTemplate(
        template_id="test_template_001",
        flow_type=FlowType.DAILY_FOLLOW_UP,
        version="1.0.0",
        name="Test Template",
        description="Test template description",
        steps=[
            {
                "step_id": "step_001",
                "type": "message",
                "name": "Greeting",
                "content": "Hello! How are you today?",
            },
            {
                "step_id": "step_002",
                "type": "question",
                "name": "Daily Check",
                "question": "How are you feeling?",
                "expected_response_type": "text",
            },
            {
                "step_id": "step_003",
                "type": "end",
                "name": "Complete",
            },
        ],
        transitions=[
            {"from_step": "step_001", "to_step": "step_002", "type": "automatic"},
            {"from_step": "step_002", "to_step": "step_003", "type": "user_response"},
        ],
    )


@pytest.fixture
def minimal_template():
    """Create minimal valid template."""
    return FlowTemplate(
        template_id="minimal_template",
        flow_type=FlowType.CUSTOM,
        version="1.0.0",
        name="Minimal Template",
        description="Minimal template",
        steps=[{"step_id": "step_001", "type": "message", "name": "Single Step"}],
    )


class TestFlowTemplateValidatorInitialization:
    """Test FlowTemplateValidator initialization."""

    def test_initialization(self, validator):
        """Test validator initializes correctly."""
        assert validator is not None
        assert validator.config is not None
        assert validator.required_step_fields is not None
        assert validator.valid_step_types is not None

    def test_configuration_loaded(self, validator):
        """Test configuration is loaded."""
        assert hasattr(validator.config, "validate_template_on_load")
        assert hasattr(validator.config, "strict_template_validation")


class TestStructureValidation:
    """Test basic template structure validation."""

    def test_validate_valid_template(self, validator, valid_template):
        """Test validating a valid template."""
        result = validator.validate_template(valid_template)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_minimal_template(self, validator, minimal_template):
        """Test validating minimal template."""
        result = validator.validate_template(minimal_template)

        assert result.is_valid is True

    def test_missing_template_id(self, validator):
        """Test validation fails with missing template_id."""
        template = FlowTemplate(
            template_id="",
            flow_type=FlowType.DAILY_FOLLOW_UP,
            name="Test",
            description="Test",
            steps=[{"step_id": "s1", "type": "message", "name": "Step 1"}],
        )

        result = validator.validate_template(template)

        assert result.is_valid is False
        assert any("template id" in err.lower() for err in result.errors)

    def test_missing_flow_type(self, validator, valid_template):
        """Test validation with missing flow type."""
        valid_template.flow_type = None

        result = validator.validate_template(valid_template)

        assert result.is_valid is False
        assert any("flow type" in err.lower() for err in result.errors)

    def test_invalid_version_format(self, validator, valid_template):
        """Test validation with invalid version format."""
        valid_template.version = "1.0"  # Should be x.y.z

        result = validator.validate_template(valid_template)

        assert any("version" in warn.lower() for warn in result.warnings)

    def test_valid_version_formats(self, validator):
        """Test various valid version formats."""
        assert validator._is_valid_version_format("1.0.0") is True
        assert validator._is_valid_version_format("2.1.3") is True
        assert validator._is_valid_version_format("10.20.30") is True

    def test_invalid_version_formats(self, validator):
        """Test various invalid version formats."""
        assert validator._is_valid_version_format("1.0") is False
        assert validator._is_valid_version_format("1") is False
        assert validator._is_valid_version_format("v1.0.0") is False
        assert validator._is_valid_version_format("1.0.0-beta") is False

    def test_no_steps(self, validator):
        """Test validation fails with no steps."""
        template = FlowTemplate(
            template_id="no_steps",
            flow_type=FlowType.DAILY_FOLLOW_UP,
            name="No Steps",
            description="Template with no steps",
            steps=[],
        )

        result = validator.validate_template(template)

        assert result.is_valid is False
        assert any("at least one step" in err.lower() for err in result.errors)

    def test_negative_timeout(self, validator, valid_template):
        """Test validation fails with negative timeout."""
        valid_template.default_timeout_minutes = -1

        result = validator.validate_template(valid_template)

        assert result.is_valid is False
        assert any("timeout" in err.lower() for err in result.errors)

    def test_zero_timeout(self, validator, valid_template):
        """Test validation fails with zero timeout."""
        valid_template.default_timeout_minutes = 0

        result = validator.validate_template(valid_template)

        assert result.is_valid is False

    def test_very_high_timeout_warning(self, validator, valid_template):
        """Test warning for very high timeout."""
        valid_template.default_timeout_minutes = 10000  # Very high

        result = validator.validate_template(valid_template)

        assert any("timeout" in warn.lower() for warn in result.warnings)

    def test_negative_max_retries(self, validator, valid_template):
        """Test validation fails with negative max retries."""
        valid_template.max_retries = -1

        result = validator.validate_template(valid_template)

        assert result.is_valid is False
        assert any("retries" in err.lower() for err in result.errors)

    def test_very_high_max_retries_warning(self, validator, valid_template):
        """Test warning for very high max retries."""
        valid_template.max_retries = 20

        result = validator.validate_template(valid_template)

        assert any("retries" in warn.lower() for warn in result.warnings)


class TestStepValidation:
    """Test individual step validation."""

    def test_validate_valid_step(self, validator):
        """Test validating a valid step."""
        step = {"step_id": "s1", "type": "message", "name": "Test Step"}

        result = validator.validate_step(step)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_step_missing_required_fields(self, validator):
        """Test step validation fails with missing required fields."""
        step = {"step_id": "s1"}  # Missing type and name

        result = validator.validate_step(step)

        assert result.is_valid is False
        assert any("type" in err.lower() for err in result.errors)
        assert any("name" in err.lower() for err in result.errors)

    def test_step_invalid_type(self, validator):
        """Test step validation fails with invalid type."""
        step = {"step_id": "s1", "type": "invalid_type", "name": "Test"}

        result = validator.validate_step(step)

        assert result.is_valid is False
        assert any("invalid step type" in err.lower() for err in result.errors)

    def test_step_invalid_step_id(self, validator):
        """Test step validation with invalid step_id."""
        step = {"step_id": "", "type": "message", "name": "Test"}

        result = validator.validate_step(step)

        assert result.is_valid is False
        assert any("step_id" in err.lower() for err in result.errors)

    def test_step_invalid_name(self, validator):
        """Test step validation with invalid name."""
        step = {"step_id": "s1", "type": "message", "name": ""}

        result = validator.validate_step(step)

        assert result.is_valid is False
        assert any("name" in err.lower() for err in result.errors)


class TestStepTypeValidation:
    """Test type-specific step validation."""

    def test_message_step_valid(self, validator):
        """Test valid MESSAGE step."""
        step = {
            "step_id": "s1",
            "type": "message",
            "name": "Message",
            "content": "Hello world",
        }

        result = validator.validate_step(step)

        assert result.is_valid is True

    def test_message_step_missing_content(self, validator):
        """Test MESSAGE step missing content."""
        step = {"step_id": "s1", "type": "message", "name": "Message"}

        result = validator.validate_step(step)

        assert result.is_valid is True
        assert any("content" in warn.lower() for warn in result.warnings)

    def test_question_step_valid(self, validator):
        """Test valid QUESTION step."""
        step = {
            "step_id": "s1",
            "type": "question",
            "name": "Question",
            "question": "How are you?",
            "expected_response_type": "text",
        }

        result = validator.validate_step(step)

        assert result.is_valid is True

    def test_question_step_missing_question(self, validator):
        """Test QUESTION step missing question field."""
        step = {"step_id": "s1", "type": "question", "name": "Question"}

        result = validator.validate_step(step)

        assert result.is_valid is False
        assert any("question" in err.lower() for err in result.errors)

    def test_question_step_no_response_type_warning(self, validator):
        """Test QUESTION step without expected_response_type."""
        step = {
            "step_id": "s1",
            "type": "question",
            "name": "Question",
            "question": "How are you?",
        }

        result = validator.validate_step(step)

        assert any("expected_response_type" in warn.lower() for warn in result.warnings)

    def test_decision_step_valid(self, validator):
        """Test valid DECISION step."""
        step = {
            "step_id": "s1",
            "type": "decision",
            "name": "Decision",
            "condition": "response == 'yes'",
            "branches": {"true": "step_2", "false": "step_3"},
        }

        result = validator.validate_step(step)

        assert result.is_valid is True

    def test_decision_step_missing_condition(self, validator):
        """Test DECISION step missing condition."""
        step = {"step_id": "s1", "type": "decision", "name": "Decision"}

        result = validator.validate_step(step)

        assert result.is_valid is False
        assert any("condition" in err.lower() for err in result.errors)

    def test_decision_step_missing_branches(self, validator):
        """Test DECISION step missing branches."""
        step = {
            "step_id": "s1",
            "type": "decision",
            "name": "Decision",
            "condition": "x > 0",
        }

        result = validator.validate_step(step)

        assert result.is_valid is False
        assert any("branches" in err.lower() for err in result.errors)

    def test_action_step_valid(self, validator):
        """Test valid ACTION step."""
        step = {
            "step_id": "s1",
            "type": "action",
            "name": "Action",
            "action": "send_notification",
        }

        result = validator.validate_step(step)

        assert result.is_valid is True

    def test_action_step_missing_action(self, validator):
        """Test ACTION step missing action field."""
        step = {"step_id": "s1", "type": "action", "name": "Action"}

        result = validator.validate_step(step)

        assert result.is_valid is False
        assert any("action" in err.lower() for err in result.errors)

    def test_wait_step_valid(self, validator):
        """Test valid WAIT step."""
        step = {
            "step_id": "s1",
            "type": "wait",
            "name": "Wait",
            "duration": 300,
        }

        result = validator.validate_step(step)

        assert result.is_valid is True

    def test_wait_step_missing_duration(self, validator):
        """Test WAIT step missing duration."""
        step = {"step_id": "s1", "type": "wait", "name": "Wait"}

        result = validator.validate_step(step)

        assert result.is_valid is False
        assert any(
            "duration" in err.lower() or "wait_for" in err.lower()
            for err in result.errors
        )

    def test_branch_step_valid(self, validator):
        """Test valid BRANCH step."""
        step = {
            "step_id": "s1",
            "type": "branch",
            "name": "Branch",
            "condition": "score > 5",
            "paths": {"high": "step_2", "low": "step_3"},
        }

        result = validator.validate_step(step)

        assert result.is_valid is True

    def test_branch_step_missing_condition(self, validator):
        """Test BRANCH step missing condition."""
        step = {"step_id": "s1", "type": "branch", "name": "Branch"}

        result = validator.validate_step(step)

        assert result.is_valid is False
        assert any("condition" in err.lower() for err in result.errors)

    def test_branch_step_missing_paths(self, validator):
        """Test BRANCH step missing paths."""
        step = {
            "step_id": "s1",
            "type": "branch",
            "name": "Branch",
            "condition": "x > 0",
        }

        result = validator.validate_step(step)

        assert result.is_valid is False
        assert any("paths" in err.lower() for err in result.errors)

    def test_loop_step_valid(self, validator):
        """Test valid LOOP step."""
        step = {
            "step_id": "s1",
            "type": "loop",
            "name": "Loop",
            "target_step_id": "step_001",
            "max_iterations": 5,
        }

        result = validator.validate_step(step)

        assert result.is_valid is True

    def test_loop_step_missing_target(self, validator):
        """Test LOOP step missing target_step_id."""
        step = {"step_id": "s1", "type": "loop", "name": "Loop"}

        result = validator.validate_step(step)

        assert result.is_valid is False
        assert any("target_step_id" in err.lower() for err in result.errors)

    def test_loop_step_no_max_iterations_warning(self, validator):
        """Test LOOP step without max_iterations."""
        step = {
            "step_id": "s1",
            "type": "loop",
            "name": "Loop",
            "target_step_id": "step_001",
        }

        result = validator.validate_step(step)

        assert any("max_iterations" in warn.lower() for warn in result.warnings)

    def test_end_step_valid(self, validator):
        """Test valid END step."""
        step = {"step_id": "s1", "type": "end", "name": "End"}

        result = validator.validate_step(step)

        assert result.is_valid is True


class TestDuplicateStepValidation:
    """Test duplicate step detection."""

    def test_duplicate_step_ids(self, validator):
        """Test validation fails with duplicate step IDs."""
        template = FlowTemplate(
            template_id="dup_steps",
            flow_type=FlowType.DAILY_FOLLOW_UP,
            name="Duplicate Steps",
            description="Template with duplicate step IDs",
            steps=[
                {"step_id": "step_001", "type": "message", "name": "Step 1"},
                {"step_id": "step_001", "type": "message", "name": "Step 2"},
            ],
        )

        result = validator.validate_template(template)

        assert result.is_valid is False
        assert any("duplicate" in err.lower() for err in result.errors)

    def test_no_duplicate_step_ids(self, validator, valid_template):
        """Test validation passes with unique step IDs."""
        result = validator.validate_template(valid_template)

        assert result.is_valid is True


class TestStepOrderValidation:
    """Test step order validation."""

    def test_end_step_not_in_middle(self, validator):
        """Test validation fails when END step is in middle."""
        template = FlowTemplate(
            template_id="end_in_middle",
            flow_type=FlowType.DAILY_FOLLOW_UP,
            name="End in Middle",
            description="Template with END step in middle",
            steps=[
                {"step_id": "step_001", "type": "message", "name": "Start"},
                {"step_id": "step_002", "type": "end", "name": "End"},
                {"step_id": "step_003", "type": "message", "name": "After End"},
            ],
        )

        result = validator.validate_template(template)

        assert any("order" in warn.lower() for warn in result.warnings)

    def test_end_step_at_end_valid(self, validator, valid_template):
        """Test END step at end is valid."""
        result = validator.validate_template(valid_template)

        assert result.is_valid is True


class TestTransitionValidation:
    """Test transition validation."""

    def test_validate_transitions_valid(self, validator, valid_template):
        """Test validating valid transitions."""
        result = validator.validate_template(valid_template)

        assert result.is_valid is True

    def test_transition_missing_from_step(self, validator):
        """Test transition missing from_step."""
        template = FlowTemplate(
            template_id="missing_from",
            flow_type=FlowType.DAILY_FOLLOW_UP,
            name="Missing From",
            description="Transition missing from_step",
            steps=[
                {"step_id": "step_001", "type": "message", "name": "Step 1"},
                {"step_id": "step_002", "type": "message", "name": "Step 2"},
            ],
            transitions=[{"to_step": "step_002", "type": "automatic"}],
        )

        result = validator.validate_template(template)

        assert result.is_valid is False
        assert any("from_step" in err.lower() for err in result.errors)

    def test_transition_missing_to_step(self, validator):
        """Test transition missing to_step."""
        template = FlowTemplate(
            template_id="missing_to",
            flow_type=FlowType.DAILY_FOLLOW_UP,
            name="Missing To",
            description="Transition missing to_step",
            steps=[
                {"step_id": "step_001", "type": "message", "name": "Step 1"},
                {"step_id": "step_002", "type": "message", "name": "Step 2"},
            ],
            transitions=[{"from_step": "step_001", "type": "automatic"}],
        )

        result = validator.validate_template(template)

        assert result.is_valid is False
        assert any("to_step" in err.lower() for err in result.errors)

    def test_transition_invalid_from_step(self, validator):
        """Test transition with non-existent from_step."""
        template = FlowTemplate(
            template_id="invalid_from",
            flow_type=FlowType.DAILY_FOLLOW_UP,
            name="Invalid From",
            description="Transition with invalid from_step",
            steps=[
                {"step_id": "step_001", "type": "message", "name": "Step 1"},
                {"step_id": "step_002", "type": "message", "name": "Step 2"},
            ],
            transitions=[
                {"from_step": "step_999", "to_step": "step_002", "type": "automatic"}
            ],
        )

        result = validator.validate_template(template)

        assert result.is_valid is False
        assert any("not found" in err.lower() for err in result.errors)

    def test_transition_invalid_to_step(self, validator):
        """Test transition with non-existent to_step."""
        template = FlowTemplate(
            template_id="invalid_to",
            flow_type=FlowType.DAILY_FOLLOW_UP,
            name="Invalid To",
            description="Transition with invalid to_step",
            steps=[
                {"step_id": "step_001", "type": "message", "name": "Step 1"},
                {"step_id": "step_002", "type": "message", "name": "Step 2"},
            ],
            transitions=[
                {"from_step": "step_001", "to_step": "step_999", "type": "automatic"}
            ],
        )

        result = validator.validate_template(template)

        assert result.is_valid is False
        assert any("not found" in err.lower() for err in result.errors)

    def test_transition_invalid_type(self, validator):
        """Test transition with invalid type."""
        template = FlowTemplate(
            template_id="invalid_type",
            flow_type=FlowType.DAILY_FOLLOW_UP,
            name="Invalid Type",
            description="Transition with invalid type",
            steps=[
                {"step_id": "step_001", "type": "message", "name": "Step 1"},
                {"step_id": "step_002", "type": "message", "name": "Step 2"},
            ],
            transitions=[
                {
                    "from_step": "step_001",
                    "to_step": "step_002",
                    "type": "invalid_type",
                }
            ],
        )

        result = validator.validate_template(template)

        assert result.is_valid is False
        assert any("invalid type" in err.lower() for err in result.errors)

    def test_conditional_transition_missing_condition(self, validator):
        """Test conditional transition missing condition field."""
        template = FlowTemplate(
            template_id="missing_condition",
            flow_type=FlowType.DAILY_FOLLOW_UP,
            name="Missing Condition",
            description="Conditional transition without condition",
            steps=[
                {"step_id": "step_001", "type": "message", "name": "Step 1"},
                {"step_id": "step_002", "type": "message", "name": "Step 2"},
            ],
            transitions=[
                {
                    "from_step": "step_001",
                    "to_step": "step_002",
                    "type": "conditional",
                }
            ],
        )

        result = validator.validate_template(template)

        assert result.is_valid is False
        assert any("condition" in err.lower() for err in result.errors)


class TestFlowGraphValidation:
    """Test flow graph structure validation."""

    def test_flow_with_start_step(self, validator, valid_template):
        """Test flow with proper start step."""
        result = validator.validate_template(valid_template)

        assert result.is_valid is True

    def test_flow_without_start_step(self, validator):
        """Test flow without start step (all have incoming transitions)."""
        template = FlowTemplate(
            template_id="no_start",
            flow_type=FlowType.DAILY_FOLLOW_UP,
            name="No Start",
            description="Flow without start step",
            steps=[
                {"step_id": "step_001", "type": "message", "name": "Step 1"},
                {"step_id": "step_002", "type": "message", "name": "Step 2"},
            ],
            transitions=[
                {"from_step": "step_001", "to_step": "step_002", "type": "automatic"},
                {"from_step": "step_002", "to_step": "step_001", "type": "automatic"},
            ],
        )

        result = validator.validate_template(template)

        assert result.is_valid is False
        assert any("start step" in err.lower() for err in result.errors)

    def test_flow_with_multiple_start_steps(self, validator):
        """Test flow with multiple start steps (warning)."""
        template = FlowTemplate(
            template_id="multi_start",
            flow_type=FlowType.DAILY_FOLLOW_UP,
            name="Multiple Starts",
            description="Flow with multiple start steps",
            steps=[
                {"step_id": "step_001", "type": "message", "name": "Start 1"},
                {"step_id": "step_002", "type": "message", "name": "Start 2"},
                {"step_id": "step_003", "type": "message", "name": "Step 3"},
            ],
            transitions=[
                {"from_step": "step_001", "to_step": "step_003", "type": "automatic"},
                {"from_step": "step_002", "to_step": "step_003", "type": "automatic"},
            ],
        )

        result = validator.validate_template(template)

        assert any("multiple start" in warn.lower() for warn in result.warnings)

    def test_flow_without_end_step(self, validator):
        """Test flow without end step (warning)."""
        template = FlowTemplate(
            template_id="no_end",
            flow_type=FlowType.DAILY_FOLLOW_UP,
            name="No End",
            description="Flow without explicit end",
            steps=[
                {"step_id": "step_001", "type": "message", "name": "Step 1"},
                {"step_id": "step_002", "type": "message", "name": "Step 2"},
            ],
            transitions=[
                {"from_step": "step_001", "to_step": "step_002", "type": "automatic"}
            ],
        )

        result = validator.validate_template(template)

        assert any("end step" in warn.lower() for warn in result.warnings)

    def test_flow_with_unreachable_steps(self, validator):
        """Test flow with unreachable steps (warning)."""
        template = FlowTemplate(
            template_id="unreachable",
            flow_type=FlowType.DAILY_FOLLOW_UP,
            name="Unreachable Steps",
            description="Flow with unreachable steps",
            steps=[
                {"step_id": "step_001", "type": "message", "name": "Start"},
                {"step_id": "step_002", "type": "message", "name": "Connected"},
                {"step_id": "step_003", "type": "message", "name": "Unreachable"},
                {"step_id": "step_004", "type": "end", "name": "End"},
            ],
            transitions=[
                {"from_step": "step_001", "to_step": "step_002", "type": "automatic"},
                {"from_step": "step_002", "to_step": "step_004", "type": "automatic"},
            ],
        )

        result = validator.validate_template(template)

        assert any("unreachable" in warn.lower() for warn in result.warnings)


class TestCycleDetection:
    """Test cycle detection in flow graphs."""

    def test_flow_with_intentional_loop(self, validator):
        """Test flow with intentional loop (LOOP step)."""
        template = FlowTemplate(
            template_id="intentional_loop",
            flow_type=FlowType.CUSTOM,
            name="Intentional Loop",
            description="Flow with intentional loop step",
            steps=[
                {"step_id": "step_001", "type": "message", "name": "Start"},
                {
                    "step_id": "step_002",
                    "type": "loop",
                    "name": "Loop",
                    "target_step_id": "step_001",
                    "max_iterations": 3,
                },
                {"step_id": "step_003", "type": "end", "name": "End"},
            ],
            transitions=[
                {"from_step": "step_001", "to_step": "step_002", "type": "automatic"},
                {"from_step": "step_002", "to_step": "step_003", "type": "automatic"},
            ],
        )

        result = validator.validate_template(template)

        # Should not flag intentional loops as errors
        assert result.is_valid is True

    def test_flow_with_unintentional_cycle(self, validator):
        """Test flow with unintentional cycle (warning)."""
        template = FlowTemplate(
            template_id="unintentional_cycle",
            flow_type=FlowType.DAILY_FOLLOW_UP,
            name="Unintentional Cycle",
            description="Flow with unintentional cycle",
            steps=[
                {"step_id": "step_001", "type": "message", "name": "Step 1"},
                {"step_id": "step_002", "type": "message", "name": "Step 2"},
                {"step_id": "step_003", "type": "message", "name": "Step 3"},
            ],
            transitions=[
                {"from_step": "step_001", "to_step": "step_002", "type": "automatic"},
                {"from_step": "step_002", "to_step": "step_003", "type": "automatic"},
                {"from_step": "step_003", "to_step": "step_001", "type": "automatic"},
            ],
        )

        result = validator.validate_template(template)

        assert any("cycle" in warn.lower() for warn in result.warnings)


class TestBusinessRulesValidation:
    """Test business rules and best practices validation."""

    def test_flow_with_many_steps_warning(self, validator):
        """Test warning for flow with many steps."""
        steps = [
            {"step_id": f"step_{i:03d}", "type": "message", "name": f"Step {i}"}
            for i in range(60)
        ]

        template = FlowTemplate(
            template_id="many_steps",
            flow_type=FlowType.CUSTOM,
            name="Many Steps",
            description="Flow with many steps",
            steps=steps,
        )

        result = validator.validate_template(template)

        assert any("many steps" in warn.lower() for warn in result.warnings)

    def test_onboarding_flow_should_have_questions(self, validator):
        """Test onboarding flow without questions (warning)."""
        template = FlowTemplate(
            template_id="onboarding_no_questions",
            flow_type=FlowType.ONBOARDING,
            name="Onboarding No Questions",
            description="Onboarding without questions",
            steps=[
                {"step_id": "step_001", "type": "message", "name": "Welcome"},
                {"step_id": "step_002", "type": "end", "name": "Done"},
            ],
        )

        result = validator.validate_template(template)

        assert any("question" in warn.lower() for warn in result.warnings)

    def test_emergency_protocol_timeout_warning(self, validator):
        """Test emergency protocol with long timeout (warning)."""
        template = FlowTemplate(
            template_id="emergency_slow",
            flow_type=FlowType.EMERGENCY_PROTOCOL,
            name="Slow Emergency",
            description="Emergency with long timeout",
            default_timeout_minutes=30,
            steps=[
                {"step_id": "step_001", "type": "message", "name": "Emergency"},
                {"step_id": "step_002", "type": "end", "name": "Done"},
            ],
        )

        result = validator.validate_template(template)

        assert any(
            "emergency" in warn.lower() and "timeout" in warn.lower()
            for warn in result.warnings
        )

    def test_flow_without_error_handling_warning(self, validator):
        """Test flow without error handling (warning)."""
        template = FlowTemplate(
            template_id="no_error_handling",
            flow_type=FlowType.DAILY_FOLLOW_UP,
            name="No Error Handling",
            description="Flow without error handling",
            steps=[
                {"step_id": "step_001", "type": "message", "name": "Step 1"},
                {"step_id": "step_002", "type": "message", "name": "Step 2"},
            ],
        )

        result = validator.validate_template(template)

        assert any("error handling" in warn.lower() for warn in result.warnings)


class TestCompleteTemplateValidation:
    """Test complete template validation scenarios."""

    def test_complex_valid_template(self, validator):
        """Test complex but valid template."""
        template = FlowTemplate(
            template_id="complex_valid",
            flow_type=FlowType.QUIZ_MENSAL,
            version="2.1.0",
            name="Complex Valid Template",
            description="Complex template with multiple step types",
            steps=[
                {
                    "step_id": "start",
                    "type": "message",
                    "name": "Start",
                    "content": "Welcome",
                },
                {
                    "step_id": "q1",
                    "type": "question",
                    "name": "Question 1",
                    "question": "How are you?",
                },
                {
                    "step_id": "decision",
                    "type": "decision",
                    "name": "Check Response",
                    "condition": "response == 'good'",
                    "branches": {"true": "good_path", "false": "bad_path"},
                },
                {
                    "step_id": "good_path",
                    "type": "message",
                    "name": "Good Response",
                    "content": "Great!",
                },
                {
                    "step_id": "bad_path",
                    "type": "message",
                    "name": "Bad Response",
                    "content": "Sorry to hear that",
                },
                {"step_id": "end", "type": "end", "name": "Complete"},
            ],
            transitions=[
                {"from_step": "start", "to_step": "q1", "type": "automatic"},
                {"from_step": "q1", "to_step": "decision", "type": "user_response"},
                {
                    "from_step": "decision",
                    "to_step": "good_path",
                    "type": "conditional",
                    "condition": "response == 'good'",
                },
                {
                    "from_step": "decision",
                    "to_step": "bad_path",
                    "type": "conditional",
                    "condition": "response != 'good'",
                },
                {"from_step": "good_path", "to_step": "end", "type": "automatic"},
                {"from_step": "bad_path", "to_step": "end", "type": "automatic"},
            ],
        )

        result = validator.validate_template(template)

        assert result.is_valid is True

    def test_strict_validation_mode(self, validator, valid_template):
        """Test strict validation mode (warnings become errors)."""
        validator.config.strict_template_validation = True

        # Add something that causes a warning
        valid_template.version = "1.0"  # Invalid format

        result = validator.validate_template(valid_template)

        # In strict mode, warnings should make template invalid
        assert result.is_valid is False


class TestValidationResultDetails:
    """Test validation result details."""

    def test_validation_result_has_details(self, validator, valid_template):
        """Test that validation result includes details."""
        result = validator.validate_template(valid_template)

        assert "template_id" in result.details
        assert "flow_type" in result.details
        assert "step_count" in result.details
        assert "validated_at" in result.details

    def test_validation_result_details_content(self, validator, valid_template):
        """Test validation result details content."""
        result = validator.validate_template(valid_template)

        assert result.details["template_id"] == valid_template.template_id
        assert result.details["flow_type"] == valid_template.flow_type.value
        assert result.details["step_count"] == len(valid_template.steps)
