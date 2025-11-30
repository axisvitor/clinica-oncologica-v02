# Patients Router - Code Examples

## 📚 Import Examples

### New Consolidated Import
```python
# Single unified router
from app.api.v2.routers.patients import router as patients_router

api_v2_router.include_router(
    patients_router,
    prefix="/patients",
    tags=["patients"]
)
```

### Individual Module Imports (Alternative)
```python
# Import specific sub-routers if needed
from app.api.v2.routers.patients.crud import router as crud_router
from app.api.v2.routers.patients.flow import router as flow_router
from app.api.v2.routers.patients.import_export import router as import_router
from app.api.v2.routers.patients.integrity import router as integrity_router
```

### Utility Imports
```python
# Import shared utilities
from app.api.v2.routers.patients.base import (
    extract_user_context,
    ensure_uuid,
    normalize_cpf,
    normalize_phone,
    serialize_patient,
    serialize_patient_with_includes,
)
```

## 🎯 Using Shared Utilities

### User Context Extraction
```python
from app.api.v2.routers.patients.base import extract_user_context, is_admin

@router.get("/custom-endpoint")
async def custom_endpoint(current_user = Depends(get_current_user_from_session)):
    role_enum, user_id = extract_user_context(current_user)

    if is_admin(current_user):
        # Admin-only logic
        pass
    else:
        # Regular user logic
        pass
```

### UUID Conversion
```python
from app.api.v2.routers.patients.base import ensure_uuid

@router.get("/{patient_id}")
async def get_patient(patient_id: str):
    patient_uuid = ensure_uuid(patient_id)
    if patient_uuid is None:
        raise HTTPException(status_code=400, detail="Invalid patient ID")

    # Use patient_uuid safely
    patient = repo.get_by_id(patient_uuid)
```

### Data Normalization
```python
from app.api.v2.routers.patients.base import normalize_cpf, normalize_phone

# Normalize CPF
cpf_input = "123.456.789-00"
normalized_cpf = normalize_cpf(cpf_input)  # "12345678900"

# Normalize phone
phone_input = "(11) 98765-4321"
normalized_phone = normalize_phone(phone_input)  # "11987654321"
```

### Patient Serialization
```python
from app.api.v2.routers.patients.base import serialize_patient, serialize_patient_with_includes

# Basic serialization
patient_dict = serialize_patient(patient_model)

# With eager-loaded relations
patient_dict = serialize_patient_with_includes(
    patient_model,
    include=["doctor", "quiz_sessions"]
)
```

## 🔧 Custom Endpoint Examples

### Adding a New CRUD Endpoint
```python
# app/api/v2/routers/patients/crud.py

@router.get(
    "/{patient_id}/summary",
    response_model=PatientSummaryResponse,
    summary="Get patient summary"
)
@require_permission(Permission.PATIENT_READ)
@limiter.limit("60/minute")
async def get_patient_summary(
    request: Request,
    patient_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Get comprehensive patient summary."""
    patient_uuid = ensure_uuid(patient_id)
    if not patient_uuid:
        raise HTTPException(status_code=400, detail="Invalid patient ID")

    repo = PatientRepository(db)
    patient = repo.get_by_id(patient_uuid, eager_load=True)

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    ensure_patient_access(current_user, patient.doctor_id)

    # Build summary
    summary = {
        "patient": serialize_patient(patient),
        "treatment_summary": get_treatment_summary(patient),
        "recent_activities": get_recent_activities(patient),
    }

    return summary
```

### Adding a Flow State Endpoint
```python
# app/api/v2/routers/patients/flow.py

@router.post(
    "/{patient_id}/complete",
    response_model=dict,
    summary="Mark patient treatment as completed"
)
@limiter.limit("30/hour")
async def complete_patient(
    request: Request,
    patient_id: str,
    completion_data: PatientCompletionData,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Complete patient treatment."""
    patient_uuid = ensure_uuid(patient_id)
    if not patient_uuid:
        raise HTTPException(status_code=400, detail="Invalid patient ID")

    repo = PatientRepository(db)
    patient = repo.get_by_id(patient_uuid)

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    ensure_patient_access(current_user, patient.doctor_id)

    # Use flow service
    flow_engine = get_enhanced_flow_engine(db)
    flow_service = PatientFlowService(db, flow_engine)

    updated_patient = await flow_service.complete_patient(
        patient_uuid,
        completion_data
    )

    invalidate_patient_cache(str(patient_uuid))
    return serialize_patient(updated_patient)
```

### Adding a Data Integrity Check
```python
# app/api/v2/routers/patients/integrity.py

@router.get(
    "/check-phone",
    response_model=PhoneCheckResponse,
    summary="Check if patient phone exists"
)
@limiter.limit("60/minute")
async def check_phone_exists(
    request: Request,
    phone: str = Query(..., description="Phone to validate"),
    db: Session = Depends(get_db),
):
    """Check if a patient phone already exists."""
    normalized = normalize_phone(phone)
    if not normalized:
        raise HTTPException(
            status_code=400,
            detail="Invalid phone format"
        )

    # Ensure E.164 format
    e164_phone = normalized if normalized.startswith('+') else f"+{normalized}"

    exists = (
        db.query(Patient)
        .filter(
            Patient.deleted_at.is_(None),
            Patient.phone == e164_phone,
        )
        .first()
        is not None
    )

    return PhoneCheckResponse(phone=e164_phone, exists=exists)
```

