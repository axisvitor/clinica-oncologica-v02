# LGPD Developer Quick Reference Guide

**Last Updated:** 2025-11-26
**For:** Backend Developers working with Patient data

## 🚀 Quick Start

### Using Encrypted Email/Phone in Patient Creation

```python
from app.models.patient import Patient
from app.services.lgpd_encryption_service import get_lgpd_encryption_service

# Create patient with automatic encryption
patient = Patient(
    name="João Silva",
    doctor_id=doctor_uuid,
    birth_date=date(1990, 1, 1)
)

# Set email (automatically encrypted)
patient.set_email("joao@example.com")

# Set phone (automatically encrypted)
patient.set_phone("+5511999999999")

# Save to database
db.add(patient)
await db.commit()

# Read encrypted values
email = patient.email_decrypted  # "joao@example.com"
phone = patient.phone_decrypted  # "+5511999999999"
```

### Searching by Email/Phone (Hash-based)

```python
from app.services.lgpd_encryption_service import get_lgpd_encryption_service
from app.models.patient import Patient

service = get_lgpd_encryption_service()

# Generate search hash
email_hash = service.hash_email_for_search("joao@example.com")

# Query by hash (fast, indexed)
patient = await db.query(Patient).filter(
    Patient.email_hash == email_hash,
    Patient.doctor_id == doctor_id,
    Patient.deleted_at.is_(None)
).first()
```

### Hard Delete (Right to be Forgotten)

```python
from app.repositories.patient import PatientRepository

repo = PatientRepository(db)

# LGPD Art. 16 - Right to deletion
deleted = await repo.hard_delete(
    patient_id=patient_uuid,
    audit_reason="LGPD Art. 16 - Patient requested data deletion via email on 2025-11-26"
)

if deleted:
    logger.info(f"Patient {patient_uuid} permanently deleted per LGPD compliance")
```

## 📋 Common Patterns

### Pattern 1: Create Patient with Full Encryption

```python
async def create_patient_lgpd_compliant(
    name: str,
    email: str,
    phone: str,
    cpf: str,
    doctor_id: UUID,
    db: Session
) -> Patient:
    """Create patient with all PII encrypted."""

    patient = Patient(
        name=name,
        doctor_id=doctor_id
    )

    # Encrypt all PII fields
    patient.set_email(email)
    patient.set_phone(phone)
    patient.set_cpf(cpf)

    db.add(patient)
    await db.commit()
    await db.refresh(patient)

    return patient
```

### Pattern 2: Update Patient Email/Phone

```python
async def update_patient_contact(
    patient: Patient,
    new_email: Optional[str] = None,
    new_phone: Optional[str] = None,
    db: Session = None
) -> Patient:
    """Update patient contact info with automatic re-encryption."""

    if new_email:
        patient.set_email(new_email)

    if new_phone:
        patient.set_phone(new_phone)

    await db.commit()
    await db.refresh(patient)

    return patient
```

### Pattern 3: Search with Case-Insensitive Email

```python
from app.services.lgpd_encryption_service import get_lgpd_encryption_service

async def find_patient_by_email(
    email: str,
    doctor_id: UUID,
    db: Session
) -> Optional[Patient]:
    """Find patient by email (case-insensitive, encrypted)."""

    service = get_lgpd_encryption_service()

    # Hash is case-insensitive (automatically lowercased)
    email_hash = service.hash_email_for_search(email)

    return await db.query(Patient).filter(
        Patient.email_hash == email_hash,
        Patient.doctor_id == doctor_id,
        Patient.deleted_at.is_(None)
    ).first()
```

### Pattern 4: Batch Update for Migration

```python
async def migrate_plaintext_to_encrypted(db: Session):
    """Migrate existing plaintext emails/phones to encrypted format."""

    from app.services.lgpd_encryption_service import get_lgpd_encryption_service

    service = get_lgpd_encryption_service()

    # Get patients without encrypted data
    patients = await db.query(Patient).filter(
        Patient.email_encrypted.is_(None),
        Patient.email.isnot(None)
    ).all()

    for patient in patients:
        # Encrypt email if exists
        if patient.email and not patient.email_encrypted:
            encrypted, hash_val = service.encrypt_email(patient.email)
            patient.email_encrypted = encrypted
            patient.email_hash = hash_val

        # Encrypt phone if exists
        if patient.phone and not patient.phone_encrypted:
            encrypted, hash_val = service.encrypt_phone(patient.phone)
            patient.phone_encrypted = encrypted
            patient.phone_hash = hash_val

    await db.commit()
    logger.info(f"Migrated {len(patients)} patients to encrypted storage")
```

