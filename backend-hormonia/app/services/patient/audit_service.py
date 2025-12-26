"""
PatientAuditService - Patient audit and integrity tracking.

Handles:
- Integrity hash generation
- Audit logging
- Data integrity verification

File: backend-hormonia/app/services/patient/audit_service.py
LOC: ~80
Responsibility: Audit and integrity tracking
Pattern: Single Responsibility
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class PatientAuditService:
    """
    Service for patient audit and integrity tracking.

    Responsibilities:
    - Generate integrity hashes
    - Track data changes
    - Provide audit trail
    """

    def __init__(self):
        """Initialize audit service."""
        self._logger = logging.getLogger(__name__)

    def generate_patient_hash(self, patient_data: Dict[str, Any]) -> str:
        """
        Generate integrity hash for patient data.

        Creates a SHA256 hash from critical patient fields to ensure
        data integrity and detect unauthorized changes.

        Args:
            patient_data: Patient data dictionary

        Returns:
            SHA256 hash string
        """
        try:
            # Create hash from critical fields
            hash_fields = {
                "phone": patient_data.get("phone", ""),
                "name": patient_data.get("name", ""),
                "email": patient_data.get("email", ""),
                "cpf": patient_data.get("patient_data", {}).get("cpf", "")
                if patient_data.get("patient_data")
                else "",
            }

            # Sort fields for consistent hashing
            hash_string = "|".join(f"{k}:{v}" for k, v in sorted(hash_fields.items()))

            return hashlib.sha256(hash_string.encode("utf-8")).hexdigest()

        except Exception as e:
            self._logger.error(f"Hash generation failed: {e}")
            return ""

    def verify_data_integrity(
        self, patient_data: Dict[str, Any], expected_hash: str
    ) -> bool:
        """
        Verify patient data integrity against hash.

        Args:
            patient_data: Patient data to verify
            expected_hash: Expected hash value

        Returns:
            True if hash matches, False otherwise
        """
        try:
            current_hash = self.generate_patient_hash(patient_data)
            return current_hash == expected_hash
        except Exception as e:
            self._logger.error(f"Integrity verification failed: {e}")
            return False

    def log_data_change(
        self,
        patient_id: str,
        field_name: str,
        old_value: Any,
        new_value: Any,
        changed_by: str,
    ) -> None:
        """
        Log patient data change for audit trail.

        Args:
            patient_id: Patient identifier
            field_name: Field that changed
            old_value: Previous value
            new_value: New value
            changed_by: User who made the change
        """
        self._logger.info(
            f"Patient data change: patient_id={patient_id}, "
            f"field={field_name}, "
            f"old={old_value}, "
            f"new={new_value}, "
            f"changed_by={changed_by}"
        )
