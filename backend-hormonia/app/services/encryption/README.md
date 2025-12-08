# Encryption Services Package

Unified encryption services for healthcare compliance (HIPAA, LGPD).

## Quick Start

```python
from app.services.encryption import get_unified_encryption_service

service = get_unified_encryption_service()

# Encrypt CPF (Brazilian National ID)
encrypted_cpf, cpf_hash = service.encrypt_cpf("12345678901")
decrypted = service.decrypt_cpf(encrypted_cpf)

# Encrypt email
encrypted_email, email_hash = service.encrypt_email("user@example.com")
decrypted = service.decrypt_email(encrypted_email)

# Encrypt phone
encrypted_phone, phone_hash = service.encrypt_phone("+5511999999999")
decrypted = service.decrypt_phone(encrypted_phone)

# Encrypt generic PHI field
encrypted = service.encrypt_field("sensitive data")
decrypted = service.decrypt_field(encrypted)
```

## Files

- **`unified_encryption_service.py`** - Main unified encryption service
- **`__init__.py`** - Package exports and backward compatibility aliases

## Features

### Algorithms
- **AES-256-GCM** (default): Authenticated encryption
- **AES-256-CBC** (legacy): Backward compatibility
- **Fernet**: Quiz token encryption

### Field Types
- CPF (Brazilian National ID)
- Email addresses
- Phone numbers
- Generic PHI data
- Sensitive quiz responses

### Security
- PBKDF2 key derivation (100,000 iterations)
- SHA-256 HMAC searchable hashes
- Salt-based hashing
- Tamper detection (GCM mode)

## Backward Compatibility

All old service imports still work:

```python
# ✅ OLD CODE STILL WORKS
from app.services.encryption import get_phi_encryption_service
from app.services.encryption import get_lgpd_encryption_service
from app.services.encryption import get_cpf_encryption_service
from app.services.encryption import get_encryption_service

# All return the same UnifiedEncryptionService instance
```

## Documentation

- **Migration Guide:** `/docs/ENCRYPTION_SERVICE_MIGRATION.md`
- **Summary:** `/docs/ENCRYPTION_CONSOLIDATION_SUMMARY.md`
- **Tests:** `/tests/services/test_unified_encryption_service.py`

## Usage Examples

### CPF Encryption
```python
service = get_unified_encryption_service()

# With formatting
encrypted_cpf, cpf_hash = service.encrypt_cpf("123.456.789-01")
# Returns: ("encrypted:gcm:...", "sha256_hash...")

# Decrypt (returns normalized CPF without formatting)
decrypted = service.decrypt_cpf(encrypted_cpf)
# Returns: "12345678901"
```

### Email Encryption
```python
# Normalize to lowercase automatically
encrypted_email, email_hash = service.encrypt_email("User@Example.COM")
decrypted = service.decrypt_email(encrypted_email)
# Returns: "user@example.com"
```

### Phone Encryption
```python
# Normalize by removing formatting
encrypted_phone, phone_hash = service.encrypt_phone("+55 (11) 99999-9999")
decrypted = service.decrypt_phone(encrypted_phone)
# Returns: "+5511999999999"
```

### Patient Data Encryption
```python
patient_data = {
    "name": "John Doe",
    "cpf": "12345678901",
    "email": "john@example.com",
    "phone": "+5511999999999",
    "diagnosis": "Test diagnosis",
    "non_phi_field": "not encrypted"
}

# Encrypt all PHI fields
encrypted_data = service.encrypt_patient_data(patient_data)
# PHI fields encrypted, non-PHI preserved
# Adds metadata: __encrypted, __encryption_version, __encryption_algorithm

# Decrypt all PHI fields
decrypted_data = service.decrypt_patient_data(encrypted_data)
# Returns original data, removes metadata
```

### Algorithm Selection
```python
from app.services.encryption import UnifiedEncryptionService, EncryptionAlgorithm

# Use AES-GCM (recommended)
service = UnifiedEncryptionService(algorithm=EncryptionAlgorithm.AES_256_GCM)
encrypted = service.encrypt_field("test")
# Returns: "encrypted:gcm:..."

# Use AES-CBC (legacy)
service = UnifiedEncryptionService(algorithm=EncryptionAlgorithm.AES_256_CBC)
encrypted = service.encrypt_field("test")
# Returns: "encrypted:..."

# Use Fernet (quiz tokens)
service = UnifiedEncryptionService(algorithm=EncryptionAlgorithm.FERNET)
encrypted = service.encrypt_field("test")
# Returns: "encrypted:fernet:..."
```

### Searchable Hashes
```python
from app.services.encryption import FieldType

# Generate hash for searching
cpf = "12345678901"
cpf_hash = service.generate_hash(cpf, FieldType.CPF)

# Later: search by hash without decryption
# SELECT * FROM patients WHERE cpf_hash = ?
```

## Environment Variables

```bash
# Required (production)
PHI_ENCRYPTION_KEY=<base64-encoded-32-byte-key>
HASH_SALT=<hex-encoded-salt>

# Optional (uses PHI_ENCRYPTION_KEY if not set)
MONTHLY_QUIZ_TOKEN_SECRET=<secret-for-quiz-tokens>

# Development only (auto-generated if not set)
APP_ENVIRONMENT=development
```

Generate keys:
```bash
# Generate PHI encryption key (32 bytes, base64)
python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"

# Generate hash salt (64 chars, hex)
python -c "import secrets; print(secrets.token_hex(32))"
```

## Testing

Run comprehensive test suite:

```bash
# All encryption tests
pytest tests/services/test_unified_encryption_service.py -v

# Specific test class
pytest tests/services/test_unified_encryption_service.py::TestCPFEncryption -v

# Single test
pytest tests/services/test_unified_encryption_service.py::TestCPFEncryption::test_encrypt_cpf_valid -v
```

## Advanced Features

### Key Rotation
```python
service = get_unified_encryption_service()

# Rotate encryption key (requires maintenance window)
new_master_key = "new-key-32-bytes-base64-encoded..."
success = service.rotate_encryption_key(new_master_key)

# Note: This requires re-encrypting all data in database
# Should be done during scheduled maintenance
```

### Key Entropy Validation
```python
# Validate key has sufficient entropy
key = "my-encryption-key-12345678901234567890"
is_valid = service.validate_key_entropy(key, min_entropy_bits=128)
# Returns: True if key meets requirements
```

## Migration from Old Services

If you're migrating from old services:

1. **No changes required** - backward compatible
2. **Optionally update imports** to new package
3. **See migration guide** for detailed instructions

Old imports (still work):
```python
from app.services.phi_encryption_service import get_phi_encryption_service
from app.services.lgpd_encryption_service import get_lgpd_encryption_service
from app.services.cpf_encryption_service import get_cpf_encryption_service
```

New imports (recommended):
```python
from app.services.encryption import get_unified_encryption_service
```

## Compliance

- ✅ **HIPAA** compliant (PHI encryption)
- ✅ **LGPD** compliant (PII encryption - Brazilian GDPR)
- ✅ **Audit trail** ready (built-in logging)
- ✅ **Key rotation** support
- ✅ **Searchable encryption** (hash-based)

## Support

- **Migration Guide:** `/docs/ENCRYPTION_SERVICE_MIGRATION.md`
- **Summary:** `/docs/ENCRYPTION_CONSOLIDATION_SUMMARY.md`
- **Source Code:** `unified_encryption_service.py`
- **Tests:** `/tests/services/test_unified_encryption_service.py`

---

**Version:** 2.0.0
**Author:** Hormonia Development Team