## 🔍 Debugging & Troubleshooting

### Check if Data is Encrypted

```python
def is_encrypted(patient: Patient) -> dict:
    """Check encryption status of patient data."""
    return {
        "cpf_encrypted": patient.cpf_encrypted is not None,
        "email_encrypted": patient.email_encrypted is not None,
        "phone_encrypted": patient.phone_encrypted is not None,
        "cpf_hash": patient.cpf_hash is not None,
        "email_hash": patient.email_hash is not None,
        "phone_hash": patient.phone_hash is not None,
    }
```

### Verify Decryption Works

```python
async def verify_patient_encryption(patient_id: UUID, db: Session):
    """Verify encryption/decryption for a patient."""

    patient = await db.get(Patient, patient_id)

    if not patient:
        return {"error": "Patient not found"}

    return {
        "patient_id": str(patient.id),
        "email": {
            "plaintext": patient.email,
            "encrypted": patient.email_encrypted is not None,
            "hash": patient.email_hash,
            "decrypted": patient.email_decrypted,
            "matches": patient.email == patient.email_decrypted if patient.email else None
        },
        "phone": {
            "plaintext": patient.phone,
            "encrypted": patient.phone_encrypted is not None,
            "hash": patient.phone_hash,
            "decrypted": patient.phone_decrypted,
            "matches": patient.phone == patient.phone_decrypted if patient.phone else None
        }
    }
```

### Test Hash Consistency

```python
def test_hash_consistency():
    """Verify hash is deterministic and case-insensitive."""
    from app.services.lgpd_encryption_service import get_lgpd_encryption_service

    service = get_lgpd_encryption_service()

    # Test email hashing
    hash1 = service.hash_email_for_search("TEST@EXAMPLE.COM")
    hash2 = service.hash_email_for_search("test@example.com")
    hash3 = service.hash_email_for_search("  Test@Example.Com  ")

    assert hash1 == hash2 == hash3, "Email hashes should be case-insensitive"

    # Test phone hashing
    hash1 = service.hash_phone_for_search("+55 11 99999-9999")
    hash2 = service.hash_phone_for_search("+5511999999999")
    hash3 = service.hash_phone_for_search("(11) 99999-9999")

    # Note: Phone hashing removes formatting
    print(f"Phone hash 1: {hash1}")
    print(f"Phone hash 2: {hash2}")
    print(f"Phone hash 3: {hash3}")
```

## ⚠️ Common Mistakes

### ❌ Don't: Direct assignment to encrypted fields

```python
# WRONG - Bypasses encryption
patient.email_encrypted = b"some bytes"
patient.email_hash = "some hash"
```

### ✅ Do: Use setter methods

```python
# CORRECT - Automatic encryption
patient.set_email("user@example.com")
```

### ❌ Don't: Search by plaintext when encrypted

```python
# WRONG - Won't find encrypted emails
patient = db.query(Patient).filter(
    Patient.email == "user@example.com"  # Plaintext comparison
).first()
```

### ✅ Do: Search by hash

```python
# CORRECT - Hash-based search
from app.services.lgpd_encryption_service import get_lgpd_encryption_service

service = get_lgpd_encryption_service()
email_hash = service.hash_email_for_search("user@example.com")

patient = db.query(Patient).filter(
    Patient.email_hash == email_hash
).first()
```

### ❌ Don't: Hard delete without audit reason

```python
# WRONG - Missing audit reason
await repo.hard_delete(patient_id)  # Raises ValueError
```

### ✅ Do: Provide detailed audit reason

```python
# CORRECT - Clear audit trail
await repo.hard_delete(
    patient_id,
    audit_reason="LGPD Art. 16 - Patient data deletion request received via email on 2025-11-26 16:30 UTC. Request ID: REQ-12345"
)
```

## 📊 Performance Tips

### Tip 1: Use Indexes for Hash Searches

