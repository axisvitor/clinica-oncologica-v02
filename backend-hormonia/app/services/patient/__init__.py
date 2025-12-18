"""
Patient Services Package

This package contains specialized services for patient management,
following Single Responsibility Principle (SRP).

Structure:
- crud_service.py: Basic CRUD operations
- onboarding_service.py: Patient creation with Saga Pattern
- flow_service.py: Flow lifecycle management
- integrity_service.py: Data validation and integrity

Main export is PatientService facade for backward compatibility.
"""
from app.services.patient.crud_service import PatientCRUDService

from app.services.patient.flow_service import PatientFlowService
from app.services.patient.integrity_service import PatientIntegrityService

__all__ = [
    "PatientCRUDService",
    "PatientFlowService",
    "PatientIntegrityService",
]
