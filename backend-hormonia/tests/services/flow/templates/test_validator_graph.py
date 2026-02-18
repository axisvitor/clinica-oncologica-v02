"""
Tests for FlowTemplateValidator - Graph Validation.

This module tests the flow graph validation logic including:
- Start step detection
- End step detection
- Cycle detection (intentional vs unintentional)
- Reachability analysis
- Graph structure validation
"""

import pytest

from app.services.flow.templates.validator import FlowTemplateValidator
from app.services.flow.types import (
    FlowTransitionType,
    FlowStepType,
)
from tests.services.flow.templates._template_test_utils import build_template


class TestStartStepDetection:
    """Test suite for start step detection."""

    @pytest.fixture
    def validator(self) -> FlowTemplateValidator:
        """Create validator instance."""
        return FlowTemplateValidator()

    def test_single_start_step(self, validator: FlowTemplateValidator):
        """Test flow with single start step (no incoming transitions)."""
        template_dict = {
            "template_id": "single-start",
            "name": "Single Start",
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

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        assert result.is_valid
        assert len(result.errors) == 0
        # Should not warn about multiple start steps
        assert not any("multiple start" in w.lower() for w in result.warnings)

    def test_multiple_start_steps(self, validator: FlowTemplateValidator):
        """Test flow with multiple start steps generates warning."""
        template_dict = {
            "template_id": "multi-start",
            "name": "Multi Start",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "start1",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "start2",
                    "type": FlowStepType.START.value,
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
                {"from_step": "start1", "to_step": "end", "type": "direct"},
                {"from_step": "start2", "to_step": "end", "type": "direct"},
            ],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        # Multiple start steps should generate warning
        assert any("multiple start" in w.lower() for w in result.warnings)

    def test_no_start_step(self, validator: FlowTemplateValidator):
        """Test flow with no start step generates error."""
        template_dict = {
            "template_id": "no-start",
            "name": "No Start",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "step1",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "step2",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
            ],
            "transitions": [
                {"from_step": "step1", "to_step": "step2", "type": "direct"},
                {"from_step": "step2", "to_step": "step1", "type": "direct"},
            ],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        # No start step should be an error
        assert not result.is_valid
        assert any("start step" in e.lower() for e in result.errors)

    def test_start_step_with_incoming_transition(
        self, validator: FlowTemplateValidator
    ):
        """Test step with incoming transition is not considered start step."""
        template_dict = {
            "template_id": "incoming-start",
            "name": "Incoming Start",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "step1",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "step2",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "step3",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
            ],
            "transitions": [
                {"from_step": "step1", "to_step": "step2", "type": "direct"},
                {"from_step": "step2", "to_step": "step3", "type": "direct"},
                # step1 is the only one with no incoming - it's the start
            ],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        assert result.is_valid
        # step1 should be detected as start


class TestEndStepDetection:
    """Test suite for end step detection."""

    @pytest.fixture
    def validator(self) -> FlowTemplateValidator:
        """Create validator instance."""
        return FlowTemplateValidator()

    def test_explicit_end_step(self, validator: FlowTemplateValidator):
        """Test flow with explicit END type step."""
        template_dict = {
            "template_id": "explicit-end",
            "name": "Explicit End",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "start",
                    "type": FlowStepType.START.value,
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

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        assert result.is_valid
        # Should not warn about no end steps
        assert not any("no explicit end" in w.lower() for w in result.warnings)

    def test_implicit_end_step(self, validator: FlowTemplateValidator):
        """Test flow with implicit end step (no outgoing transitions)."""
        template_dict = {
            "template_id": "implicit-end",
            "name": "Implicit End",
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
            ],
            "transitions": [
                {"from_step": "start", "to_step": "step1", "type": "direct"},
                # step1 has no outgoing transitions - implicit end
            ],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        assert result.is_valid

    def test_multiple_end_steps(self, validator: FlowTemplateValidator):
        """Test flow with multiple end steps."""
        template_dict = {
            "template_id": "multi-end",
            "name": "Multi End",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "end1",
                    "type": FlowStepType.END.value,
                    "action": "end_flow",
                    "config": {},
                },
                {
                    "step_id": "end2",
                    "type": FlowStepType.END.value,
                    "action": "end_flow",
                    "config": {},
                },
            ],
            "transitions": [
                {
                    "from_step": "start",
                    "to_step": "end1",
                    "type": FlowTransitionType.CONDITIONAL.value,
                    "condition": "response == 'yes'",
                },
                {
                    "from_step": "start",
                    "to_step": "end2",
                    "type": FlowTransitionType.CONDITIONAL.value,
                    "condition": "response == 'no'",
                },
            ],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        assert result.is_valid
        # Multiple end steps are allowed

    def test_no_end_step_warning(self, validator: FlowTemplateValidator):
        """Test flow with no end step generates warning."""
        template_dict = {
            "template_id": "no-end",
            "name": "No End",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "step1",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "step2",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
            ],
            "transitions": [
                {"from_step": "step1", "to_step": "step2", "type": "direct"},
                {"from_step": "step2", "to_step": "step1", "type": "direct"},
            ],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        # Circular flow with no end should generate warning
        assert any("no explicit end" in w.lower() for w in result.warnings)


class TestCycleDetection:
    """Test suite for cycle detection in flow graphs."""

    @pytest.fixture
    def validator(self) -> FlowTemplateValidator:
        """Create validator instance."""
        return FlowTemplateValidator()

    def test_no_cycles_linear_flow(self, validator: FlowTemplateValidator):
        """Test linear flow has no cycles."""
        template_dict = {
            "template_id": "linear",
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
                    "step_id": "step2",
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
                {"from_step": "step1", "to_step": "step2", "type": "direct"},
                {"from_step": "step2", "to_step": "end", "type": "direct"},
            ],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        assert result.is_valid
        assert not any("cycle" in w.lower() for w in result.warnings)

    def test_simple_cycle(self, validator: FlowTemplateValidator):
        """Test simple cycle detection (A -> B -> A)."""
        template_dict = {
            "template_id": "simple-cycle",
            "name": "Simple Cycle",
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
                    "step_id": "step2",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
            ],
            "transitions": [
                {"from_step": "start", "to_step": "step1", "type": "direct"},
                {"from_step": "step1", "to_step": "step2", "type": "direct"},
                {"from_step": "step2", "to_step": "step1", "type": "direct"},
            ],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        # Should warn about cycles
        assert any("cycle" in w.lower() for w in result.warnings)

    def test_self_loop(self, validator: FlowTemplateValidator):
        """Test self-loop cycle detection (A -> A)."""
        template_dict = {
            "template_id": "self-loop",
            "name": "Self Loop",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "loop_step",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
            ],
            "transitions": [
                {"from_step": "start", "to_step": "loop_step", "type": "direct"},
                {"from_step": "loop_step", "to_step": "loop_step", "type": "direct"},
            ],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        # Self-loop should trigger cycle warning
        assert any("cycle" in w.lower() for w in result.warnings)

    def test_intentional_loop_step(self, validator: FlowTemplateValidator):
        """Test intentional LOOP step type is allowed."""
        template_dict = {
            "template_id": "intentional-loop",
            "name": "Intentional Loop",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "loop_step",
                    "type": FlowStepType.LOOP.value,
                    "action": "send_message",
                    "target_step_id": "loop_step",
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
                {"from_step": "start", "to_step": "loop_step", "type": "direct"},
                {"from_step": "loop_step", "to_step": "loop_step", "type": "direct"},
                {
                    "from_step": "loop_step",
                    "to_step": "end",
                    "type": FlowTransitionType.CONDITIONAL.value,
                    "condition": "done == true",
                },
            ],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        # Intentional loops (with LOOP type) should not warn
        # or warn less severely
        assert result.is_valid

    def test_complex_cycle(self, validator: FlowTemplateValidator):
        """Test complex cycle detection (A -> B -> C -> D -> B)."""
        template_dict = {
            "template_id": "complex-cycle",
            "name": "Complex Cycle",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "stepA",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "stepB",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "stepC",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "stepD",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
            ],
            "transitions": [
                {"from_step": "start", "to_step": "stepA", "type": "direct"},
                {"from_step": "stepA", "to_step": "stepB", "type": "direct"},
                {"from_step": "stepB", "to_step": "stepC", "type": "direct"},
                {"from_step": "stepC", "to_step": "stepD", "type": "direct"},
                {"from_step": "stepD", "to_step": "stepB", "type": "direct"},
            ],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        # Complex cycle should be detected
        assert any("cycle" in w.lower() for w in result.warnings)

    def test_multiple_independent_cycles(self, validator: FlowTemplateValidator):
        """Test multiple independent cycles in flow."""
        template_dict = {
            "template_id": "multi-cycle",
            "name": "Multi Cycle",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
                # First cycle
                {
                    "step_id": "cycle1_a",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "cycle1_b",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                # Second cycle
                {
                    "step_id": "cycle2_a",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "cycle2_b",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
            ],
            "transitions": [
                {"from_step": "start", "to_step": "cycle1_a", "type": "direct"},
                {"from_step": "cycle1_a", "to_step": "cycle1_b", "type": "direct"},
                {"from_step": "cycle1_b", "to_step": "cycle1_a", "type": "direct"},
                {"from_step": "start", "to_step": "cycle2_a", "type": "direct"},
                {"from_step": "cycle2_a", "to_step": "cycle2_b", "type": "direct"},
                {"from_step": "cycle2_b", "to_step": "cycle2_a", "type": "direct"},
            ],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        # Should detect cycles
        assert any("cycle" in w.lower() for w in result.warnings)

    def test_branching_without_cycle(self, validator: FlowTemplateValidator):
        """Test branching flow without cycles."""
        template_dict = {
            "template_id": "branch-no-cycle",
            "name": "Branch No Cycle",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "branch_point",
                    "type": FlowStepType.DECISION.value,
                    "action": "collect_response",
                    "config": {},
                },
                {
                    "step_id": "path_a",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "path_b",
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
                {"from_step": "start", "to_step": "branch_point", "type": "direct"},
                {
                    "from_step": "branch_point",
                    "to_step": "path_a",
                    "type": FlowTransitionType.CONDITIONAL.value,
                    "condition": "choice == 'a'",
                },
                {
                    "from_step": "branch_point",
                    "to_step": "path_b",
                    "type": FlowTransitionType.CONDITIONAL.value,
                    "condition": "choice == 'b'",
                },
                {"from_step": "path_a", "to_step": "end", "type": "direct"},
                {"from_step": "path_b", "to_step": "end", "type": "direct"},
            ],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        assert result.is_valid
        assert not any("cycle" in w.lower() for w in result.warnings)


class TestReachabilityAnalysis:
    """Test suite for reachability analysis."""

    @pytest.fixture
    def validator(self) -> FlowTemplateValidator:
        """Create validator instance."""
        return FlowTemplateValidator()

    def test_all_steps_reachable(self, validator: FlowTemplateValidator):
        """Test all steps are reachable from start."""
        template_dict = {
            "template_id": "all-reachable",
            "name": "All Reachable",
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
                    "step_id": "step2",
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
                {"from_step": "step1", "to_step": "step2", "type": "direct"},
                {"from_step": "step2", "to_step": "end", "type": "direct"},
            ],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        assert result.is_valid
        assert not any("unreachable" in w.lower() for w in result.warnings)

    def test_single_unreachable_step(self, validator: FlowTemplateValidator):
        """Test detection of single unreachable step."""
        template_dict = {
            "template_id": "single-unreachable",
            "name": "Single Unreachable",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "reachable",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "unreachable",
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
                {"from_step": "start", "to_step": "reachable", "type": "direct"},
                {"from_step": "reachable", "to_step": "end", "type": "direct"},
                # unreachable step has no incoming transitions
            ],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        # Should warn about unreachable step
        assert any("unreachable" in w.lower() for w in result.warnings)

    def test_multiple_unreachable_steps(self, validator: FlowTemplateValidator):
        """Test detection of multiple unreachable steps."""
        template_dict = {
            "template_id": "multi-unreachable",
            "name": "Multi Unreachable",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "reachable",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "unreachable1",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "unreachable2",
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
                {"from_step": "start", "to_step": "reachable", "type": "direct"},
                {"from_step": "reachable", "to_step": "end", "type": "direct"},
                # unreachable1 and unreachable2 have no path from start
            ],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        # Should warn about unreachable steps
        assert any("unreachable" in w.lower() for w in result.warnings)

    def test_unreachable_island_of_steps(self, validator: FlowTemplateValidator):
        """Test detection of unreachable island (connected steps not reachable from start)."""
        template_dict = {
            "template_id": "island",
            "name": "Island",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "main",
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
                # Island of connected but unreachable steps
                {
                    "step_id": "island1",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "island2",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
            ],
            "transitions": [
                {"from_step": "start", "to_step": "main", "type": "direct"},
                {"from_step": "main", "to_step": "end", "type": "direct"},
                # Island transitions (not reachable from start)
                {"from_step": "island1", "to_step": "island2", "type": "direct"},
            ],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        # Should warn about unreachable steps
        assert any("unreachable" in w.lower() for w in result.warnings)

    def test_reachability_with_conditional_branches(
        self, validator: FlowTemplateValidator
    ):
        """Test reachability through conditional branches."""
        template_dict = {
            "template_id": "conditional-reach",
            "name": "Conditional Reach",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "decision",
                    "type": FlowStepType.DECISION.value,
                    "action": "collect_response",
                    "config": {},
                },
                {
                    "step_id": "path_a",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "path_b",
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
                {"from_step": "start", "to_step": "decision", "type": "direct"},
                {
                    "from_step": "decision",
                    "to_step": "path_a",
                    "type": FlowTransitionType.CONDITIONAL.value,
                    "condition": "choice == 'a'",
                },
                {
                    "from_step": "decision",
                    "to_step": "path_b",
                    "type": FlowTransitionType.CONDITIONAL.value,
                    "condition": "choice == 'b'",
                },
                {"from_step": "path_a", "to_step": "end", "type": "direct"},
                {"from_step": "path_b", "to_step": "end", "type": "direct"},
            ],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        assert result.is_valid
        # All steps should be reachable through conditional paths
        assert not any("unreachable" in w.lower() for w in result.warnings)


class TestGraphStructureValidation:
    """Test suite for overall graph structure validation."""

    @pytest.fixture
    def validator(self) -> FlowTemplateValidator:
        """Create validator instance."""
        return FlowTemplateValidator()

    def test_empty_flow_graph(self, validator: FlowTemplateValidator):
        """Test validation of empty flow (no steps)."""
        template_dict = {
            "template_id": "empty",
            "name": "Empty",
            "version": "1.0.0",
            "steps": [],
            "transitions": [],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        # Empty flow should fail with explicit validation error.
        assert not result.is_valid
        assert any("at least one step" in error.lower() for error in result.errors)

    def test_single_step_no_transitions(self, validator: FlowTemplateValidator):
        """Test flow with single step and no transitions."""
        template_dict = {
            "template_id": "single",
            "name": "Single",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "only_step",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
            ],
            "transitions": [],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        assert result.is_valid

    def test_disconnected_components(self, validator: FlowTemplateValidator):
        """Test flow with multiple disconnected components."""
        template_dict = {
            "template_id": "disconnected",
            "name": "Disconnected",
            "version": "1.0.0",
            "steps": [
                # Component 1
                {
                    "step_id": "start1",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "end1",
                    "type": FlowStepType.END.value,
                    "action": "end_flow",
                    "config": {},
                },
                # Component 2 (disconnected)
                {
                    "step_id": "start2",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "end2",
                    "type": FlowStepType.END.value,
                    "action": "end_flow",
                    "config": {},
                },
            ],
            "transitions": [
                {"from_step": "start1", "to_step": "end1", "type": "direct"},
                {"from_step": "start2", "to_step": "end2", "type": "direct"},
            ],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        # Should warn about multiple start steps and possibly unreachable
        assert any("multiple start" in w.lower() for w in result.warnings)

    def test_complex_valid_graph(self, validator: FlowTemplateValidator):
        """Test complex but valid flow graph."""
        template_dict = {
            "template_id": "complex",
            "name": "Complex",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "decision1",
                    "type": FlowStepType.DECISION.value,
                    "action": "collect_response",
                    "config": {},
                },
                {
                    "step_id": "path_a",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "path_b",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "decision2",
                    "type": FlowStepType.DECISION.value,
                    "action": "collect_response",
                    "config": {},
                },
                {
                    "step_id": "final_a",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {},
                },
                {
                    "step_id": "final_b",
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
                {"from_step": "start", "to_step": "decision1", "type": "direct"},
                {
                    "from_step": "decision1",
                    "to_step": "path_a",
                    "type": FlowTransitionType.CONDITIONAL.value,
                    "condition": "choice == 'a'",
                },
                {
                    "from_step": "decision1",
                    "to_step": "path_b",
                    "type": FlowTransitionType.CONDITIONAL.value,
                    "condition": "choice == 'b'",
                },
                {"from_step": "path_a", "to_step": "decision2", "type": "direct"},
                {"from_step": "path_b", "to_step": "decision2", "type": "direct"},
                {
                    "from_step": "decision2",
                    "to_step": "final_a",
                    "type": FlowTransitionType.CONDITIONAL.value,
                    "condition": "subchoice == 'x'",
                },
                {
                    "from_step": "decision2",
                    "to_step": "final_b",
                    "type": FlowTransitionType.CONDITIONAL.value,
                    "condition": "subchoice == 'y'",
                },
                {"from_step": "final_a", "to_step": "end", "type": "direct"},
                {"from_step": "final_b", "to_step": "end", "type": "direct"},
            ],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_graph_with_all_validation_aspects(self, validator: FlowTemplateValidator):
        """Test comprehensive graph validation covering all aspects."""
        template_dict = {
            "template_id": "comprehensive",
            "name": "Comprehensive",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {"message": "Welcome"},
                },
                {
                    "step_id": "collect",
                    "type": FlowStepType.QUESTION.value,
                    "action": "collect_response",
                    "question": "Please respond",
                    "config": {"prompt": "Please respond"},
                },
                {
                    "step_id": "validate",
                    "type": FlowStepType.ACTION.value,
                    "action": "validate_response",
                    "config": {"rules": []},
                },
                {
                    "step_id": "process",
                    "type": FlowStepType.ACTION.value,
                    "action": "process_data",
                    "config": {},
                },
                {
                    "step_id": "branch",
                    "type": FlowStepType.DECISION.value,
                    "action": "make_decision",
                    "config": {},
                },
                {
                    "step_id": "success",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {"message": "Success"},
                },
                {
                    "step_id": "retry",
                    "type": FlowStepType.MESSAGE.value,
                    "action": "send_message",
                    "config": {"message": "Please retry"},
                },
                {
                    "step_id": "end",
                    "type": FlowStepType.END.value,
                    "action": "end_flow",
                    "config": {},
                },
            ],
            "transitions": [
                {"from_step": "start", "to_step": "collect", "type": "direct"},
                {"from_step": "collect", "to_step": "validate", "type": "direct"},
                {
                    "from_step": "validate",
                    "to_step": "process",
                    "type": FlowTransitionType.CONDITIONAL.value,
                    "condition": "is_valid == true",
                },
                {
                    "from_step": "validate",
                    "to_step": "retry",
                    "type": FlowTransitionType.CONDITIONAL.value,
                    "condition": "is_valid == false",
                },
                {"from_step": "retry", "to_step": "collect", "type": "direct"},
                {"from_step": "process", "to_step": "branch", "type": "direct"},
                {
                    "from_step": "branch",
                    "to_step": "success",
                    "type": FlowTransitionType.CONDITIONAL.value,
                    "condition": "result == 'success'",
                },
                {
                    "from_step": "branch",
                    "to_step": "end",
                    "type": FlowTransitionType.CONDITIONAL.value,
                    "condition": "result == 'skip'",
                },
                {"from_step": "success", "to_step": "end", "type": "direct"},
                {
                    "from_step": "collect",
                    "to_step": "end",
                    "type": FlowTransitionType.TIMEOUT.value,
                    "timeout": 3600,
                },
            ],
        }

        template = build_template(template_dict, include_step_type_defaults=True)
        result = validator.validate_template(template)

        # Should be valid but may have warnings about cycles (retry loop)
        assert result.is_valid or len(result.warnings) > 0
