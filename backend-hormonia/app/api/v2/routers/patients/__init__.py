"""
Patients API v2 - Consolidated Router Module.

This module consolidates all patient-related endpoints into a single, well-organized router.
Previously scattered across 4 different files (patients.py, patients_flow.py,
patients_import.py, patients_integrity.py), all functionality is now organized into:

- crud.py: CRUD operations (list, get, create, update, delete)
- flow.py: Flow state management (activate, deactivate, archive, timeline, stats)
- import_export.py: CSV import/export operations
- integrity.py: Data validation and integrity operations (CPF, email checks)

All endpoints maintain backward compatibility with the previous API structure.
"""

# NOTE: Removed 'from __future__ import annotations' to fix Pydantic/FastAPI
# OpenAPI schema generation issues with Query() and Depends() parameters
from fastapi import APIRouter

from app.api.v2.routers.patients.crud import list_patients
from app.api.v2.routers.patients.crud import router as crud_router
from app.api.v2.routers.patients.flow import router as flow_router
from app.api.v2.routers.patients.import_export import router as import_export_router
from app.api.v2.routers.patients.integrity import router as integrity_router

# Create main patients router with explicit prefix to avoid "empty path" issues
router = APIRouter(prefix="")

# Include all sub-routers with explicit empty prefix
# All routes are prefixed with /patients in the main API v2 router
router.include_router(crud_router, prefix="", tags=["patients-crud"])
router.include_router(flow_router, prefix="", tags=["patients-flow"])
router.include_router(import_export_router, prefix="", tags=["patients-import-export"])
router.include_router(integrity_router, prefix="", tags=["patients-integrity"])

__all__ = [
    "router",
    "list_patients",
]
