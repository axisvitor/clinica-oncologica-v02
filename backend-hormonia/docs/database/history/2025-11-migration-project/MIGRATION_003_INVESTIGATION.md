# Migration 003 Investigation Report

**Report Generated:** 2025-11-16
**Investigation Agent:** Database Migration Inspector (Agent 31)
**Priority:** P0 (Critical) - Migration Chain Integrity

---

## Executive Summary

Migration `003_add_last_retry_at` is **missing** from the production `alembic_version` table, creating a gap in the migration chain:

```
002_patient_onboarding_saga → ??? → 004_add_flow_state_version
                              ^^^
                        Missing migration 003!
```

This investigation determines whether:
1. Migration 003 was applied but not recorded (schema exists, version missing)
2. Migration 003 was never applied (schema missing, migration skipped)

---

## Migration Details

### Migration 003 Specifications

| Property | Value |
|----------|-------|
| **Revision ID** | `003_add_last_retry_at` |
| **Revises** | `002_patient_onboarding_saga` |
| **Created** | 2025-11-07 10:00:00 |
| **Purpose** | Add retry tracking to patient onboarding saga |

### Database Changes

**Table:** `patient_onboarding_saga`

**Added Column:**
```sql
last_retry_at TIMESTAMP WITH TIME ZONE NULL
```

**Added Index:**
```sql
CREATE INDEX idx_patient_onboarding_saga_last_retry
    ON patient_onboarding_saga (last_retry_at);
```

---

## Migration Chain Analysis

### Expected Migration Sequence

```mermaid
graph LR
    A[001_add_idempotency_key] --> B[002_patient_onboarding_saga]
    B --> C[003_add_last_retry_at]
    C --> D[004_add_flow_state_version]
    D --> E[005_add_gin_indexes]
    E --> F[...]
```

### Current Production State

```
✅ 002_patient_onboarding_saga  (applied)
❌ 003_add_last_retry_at        (MISSING!)
✅ 004_add_flow_state_version   (applied)
```

**Risk:** Migration 004 expects migration 003 to have been applied first (dependency chain).

---

## Investigation Process

### Automated Script

The investigation script checks:

1. **Alembic Version Table**
   - Is migration 003 recorded?
   - What migrations are present?

2. **Table Existence**
   - Does `patient_onboarding_saga` table exist?
   - Created by migration 002

3. **Column Existence**
   - Does `last_retry_at` column exist?
   - Expected data type: `timestamp with time zone`

4. **Index Existence**
   - Does `idx_patient_onboarding_saga_last_retry` index exist?

5. **Data Integrity**
   - Are there rows with `last_retry_at` values?
   - Is the column being actively used?

### Running the Investigation

```bash
# From backend-hormonia directory
cd backend-hormonia

# Ensure .env file has DATABASE_URL configured
# DATABASE_URL=postgresql+psycopg://user:pass@host:port/db

# Run investigation script
python scripts/migration_investigation/investigate_migration_003.py

# Exit codes:
# 0 = All correct (migration recorded and applied)
# 1 = Applied but not recorded (needs version insert)
# 2 = Never applied (critical - missing migration)
# 3 = Inconsistent state (needs manual investigation)
```

---

## Possible Scenarios

### Scenario 1: Applied but Not Recorded ✅ LIKELY

**Symptoms:**
- ✅ Column `last_retry_at` exists
- ✅ Index `idx_patient_onboarding_saga_last_retry` exists
- ❌ Migration 003 NOT in `alembic_version`

**Cause:**
- Migration applied directly via SQL
- Database restore from backup (schema restored but not alembic_version)
- Alembic version update transaction failed

**Impact:** Low - Schema is correct, only tracking is wrong

**Resolution:**
```sql
-- Simply record the migration as applied
INSERT INTO alembic_version (version_num)
VALUES ('003_add_last_retry_at');
```

**Verification:**
```sql
-- Check migration is now recorded
SELECT version_num FROM alembic_version ORDER BY version_num;

-- Should show: 002, 003, 004, ...
```

---

### Scenario 2: Never Applied ⚠️ CRITICAL

**Symptoms:**
- ❌ Column `last_retry_at` does NOT exist
- ❌ Index does NOT exist
- ❌ Migration 003 NOT in `alembic_version`

