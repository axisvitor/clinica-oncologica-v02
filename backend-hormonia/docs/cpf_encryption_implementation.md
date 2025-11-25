# CPF Encryption Implementation - LGPD Compliance

## Overview

This document describes the CPF (Brazilian tax ID) encryption implementation for LGPD (Lei Geral de Proteção de Dados) compliance. CPF is considered Personally Identifiable Information (PII) and sensitive data under Brazilian law, requiring encryption at rest.

## Architecture

### Components

1. **CPFEncryptionService** (`app/services/cpf_encryption_service.py`)
   - Main service for CPF encryption/decryption
   - Uses PHIEncryptionService for AES-256-CBC encryption
   - Generates searchable hashes via SearchableHash utility
   - Handles format normalization and validation

2. **Patient Model** (`app/models/patient.py`)
   - Added `cpf_encrypted` column for encrypted CPF storage
   - Added `cpf_hash` column for searchable hash
   - Kept `cpf` column for backward compatibility (will be deprecated)
   - Property `cpf_decrypted` for transparent decryption
   - Method `set_cpf()` for automatic encryption

3. **Database Migration** (`alembic/versions/020_encrypt_cpf_lgpd.py`)
   - Adds encrypted columns
   - Migrates existing plaintext CPF to encrypted format
   - Updates indexes and constraints
   - Supports rollback (with security warning)

### Security Design

```
┌─────────────────────────────────────────────────────────────┐
│                    CPF Encryption Flow                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Input CPF                                                   │
│  "123.456.789-01"                                           │
│       │                                                      │
│       ▼                                                      │
│  ┌──────────────┐                                          │
│  │ Normalize    │ Remove formatting → "12345678901"        │
│  └──────┬───────┘                                          │
│         │                                                   │
│         ├──────────────────┬───────────────────┐          │
│         ▼                  ▼                   ▼          │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │ Validate     │   │ Encrypt      │   │ Hash         │ │
│  │ Format       │   │ AES-256-CBC  │   │ SHA-256      │ │
│  └──────────────┘   └──────┬───────┘   └──────┬───────┘ │
│                             │                   │          │
│                             ▼                   ▼          │
│                      cpf_encrypted         cpf_hash       │
│                      (Text column)      (String(64))      │
│                                                            │
│  Database Storage:                                         │
│  ┌────────────────────────────────────────────────┐      │
│  │ cpf_encrypted: "encrypted:gAAAAA..."          │      │
│  │ cpf_hash: "a1b2c3d4e5f6..."                   │      │
│  │ cpf: NULL (legacy column)                      │      │
│  └────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### Encryption Specifications

| Component | Algorithm | Details |
|-----------|-----------|---------|
| **Encryption** | AES-256-CBC | Via PHIEncryptionService with PBKDF2 key derivation |
| **Key Derivation** | PBKDF2-SHA256 | 100,000 iterations, unique salt per deployment |
| **Searchable Hash** | SHA-256 HMAC | Deterministic hash with application salt |
| **Storage Format** | Base64 | Prefix: "encrypted:" for encrypted values |
| **Hash Length** | 64 characters | Fixed-length SHA-256 hex digest |

## Usage Examples

### Setting CPF (Automatic Encryption)

```python
from app.models.patient import Patient

# Create patient with CPF encryption
patient = Patient(
    name="João Silva",
    phone="+5511999999999",
    doctor_id=doctor_id
)

# Set CPF - automatically encrypts
patient.set_cpf("123.456.789-01")

# Database stores:
# - cpf_encrypted: "encrypted:gAAAAA..."
# - cpf_hash: "a1b2c3d4e5f6..."
# - cpf: NULL

db.add(patient)
db.commit()
```

### Reading CPF (Automatic Decryption)

```python
# Read patient from database
patient = db.query(Patient).filter_by(id=patient_id).first()

# Access decrypted CPF via property
cpf = patient.cpf_decrypted  # Returns: "12345678901"

# Get formatted CPF for display
formatted = patient.get_cpf_display()  # Returns: "123.456.789-01"
masked = patient.get_cpf_display(mask=True)  # Returns: "***.***.789-**"
```

### Searching by CPF

```python
from app.services.cpf_encryption_service import get_cpf_encryption_service

service = get_cpf_encryption_service()

# Generate hash for search
search_cpf = "123.456.789-01"
cpf_hash = service.hash_cpf_for_search(search_cpf)

# Query using hash (no decryption needed)
patient = db.query(Patient).filter(
    Patient.cpf_hash == cpf_hash,
    Patient.doctor_id == doctor_id
).first()
```

### Repository Integration

The repository methods need to be updated to use `cpf_hash` for lookups:

```python
# OLD (plaintext search)
def get_by_cpf(self, cpf: str, doctor_id: UUID) -> Optional[Patient]:
    return self.db.query(Patient).filter(
        Patient.cpf == cpf,
        Patient.doctor_id == doctor_id
    ).first()

