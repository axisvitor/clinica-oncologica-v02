# CPF Repository Migration Guide

## Overview

This guide shows how to update repository methods to use encrypted CPF fields instead of plaintext CPF.

## Required Changes

### 1. Update PatientRepository.get_by_cpf()

**Location**: `app/repositories/patient.py`

**Before** (Plaintext Search):
```python
def get_by_cpf(self, cpf: str) -> Optional[Patient]:
    """Get patient by CPF (only active patients)"""
    return self.db.query(Patient).filter(
        Patient.cpf == cpf,
        Patient.deleted_at.is_(None)
    ).first()
```

**After** (Encrypted Search):
```python
def get_by_cpf(self, cpf: str, doctor_id: Optional[UUID] = None) -> Optional[Patient]:
    """
    Get patient by CPF using encrypted search.

    Args:
        cpf: CPF to search (with or without formatting)
        doctor_id: Optional doctor filter for tenant isolation

    Returns:
        Patient or None
    """
    from app.services.cpf_encryption_service import get_cpf_encryption_service

    # Generate searchable hash
    service = get_cpf_encryption_service()
    cpf_hash = service.hash_cpf_for_search(cpf)

    if not cpf_hash:
        return None

    # Query using hash
    query = self.db.query(Patient).filter(
        Patient.cpf_hash == cpf_hash,
        Patient.deleted_at.is_(None)
    )

    # Add doctor filter for tenant isolation
    if doctor_id:
        query = query.filter(Patient.doctor_id == doctor_id)

    return query.first()
```

### 2. Update Search Methods

**Before**:
```python
def search_active(self, search_term: str, skip: int = 0, limit: int = 100) -> List[Patient]:
    """Search active patients by name, email, or phone"""
    search_pattern = f"%{search_term}%"
    return self.db.query(Patient).filter(
        Patient.deleted_at.is_(None)
    ).filter(
        (Patient.name.ilike(search_pattern)) |
        (Patient.email.ilike(search_pattern)) |
        (Patient.phone.ilike(search_pattern))
    ).offset(skip).limit(limit).all()
```

**After** (Add CPF Search):
```python
def search_active(self, search_term: str, skip: int = 0, limit: int = 100) -> List[Patient]:
    """
    Search active patients by name, email, phone, or CPF.

    Note: CPF search uses hash matching for exact matches only.
    """
    from app.services.cpf_encryption_service import get_cpf_encryption_service

    search_pattern = f"%{search_term}%"

    # Try to parse search_term as CPF
    service = get_cpf_encryption_service()
    cpf_hash = service.hash_cpf_for_search(search_term)

    query = self.db.query(Patient).filter(Patient.deleted_at.is_(None))

    # Build search conditions
    conditions = [
        Patient.name.ilike(search_pattern),
        Patient.email.ilike(search_pattern),
        Patient.phone.ilike(search_pattern)
    ]

    # Add CPF hash condition if valid CPF format
    if cpf_hash:
        conditions.append(Patient.cpf_hash == cpf_hash)

    return query.filter(or_(*conditions)).offset(skip).limit(limit).all()
```

### 3. Update Duplicate Detection

**Before**:
```python
def check_duplicate_cpf(self, cpf: str, doctor_id: UUID, exclude_id: Optional[UUID] = None) -> bool:
    """Check if CPF already exists for this doctor"""
    query = self.db.query(Patient).filter(
        Patient.cpf == cpf,
        Patient.doctor_id == doctor_id,
        Patient.deleted_at.is_(None)
    )

    if exclude_id:
        query = query.filter(Patient.id != exclude_id)

    return query.first() is not None
```

**After**:
```python
def check_duplicate_cpf(self, cpf: str, doctor_id: UUID, exclude_id: Optional[UUID] = None) -> bool:
    """
    Check if CPF already exists for this doctor using encrypted search.

    Args:
        cpf: CPF to check (with or without formatting)
        doctor_id: Doctor ID for tenant isolation
        exclude_id: Patient ID to exclude from check (for updates)

    Returns:
        True if duplicate exists, False otherwise
    """
    from app.services.cpf_encryption_service import get_cpf_encryption_service

    if not cpf:
        return False

    # Generate hash for search
    service = get_cpf_encryption_service()
    cpf_hash = service.hash_cpf_for_search(cpf)

    if not cpf_hash:
        return False

    # Query using hash
    query = self.db.query(Patient).filter(
        Patient.cpf_hash == cpf_hash,
        Patient.doctor_id == doctor_id,
        Patient.deleted_at.is_(None)
    )

    if exclude_id:
        query = query.filter(Patient.id != exclude_id)

    return query.first() is not None
```

