"""
Patient Services Package.

This package contains specialized services for patient management,
following Single Responsibility Principle (SRP).

Structure:
- crud_service.py: Basic CRUD operations
- flow_service.py: Flow lifecycle management
- integrity_service.py: Facade for validation, sync, and audit (backward compatibility)
- validation_service.py: Data validation logic
- sync_service.py: Synchronization and consistency
- audit_service.py: Audit and integrity tracking
- onboarding_factory.py: Factory for creating onboarding coordinators

Main exports are specialized service classes for patient operations.
"""

from __future__ import annotations

from app.services.patient.audit_service import PatientAuditService
from app.services.patient.crud_service import PatientCRUDService
from app.services.patient.flow_service import PatientFlowService
from app.services.patient.integrity_service import PatientIntegrityService
from app.services.patient.onboarding_factory import get_onboarding_coordinator
from app.services.patient.sync_service import PatientSyncService
from app.services.patient.validation_service import PatientValidationService

__all__ = [
    "PatientCRUDService",
    "PatientFlowService",
    "PatientIntegrityService",
    "PatientValidationService",
    "PatientSyncService",
    "PatientAuditService",
    "get_onboarding_coordinator",
]