# NEW (encrypted search)
def get_by_cpf(self, cpf: str, doctor_id: UUID) -> Optional[Patient]:
    from app.services.cpf_encryption_service import get_cpf_encryption_service
    service = get_cpf_encryption_service()
    cpf_hash = service.hash_cpf_for_search(cpf)

    return self.db.query(Patient).filter(
        Patient.cpf_hash == cpf_hash,
        Patient.doctor_id == doctor_id
    ).first()
```

## Migration Guide

### Prerequisites

1. **Set Environment Variables**
   ```bash
   # Generate encryption keys
   python -c 'import secrets; print(secrets.token_hex(32))'

   # Add to .env
   PHI_ENCRYPTION_KEY=<generated-key>
   HASH_SALT=<generated-salt>
   ```

2. **Backup Database**
   ```bash
   pg_dump -U postgres -d hormonia > backup_before_cpf_encryption.sql
   ```

### Running the Migration

```bash
# Run migration
alembic upgrade head

# Verify migration
python -c "
from app.database import SessionLocal
from app.models.patient import Patient

db = SessionLocal()
patients = db.query(Patient).filter(Patient.cpf_encrypted.isnot(None)).limit(5).all()
for p in patients:
    print(f'Patient {p.id}: cpf_encrypted={p.cpf_encrypted is not None}, cpf_hash={p.cpf_hash is not None}')
db.close()
"
```

### Rollback (Emergency Only)

⚠️ **WARNING**: Rollback restores plaintext CPF storage. Use only in emergencies.

```bash
# Rollback to previous version
alembic downgrade -1

# Verify rollback
python -c "
from app.database import SessionLocal
from app.models.patient import Patient

db = SessionLocal()
count = db.query(Patient).filter(Patient.cpf.isnot(None)).count()
print(f'Patients with plaintext CPF: {count}')
db.close()
"
```

## API Updates

### Request/Response Changes

The API endpoints remain unchanged for backward compatibility. The encryption is transparent:

```json
// POST /api/v2/patients - Create patient
{
  "name": "João Silva",
  "phone": "+5511999999999",
  "cpf": "123.456.789-01",  // Automatically encrypted
  "email": "joao@example.com"
}

// GET /api/v2/patients/{id} - Get patient
{
  "id": "uuid",
  "name": "João Silva",
  "cpf": "123.456.789-01",  // Automatically decrypted
  "email": "joao@example.com"
}
```

### Schema Updates

Update patient schemas to use the encryption service in validators:

```python
# app/schemas/v2/patient.py

class PatientV2Create(BaseModel):
    cpf: Optional[str] = None

    @validator('cpf')
    def validate_cpf(cls, v):
        if v:
            from app.services.cpf_encryption_service import get_cpf_encryption_service
            service = get_cpf_encryption_service()
            # Normalize and validate
            normalized = service._normalize_cpf(v)
            if not service._validate_cpf_format(normalized):
                raise ValueError("Invalid CPF format")
        return v
```

## Performance Considerations

### Query Performance

- **Hash lookups**: O(1) with index on `cpf_hash`
- **Decryption overhead**: ~1ms per record (AES-256-CBC)
- **Batch decryption**: Use eager loading to minimize queries

### Optimization Tips

1. **Use hash for filtering**
   ```python
   # Good: Filter by hash first
   cpf_hash = service.hash_cpf_for_search(cpf)
   patients = db.query(Patient).filter(Patient.cpf_hash == cpf_hash).all()

   # Bad: Load all and decrypt
   patients = db.query(Patient).all()
   filtered = [p for p in patients if p.cpf_decrypted == cpf]
   ```

2. **Lazy decryption**
   ```python
   # Only decrypt when needed
   patients = db.query(Patient).all()
   for p in patients:
       # cpf_decrypted is a property - only decrypts on access
       if p.cpf_decrypted:
           print(p.get_cpf_display(mask=True))
   ```

3. **Index strategy**
   - Index on `cpf_hash` for searches
   - Composite index on `(cpf_hash, doctor_id)` for tenant-scoped queries
   - Partial index to exclude NULL values

## Security Best Practices

### Key Management

1. **Never commit keys to version control**
   - Use environment variables
   - Store in secret management system (AWS Secrets Manager, HashiCorp Vault)
   - Rotate keys periodically

2. **Key rotation procedure**
   ```python
   # 1. Generate new key
   # 2. Re-encrypt all CPF values
   # 3. Update environment
   # 4. Restart application

   # See: app/services/phi_encryption_service.py::rotate_encryption_key()
   ```

### Access Control

1. **Limit decryption access**
   - Only authorized services should decrypt
   - Log all decryption operations
   - Implement RBAC for CPF access

2. **Audit logging**
   ```python
   import logging

   logger = logging.getLogger(__name__)

   def get_patient_cpf(patient_id, user):
       patient = db.query(Patient).get(patient_id)
       cpf = patient.cpf_decrypted

       # Log access
       logger.info(f"User {user.id} accessed CPF for patient {patient_id}")

       return cpf
   ```

## Testing

### Unit Tests

```python
# tests/services/test_cpf_encryption_service.py

