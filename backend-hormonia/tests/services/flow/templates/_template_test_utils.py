"""
TOMBSTONED -- Phase 16 (Dead Code Removal)

Tests for app.services.flow.templates which has been tombstoned.
"""

import pytest

pytest.skip(
    "app.services.flow.templates tombstoned in Phase 16 (Dead Code Removal)",
    allow_module_level=True,
)

from app.services.flow.types import (
    FlowTemplate,
    FlowStepType,
    FlowTransitionType,
    FlowType,
)


def normalize_template_dict(
    template_dict: dict, *, include_step_type_defaults: bool = False
) -> dict:
    """Normalize legacy fixture dictionaries to current FlowTemplate contract."""
    normalized = dict(template_dict)
    normalized.setdefault("flow_type", FlowType.ONBOARDING.value)
    normalized.setdefault("description", normalized.get("name", "Template"))

    steps = []
    for step in normalized.get("steps", []):
        step_copy = dict(step)
        step_copy.setdefault("name", step_copy.get("step_id", "step"))

        if include_step_type_defaults:
            step_type = step_copy.get("type")
            if step_type == FlowStepType.DECISION.value:
                step_copy.setdefault("condition", "true")
                step_copy.setdefault("branches", [])
            elif step_type == FlowStepType.BRANCH.value:
                step_copy.setdefault("condition", "true")
                step_copy.setdefault("paths", [])
            elif step_type == FlowStepType.LOOP.value:
                step_copy.setdefault("target_step_id", step_copy.get("step_id", "step"))
                step_copy.setdefault("max_iterations", 3)

        steps.append(step_copy)
    normalized["steps"] = steps

    transitions = []
    for transition in normalized.get("transitions", []):
        transition_copy = dict(transition)
        if transition_copy.get("type") == "direct":
            transition_copy["type"] = FlowTransitionType.AUTOMATIC.value
        transitions.append(transition_copy)
    normalized["transitions"] = transitions

    return normalized


def build_template(
    template_dict: dict, *, include_step_type_defaults: bool = False
) -> FlowTemplate:
    """Build FlowTemplate from normalized fixture dictionary."""
    return FlowTemplate(
        **normalize_template_dict(
            template_dict,
            include_step_type_defaults=include_step_type_defaults,
        )
    )