**Cause:**
- Migration 004 applied before migration 003
- Migration 003 accidentally skipped
- Manual database changes bypassed Alembic

**Impact:** High - Missing database schema, application may fail

**Resolution Options:**

#### Option A: Apply Migration 003 (RISKY)
```bash
# This may fail if migration 004 conflicts
cd backend-hormonia
alembic upgrade 003_add_last_retry_at
```

**Risk:** Migration 004 may have dependencies on migration 003 being applied first.

#### Option B: Create New Migration (SAFER)
```bash
# Create new migration that adds missing column
alembic revision -m "add_missing_last_retry_at_column"
```

Edit the new migration:
```python
def upgrade() -> None:
    """Add missing last_retry_at column (catch-up migration)"""
    # Check if column already exists (idempotent)
    conn = op.get_bind()
    result = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'patient_onboarding_saga'
              AND column_name = 'last_retry_at'
        )
    """))

    if not result.scalar():
        op.add_column(
            "patient_onboarding_saga",
            sa.Column("last_retry_at", sa.DateTime(timezone=True), nullable=True),
        )

        op.create_index(
            "idx_patient_onboarding_saga_last_retry",
            "patient_onboarding_saga",
            ["last_retry_at"],
        )
```

#### Option C: Document and Accept (LEAST DISRUPTIVE)
- Document that migration 003 is missing
- Update migration 004 to not depend on 003
- Add column manually if needed in future

**Recommended:** Option B (create new idempotent migration)

---

### Scenario 3: Partial Application ⚠️

**Symptoms:**
- ✅ Column `last_retry_at` exists
- ❌ Index does NOT exist
- ❌ Migration 003 NOT in `alembic_version`

**Resolution:**
```sql
-- Create missing index
CREATE INDEX idx_patient_onboarding_saga_last_retry
    ON patient_onboarding_saga (last_retry_at);

-- Record migration as applied
INSERT INTO alembic_version (version_num)
VALUES ('003_add_last_retry_at');
```

---

## Code References

### Migration 003 Source

**File:** `/backend-hormonia/alembic/versions/003_add_last_retry_at.py`

```python
def upgrade() -> None:
    """Add last_retry_at column to track when last retry attempt was made."""

    # Add last_retry_at column
    op.add_column(
        "patient_onboarding_saga",
        sa.Column("last_retry_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create index for efficient retry queries
    op.create_index(
        "idx_patient_onboarding_saga_last_retry",
        "patient_onboarding_saga",
        ["last_retry_at"],
    )
```

### Usage in Application Code

The `last_retry_at` column is used in the Saga Orchestrator for retry scheduling:

```python
# backend-hormonia/app/coordination/saga_orchestrator.py
async def schedule_retry(saga_id: UUID, retry_at: datetime):
    """Schedule saga retry attempt"""
    await db.execute(
        """
        UPDATE patient_onboarding_saga
        SET next_retry_at = :retry_at,
            last_retry_at = NOW(),  -- ⬅️ Uses migration 003 column
            retry_count = retry_count + 1
        WHERE id = :saga_id
        """,
        {"retry_at": retry_at, "saga_id": saga_id}
    )
```

**Impact if column missing:**
- ❌ SQL query will fail with "column does not exist"
- ❌ Saga retry scheduling breaks
- ❌ Failed patient onboarding sagas cannot recover

---

## Recommendations

### Immediate Actions (Production)

1. **Run Investigation Script**
   ```bash
   python scripts/migration_investigation/investigate_migration_003.py
   ```

2. **Based on Exit Code:**
   - **Exit 0:** No action needed ✅
   - **Exit 1:** Insert into `alembic_version` (Scenario 1)
   - **Exit 2:** Create new migration (Scenario 2, Option B)
   - **Exit 3:** Contact database administrator

### Preventive Measures

1. **Migration Validation**
   - Add pre-deployment check: all migrations in alembic_version
   - Add automated test: migration chain integrity

2. **Alembic Best Practices**
   - Never apply migrations manually (always use `alembic upgrade`)
   - Never skip migrations in sequence
   - Always backup before migrations

3. **Monitoring**
   - Alert on missing migrations in production
   - Log migration history in CI/CD

---

## Investigation Deliverables

### Files Created

