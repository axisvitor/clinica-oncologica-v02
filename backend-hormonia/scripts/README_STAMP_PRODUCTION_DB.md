# Production Database Stamping Guide

## Overview

The `stamp_production_db.py` script safely stamps the Alembic version table when your production database schema was created manually (outside of Alembic migrations).

## Problem Statement

**Scenario:**
- Production database has all tables created manually or via SQL dumps
- `alembic_version` table is empty or shows old version
- Running `alembic upgrade head` would try to recreate existing tables → **ERROR!**

**Solution:**
"Stamp" tells Alembic: *"The database is already at this migration state, don't re-run it."*

---

## Installation & Setup

### Prerequisites

```bash
cd backend-hormonia

# Install dependencies
pip install asyncpg alembic

# Verify script is executable
chmod +x scripts/stamp_production_db.py
```

### Environment Setup

The script uses the production database URL from environment:

```bash
export DATABASE_URL="postgresql://user:pass@host:5432/dbname?sslmode=require"
```

Or it defaults to the AWS RDS production database (hardcoded).

---

## Usage Guide

### 1. **Show Available Migrations** (No DB Connection)

View all migration files in order:

```bash
python scripts/stamp_production_db.py --show-migrations
```

**Output:**
```
AVAILABLE MIGRATIONS
====================

Migration chain (65 migrations):

  1. 001_initial_migration
     001_initial_migration.py
      ↓
  2. 002_add_flow_templates
     002_add_flow_templates.py
      ↓
  ...
 65. 5479068ccdaa
     5479068ccdaa_rename_audit_log_metadata_to_event_.py

Latest revision (head): 5479068ccdaa
```

---

### 2. **Analyze Schema** (Recommended First Step)

Analyze current database and get recommendation:

```bash
python scripts/stamp_production_db.py --analyze
```

**What it does:**
- ✅ Connects to production database
- ✅ Inspects all tables, columns, indexes, constraints
- ✅ Compares with migration files
- ✅ Validates schema against latest migration
- ✅ Recommends which revision to stamp

**Output:**
```
SCHEMA ANALYSIS & RECOMMENDATION
=================================

Current Database State:
  Tables: 42
  Alembic Version: None

Latest Migration:
  Revision: 5479068ccdaa

✓ Your schema appears to match revision: 5479068ccdaa

RECOMMENDATION:
  python scripts/stamp_production_db.py --stamp 5479068ccdaa
```

---

### 3. **Preview Stamp (Dry Run)** - SAFE ✅

Preview what will happen without making changes:

```bash
python scripts/stamp_production_db.py --stamp 5479068ccdaa --dry-run
```

**What it does:**
- ✅ Validates revision exists
- ✅ Checks schema compatibility
- ✅ Shows what would be modified
- ✅ **NO CHANGES TO DATABASE**

**Output:**
```
STAMPING DATABASE WITH REVISION: 5479068ccdaa
==============================================

✓ Connected to production database
✓ Found 42 tables in database
✓ Schema validates successfully for revision 5479068ccdaa

ℹ DRY RUN MODE - No changes will be made
ℹ DRY RUN: Would insert revision: 5479068ccdaa
```

---

### 4. **Actual Stamp** - REQUIRES CONFIRMATION ⚠️

Stamp the database (modifies alembic_version table):

```bash
python scripts/stamp_production_db.py --stamp 5479068ccdaa
```

**Safety Features:**
- ✅ Validates schema matches revision
- ✅ Shows current vs new version
- ✅ Requires TWO confirmations before proceeding
- ✅ Verifies stamp was successful

**Interactive Flow:**
```
STAMPING DATABASE WITH REVISION: 5479068ccdaa
==============================================

✓ Schema validates successfully for revision 5479068ccdaa

⚠️  WARNING: This will modify the database!

Current alembic_version: None
New version will be: 5479068ccdaa

⚠ Are you sure you want to stamp the database? (yes/no): yes

⚠ FINAL CONFIRMATION: Proceed with stamping? (yes/no): yes

ℹ Inserting revision: 5479068ccdaa...
✓ Successfully stamped database with revision: 5479068ccdaa

✓ Database stamped successfully!

Next steps:
  1. Verify: SELECT * FROM alembic_version;
  2. Check: alembic current
  3. Review: alembic history --verbose
```

---

### 5. **Force Stamp (Skip Validation)** - DANGEROUS ⚠️⚠️⚠️

Skip schema validation (use with extreme caution):

```bash
python scripts/stamp_production_db.py --stamp 5479068ccdaa --force
```

**⚠️ WARNING:**
- Bypasses all schema validation
- Use only if you're absolutely certain
- Can cause migration conflicts if wrong

---

## Verification After Stamping

### 1. Check Database Directly

```sql
-- Connect to production database
psql $DATABASE_URL

-- Verify alembic_version
SELECT * FROM alembic_version;

-- Should show:
-- version_num
-- --------------
-- 5479068ccdaa
```

