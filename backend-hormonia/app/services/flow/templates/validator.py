"""
Flow Template Validator - Validation for Flow Templates (QW-021).

This module provides validation capabilities for flow templates,
ensuring templates are well-formed, consistent, and executable.

Migration Note:
    This consolidates template validation from:
    - flow_template.py (legacy template validation)
    - enhanced_flow_engine.py (execution validation)
    - Various validation scattered across flow services
"""

from typing import Dict, Any, List, Set
from datetime import datetime, timezone
import logging

from ..types import (
    FlowType,
    FlowStepType,
    FlowTemplate,
    FlowValidationResult,
    FlowTransitionType,
)
from ..config import get_flow_config
from ..constants import (
    TemplateValidation,
    FlowErrorMessages,
)
from app.utils.version_utils import is_semantic_version, is_valid_version
from app.utils.timezone import now_sao_paulo


logger = logging.getLogger(__name__)


class FlowTemplateValidator:
    """
    Validator for flow templates.

    Validates template structure, steps, transitions, and business rules.
    """

    def __init__(self):
        """Initialize template validator."""
        self.config = get_flow_config().templates

        # Validation rules
        self.required_step_fields = ["step_id", "type", "name"]
        self.valid_step_types = set(FlowStepType)
        self.valid_transition_types = set(FlowTransitionType)

        logger.info("FlowTemplateValidator initialized")

    # ========================================================================
    # Main Validation Methods
    # ========================================================================

    def validate_template(self, template: FlowTemplate) -> FlowValidationResult:
        """
        Validate a complete flow template.

        Args:
            template: Flow template to validate.

        Returns:
            FlowValidationResult with validation status and messages.
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        # Basic structure validation
        structure_result = self._validate_structure(template)
        errors.extend(structure_result.errors)
        warnings.extend(structure_result.warnings)

        # Step validation
        steps_result = self._validate_steps(template)
        errors.extend(steps_result.errors)
        warnings.extend(steps_result.warnings)

        # Transition validation
        transitions_result = self._validate_transitions(template)
        errors.extend(transitions_result.errors)
        warnings.extend(transitions_result.warnings)

        # Flow graph validation
        graph_result = self._validate_flow_graph(template)
        errors.extend(graph_result.errors)
        warnings.extend(graph_result.warnings)

        # Business rules validation
        business_result = self._validate_business_rules(template)
        errors.extend(business_result.errors)
        warnings.extend(business_result.warnings)

        # Determine if valid
        is_valid = len(errors) == 0

        # Check strict validation mode
        if self.config.strict_template_validation and len(warnings) > 0:
            is_valid = False

        details = {
            "template_id": template.template_id,
            "flow_type": template.flow_type.value if template.flow_type else None,
            "step_count": len(template.steps),
            "transition_count": len(template.transitions),
            "validated_at": now_sao_paulo().isoformat(),
        }

        result = FlowValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details,
        )

        if is_valid:
            logger.info(f"Template {template.template_id} validated successfully")
        else:
            logger.warning(
                f"Template {template.template_id} validation failed: "
                f"{len(errors)} errors, {len(warnings)} warnings"
            )

        return result

    def validate_step(self, step: Dict[str, Any]) -> FlowValidationResult:
        """
        Validate a single step definition.

        Args:
            step: Step definition to validate.

        Returns:
            FlowValidationResult with validation status and messages.
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Check required fields
        for field in self.required_step_fields:
            if field not in step:
                errors.append(
                    FlowErrorMessages.format(
                        FlowErrorMessages.VALIDATION_MISSING_FIELD,
                        field=field,
                    )
                )

        # Validate step type
        if "type" in step:
            try:
                FlowStepType(step["type"])
            except ValueError:
                errors.append(
                    FlowErrorMessages.format(
                        FlowErrorMessages.VALIDATION_INVALID_TYPE,
                        type_name="step",
                        value=step["type"],
                    )
                )

        # Validate step ID
        if "step_id" in step:
            if not step["step_id"] or not isinstance(step["step_id"], str):
                errors.append(
                    FlowErrorMessages.format(
                        FlowErrorMessages.STEP_INVALID_ID,
                        step_id=step.get("step_id"),
                    )
                )

        # Validate step name
        if "name" in step:
            if not step["name"] or not isinstance(step["name"], str):
                errors.append(
                    FlowErrorMessages.format(
                        FlowErrorMessages.STEP_INVALID_NAME,
                        step_name=step.get("name"),
                    )
                )

        # Type-specific validation
        if "type" in step:
            type_result = self._validate_step_by_type(step)
            errors.extend(type_result.errors)
            warnings.extend(type_result.warnings)

        return FlowValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details={"step_id": step.get("step_id", "unknown")},
        )

    # ========================================================================
    # Structure Validation
    # ========================================================================

    def _validate_structure(self, template: FlowTemplate) -> FlowValidationResult:
        """
        Validate basic template structure.

        Args:
            template: Flow template to validate.

        Returns:
            FlowValidationResult with validation status.
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Validate template ID
        if not template.template_id:
            errors.append(FlowErrorMessages.TEMPLATE_ID_REQUIRED)

        # Validate flow type
        if not template.flow_type:
            errors.append(FlowErrorMessages.FLOW_TYPE_REQUIRED)

        # Validate version format
        if not template.version:
            warnings.append(FlowErrorMessages.TEMPLATE_VERSION_MISSING)
        elif not self._is_valid_version_format(template.version):
            warnings.append(
                FlowErrorMessages.format(
                    FlowErrorMessages.TEMPLATE_VERSION_INVALID,
                    version=template.version,
                )
            )

        # Validate steps exist
        if not template.steps or len(template.steps) == 0:
            errors.append(FlowErrorMessages.TEMPLATE_STEPS_REQUIRED)

        # Validate timeout settings
        if template.default_timeout_minutes <= 0:
            errors.append(FlowErrorMessages.TEMPLATE_TIMEOUT_INVALID)

        if template.default_timeout_minutes > self.config.max_template_versions * 60:
            warnings.append(
                FlowErrorMessages.format(
                    FlowErrorMessages.TEMPLATE_TIMEOUT_TOO_HIGH,
                    timeout=template.default_timeout_minutes,
                )
            )

        # Validate max retries
        if template.max_retries < 0:
            errors.append(FlowErrorMessages.TEMPLATE_RETRIES_NEGATIVE)

        if template.max_retries > TemplateValidation.MAX_RETRIES:
            warnings.append(
                FlowErrorMessages.format(
                    FlowErrorMessages.TEMPLATE_RETRIES_TOO_HIGH,
                    retries=template.max_retries,
                )
            )

        return FlowValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    # ========================================================================
    # Step Validation
    # ========================================================================

    def _validate_steps(self, template: FlowTemplate) -> FlowValidationResult:
        """
        Validate all steps in template.

        Args:
            template: Flow template to validate.

        Returns:
            FlowValidationResult with validation status.
        """
        errors: List[str] = []
        warnings: List[str] = []

        step_ids: Set[str] = set()

        for idx, step in enumerate(template.steps):
            # Validate individual step
            step_result = self.validate_step(step)
            errors.extend([f"Step {idx}: {err}" for err in step_result.errors])
            warnings.extend([f"Step {idx}: {warn}" for warn in step_result.warnings])

            # Check for duplicate step IDs
            step_id = step.get("step_id")
            if step_id:
                if step_id in step_ids:
                    errors.append(f"Duplicate step ID: {step_id}")
                step_ids.add(step_id)

        # Validate step order
        if not self._has_valid_step_order(template.steps):
            warnings.append("Step order may cause execution issues")

        return FlowValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def _validate_step_by_type(
        self,
        step: Dict[str, Any],
    ) -> FlowValidationResult:
        """
        Validate step based on its type.

        Args:
            step: Step definition to validate.

        Returns:
            FlowValidationResult with validation status.
        """
        errors: List[str] = []
        warnings: List[str] = []

        step_type_str = step.get("type")
        if not step_type_str:
            return FlowValidationResult(is_valid=True, errors=[], warnings=[])

        try:
            step_type = FlowStepType(step_type_str)
        except ValueError:
            return FlowValidationResult(
                is_valid=False,
                errors=[f"Invalid step type: {step_type_str}"],
                warnings=[],
            )

        # Type-specific validation
        if step_type == FlowStepType.MESSAGE:
            if "content" not in step and "message" not in step:
                warnings.append("MESSAGE step should include 'content' or 'message' field")

        elif step_type == FlowStepType.QUESTION:
            if "question" not in step:
                errors.append("QUESTION step requires 'question' field")
            if "expected_response_type" not in step:
                warnings.append("QUESTION step should specify expected_response_type")

        elif step_type == FlowStepType.DECISION:
            if "condition" not in step:
                errors.append("DECISION step requires 'condition' field")
            if "branches" not in step:
                errors.append("DECISION step requires 'branches' field")

        elif step_type == FlowStepType.ACTION:
            if "action" not in step and "action_type" not in step:
                errors.append("ACTION step requires 'action' or 'action_type' field")

        elif step_type == FlowStepType.WAIT:
            if "duration" not in step and "wait_for" not in step:
                errors.append("WAIT step requires 'duration' or 'wait_for' field")

        elif step_type == FlowStepType.BRANCH:
            if "condition" not in step:
                errors.append("BRANCH step requires 'condition' field")
            if "paths" not in step:
                errors.append("BRANCH step requires 'paths' field")

        elif step_type == FlowStepType.LOOP:
            if "target_step_id" not in step:
                errors.append("LOOP step requires 'target_step_id' field")
            if "max_iterations" not in step:
                warnings.append("LOOP step should specify max_iterations")

        return FlowValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    # ========================================================================
    # Transition Validation
    # ========================================================================

    def _validate_transitions(
        self,
        template: FlowTemplate,
    ) -> FlowValidationResult:
        """
        Validate all transitions in template.

        Args:
            template: Flow template to validate.

        Returns:
            FlowValidationResult with validation status.
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Get all step IDs
        step_ids = {step.get("step_id") for step in template.steps if "step_id" in step}

        for idx, transition in enumerate(template.transitions):
            # Validate from_step
            from_step = transition.get("from_step")
            if not from_step:
                errors.append(f"Transition {idx}: missing 'from_step'")
            elif from_step not in step_ids:
                errors.append(f"Transition {idx}: from_step '{from_step}' not found")

            # Validate to_step
            to_step = transition.get("to_step")
            if not to_step:
                errors.append(f"Transition {idx}: missing 'to_step'")
            elif to_step not in step_ids:
                errors.append(f"Transition {idx}: to_step '{to_step}' not found")

            # Validate transition type
            transition_type = transition.get("type")
            if transition_type:
                try:
                    FlowTransitionType(transition_type)
                except ValueError:
                    errors.append(f"Transition {idx}: invalid type '{transition_type}'")

            # Validate conditional transitions
            if transition_type == FlowTransitionType.CONDITIONAL.value:
                if "condition" not in transition:
                    errors.append(
                        f"Transition {idx}: CONDITIONAL transition requires 'condition'"
                    )

        # Check for orphaned steps (no incoming transitions except start)
        self._check_orphaned_steps(template, step_ids, warnings)

        return FlowValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    # ========================================================================
    # Flow Graph Validation
    # ========================================================================

    def _validate_flow_graph(
        self,
        template: FlowTemplate,
    ) -> FlowValidationResult:
        """
        Validate flow as a directed graph.

        Args:
            template: Flow template to validate.

        Returns:
            FlowValidationResult with validation status.
        """
        errors: List[str] = []
        warnings: List[str] = []

        if not template.steps:
            return FlowValidationResult(is_valid=True, errors=[], warnings=[])

        # Build adjacency list
        graph = self._build_graph(template)

        # Check for start step
        start_steps = self._find_start_steps(template)
        if not start_steps:
            errors.append("Flow must have at least one start step")
        elif len(start_steps) > 1:
            warnings.append(f"Flow has multiple start steps: {start_steps}")

        # Check for explicit end steps
        explicit_end_steps = [
            step.get("step_id")
            for step in template.steps
            if step.get("type") == FlowStepType.END.value
        ]
        if not explicit_end_steps:
            warnings.append("Flow has no explicit end steps")

        # Check for cycles (except intentional loops)
        if self._has_unintentional_cycles(template, graph):
            warnings.append("Flow may contain unintentional cycles")

        # Check for unreachable steps
        if start_steps:
            reachable = self._find_reachable_steps(start_steps[0], graph)
            all_steps = {step.get("step_id") for step in template.steps}
            unreachable = all_steps - reachable
            if unreachable:
                warnings.append(f"Unreachable steps: {unreachable}")

        return FlowValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    # ========================================================================
    # Business Rules Validation
    # ========================================================================

    def _validate_business_rules(
        self,
        template: FlowTemplate,
    ) -> FlowValidationResult:
        """
        Validate business rules and best practices.

        Args:
            template: Flow template to validate.

        Returns:
            FlowValidationResult with validation status.
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Check maximum steps
        if len(template.steps) > TemplateValidation.MAX_TEMPLATE_STEPS:
            warnings.append(
                FlowErrorMessages.format(
                    FlowErrorMessages.FLOW_TOO_MANY_STEPS,
                    count=len(template.steps),
                )
            )

        # Check for recommended patterns
        step_types = [step.get("type") for step in template.steps]

        # Onboarding flows should have questions
        if template.flow_type == FlowType.ONBOARDING:
            if FlowStepType.QUESTION.value not in step_types:
                warnings.append(FlowErrorMessages.ONBOARDING_MISSING_QUESTIONS)

        # Emergency protocols should be fast
        if template.flow_type == FlowType.EMERGENCY_PROTOCOL:
            if (
                template.default_timeout_minutes
                > TemplateValidation.EMERGENCY_PROTOCOL_MAX_TIMEOUT
            ):
                warnings.append(
                    FlowErrorMessages.format(
                        FlowErrorMessages.EMERGENCY_TIMEOUT_TOO_HIGH,
                        max_timeout=TemplateValidation.EMERGENCY_PROTOCOL_MAX_TIMEOUT,
                    )
                )

        # Check for error handling
        has_error_handling = any(
            step.get("on_error") or step.get("error_handler") for step in template.steps
        )
        if not has_error_handling:
            warnings.append(FlowErrorMessages.FLOW_MISSING_ERROR_HANDLING)

        return FlowValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _is_valid_version_format(self, version: str) -> bool:
        """
        Check if version follows semantic versioning using standardized utilities.

        Args:
            version: Version string to validate.

        Returns:
            True if valid, False otherwise.
        """
        # Use the centralized version utility
        return is_valid_version(version) and is_semantic_version(version)

    def _has_valid_step_order(self, steps: List[Dict[str, Any]]) -> bool:
        """
        Check if steps are in a valid order.

        Args:
            steps: List of step definitions.

        Returns:
            True if order is valid, False otherwise.
        """
        # Check if END step is not in the middle
        for idx, step in enumerate(steps[:-1]):
            if step.get("type") == FlowStepType.END.value:
                return False
        return True

    def _build_graph(self, template: FlowTemplate) -> Dict[str, List[str]]:
        """
        Build adjacency list from transitions.

        Args:
            template: Flow template.

        Returns:
            Adjacency list representation of flow graph.
        """
        graph: Dict[str, List[str]] = {}

        for transition in template.transitions:
            from_step = transition.get("from_step")
            to_step = transition.get("to_step")
            if from_step and to_step:
                if from_step not in graph:
                    graph[from_step] = []
                graph[from_step].append(to_step)

        return graph

    def _find_start_steps(self, template: FlowTemplate) -> List[str]:
        """
        Find start steps (no incoming transitions).

        Args:
            template: Flow template.

        Returns:
            List of start step IDs.
        """
        all_steps = {
            step.get("step_id") for step in template.steps if "step_id" in step
        }
        target_steps = {
            t.get("to_step") for t in template.transitions if "to_step" in t
        }
        return list(all_steps - target_steps)

    def _find_end_steps(self, template: FlowTemplate) -> List[str]:
        """
        Find end steps (no outgoing transitions or END type).

        Args:
            template: Flow template.

        Returns:
            List of end step IDs.
        """
        end_steps = []

        # Find steps with END type
        for step in template.steps:
            if step.get("type") == FlowStepType.END.value:
                end_steps.append(step.get("step_id"))

        # Find steps with no outgoing transitions
        source_steps = {
            t.get("from_step") for t in template.transitions if "from_step" in t
        }
        all_steps = {
            step.get("step_id") for step in template.steps if "step_id" in step
        }
        end_steps.extend(all_steps - source_steps)

        return list(set(end_steps))

    def _has_unintentional_cycles(
        self,
        template: FlowTemplate,
        graph: Dict[str, List[str]],
    ) -> bool:
        """
        Check for unintentional cycles in flow.

        Args:
            template: Flow template.
            graph: Adjacency list of flow graph.

        Returns:
            True if unintentional cycles exist, False otherwise.
        """
        # Get intentional loops
        loop_steps = {
            step.get("step_id")
            for step in template.steps
            if step.get("type") == FlowStepType.LOOP.value
        }

        # DFS to detect cycles
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def has_cycle(step_id: str) -> bool:
            visited.add(step_id)
            rec_stack.add(step_id)

            for neighbor in graph.get(step_id, []):
                # Ignore intentional loops
                if step_id in loop_steps:
                    continue

                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(step_id)
            return False

        for step_id in graph:
            if step_id not in visited:
                if has_cycle(step_id):
                    return True

        return False

    def _find_reachable_steps(
        self,
        start_step: str,
        graph: Dict[str, List[str]],
    ) -> Set[str]:
        """
        Find all steps reachable from start step.

        Args:
            start_step: Starting step ID.
            graph: Adjacency list of flow graph.

        Returns:
            Set of reachable step IDs.
        """
        reachable: Set[str] = set()
        stack = [start_step]

        while stack:
            step_id = stack.pop()
            if step_id in reachable:
                continue

            reachable.add(step_id)

            for neighbor in graph.get(step_id, []):
                if neighbor not in reachable:
                    stack.append(neighbor)

        return reachable

    def _check_orphaned_steps(
        self,
        template: FlowTemplate,
        step_ids: Set[str],
        warnings: List[str],
    ) -> None:
        """
        Check for orphaned steps (unreachable from start).

        Note: This validation is fully handled in _validate_flow_graph()
        (lines 448-498) which performs a comprehensive reachability analysis
        using graph traversal. This method is kept for backward compatibility
        with external validators that may call it directly.

        The comprehensive graph validation includes:
        - Start step detection
        - End step detection
        - Cycle detection
        - Reachability analysis (which covers orphaned steps)

        Args:
            template: Flow template.
            step_ids: Set of all step IDs.
            warnings: List to append warnings to.
        """
        # Implementation deliberately empty - all orphaned step detection
        # is now handled by _validate_flow_graph() for better accuracy
        # and to avoid duplicate validation logic.
        pass


# ============================================================================
# Exports
# ============================================================================

__all__ = ["FlowTemplateValidator"]
