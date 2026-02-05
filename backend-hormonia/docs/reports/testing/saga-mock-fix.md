# Saga Mock Fix for Patient Creation Tests

## Problem

The `mock_saga_patient` fixture in `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/api/critical/conftest.py` was not properly intercepting patient creation, causing tests to hang.

### Root Cause

The patient creation route (`app/api/v2/routers/patients/crud.py` line 360) imports `get_onboarding_coordinator` **at runtime** inside the endpoint function:

```python
@router.post("/")
async def create_patient(...):
    # Import happens HERE at runtime, not at module load time
    from app.services.patient.onboarding_factory import get_onboarding_coordinator

    coordinator = get_onboarding_coordinator(db, saga_orchestrator)
    created = await coordinator.create_patient(...)
```

### Why Previous Approach Failed

**Attempt 1: monkeypatch.setattr()**
```python
monkeypatch.setattr(
    "app.api.v2.routers.patients.crud.get_onboarding_coordinator",
    mock_get_coordinator
)
```
❌ **Failed**: The import happens inside the function, so patching the crud module doesn't work - the function doesn't exist in that module's namespace until runtime.

**Attempt 2: FastAPI dependency_overrides**
```python
app_instance.dependency_overrides[get_onboarding_coordinator] = mock_get_coordinator
```
❌ **Failed**: `get_onboarding_coordinator` is not a FastAPI dependency (not used with `Depends()`), it's a plain function call.

## Solution

Use `unittest.mock.patch` to patch the function **at its source module**:

```python
from unittest.mock import patch

patcher = patch(
    "app.services.patient.onboarding_factory.get_onboarding_coordinator",
    side_effect=mock_get_coordinator
)
patcher.start()

yield {...}

patcher.stop()
```

✅ **Success**: This patches the function in the module where it's defined (`app.services.patient.onboarding_factory`), so when the route imports it at runtime, it gets our mock.

## Key Principles

1. **Patch where the function is defined**, not where it's imported
2. **Use `unittest.mock.patch`** for runtime imports, not `monkeypatch.setattr()`
3. **Use `dependency_overrides`** only for FastAPI dependencies (functions used with `Depends()`)

## Testing

Run the test to verify the mock works:

```bash
pytest tests/api/critical/test_patients_crud.py::TestPatientCRUD::test_create_patient_success -v
```

Expected output should show:
- `🔧 MOCK: get_onboarding_coordinator called (returning mock)`
- `🎯 MOCK: create_patient called with name=...`
- Test passes with 201 status

## Files Modified

- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/api/critical/conftest.py`
  - Changed `mock_saga_patient` fixture to use `unittest.mock.patch`
  - Added debug print statements to verify mock is being used
  - Removed monkeypatch approach