## 📊 Using Shared Schemas

### Creating Custom Request/Response Models
```python
# app/api/v2/routers/patients/base.py

class PatientSummaryResponse(BaseModel):
    """Response model for patient summary."""
    patient: PatientV2Response
    treatment_summary: Dict[str, Any]
    recent_activities: List[Dict[str, Any]]

class PatientCompletionData(BaseModel):
    """Request model for completing patient treatment."""
    completion_date: date
    final_notes: Optional[str] = None
    treatment_success: bool = True
```

### Using Existing Schemas
```python
from app.api.v2.routers.patients.base import (
    CPFValidationRequest,
    EmailCheckResponse,
    ImportResponse,
    PatientStatsResponse,
)

# Use in endpoint
@router.post("/validate-data")
async def validate_data(request: CPFValidationRequest):
    # CPF validation logic
    pass
```

## 🔐 RBAC Examples

### Permission-Based Access
```python
from app.core.authorization import require_permission
from app.core.permissions import Permission

@router.get("/sensitive-data")
@require_permission(Permission.PATIENT_READ)
async def get_sensitive_data(
    request: Request,
    current_user = Depends(get_current_user_from_session),
):
    """Endpoint requires PATIENT_READ permission."""
    pass
```

### Role-Based Access
```python
from app.api.v2.routers.patients.base import is_admin, extract_user_context

@router.get("/admin-only")
async def admin_only_endpoint(current_user = Depends(get_current_user_from_session)):
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")

    # Admin-only logic
    pass
```

### Patient Access Control
```python
from app.api.v2.routers.patients.base import ensure_patient_access

@router.get("/{patient_id}/details")
async def get_patient_details(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    patient_uuid = ensure_uuid(patient_id)
    patient = repo.get_by_id(patient_uuid)

    # This raises HTTPException if user lacks access
    ensure_patient_access(current_user, patient.doctor_id)

    # Proceed with logic
    pass
```

## 🎨 Pagination Examples

### Cursor-Based Pagination
```python
from app.api.v2.dependencies import get_pagination_params

@router.get("/")
async def list_items(
    pagination = Depends(get_pagination_params),
    db: Session = Depends(get_db),
):
    # Use pagination params
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    # Apply to query
    items, has_more, next_cursor, total = repo.list_v2(
        cursor_data=cursor_data,
        limit=limit,
    )

    return {
        "data": items,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
    }
```

### Field Selection
```python
from app.api.v2.dependencies import get_field_selection, apply_field_selection

@router.get("/")
async def list_items(
    fields: Optional[List[str]] = Depends(get_field_selection),
):
    items = get_all_items()

    # Apply field selection to each item
    response_items = []
    for item in items:
        item_dict = item.dict()
        if fields:
            item_dict = apply_field_selection(item_dict, fields)
        response_items.append(item_dict)

    return {"data": response_items}
```

## 🚀 Service Layer Integration (Future)

### Creating a Service
```python
# app/api/v2/routers/patients/services/patient_service.py

from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

class PatientService:
    """Patient business logic service."""

    def __init__(self, db: Session, repo: PatientRepository):
        self.db = db
        self.repo = repo

    async def create_patient_with_validation(
        self,
        patient_data: PatientCreate,
        doctor_id: UUID,
    ) -> Patient:
        """Create patient with comprehensive validation."""
        # Validation logic
        self._validate_cpf(patient_data.cpf)
        self._validate_phone(patient_data.phone)
        self._check_duplicates(patient_data)

        # Create patient
        patient = await self.repo.create(patient_data, doctor_id)

        # Post-creation tasks
        await self._send_welcome_message(patient)
        await self._create_initial_flow(patient)

        return patient

    def _validate_cpf(self, cpf: str) -> None:
        """Validate CPF format."""
        # Validation logic
        pass
```

### Using a Service
```python
# app/api/v2/routers/patients/crud.py

from .services.patient_service import PatientService

@router.post("/")
async def create_patient(
    patient_data: PatientV2Create,
    db: Session = Depends(get_db),
):
    # Initialize service
    repo = PatientRepository(db)
    service = PatientService(db, repo)

    # Use service
    patient = await service.create_patient_with_validation(
        patient_data,
        doctor_id
    )

    return serialize_patient(patient)
```

## 📝 Testing Examples

### Unit Test
```python
# tests/api/v2/routers/patients/test_crud.py

import pytest
from app.api.v2.routers.patients.crud import router

def test_list_patients(client, auth_headers):
    response = client.get("/api/v2/patients", headers=auth_headers)
    assert response.status_code == 200
    assert "data" in response.json()
    assert "next_cursor" in response.json()
```

### Integration Test
```python
# tests/integration/patients/test_patient_flow.py

def test_patient_creation_and_activation(client, db, auth_headers):
    # Create patient
    create_data = {
        "name": "Test Patient",
        "phone": "+5511987654321",
        "doctor_id": str(doctor_id),
    }
    response = client.post(
        "/api/v2/patients",
        json=create_data,
        headers=auth_headers
    )
    assert response.status_code == 201
    patient_id = response.json()["id"]

    # Activate patient
    response = client.post(
        f"/api/v2/patients/{patient_id}/activate",
        headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["flow_state"] == "active"
```

---

**Last Updated:** 2025-11-30
**Status:** ✅ Production Ready
