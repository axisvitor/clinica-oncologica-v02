"""
FlowDispatcher - Enrollment routing facade for the canonical flow system.

This module provides a thin facade that routes patient flow enrollment to
the production flow system (flow_core.py / EnhancedFlowEngine / PatientFlowService).

Design:
    - ONLY handles enrollment routing (initialize_flow, is_new_patient).
    - Does NOT wrap advance_flow, pause, resume, or other operations -- those
      continue going directly to production services (EnhancedFlowEngine,
      FlowManagementService).
    - Uses lazy imports inside methods to avoid circular import issues
      (same pattern as service_provider.py).
    - Feature flags read from FlowFeatureFlags (patient-type routing only).

Canonical System:
    Production: flow_core.py / EnhancedFlowEngine / PatientFlowService
    (59 external call sites, day-based SQLAlchemy PatientFlowState model)
"""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.models.flow import PatientFlowState
    from app.models.patient import Patient

logger = logging.getLogger(__name__)


class FlowDispatcher:
    """
    Enrollment routing facade for patient flow initialization.

    Routes new patient enrollments to the canonical production flow system
    (PatientFlowService -> EnhancedFlowEngine -> flow_core.py).

    This dispatcher is intentionally narrow in scope: it covers only the
    enrollment path. All other flow operations (advance, pause, resume,
    complete) are called directly on the production services.

    Usage:
        dispatcher = FlowDispatcher(db)
        flow_state = await dispatcher.initialize_flow(patient, user_id)
    """

    def __init__(self, db: "Session"):
        """
        Initialize the FlowDispatcher with a database session.

        Args:
            db: SQLAlchemy Session for this request.
        """
        self.db = db

    def _get_feature_flags(self):
        """Lazily load FlowFeatureFlags to avoid circular imports."""
        from app.services.flow.config import FlowFeatureFlags
        return FlowFeatureFlags()

    async def initialize_flow(
        self,
        patient: "Patient",
        current_user_id: Optional[UUID] = None,
        auto_commit: bool = True,
    ) -> "Optional[PatientFlowState]":
        """
        Initialize the default flow for a patient.

        Delegates to PatientFlowService.initialize_default_flow() in the
        canonical production flow system.

        Args:
            patient: The Patient ORM instance to enroll.
            current_user_id: UUID of the user triggering the enrollment (for audit).
            auto_commit: If True (default), commits the transaction immediately.

        Returns:
            PatientFlowState if enrollment succeeded, None otherwise.
        """
        flags = self._get_feature_flags()

        if flags.log_dispatcher_routing:
            logger.info(
                "FlowDispatcher.initialize_flow: routing patient_id=%s to canonical "
                "production system (PatientFlowService) | canonical_system=%s | "
                "route_new=%s | route_existing=%s",
                getattr(patient, "id", "<unknown>"),
                flags.canonical_system,
                flags.route_new_patients_to_canonical,
                flags.route_existing_patients_to_canonical,
            )

        # Delegate to the canonical production service.
        # Lazy import to avoid circular dependency (same pattern as service_provider.py).
        from app.services.patient.flow_service import PatientFlowService

        service = PatientFlowService(self.db)
        return await service.initialize_default_flow(
            patient=patient,
            current_user_id=current_user_id,
            auto_commit=auto_commit,
        )

    def is_new_patient(self, patient_id: UUID) -> bool:
        """
        Check if a patient has no active flow state (is effectively new to flows).

        Uses FlowStateRepository to check for any active PatientFlowState record
        for the given patient_id.

        Args:
            patient_id: UUID of the patient to check.

        Returns:
            True if no active flow state exists for this patient, False otherwise.
        """
        # Lazy import to avoid circular dependency.
        from app.repositories.flow import FlowStateRepository

        repo = FlowStateRepository(self.db)
        active_flow = repo.get_active_flow(patient_id)
        is_new = active_flow is None

        flags = self._get_feature_flags()
        if flags.log_dispatcher_routing:
            logger.info(
                "FlowDispatcher.is_new_patient: patient_id=%s is_new=%s",
                patient_id,
                is_new,
            )

        return is_new
