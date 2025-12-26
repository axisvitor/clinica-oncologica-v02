"""
Flow Template and Validation Constants.

This module consolidates magic numbers and configuration values
specific to flow template validation and processing.

Addresses:
- P2 Task 2: Extract magic numbers to constants
- Improves maintainability and DRY compliance

File: backend-hormonia/app/services/flow/constants.py
Created: 2025-12-22
"""

from typing import Final


# ============================================================================
# TEMPLATE VALIDATION THRESHOLDS
# ============================================================================


class TemplateValidation:
    """Constants for template validation thresholds."""

    # Step limits
    MAX_TEMPLATE_STEPS: Final[int] = 50
    """Maximum number of steps in a single template before warning"""

    # Retry limits
    MAX_RETRIES: Final[int] = 10
    """Maximum number of retries before warning"""

    # Timeout limits (minutes)
    EMERGENCY_PROTOCOL_MAX_TIMEOUT: Final[int] = 15
    """Maximum timeout for emergency protocols (minutes)"""

    # Version format
    VERSION_PARTS_COUNT: Final[int] = 3
    """Number of parts in semantic version (major.minor.patch)"""


# ============================================================================
# TREATMENT FLOW CONSTANTS
# ============================================================================


class TreatmentFlow:
    """Constants for treatment flow processing."""

    MAX_GAP_BETWEEN_DAYS: Final[int] = 7
    """Maximum days between treatment steps before warning"""

    # Treatment day thresholds
    INITIAL_PERIOD_DAYS: Final[int] = 15
    """End of initial treatment period (days 1-15)"""

    INTERMEDIATE_PERIOD_DAYS: Final[int] = 45
    """End of intermediate treatment period (days 16-45)"""


# ============================================================================
# FLOW ENGINE CONSTANTS
# ============================================================================


class FlowEngine:
    """Constants for flow engine processing and analytics."""

    # History and queue limits
    MAX_ERROR_HISTORY: Final[int] = 100
    """Maximum number of error events to keep in history"""

    MAX_AI_INTERACTION_HISTORY: Final[int] = 100
    """Maximum number of AI interactions to keep per flow"""

    MAX_AI_DECISION_HISTORY: Final[int] = 50
    """Maximum number of AI decisions to keep per flow"""

    MAX_EVENT_QUEUE_SIZE: Final[int] = 1000
    """Maximum size of event queue before dropping old events"""

    # Health thresholds
    UNHEALTHY_THRESHOLD_PERCENT: Final[float] = 0.1
    """Percentage of unhealthy flows before system is degraded (10%)"""

    # Rollout percentages
    ROLLOUT_DISABLED: Final[int] = 0
    """Feature rollout is completely disabled"""

    ROLLOUT_FULL: Final[int] = 100
    """Feature rollout is at 100% (fully enabled)"""

    # Validation limits
    MIN_BRANCH_PATHS: Final[int] = 2
    """Minimum number of branches for a BRANCH step"""


# ============================================================================
# ERROR MESSAGES
# ============================================================================


class FlowErrorMessages:
    """Standardized error message templates for flow services."""

    # Template errors
    TEMPLATE_NOT_FOUND = "Template with ID '{template_id}' not found"
    TEMPLATE_ALREADY_EXISTS = "Template already exists: {template_id}"
    TEMPLATE_VALIDATION_FAILED = "Template validation failed: {details}"

    # Validation errors
    VALIDATION_MISSING_FIELD = "Template missing required field: {field}"
    VALIDATION_INVALID_TYPE = "Invalid {type_name} type: {value}"
    VALIDATION_DUPLICATE_ID = "Duplicate {id_type} ID: {id_value}"

    # Step errors
    STEP_MISSING_FIELD = "{step_type} step requires '{field}' field"
    STEP_INVALID_ID = "Invalid step_id: {step_id}"
    STEP_INVALID_NAME = "Invalid step name: {step_name}"

    # Transition errors
    TRANSITION_MISSING_FIELD = "Transition {index}: missing '{field}'"
    TRANSITION_STEP_NOT_FOUND = "Transition {index}: {step_type} '{step_id}' not found"
    TRANSITION_INVALID_TYPE = "Transition {index}: invalid type '{transition_type}'"
    TRANSITION_MISSING_CONDITION = "Transition {index}: CONDITIONAL transition requires 'condition'"

    # Flow graph errors
    FLOW_NO_START = "Flow must have at least one start step"
    FLOW_MULTIPLE_STARTS = "Flow has multiple start steps: {start_steps}"
    FLOW_NO_END = "Flow has no explicit end steps"
    FLOW_UNINTENTIONAL_CYCLES = "Flow may contain unintentional cycles"
    FLOW_UNREACHABLE_STEPS = "Unreachable steps: {steps}"

    # Business rule errors
    FLOW_TOO_MANY_STEPS = (
        "Flow has many steps ({count}), consider breaking into smaller flows"
    )
    ONBOARDING_MISSING_QUESTIONS = "ONBOARDING flow should include QUESTION steps"
    EMERGENCY_TIMEOUT_TOO_HIGH = (
        "EMERGENCY_PROTOCOL should have shorter timeout (< {max_timeout} min)"
    )
    FLOW_MISSING_ERROR_HANDLING = "Flow should include error handling steps"

    # Structure errors
    TEMPLATE_ID_REQUIRED = "Template ID is required"
    FLOW_TYPE_REQUIRED = "Flow type is required"
    TEMPLATE_VERSION_MISSING = "Template version not specified"
    TEMPLATE_VERSION_INVALID = "Invalid version format: {version}"
    TEMPLATE_STEPS_REQUIRED = "Template must have at least one step"
    TEMPLATE_TIMEOUT_INVALID = "Default timeout must be positive"
    TEMPLATE_TIMEOUT_TOO_HIGH = "Default timeout ({timeout}min) is very high"
    TEMPLATE_RETRIES_NEGATIVE = "Max retries cannot be negative"
    TEMPLATE_RETRIES_TOO_HIGH = "Max retries ({retries}) is very high"

    # Step order errors
    STEP_ORDER_INVALID = "Step order may cause execution issues"

    # Access control errors
    UNAUTHORIZED_ACCESS = (
        "User {user_id} not authorized to access template {template_id}"
    )

    @classmethod
    def format(cls, message: str, **kwargs) -> str:
        """
        Format an error message with provided kwargs.

        Args:
            message: Error message template
            **kwargs: Values to format into message

        Returns:
            Formatted error message
        """
        return message.format(**kwargs)


# ============================================================================
# BATCH PROCESSING CONSTANTS
# ============================================================================


class BatchProcessing:
    """Constants for batch processing operations."""

    MAX_BATCH_SIZE: Final[int] = 10
    """Maximum number of items to process in a single batch request"""

    # Async operation timeouts (seconds)
    BATCH_ITEM_TIMEOUT: Final[int] = 30
    """Timeout for processing a single batch item"""

    BATCH_TOTAL_TIMEOUT: Final[int] = 300
    """Total timeout for entire batch operation (5 minutes)"""


# ============================================================================
# EXPORT ALL CONSTANTS
# ============================================================================

__all__ = [
    "TemplateValidation",
    "TreatmentFlow",
    "FlowEngine",
    "BatchProcessing",
    "FlowErrorMessages",
]
