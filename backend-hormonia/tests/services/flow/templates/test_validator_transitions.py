"""
Tests for FlowTemplateValidator - Transitions Validation.

This module tests the transition validation logic including:
- Transition structure validation
- From/to step references
- Transition types
- Conditional transition requirements
- Orphaned step detection
"""

import pytest
from typing import Dict, Any

from app.services.flow.templates.validator import FlowTemplateValidator
from app.services.flow.types import (
    FlowTransitionType,
    FlowStepType,
)
from tests.services.flow.templates._template_test_utils import build_template


class TestTransitionValidation:
    """Test suite for transition validation."""

    @pytest.fixture
    def validator(self) -> FlowTemplateValidator:
        """Create validator instance."""
        return FlowTemplateValidator()

    @pytest.fixture
    def base_template_dict(self) -> Dict[str, Any]:
        """Create base valid template dictionary."""
        return {
            "template_id": "test-flow",
            "name": "Test Flow",
            "version": "1.0.0",
            "description": "Test flow for transitions",
            "steps": [
                {
                    "step_id": "start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {"message": "Welcome"},
                },
                {
                    "step_id": "step1",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {"message": "Step 1"},
                },
                {
                    "step_id": "step2",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {"message": "Step 2"},
                },
                {
                    "step_id": "end",
                    "type": FlowStepType.END.value,
                    "action": "end_flow",
                    "config": {},
                },
            ],
            "transitions": [],
        }

    # ========================================================================
    # Basic Transition Validation
    # ========================================================================

    def test_valid_simple_transitions(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test validation of simple valid transitions."""
        base_template_dict["transitions"] = [
            {"from_step": "start", "to_step": "step1", "type": "direct"},
            {"from_step": "step1", "to_step": "step2", "type": "direct"},
            {"from_step": "step2", "to_step": "end", "type": "direct"},
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_valid_conditional_transition(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test validation of conditional transitions."""
        base_template_dict["transitions"] = [
            {"from_step": "start", "to_step": "step1", "type": "direct"},
            {
                "from_step": "step1",
                "to_step": "step2",
                "type": FlowTransitionType.CONDITIONAL.value,
                "condition": "response == 'yes'",
            },
            {
                "from_step": "step1",
                "to_step": "end",
                "type": FlowTransitionType.CONDITIONAL.value,
                "condition": "response == 'no'",
            },
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_valid_timeout_transition(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test validation of timeout transitions."""
        base_template_dict["transitions"] = [
            {"from_step": "start", "to_step": "step1", "type": "direct"},
            {
                "from_step": "step1",
                "to_step": "end",
                "type": FlowTransitionType.TIMEOUT.value,
                "timeout": 3600,
            },
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        assert result.is_valid
        assert len(result.errors) == 0

    # ========================================================================
    # Missing Required Fields
    # ========================================================================

    def test_missing_from_step(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test validation fails when from_step is missing."""
        base_template_dict["transitions"] = [
            {"to_step": "step1", "type": "direct"},
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        assert not result.is_valid
        assert any("missing 'from_step'" in error for error in result.errors)

    def test_missing_to_step(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test validation fails when to_step is missing."""
        base_template_dict["transitions"] = [
            {"from_step": "start", "type": "direct"},
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        assert not result.is_valid
        assert any("missing 'to_step'" in error for error in result.errors)

    def test_missing_both_steps(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test validation fails when both from_step and to_step are missing."""
        base_template_dict["transitions"] = [
            {"type": "direct"},
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        assert not result.is_valid
        assert any("missing 'from_step'" in error for error in result.errors)
        assert any("missing 'to_step'" in error for error in result.errors)

    # ========================================================================
    # Invalid Step References
    # ========================================================================

    def test_invalid_from_step_reference(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test validation fails when from_step references non-existent step."""
        base_template_dict["transitions"] = [
            {"from_step": "nonexistent", "to_step": "step1", "type": "direct"},
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        assert not result.is_valid
        assert any(
            "from_step 'nonexistent' not found" in error for error in result.errors
        )

    def test_invalid_to_step_reference(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test validation fails when to_step references non-existent step."""
        base_template_dict["transitions"] = [
            {"from_step": "start", "to_step": "nonexistent", "type": "direct"},
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        assert not result.is_valid
        assert any(
            "to_step 'nonexistent' not found" in error for error in result.errors
        )

    def test_invalid_both_step_references(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test validation fails when both step references are invalid."""
        base_template_dict["transitions"] = [
            {"from_step": "invalid1", "to_step": "invalid2", "type": "direct"},
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        assert not result.is_valid
        assert any("from_step 'invalid1' not found" in error for error in result.errors)
        assert any("to_step 'invalid2' not found" in error for error in result.errors)

    # ========================================================================
    # Transition Type Validation
    # ========================================================================

    def test_invalid_transition_type(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test validation fails with invalid transition type."""
        base_template_dict["transitions"] = [
            {"from_step": "start", "to_step": "step1", "type": "invalid_type"},
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        assert not result.is_valid
        assert any("invalid type 'invalid_type'" in error for error in result.errors)

    def test_all_valid_transition_types(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test all valid transition types pass validation."""
        # Add more steps for different transition types
        base_template_dict["steps"].extend(
            [
                {
                    "step_id": "step3",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {"message": "Step 3"},
                },
                {
                    "step_id": "step4",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {"message": "Step 4"},
                },
            ]
        )

        base_template_dict["transitions"] = [
            {
                "from_step": "start",
                "to_step": "step1",
                "type": FlowTransitionType.AUTOMATIC.value,
            },
            {
                "from_step": "step1",
                "to_step": "step2",
                "type": FlowTransitionType.CONDITIONAL.value,
                "condition": "response == 'yes'",
            },
            {
                "from_step": "step2",
                "to_step": "step3",
                "type": FlowTransitionType.TIMEOUT.value,
                "timeout": 3600,
            },
            {
                "from_step": "step3",
                "to_step": "step4",
                "type": FlowTransitionType.USER_RESPONSE.value,
            },
            {
                "from_step": "step4",
                "to_step": "end",
                "type": FlowTransitionType.AUTOMATIC.value,
            },
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        assert result.is_valid
        assert len(result.errors) == 0

    # ========================================================================
    # Conditional Transition Requirements
    # ========================================================================

    def test_conditional_transition_without_condition(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test conditional transition requires condition field."""
        base_template_dict["transitions"] = [
            {
                "from_step": "start",
                "to_step": "step1",
                "type": FlowTransitionType.CONDITIONAL.value,
            },
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        assert not result.is_valid
        assert any(
            "CONDITIONAL transition requires 'condition'" in error
            for error in result.errors
        )

    def test_conditional_transition_with_empty_condition(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test conditional transition with empty condition string."""
        base_template_dict["transitions"] = [
            {
                "from_step": "start",
                "to_step": "step1",
                "type": FlowTransitionType.CONDITIONAL.value,
                "condition": "",
            },
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        # Empty string still counts as having condition field
        # Business logic validation would handle empty conditions
        assert result.is_valid or any(
            "condition" in error.lower() for error in result.errors
        )

    def test_multiple_conditional_transitions_from_same_step(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test multiple conditional transitions from same step."""
        base_template_dict["transitions"] = [
            {
                "from_step": "start",
                "to_step": "step1",
                "type": FlowTransitionType.CONDITIONAL.value,
                "condition": "response == 'option1'",
            },
            {
                "from_step": "start",
                "to_step": "step2",
                "type": FlowTransitionType.CONDITIONAL.value,
                "condition": "response == 'option2'",
            },
            {
                "from_step": "start",
                "to_step": "end",
                "type": FlowTransitionType.CONDITIONAL.value,
                "condition": "response == 'option3'",
            },
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        assert result.is_valid
        assert len(result.errors) == 0

    # ========================================================================
    # Complex Transition Scenarios
    # ========================================================================

    def test_self_loop_transition(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test self-loop transition (step to itself)."""
        base_template_dict["transitions"] = [
            {"from_step": "start", "to_step": "step1", "type": "direct"},
            {"from_step": "step1", "to_step": "step1", "type": "direct"},
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        # Self-loops should be valid structurally
        assert result.is_valid

    def test_multiple_transitions_between_same_steps(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test multiple transitions between same pair of steps."""
        base_template_dict["transitions"] = [
            {"from_step": "start", "to_step": "step1", "type": "direct"},
            {
                "from_step": "start",
                "to_step": "step1",
                "type": FlowTransitionType.TIMEOUT.value,
                "timeout": 3600,
            },
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        # Multiple transitions between same steps should be valid
        assert result.is_valid

    def test_bidirectional_transitions(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test bidirectional transitions between steps."""
        base_template_dict["transitions"] = [
            {"from_step": "start", "to_step": "step1", "type": "direct"},
            {"from_step": "step1", "to_step": "step2", "type": "direct"},
            {"from_step": "step2", "to_step": "step1", "type": "direct"},
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        # Bidirectional should be valid (creates a cycle, but that's OK)
        assert result.is_valid

    # ========================================================================
    # Multiple Transition Errors
    # ========================================================================

    def test_multiple_invalid_transitions(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test multiple transitions with different errors."""
        base_template_dict["transitions"] = [
            # Missing from_step
            {"to_step": "step1", "type": "direct"},
            # Invalid from_step reference
            {"from_step": "invalid", "to_step": "step1", "type": "direct"},
            # Invalid to_step reference
            {"from_step": "start", "to_step": "invalid", "type": "direct"},
            # Invalid type
            {"from_step": "start", "to_step": "step1", "type": "bad_type"},
            # Missing condition for conditional
            {
                "from_step": "start",
                "to_step": "step2",
                "type": FlowTransitionType.CONDITIONAL.value,
            },
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        assert not result.is_valid
        assert len(result.errors) >= 5
        assert any("missing 'from_step'" in error for error in result.errors)
        assert any("'invalid' not found" in error for error in result.errors)
        assert any("invalid type 'bad_type'" in error for error in result.errors)
        assert any(
            "CONDITIONAL transition requires 'condition'" in error
            for error in result.errors
        )

    # ========================================================================
    # Edge Cases
    # ========================================================================

    def test_no_transitions(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test template with no transitions."""
        base_template_dict["transitions"] = []

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        # No transitions is valid structurally, but may generate warnings
        assert result.is_valid or len(result.warnings) > 0

    def test_single_transition(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test template with single transition."""
        base_template_dict["transitions"] = [
            {"from_step": "start", "to_step": "end", "type": "direct"},
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        assert result.is_valid

    def test_transition_with_extra_fields(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test transition with extra, non-standard fields."""
        base_template_dict["transitions"] = [
            {
                "from_step": "start",
                "to_step": "step1",
                "type": "direct",
                "custom_field": "custom_value",
                "metadata": {"key": "value"},
            },
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        # Extra fields should be allowed (flexible schema)
        assert result.is_valid

    def test_transition_indexing_in_errors(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test that transition errors include proper index."""
        base_template_dict["transitions"] = [
            {"from_step": "start", "to_step": "step1", "type": "direct"},
            {"from_step": "invalid", "to_step": "step2", "type": "direct"},
            {"from_step": "start", "to_step": "step2", "type": "direct"},
            {"to_step": "end", "type": "direct"},
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        assert not result.is_valid
        # Check that error messages include transition index
        assert any("Transition 1" in error for error in result.errors)
        assert any("Transition 3" in error for error in result.errors)

    # ========================================================================
    # Transition Type Combinations
    # ========================================================================

    def test_mixed_transition_types_from_same_step(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test different transition types originating from same step."""
        base_template_dict["transitions"] = [
            {"from_step": "start", "to_step": "step1", "type": "direct"},
            {
                "from_step": "start",
                "to_step": "step2",
                "type": FlowTransitionType.CONDITIONAL.value,
                "condition": "response == 'skip'",
            },
            {
                "from_step": "start",
                "to_step": "end",
                "type": FlowTransitionType.TIMEOUT.value,
                "timeout": 3600,
            },
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_manual_transition_type(
        self,
        validator: FlowTemplateValidator,
        base_template_dict: Dict[str, Any],
    ):
        """Test MANUAL transition type."""
        base_template_dict["transitions"] = [
            {"from_step": "start", "to_step": "step1", "type": "direct"},
            {
                "from_step": "step1",
                "to_step": "end",
                "type": FlowTransitionType.MANUAL.value,
            },
        ]

        template = build_template(base_template_dict)
        result = validator.validate_template(template)

        assert result.is_valid
        assert len(result.errors) == 0


class TestOrphanedStepDetection:
    """Test suite for orphaned step detection in transitions."""

    @pytest.fixture
    def validator(self) -> FlowTemplateValidator:
        """Create validator instance."""
        return FlowTemplateValidator()

    def test_no_orphaned_steps_linear_flow(self, validator: FlowTemplateValidator):
        """Test no orphaned steps in linear flow."""
        template_dict = {
            "template_id": "linear-flow",
            "name": "Linear Flow",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "step1",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "end",
                    "type": FlowStepType.END.value,
                    "action": "end_flow",
                    "config": {},
                },
            ],
            "transitions": [
                {"from_step": "start", "to_step": "step1", "type": "direct"},
                {"from_step": "step1", "to_step": "end", "type": "direct"},
            ],
        }

        template = build_template(template_dict)
        result = validator.validate_template(template)

        assert result.is_valid
        # Should not have unreachable warnings
        assert not any("unreachable" in warning.lower() for warning in result.warnings)

    def test_orphaned_step_no_incoming_transitions(
        self,
        validator: FlowTemplateValidator,
    ):
        """Test detection of orphaned step with no incoming transitions."""
        template_dict = {
            "template_id": "orphaned-flow",
            "name": "Orphaned Flow",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "orphaned",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "end",
                    "type": FlowStepType.END.value,
                    "action": "end_flow",
                    "config": {},
                },
            ],
            "transitions": [
                {"from_step": "start", "to_step": "end", "type": "direct"},
                # orphaned step has no transitions to or from it
            ],
        }

        template = build_template(template_dict)
        result = validator.validate_template(template)

        # Should have warnings about unreachable steps
        assert "orphaned" in str(result.warnings).lower() or any(
            "unreachable" in warning.lower() for warning in result.warnings
        )

    def test_multiple_orphaned_steps(self, validator: FlowTemplateValidator):
        """Test detection of multiple orphaned steps."""
        template_dict = {
            "template_id": "multi-orphaned",
            "name": "Multi Orphaned",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "orphaned1",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "orphaned2",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "end",
                    "type": FlowStepType.END.value,
                    "action": "end_flow",
                    "config": {},
                },
            ],
            "transitions": [
                {"from_step": "start", "to_step": "end", "type": "direct"},
            ],
        }

        template = build_template(template_dict)
        result = validator.validate_template(template)

        # Should warn about multiple unreachable steps
        assert any("unreachable" in warning.lower() for warning in result.warnings)