```python
# Fast - Uses ix_patients_email_hash index
patient = db.query(Patient).filter(
    Patient.email_hash == hash_value
).first()

# Also fast - Uses ix_patients_email_hash_doctor composite index
patient = db.query(Patient).filter(
    Patient.email_hash == hash_value,
    Patient.doctor_id == doctor_id
).first()
```

### Tip 2: Avoid Decrypting in Loops

```python
# SLOW - Decrypts every patient
patients = db.query(Patient).all()
for patient in patients:
    email = patient.email_decrypted  # Decrypt operation

# BETTER - Only decrypt when needed
patients = db.query(Patient).all()
selected_patient = select_patient_somehow(patients)
email = selected_patient.email_decrypted  # Single decrypt
```

### Tip 3: Batch Operations for Migration

```python
# Efficient batch migration
BATCH_SIZE = 100

offset = 0
while True:
    batch = db.query(Patient).filter(
        Patient.email_encrypted.is_(None)
    ).offset(offset).limit(BATCH_SIZE).all()

    if not batch:
        break

    for patient in batch:
        patient.set_email(patient.email)

    db.commit()
    offset += BATCH_SIZE
```

## 🔐 Security Best Practices

### 1. Never Log Decrypted PII

```python
# ❌ WRONG - Logs sensitive data
logger.info(f"Patient email: {patient.email_decrypted}")

# ✅ CORRECT - Logs only hash
logger.info(f"Patient email hash: {patient.email_hash[:16]}...")
```

### 2. Mask PII in API Responses

```python
from app.services.lgpd_encryption_service import get_lgpd_encryption_service

def patient_to_api_response(patient: Patient) -> dict:
    """Convert patient to API response with masked PII."""

    service = get_lgpd_encryption_service()

    return {
        "id": str(patient.id),
        "name": patient.name,
        "email": mask_email(patient.email_decrypted),  # user@example.com -> u***@example.com
        "phone": mask_phone(patient.phone_decrypted),  # +5511999999999 -> +55119****9999
        "cpf": service.format_cpf_for_display(patient.cpf_decrypted, mask=True),
    }

def mask_email(email: str) -> str:
    """Mask email for display."""
    if not email or '@' not in email:
        return email

    local, domain = email.split('@', 1)
    if len(local) <= 2:
        return f"{local[0]}***@{domain}"
    return f"{local[0]}***{local[-1]}@{domain}"

def mask_phone(phone: str) -> str:
    """Mask phone for display."""
    if not phone:
        return phone

    if len(phone) > 8:
        return f"{phone[:6]}****{phone[-4:]}"
    return phone
```

### 3. Require Audit Reasons for Sensitive Operations

```python
async def delete_patient_with_approval(
    patient_id: UUID,
    requesting_user_id: UUID,
    approval_document: str,
    db: Session
) -> bool:
    """Delete patient with documented approval."""

    # Build comprehensive audit reason
    audit_reason = (
        f"LGPD Art. 16 - Patient data deletion request. "
        f"Requested by user: {requesting_user_id}. "
        f"Approval document: {approval_document}. "
        f"Timestamp: {datetime.utcnow().isoformat()}"
    )

    repo = PatientRepository(db)
    return await repo.hard_delete(patient_id, audit_reason=audit_reason)
```

## 📚 Related Documentation

- **Full Implementation Guide:** `/docs/LGPD_IMPLEMENTATION_SUMMARY.md`
- **Encryption Service:** `/app/services/lgpd_encryption_service.py`
- **Middleware:** `/app/middleware/lgpd_middleware.py`
- **Patient Model:** `/app/models/patient.py`
- **Patient Repository:** `/app/repositories/patient.py`
- **Migrations:** `/alembic/versions/027_*.py` and `/alembic/versions/028_*.py`

## 🧪 Testing

Run verification script:

```bash
python scripts/verify_lgpd_implementation.py
```

Run unit tests:

```bash
pytest tests/test_lgpd_encryption.py -v
pytest tests/test_patient_hard_delete.py -v
```

## 💡 Need Help?

1. **Technical Issues:** Check `/docs/LGPD_IMPLEMENTATION_SUMMARY.md`
2. **LGPD Compliance:** Contact Legal/Compliance team
3. **Security Questions:** Contact InfoSec team
4. **Implementation Questions:** Backend development team

---

**Remember:** LGPD compliance is not just about encryption - it's about respecting user privacy and data rights. Always prioritize patient data protection.
