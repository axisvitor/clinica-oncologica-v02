# Migration Investigation Tools

## Overview

This directory contains automated scripts for investigating database migration issues in production.

## Scripts

### 1. investigate_migration_003.py

**Purpose:** Check if migration 003 (`add_last_retry_at`) was applied but not recorded in `alembic_version`.

**What it checks:**
- ✅ Is migration 003 in `alembic_version` table?
- ✅ Does `patient_onboarding_saga.last_retry_at` column exist?
- ✅ Does `idx_patient_onboarding_saga_last_retry` index exist?
- ✅ Are there rows with `last_retry_at` values?

**Exit Codes:**
- `0` - All correct (migration recorded and applied)
- `1` - Applied but not recorded (needs version insert)
- `2` - Never applied (critical - missing migration)
- `3` - Inconsistent state (needs manual investigation)

## Usage

### Prerequisites

```bash
# 1. Navigate to backend-hormonia directory
cd backend-hormonia

# 2. Ensure .env file exists with DATABASE_URL
# DATABASE_URL=postgresql+psycopg://user:password@host:port/database

# 3. Install dependencies (if not already installed)
pip install -r requirements.txt
```

### Running the Investigation

```bash
# Run the script
python scripts/migration_investigation/investigate_migration_003.py

# Or make it executable and run directly
chmod +x scripts/migration_investigation/investigate_migration_003.py
./scripts/migration_investigation/investigate_migration_003.py
```

### Reading the Output

The script provides color-coded output:

- 🟢 **Green (✅)** - Success, everything looks good
- 🔴 **Red (❌)** - Error, something is missing or wrong
- 🟡 **Yellow (⚠️)** - Warning, needs attention
- 🔵 **Blue (ℹ️)** - Information

### Example Output: Scenario 1 (Applied but Not Recorded)

```
================================================================================
                        MIGRATION 003 INVESTIGATION REPORT
================================================================================

ℹ️  Applied migrations: 002_patient_onboarding_saga, 004_add_flow_state_version

================================================================================
                             1. ALEMBIC VERSION CHECK
================================================================================

❌ Migration 003 is NOT recorded in alembic_version
⚠️  This creates a gap: 002 → ??? → 004

================================================================================
                             3. COLUMN EXISTENCE CHECK
================================================================================

✅ Column 'last_retry_at' exists
ℹ️  Column name: last_retry_at
ℹ️  Data type: timestamp with time zone
ℹ️  Nullable: YES

================================================================================
                             6. ANALYSIS & RECOMMENDATION
================================================================================

⚠️  SCENARIO: Migration 003 was APPLIED but NOT RECORDED

📋 RECOMMENDED ACTION:
✅ Manually insert migration 003 into alembic_version table

SQL to execute:
INSERT INTO alembic_version (version_num) VALUES ('003_add_last_retry_at');
```

### Example Output: Scenario 2 (Never Applied)

```
================================================================================
                             3. COLUMN EXISTENCE CHECK
================================================================================

❌ Column 'last_retry_at' does NOT exist

================================================================================
                             6. ANALYSIS & RECOMMENDATION
================================================================================

❌ SCENARIO: Migration 003 was NEVER APPLIED

📋 RECOMMENDED ACTION:
⚠️  CAUTION: Applying migration 003 now may cause issues

Options:
  A) Apply migration 003 manually (if safe)
  B) Create a new migration that adds the column (safer)
  C) Accept the gap and document it (least disruptive)
```

## Output Files

The script generates two files:

1. **JSON Report** (machine-readable)
   - Path: `docs/database/MIGRATION_003_INVESTIGATION.json`
   - Contains all findings in structured format

2. **Markdown Report** (human-readable)
   - Path: `docs/database/MIGRATION_003_INVESTIGATION.md`
   - Complete investigation guide with recommendations

## Resolution Examples

### Scenario 1: Insert Missing Version Record

If the column exists but version is not recorded:

```sql
-- Connect to production database
psql $DATABASE_URL

-- Insert migration record
INSERT INTO alembic_version (version_num)
VALUES ('003_add_last_retry_at');

-- Verify
SELECT version_num FROM alembic_version ORDER BY version_num;
-- Should show: 001, 002, 003, 004, ...
```

### Scenario 2: Create Catch-up Migration

If the column does NOT exist:

```bash
# Create new migration
cd backend-hormonia
alembic revision -m "add_missing_last_retry_at_column"
```

Edit the new migration file:

```python
def upgrade() -> None:
    """Add missing last_retry_at column (catch-up migration)"""
    from sqlalchemy import text

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
        # Add column
        op.add_column(
            "patient_onboarding_saga",
            sa.Column("last_retry_at", sa.DateTime(timezone=True), nullable=True),
        )

        # Add index
        op.create_index(
            "idx_patient_onboarding_saga_last_retry",
            "patient_onboarding_saga",
            ["last_retry_at"],
        )

        print("✅ Added missing last_retry_at column")
    else:
        print("ℹ️  Column already exists, skipping")
```

Then apply:

```bash
alembic upgrade head
```

## Troubleshooting

### Script Fails to Connect to Database

```bash
# Check DATABASE_URL is set
echo $DATABASE_URL

# Or check .env file
cat .env | grep DATABASE_URL

# Test connection manually
psql $DATABASE_URL -c "SELECT version();"
```

### Permission Denied

```bash
# Make script executable
chmod +x scripts/migration_investigation/investigate_migration_003.py

# Or run with python explicitly
python scripts/migration_investigation/investigate_migration_003.py
```

### Missing Dependencies

```bash
# Install required packages
pip install sqlalchemy psycopg python-dotenv

# Or install all requirements
pip install -r requirements.txt
```

## Best Practices

1. **Always Backup First**
   ```bash
   pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **Test in Staging First**
   - Run investigation script in staging
   - Apply fix in staging
   - Verify application works
   - Then apply to production

3. **Document Changes**
   - Record what you found
   - Document what fix was applied
   - Note any special considerations

4. **Coordinate with Team**
   - Share findings via memory system
   - Alert team before applying fixes
   - Schedule maintenance window if needed

## Memory Coordination

The script automatically stores findings in the swarm memory system:

```bash
# Investigation findings are stored at:
# Key: migration-003-status
# Namespace: default

# Other agents can retrieve findings:
npx claude-flow@alpha memory retrieve migration-003-status

# Search for related migrations:
npx claude-flow@alpha memory search "migration-003" --limit 10
```

## Related Documentation

- **Investigation Report:** `/docs/database/MIGRATION_003_INVESTIGATION.md`
- **Migration 003 Source:** `/alembic/versions/003_add_last_retry_at.py`
- **Migration 002 Source:** `/alembic/versions/002_patient_onboarding_saga.py`
- **Migration 004 Source:** `/alembic/versions/004_add_flow_state_version.py`

## Support

If you encounter issues:

1. Check the full investigation report: `docs/database/MIGRATION_003_INVESTIGATION.md`
2. Review script output and exit code
3. Share findings with database administrator
4. Consult Alembic documentation: https://alembic.sqlalchemy.org/

---

**Last Updated:** 2025-11-16
**Maintained By:** Database Migration Team
