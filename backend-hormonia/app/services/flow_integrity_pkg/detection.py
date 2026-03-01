"""Flow integrity detection and validation mixin."""

import hashlib
import logging
from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from app.exceptions import ValidationError
from app.models.flow import PatientFlowState
from app.models.message import Message
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class FlowIntegrityDetectionMixin:
    """Detection and validation methods for flow integrity."""

    async def validate_flow_consistency(self, flow_state: PatientFlowState) -> None:
        """
        Validate flow state consistency and referential integrity.

        Args:
            flow_state: Flow state to validate

        Raises:
            ValidationError: If validation fails
        """
        try:
            patient = self.patient_repo.get(flow_state.patient_id)
            if not patient:
                raise ValidationError(
                    f"Patient {flow_state.patient_id} not found for flow state"
                )

            if not self._validate_flow_type_compatibility(
                flow_state.flow_type, patient.treatment_type
            ):
                raise ValidationError(
                    f"Flow type {flow_state.flow_type} incompatible with treatment {patient.treatment_type}"
                )

            await self._validate_state_transitions(flow_state)

            if flow_state.current_step < 0:
                raise ValidationError("Flow step cannot be negative")

            if flow_state.current_step > self._get_max_step_for_flow(flow_state.flow_type):
                raise ValidationError(
                    f"Flow step {flow_state.current_step} exceeds maximum for {flow_state.flow_type}"
                )

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
        """
        Validate flow type is compatible with patient treatment.

        Args:
            flow_type: Flow type to validate
            treatment_type: Patient's treatment type

        Returns:
            bool: True if compatible
        """
        if not treatment_type:
            return True

        compatibility_matrix = {
            "hormone_therapy": ["onboarding", "daily_follow_up", "quiz_mensal"],
            "chemotherapy": ["onboarding", "daily_follow_up", "quiz_mensal"],
            "radiation": ["onboarding", "daily_follow_up"],
            "immunotherapy": ["onboarding", "quiz_mensal"],
            "surgery": ["onboarding", "daily_follow_up"],
        }

        compatible_flows = compatibility_matrix.get(treatment_type.lower(), [])
        return flow_type in compatible_flows

    async def _validate_state_transitions(self, flow_state: PatientFlowState) -> None:
        """
        Validate state transitions are valid.

        Args:
            flow_state: Flow state to validate

        Raises:
            ValidationError: If transitions are invalid
        """
        try:
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

            valid_transitions = {
                "onboarding": ["daily_follow_up", "quiz_mensal", "completed"],
                "daily_follow_up": ["quiz_mensal", "completed"],
                "quiz_mensal": ["completed", "paused"],
                "paused": ["quiz_mensal", "completed"],
                "completed": [],
            }

            if previous_states:
                last_flow_type = previous_states[0].flow_type
                if flow_state.flow_type not in valid_transitions.get(last_flow_type, []):
                    if flow_state.flow_type != last_flow_type:
                        raise ValidationError(
                            f"Invalid transition from {last_flow_type} to {flow_state.flow_type}"
                        )

            active_flows = (
                self.db.query(PatientFlowState)
                .filter(
                    PatientFlowState.patient_id == flow_state.patient_id,
                    PatientFlowState.id != flow_state.id,
                    PatientFlowState.step_data["status"].astext != "completed",
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
        """
        Get maximum valid step for flow type.

        Args:
            flow_type: Flow type

        Returns:
            int: Maximum valid step
        """
        max_steps = {
            "onboarding": 15,
            "daily_follow_up": 30,
            "quiz_mensal": 365,
        }
        return max_steps.get(flow_type, 365)

    async def _validate_flow_data_integrity(self, flow_state: PatientFlowState) -> None:
        """
        Validate flow state data integrity.

        Args:
            flow_state: Flow state to validate

        Raises:
            ValidationError: If data integrity fails
        """
        try:
            state_data = flow_state.state_data or {}

            required_fields = ["status", "last_updated"]
            for field in required_fields:
                if field not in state_data:
                    logger.warning(f"Missing required field '{field}' in flow state data")

            if "last_updated" in state_data:
                try:
                    last_updated = datetime.fromisoformat(state_data["last_updated"])
                    if last_updated > now_sao_paulo():
                        raise ValidationError("Flow last_updated cannot be in the future")
                except ValueError:
                    raise ValidationError("Invalid last_updated timestamp format")

            if "last_message_sent" in state_data:
                message_data = state_data["last_message_sent"]
                if "message_id" in message_data:
                    message = (
                        self.db.query(Message)
                        .filter(Message.id == message_data["message_id"])
                        .first()
                    )
                    if not message:
                        raise ValidationError(
                            f"Referenced message {message_data['message_id']} not found"
                        )

            expected_checksum = self._generate_flow_checksum(flow_state)
            stored_checksum = state_data.get("integrity_checksum")

            if stored_checksum and stored_checksum != expected_checksum:
                logger.warning(
                    f"Flow data integrity checksum mismatch for flow {flow_state.id}"
                )
                state_data["integrity_checksum"] = expected_checksum
                state_data["checksum_updated"] = now_sao_paulo().isoformat()
                self.db.commit()

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Flow data integrity validation error: {e}")
            raise

    def _generate_flow_checksum(self, flow_state: PatientFlowState) -> str:
        """
        Generate integrity checksum for flow state.

        Args:
            flow_state: Flow state to generate checksum for

        Returns:
            str: Checksum string
        """
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

            checksum_string = "|".join(f"{k}:{v}" for k, v in sorted(checksum_data.items()))
            return hashlib.sha256(checksum_string.encode("utf-8")).hexdigest()

        except Exception as e:
            logger.error(f"Flow checksum generation failed: {e}")
            return ""

    async def prevent_invalid_transitions(
        self, patient_id: UUID, new_flow_type: str
    ) -> None:
        """
        Prevent invalid workflow transitions.

        Args:
            patient_id: Patient UUID
            new_flow_type: New flow type to validate

        Raises:
            ValidationError: If transition is invalid
        """
        try:
            current_flow = self.flow_state_repo.get_active_flow(patient_id)

            if current_flow and current_flow.flow_type != new_flow_type:
                valid_transitions = {
                    "onboarding": ["daily_follow_up", "quiz_mensal"],
                    "daily_follow_up": ["quiz_mensal"],
                    "quiz_mensal": [],
                    "paused": ["quiz_mensal"],
                    "completed": [],
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
        """
        Validate all referential integrity constraints.

        Args:
            flow_state: Flow state to validate

        Returns:
            List[str]: List of integrity issues found
        """
        issues = []

        try:
            patient = self.patient_repo.get(flow_state.patient_id)
            if not patient:
                issues.append(f"Patient {flow_state.patient_id} not found")

            if flow_state.state_data:
                state_data = flow_state.state_data

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

                for msg_id in message_refs:
                    try:
                        message = self.db.query(Message).filter(Message.id == msg_id).first()
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
