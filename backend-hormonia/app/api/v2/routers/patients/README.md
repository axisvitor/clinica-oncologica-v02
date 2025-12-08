# Patients Router - Consolidated Module

## Quick Navigation

### 📁 File Structure
```
patients/
├── __init__.py          - Router aggregator (START HERE)
├── base.py              - Shared utilities & schemas
├── crud.py              - CRUD operations (5 endpoints)
├── flow.py              - Flow management (5 endpoints)
├── import_export.py     - CSV operations (2 endpoints)
├── integrity.py         - Data validation (5 endpoints)
├── services/            - Business logic layer (future)
└── README.md            - This file
```

### 📚 Documentation
- [Full Migration Guide](../../../../docs/PATIENTS_ROUTER_CONSOLIDATION.md)
- [Architecture Documentation](../../../../docs/PATIENTS_ROUTER_STRUCTURE.md)
- [Quick Start Guide](../../../../docs/PATIENTS_MIGRATION_QUICKSTART.md)
- [Code Examples](../../../../docs/PATIENTS_CODE_EXAMPLES.md)

## Module Overview

### `__init__.py` - Entry Point
Single unified router that aggregates all patient endpoints.

**Usage:**
```python
from app.api.v2.routers.patients import router as patients_router
```

### `base.py` - Shared Foundation
Common utilities and schemas used across all patient modules.

**Contents:**
- 5 Pydantic models
- 11 utility functions
- 2 serialization functions

**Key Utilities:**
```python
from .base import (
    extract_user_context,      # Extract role & user_id
    ensure_uuid,                # Safe UUID conversion
    normalize_cpf,              # CPF normalization
    serialize_patient,          # Patient serialization
)
```

### `crud.py` - CRUD Operations
Core patient CRUD endpoints with advanced features.

**Endpoints:**
- `GET /` - List patients (paginated, filtered)
- `GET /{id}` - Get patient by ID
- `POST /` - Create patient (saga orchestration)
- `PATCH /{id}` - Update patient
- `DELETE /{id}` - Soft delete patient

**Features:**
- Cursor-based pagination
- Advanced filtering
- Field selection
- Eager loading
- Idempotency keys

### `flow.py` - Flow Management
Patient treatment flow state management.

**Endpoints:**
- `POST /{id}/activate` - Set flow_state to ACTIVE
- `POST /{id}/deactivate` - Set flow_state to PAUSED
- `POST /{id}/archive` - Set flow_state to CANCELLED
- `GET /{id}/timeline` - Get patient timeline
- `GET /stats` - Get patient statistics

**Flow States:**
- ONBOARDING → ACTIVE → PAUSED/COMPLETED/CANCELLED

### `import_export.py` - CSV Operations
Bulk import/export of patient data via CSV.

**Endpoints:**
- `GET /export` - Export patients to CSV
- `POST /import` - Import patients from CSV

**Features:**
- Streaming responses
- Data validation
- Duplicate detection
- Redis caching
- Error reporting

### `integrity.py` - Data Validation
Data integrity validation and soft delete operations.

**Endpoints:**
- `POST /validate-cpf` - Validate CPF
- `GET /check-email` - Check email existence
- `DELETE /{id}` - Soft delete
- `POST /{id}/restore` - Restore deleted
- `GET /deleted` - List deleted (ADMIN)

**Features:**
- CPF validation
- Email uniqueness check
- Soft delete with audit
- Restore capability

## Quick Examples

### Import the Router
```python
# Single unified import
from app.api.v2.routers.patients import router

# Use in main router
api_v2_router.include_router(router, prefix="/patients", tags=["patients"])
```

### Use Shared Utilities
```python
from app.api.v2.routers.patients.base import (
    extract_user_context,
    ensure_uuid,
    serialize_patient,
)

# Extract user context
role, user_id = extract_user_context(current_user)

# Safe UUID conversion
patient_uuid = ensure_uuid(patient_id)

# Serialize patient model
patient_dict = serialize_patient(patient_model)
```

### Add Custom Endpoint
```python
# In crud.py
@router.get("/{patient_id}/custom")
async def custom_endpoint(patient_id: str, db = Depends(get_db)):
    patient_uuid = ensure_uuid(patient_id)
    # Your logic here
    return {"message": "Custom endpoint"}
```

## API Endpoints Summary

| Module | Endpoints | Rate Limit |
|--------|-----------|------------|
| CRUD | 5 | 20-120/min |
| Flow | 5 | 30-60/min |
| Import/Export | 2 | 5-10/hour |
| Integrity | 5 | 10-60/min |
| **Total** | **22** | - |

## Features

- ✅ 22 RESTful endpoints
- ✅ RBAC with Permission system
- ✅ Rate limiting
- ✅ Cursor-based pagination
- ✅ Field selection & eager loading
- ✅ Idempotency keys
- ✅ Saga orchestration
- ✅ CSV import/export
- ✅ Flow state management
- ✅ Soft delete with audit
- ✅ Redis caching
- ✅ Complete type hints
- ✅ Comprehensive documentation

## Architecture

```
Request → Router Aggregator → Specific Router → Shared Utils → Service → Repository → Database
         (__init__.py)        (crud/flow/etc)    (base.py)     (future)
```

## Dependencies

**Required:**
- FastAPI
- SQLAlchemy
- Pydantic
- Redis (for caching)

**Services Used:**
- PatientRepository
- PatientCRUDService
- PatientIntegrityService
- PatientFlowService
- SagaOrchestrator

## Testing

```bash
# Run all patient tests
pytest tests/api/v2/test_patients*.py -v

# Run specific module tests
pytest tests/api/v2/routers/patients/ -v
```

## Contributing

When adding new endpoints:

1. Choose the appropriate module (crud/flow/import_export/integrity)
2. Use shared utilities from `base.py`
3. Add type hints
4. Add docstrings
5. Apply rate limiting
6. Enforce RBAC
7. Update this README

## Migration

Migrating from old structure? See:
- [Quick Start Guide](../../../../docs/PATIENTS_MIGRATION_QUICKSTART.md) - 5 minutes
- [Full Guide](../../../../docs/PATIENTS_ROUTER_CONSOLIDATION.md) - Complete details

## Support

- Documentation: `/docs` directory
- Code Examples: `PATIENTS_CODE_EXAMPLES.md`
- Architecture: `PATIENTS_ROUTER_STRUCTURE.md`

---

**Version:** 1.0.0
**Status:** ✅ Production Ready
**Backward Compatible:** Yes
**Last Updated:** 2025-11-30