### 4. Update Filters in list_v2()

**Location**: `app/repositories/patient.py` - `list_v2()` method

Find the search filter section and update:

**Before**:
```python
# Search (Name or Email)
if filters.get("search"):
    search_val = f"%{filters['search']}%"
    criteria.append(
        or_(
            Patient.name.ilike(search_val),
            Patient.email.ilike(search_val)
        )
    )
```

**After**:
```python
# Search (Name, Email, or CPF)
if filters.get("search"):
    from app.services.cpf_encryption_service import get_cpf_encryption_service

    search_val = f"%{filters['search']}%"
    search_conditions = [
        Patient.name.ilike(search_val),
        Patient.email.ilike(search_val)
    ]

    # Try to parse as CPF and add hash condition
    service = get_cpf_encryption_service()
    cpf_hash = service.hash_cpf_for_search(filters['search'])
    if cpf_hash:
        search_conditions.append(Patient.cpf_hash == cpf_hash)

    criteria.append(or_(*search_conditions))
```

## Service Layer Updates

### 1. Update Patient Creation

**Location**: `app/services/patient/crud_service.py`

**Before**:
```python
def create_patient(self, patient_data: PatientCreate, doctor_id: UUID) -> Patient:
    patient = Patient(
        name=patient_data.name,
        phone=patient_data.phone,
        cpf=patient_data.cpf,  # Plaintext storage
        doctor_id=doctor_id
    )
    self.db.add(patient)
    self.db.commit()
    return patient
```

**After**:
```python
def create_patient(self, patient_data: PatientCreate, doctor_id: UUID) -> Patient:
    patient = Patient(
        name=patient_data.name,
        phone=patient_data.phone,
        doctor_id=doctor_id
    )

    # Set CPF with automatic encryption
    if patient_data.cpf:
        patient.set_cpf(patient_data.cpf)

    self.db.add(patient)
    self.db.commit()
    self.db.refresh(patient)
    return patient
```

### 2. Update Patient Updates

**Before**:
```python
def update_patient(self, patient_id: UUID, patient_data: PatientUpdate) -> Optional[Patient]:
    patient = self.repo.get_by_id(patient_id)
    if not patient:
        return None

    if patient_data.cpf is not None:
        patient.cpf = patient_data.cpf  # Plaintext update

    self.db.commit()
    return patient
```

**After**:
```python
def update_patient(self, patient_id: UUID, patient_data: PatientUpdate) -> Optional[Patient]:
    patient = self.repo.get_by_id(patient_id)
    if not patient:
        return None

    # Update CPF with automatic encryption
    if patient_data.cpf is not None:
        patient.set_cpf(patient_data.cpf)

    self.db.commit()
    self.db.refresh(patient)
    return patient
```

## API Router Updates

### Update Patient Response Serialization

**Location**: `app/api/v2/patients_utils.py`

**Before**:
```python
def _serialize_patient(patient: Patient) -> dict:
    return {
        "id": str(patient.id),
        "name": patient.name,
        "cpf": patient.cpf,  # Plaintext response
        "email": patient.email,
        # ...
    }
```

**After**:
```python
def _serialize_patient(patient: Patient, mask_cpf: bool = False) -> dict:
    """
    Serialize patient for API response.

    Args:
        patient: Patient model instance
        mask_cpf: If True, mask CPF for privacy (***.***.789-**)

    Returns:
        Serialized patient dictionary
    """
    # Get decrypted CPF (transparent decryption)
    cpf_value = patient.cpf_decrypted

    # Format for display
    if cpf_value:
        cpf_display = patient.get_cpf_display(mask=mask_cpf)
    else:
        cpf_display = None

    return {
        "id": str(patient.id),
        "name": patient.name,
        "cpf": cpf_display,  # Formatted/masked CPF
        "email": patient.email,
        # ...
    }
```

