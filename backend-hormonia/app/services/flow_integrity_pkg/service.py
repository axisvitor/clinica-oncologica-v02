"""Composed flow integrity service."""

import logging
from typing import Any

from app.repositories.flow import FlowStateRepository
from app.repositories.patient import PatientRepository

from .detection import FlowIntegrityDetectionMixin
from .recovery import FlowIntegrityRecoveryMixin

logger = logging.getLogger(__name__)


class FlowIntegrityService(
    FlowIntegrityDetectionMixin,
    FlowIntegrityRecoveryMixin,
):
    """Service for flow consistency validation and referential integrity checking."""

    def __init__(self, db: Any):
        self.db = db
        self.flow_state_repo = FlowStateRepository(db)
        self.patient_repo = PatientRepository(db)
        logger.info("Flow Integrity Service initialized")


def get_flow_integrity_service(db: Any) -> FlowIntegrityService:
    """Get flow integrity service instance."""
    return FlowIntegrityService(db)
