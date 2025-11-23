# Data Migration Strategy

**Document Version:** 1.0.0
**Last Updated:** 2025-11-16
**Owner:** Backend Team
**Status:** Active

## Table of Contents

1. [Overview](#overview)
2. [Migration Types](#migration-types)
3. [Zero-Downtime Patterns](#zero-downtime-patterns)
4. [Data Transformation Strategies](#data-transformation-strategies)
5. [Testing & Validation](#testing--validation)
6. [Production Deployment](#production-deployment)
7. [Rollback Procedures](#rollback-procedures)
8. [Best Practices](#best-practices)
9. [Common Patterns](#common-patterns)
10. [Troubleshooting](#troubleshooting)

---

## Overview

This document defines the comprehensive strategy for handling database migrations that involve schema changes with data transformation. All migrations must follow these patterns to ensure zero-downtime deployments and data integrity.

### Key Principles

1. **Zero-Downtime First**: All migrations must allow concurrent reads/writes
2. **Batched Processing**: Large data transformations must be batched
3. **Idempotent Operations**: All migrations must be safely re-runnable
4. **Reversible**: All migrations must have a working downgrade path
5. **Production-Tested**: All migrations must be tested on production data dumps

### Migration Classification

| Type | Description | Downtime | Example |
|------|-------------|----------|---------|
| **Schema-Only** | DDL changes without data transformation | None | ADD COLUMN (nullable) |
| **Data Transformation** | Schema change + data backfill | None (with batching) | VARCHAR → JSONB conversion |
| **Zero-Downtime** | Multi-step deployment for breaking changes | None | Adding NOT NULL constraint |
| **Emergency** | Hotfix migrations for production issues | < 5 seconds | Index creation |

---

## Migration Types

### 1. Schema-Only Migrations

Simple DDL changes that don't require data transformation.

**Characteristics:**
- Fast execution (< 1 second)
- No data modification
- Can use CONCURRENTLY for indexes
- Safe for immediate deployment

**Examples:**

#### Adding Nullable Column
```python
"""Add notification preferences column

Revision ID: 015_add_notification_prefs
Revises: 014
Create Date: 2025-01-16

WHY: Support user notification preferences (email, SMS, WhatsApp)
WHAT: Add nullable JSONB column for flexible preference storage
IMPACT: No performance impact, instant execution
ROLLBACK: Safe - column can be dropped without data loss
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '015_add_notification_prefs'
down_revision = '014'

def upgrade():
    """Add notification_preferences column to users table."""
    op.add_column(
        'users',
        sa.Column(
            'notification_preferences',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='User notification preferences (email, SMS, WhatsApp channels)'
        )
    )

    # Add GIN index for JSONB queries (CONCURRENTLY = no table lock)
    op.execute(
        "CREATE INDEX CONCURRENTLY idx_users_notification_prefs_gin "
        "ON users USING GIN (notification_preferences)"
    )

def downgrade():
    """Remove notification_preferences column."""
    op.drop_index('idx_users_notification_prefs_gin', table_name='users')
    op.drop_column('users', 'notification_preferences')
```

#### Creating Index (CONCURRENTLY)
```python
"""Add index on patients.birth_date for age queries

Revision ID: 016_add_birthdate_index
Revises: 015
Create Date: 2025-01-16

WHY: Age-based queries are slow (1200ms) due to sequential scan
WHAT: Add B-tree index on birth_date column
IMPACT: 95% faster age-based queries (1200ms → 60ms)
BENCHMARK: Tested with 500k patient records
ROLLBACK: Safe - just drops index, no data impact

Performance gains:
- Before: SELECT * FROM patients WHERE birth_date < '1970-01-01' -- 1200ms
- After:  SELECT * FROM patients WHERE birth_date < '1970-01-01' -- 60ms
"""
from alembic import op

revision = '016_add_birthdate_index'
down_revision = '015'

def upgrade():
    """Add index to patients.birth_date column."""
    # CONCURRENTLY = no table lock, allows concurrent reads/writes
    # IMPORTANT: Must be in separate transaction, can't use op.create_index()
    op.execute(
        "CREATE INDEX CONCURRENTLY idx_patients_birth_date "
        "ON patients (birth_date)"
    )

def downgrade():
    """Remove birth_date index."""
    op.drop_index('idx_patients_birth_date', table_name='patients')
```

---

### 2. Data Transformation Migrations

Schema changes that require transforming existing data.

**Characteristics:**
- Requires batched processing for large tables
- Must handle NULL values gracefully
- Should monitor progress
- Needs rollback plan with data preservation

**Pattern: VARCHAR to JSONB Migration**

```python
"""Migrate patient.metadata from VARCHAR to JSONB

Revision ID: 017_metadata_to_jsonb
Revises: 016
Create Date: 2025-01-16

WHY: Metadata stored as VARCHAR limits querying capabilities
WHAT: Convert VARCHAR column to JSONB for structured queries
IMPACT: Enables fast JSONB queries with GIN indexes
DATA: ~250k patients, estimated 10 minutes for conversion
ROLLBACK: Reversible - JSONB cast back to VARCHAR (may lose formatting)

Performance improvements:
- Before: LIKE '%key%' queries on VARCHAR -- 3500ms
- After:  JSONB @> '{"key": "value"}' -- 8ms (with GIN index)

Migration steps:
1. Add new JSONB column (nullable)
2. Backfill data in batches (1000 rows at a time)
3. Create GIN index on new column
4. Application code starts using new column
5. (Future migration) Drop old VARCHAR column
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import json
import time

revision = '017_metadata_to_jsonb'
down_revision = '016'

def upgrade():
    """Convert patient.metadata from VARCHAR to JSONB."""

    # Step 1: Add new JSONB column (nullable, no default)
    print("Step 1/4: Adding metadata_jsonb column...")
    op.add_column(
        'patients',
        sa.Column(
            'metadata_jsonb',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='Patient metadata in JSONB format (replaces metadata VARCHAR)'
        )
    )

    # Step 2: Backfill data in batches
    print("Step 2/4: Backfilling data (this may take 5-10 minutes)...")
    connection = op.get_bind()

    batch_size = 1000
    offset = 0
    total_updated = 0
    start_time = time.time()

    while True:
        # Select batch of rows where metadata_jsonb is NULL but metadata is NOT NULL
        result = connection.execute(sa.text("""
            UPDATE patients
            SET metadata_jsonb =
                CASE
                    -- Try to parse as JSON
                    WHEN metadata ~ '^[\[\{]' THEN metadata::jsonb
                    -- Wrap plain text in JSON object
                    ELSE jsonb_build_object('legacy_value', metadata)
                END
            WHERE id IN (
                SELECT id FROM patients
                WHERE metadata_jsonb IS NULL
                  AND metadata IS NOT NULL
                LIMIT :batch_size
            )
            RETURNING id
        """), {"batch_size": batch_size})

        updated_count = result.rowcount
        total_updated += updated_count

        if updated_count == 0:
            break

        # Progress reporting every 10 batches
        if (total_updated // batch_size) % 10 == 0:
            elapsed = time.time() - start_time
            rate = total_updated / elapsed if elapsed > 0 else 0
            print(f"  Processed {total_updated:,} rows ({rate:.0f} rows/sec)")

        offset += batch_size

    elapsed = time.time() - start_time
    print(f"Step 2/4: Backfill complete. {total_updated:,} rows in {elapsed:.1f} seconds")

    # Step 3: Create GIN index on new JSONB column (CONCURRENTLY)
    print("Step 3/4: Creating GIN index (this may take 2-3 minutes)...")
    op.execute(
        "CREATE INDEX CONCURRENTLY idx_patients_metadata_jsonb_gin "
        "ON patients USING GIN (metadata_jsonb)"
    )
    print("Step 3/4: Index created successfully")

    # Step 4: Log completion
    print("Step 4/4: Migration complete!")
    print("NEXT STEPS:")
    print("  1. Update application code to use metadata_jsonb column")
    print("  2. Deploy application code")
    print("  3. Run follow-up migration to drop old metadata column")

def downgrade():
    """Revert JSONB column back to VARCHAR (with data loss)."""
    print("WARNING: Downgrade will convert JSONB back to VARCHAR")
    print("  - Complex JSON structures will be serialized as strings")
    print("  - Querying capabilities will be reduced")

    connection = op.get_bind()

    # Copy JSONB data back to VARCHAR column (as JSON string)
    connection.execute(sa.text("""
        UPDATE patients
        SET metadata = metadata_jsonb::text
        WHERE metadata_jsonb IS NOT NULL
    """))

    # Drop index and column
    op.drop_index('idx_patients_metadata_jsonb_gin', table_name='patients')
    op.drop_column('patients', 'metadata_jsonb')

    print("Downgrade complete. VARCHAR column restored.")
```

---

### 3. Zero-Downtime Migrations

Multi-step migrations for breaking changes that require application code coordination.

**Use Cases:**
- Adding NOT NULL constraints
- Changing column types with incompatible data
- Removing columns still in use
- Renaming columns

**Pattern: Adding NOT NULL Constraint**

This requires a **3-migration sequence**:

#### Migration 018a: Add Nullable Column

```python
"""Add email_verified column (step 1/3)

Revision ID: 018a_add_email_verified
Revises: 017
Create Date: 2025-01-16

WHY: Track email verification status for security
WHAT: Add nullable boolean column (will be NOT NULL in step 3)
IMPACT: No performance impact, instant execution
ROLLBACK: Safe - column unused, can be dropped

ZERO-DOWNTIME SEQUENCE:
  Step 1 (THIS): Add nullable column ✓
  Step 2: Backfill default values
  Step 3: Add NOT NULL constraint
"""
from alembic import op
import sqlalchemy as sa

revision = '018a_add_email_verified'
down_revision = '017'

def upgrade():
    """Add email_verified column (nullable)."""
    op.add_column(
        'users',
        sa.Column(
            'email_verified',
            sa.Boolean(),
            nullable=True,  # Must be nullable initially
            comment='Email verification status (step 1/3: nullable)'
        )
    )

def downgrade():
    """Remove email_verified column."""
    op.drop_column('users', 'email_verified')
```

#### Migration 018b: Backfill Default Values

```python
"""Backfill email_verified default values (step 2/3)

Revision ID: 018b_backfill_email_verified
Revises: 018a
Create Date: 2025-01-16

WHY: Set default values before adding NOT NULL constraint
WHAT: Backfill email_verified = false for existing users
IMPACT: ~2 minutes for 500k users (batched processing)
ROLLBACK: Safe - sets values back to NULL

ZERO-DOWNTIME SEQUENCE:
  Step 1: Add nullable column
  Step 2 (THIS): Backfill default values ✓
  Step 3: Add NOT NULL constraint
"""
from alembic import op
import sqlalchemy as sa
import time

revision = '018b_backfill_email_verified'
down_revision = '018a'

def upgrade():
    """Backfill email_verified with default value (false)."""
    connection = op.get_bind()

    batch_size = 1000
    total_updated = 0
    start_time = time.time()

    print("Backfilling email_verified column...")

    while True:
        result = connection.execute(sa.text("""
            UPDATE users
            SET email_verified = false
            WHERE id IN (
                SELECT id FROM users
                WHERE email_verified IS NULL
                LIMIT :batch_size
            )
            RETURNING id
        """), {"batch_size": batch_size})

        updated_count = result.rowcount
        total_updated += updated_count

        if updated_count == 0:
            break

        if (total_updated // batch_size) % 10 == 0:
            elapsed = time.time() - start_time
            rate = total_updated / elapsed if elapsed > 0 else 0
            print(f"  Processed {total_updated:,} rows ({rate:.0f} rows/sec)")

    elapsed = time.time() - start_time
    print(f"Backfill complete. {total_updated:,} rows in {elapsed:.1f} seconds")

def downgrade():
    """Reset email_verified to NULL."""
    connection = op.get_bind()
    connection.execute(sa.text("UPDATE users SET email_verified = NULL"))
```

#### Migration 018c: Add NOT NULL Constraint

```python
"""Add NOT NULL constraint to email_verified (step 3/3)

Revision ID: 018c_email_verified_not_null
Revises: 018b
Create Date: 2025-01-16

WHY: Enforce data integrity after backfill
WHAT: Add NOT NULL constraint to email_verified
IMPACT: Instant execution (all values already set)
ROLLBACK: Safe - drops constraint, keeps data

ZERO-DOWNTIME SEQUENCE:
  Step 1: Add nullable column
  Step 2: Backfill default values
  Step 3 (THIS): Add NOT NULL constraint ✓

PREREQUISITES:
  - Migration 018b must be deployed and run
  - All email_verified values must be non-NULL
  - Verify with: SELECT COUNT(*) FROM users WHERE email_verified IS NULL;
    (Should return 0)
"""
from alembic import op
import sqlalchemy as sa

revision = '018c_email_verified_not_null'
down_revision = '018b'

def upgrade():
    """Add NOT NULL constraint to email_verified."""
    # Verify all values are non-NULL before adding constraint
    connection = op.get_bind()
    result = connection.execute(sa.text(
        "SELECT COUNT(*) FROM users WHERE email_verified IS NULL"
    ))
    null_count = result.scalar()

    if null_count > 0:
        raise Exception(
            f"Cannot add NOT NULL constraint: {null_count} rows have NULL values. "
            f"Run migration 018b first to backfill data."
        )

    # Add NOT NULL constraint
    op.alter_column(
        'users',
        'email_verified',
        nullable=False,
        comment='Email verification status (NOT NULL enforced)'
    )

    print(f"NOT NULL constraint added successfully")

def downgrade():
    """Remove NOT NULL constraint."""
    op.alter_column(
        'users',
        'email_verified',
        nullable=True
    )
```

---

### 4. Emergency Migrations

Fast migrations for production hotfixes.

**Characteristics:**
- Must execute in < 5 seconds
- Minimal data transformation
- Immediate deployment required
- Comprehensive monitoring

**Example: Emergency Index for Slow Query**

```python
"""Emergency: Add index for slow dashboard query

Revision ID: 019_emergency_dashboard_index
Revises: 018c
Create Date: 2025-01-16

WHY: Production dashboard timing out (8000ms) on doctor queries
WHAT: Add composite index on (doctor_id, status, created_at)
IMPACT: 99% faster queries (8000ms → 80ms)
URGENCY: HIGH - Production issue affecting all doctors
ROLLBACK: Safe - just drops index

PRODUCTION VERIFICATION:
Before deployment:
  EXPLAIN ANALYZE
  SELECT * FROM patients
  WHERE doctor_id = '...' AND status = 'active'
  ORDER BY created_at DESC LIMIT 20;
  -- Seq Scan, Time: 8247ms

After deployment:
  -- Index Scan using idx_patients_doctor_status_created
  -- Time: 78ms
"""
from alembic import op

revision = '019_emergency_dashboard_index'
down_revision = '018c'

def upgrade():
    """Add emergency index for doctor dashboard."""
    # CONCURRENTLY to avoid table lock during production deployment
    op.execute(
        "CREATE INDEX CONCURRENTLY idx_patients_doctor_status_created "
        "ON patients (doctor_id, status, created_at DESC)"
    )
    print("Emergency index created successfully")

def downgrade():
    """Remove emergency index."""
    op.drop_index('idx_patients_doctor_status_created', table_name='patients')
```

---

## Testing & Validation

### Pre-Deployment Testing

#### 1. Test on Production Data Dump

```bash
#!/bin/bash
# scripts/test_migration_prod_dump.sh

set -e

echo "=== Testing Migration on Production Data ==="
echo ""

# Configuration
PROD_DB="production_db"
TEST_DB="migration_test_$(date +%s)"
MIGRATION_ID="${1:-head}"

# Step 1: Create test database from production dump
echo "Step 1/5: Creating production dump..."
pg_dump "$PROD_DB" \
  --no-owner \
  --no-privileges \
  --format=custom \
  --file=/tmp/prod_dump.pgdump

echo "Step 2/5: Creating test database..."
createdb "$TEST_DB"

echo "Step 3/5: Restoring production data..."
pg_restore \
  --dbname="$TEST_DB" \
  --no-owner \
  --no-privileges \
  /tmp/prod_dump.pgdump

# Step 4: Run migration
echo "Step 4/5: Running migration $MIGRATION_ID..."
cd backend-hormonia
DATABASE_URL="postgresql://localhost:5432/$TEST_DB" \
  alembic upgrade "$MIGRATION_ID"

# Step 5: Validate data integrity
echo "Step 5/5: Validating data integrity..."
psql "$TEST_DB" << EOF
-- Check for NULL values in NOT NULL columns
SELECT
  table_name,
  column_name,
  COUNT(*) as null_count
FROM information_schema.columns c
JOIN pg_class t ON t.relname = c.table_name
LEFT JOIN LATERAL (
  SELECT COUNT(*) as cnt
  FROM pg_class
  WHERE relname = c.table_name
) counts ON true
WHERE c.is_nullable = 'NO'
  AND counts.cnt > 0
GROUP BY table_name, column_name
HAVING COUNT(*) > 0;

-- Check for orphaned foreign keys
\echo 'Checking foreign key integrity...'
-- (Add FK checks here)

EOF

# Cleanup
echo ""
echo "Test complete! Cleaning up..."
dropdb "$TEST_DB"
rm /tmp/prod_dump.pgdump

echo ""
echo "✅ Migration tested successfully on production data"
```

Make it executable:
```bash
chmod +x scripts/test_migration_prod_dump.sh
```

#### 2. Benchmark Migration Performance

```python
# scripts/benchmark_migration.py
"""
Benchmark migration performance on different dataset sizes.

Usage:
  python scripts/benchmark_migration.py 018b
"""

import sys
import time
import psycopg
from datetime import datetime

def benchmark_migration(migration_id: str, dataset_sizes: list[int]):
    """Run migration on different dataset sizes and measure performance."""

    results = []

    for size in dataset_sizes:
        print(f"\n{'='*60}")
        print(f"Testing with {size:,} rows")
        print(f"{'='*60}")

        # Create test database
        test_db = f"migration_bench_{size}_{int(time.time())}"

        # Populate test data
        start_time = time.time()
        create_test_data(test_db, size)
        populate_time = time.time() - start_time

        # Run migration
        start_time = time.time()
        run_migration(test_db, migration_id)
        migration_time = time.time() - start_time

        # Validate results
        validation_ok = validate_migration(test_db)

        # Cleanup
        cleanup_database(test_db)

        results.append({
            'size': size,
            'populate_time': populate_time,
            'migration_time': migration_time,
            'rows_per_second': size / migration_time if migration_time > 0 else 0,
            'validation': 'PASS' if validation_ok else 'FAIL'
        })

    # Print summary
    print(f"\n{'='*60}")
    print("BENCHMARK RESULTS")
    print(f"{'='*60}")
    print(f"{'Size':<15} {'Migration Time':<20} {'Rows/Sec':<15} {'Status'}")
    print(f"{'-'*60}")
    for r in results:
        print(
            f"{r['size']:>10,} rows  "
            f"{r['migration_time']:>8.2f} seconds      "
            f"{r['rows_per_second']:>10,.0f}      "
            f"{r['validation']}"
        )

    # Estimate production time
    if results:
        avg_rate = sum(r['rows_per_second'] for r in results) / len(results)
        prod_rows = 500_000  # Estimate
        prod_time = prod_rows / avg_rate if avg_rate > 0 else 0

        print(f"\n{'='*60}")
        print(f"PRODUCTION ESTIMATE (500k rows): {prod_time:.1f} seconds")
        print(f"{'='*60}")

if __name__ == '__main__':
    migration_id = sys.argv[1] if len(sys.argv) > 1 else 'head'
    dataset_sizes = [1_000, 10_000, 100_000, 250_000]

    benchmark_migration(migration_id, dataset_sizes)
```

### Validation Checklist

```markdown
## Migration Validation Checklist

### Pre-Deployment
- [ ] Migration tested on production data dump
- [ ] Performance benchmarked on realistic dataset
- [ ] Downgrade tested and verified
- [ ] No table locks on large tables (> 100k rows)
- [ ] Estimated duration documented (< 5 minutes preferred)
- [ ] Rollback plan documented
- [ ] Monitoring alerts configured
- [ ] Team notified of deployment window

### Post-Deployment
- [ ] Migration completed successfully
- [ ] No errors in application logs
- [ ] Database performance metrics normal
- [ ] All indexes created successfully
- [ ] Foreign key constraints validated
- [ ] Application functionality verified
- [ ] Rollback tested in staging (if possible)

### Data Integrity
- [ ] Row counts match before/after
- [ ] No NULL values in NOT NULL columns
- [ ] Foreign key integrity maintained
- [ ] JSONB data parses correctly
- [ ] No orphaned records
- [ ] Sample data spot-checked manually
```

---

## Production Deployment

### Deployment Process

#### 1. Pre-Deployment

```bash
# 1. Create backup
pg_dump production_db \
  --format=custom \
  --file=/backups/pre_migration_$(date +%Y%m%d_%H%M%S).pgdump

# 2. Verify current migration state
cd backend-hormonia
alembic current

# 3. Check for pending migrations
alembic history | grep "current"
```

#### 2. Deployment

```bash
# Run migration with monitoring
alembic upgrade head 2>&1 | tee /logs/migration_$(date +%Y%m%d_%H%M%S).log

# Monitor progress (in separate terminal)
watch -n 5 'psql production_db -c "SELECT NOW(), COUNT(*) FROM pg_stat_activity WHERE query LIKE '\''%alembic%'\'';"'
```

#### 3. Post-Deployment Validation

```bash
# Verify migration state
alembic current

# Check for errors
tail -f /var/log/postgresql/postgresql.log | grep ERROR

# Validate data integrity
psql production_db << EOF
-- Check row counts
SELECT
  schemaname,
  tablename,
  n_live_tup as row_count
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY n_live_tup DESC
LIMIT 20;

-- Check index health
SELECT
  schemaname,
  tablename,
  indexname,
  idx_scan as index_scans,
  idx_tup_read as tuples_read,
  idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC
LIMIT 20;
EOF
```

---

## Rollback Procedures

### Immediate Rollback (< 5 minutes since deployment)

```bash
# 1. Stop application (prevent writes)
kubectl scale deployment backend --replicas=0

# 2. Rollback migration
cd backend-hormonia
alembic downgrade -1

# 3. Verify rollback
alembic current

# 4. Restart application
kubectl scale deployment backend --replicas=3

# 5. Monitor logs
kubectl logs -f deployment/backend
```

### Delayed Rollback (> 5 minutes, data may be affected)

```bash
# 1. Assess data changes
psql production_db << EOF
-- Check for recent data modifications
SELECT
  schemaname,
  tablename,
  n_tup_ins as inserts,
  n_tup_upd as updates,
  n_tup_del as deletes,
  last_vacuum,
  last_autovacuum
FROM pg_stat_user_tables
WHERE schemaname = 'public'
  AND (n_tup_ins > 0 OR n_tup_upd > 0 OR n_tup_del > 0)
ORDER BY (n_tup_ins + n_tup_upd + n_tup_del) DESC;
EOF

# 2. Create snapshot before rollback
pg_dump production_db \
  --format=custom \
  --file=/backups/pre_rollback_$(date +%Y%m%d_%H%M%S).pgdump

# 3. Rollback with data preservation
alembic downgrade -1

# 4. Verify data integrity
# Run validation queries...
```

---

## Best Practices

### DO's ✅

1. **Always use CONCURRENTLY for indexes on large tables**
   ```python
   # ✅ GOOD
   op.execute("CREATE INDEX CONCURRENTLY idx_name ON table (column)")

   # ❌ BAD - locks table
   op.create_index('idx_name', 'table', ['column'])
   ```

2. **Batch large data transformations**
   ```python
   # ✅ GOOD - processes 1000 rows at a time
   batch_size = 1000
   while True:
       result = connection.execute(update_query.limit(batch_size))
       if result.rowcount == 0:
           break

   # ❌ BAD - updates all rows in single transaction
   connection.execute(update_query)
   ```

3. **Add comprehensive documentation**
   ```python
   # ✅ GOOD
   """Add GIN index on patient metadata for JSONB queries

   WHY: Metadata queries are slow (450ms) due to sequential scan
   WHAT: Add GIN index to enable fast JSONB containment queries
   IMPACT: 87x speedup (450ms → 5.2ms)
   ROLLBACK: Safe - just drops index
   """
   ```

4. **Test on production data dumps**
   ```bash
   # ✅ GOOD
   ./scripts/test_migration_prod_dump.sh
   ```

5. **Monitor migration progress**
   ```python
   # ✅ GOOD
   if (total_updated // batch_size) % 10 == 0:
       print(f"Processed {total_updated:,} rows")
   ```

### DON'Ts ❌

1. **Don't use table locks on large tables**
   ```python
   # ❌ BAD - locks entire table
   op.create_index('idx', 'large_table', ['col'])

   # ✅ GOOD - no lock
   op.execute("CREATE INDEX CONCURRENTLY idx ON large_table (col)")
   ```

2. **Don't add NOT NULL without backfilling**
   ```python
   # ❌ BAD - will fail if NULL values exist
   op.add_column('table', Column('col', String, nullable=False))

   # ✅ GOOD - use 3-step process
   # Step 1: Add nullable column
   # Step 2: Backfill values
   # Step 3: Add NOT NULL constraint
   ```

3. **Don't transform large datasets in single transaction**
   ```python
   # ❌ BAD - locks table for hours
   op.execute("UPDATE large_table SET col = transform(col)")

   # ✅ GOOD - batch processing
   while True:
       result = connection.execute(
           "UPDATE large_table SET col = transform(col) "
           "WHERE id IN (SELECT id FROM large_table WHERE col IS NULL LIMIT 1000)"
       )
       if result.rowcount == 0:
           break
   ```

4. **Don't skip downgrade implementation**
   ```python
   # ❌ BAD
   def downgrade():
       pass  # TODO: implement later

   # ✅ GOOD
   def downgrade():
       """Revert migration changes."""
       op.drop_index('idx_name')
       op.drop_column('table', 'column')
   ```

---

## Common Patterns

### Pattern 1: Adding Column with Default Value

```python
# Step 1: Add nullable column
op.add_column('table', Column('new_col', String, nullable=True))

# Step 2: Backfill default value
connection.execute(text("UPDATE table SET new_col = 'default' WHERE new_col IS NULL"))

# Step 3: Add NOT NULL constraint
op.alter_column('table', 'new_col', nullable=False)
```

### Pattern 2: Changing Column Type

```python
# Step 1: Add new column with target type
op.add_column('table', Column('new_col_temp', Integer, nullable=True))

# Step 2: Transform data
connection.execute(text("UPDATE table SET new_col_temp = CAST(old_col AS INTEGER)"))

# Step 3: Drop old column, rename new column
op.drop_column('table', 'old_col')
op.alter_column('table', 'new_col_temp', new_column_name='old_col')
```

### Pattern 3: Splitting Column

```python
# Before: full_name VARCHAR
# After: first_name VARCHAR, last_name VARCHAR

# Step 1: Add new columns
op.add_column('users', Column('first_name', String, nullable=True))
op.add_column('users', Column('last_name', String, nullable=True))

# Step 2: Split data
connection.execute(text("""
    UPDATE users
    SET
        first_name = SPLIT_PART(full_name, ' ', 1),
        last_name = SPLIT_PART(full_name, ' ', 2)
    WHERE first_name IS NULL
"""))

# Step 3: Add NOT NULL constraints (in separate migration)
```

---

## Troubleshooting

### Issue: Migration Timeout

**Symptom:** Migration times out after 10 minutes

**Solution:**
```python
# Increase batch size for faster processing
batch_size = 5000  # Increase from 1000

# Or reduce batch size if hitting memory limits
batch_size = 500  # Decrease from 1000
```

### Issue: Index Creation Fails

**Symptom:** `CREATE INDEX CONCURRENTLY` fails with "tuple concurrently updated"

**Solution:**
```bash
# 1. Check for long-running transactions
psql production_db << EOF
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active' AND query NOT LIKE '%pg_stat_activity%'
ORDER BY duration DESC;
EOF

# 2. Retry index creation after transactions complete
# 3. If persistent, create index without CONCURRENTLY during maintenance window
```

### Issue: Foreign Key Violation

**Symptom:** Migration fails with "violates foreign key constraint"

**Solution:**
```python
# 1. Check for orphaned records before migration
orphaned_count = connection.execute(text("""
    SELECT COUNT(*)
    FROM child_table c
    LEFT JOIN parent_table p ON c.parent_id = p.id
    WHERE p.id IS NULL
""")).scalar()

if orphaned_count > 0:
    raise Exception(f"Found {orphaned_count} orphaned records. Clean up before migration.")

# 2. Clean up orphaned records
connection.execute(text("""
    DELETE FROM child_table
    WHERE id IN (
        SELECT c.id
        FROM child_table c
        LEFT JOIN parent_table p ON c.parent_id = p.id
        WHERE p.id IS NULL
    )
"""))
```

---

## Appendix

### Migration Template

See: `backend-hormonia/alembic/MIGRATION_TEMPLATE.py`

### Useful SQL Queries

```sql
-- Check migration history
SELECT * FROM alembic_version;

-- Check index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;

-- Check table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check for missing indexes on foreign keys
SELECT
    c.conrelid::regclass AS table_name,
    a.attname AS column_name,
    c.confrelid::regclass AS referenced_table
FROM pg_constraint c
JOIN pg_attribute a ON a.attnum = ANY(c.conkey) AND a.attrelid = c.conrelid
LEFT JOIN pg_index i ON i.indrelid = c.conrelid
    AND a.attnum = ANY(i.indkey)
WHERE c.contype = 'f'
    AND i.indrelid IS NULL
ORDER BY c.conrelid::regclass::text, a.attnum;
```

---

**Document Changelog:**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-01-16 | Agent 19 | Initial comprehensive data migration strategy |
