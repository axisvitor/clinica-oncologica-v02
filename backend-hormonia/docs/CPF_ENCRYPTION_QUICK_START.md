# CPF Encryption - Quick Start Guide

## 🚀 5-Minute Setup

### Prerequisites
- Python 3.11+
- PostgreSQL database
- Alembic configured
- Access to environment variables

## Step 1: Generate Encryption Keys (2 minutes)

```bash
# Generate PHI encryption key
python -c 'import secrets; print("PHI_ENCRYPTION_KEY=" + secrets.token_hex(32))'

# Generate hash salt
python -c 'import secrets; print("HASH_SALT=" + secrets.token_hex(32))'
```

Add to `.env`:
```bash
PHI_ENCRYPTION_KEY=<generated-key-from-above>
HASH_SALT=<generated-salt-from-above>
```

## Step 2: Run Database Migration (1 minute)

```bash
# Backup database first (IMPORTANT!)
pg_dump -U postgres -d hormonia > backup_before_cpf_encryption.sql

# Run migration
alembic upgrade head
```

## Step 3: Verify Installation (2 minutes)

```python
# test_encryption.py
from app.services.cpf_encryption_service import get_cpf_encryption_service

service = get_cpf_encryption_service()

# Test encryption
cpf = "12345678901"
encrypted, hash_val = service.encrypt_cpf(cpf)
print(f"✅ Encrypted: {encrypted[:30]}...")
print(f"✅ Hash: {hash_val}")

# Test decryption
decrypted = service.decrypt_cpf(encrypted)
print(f"✅ Decrypted: {decrypted}")
assert decrypted == cpf, "Encryption/Decryption failed!"

print("\n🎉 CPF Encryption is working correctly!")
```

Run:
```bash
python test_encryption.py
```

## 🎯 Common Use Cases

### Creating a Patient
```python
from app.models.patient import Patient

patient = Patient(
    name="João Silva",
    phone="+5511999999999",
    doctor_id=doctor_id
)

# CPF is automatically encrypted
patient.set_cpf("123.456.789-01")

db.add(patient)
db.commit()
```

### Reading CPF
```python
# Get decrypted value
cpf = patient.cpf_decrypted  # "12345678901"

# Get formatted display
formatted = patient.get_cpf_display()  # "123.456.789-01"
masked = patient.get_cpf_display(mask=True)  # "***.***.789-**"
```

### Searching by CPF
```python
from app.repositories.patient import PatientRepository

repo = PatientRepository(db)

# Search handles both formatted and plain CPF
patient = repo.get_by_cpf("123.456.789-01", doctor_id)
# OR
patient = repo.get_by_cpf("12345678901", doctor_id)
```

## ⚠️ Important: Update Your Code

### DO THIS ✅
```python
# Use set_cpf() for setting CPF
patient.set_cpf("123.456.789-01")

# Use cpf_decrypted for reading
cpf = patient.cpf_decrypted

# Use get_cpf_display() for display
display = patient.get_cpf_display(mask=True)
```

### DON'T DO THIS ❌
```python
# DON'T set cpf directly
patient.cpf = "12345678901"  # This stores plaintext!

# DON'T read cpf directly
cpf = patient.cpf  # This might be None or outdated
```

## 🔧 Updating Repository Methods

### Old Code (Plaintext)
```python
def get_by_cpf(self, cpf: str) -> Optional[Patient]:
    return self.db.query(Patient).filter(
        Patient.cpf == cpf  # ❌ Plaintext comparison
    ).first()
```

### New Code (Encrypted)
```python
def get_by_cpf(self, cpf: str) -> Optional[Patient]:
    from app.services.cpf_encryption_service import get_cpf_encryption_service

    service = get_cpf_encryption_service()
    cpf_hash = service.hash_cpf_for_search(cpf)

    return self.db.query(Patient).filter(
        Patient.cpf_hash == cpf_hash  # ✅ Hash comparison
    ).first()
```

## 📋 Files to Update

1. **Repository Layer** (`app/repositories/patient.py`):
   - [ ] `get_by_cpf()` - Use hash for lookup
   - [ ] `search_active()` - Include CPF hash in search
   - [ ] `check_duplicate_cpf()` - Use hash for duplicate check
   - [ ] `list_v2()` - Update search filters

2. **Service Layer** (`app/services/patient/crud_service.py`):
   - [ ] `create_patient()` - Use `patient.set_cpf()`
   - [ ] `update_patient()` - Use `patient.set_cpf()`

3. **API Layer** (`app/api/v2/patients_utils.py`):
   - [ ] `_serialize_patient()` - Use `patient.cpf_decrypted`

4. **Schemas** (`app/schemas/patient.py`):
   - [ ] Add CPF validator to `PatientCreate`
   - [ ] Add CPF validator to `PatientUpdate`

## 🧪 Testing

```bash
# Run unit tests
pytest tests/services/test_cpf_encryption_service.py -v

# Expected: 45 tests passed
```

## 📊 Verify Migration Success

```python
from app.database import SessionLocal
from app.models.patient import Patient
from sqlalchemy import func

db = SessionLocal()

# Check migration status
total = db.query(func.count(Patient.id)).scalar()
encrypted = db.query(func.count(Patient.id)).filter(
    Patient.cpf_encrypted.isnot(None)
).scalar()
has_cpf = db.query(func.count(Patient.id)).filter(
    Patient.cpf.isnot(None)
).scalar()

print(f"Total patients: {total}")
print(f"Encrypted CPF: {encrypted}")
print(f"Plaintext CPF: {has_cpf}")
print(f"Migration complete: {encrypted == has_cpf}")

db.close()
```

## 🆘 Rollback (Emergency Only)

```bash
# ONLY use if encryption is causing production issues
alembic downgrade -1

# Verify rollback
python -c "
from app.database import SessionLocal
from app.models.patient import Patient

db = SessionLocal()
count = db.query(Patient).filter(Patient.cpf.isnot(None)).count()
print(f'Rollback complete: {count} patients with plaintext CPF')
db.close()
"
```

## 📚 Full Documentation

- **Architecture & Design**: `docs/cpf_encryption_implementation.md`
- **Repository Migration**: `docs/cpf_repository_migration_guide.md`
- **Summary & Checklist**: `docs/CPF_ENCRYPTION_SUMMARY.md`

## 🔐 Security Reminders

1. ✅ Never commit encryption keys to git
2. ✅ Store keys in secret management system (production)
3. ✅ Rotate keys periodically
4. ✅ Log all decryption operations for audit
5. ✅ Use masked display for UI (`mask=True`)

## 💡 Tips

- **Performance**: Hash lookups are O(1) with proper indexes
- **Formatting**: Service handles both "123.456.789-01" and "12345678901"
- **Backward Compatibility**: Old plaintext CPF is automatically migrated
- **Display**: Always use `get_cpf_display(mask=True)` in UI for privacy

## ✅ Checklist

- [ ] Environment variables set
- [ ] Database backed up
- [ ] Migration run successfully
- [ ] Encryption verified with test script
- [ ] Repository methods updated
- [ ] Service layer updated
- [ ] API serialization updated
- [ ] Unit tests passing
- [ ] Integration tests updated
- [ ] Team trained
- [ ] Documentation reviewed

## 🎉 You're Done!

CPF encryption is now active. All new patient records will automatically use encryption.

**Questions?** Check the full documentation in `docs/cpf_encryption_implementation.md`
