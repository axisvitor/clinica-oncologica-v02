"""
Flow Orchestrator - Utility Functions

Contains helper functions for flow orchestration operations.
"""

from datetime import datetime
from typing import Optional

from app.models.patient import Patient
from app.utils.date_helpers import _calculate_treatment_day


def calculate_treatment_day(
    patient: Patient, reference_date: Optional[datetime] = None, logger=None
) -> int:
    """
    Calculate current treatment day for patient.

    Args:
        patient: Patient model instance
        reference_date: Optional reference date for calculation
        logger: Optional logger instance for error logging

    Returns:
        int: Current treatment day (1-based), defaults to 1 on error
    """
    try:
        treatment_start = patient.enrollment_date or patient.created_at
        return _calculate_treatment_day(
            treatment_start_date=treatment_start,
            reference_date=reference_date,
            timezone=getattr(patient, "timezone", "America/Sao_Paulo"),
        )
    except Exception as e:
        if logger:
            logger.error(
                f"Error calculating treatment day for patient {patient.id}: {e}"
            )
        return 1  # Safe default
