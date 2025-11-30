# Encryption Service Migration Guide

## Overview

This document guides the migration from 4 separate encryption services to the unified `UnifiedEncryptionService`.

**Consolidated Services:**
1. `app/services/phi_encryption_service.py` - PHI encryption (HIPAA)
2. `app/services/lgpd_encryption_service.py` - LGPD encryption (Brazilian GDPR)
3. `app/services/cpf_encryption_service.py` - CPF encryption
4. `app/services/encryption_service.py` - Quiz encryption (Fernet)
5. `app/domain/quizzes/security/token_rotation.py` - Token rotation code

**New Unified Service:**
- `app/services/encryption/unified_encryption_service.py`
- `app/services/encryption/__init__.py`

## Key Features of Unified Service

### Algorithms Supported
- **AES-256-GCM** (default, recommended): Authenticated encryption
- **AES-256-CBC** (legacy): For backward compatibility
- **Fernet**: For quiz tokens

### Field Types Supported
- CPF (Brazilian National ID)
- Email addresses
- Phone numbers
- Generic PHI data
- Sensitive quiz responses

### Key Improvements
1. **Single service** replaces 4+ separate services
2. **Backward compatible** - old imports still work
3. **More secure** - AES-GCM by default (vs AES-CBC)
4. **Consistent API** - all field types use same methods
5. **Better organized** - in `app/services/encryption/` package

## Backward Compatibility

All old imports continue to work without changes:

```python
# ✅ OLD CODE STILL WORKS
from app.services.phi_encryption_service import get_phi_encryption_service
from app.services.lgpd_encryption_service import get_lgpd_encryption_service
from app.services.cpf_encryption_service import get_cpf_encryption_service
from app.services.encryption_service import get_encryption_service

# All return the SAME UnifiedEncryptionService instance
```

## Recommended Migration Path

### Option 1: Keep Old Imports (No Changes Required)
Your code will continue working as-is. The old imports are aliases to the new service.

### Option 2: Update to New Imports (Recommended)
Update imports to use the new unified service:

```python
# ✅ NEW RECOMMENDED CODE
from app.services.encryption import (
    get_unified_encryption_service,
    FieldType,
    EncryptionAlgorithm
)

service = get_unified_encryption_service()

# Explicit field types for better code clarity
encrypted_cpf, cpf_hash = service.encrypt_cpf("12345678901")
encrypted_email, email_hash = service.encrypt_email("user@example.com")
encrypted_phone, phone_hash = service.encrypt_phone("+5511999999999")
```

## Files Requiring Import Updates

### Core Application Files

#### 1. `app/models/patient.py`
**Lines:** 250, 269, 296, 315, 335, 359, 379
**Current imports:**
```python
from app.services.cpf_encryption_service import get_cpf_encryption_service
from app.services.lgpd_encryption_service import get_lgpd_encryption_service
```

**Recommended change:**
```python
from app.services.encryption import get_unified_encryption_service
# Use: service = get_unified_encryption_service()
```

**Or keep as-is (backward compatible):**
```python
from app.services.encryption import get_cpf_encryption_service, get_lgpd_encryption_service
```

---

#### 2. `app/domain/quizzes/answer_validator.py`
**Line:** 15
**Current import:**
```python
from app.services.encryption_service import get_encryption_service
```

**Recommended change:**
```python
from app.services.encryption import get_unified_encryption_service, FieldType
service = get_unified_encryption_service()
# Use FieldType.QUIZ_RESPONSE when encrypting
```

**Or keep as-is:**
```python
from app.services.encryption import get_encryption_service
```

---

#### 3. `app/services/ab_testing_audit.py`
**Line:** 20
**Current import:**
```python
from app.services.encryption_service import EncryptionService
```

**Recommended change:**
```python
from app.services.encryption import UnifiedEncryptionService, get_unified_encryption_service
```

---

#### 4. `app/services/analytics/ab_testing_analytics/service.py`
**Line:** 17
**Current import:**
```python
from app.services.encryption_service import EncryptionService
```

**Recommended change:**
```python
from app.services.encryption import UnifiedEncryptionService, get_unified_encryption_service
```

---

### Test Files

#### 5. `tests/services/test_encryption_lgpd.py`
**Lines:** 11, 203, 230
**Current import:**
```python
from app.services.encryption_service import EncryptionService
```

**Recommended change:**
```python
from app.services.encryption import UnifiedEncryptionService, get_unified_encryption_service, FieldType
```

---

#### 6. `tests/services/test_cpf_encryption_service.py`
**Line:** 12
**Current import:**
```python
from app.services.cpf_encryption_service import CPFEncryptionService, get_cpf_encryption_service
```

**Recommended change:**
```python
from app.services.encryption import UnifiedEncryptionService, get_unified_encryption_service
# Note: UnifiedEncryptionService has all CPFEncryptionService methods
```

---

### Migration Scripts

#### 7. `alembic/versions/020_encrypt_cpf_lgpd.py`
**Line:** 65
**Current import:**
```python
from app.services.cpf_encryption_service import get_cpf_encryption_service
```

**Keep as-is (backward compatible):**
```python
from app.services.encryption import get_cpf_encryption_service
```

---

#### 8. `scripts/verify_cpf_encryption.py`
**Line:** 18
**Current import:**
```python
from app.services.cpf_encryption_service import get_cpf_encryption_service
```