### 2. Verify with Alembic

```bash
cd backend-hormonia

# Show current revision
alembic current

# Should output:
# 5479068ccdaa (head)

# Show migration history
alembic history --verbose

# Check for pending migrations
alembic upgrade head --sql > /tmp/pending.sql
cat /tmp/pending.sql

# Should show "Already up to date" or minimal changes
```

### 3. Test Migration Path

```bash
# Generate SQL for next upgrade (if any)
alembic upgrade head --sql > /tmp/upgrade.sql

# Review SQL before applying
less /tmp/upgrade.sql

# If looks good, apply
alembic upgrade head
```

---

## Error Recovery

### If Stamping Goes Wrong

**Problem:** Stamped with wrong revision

**Solution 1: Re-stamp with correct revision**
```bash
# Delete current version
psql $DATABASE_URL -c "DELETE FROM alembic_version;"

# Re-run analysis
python scripts/stamp_production_db.py --analyze

# Stamp with correct revision
python scripts/stamp_production_db.py --stamp CORRECT_REVISION
```

**Solution 2: Manual correction**
```sql
-- Connect to database
psql $DATABASE_URL

-- Update to correct revision
UPDATE alembic_version SET version_num = 'CORRECT_REVISION';

-- Verify
SELECT * FROM alembic_version;
```

---

## Common Scenarios

### Scenario 1: Fresh Manual Schema

**Situation:**
- Database created from SQL dump
- No alembic_version table exists

**Steps:**
```bash
# 1. Analyze
python scripts/stamp_production_db.py --analyze

# 2. Dry run
python scripts/stamp_production_db.py --stamp RECOMMENDED_REVISION --dry-run

# 3. Actual stamp
python scripts/stamp_production_db.py --stamp RECOMMENDED_REVISION

# 4. Verify
alembic current
```

---

### Scenario 2: Old Alembic Version

**Situation:**
- alembic_version exists but is outdated
- New migrations applied manually (outside Alembic)

**Steps:**
```bash
# 1. Check current version
psql $DATABASE_URL -c "SELECT * FROM alembic_version;"

# 2. Analyze schema
python scripts/stamp_production_db.py --analyze

# 3. Stamp with newer revision
python scripts/stamp_production_db.py --stamp NEW_REVISION

# 4. Verify
alembic history --verbose
```

---

### Scenario 3: Schema Doesn't Match

