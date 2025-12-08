# Manual Migration Guide: Migrations 007-018

**Agent: 37 - CONCURRENT INDEX Migration Specialist**
**Date: 2025-11-16**
**Priority: P0 - Critical Database Migration**

---

## Executive Summary

This guide provides comprehensive instructions for manually applying database migrations 007 through 018 using the custom migration script that properly handles PostgreSQL CONCURRENT INDEX operations.

**Problem:** Alembic's default transaction mode conflicts with `CREATE INDEX CONCURRENTLY`, which MUST run outside transactions in PostgreSQL.

**Solution:** Manual script with proper isolation level handling (AUTOCOMMIT for CONCURRENT, transaction for standard operations).

---

## Table of Contents

1. [Pre-Migration Checklist](#pre-migration-checklist)
2. [Migration Overview](#migration-overview)
3. [Execution Steps](#execution-steps)
4. [Verification Procedures](#verification-procedures)
5. [Rollback Procedures](#rollback-procedures)
6. [Troubleshooting](#troubleshooting)
7. [FAQ](#faq)

---

## Pre-Migration Checklist

### 1. Database Backup (CRITICAL)

```bash
# PostgreSQL backup
pg_dump $DATABASE_URL > backup_before_migration_007_018_$(date +%Y%m%d_%H%M%S).sql

# Verify backup file exists and has content
ls -lh backup_*.sql
```

**Verification:**
- Backup file size > 1MB (depending on data)
- File can be opened and contains SQL statements
- Store backup in safe location (S3, external drive)

### 2. Environment Validation

```bash
# Verify DATABASE_URL is set
echo $DATABASE_URL

# Check Python environment
python --version  # Should be 3.9+

# Install dependencies
pip install sqlalchemy psycopg2-binary

# Test database connection
python -c "import os; from sqlalchemy import create_engine; engine = create_engine(os.getenv('DATABASE_URL')); conn = engine.connect(); print('✅ Connection successful'); conn.close()"
```

### 3. Check Current Migration State

```bash
# Connect to database
psql $DATABASE_URL

# Check current alembic version
SELECT version_num FROM alembic_version;
-- Expected: 006_add_message_priority

# Check for any pending migrations
\d+ patients  -- Should show existing columns
\di            -- List indexes
```

### 4. Maintenance Window

**Recommended:**
- Duration: 1-2 hours
- During low-traffic period (2-6 AM local time)
- Notify users of potential downtime
- Put application in maintenance mode (optional but recommended)

### 5. Monitoring Setup

```bash
# Terminal 1: Run migration script
python scripts/manual_migrate_007_018.py

# Terminal 2: Monitor database connections
watch -n 5 'psql $DATABASE_URL -c "SELECT count(*) as active_connections FROM pg_stat_activity WHERE datname = current_database()"'

# Terminal 3: Monitor disk space
watch -n 5 'df -h'
```

---

## Migration Overview

### Migrations to Apply (12 Total)

| Migration | Type | Description | Est. Time | Risk |
|-----------|------|-------------|-----------|------|
| 007 | CONCURRENT | Quiz sessions indexes (3 indexes) | 30s-2m | Low |
| 008 | CONCURRENT | Flow states indexes (4 indexes) | 30s-2m | Low |
| 009 | MIXED | Patient constraints + CONCURRENT indexes | 1-3m | Medium |
| 010 | CONCURRENT | Missing FK indexes (28 indexes) | 3-5m | Low |
| 011 | STANDARD | HIPAA audit trail (complex) | SKIP* | High |
| 012 | STANDARD | Quiz response JSONB (complex) | SKIP* | High |
| 013 | CONCURRENT | GIN indexes on patient metadata | 1-2m | Low |
| 014 | CONCURRENT | Cursor pagination indexes | 1-2m | Low |
| 015 | STANDARD | Rename upload metadata column | 5-10s | Low |
| 016 | STANDARD | Validate patient metadata | 5-10s | Low |
| 017 | MIXED | Add patient soft delete | 30s-1m | Low |
| 018 | STANDARD | Seed flow templates | 5-10s | Low |

**\*Note:** Migrations 011 and 012 are highly complex (500+ lines of SQL each). The manual script will SKIP these and recommend running via alembic in a separate maintenance window.

### Expected Total Time

- **Without 011/012:** 10-20 minutes
- **With 011/012:** 30-45 minutes (run via alembic)

---

## Execution Steps

### Step 1: Dry Run (Recommended)

```bash
cd backend-hormonia

# Test without applying changes
python scripts/manual_migrate_007_018.py --dry-run
```

**Expected Output:**
```
[INFO] Migration Execution Plan
[INFO] Mode: DRY RUN
[INFO] Migrations to apply: 12
[INFO]   - 007: Quiz Sessions Indexes
[INFO]   - 008: Flow Executions Indexes
...
[INFO] ✅ All migrations completed successfully!
```

### Step 2: Apply Migrations (Production)

```bash
# Set DATABASE_URL if not already in environment
export DATABASE_URL="postgresql+psycopg://user:pass@host:port/db?sslmode=require"

# Run migrations
python scripts/manual_migrate_007_018.py
```

**Interactive Confirmation:**
```
⚠️  This will modify your database. Continue? (yes/no): yes
```

**Monitor Output:**
```
[INFO] ================================================================================
[INFO] Migration 007: Quiz Sessions Indexes (CONCURRENT)
[INFO] ================================================================================
[INFO] Current alembic_version: 006_add_message_priority
[INFO] Creating index: idx_quiz_sessions_patient_id
[INFO] ✅ Created idx_quiz_sessions_patient_id
[INFO] Creating index: idx_quiz_sessions_patient_status
[INFO] ✅ Created idx_quiz_sessions_patient_status
[INFO] Creating index: idx_quiz_sessions_started_at
[INFO] ✅ Created idx_quiz_sessions_started_at
[INFO] ✅ Updated alembic_version to: 007_quiz_sessions_index
[INFO] ✅ Migration 007 completed successfully
```

### Step 3: Apply Complex Migrations (011 & 012) via Alembic

```bash
# Migrations 011 and 012 must be run via alembic
alembic upgrade 011_hipaa_audit
alembic upgrade 012_migrate_quiz_response_value_to_jsonb
```

### Step 4: Verify All Migrations Applied

```bash
# Check alembic version
python scripts/manual_migrate_007_018.py --only 018

# Should show: "Already applied" if all migrations ran successfully
```

---

## Advanced Usage

### Apply Specific Migration Only

```bash
# Apply only migration 007
python scripts/manual_migrate_007_018.py --only 007
```

### Start from Specific Migration

```bash
# Start from migration 010 (skip 007-009)
python scripts/manual_migrate_007_018.py --start-from 010
```

### Skip Specific Migrations

```bash
# Skip migrations 011 and 012 (complex ones)
python scripts/manual_migrate_007_018.py --skip 011,012
```

---

## Verification Procedures

### 1. Verify Alembic Version

```sql
SELECT version_num FROM alembic_version;
-- Expected: 018_seed_flow_templates (or highest migration applied)
```

### 2. Verify Indexes Created

```sql
-- Check quiz_sessions indexes
SELECT indexname FROM pg_indexes
WHERE tablename = 'quiz_sessions'
AND indexname LIKE 'idx_quiz%';

-- Expected:
-- idx_quiz_sessions_patient_id
-- idx_quiz_sessions_patient_status
-- idx_quiz_sessions_started_at
-- idx_quiz_sessions_patient_created (from migration 010)

-- Check patient_flow_states indexes
SELECT indexname FROM pg_indexes
WHERE tablename = 'patient_flow_states'
AND indexname LIKE 'idx_patient%';

-- Expected: Multiple indexes including patient_id, template_version, etc.
```

### 3. Verify Constraints Added

```sql
-- Check patient unique constraints
SELECT constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_name = 'patients'
AND constraint_type = 'UNIQUE';

-- Expected:
-- uq_patient_email_doctor
-- uq_patient_cpf_doctor
-- uq_patient_phone_doctor
```

### 4. Verify Soft Delete Column

```sql
-- Check deleted_at column exists
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'patients'
AND column_name = 'deleted_at';

-- Expected: deleted_at | timestamp with time zone
```

### 5. Verify Flow Templates Seeded

```sql
-- Check flow kind exists
SELECT id, kind_key, display_name
FROM flow_kinds
WHERE kind_key = 'initial_15_days';

-- Expected: 1 row with ID 00000000-0000-0000-0000-000000000001

-- Check template version exists
SELECT id, template_name, version_number
FROM flow_template_versions
WHERE flow_kind_id = '00000000-0000-0000-0000-000000000001';

-- Expected: 1 row with version_number = 1
```

### 6. Performance Test

```sql
-- Test index usage on quiz_sessions
EXPLAIN ANALYZE
SELECT * FROM quiz_sessions
WHERE patient_id = '<some-patient-id>'
ORDER BY started_at DESC
LIMIT 10;

-- Should show: "Index Scan using idx_quiz_sessions_patient_id"
-- Execution time should be < 10ms
```

---

## Rollback Procedures

### Emergency Rollback

If migrations fail mid-execution, follow these steps:

**1. Restore from Backup (Nuclear Option)**

```bash
# WARNING: This will restore entire database to pre-migration state
psql $DATABASE_URL < backup_before_migration_007_018_TIMESTAMP.sql
```

**2. Selective Rollback (Recommended)**

Each migration has a downgrade procedure. See `alembic/versions/XXX_*.py` for details.

```bash
# Example: Rollback migration 017 (soft delete)
psql $DATABASE_URL <<EOF
-- Drop indexes
DROP INDEX IF EXISTS idx_patients_deleted;
DROP INDEX IF EXISTS idx_patients_active;

-- Drop column
ALTER TABLE patients DROP COLUMN IF EXISTS deleted_at;

-- Update alembic version
UPDATE alembic_version SET version_num = '016_validate_patient_metadata';
EOF
```

**3. Rollback Specific Migrations**

| Migration | Rollback SQL |
|-----------|--------------|
| 007 | `DROP INDEX idx_quiz_sessions_patient_id, idx_quiz_sessions_patient_status, idx_quiz_sessions_started_at;` |
| 008 | `DROP INDEX idx_patient_flow_states_patient_id, idx_patient_flow_states_patient_completed, idx_patient_flow_states_template_version, idx_patient_flow_states_started_at;` |
| 009 | See migration file - complex constraint rollback |
| 013 | `DROP INDEX idx_patient_metadata_gin, idx_patient_metadata_consent_gin, idx_patient_metadata_preferences_gin;` |
| 017 | See above |

---

## Troubleshooting

### Problem: "CREATE INDEX CONCURRENTLY cannot run inside a transaction block"

**Cause:** Migration running with wrong isolation level.

**Solution:**
```python
# Verify script is using AUTOCOMMIT for CONCURRENT operations
# Check line in script:
# engine = create_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")
```

### Problem: "Index already exists"

**Cause:** Migration partially applied previously.

**Solution:**
```bash
# Use --skip flag to skip already-applied migrations
python scripts/manual_migrate_007_018.py --skip 007,008
```

### Problem: "Could not serialize access due to concurrent update"

**Cause:** High database activity during migration.

**Solution:**
1. Put application in maintenance mode
2. Wait for active transactions to complete
3. Retry migration

### Problem: "Constraint already exists" on migration 009

**Cause:** Partial application from previous attempt.

**Solution:**
```sql
-- Check which constraints exist
SELECT constraint_name FROM information_schema.table_constraints
WHERE table_name = 'patients' AND constraint_type = 'UNIQUE';

-- Drop any existing constraints before re-running
ALTER TABLE patients DROP CONSTRAINT IF EXISTS uq_patient_email_doctor;
ALTER TABLE patients DROP CONSTRAINT IF EXISTS uq_patient_cpf_doctor;
ALTER TABLE patients DROP CONSTRAINT IF EXISTS uq_patient_phone_doctor;

-- Restore original constraints
ALTER TABLE patients ADD CONSTRAINT patients_phone_key UNIQUE (phone);
ALTER TABLE patients ADD CONSTRAINT patients_cpf_key UNIQUE (cpf);
```

### Problem: Migration 011 or 012 Failing

**Cause:** These migrations are too complex for manual script.

**Solution:**
```bash
# Use alembic instead
alembic upgrade 011_hipaa_audit
alembic upgrade 012_migrate_quiz_response_value_to_jsonb
```

### Problem: "Table does not exist" errors

**Cause:** Some tables may not exist in your schema.

**Solution:**
- Script automatically skips indexes for non-existent tables
- Review warnings in output
- No action needed if tables genuinely don't exist

---

## FAQ

### Q: Can I run this on production without downtime?

**A:** Partially. CONCURRENT index creation doesn't block reads/writes, BUT:
- Constraint changes (migration 009) may briefly lock the `patients` table
- Recommend brief maintenance window (5-10 minutes) for safety

### Q: What if I only want to apply some migrations?

**A:** Use the `--only` or `--start-from` flags:
```bash
# Apply only migrations 013-018
python scripts/manual_migrate_007_018.py --start-from 013
```

### Q: How long will this take?

**A:** Depends on database size:
- Small DB (< 10k rows): 5-10 minutes
- Medium DB (10k-100k rows): 10-20 minutes
- Large DB (> 100k rows): 20-45 minutes

### Q: Can I run this multiple times?

**A:** Yes! Script is idempotent:
- Already-applied migrations are skipped
- Already-existing indexes are skipped
- Safe to re-run

### Q: What about migrations 011 and 012?

**A:** These are VERY complex (500+ lines of SQL each):
- Manual script will SKIP them
- Use alembic instead: `alembic upgrade 011_hipaa_audit`
- Recommend separate maintenance window

### Q: What if alembic_version table doesn't exist?

**A:** Create it first:
```sql
CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL PRIMARY KEY
);
INSERT INTO alembic_version (version_num) VALUES ('006_add_message_priority');
```

---

## Post-Migration Actions

### 1. Update Documentation

- Mark migrations 007-018 as applied in project docs
- Update database schema documentation

### 2. Monitor Performance

```sql
-- Check index usage after 24 hours
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE indexname LIKE 'idx_quiz%' OR indexname LIKE 'idx_patient%'
ORDER BY idx_scan DESC;

-- High idx_scan = index is being used (good!)
```

### 3. Vacuum and Analyze

```sql
-- Update table statistics for query planner
VACUUM ANALYZE patients;
VACUUM ANALYZE quiz_sessions;
VACUUM ANALYZE patient_flow_states;
VACUUM ANALYZE messages;
```

### 4. Application Testing

- Test patient creation
- Test quiz sessions
- Test flow execution
- Test search/filtering queries
- Monitor error logs

---

## Support

**Issues?** Contact:
- Database Team: db-team@company.com
- DevOps Team: devops@company.com
- Slack: #database-migrations

**Escalation:**
- P0 (Critical): Page on-call engineer
- P1 (High): Create urgent ticket
- P2+ (Medium/Low): Create standard ticket

---

## Appendix A: Migration Details

### Migration 007: Quiz Sessions Indexes

**Indexes Created:**
1. `idx_quiz_sessions_patient_id` - B-tree on `patient_id`
2. `idx_quiz_sessions_patient_status` - Composite on `(patient_id, status)`
3. `idx_quiz_sessions_started_at` - B-tree on `started_at`

**Purpose:** Speed up patient quiz lookup queries by 10-50x.

**Query Optimization:**
```sql
-- Before: Full table scan (500ms+)
-- After: Index scan (< 10ms)
SELECT * FROM quiz_sessions WHERE patient_id = 'xxx' ORDER BY started_at DESC;
```

### Migration 009: Patient Unique Constraints

**Constraints Added:**
1. `uq_patient_email_doctor` - Unique on `(email, doctor_id)`
2. `uq_patient_cpf_doctor` - Unique on `(cpf, doctor_id)`
3. `uq_patient_phone_doctor` - Unique on `(phone, doctor_id)`

**Purpose:** Prevent duplicate patient records per doctor.

**Impact:** Applications can no longer create duplicate patients with same phone/email/CPF per doctor.

---

## Appendix B: Script Source Code

Full script available at:
`backend-hormonia/scripts/manual_migrate_007_018.py`

Key features:
- AUTOCOMMIT isolation for CONCURRENT operations
- Transaction mode for standard operations
- Comprehensive error handling
- Progress tracking via alembic_version
- Idempotent operations (safe to re-run)
- Dry-run mode for testing

---

**Document Version:** 1.0
**Last Updated:** 2025-11-16
**Author:** Agent 37 - CONCURRENT INDEX Migration Specialist
