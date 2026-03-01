"""
Template validation logic.

Contains the validator and validation result model used to check
template data structures before persistence or execution.
"""

from typing import Dict, List

from pydantic import BaseModel, Field

from app.services.template_loader_pkg.models import (
    FlowTemplateData,
    MessageTemplate,
)


class TemplateValidationResult(BaseModel):
    """Template validation result."""

    is_valid: bool = Field(..., description="Whether template is valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    message_count: int = Field(default=0, description="Number of messages in template")
    ai_optimized_count: int = Field(
        default=0, description="Number of AI-optimized messages"
    )


class TemplateValidator:
    """Dedicated template validation logic."""

    def validate(self, template_data: FlowTemplateData) -> TemplateValidationResult:
        """Validate template data structure and content."""
        errors: List[str] = []
        warnings: List[str] = []
        ai_optimized_count = 0

        errors.extend(self._validate_basic_structure(template_data))

        message_errors, message_warnings, ai_count = self._validate_messages(
            template_data.messages
        )
        errors.extend(message_errors)
        warnings.extend(message_warnings)
        ai_optimized_count = ai_count

        warnings.extend(
            self._validate_ai_optimization(template_data, ai_optimized_count)
        )

        warnings.extend(self._validate_flow_progression(template_data.messages))

        return TemplateValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            message_count=len(template_data.messages),
            ai_optimized_count=ai_optimized_count,
        )

    def _validate_basic_structure(self, template_data: FlowTemplateData) -> List[str]:
        """Validate basic template structure."""
        errors: List[str] = []
        if not template_data.flow_type:
            errors.append("flow_type is required")
        if not template_data.name:
            errors.append("name is required")
        if not template_data.messages:
            errors.append("messages dictionary is required and cannot be empty")
        return errors

    def _validate_messages(
        self, messages: Dict[int, MessageTemplate]
    ) -> tuple[List[str], List[str], int]:
        """Validate individual messages."""
        errors: List[str] = []
        warnings: List[str] = []
        ai_optimized_count = 0

        for day, message in messages.items():
            if not isinstance(day, int) or day < 1:
                errors.append(f"Invalid day number: {day}")

            if not message.intent:
                errors.append(f"Message for day {day} missing intent")

            if not message.base_content:
                errors.append(f"Message for day {day} missing base_content")

            try:
                allowed_types = {"text", "media", "quiz_trigger"}
                mt_value = (
                    message.message_type.value
                    if hasattr(message.message_type, "value")
                    else str(message.message_type)
                )
                if mt_value not in allowed_types:
                    errors.append(
                        f"Invalid message_type '{mt_value}' for day {day}. "
                        f"Allowed: {sorted(allowed_types)}"
                    )
            except Exception:
                errors.append(f"Invalid message_type for day {day}")

            if message.ai_instructions or message.personalization_hints:
                ai_optimized_count += 1

            if (
                message.interactive_elements
                and not message.interactive_elements.options
            ):
                warnings.append(
                    f"Message for day {day} has interactive elements but no options"
                )

            for condition in message.conditions:
                if not condition.type or not condition.field or not condition.operator:
                    errors.append(f"Invalid condition in message for day {day}")

        return errors, warnings, ai_optimized_count

    def _validate_ai_optimization(
        self, template_data: FlowTemplateData, ai_optimized_count: int
    ) -> List[str]:
        """Validate AI optimization requirements."""
        warnings: List[str] = []
        if template_data.humanization_level == "high" and ai_optimized_count == 0:
            warnings.append(
                "High humanization level template has no AI-optimized messages"
            )
        return warnings

    def _validate_flow_progression(
        self, messages: Dict[int, MessageTemplate]
    ) -> List[str]:
        """Validate flow progression logic."""
        warnings: List[str] = []
        days = sorted(messages.keys())

        if days and days[0] != 1:
            warnings.append("Flow should start with day 1")

        for i in range(len(days) - 1):
            if days[i + 1] - days[i] > 7:
                warnings.append(
                    f"Large gap between day {days[i]} and day {days[i + 1]}"
                )

        return warnings
