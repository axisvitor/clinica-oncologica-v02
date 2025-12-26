# Patient CRUD Quick Fix Guide

**Priority 0 Fixes - Do These First (7 hours total)**

---

## 🔴 FIX #1: Test Fixture Invalid Parameter (5 minutes)

**Bug:** Test fixture uses `is_active=True` but Patient model doesn't have this field

**Location:** `tests/api/critical/conftest.py:293`

**Fix:**
```python
# File: tests/api/critical/conftest.py
# Around line 293

# BEFORE:
patient_data = {
    "name": "Test Patient",
    "cpf": "12345678901",
    "is_active": True,  # ❌ REMOVE THIS LINE
    # ... other fields
}

# AFTER:
patient_data = {
    "name": "Test Patient",
    "cpf": "12345678901",
    # ✅ is_active removed - Patient model uses deleted_at for soft deletion
    # ... other fields
}
```

**Verify:**
```bash
pytest tests/api/critical/test_patients_crud.py::test_create_patient_success -v
```

---

## 🔴 FIX #2: CSV Import Rollback Bug (2 hours)

**Bug:** `db.rollback()` inside loop undoes ALL previous inserts, causing data loss

**Location:** `app/api/v2/routers/patients/import_export.py:486-497`

**Current Code (BROKEN):**
```python
for row in rows:
    try:
        patient = await create_patient(row, db)
        success_count += 1
    except Exception as e:
        await db.rollback()  # ❌ THIS UNDOES ALL PREVIOUS INSERTS!
        errors.append({"row": row, "error": str(e)})
```

**Fixed Code:**
```python
from sqlalchemy.exc import SQLAlchemyError

for row in rows:
    # Create a savepoint for this row only
    savepoint = await db.begin_nested()
    try:
        patient = await create_patient(row, db)
        await savepoint.commit()  # ✅ Commit just this row
        success_count += 1
    except SQLAlchemyError as e:
        await savepoint.rollback()  # ✅ Rollback only this row
        errors.append({
            "row": row_num,
            "error": str(e),
            "data": {k: v for k, v in row.items() if k not in ["cpf", "email"]}
        })
        logger.error(f"CSV import row {row_num} failed: {e}")
```

**Complete Implementation:**
```python
@router.post("/import", response_model=BulkImportResponse)
async def import_patients_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Import patients from CSV with atomic per-row transactions"""

    if not file.filename.endswith('.csv'):
        raise HTTPException(400, "Only CSV files are accepted")

    success_count = 0
    errors = []

    content = await file.read()
    csv_data = content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(csv_data))

    for row_num, row in enumerate(reader, start=1):
        # Validate required fields
        required = ["name", "cpf", "date_of_birth", "phone"]
        missing = [f for f in required if not row.get(f)]
        if missing:
            errors.append({
                "row": row_num,
                "error": f"Missing required fields: {', '.join(missing)}"
            })
            continue

        # Create savepoint for atomic row processing
        savepoint = await db.begin_nested()

        try:
            # Create patient with validation
            patient_data = {
                "name": row["name"],
                "cpf": row["cpf"],
                "date_of_birth": datetime.strptime(row["date_of_birth"], "%Y-%m-%d").date(),
                "phone": row["phone"],
                "email": row.get("email"),
                "address": row.get("address"),
                "doctor_id": current_user.id
            }

            patient = await patient_crud_service.create(db, patient_data)
            await savepoint.commit()
            success_count += 1

        except IntegrityError as e:
            await savepoint.rollback()
            errors.append({
                "row": row_num,
                "error": "Duplicate patient (CPF already exists)"
            })
            logger.warning(f"CSV import row {row_num}: Duplicate CPF")

        except ValidationError as e:
            await savepoint.rollback()
            errors.append({
                "row": row_num,
                "error": f"Validation failed: {str(e)}"
            })
            logger.warning(f"CSV import row {row_num}: Validation error - {e}")

        except Exception as e:
            await savepoint.rollback()
            errors.append({
                "row": row_num,
                "error": f"Unexpected error: {str(e)}"
            })
            logger.error(f"CSV import row {row_num} failed: {e}", exc_info=True)

    # Commit the outer transaction (all successful savepoints)
    await db.commit()

    return BulkImportResponse(
        success_count=success_count,
        error_count=len(errors),
        errors=errors[:100]  # Limit error list size
    )
```

**Verify:**
```bash
# Create test CSV with intentional error in middle
pytest tests/api/v2/test_patient_import_atomicity.py -v
```

---

## 🔴 FIX #3: Missing Transaction Management (3 hours)

**Bug:** No transaction wrapper around multi-step saga operations

**Location:** `app/api/v2/routers/patients/crud.py:372-415`

**Step 1: Create Transaction Manager**

Create file: `app/utils/transaction_manager.py`
```python
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def transactional(db: AsyncSession, operation: str = "operation"):
    """
    Context manager for atomic database transactions

    Usage:
        async with transactional(db, "create_patient"):
            # Multiple DB operations here
            # All committed together or all rolled back
    """
    try:
        yield db
        await db.commit()
        logger.info(f"Transaction '{operation}' committed successfully")

    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Transaction '{operation}' rolled back: {e}")
        raise

    except Exception as e:
        await db.rollback()
        logger.error(f"Transaction '{operation}' failed: {e}")
        raise
```

**Step 2: Apply to Patient Creation**