**Keep as-is (backward compatible):**
```python
from app.services.encryption import get_cpf_encryption_service
```

---

#### 9. `scripts/verify_lgpd_implementation.py`
**Line:** 61
**Current import:**
```python
from app.services.lgpd_encryption_service import (
    get_lgpd_encryption_service,
    LGPDEncryptionService
)
```

**Keep as-is (backward compatible):**
```python
from app.services.encryption import get_lgpd_encryption_service
# Note: UnifiedEncryptionService is returned, has all LGPD methods
```

---

## Deprecation Schedule

### Phase 1: Now - 3 months (Current)
- ✅ New unified service available
- ✅ Old services still present as files
- ✅ All old imports work via aliases
- ⚠️  No breaking changes

### Phase 2: 3-6 months (Future)
- ⚠️  Old service files marked as deprecated
- ⚠️  Deprecation warnings logged when using old imports
- ✅ Still backward compatible

### Phase 3: 6+ months (Future)
- ❌ Old service files may be removed
- ✅ Backward compatible imports still work (via __init__.py)
- 📝 Must use new imports only

## Migration Checklist

### Application Code
- [ ] Update `app/models/patient.py` imports (optional)
- [ ] Update `app/domain/quizzes/answer_validator.py` imports (optional)
- [ ] Update `app/services/ab_testing_audit.py` imports (optional)
- [ ] Update `app/services/analytics/ab_testing_analytics/service.py` imports (optional)

### Test Code
- [ ] Update `tests/services/test_encryption_lgpd.py` imports (optional)
- [ ] Update `tests/services/test_cpf_encryption_service.py` imports (optional)
- [ ] Create tests for `UnifiedEncryptionService`

### Scripts
- [ ] Update `scripts/verify_cpf_encryption.py` imports (optional)
- [ ] Update `scripts/verify_lgpd_implementation.py` imports (optional)
- [ ] Update `alembic/versions/020_encrypt_cpf_lgpd.py` imports (optional)

### Documentation
- [ ] Update API documentation
- [ ] Update developer onboarding docs
- [ ] Update deployment guides with new env var requirements

## Environment Variables

The unified service uses the same environment variables:

```bash
# Required (production)
PHI_ENCRYPTION_KEY=<base64-encoded-32-byte-key>
HASH_SALT=<hex-encoded-salt>

# Optional (quiz encryption uses PHI key if not set)
MONTHLY_QUIZ_TOKEN_SECRET=<secret-for-quiz-tokens>

# Development only (auto-generated if not set)
# Do NOT rely on auto-generation in production!
```

## Testing Migration

### 1. Test Backward Compatibility
```python
# Test old imports still work
from app.services.phi_encryption_service import get_phi_encryption_service
from app.services.lgpd_encryption_service import get_lgpd_encryption_service
from app.services.cpf_encryption_service import get_cpf_encryption_service

phi_service = get_phi_encryption_service()
lgpd_service = get_lgpd_encryption_service()
cpf_service = get_cpf_encryption_service()

# All should be the same instance
assert phi_service is lgpd_service
assert lgpd_service is cpf_service
```

### 2. Test Encryption/Decryption
```python
from app.services.encryption import get_unified_encryption_service

service = get_unified_encryption_service()

# Test CPF
encrypted_cpf, cpf_hash = service.encrypt_cpf("12345678901")
assert service.decrypt_cpf(encrypted_cpf) == "12345678901"

# Test email
encrypted_email, email_hash = service.encrypt_email("test@example.com")
decrypted_email = service.decrypt_email(encrypted_email)
assert decrypted_email == "test@example.com"

# Test phone
encrypted_phone, phone_hash = service.encrypt_phone("+5511999999999")
decrypted_phone = service.decrypt_phone(encrypted_phone)
assert decrypted_phone == "+5511999999999"
```

### 3. Test Algorithm Compatibility
```python
# Test GCM (new default)
service_gcm = UnifiedEncryptionService(algorithm=EncryptionAlgorithm.AES_256_GCM)
encrypted = service_gcm.encrypt_field("test", FieldType.PHI_GENERIC)
assert encrypted.startswith("encrypted:gcm:")

# Test CBC (legacy)
service_cbc = UnifiedEncryptionService(algorithm=EncryptionAlgorithm.AES_256_CBC)
encrypted = service_cbc.encrypt_field("test", FieldType.PHI_GENERIC)
assert encrypted.startswith("encrypted:")
assert ":gcm:" not in encrypted
```

## Rollback Plan

If issues arise, you can quickly rollback:

1. **No code changes needed** - old imports still work
2. **Old service files still present** - can be used directly if needed
3. **No database changes** - encryption format is backward compatible

## Support

For questions or issues:
1. Check this migration guide
2. Review `app/services/encryption/unified_encryption_service.py` docstrings
3. Run existing tests: `pytest tests/services/test_encryption*.py`
4. Contact: Hormonia Development Team

## Summary

- ✅ **No breaking changes** - all old code continues to work
- ✅ **Backward compatible** - old imports are aliases to new service
- ✅ **Improved security** - AES-GCM by default
- ✅ **Cleaner codebase** - 4 services → 1 unified service
- ✅ **Better organized** - in `app/services/encryption/` package

**Recommendation:** Update imports gradually as you touch each file, but there's no urgency - everything works as-is.
