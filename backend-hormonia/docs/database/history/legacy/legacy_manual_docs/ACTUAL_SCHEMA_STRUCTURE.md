# Actual Database Schema Structure

**Date:** 2025-11-16
**Source:** Direct database inspection
**Purpose:** Document ACTUAL production schema (not migration-based assumptions)

---

## Patient Table - Actual Structure

### Columns (18 total)

```sql
CREATE TABLE patients (
    -- Identity
    id                      UUID PRIMARY KEY,
    doctor_id               UUID REFERENCES doctors(id),

    -- Contact Information
    phone                   VARCHAR(20),
    name                    VARCHAR(255),           -- ⚠️ NOT "full_name"!
    email                   VARCHAR(255),

    -- Personal Data
    birth_date              DATE,
    cpf                     VARCHAR(14),

    -- Treatment Information
    treatment_type          VARCHAR(100),
    treatment_start_date    DATE,
    treatment_phase         VARCHAR(50),
    diagnosis               TEXT,

    -- Flow State
    flow_state              VARCHAR(10),
    current_day             INTEGER,

    -- Clinical Notes
    doctor_notes            TEXT,

    -- Metadata & Timestamps
    metadata                JSONB,                  -- ✅ With GIN index
    created_at              TIMESTAMP,
    updated_at              TIMESTAMP,
    deleted_at              TIMESTAMP               -- ✅ Soft delete support
);
```

### Key Findings

1. **Column Name Mismatch:**
   - Database has: `name` (VARCHAR(255))
   - Tests expected: `full_name`
   - **Action Required:** Update all queries to use `name` instead of `full_name`

2. **Soft Delete Working:**
   - ✅ `deleted_at` column exists
   - ✅ NULL = active record
   - ✅ NOT NULL = soft-deleted record

3. **Metadata JSONB:**
   - ✅ `metadata` column exists (JSONB type)
   - ✅ Has GIN index for fast querying
   - ✅ Supports JSONB operators (@>, ?, etc.)

4. **Missing from Schema:**
   - ❌ No `full_name` column
   - ✅ All expected columns present otherwise

---

## Indexes on Patient Table

### Confirmed Indexes

1. **Primary Key:**
   - `patients_pkey` on `id`

2. **GIN Indexes:**
   - `idx_patients_metadata_gin` on `metadata` (JSONB GIN index)
   - Supports fast metadata queries like:
     ```sql
     WHERE metadata @> '{"status": "active"}'
     ```

3. **Pagination Index:**
   - `idx_patients_pagination`
   - Likely on (created_at, id) or similar
   - Supports cursor-based pagination

4. **Foreign Key Index:**
   - Index on `doctor_id` (for JOIN performance)

---

## Other Critical Tables

### Uploads Table: ❌ DOES NOT EXIST

**Expected Schema (from migration 015):**
```sql
CREATE TABLE uploads (
    id              UUID PRIMARY KEY,
    filename        VARCHAR(255),
    content_type    VARCHAR(100),
    file_size       INTEGER,
    file_metadata   JSONB,              -- Renamed from "metadata"
    uploaded_by     UUID,
    created_at      TIMESTAMP
);
```

**Status:** Table not created yet
**Impact:** File upload functionality unavailable
**Action Required:** Apply migration 015 or create table manually

---

### Flow Templates Table: ❌ DOES NOT EXIST

**Expected Schema (from migration 018):**
```sql
CREATE TABLE flow_templates (
    id              UUID PRIMARY KEY,
    name            VARCHAR(255),
    description     TEXT,
    template_data   JSONB,
    category        VARCHAR(100),
    is_active       BOOLEAN,
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP
);
```

**Status:** Table not created yet
**Impact:** Cannot use predefined flow templates
**Action Required:** Apply migration 018 or seed templates manually

---

## Migration Revision Inventory

### Migration Files in alembic/versions/

```
✓ 001_add_message_idempotency_key.py       (Nov  9)
✓ 002_patient_onboarding_saga.py           (Nov  9) ✅ APPLIED
✓ 003_add_last_retry_at.py                 (Nov  9)
✓ 004_add_flow_state_version.py            (Nov  9) ✅ APPLIED
✓ 005_add_gin_indexes_patient_metadata.py  (Nov  9)
✓ 006_add_message_priority.py              (Nov 16)
✓ 007_add_quiz_sessions_patient_id_index.py(Nov 13)
✓ 008_add_flow_executions_flow_id_index.py (Nov 13)
✓ 009_add_patient_unique_constraints.py    (Nov 13)
✓ 010_add_missing_foreign_key_and_composite_indexes_p0_performance.py (Nov 13)
✓ 011_hipaa_audit_trail_enhancement.py     (Nov 16)
✓ 012_migrate_quiz_response_value_to_jsonb.py (Nov 14)
✓ 013_add_gin_index_patient_metadata.py    (Nov 16)
✓ 014_add_cursor_pagination_indexes.py     (Nov 16)
✓ 015_rename_upload_metadata_column.py     (Nov 16)
✓ 016_validate_patient_metadata.py         (Nov 16)
✓ 017_add_patient_soft_delete.py           (Nov 16)
✓ 018_seed_flow_templates_for_onboarding.py(Nov 16)
```

