"""
Flow Validator - Validation logic for Flow Services (QW-021).

This module implements the FlowValidator class, which handles validation
of flows, steps, transitions, and business rules.

Validation includes:
- Flow start validation (prerequisites, constraints)
- Step execution validation
- Transition validation (valid paths, conditions)
- Data integrity validation
- Business rules validation

Migration Note:
    This consolidates validation logic from:
    - flow_validation.py (main validation)
    - flow_integrity.py (data integrity)
    - flow_data_integrity.py (duplicate integrity checks)
    - Various validation scattered across flow services
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import UUID
import logging

from ..types import (
    FlowContext,
    FlowType,
    FlowStatus,
    FlowStepType,
    FlowStepData,
    FlowValidationResult,
)
from ..config import get_flow_config
from .integrity import FlowIntegrityChecker
from .rules import ValidationRule
from .constraints import get_default_rules

logger = logging.getLogger(__name__)


class FlowValidator:
    """
    Flow validation engine.

    Handles all validation logic for flows, steps, and transitions.
    Can be configured for strict or lenient validation based on config.

    Example:
        >>> validator = FlowValidator()
        >>> result = await validator.validate_start(
        ...     patient_id=patient_id,
        ...     flow_type=FlowType.DAILY_CHECKIN,
        ...     template=template
        ... )
        >>> if not result.is_valid:
        ...     print(f"Validation failed: {result.errors}")
    """

    def __init__(
        self,
        strict_mode: Optional[bool] = None,
        integrity_checker: Optional[FlowIntegrityChecker] = None,
        rules: Optional[List[ValidationRule]] = None,
    ):
        """
        Initialize the flow validator.

        Args:
            strict_mode: Override config's strict validation setting
        """
        self.config = get_flow_config()
        self.execution_config = self.config.execution
        self.strict_mode = (
            strict_mode
            if strict_mode is not None
            else self.execution_config.enable_strict_validation
        )
        self.integrity_checker = integrity_checker or FlowIntegrityChecker()
        self.rules: List[ValidationRule] = rules or get_default_rules(self.config)
        logger.info(f"FlowValidator initialized (strict_mode={self.strict_mode})")

    async def validate_start(
        self,
        patient_id: UUID,
        flow_type: FlowType,
        template: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> FlowValidationResult:
        """
        Validate that a flow can be started.

        Checks:
        - Template is valid
        - Patient exists and is active
        - No conflicting flows running
        - Prerequisites are met
        - Resource constraints

        Args:
            patient_id: Patient ID
            flow_type: Type of flow to start
            template: Flow template
            context: Optional context data

        Returns:
            Validation result with errors/warnings

        Example:
            >>> result = await validator.validate_start(
            ...     patient_id=uuid4(),
            ...     flow_type=FlowType.DAILY_CHECKIN,
            ...     template=template
            ... )
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        # Validate template
        template_validation = self._validate_template_structure(template)
        if not template_validation.is_valid:
            errors.extend(template_validation.errors)
            warnings.extend(template_validation.warnings)

        # Validate flow type matches template
        if template.get("flow_type") != flow_type.value:
            errors.append(
                f"Template flow_type '{template.get('flow_type')}' "
                f"does not match requested type '{flow_type.value}'"
            )

        # Validate patient (in production, would check database)
        # For now, just validate UUID is provided
        if not patient_id:
            errors.append("Patient ID is required")
        else:
            details["patient_id"] = str(patient_id)

        # Check for conflicting flows (in production, would query database)
        # For now, just log
        details["concurrent_flows_check"] = "not_implemented"

        # Validate prerequisites (if defined in template)
        prerequisites = template.get("prerequisites", [])
        if prerequisites:
            prereq_validation = await self._validate_prerequisites(
                patient_id, prerequisites, context
            )
            if not prereq_validation.is_valid:
                errors.extend(prereq_validation.errors)
                warnings.extend(prereq_validation.warnings)

        # Check resource constraints
        max_concurrent = self.config.execution.max_concurrent_flows_per_patient
        details["max_concurrent_flows"] = max_concurrent

        is_valid = len(errors) == 0
        if not is_valid:
            logger.warning(f"Flow start validation failed for {flow_type}: {errors}")

        return FlowValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details,
        )

    async def validate_transition(
        self,
        context: FlowContext,
        from_step: str,
        to_step: Optional[str],
        template: Optional[Dict[str, Any]] = None,
    ) -> FlowValidationResult:
        """
        Validate a transition between steps.

        Checks:
        - Transition is allowed by template
        - Conditions are met
        - Step exists in template
        - Flow is in valid state

        Args:
            context: Current flow context
            from_step: Current step ID
            to_step: Next step ID (None if ending)
            template: Optional flow template

        Returns:
            Validation result

        Example:
            >>> result = await validator.validate_transition(
            ...     context=context,
            ...     from_step="step_001",
            ...     to_step="step_002"
            ... )
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "from_step": from_step,
            "to_step": to_step,
        }

        # Validate flow is in active state
        if context.status != FlowStatus.ACTIVE:
            errors.append(f"Cannot transition: flow is in {context.status.value} state")

        # If no template provided, can't validate transition rules
        if not template:
            warnings.append("No template provided, skipping transition rule validation")
        else:
            # Validate from_step exists
            if not self._find_step_in_template(template, from_step):
                errors.append(f"From step '{from_step}' not found in template")

            # Validate to_step exists (if not ending)
            if to_step and not self._find_step_in_template(template, to_step):
                errors.append(f"To step '{to_step}' not found in template")

            # Validate transition is allowed
            if self.config.execution.validate_transitions:
                transition_allowed = self._is_transition_allowed(
                    template, from_step, to_step, context
                )
                if not transition_allowed:
                    errors.append(
                        f"Transition from '{from_step}' to '{to_step}' "
                        "is not allowed by template"
                    )

        # Validate step hasn't been completed already (prevent loops without loop step)
        if to_step and to_step in context.steps_completed:
            warnings.append(
                f"Step '{to_step}' has already been completed (potential infinite loop)"
            )

        rule_errors = await self._run_rules(
            scope="transition",
            context=context,
            from_step=from_step,
            to_step=to_step,
        )
        errors.extend(rule_errors)

        is_valid = len(errors) == 0
        if not is_valid:
            logger.warning(f"Transition validation failed: {errors}")

        return FlowValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details,
        )

    async def validate_step_execution(
        self,
        context: FlowContext,
        step_definition: Dict[str, Any],
    ) -> FlowValidationResult:
        """
        Validate that a step can be executed.

        Checks:
        - Step definition is valid
        - Required input data is present
        - Step-specific validation rules

        Args:
            context: Flow context
            step_definition: Step definition from template

        Returns:
            Validation result

        Example:
            >>> result = await validator.validate_step_execution(
            ...     context=context,
            ...     step_definition=step_def
            ... )
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        # Validate step_id is present
        step_id = step_definition.get("step_id")
        if not step_id:
            errors.append("Step definition missing 'step_id'")
            return FlowValidationResult(is_valid=False, errors=errors)

        details["step_id"] = step_id

        # Validate step_type is valid
        step_type_str = step_definition.get("type")
        if not step_type_str:
            errors.append(f"Step {step_id} missing 'type'")
        else:
            try:
                step_type = FlowStepType(step_type_str)
                details["step_type"] = step_type.value
            except ValueError:
                errors.append(f"Invalid step type: {step_type_str}")

        # Validate required fields based on step type
        if step_type_str == FlowStepType.MESSAGE.value:
            if not step_definition.get("content"):
                errors.append(f"Message step {step_id} missing 'content'")

        elif step_type_str == FlowStepType.QUESTION.value:
            if not step_definition.get("question"):
                errors.append(f"Question step {step_id} missing 'question'")

        elif step_type_str == FlowStepType.DECISION.value:
            conditions = step_definition.get("conditions", [])
            if not conditions and not step_definition.get("default_path"):
                errors.append(
                    f"Decision step {step_id} needs conditions or default_path"
                )

        elif step_type_str == FlowStepType.ACTION.value:
            if not step_definition.get("action_type"):
                errors.append(f"Action step {step_id} missing 'action_type'")

        elif step_type_str == FlowStepType.WAIT.value:
            if not step_definition.get("duration_seconds") and not step_definition.get(
                "wait_until"
            ):
                errors.append(
                    f"Wait step {step_id} needs duration_seconds or wait_until"
                )

        elif step_type_str == FlowStepType.BRANCH.value:
            branches = step_definition.get("branches", [])
            if len(branches) < 2:
                warnings.append(f"Branch step {step_id} has less than 2 branches")

        elif step_type_str == FlowStepType.LOOP.value:
            if not step_definition.get("loop_to_step"):
                errors.append(f"Loop step {step_id} missing 'loop_to_step'")

        is_valid = len(errors) == 0
        return FlowValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details,
        )

    async def validate_data_integrity(
        self, context: FlowContext
    ) -> FlowValidationResult:
        """
        Validate data integrity of flow context.

        Checks:
        - Required fields are present
        - Data types are correct
        - No data corruption
        - Timestamps are logical

        Args:
            context: Flow context to validate

        Returns:
            Validation result

        Example:
            >>> result = await validator.validate_data_integrity(context)
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        # Validate required fields
        if not context.flow_instance_id:
            errors.append("Missing flow_instance_id")

        if not context.flow_type:
            errors.append("Missing flow_type")

        if not context.patient_id:
            errors.append("Missing patient_id")

        # Validate status is valid
        try:
            FlowStatus(context.status)
        except ValueError:
            errors.append(f"Invalid flow status: {context.status}")

        # Validate timestamps are logical
        if context.started_at and context.completed_at:
            if context.completed_at < context.started_at:
                errors.append("Completed_at is before started_at (time paradox)")

        # Validate expiry
        if context.expires_at:
            if context.started_at and context.expires_at < context.started_at:
                errors.append("Expires_at is before started_at")

            if context.status == FlowStatus.ACTIVE:
                if datetime.utcnow() > context.expires_at:
                    warnings.append("Flow has expired but is still active")

        # Validate steps history
        if context.steps_completed:
            for step_id in context.steps_completed:
                if not any(s.step_id == step_id for s in context.steps_history):
                    warnings.append(
                        f"Step {step_id} in completed list but not in history"
                    )

        # Validate current step
        if context.current_step_id:
            if (
                context.status == FlowStatus.COMPLETED
                or context.status == FlowStatus.CANCELLED
            ):
                warnings.append(
                    f"Flow is {context.status.value} but has current_step_id set"
                )

        details["total_steps"] = len(context.steps_history)
        details["completed_steps"] = len(context.steps_completed)

        integrity_result = self.integrity_checker.validate(context)
        if not integrity_result.is_valid:
            errors.extend(integrity_result.errors)

        rule_errors = await self._run_rules(scope="integrity", context=context)
        errors.extend(rule_errors)

        is_valid = len(errors) == 0
        if not is_valid:
            logger.error(f"Data integrity validation failed: {errors}")

        return FlowValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details,
        )

    async def validate_business_rules(
        self,
        context: FlowContext,
        template: Dict[str, Any],
        custom_rules: Optional[List[Dict[str, Any]]] = None,
    ) -> FlowValidationResult:
        """
        Validate business rules for flow execution.

        Business rules can include:
        - Time-based constraints (e.g., only during business hours)
        - Patient-specific rules (e.g., age, condition)
        - Flow-specific rules (e.g., max daily flows)

        Args:
            context: Flow context
            template: Flow template
            custom_rules: Optional custom validation rules

        Returns:
            Validation result

        Example:
            >>> result = await validator.validate_business_rules(
            ...     context=context,
            ...     template=template,
            ...     custom_rules=[{"rule": "max_daily_flows", "max": 3}]
            ... )
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        # Template-defined business rules
        business_rules = template.get("business_rules", [])
        for rule in business_rules:
            rule_result = await self._evaluate_business_rule(rule, context)
            if not rule_result.is_valid:
                errors.extend(rule_result.errors)
                warnings.extend(rule_result.warnings)

        # Custom rules
        if custom_rules:
            for rule in custom_rules:
                rule_result = await self._evaluate_business_rule(rule, context)
                if not rule_result.is_valid:
                    errors.extend(rule_result.errors)
                    warnings.extend(rule_result.warnings)

        # Built-in business rules
        # Rule: Check if flow priority allows execution
        if context.priority:
            details["priority"] = context.priority.value

        is_valid = len(errors) == 0
        return FlowValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details,
        )

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    def _validate_template_structure(
        self, template: Dict[str, Any]
    ) -> FlowValidationResult:
        """Validate template has required structure."""
        errors: List[str] = []
        warnings: List[str] = []

        # Required fields
        if not template.get("template_id"):
            errors.append("Template missing 'template_id'")

        if not template.get("flow_type"):
            errors.append("Template missing 'flow_type'")

        # Steps validation
        steps = template.get("steps", [])
        if not steps:
            errors.append("Template has no steps")
        else:
            # Validate each step has required fields
            step_ids = set()
            for i, step in enumerate(steps):
                step_id = step.get("step_id")
                if not step_id:
                    errors.append(f"Step {i} missing 'step_id'")
                else:
                    if step_id in step_ids:
                        errors.append(f"Duplicate step_id: {step_id}")
                    step_ids.add(step_id)

                if not step.get("type"):
                    errors.append(f"Step {step_id or i} missing 'type'")

        is_valid = len(errors) == 0
        return FlowValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)

    async def _validate_prerequisites(
        self,
        patient_id: UUID,
        prerequisites: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]],
    ) -> FlowValidationResult:
        """Validate flow prerequisites are met."""
        errors: List[str] = []
        warnings: List[str] = []

        for prereq in prerequisites:
            prereq_type = prereq.get("type")
            if prereq_type == "patient_status":
                # In production, would check patient status
                pass
            elif prereq_type == "previous_flow_completed":
                # In production, would check if previous flow completed
                pass
            else:
                warnings.append(f"Unknown prerequisite type: {prereq_type}")

        is_valid = len(errors) == 0
        return FlowValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)

    def _is_transition_allowed(
        self,
        template: Dict[str, Any],
        from_step: str,
        to_step: Optional[str],
        context: FlowContext,
    ) -> bool:
        """Check if transition is allowed by template rules."""
        transitions = template.get("transitions", [])

        # If no transitions defined, allow sequential
        if not transitions:
            return True

        # Look for explicit transition rule
        for transition in transitions:
            if transition.get("from") == from_step:
                if transition.get("to") == to_step:
                    # Check conditions if present
                    conditions = transition.get("conditions", [])
                    if not conditions:
                        return True
                    # For now, assume conditions are met
                    # In production, would evaluate conditions
                    return True

        # If no explicit rule found, check if sequential is allowed
        steps = template.get("steps", [])
        step_ids = [s.get("step_id") for s in steps]
        try:
            from_index = step_ids.index(from_step)
            to_index = step_ids.index(to_step) if to_step else -1
            # Allow sequential transitions
            if to_index == from_index + 1:
                return True
        except ValueError as e:
            logger.debug(f"Step not found in template transition validation: {e}")

        return False

    def _find_step_in_template(
        self, template: Dict[str, Any], step_id: str
    ) -> Optional[Dict[str, Any]]:
        """Find step definition in template."""
        steps = template.get("steps", [])
        for step in steps:
            if step.get("step_id") == step_id:
                return step
        return None

    async def _run_rules(
        self,
        scope: str,
        context: FlowContext,
        *,
        from_step: Optional[str] = None,
        to_step: Optional[str] = None,
        step_data: Optional[FlowStepData] = None,
    ) -> List[str]:
        """Execute rule set for a given scope."""
        errors: List[str] = []
        for rule in self.rules:
            if scope not in rule.scopes:
                continue
            result = await rule.validate(
                context,
                from_step=from_step,
                to_step=to_step,
                step_data=step_data,
            )
            if result:
                errors.extend(result)
        return errors

    async def _evaluate_business_rule(
        self, rule: Dict[str, Any], context: FlowContext
    ) -> FlowValidationResult:
        """Evaluate a single business rule."""
        errors: List[str] = []
        warnings: List[str] = []

        rule_type = rule.get("type")
        rule_name = rule.get("name", rule_type)

        # Placeholder for business rule evaluation
        # In production, would have complex rule engine
        logger.debug(f"Evaluating business rule: {rule_name}")

        is_valid = True  # For now, all rules pass
        return FlowValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)

    def __repr__(self) -> str:
        """String representation."""
        return f"<FlowValidator(strict_mode={self.strict_mode})>"
