"""
Patients API v2 - Consolidated Router Module

This module consolidates all patient-related endpoints into a single, well-organized router.
Previously scattered across 4 different files (patients.py, patients_flow.py,
patients_import.py, patients_integrity.py), all functionality is now organized into:

- crud.py: CRUD operations (list, get, create, update, delete)
- flow.py: Flow state management (activate, deactivate, archive, timeline, stats)
- import_export.py: CSV import/export operations
- integrity.py: Data validation and integrity operations (CPF, email checks)

All endpoints maintain backward compatibility with the previous API structure.
"""

from fastapi import APIRouter
from .crud import router as crud_router
from .flow import router as flow_router
from .import_export import router as import_export_router
from .integrity import router as integrity_router

# Create main patients router
router = APIRouter()

# Include all sub-routers
# All routes are prefixed with /patients in the main API v2 router
router.include_router(crud_router, tags=["patients-crud"])
router.include_router(flow_router, tags=["patients-flow"])
router.include_router(import_export_router, tags=["patients-import-export"])
router.include_router(integrity_router, tags=["patients-integrity"])

__all__ = ["router"]
