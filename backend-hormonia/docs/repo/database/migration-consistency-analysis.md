# Alembic Migrations Consistency Analysis Report

**Analysis Date**: 2025-11-25
**Agent**: Hive Mind Migration Verification Agent
**Working Directory**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia`

---

## Executive Summary

**Status**: ⚠️ **CRITICAL ISSUES FOUND** - Migration chain is broken

**Total Migrations**: 23 files (including __init__.py)
**Actual Migrations**: 22 migrations
**Broken Links**: 2 critical issues preventing migration execution

---

## 1. Migration Chain Listing (Revision Order)

```
001_add_idempotency_key (root)
  ↓
002_patient_onboarding_saga
  ↓
003_add_last_retry_at
  ↓
004_add_flow_state_version
  ↓
005_add_gin_indexes_patient_metadata
  ↓
006_add_message_priority
  ↓
007_add_quiz_sessions_patient_id_index
  ↓
008_add_flow_executions_flow_id_index
  ↓
009_add_patient_unique_constraints
  ↓
010_add_missing_foreign_key_and_composite_indexes
  ↓
011_hipaa_audit_trail_enhancement
  ↓
012_migrate_quiz_response_value_to_jsonb
  ↓
013_add_gin_index_patient_metadata
  ↓
014_add_cursor_pagination_indexes
  ↓
015_rename_upload_metadata_column
  ↓
016_validate_patient_metadata ✅ EXISTS
  ↓
017_add_patient_soft_delete
  ↓
018_seed_flow_templates_for_onboarding
  ↓
27ee28e62ff8_create_message_templates_table ⚠️ (auto-generated, breaks convention)
  ↓
019_seed_welcome_message_template ❌ BROKEN LINK
  ↓
020_encrypt_cpf_lgpd ❌ REFERENCES WRONG REVISION
  ↓
021_add_patient_summaries
```

---

## 2. Critical Issues

### Issue #1: **BROKEN REVISION REFERENCE - Migration 019**

**Severity**: 🔴 **CRITICAL**

**Problem**:
- **File**: `019_seed_welcome_message_template.py`
- **Revision ID in file**: `'019_seed_welcome_message'` (missing `_template` suffix)
- **Referenced by 020**: `down_revision = '019_seed_welcome_message_template'`
- **Actual down_revision**: `'27ee28e62ff8'`

**Impact**:
- Alembic cannot build revision map
- Throws `KeyError: '019_seed_welcome_message_template'`
- **Migrations cannot run** (blocks all subsequent migrations)

**Root Cause**:
Naming inconsistency between revision ID and filename.

**Fix Required**:
```python
# In 019_seed_welcome_message_template.py
# CHANGE:
revision = '019_seed_welcome_message'

# TO:
revision = '019_seed_welcome_message_template'
```

---

### Issue #2: **INCORRECT DOWN_REVISION - Migration 020**

**Severity**: 🔴 **CRITICAL**

**Problem**:
- **File**: `020_encrypt_cpf_lgpd.py`
- **Current down_revision**: `'019_seed_welcome_message_template'`
- **Correct down_revision**: `'019_seed_welcome_message'` (actual revision ID)

**Impact**:
- Chain broken between 019 and 020
- Alembic cannot resolve dependency

**Fix Required**:
```python
# In 020_encrypt_cpf_lgpd.py
# CHANGE:
down_revision = '019_seed_welcome_message_template'

# TO:
down_revision = '019_seed_welcome_message'
```

---

### Issue #3: ⚠️ **OUT-OF-SEQUENCE MIGRATION - 27ee28e62ff8**

**Severity**: 🟡 **MEDIUM**

**Problem**:
- Auto-generated migration with hash-based revision ID
- Inserted between 018 and 019
- Breaks sequential numbering convention

**Current Chain**:
```
018_seed_flow_templates
  ↓
27ee28e62ff8_create_message_templates ← Auto-generated
  ↓
019_seed_welcome_message
```

**Should Be**:
```
018_seed_flow_templates
  ↓
019_seed_welcome_message
  ↓
020_encrypt_cpf_lgpd
  ↓
021_add_patient_summaries
  ↓