### Optional: Add CPF Masking Endpoint

```python
@router.get("/{patient_id}/cpf/masked")
@require_permission(Permission.PATIENT_READ_SENSITIVE)
async def get_patient_cpf_masked(
    patient_id: str,
    db = Depends(get_db),
    current_user = Depends(get_current_user_from_session)
):
    """Get patient CPF in masked format for sensitive data access"""
    patient_uuid = UUID(patient_id)
    repo = PatientRepository(db)
    patient = repo.get_by_id(patient_uuid)

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    _ensure_patient_access(current_user, patient.doctor_id)

    return {
        "patient_id": str(patient.id),
        "cpf_masked": patient.get_cpf_display(mask=True),  # ***.***.789-**
        "cpf_full": patient.get_cpf_display(mask=False)  # Only if user has permission
    }
```

## Schema Updates

### Update Pydantic Schemas

**Location**: `app/schemas/patient.py`

Add CPF validator:

```python
from pydantic import BaseModel, validator
from typing import Optional

class PatientCreate(BaseModel):
    name: str
    phone: str
    cpf: Optional[str] = None
    email: Optional[str] = None

    @validator('cpf')
    def validate_cpf_format(cls, v):
        """Validate CPF format before storage"""
        if v:
            from app.services.cpf_encryption_service import get_cpf_encryption_service
            service = get_cpf_encryption_service()

            # Normalize
            normalized = service._normalize_cpf(v)

            # Validate
            if not service._validate_cpf_format(normalized):
                raise ValueError(
                    "Invalid CPF format. Must be 11 digits or formatted as XXX.XXX.XXX-XX"
                )

            # Return normalized (will be encrypted on storage)
            return normalized

        return v
```

## Complete Repository Update Example

Here's a complete updated repository method incorporating all changes:

```python
# app/repositories/patient.py

from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.patient import Patient
from app.services.cpf_encryption_service import get_cpf_encryption_service


class PatientRepository:
    """Patient repository with encrypted CPF support"""

    def __init__(self, db: Session):
        self.db = db
        self.cpf_service = get_cpf_encryption_service()

    def get_by_cpf(
        self,
        cpf: str,
        doctor_id: Optional[UUID] = None
    ) -> Optional[Patient]:
        """
        Get patient by CPF using encrypted search.

        Args:
            cpf: CPF to search (normalized or formatted)
            doctor_id: Optional doctor filter

        Returns:
            Patient or None
        """
        cpf_hash = self.cpf_service.hash_cpf_for_search(cpf)
        if not cpf_hash:
            return None

        query = self.db.query(Patient).filter(
            Patient.cpf_hash == cpf_hash,
            Patient.deleted_at.is_(None)
        )

        if doctor_id:
            query = query.filter(Patient.doctor_id == doctor_id)

        return query.first()

    def check_cpf_exists(
        self,
        cpf: str,
        doctor_id: UUID,
        exclude_patient_id: Optional[UUID] = None
    ) -> bool:
        """
        Check if CPF exists for doctor.

        Args:
            cpf: CPF to check
            doctor_id: Doctor ID for tenant isolation
            exclude_patient_id: Patient ID to exclude (for updates)

        Returns:
            True if exists, False otherwise
        """
        cpf_hash = self.cpf_service.hash_cpf_for_search(cpf)
        if not cpf_hash:
            return False

        query = self.db.query(Patient).filter(
            Patient.cpf_hash == cpf_hash,
            Patient.doctor_id == doctor_id,
            Patient.deleted_at.is_(None)
        )

        if exclude_patient_id:
            query = query.filter(Patient.id != exclude_patient_id)

        return query.first() is not None

    def search_patients(
        self,
        search_term: str,
        doctor_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Patient]:
        """
        Search patients by name, email, phone, or CPF.

        Args:
            search_term: Search term
            doctor_id: Optional doctor filter
            skip: Pagination offset
            limit: Max results

        Returns:
            List of matching patients
        """
        # Build search conditions
        search_pattern = f"%{search_term}%"
        conditions = [
            Patient.name.ilike(search_pattern),
            Patient.email.ilike(search_pattern),
            Patient.phone.ilike(search_pattern)
        ]

        # Try CPF search
        cpf_hash = self.cpf_service.hash_cpf_for_search(search_term)
        if cpf_hash:
            conditions.append(Patient.cpf_hash == cpf_hash)

        # Build query
        query = self.db.query(Patient).filter(
            Patient.deleted_at.is_(None),
            or_(*conditions)
        )

        if doctor_id:
            query = query.filter(Patient.doctor_id == doctor_id)

        return query.offset(skip).limit(limit).all()
```

