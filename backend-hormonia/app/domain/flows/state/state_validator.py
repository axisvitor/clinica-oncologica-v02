"""
State Validation Module - Flow State Validation Rules

Validates flow state transitions and ensures business rules are followed.
"""

import logging
from typing import Dict, Any, Optional, Tuple
from uuid import UUID

from app.models.flow import PatientFlowState
from app.models.patient import Patient


logger = logging.getLogger(__name__)


class FlowStateValidator:
    """
    Validates flow state transitions and conditions.

    Responsibilities:
    - Validate state transitions
    - Check business rules
    - Verify preconditions for operations
    """

    def __init__(self):
        """Initialize FlowStateValidator."""
        logger.info("FlowStateValidator initialized")

    def validate_flow_start(
        self,
        patient: Patient,
        existing_flow: Optional[PatientFlowState],
        flow_type: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate flow start conditions.

        Args:
            patient: Patient object
            existing_flow: Existing flow state if any
            flow_type: Requested flow type

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not patient:
            return False, "Patient not found"

        if existing_flow and existing_flow.state_data.get('status') != 'completed':
            return False, f"Patient already has active flow: {existing_flow.flow_type}"

        if not flow_type:
            return False, "Flow type is required"

        return True, None

    def validate_flow_advancement(
        self,
        current_day: int,
        target_day: int,
        force_advance: bool,
        flow_state: Optional[PatientFlowState]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate flow advancement conditions.

        Args:
            current_day: Current treatment day
            target_day: Target day to advance to
            force_advance: Whether to force advancement
            flow_state: Current flow state

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not flow_state:
            return False, "No active flow found"

        if flow_state.state_data.get('status') == 'paused':
            return False, "Flow is paused. Resume before advancing."

        if flow_state.state_data.get('status') == 'completed':
            return False, "Flow is already completed"

        if current_day >= target_day and not force_advance:
            return False, "Flow already at or past target day"

        return True, None

    def validate_flow_pause(
        self,
        flow_state: Optional[PatientFlowState]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate flow pause conditions.

        Args:
            flow_state: Current flow state

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not flow_state:
            return False, "No active flow found"

        if flow_state.state_data.get('status') == 'paused':
            return False, "Flow is already paused"

        if flow_state.state_data.get('status') == 'completed':
            return False, "Cannot pause completed flow"

        return True, None

    def validate_flow_resume(
        self,
        flow_state: Optional[PatientFlowState]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate flow resume conditions.

        Args:
            flow_state: Current flow state

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not flow_state:
            return False, "No flow found"

        if flow_state.state_data.get('status') != 'paused':
            return False, "Flow is not paused"

        return True, None

    def validate_flow_stop(
        self,
        flow_state: Optional[PatientFlowState]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate flow stop conditions.

        Args:
            flow_state: Current flow state

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not flow_state:
            return False, "No active flow found"

        if flow_state.state_data.get('status') == 'completed':
            return False, "Flow is already completed"

        return True, None

    def check_flow_type_transition_needed(
        self,
        current_flow_type: str,
        target_day: int,
        flow_type_calculator: callable
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if flow type transition is needed.

        Args:
            current_flow_type: Current flow type
            target_day: Target treatment day
            flow_type_calculator: Function to calculate flow type from day

        Returns:
            Tuple of (needs_transition, new_flow_type)
        """
        new_flow_type = flow_type_calculator(target_day)

        if new_flow_type != current_flow_type:
            return True, new_flow_type

        return False, None