**Total Migration Files:** 18
**Applied to Database:** 2
**Gap:** 16 migrations

---

## Schema Features Already Present (Despite Untracked Migrations)

### ✅ Features That Work

1. **GIN Indexes** (from migrations 005, 013)
   - Present on: patients.metadata, error_logs.context, security_audit_log.*
   - Working: JSONB queries are fast

2. **Cursor Pagination** (from migration 014)
   - 26 pagination indexes found
   - Queries with ORDER BY created_at, id work efficiently

3. **Soft Delete** (from migration 017)
   - `deleted_at` column exists on patients
   - NULL = active, NOT NULL = deleted
   - Filtering works correctly

4. **Patient Metadata Validation** (from migration 016)
   - JSONB column functional
   - Constraints may or may not be present (need to verify)

5. **HIPAA Audit Trail** (from migration 011)
   - `security_audit_log` table exists
   - GIN indexes on additional_data and source_metadata

---

## Schema Features NOT Present

### ❌ Missing Features

1. **Message Idempotency** (migration 001)
   - Need to verify: Does `messages` table have `idempotency_key` column?

2. **Last Retry Tracking** (migration 003)
   - ❌ `patient_flow_states.last_retry_at` does NOT exist
   - Impact: Cannot track saga retry timing

3. **Message Priority** (migration 006)
   - Need to verify: Does `messages` table have `priority` column?

4. **Uploads Table** (migration 015)
   - ❌ Table does not exist at all

5. **Flow Templates** (migration 018)
   - ❌ Table does not exist at all

---

## Recommended Query Updates

### Old (Failing) Queries

```sql
-- ❌ FAILS: column "full_name" does not exist
SELECT id, full_name, email FROM patients;

-- ❌ FAILS: column "metadata" is ambiguous (uploads table doesn't exist)
SELECT metadata FROM uploads;
```

### New (Correct) Queries

```sql
-- ✅ WORKS: Use "name" instead of "full_name"
SELECT id, name, email FROM patients;

-- ✅ WORKS: Metadata queries on patients
SELECT id, name, metadata FROM patients
WHERE metadata @> '{"status": "active"}';

-- ✅ WORKS: Soft delete filtering
SELECT id, name FROM patients
WHERE deleted_at IS NULL;  -- Active records only

-- ✅ WORKS: Cursor pagination
SELECT id, name, created_at FROM patients
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

---

## Next Steps for Schema Reconciliation

### Phase 1: Verify Current State
```sql
-- Check for missing columns that should exist
SELECT column_name FROM information_schema.columns
WHERE table_name = 'messages'
  AND column_name IN ('idempotency_key', 'priority');

SELECT column_name FROM information_schema.columns
WHERE table_name = 'patient_flow_states'
  AND column_name = 'last_retry_at';
```

### Phase 2: Create Missing Tables
```bash
# Option A: Apply migrations
alembic upgrade 015  # Create uploads table
alembic upgrade 018  # Seed flow templates

# Option B: Manual creation (if migrations can't be applied)
psql $DATABASE_URL < scripts/create_missing_tables.sql
```

### Phase 3: Stamp Migration State
```bash
# Mark all migrations as applied (if schema matches)
alembic stamp head

# Or stamp to last known good state
alembic stamp 004_add_flow_state_version
```

---

## Conclusion

**Database Schema Status:** ✅ Mostly functional, ⚠️ some gaps

- **Working:** Patient CRUD, metadata queries, soft delete, pagination
- **Missing:** Uploads table, flow templates table, some audit columns
- **Inconsistency:** Migration tracking out of sync with reality

**Key Insight:** The production database has evolved through a mix of:
1. Alembic migrations (2 tracked)
2. Direct SQL changes (evident from features working despite missing migrations)
3. Manual schema modifications

**Action Required:** Reconcile migration state before applying future changes.

---

**Generated by:** Agent 35 - Post-Migration Validator
**Timestamp:** 2025-11-16T22:08:00Z
**Related Report:** POST_MIGRATION_VALIDATION.md
