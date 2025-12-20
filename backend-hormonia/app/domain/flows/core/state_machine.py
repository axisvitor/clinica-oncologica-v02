"""
Flow State Machine and Validation Module.
Handles state transitions, validation, and referential integrity for patient flows.
"""

import hashlib
import logging
from typing import List, Optional
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.flow import PatientFlowState
from app.models.message import Message
from app.repositories.patient import PatientRepository
from app.repositories.flow import FlowStateRepository
from app.exceptions import ValidationError

logger = logging.getLogger(__name__)


class FlowIntegrityService:
    """Service for flow consistency validation and referential integrity"""

    def __init__(self, db: Session):
        self.db = db
        self.flow_state_repo = FlowStateRepository(db)
        self.patient_repo = PatientRepository(db)

    async def validate_flow_consistency(self, flow_state: PatientFlowState) -> None:
        """Validate flow state consistency and referential integrity"""
        try:
            # Check patient existence
            patient = self.patient_repo.get(flow_state.patient_id)
            if not patient:
                raise ValidationError(
                    f"Patient {flow_state.patient_id} not found for flow state"
                )

            # Validate flow type against patient treatment
            if not self._validate_flow_type_compatibility(
                flow_state.flow_type, patient.treatment_type
            ):
                raise ValidationError(
                    f"Flow type {flow_state.flow_type} incompatible with treatment {patient.treatment_type}"
                )

            # Check flow state transitions
            await self._validate_state_transitions(flow_state)

            # Validate current step bounds
            if flow_state.current_step < 0:
                raise ValidationError("Flow step cannot be negative")

            if flow_state.current_step > self._get_max_step_for_flow(
                flow_state.flow_type
            ):
                raise ValidationError(
                    f"Flow step {flow_state.current_step} exceeds maximum for {flow_state.flow_type}"
                )

            # Validate flow data integrity
            if flow_state.state_data:
                await self._validate_flow_data_integrity(flow_state)

            logger.info(
                f"Flow consistency validation passed for patient {flow_state.patient_id}"
            )

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Flow consistency validation error: {e}")
            raise ValidationError(f"Flow validation failed: {str(e)}")

    def _validate_flow_type_compatibility(
        self, flow_type: str, treatment_type: Optional[str]
    ) -> bool:
        """Validate flow type is compatible with patient treatment"""
        if not treatment_type:
            return True  # Allow any flow if no treatment specified

        # Define treatment-flow compatibility matrix
        compatibility_matrix = {
            "hormone_therapy": ["initial_15_days", "days_16_45", "monthly_recurring"],
            "chemotherapy": ["initial_15_days", "days_16_45", "monthly_recurring"],
            "radiation": ["initial_15_days", "days_16_45"],
            "immunotherapy": ["initial_15_days", "monthly_recurring"],
            "surgery": ["initial_15_days", "days_16_45"],
        }

        compatible_flows = compatibility_matrix.get(treatment_type.lower(), [])
        return flow_type in compatible_flows

    async def _validate_state_transitions(self, flow_state: PatientFlowState) -> None:
        """Validate state transitions are valid"""
        try:
            # Get previous flow states for this patient
            previous_states = (
                self.db.query(PatientFlowState)
                .filter(
                    PatientFlowState.patient_id == flow_state.patient_id,
                    PatientFlowState.created_at < flow_state.created_at,
                )
                .order_by(PatientFlowState.created_at.desc())
                .limit(5)
                .all()
            )

            # Define valid transitions
            valid_transitions = {
                "initial_15_days": ["days_16_45", "monthly_recurring", "completed"],
                "days_16_45": ["monthly_recurring", "completed"],
                "monthly_recurring": ["completed", "paused"],
                "paused": ["monthly_recurring", "completed"],
                "completed": [],  # No transitions from completed
            }

            if previous_states:
                last_flow_type = previous_states[0].flow_type
                if flow_state.flow_type not in valid_transitions.get(
                    last_flow_type, []
                ):
                    # Allow same flow type (continuation)
                    if flow_state.flow_type != last_flow_type:
                        raise ValidationError(
                            f"Invalid transition from {last_flow_type} to {flow_state.flow_type}"
                        )

            # Check for duplicate active flows
            active_flows = (
                self.db.query(PatientFlowState)
                .filter(
                    PatientFlowState.patient_id == flow_state.patient_id,
                    PatientFlowState.id != flow_state.id,
                    PatientFlowState.state_data["status"].astext != "completed",
                )
                .count()
            )

            if active_flows > 0 and flow_state.state_data.get("status") != "completed":
                logger.warning(
                    f"Multiple active flows detected for patient {flow_state.patient_id}"
                )

        except Exception as e:
            logger.error(f"State transition validation error: {e}")
            raise

    def _get_max_step_for_flow(self, flow_type: str) -> int:
        """Get maximum valid step for flow type"""
        max_steps = {
            "initial_15_days": 15,
            "days_16_45": 30,  # 16-45 is 30 days
            "monthly_recurring": 365,  # Up to a year
        }
        return max_steps.get(flow_type, 365)

    async def _validate_flow_data_integrity(self, flow_state: PatientFlowState) -> None:
        """Validate flow state data integrity"""
        try:
            state_data = flow_state.state_data or {}

            # Check required fields exist
            required_fields = ["status", "last_updated"]
            for field in required_fields:
                if field not in state_data:
                    logger.warning(
                        f"Missing required field '{field}' in flow state data"
                    )

            # Validate timestamp consistency
            if "last_updated" in state_data:
                try:
                    last_updated = datetime.fromisoformat(state_data["last_updated"])
                    if last_updated > datetime.now(timezone.utc):
                        raise ValidationError(
                            "Flow last_updated cannot be in the future"
                        )
                except ValueError:
                    raise ValidationError("Invalid last_updated timestamp format")

            # Validate message references
            if "last_message_sent" in state_data:
                message_data = state_data["last_message_sent"]
                if "message_id" in message_data:
                    # Verify message exists
                    message = (
                        self.db.query(Message)
                        .filter(Message.id == message_data["message_id"])
                        .first()
                    )
                    if not message:
                        raise ValidationError(
                            f"Referenced message {message_data['message_id']} not found"
                        )

            # Generate and validate checksum
            expected_checksum = self._generate_flow_checksum(flow_state)
            stored_checksum = state_data.get("integrity_checksum")

            if stored_checksum and stored_checksum != expected_checksum:
                logger.warning(
                    f"Flow data integrity checksum mismatch for flow {flow_state.id}"
                )
                # Update with correct checksum
                state_data["integrity_checksum"] = expected_checksum
                state_data["checksum_updated"] = datetime.now(timezone.utc).isoformat()
                self.db.commit()

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Flow data integrity validation error: {e}")
            raise

    def _generate_flow_checksum(self, flow_state: PatientFlowState) -> str:
        """Generate integrity checksum for flow state"""
        try:
            checksum_data = {
                "patient_id": str(flow_state.patient_id),
                "flow_type": flow_state.flow_type,
                "current_step": flow_state.current_step,
                "started_at": flow_state.started_at.isoformat()
                if flow_state.started_at
                else "",
                "status": flow_state.state_data.get("status", "")
                if flow_state.state_data
                else "",
            }

            checksum_string = "|".join(
                f"{k}:{v}" for k, v in sorted(checksum_data.items())
            )
            return hashlib.sha256(checksum_string.encode("utf-8")).hexdigest()

        except Exception as e:
            logger.error(f"Flow checksum generation failed: {e}")
            return ""

    async def prevent_invalid_transitions(
        self, patient_id: UUID, new_flow_type: str
    ) -> None:
        """Prevent invalid workflow transitions"""
        try:
            # Get current active flow
            current_flow = self.flow_state_repo.get_active_flow(patient_id)

            if current_flow and current_flow.flow_type != new_flow_type:
                # Check if transition is allowed
                valid_transitions = {
                    "initial_15_days": ["days_16_45", "monthly_recurring"],
                    "days_16_45": ["monthly_recurring"],
                    "monthly_recurring": [],  # Can only continue or complete
                    "paused": ["monthly_recurring"],  # Can resume
                    "completed": [],  # No transitions allowed
                }

                allowed = valid_transitions.get(current_flow.flow_type, [])
                if new_flow_type not in allowed:
                    raise ValidationError(
                        f"Invalid flow transition: {current_flow.flow_type} -> {new_flow_type}"
                    )

            logger.info(
                f"Flow transition validated for patient {patient_id}: {new_flow_type}"
            )

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Flow transition validation error: {e}")
            raise ValidationError(f"Flow transition validation failed: {str(e)}")

    async def validate_referential_integrity(
        self, flow_state: PatientFlowState
    ) -> List[str]:
        """Validate all referential integrity constraints"""
        issues = []

        try:
            # Check patient reference
            patient = self.patient_repo.get(flow_state.patient_id)
            if not patient:
                issues.append(f"Patient {flow_state.patient_id} not found")

            # Check message references in state data
            if flow_state.state_data:
                state_data = flow_state.state_data

                # Check message references
                message_refs = []
                if (
                    "last_message_sent" in state_data
                    and "message_id" in state_data["last_message_sent"]
                ):
                    message_refs.append(state_data["last_message_sent"]["message_id"])

                if "message_status_updates" in state_data:
                    for update in state_data["message_status_updates"]:
                        if "message_id" in update:
                            message_refs.append(update["message_id"])

                # Validate message references exist
                for msg_id in message_refs:
                    try:
                        message = (
                            self.db.query(Message).filter(Message.id == msg_id).first()
                        )
                        if not message:
                            issues.append(f"Referenced message {msg_id} not found")
                        elif message.patient_id != flow_state.patient_id:
                            issues.append(
                                f"Message {msg_id} belongs to different patient"
                            )
                    except Exception as e:
                        issues.append(f"Error validating message {msg_id}: {e}")

            if issues:
                logger.warning(f"Referential integrity issues found: {issues}")
            else:
                logger.info(
                    f"Referential integrity validation passed for flow {flow_state.id}"
                )

            return issues

        except Exception as e:
            logger.error(f"Referential integrity validation error: {e}")
            return [f"Validation error: {str(e)}"]