def test_cpf_encryption_decryption():
    service = get_cpf_encryption_service()

    # Test encryption
    original_cpf = "12345678901"
    encrypted, hash_val = service.encrypt_cpf(original_cpf)

    assert encrypted.startswith("encrypted:")
    assert len(hash_val) == 64

    # Test decryption
    decrypted = service.decrypt_cpf(encrypted)
    assert decrypted == original_cpf

def test_cpf_normalization():
    service = get_cpf_encryption_service()

    # Test with formatting
    cpf_formatted = "123.456.789-01"
    cpf_plain = "12345678901"

    hash1 = service.hash_cpf_for_search(cpf_formatted)
    hash2 = service.hash_cpf_for_search(cpf_plain)

    assert hash1 == hash2  # Same hash regardless of formatting
```

### Integration Tests

```python
# tests/integration/test_patient_cpf_encryption.py

def test_patient_cpf_roundtrip(db_session):
    # Create patient with CPF
    patient = Patient(name="Test", phone="+5511999999999")
    patient.set_cpf("123.456.789-01")

    db_session.add(patient)
    db_session.commit()

    # Verify storage
    assert patient.cpf_encrypted is not None
    assert patient.cpf_hash is not None
    assert patient.cpf is None  # Legacy column should be NULL

    # Verify decryption
    assert patient.cpf_decrypted == "12345678901"

    # Verify search
    from app.services.cpf_encryption_service import get_cpf_encryption_service
    service = get_cpf_encryption_service()
    search_hash = service.hash_cpf_for_search("123.456.789-01")

    found = db_session.query(Patient).filter(
        Patient.cpf_hash == search_hash
    ).first()

    assert found.id == patient.id
```

## Compliance

### LGPD Requirements

✅ **Article 46**: Technical measures for data protection
- CPF is encrypted with industry-standard AES-256
- Key management follows best practices

✅ **Article 48**: Data minimization
- Only necessary data is stored
- Plaintext column will be dropped after migration stability

✅ **Article 49**: Security measures
- Encryption at rest
- Secure key derivation (PBKDF2)
- Access logging capabilities

### Audit Checklist

- [ ] Encryption keys generated and stored securely
- [ ] Environment variables configured in production
- [ ] Database migration tested in staging
- [ ] Backup created before migration
- [ ] Access controls implemented
- [ ] Audit logging enabled
- [ ] Documentation updated
- [ ] Team trained on new system
- [ ] Incident response plan updated
- [ ] Compliance review completed

## Troubleshooting

### Common Issues

1. **Migration fails with encryption error**
   ```
   Error: PHI_ENCRYPTION_KEY not configured
   ```
   **Solution**: Set environment variable before running migration

2. **Cannot decrypt CPF**
   ```
   Error: Failed to decrypt data - invalid token
   ```
   **Solution**: Verify encryption key matches the key used during encryption

3. **Hash lookup returns no results**
   ```
   Expected: Patient found
   Actual: None
   ```
   **Solution**: Ensure CPF normalization is consistent (remove formatting before hashing)

### Debug Commands

```python
# Check encryption service
from app.services.cpf_encryption_service import get_cpf_encryption_service
service = get_cpf_encryption_service()
encrypted, hash_val = service.encrypt_cpf("12345678901")
print(f"Encrypted: {encrypted[:50]}...")
print(f"Hash: {hash_val}")

# Verify database state
from app.database import SessionLocal
from app.models.patient import Patient

db = SessionLocal()
stats = {
    'total': db.query(Patient).count(),
    'encrypted': db.query(Patient).filter(Patient.cpf_encrypted.isnot(None)).count(),
    'plaintext': db.query(Patient).filter(Patient.cpf.isnot(None)).count()
}
print(stats)
db.close()
```

## References

- [LGPD - Lei Geral de Proteção de Dados](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm)
- [NIST Cryptographic Standards](https://csrc.nist.gov/publications/detail/fips/197/final)
- [OWASP Cryptographic Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
- [PHI Encryption Service Documentation](./phi_encryption.md)
- [Searchable Hash Service Documentation](./searchable_hash.md)