**Situation:**
- Validation fails (schema doesn't match any revision)

**Steps:**
```bash
# 1. Analyze to see issues
python scripts/stamp_production_db.py --analyze

# Output might show:
# ⚠ Schema validation found 3 issue(s):
#   - Missing expected tables: webhook_idempotency
#   - audit_logs still has 'metadata' column (should be 'event_metadata')
#   - Missing whatsapp_delivery_failures table

# 2. Fix schema issues first
# - Add missing tables
# - Rename columns
# - Apply manual migrations

# 3. Re-analyze
python scripts/stamp_production_db.py --analyze

# 4. Stamp when validation passes
python scripts/stamp_production_db.py --stamp REVISION
```

---

## Script Architecture

### What Gets Validated

1. **Tables:**
   - Expected core tables exist (users, patients, messages, etc.)
   - No unexpected tables

2. **Columns:**
   - Known migrations' columns exist
   - Column renames applied (e.g., metadata → event_metadata)

3. **Indexes:**
   - Performance indexes exist
   - Unique constraints present

4. **Constraints:**
   - Foreign keys valid
   - Check constraints applied

### Validation Rules by Revision

```python
if revision >= '5479068ccdaa':
    # Check audit_logs.event_metadata exists (not metadata)

if revision >= '20251009_230000':
    # Check whatsapp_delivery_failures table exists

if revision >= '20251009_235500':
    # Check webhook_idempotency table exists
```

### Safety Mechanisms

1. **Multiple Confirmations:**
   - First: "Are you sure?"
   - Second: "FINAL CONFIRMATION?"

2. **Dry Run Default:**
   - Must explicitly remove `--dry-run` to make changes

3. **Schema Validation:**
   - Compares current schema vs expected schema
   - Lists all issues before stamping

4. **Rollback Information:**
   - Shows how to undo if something goes wrong

5. **Verification Steps:**
   - Provides SQL queries to verify success

---

## Troubleshooting

### Issue: "Revision not found"

**Error:**
```
✗ Revision 'xyz123' not found in migration files
```

**Solution:**
```bash
# List available revisions
python scripts/stamp_production_db.py --show-migrations

# Use exact revision ID from output
python scripts/stamp_production_db.py --stamp CORRECT_REVISION
```

---

### Issue: "Schema validation failed"

**Error:**
```
✗ Schema validation failed!
  - Missing whatsapp_delivery_failures table
```

**Solution:**
```bash
# Option 1: Apply missing migrations manually
psql $DATABASE_URL < migrations/add_whatsapp_failures.sql

# Option 2: Stamp with older revision that matches
python scripts/stamp_production_db.py --analyze  # Find matching revision

# Option 3: Force stamp (not recommended)
python scripts/stamp_production_db.py --stamp REVISION --force
```

---

### Issue: "Cannot connect to database"

**Error:**
```
✗ Failed to connect to database: TimeoutError
```

**Solution:**
```bash
# Check database URL
echo $DATABASE_URL

# Test connection manually
psql $DATABASE_URL -c "SELECT 1;"

# Verify SSL certificate
psql "$DATABASE_URL?sslmode=verify-full"

# Check firewall/security groups
# Ensure your IP is whitelisted
```

---

## Best Practices

### ✅ DO:

1. **Always start with `--analyze`**
   ```bash
   python scripts/stamp_production_db.py --analyze
   ```

2. **Use `--dry-run` first**
   ```bash
   python scripts/stamp_production_db.py --stamp REVISION --dry-run
   ```

3. **Backup before stamping**
   ```bash
   pg_dump $DATABASE_URL > backup_before_stamp.sql
   ```

4. **Verify after stamping**
   ```bash
   alembic current
   alembic history --verbose
   ```

5. **Document the stamping**
   ```bash
   # In your deployment log:
   # "Stamped production DB with 5479068ccdaa on 2025-10-09 due to manual schema creation"
   ```

### ❌ DON'T:

1. **Don't use `--force` unless absolutely necessary**
   - Can cause migration conflicts
   - Might skip important validations

2. **Don't stamp without understanding**
   - Read the migration file first
   - Understand what state it represents

3. **Don't stamp randomly**
   - Use `--analyze` to get recommendation
   - Validate schema matches

4. **Don't skip verification**
   - Always check alembic_version after stamping
   - Test upgrade path

5. **Don't stamp in production without testing**
   - Test in staging first
   - Have rollback plan ready

---

## Advanced Usage

### Custom Database URL

```bash
# Use different database
export DATABASE_URL="postgresql://user:pass@different-host:5432/db"
python scripts/stamp_production_db.py --analyze
```

### Scripted Stamping (CI/CD)

```bash
#!/bin/bash
# automated_stamp.sh

set -e

# Analyze and capture output
ANALYSIS=$(python scripts/stamp_production_db.py --analyze)

# Extract recommended revision (requires parsing)
REVISION=$(echo "$ANALYSIS" | grep -oP 'python scripts/stamp_production_db.py --stamp \K[a-f0-9]+')

# Validate revision found
if [ -z "$REVISION" ]; then
    echo "ERROR: Could not determine revision to stamp"
    exit 1
fi

# Dry run
python scripts/stamp_production_db.py --stamp "$REVISION" --dry-run

# Prompt for confirmation (or auto-confirm in CI)
read -p "Proceed with stamping $REVISION? (yes/no): " CONFIRM

if [ "$CONFIRM" = "yes" ]; then
    # Actual stamp (would need to handle interactive confirmations)
    python scripts/stamp_production_db.py --stamp "$REVISION"

    # Verify
    alembic current
else
    echo "Stamping cancelled"
fi
```

---

## Related Commands

### Alembic Commands

```bash
# Show current revision
alembic current

# Show migration history
alembic history --verbose

# Show pending migrations
alembic upgrade head --sql

# Apply migrations
alembic upgrade head

# Downgrade one revision
alembic downgrade -1

# Generate new migration
alembic revision --autogenerate -m "description"
```

### Database Inspection

```bash
# List all tables
psql $DATABASE_URL -c "\dt"

# Show alembic_version
psql $DATABASE_URL -c "SELECT * FROM alembic_version;"

# Describe table structure
psql $DATABASE_URL -c "\d+ audit_logs"

# List indexes
psql $DATABASE_URL -c "\di"
```

---

## Support & References

### Documentation
- [Alembic Stamping](https://alembic.sqlalchemy.org/en/latest/cookbook.html#building-an-up-to-date-database-from-scratch)
- [Migration Best Practices](https://alembic.sqlalchemy.org/en/latest/cookbook.html)

### Getting Help
```bash
# Script help
python scripts/stamp_production_db.py --help

# Alembic help
alembic --help
alembic upgrade --help
```

### Contact
If stamping fails or you're unsure:
1. Don't proceed with production stamping
2. Review migration files in `alembic/versions/`
3. Consult with database administrator
4. Test in staging environment first

---

## Summary

**Stamping Workflow:**

```
1. ANALYZE       → Understand current state
   ↓
2. DRY RUN       → Preview changes safely
   ↓
3. BACKUP        → Ensure recovery possible
   ↓
4. STAMP         → Apply with confirmations
   ↓
5. VERIFY        → Check success
   ↓
6. TEST          → Validate migration path
```

**Remember:**
- 🔒 Stamping is a powerful operation
- ✅ Always validate before stamping
- 💾 Always backup before stamping
- 🧪 Always test in staging first
- 📝 Always document what you stamped and why