022_create_message_templates ← Renamed with sequential number
```

**Recommendation**:
Rename `27ee28e62ff8` to `022_create_message_templates` and adjust chain:
- 019 down_revision → '018_seed_flow_templates'
- 020 down_revision → '019_seed_welcome_message'
- 021 down_revision → '020_encrypt_cpf_lgpd'
- 022 down_revision → '021_add_patient_summaries'

---

## 3. Schema Evolution Summary

### Major Schema Changes by Migration:

**001**: Add message idempotency (prevents duplicate sends)
- Added `idempotency_key` to messages table
- Unique index on (patient_id, idempotency_key)

**002**: Patient onboarding saga table
- Created `patient_onboarding_saga` table
- Implements saga pattern for distributed transactions
- Retry logic and compensation support

**003**: Add retry tracking
- Added `last_retry_at` to saga table

**004-010**: Performance indexes
- GIN indexes on JSONB metadata
- Foreign key indexes
- Composite indexes for common queries

**011**: HIPAA audit trail
- Enhanced audit logging for compliance

**012**: ⭐ **MAJOR** - Quiz responses JSONB migration
- Converted `quiz_responses.response_value` from Text to JSONB
- Complex data migration with validation
- Backward compatibility views
- Helper functions for JSONB operations

**013-014**: Additional indexes
- GIN indexes, cursor pagination indexes

**015**: Metadata column rename
- Fixed naming convention

**016**: Validation migration (data integrity)
- Validates patient metadata against JSON schema
- No schema changes, only validation

**017**: Soft delete for patients
- Added `deleted_at` column
- Partial indexes for performance

**018**: Seed flow templates
- Initial onboarding flow (15-day program)

**27ee28e62ff8**: Message templates table
- Created `message_templates` table
- Supports template variables

**019**: Seed welcome message template
- Initial template for patient onboarding

**020**: ⭐ **MAJOR** - CPF encryption (LGPD compliance)
- Added `cpf_encrypted` (AES-256) and `cpf_hash` (SHA-256)
- Migrates plaintext CPF to encrypted format
- Keeps original column for rollback safety
- Updates unique constraints

**021**: ⭐ **NEW** - Patient summaries table
- AI-generated summaries for doctor consultations
- JSONB content, PDF export support
- Tracks token usage and generation time

---

## 4. Consistency Check Results

### ✅ Positive Findings:

1. **All model imports in env.py** - Complete
   - All 30+ models properly imported
   - Metadata registration correct

2. **Migration 016 exists** - Previously reported as missing
   - File: `alembic/versions/016_validate_patient_metadata.py`
   - Properly chains: 015 → 016 → 017

3. **Foreign key relationships** - Consistent
   - patient_onboarding_saga → patients (CASCADE)
   - patient_summaries → patients (CASCADE)
   - Proper ondelete handlers

4. **Index coverage** - Good
   - GIN indexes on JSONB columns
   - Composite indexes for common queries
   - Partial indexes for filtered queries

5. **Data migrations** - Well implemented
   - 001: Backfills idempotency keys
   - 012: Sophisticated JSONB migration with validation
   - 020: Encrypts existing CPF data
   - All use batching and error handling

### ⚠️ Issues Found:

1. **Critical**: Broken revision chain (019 ↔ 020)
2. **Medium**: Out-of-sequence auto-generated migration
3. **Minor**: Inconsistent revision ID naming

### 📊 Migration Statistics:

- **Schema Migrations**: 19 (create/alter tables)
- **Data Migrations**: 4 (001, 012, 018, 019, 020)
- **Index Migrations**: 8 (performance optimization)
- **Validation Migrations**: 1 (016)
- **Seed Migrations**: 2 (018, 019)

---

## 5. Alembic Configuration Review

### ✅ alembic.ini:
- Database URL from environment (correct)
- Version locations properly configured
- Logging configured appropriately

### ✅ alembic/env.py:
- **CRITICAL FIX APPLIED**: All models imported
- Proper metadata registration
- URL handling for Railway/Supabase (postgres:// → postgresql://)
- Batch mode enabled for PostgreSQL compatibility
- compare_type and compare_server_default enabled

---

## 6. Model Consistency Check

### PatientOnboardingSaga Model vs Migration 002:
✅ **CONSISTENT**
- All columns match
- Enum values match (including deprecated STEP_2_FIREBASE_USER_CREATED)
- Indexes match
- Foreign keys match

### PatientSummary Model vs Migration 021:
✅ **CONSISTENT**
- All columns match
- JSONB content structure documented
- Indexes match
- Foreign keys correct

### Patient Model:
✅ **LGPD Encryption Applied** (Migration 020)
- cpf_encrypted (Text)
- cpf_hash (String(64))
- Old cpf column preserved for rollback

---

## 7. Potential Issues & Gaps

### ⚠️ Missing Migrations (if models changed):
Based on imports in env.py, check if these models have migrations:

1. **message_templates** - ✅ Has migration (27ee28e62ff8)
2. **patient_summaries** - ✅ Has migration (021)
3. **patient_onboarding_saga** - ✅ Has migration (002)

### 🔍 Manual DB Changes:
**Recommendation**: Run this query to detect schema drift:

```bash
alembic check
```

If tables/columns exist that aren't in migrations, they were added manually.

---

## 8. Recommendations for Migration Hygiene

### Immediate Actions (Critical):

1. **Fix revision ID in migration 019**:
   ```bash
   # Edit alembic/versions/019_seed_welcome_message_template.py
   # Change revision = '019_seed_welcome_message'
   # To revision = '019_seed_welcome_message_template'
   ```

2. **Update down_revision in migration 020**:
   ```bash
   # Edit alembic/versions/020_encrypt_cpf_lgpd.py
   # Change down_revision = '019_seed_welcome_message_template'
   # To down_revision = '019_seed_welcome_message'
   ```

3. **Verify chain**:
   ```bash
   alembic history --verbose
   alembic current
   ```

### Long-term Improvements:

1. **Adopt consistent naming convention**:
   ```
   XXX_descriptive_name.py
   revision = 'XXX_descriptive_name'
   ```
   Avoid hash-based revision IDs (27ee28e62ff8)

2. **Use sequential numbering**:
   - Next migration: 022_descriptive_name.py
   - Always increment from latest

3. **Add migration checklist**:
   - [ ] Revision ID matches filename
   - [ ] down_revision points to latest migration
   - [ ] Test both upgrade() and downgrade()
   - [ ] Data migrations include error handling
   - [ ] Indexes created for new foreign keys

4. **Consider squashing old migrations**:
   - Migrations 001-010 could be squashed into initial schema
   - Keep development history separate from production

5. **Add pre-commit hook**:
   ```bash
   # Check for broken revision chains
   alembic history --verbose > /dev/null
   ```

---

## 9. Migration Execution Plan

### To fix broken chain and apply pending migrations:

```bash
# 1. Fix revision IDs in files (manual edit)
# 2. Verify chain is fixed
alembic history --verbose