1. **Investigation Script**
   - **Path:** `scripts/migration_investigation/investigate_migration_003.py`
   - **Purpose:** Automated schema and version table checks
   - **Exit Codes:** 0=OK, 1=Record needed, 2=Apply needed, 3=Unknown

2. **Documentation**
   - **Path:** `docs/database/MIGRATION_003_INVESTIGATION.md` (this file)
   - **Purpose:** Complete investigation report and resolution guide

3. **Findings JSON** (generated by script)
   - **Path:** `docs/database/MIGRATION_003_INVESTIGATION.json`
   - **Purpose:** Machine-readable investigation results

### Memory Coordination

```bash
# Investigation findings stored in swarm memory
npx claude-flow@alpha memory store migration-003-status '{
  "migration_id": "003_add_last_retry_at",
  "status": "under_investigation",
  "priority": "P0",
  "table": "patient_onboarding_saga",
  "column": "last_retry_at",
  "issue": "missing_from_alembic_version",
  "script": "scripts/migration_investigation/investigate_migration_003.py",
  "report": "docs/database/MIGRATION_003_INVESTIGATION.md"
}'
```

---

## Next Steps

### For Database Administrator

1. **Run the investigation script**
2. **Review the findings JSON**
3. **Choose appropriate scenario resolution**
4. **Execute SQL fix or create migration**
5. **Verify fix with second script run**

### For Development Team

1. **Review saga_orchestrator.py** - Check if `last_retry_at` is required
2. **Add integration test** - Verify saga retry scheduling works
3. **Update deployment docs** - Document migration chain validation

### For DevOps

1. **Add pre-deployment check** - Validate migration chain integrity
2. **Update monitoring** - Alert on missing migrations
3. **Document rollback plan** - If migration fix fails

---

## Coordination Protocol

This investigation follows the **Research Agent** coordination protocol:

**BEFORE Work:**
```bash
npx claude-flow@alpha hooks pre-task --description "Investigating migration 003 status"
```

**DURING Work:**
```bash
npx claude-flow@alpha hooks post-edit \
  --file "scripts/migration_investigation/investigate_migration_003.py" \
  --memory-key "swarm/researcher/migration-003-investigation"
```

**AFTER Work:**
```bash
npx claude-flow@alpha hooks post-task --task-id "migration-003-investigation"
npx claude-flow@alpha hooks session-end --export-metrics true
```

**Memory Sharing:**
```bash
# Store findings for other agents
npx claude-flow@alpha memory store migration-003-findings '{
  "investigation_complete": true,
  "script_created": "scripts/migration_investigation/investigate_migration_003.py",
  "report_created": "docs/database/MIGRATION_003_INVESTIGATION.md",
  "recommendation": "run_script_to_determine_scenario"
}'
```

---

## References

- **Migration File:** `backend-hormonia/alembic/versions/003_add_last_retry_at.py`
- **Migration 002:** `backend-hormonia/alembic/versions/002_patient_onboarding_saga.py`
- **Migration 004:** `backend-hormonia/alembic/versions/004_add_flow_state_version.py`
- **Saga Orchestrator:** `backend-hormonia/app/coordination/saga_orchestrator.py`
- **Alembic Docs:** https://alembic.sqlalchemy.org/

---

## Appendix: Manual SQL Queries

### Check Migration Status
```sql
-- List all applied migrations
SELECT version_num, updated_at
FROM alembic_version
ORDER BY version_num;

-- Check if migration 003 is recorded
SELECT EXISTS (
    SELECT 1 FROM alembic_version
    WHERE version_num = '003_add_last_retry_at'
);
```

### Check Column Status
```sql
-- Check if last_retry_at column exists
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'patient_onboarding_saga'
  AND column_name = 'last_retry_at';

-- Check if index exists
SELECT indexname, tablename, indexdef
FROM pg_indexes
WHERE indexname = 'idx_patient_onboarding_saga_last_retry';
```

### Check Data Usage
```sql
-- Count rows using last_retry_at
SELECT COUNT(*)
FROM patient_onboarding_saga
WHERE last_retry_at IS NOT NULL;

-- Show recent retry attempts
SELECT id, status, retry_count, last_retry_at, next_retry_at
FROM patient_onboarding_saga
WHERE last_retry_at IS NOT NULL
ORDER BY last_retry_at DESC
LIMIT 10;
```

---

**END OF INVESTIGATION REPORT**