## Testing the Migration

### 1. Test Encryption Works

```python
from app.database import SessionLocal
from app.models.patient import Patient
from uuid import uuid4

db = SessionLocal()

# Create patient with encrypted CPF
patient = Patient(
    name="Test Patient",
    phone="+5511999999999",
    doctor_id=uuid4()
)
patient.set_cpf("123.456.789-01")

db.add(patient)
db.commit()

# Verify encryption
print(f"CPF Encrypted: {patient.cpf_encrypted is not None}")
print(f"CPF Hash: {patient.cpf_hash is not None}")
print(f"CPF Plaintext: {patient.cpf}")  # Should be None
print(f"CPF Decrypted: {patient.cpf_decrypted}")  # Should be "12345678901"

db.close()
```

### 2. Test Search Works

```python
from app.repositories.patient import PatientRepository
from app.database import SessionLocal

db = SessionLocal()
repo = PatientRepository(db)

# Search by CPF (with formatting)
patient = repo.get_by_cpf("123.456.789-01")
print(f"Found: {patient.name if patient else 'Not found'}")

# Search by CPF (without formatting)
patient = repo.get_by_cpf("12345678901")
print(f"Found: {patient.name if patient else 'Not found'}")

db.close()
```

### 3. Test Duplicate Detection

```python
from app.repositories.patient import PatientRepository
from app.database import SessionLocal
from uuid import uuid4

db = SessionLocal()
repo = PatientRepository(db)

doctor_id = uuid4()

# Check if CPF exists
exists = repo.check_cpf_exists("123.456.789-01", doctor_id)
print(f"CPF exists: {exists}")

db.close()
```

## Performance Considerations

### Index Strategy

Ensure indexes exist:
```sql
-- Check index on cpf_hash
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'patients'
AND indexname LIKE '%cpf%';

-- Should show:
-- ix_patients_cpf_hash
-- ix_patients_cpf_hash_doctor
```

### Query Optimization

```python
# BAD: N+1 query problem
patients = db.query(Patient).all()
for p in patients:
    print(p.cpf_decrypted)  # Decrypts individually

# GOOD: Batch processing
patients = db.query(Patient).all()
cpf_list = [p.cpf_decrypted for p in patients]  # Still N decryptions but minimized
```

### Caching Strategy (Optional)

```python
from functools import lru_cache

class PatientRepository:
    @lru_cache(maxsize=1000)
    def _get_cpf_hash(self, cpf: str) -> Optional[str]:
        """Cache CPF hashes to avoid recomputation"""
        return self.cpf_service.hash_cpf_for_search(cpf)
```

## Rollback Procedure

If issues occur, rollback the migration:

```bash
# Rollback migration
alembic downgrade -1

# Verify plaintext CPF restored
python -c "
from app.database import SessionLocal
from app.models.patient import Patient

db = SessionLocal()
count = db.query(Patient).filter(Patient.cpf.isnot(None)).count()
print(f'Patients with plaintext CPF: {count}')
db.close()
"
```

## Checklist

- [ ] Update `PatientRepository.get_by_cpf()` to use hash
- [ ] Update `PatientRepository.search_active()` to include CPF
- [ ] Update `PatientRepository.check_duplicate_cpf()` to use hash
- [ ] Update `PatientRepository.list_v2()` filters
- [ ] Update patient creation in CRUD service
- [ ] Update patient updates in CRUD service
- [ ] Update API response serialization
- [ ] Add CPF validator to Pydantic schemas
- [ ] Test encryption/decryption
- [ ] Test search functionality
- [ ] Test duplicate detection
- [ ] Verify performance with indexes
- [ ] Update integration tests
- [ ] Update API documentation
