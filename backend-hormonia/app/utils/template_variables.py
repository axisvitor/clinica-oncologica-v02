"""
Template variable substitution and validation utilities.
"""

import re
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TemplateVariableProcessor:
    """
    Handles template variable substitution and validation.
    """

    # Define all available template variables and their context mappings
    VARIABLE_MAPPINGS = {
        "{patient_name}": ["patient_name", "patient_data.name"],
        "{treatment_day}": ["treatment_day", "patient_data.current_day"],
        "{current_day}": ["current_day", "flow_data.current_day"],
        "{treatment_type}": ["treatment_type", "patient_data.treatment_type"],
        "{treatment_start_date}": [
            "treatment_start_date",
            "patient_data.treatment_start_date",
        ],
        "{days_since_start}": ["days_since_start"],
        "{progress_percentage}": ["progress_percentage"],
        "{next_quiz_date}": ["next_quiz_date"],
        "{phone}": ["patient_phone", "patient_data.phone"],
        "{enrollment_date}": ["enrollment_date", "flow_start_time"],
        "{clinic_name}": ["clinic_name", "metadata.clinic_name"],
        "{doctor_name}": ["doctor_name", "metadata.doctor_name"],
        "{next_appointment}": ["next_appointment", "metadata.next_appointment"],
    }

    @classmethod
    def substitute_variables(cls, content: str, context: Dict[str, Any]) -> str:
        """
        Replace all template variables with actual values from context.

        Args:
            content: Template content with variables
            context: Context dictionary with patient and flow data

        Returns:
            Content with all variables substituted
        """
        if not content:
            return content

        substituted = content

        # Process each variable mapping
        for placeholder, context_paths in cls.VARIABLE_MAPPINGS.items():
            if placeholder in substituted:
                value = cls._get_context_value(context, context_paths)
                if value is not None:
                    # Convert dates to readable format
                    if isinstance(value, datetime):
                        value = value.strftime("%d/%m/%Y")
                    elif isinstance(value, timedelta):
                        value = f"{value.days} dias"

                    substituted = substituted.replace(placeholder, str(value))
                    logger.debug(f"Substituted {placeholder} with '{value}'")
                else:
                    logger.warning(f"No value found for variable {placeholder}")

        # Calculate computed variables
        substituted = cls._substitute_computed_variables(substituted, context)

        return substituted

    @classmethod
    def _get_context_value(
        cls, context: Dict[str, Any], paths: List[str]
    ) -> Optional[Any]:
        """
        Get value from context using multiple possible paths.

        Args:
            context: Context dictionary
            paths: List of possible paths to the value (e.g., ["patient_name", "patient_data.name"])

        Returns:
            Value if found, None otherwise
        """
        for path in paths:
            try:
                value = context
                for key in path.split("."):
                    if isinstance(value, dict):
                        value = value.get(key)
                        if value is None:
                            break

                if value is not None:
                    return value
            except (KeyError, AttributeError, TypeError):
                continue

        return None

    @classmethod
    def _substitute_computed_variables(
        cls, content: str, context: Dict[str, Any]
    ) -> str:
        """
        Calculate and substitute computed variables.

        Args:
            content: Template content
            context: Context dictionary

        Returns:
            Content with computed variables substituted
        """
        # Calculate days since treatment start
        if "{days_since_start}" in content:
            start_date = cls._get_context_value(
                context, ["treatment_start_date", "patient_data.treatment_start_date"]
            )
            if start_date:
                if isinstance(start_date, str):
                    try:
                        start_date = datetime.fromisoformat(start_date)
                    except (ValueError, TypeError):
                        start_date = None

                if start_date:
                    days = (datetime.now() - start_date).days
                    content = content.replace("{days_since_start}", str(days))

        # Calculate progress percentage (assuming 180-day treatment)
        if "{progress_percentage}" in content:
            current_day = cls._get_context_value(
                context, ["current_day", "treatment_day", "patient_data.current_day"]
            )
            if current_day:
                try:
                    progress = min(100, int((int(current_day) / 180) * 100))
                    content = content.replace("{progress_percentage}", f"{progress}%")
                except (ValueError, TypeError) as e:
                    logger.debug(f"Failed to calculate progress percentage: {e}")

        # Calculate next quiz date (monthly on day 15)
        if "{next_quiz_date}" in content:
            current_day = cls._get_context_value(
                context, ["current_day", "treatment_day", "patient_data.current_day"]
            )
            if current_day:
                try:
                    current = int(current_day)
                    # After day 45, quizzes are monthly on day 15
                    if current > 45:
                        days_in_cycle = (current - 45) % 30
                        days_until_quiz = (
                            15 - days_in_cycle
                            if days_in_cycle < 15
                            else 45 - days_in_cycle
                        )
                        next_date = datetime.now() + timedelta(days=days_until_quiz)
                        content = content.replace(
                            "{next_quiz_date}", next_date.strftime("%d/%m/%Y")
                        )
                except (ValueError, TypeError) as e:
                    logger.debug(f"Failed to calculate next quiz date: {e}")

        return content

    @classmethod
    def validate_variables(cls, content: str) -> List[str]:
        """
        Find any unreplaced template variables in content.

        Args:
            content: Content to validate

        Returns:
            List of unreplaced variables found
        """
        if not content:
            return []

        # Find all {variable} patterns
        pattern = r"\{[^}]+\}"
        unreplaced = re.findall(pattern, content)

        # Filter out known formatting patterns that aren't variables
        formatting_patterns = ["{:.2f}", "{:,}", "{:%}"]
        unreplaced = [
            var
            for var in unreplaced
            if var not in formatting_patterns and not var.startswith("{:")
        ]

        if unreplaced:
            logger.warning(f"Found unreplaced variables: {unreplaced}")

        return unreplaced

    @classmethod
    def extract_required_variables(cls, content: str) -> List[str]:
        """
        Extract all template variables from content.

        Args:
            content: Template content

        Returns:
            List of variable names found
        """
        if not content:
            return []

        pattern = r"\{([^}]+)\}"
        matches = re.findall(pattern, content)

        # Filter to only known variables
        known_vars = [var.strip("{}") for var in cls.VARIABLE_MAPPINGS.keys()]
        required = [f"{{{var}}}" for var in matches if var in known_vars]

        return list(set(required))

    @classmethod
    def build_complete_context(cls, **kwargs) -> Dict[str, Any]:
        """
        Build a complete context dictionary from various sources.

        Args:
            **kwargs: Various context sources (patient, flow_state, etc.)

        Returns:
            Unified context dictionary
        """
        context = {}

        # Add patient data
        if "patient" in kwargs:
            patient = kwargs["patient"]
            context["patient_name"] = patient.name
            context["patient_phone"] = patient.phone
            context["treatment_type"] = patient.treatment_type
            context["treatment_start_date"] = patient.treatment_start_date
            context["patient_data"] = {
                "name": patient.name,
                "phone": patient.phone,
                "treatment_type": patient.treatment_type,
                "treatment_start_date": patient.treatment_start_date,
                "current_day": patient.current_day,
                "metadata": patient.patient_data or {},
            }

        # Add flow state data
        if "flow_state" in kwargs:
            flow_state = kwargs["flow_state"]
            context["flow_start_time"] = flow_state.started_at
            context["enrollment_date"] = flow_state.started_at
            context["flow_data"] = flow_state.state_data or {}
            context["current_day"] = flow_state.current_day

        # Add treatment day calculation
        if "treatment_day" in kwargs:
            context["treatment_day"] = kwargs["treatment_day"]
        elif "patient" in kwargs and hasattr(kwargs["patient"], "treatment_start_date"):
            if kwargs["patient"].treatment_start_date:
                delta = datetime.now().date() - kwargs["patient"].treatment_start_date
                context["treatment_day"] = delta.days + 1

        # Add any additional context
        for key, value in kwargs.items():
            if key not in ["patient", "flow_state", "treatment_day"]:
                context[key] = value

        # Add metadata
        context["metadata"] = kwargs.get("metadata", {})

        return context


# Convenience functions
def substitute_template_variables(content: str, context: Dict[str, Any]) -> str:
    """
    Convenience function to substitute template variables.

    Args:
        content: Template content with variables
        context: Context dictionary

    Returns:
        Content with variables substituted
    """
    return TemplateVariableProcessor.substitute_variables(content, context)


def validate_template_variables(content: str) -> List[str]:
    """
    Convenience function to validate template variables.

    Args:
        content: Content to validate

    Returns:
        List of unreplaced variables
    """
    return TemplateVariableProcessor.validate_variables(content)