```python
# File: app/api/v2/routers/patients/crud.py

from app.utils.transaction_manager import transactional

@router.post("/", response_model=PatientResponse, status_code=201)
async def create_patient(
    patient_data: PatientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """Create new patient with atomic saga orchestration"""

    # Wrap entire operation in transaction
    async with transactional(db, "create_patient_with_saga"):

        # Step 1: Create patient record
        patient = await patient_crud_service.create(
            db=db,
            patient_data=patient_data,
            doctor_id=current_user.id
        )

        # Step 2: Initialize onboarding saga
        saga = await onboarding_coordinator.start_onboarding(
            db=db,
            patient_id=patient.id
        )

        # Step 3: Trigger initial flow
        await flow_service.trigger_welcome_flow(
            db=db,
            patient_id=patient.id
        )

        # Step 4: Store idempotency key if provided
        if idempotency_key:
            await idempotency_service.store(
                key=idempotency_key,
                response=patient.id,
                ttl=86400
            )

        # Transaction commits here automatically
        # If any step fails, ALL steps rollback

    return patient
```

**Step 3: Apply to Patient Update**

```python
@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: UUID,
    patient_data: PatientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update patient with atomic transaction"""

    async with transactional(db, "update_patient"):
        # Verify patient exists and belongs to doctor
        patient = await patient_crud_service.get_by_id(db, patient_id)
        if not patient:
            raise HTTPException(404, "Patient not found")

        if patient.doctor_id != current_user.id and not current_user.is_admin:
            raise HTTPException(403, "Not authorized")

        # Update patient data
        updated_patient = await patient_crud_service.update(
            db=db,
            patient_id=patient_id,
            patient_data=patient_data
        )

        # Log audit trail
        await audit_service.log_update(
            db=db,
            patient_id=patient_id,
            user_id=current_user.id,
            changes=patient_data.dict(exclude_unset=True)
        )

    return updated_patient
```

**Verify:**
```bash
# Test that partial failures rollback everything
pytest tests/api/v2/test_patient_transaction_atomicity.py -v
```

---

## 🟠 FIX #4: Silent CPF Truncation (1 hour)

**Bug:** Invalid CPF is truncated instead of rejected

**Location:** `app/services/patient/integrity_service.py:282-288`

**Current Code (BROKEN):**
```python
def normalize_cpf(cpf: str) -> str:
    """Remove formatting from CPF"""
    cpf_clean = re.sub(r'\D', '', cpf)
    return cpf_clean[:11]  # ❌ Silently truncates to 11 chars!
```

**Fixed Code:**
```python
from app.core.exceptions import ValidationError

def normalize_cpf(cpf: str) -> str:
    """
    Normalize CPF by removing formatting and validating length

    Args:
        cpf: CPF string (may contain dots, hyphens)

    Returns:
        Clean CPF string with exactly 11 digits

    Raises:
        ValidationError: If CPF doesn't have exactly 11 digits
    """
    # Remove all non-digit characters
    cpf_clean = re.sub(r'\D', '', cpf)

    # Validate length
    if len(cpf_clean) != 11:
        raise ValidationError(
            f"Invalid CPF length: expected 11 digits, got {len(cpf_clean)}. "
            f"CPF must be exactly 11 digits (received: {cpf_clean})"
        )

    # Additional validation: check if all digits are the same
    if cpf_clean == cpf_clean[0] * 11:
        raise ValidationError(
            f"Invalid CPF: all digits are the same ({cpf_clean})"
        )

    return cpf_clean
```

**Also Update Validation:**
```python
def validate_cpf(cpf: str) -> bool:
    """
    Validate Brazilian CPF using verification digits

    Args:
        cpf: CPF string with 11 digits

    Returns:
        True if valid, False otherwise
    """
    # Normalize first (will raise if invalid length)
    try:
        cpf = normalize_cpf(cpf)
    except ValidationError:
        return False

    # Calculate first verification digit
    sum1 = sum(int(cpf[i]) * (10 - i) for i in range(9))
    digit1 = 11 - (sum1 % 11)
    if digit1 >= 10:
        digit1 = 0

    # Calculate second verification digit
    sum2 = sum(int(cpf[i]) * (11 - i) for i in range(10))
    digit2 = 11 - (sum2 % 11)
    if digit2 >= 10:
        digit2 = 0

    # Verify
    return int(cpf[9]) == digit1 and int(cpf[10]) == digit2
```

**Verify:**
```bash
pytest tests/services/test_cpf_validation.py -v
```

---

## Testing After Fixes

Run complete test suite:
```bash
# Run all patient tests
pytest tests/api/critical/test_patients_*.py -v

# Run integrity tests
pytest tests/services/test_patient_integrity.py -v

# Run import tests
pytest tests/api/v2/test_patient_import.py -v

# Full coverage report
pytest tests/ --cov=app/api/v2/routers/patients --cov-report=html
```

---

## Deployment Checklist

- [ ] Fix #1: Remove `is_active` from test fixture
- [ ] Fix #2: Implement savepoint-based CSV import
- [ ] Fix #3: Add `transactional` context manager to critical operations
- [ ] Fix #4: Fix CPF validation to raise errors
- [ ] Run full test suite
- [ ] Update API documentation
- [ ] Deploy to staging
- [ ] Run smoke tests in staging
- [ ] Deploy to production
- [ ] Monitor error rates for 24 hours

---

**Total Time: 7 hours**
**Impact: Fixes critical data loss bugs and test infrastructure**
**Priority: P0 - Do immediately**