# 3. Check current database state
alembic current

# 4. Apply all pending migrations
alembic upgrade head

# 5. Verify final state
alembic current
psql -c "\d patients"  # Check CPF encryption columns
psql -c "\d patient_summaries"  # Check new table
```

---

## 10. Conclusion

**Current State**: ⚠️ **MIGRATIONS BROKEN - IMMEDIATE FIX REQUIRED**

**Critical Issues**: 2 (revision chain broken)
**Medium Issues**: 1 (naming convention)
**Blocking Migrations**: Yes (cannot run alembic upgrade)

**Priority Actions**:
1. 🔴 Fix revision IDs (5 minutes)
2. 🔴 Test migration chain (2 minutes)
3. 🟡 Rename auto-generated migration (10 minutes)
4. 🟢 Implement migration checklist (ongoing)

**Overall Assessment**:
The migration infrastructure is solid with good practices:
- Comprehensive model imports
- Data migrations with validation
- Proper indexes and constraints
- LGPD compliance implemented

However, the broken chain from migrations 019-020 is a **blocker** that must be fixed before any database upgrades can proceed.

---

## Appendix A: Full Revision Chain

```
revision                              | down_revision
--------------------------------------|----------------------------------------
001_add_idempotency_key               | None (root)
002_patient_onboarding_saga           | 001_add_idempotency_key
003_add_last_retry_at                 | 002_patient_onboarding_saga
004_add_flow_state_version            | 003_add_last_retry_at
005_add_gin_indexes                   | 004_add_flow_state_version
006_add_message_priority              | 005_add_gin_indexes
007_quiz_sessions_index               | 006_add_message_priority
008_flow_states_index                 | 007_quiz_sessions_index
009_patient_constraints               | 008_flow_states_index
010_missing_indexes                   | 009_patient_constraints
011_hipaa_audit                       | 010_missing_indexes
012_migrate_quiz_response_value_to_jsonb | 011_hipaa_audit
013                                   | 012_migrate_quiz_response_value_to_jsonb
014                                   | 013
015_rename_upload_metadata            | 014
016_validate_patient_metadata         | 015_rename_upload_metadata
017_add_patient_soft_delete           | 016_validate_patient_metadata
018_seed_flow_templates               | 017_add_patient_soft_delete
27ee28e62ff8                          | 018_seed_flow_templates
019_seed_welcome_message ❌           | 27ee28e62ff8
020_encrypt_cpf_lgpd ❌               | 019_seed_welcome_message_template
021_patient_summaries                 | 020_encrypt_cpf_lgpd
```

---

**Generated by**: Hive Mind Migration Verification Agent
**Coordination**: Claude Flow Hooks (pre-task, post-edit, memory storage)
**Next Steps**: Fix critical issues, verify chain, apply migrations
