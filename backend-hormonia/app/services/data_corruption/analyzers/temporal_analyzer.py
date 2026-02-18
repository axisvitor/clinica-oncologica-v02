"""
Temporal Analyzer
Analyzes temporal consistency and date-related corruption.
"""

import logging
from datetime import datetime, timezone
from .base import BaseAnalyzer
from ..types import CorruptionType
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class TemporalAnalyzer(BaseAnalyzer):
    """Analyzes temporal consistency"""

    async def analyze(self, data) -> list:
        """Not used - use specific methods instead"""
        return self.corruption_patterns

    async def analyze_patient_temporal(self, patient) -> None:
        """Analyze temporal consistency for patient data"""
        try:
            current_time = now_sao_paulo().date()

            # Check birth date
            if patient.birth_date:
                if patient.birth_date > current_time:
                    self._add_pattern(
                        type=CorruptionType.TEMPORAL_CORRUPTION,
                        field="patient.birth_date",
                        pattern="future_birth_date",
                        severity="high",
                        description="Birth date is in the future",
                        detection_method="temporal_validation",
                        examples=[f"Patient {patient.id}: {patient.birth_date}"],
                        confidence=0.95,
                    )

                # Check if birth date is too far in the past
                if (current_time - patient.birth_date).days > 120 * 365:
                    self._add_pattern(
                        type=CorruptionType.TEMPORAL_CORRUPTION,
                        field="patient.birth_date",
                        pattern="ancient_birth_date",
                        severity="medium",
                        description="Birth date is unrealistically old",
                        detection_method="temporal_validation",
                        examples=[f"Patient {patient.id}: {patient.birth_date}"],
                        confidence=0.8,
                    )

            # Check treatment start date
            if patient.treatment_start_date:
                if patient.treatment_start_date > current_time:
                    self._add_pattern(
                        type=CorruptionType.TEMPORAL_CORRUPTION,
                        field="patient.treatment_start_date",
                        pattern="future_treatment_date",
                        severity="medium",
                        description="Treatment start date is in the future",
                        detection_method="temporal_validation",
                        examples=[
                            f"Patient {patient.id}: {patient.treatment_start_date}"
                        ],
                        confidence=0.9,
                    )

                # Check if treatment started before birth
                if (
                    patient.birth_date
                    and patient.treatment_start_date < patient.birth_date
                ):
                    self._add_pattern(
                        type=CorruptionType.TEMPORAL_CORRUPTION,
                        field="patient.treatment_start_date",
                        pattern="treatment_before_birth",
                        severity="critical",
                        description="Treatment started before birth date",
                        detection_method="temporal_validation",
                        examples=[
                            f"Patient {patient.id}: Treatment {patient.treatment_start_date}, Birth {patient.birth_date}"
                        ],
                        confidence=1.0,
                    )

        except Exception as e:
            logger.error(
                f"Temporal consistency analysis failed for patient {patient.id}: {e}"
            )

    async def analyze_flow_temporal(self, flow) -> None:
        """Analyze temporal consistency for flow data"""
        try:
            current_time = now_sao_paulo()

            # Check if flow started in the future
            if flow.started_at and flow.started_at > current_time:
                self._add_pattern(
                    type=CorruptionType.TEMPORAL_CORRUPTION,
                    field="flow.started_at",
                    pattern="future_flow_start",
                    severity="high",
                    description="Flow started in the future",
                    detection_method="temporal_validation",
                    examples=[f"Flow {flow.id}: {flow.started_at}"],
                    confidence=0.95,
                )

            # Check step progression vs time
            if flow.started_at and flow.current_step > 0:
                days_since_start = (current_time - flow.started_at).days
                if flow.current_step > days_since_start + 10:
                    self._add_pattern(
                        type=CorruptionType.TEMPORAL_CORRUPTION,
                        field="flow.current_step",
                        pattern="impossible_step_progression",
                        severity="medium",
                        description="Flow step progression faster than possible",
                        detection_method="progression_analysis",
                        examples=[
                            f"Flow {flow.id}: Step {flow.current_step} in {days_since_start} days"
                        ],
                        confidence=0.8,
                    )

        except Exception as e:
            logger.error(f"Flow temporal analysis failed for flow {flow.id}: {e}")

    async def analyze_message_temporal(self, message) -> None:
        """Analyze temporal consistency for message data"""
        try:
            current_time = now_sao_paulo()

            # Check if message created in the future
            if message.created_at > current_time:
                self._add_pattern(
                    type=CorruptionType.TEMPORAL_CORRUPTION,
                    field="message.created_at",
                    pattern="future_message_creation",
                    severity="high",
                    description="Message created in the future",
                    detection_method="temporal_validation",
                    examples=[f"Message {message.id}: {message.created_at}"],
                    confidence=0.95,
                )

            # Check if scheduled_for is in the past but status is still pending
            if (
                message.scheduled_for
                and message.scheduled_for < current_time
                and hasattr(message, "status")
                and str(message.status) == "PENDING"
            ):
                time_diff = (current_time - message.scheduled_for).total_seconds()
                if time_diff > 3600:  # More than 1 hour overdue
                    self._add_pattern(
                        type=CorruptionType.TEMPORAL_CORRUPTION,
                        field="message.scheduled_for",
                        pattern="overdue_pending_message",
                        severity="medium",
                        description="Message scheduled in past but still pending",
                        detection_method="temporal_validation",
                        examples=[
                            f"Message {message.id}: Scheduled {message.scheduled_for}, still pending"
                        ],
                        confidence=0.7,
                    )

        except Exception as e:
            logger.error(
                f"Message temporal analysis failed for message {message.id}: {e}"
            )
