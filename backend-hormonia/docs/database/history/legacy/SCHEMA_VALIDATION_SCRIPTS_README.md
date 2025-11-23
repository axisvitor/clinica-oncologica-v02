# Database Schema Validation Scripts

This directory contains scripts for validating database schema integrity before and after migrations.

---

## Available Scripts

### 1. Alembic Configuration Validator

**Script:** `scripts/validate_alembic_setup.py`

**Purpose:** Validates Alembic configuration and migration chain integrity without requiring database access.

**Usage:**
```bash
cd backend-hormonia
python3 scripts/validate_alembic_setup.py
```

**Checks Performed:**
- ✓ Alembic configuration files exist
- ✓ All migration files are readable
- ✓ Migration chain is linear (no branches)
- ✓ Current migration head is valid
- ✓ All models are imported in env.py
- ✓ Database connection (if DATABASE_URL set)

**Output:**
```
============================================================
ALEMBIC SETUP VALIDATION
============================================================

🔍 Validating Alembic configuration...
✓ Found alembic.ini
✓ Found 18 migration files
✓ Migration chain is linear and valid
✓ Current head: 018_seed_flow_templates

============================================================
VALIDATION SUMMARY
============================================================
✅ All checks passed! Alembic is properly configured.
```

**Exit Codes:**
- `0` - All checks passed
- `1` - Critical issues found

---

### 2. Schema Integrity Validator

**Script:** `scripts/validate_schema_pre_migration.py`

**Purpose:** Comprehensive database schema validation and pre-migration health check.

**⚠️ Requires:** DATABASE_URL environment variable

**Usage:**
```bash
# Set database connection
export DATABASE_URL="postgresql+psycopg://user:pass@host:port/database?sslmode=require"

# Run validation
cd backend-hormonia
python3 scripts/validate_schema_pre_migration.py
```

**Checks Performed:**

#### 📊 Table Statistics
- Row counts for all tables
- Disk usage per table
- Column count analysis

#### 🔗 Foreign Key Analysis
- Identifies foreign keys without indexes
- Validates referential integrity
- Detects orphaned records

#### 🔒 Constraint Validation
- Checks for NULL values in NOT NULL columns
- Validates unique constraints
- Verifies check constraints

#### 📇 Index Health
- Identifies unused indexes
- Checks index bloat
- Analyzes index usage statistics

#### 🔧 Migration-Specific Checks
- Validates migration 003 requirements (patient_flow_states)
- Checks for duplicate data (migration 009)
- Validates JSONB data format (migration 012)

**Output:**

Console output:
```
🔍 Starting comprehensive schema validation...

📊 Analyzing table statistics...
  ✓ patients: 1,234 rows, 2.5 MB
  ✓ messages: 5,678 rows, 8.3 MB
  ...

🔗 Checking foreign key indexes...
  ⚠️  Found 3 foreign keys without indexes:
     - messages.patient_id → patients.id
     - alerts.patient_id → patients.id
     ...

✅ Schema validation complete!

============================================================
SCHEMA VALIDATION SUMMARY
============================================================
Tables: 25
Total Rows: 15,432
Missing FK Indexes: 3
Orphaned Records: 0
Migration Ready: ✅ YES
============================================================

📄 Full report saved to: docs/database/PRE_MIGRATION_SNAPSHOT.md
```

**Generated Report:** `docs/database/PRE_MIGRATION_SNAPSHOT.md`

**Exit Codes:**
- `0` - Database ready for migration
- `1` - Critical issues found, migration blocked

---

## Pre-Migration Workflow

### Step 1: Validate Alembic Configuration (No DB Required)

```bash
# Quick check of migration files and configuration
python3 scripts/validate_alembic_setup.py
```

**Expected Output:** All checks passed ✅

---

### Step 2: Set Database Connection

```bash
# Production
export DATABASE_URL="postgresql+psycopg://user:pass@prod-host:5432/clinica?sslmode=require"

# Staging
export DATABASE_URL="postgresql+psycopg://user:pass@staging-host:5432/clinica?sslmode=require"

# Development
export DATABASE_URL="postgresql+psycopg://localhost:5432/hormonia_dev"
```

---

### Step 3: Run Schema Validation (Requires DB)

```bash
python3 scripts/validate_schema_pre_migration.py
```

**Expected Output:** Detailed validation report + snapshot file

---

### Step 4: Review Generated Report

```bash
# Open the snapshot report
cat docs/database/PRE_MIGRATION_SNAPSHOT.md
```

**Review Sections:**
- Executive Summary (migration readiness)
- Table Statistics (data volume)
- Foreign Key Analysis (missing indexes)
- Orphaned Records (data integrity)
- Constraint Violations (schema issues)

---

### Step 5: Fix Issues (If Any)

#### Missing Foreign Key Indexes

**Issue:** Foreign keys without indexes cause slow joins

**Solution:**
```sql
-- Example: Add index for patient_id foreign key
CREATE INDEX CONCURRENTLY idx_messages_patient_id
ON messages(patient_id);
```

**Note:** These are typically added by migration 010

---

#### Orphaned Records

**Issue:** Records referencing non-existent parent records

**Solution:**
```sql
-- Example: Find orphaned messages
SELECT m.id, m.patient_id
FROM messages m
WHERE NOT EXISTS (
    SELECT 1 FROM patients p WHERE p.id = m.patient_id
);

-- Fix: Delete or reassign orphaned records
DELETE FROM messages WHERE id IN (...);
```

---

#### Constraint Violations

**Issue:** NULL values in NOT NULL columns

**Solution:**
```sql
-- Example: Find NULL values
SELECT id FROM patients WHERE email IS NULL;

-- Fix: Update with default values or delete
UPDATE patients SET email = 'unknown@example.com' WHERE email IS NULL;
```

---

#### Duplicate Patient Data (CRITICAL for Migration 009)

**Issue:** Migration 009 adds unique constraints, will fail if duplicates exist

**Solution:**
```bash
# Run duplicate checker
python3 scripts/check_duplicate_patients.py

# Follow script instructions to merge duplicates
```

---

### Step 6: Re-run Validation

After fixing issues, re-run validation:

```bash
python3 scripts/validate_schema_pre_migration.py
```

**Expected:** Migration Ready: ✅ YES

---

### Step 7: Proceed with Migration

```bash
# Check current version
alembic current

# Create backup
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# Run migration
alembic upgrade head

# Verify success
alembic current
```

---

## Post-Migration Validation

After successful migration, run validation again to verify:

```bash
# Run schema validation
python3 scripts/validate_schema_pre_migration.py

# Compare with pre-migration snapshot
diff docs/database/PRE_MIGRATION_SNAPSHOT.md docs/database/POST_MIGRATION_SNAPSHOT.md
```

**Expected Changes:**
- Additional indexes created
- New columns added
- New tables created (audit_logs, etc.)
- No orphaned records
- No constraint violations

---

## Troubleshooting

### Error: "DATABASE_URL not set"

**Solution:**
```bash
export DATABASE_URL="postgresql+psycopg://user:pass@host:port/database"
```

---

### Error: "Connection refused"

**Causes:**
- Database server not running
- Wrong host/port
- Firewall blocking connection

**Solution:**
```bash
# Test connection with psql
psql $DATABASE_URL

# Check if PostgreSQL is running
systemctl status postgresql
```

---

### Error: "Migration chain has branches"

**Cause:** Multiple migration heads exist (branched history)

**Solution:**
```bash
# Show all heads
alembic heads

# Merge branches (requires manual intervention)
alembic merge <head1> <head2>
```

---

### Error: "Permission denied" when creating indexes

**Cause:** Insufficient database permissions

**Solution:**
```sql
-- Grant required permissions
GRANT CREATE ON DATABASE clinica_oncologica TO app_user;
GRANT CREATE ON SCHEMA public TO app_user;
```

---

## Script Maintenance

### Adding New Checks

To add new validation checks, edit `scripts/validate_schema_pre_migration.py`:

```python
def _check_custom_validation(self):
    """Add custom validation logic"""
    print("\n🔍 Running custom validation...")

    # Your validation logic here
    query = text("SELECT COUNT(*) FROM your_table WHERE condition")

    with self.engine.connect() as conn:
        result = conn.execute(query)
        count = result.scalar()

        if count > 0:
            self.results['warnings'].append(f"Found {count} issues")
```

Then add to `validate_all()`:

```python
def validate_all(self):
    # ... existing checks ...
    self._check_custom_validation()  # Add here
    self._generate_summary()
```

---

### Updating Alembic Checks

To add Alembic-specific checks, edit `scripts/validate_alembic_setup.py`:

```python
def validate_custom_alembic_rule():
    """Custom Alembic validation"""
    issues = []
    warnings = []

    # Your validation logic

    return issues, warnings
```

---

## Performance Considerations

### Large Databases (1M+ rows)

**Schema Validation:** ~2-5 minutes
**Bottlenecks:**
- Foreign key validation queries
- Orphaned record detection
- Constraint checking

**Optimization:**
```python
# Add LIMIT to validation queries for sampling
query = text(f"""
    SELECT COUNT(*) FROM {table_name}
    LIMIT 10000  -- Sample only
""")
```

---

### Production Databases

**Best Practices:**
1. Run during low-traffic periods
2. Use read replicas for validation
3. Set query timeout:
   ```python
   engine = create_engine(url, connect_args={'options': '-c statement_timeout=30000'})
   ```

---

## Integration with CI/CD

### GitHub Actions Example

```yaml
- name: Validate Alembic Configuration
  run: |
    python3 scripts/validate_alembic_setup.py

- name: Validate Database Schema
  env:
    DATABASE_URL: ${{ secrets.DATABASE_URL }}
  run: |
    python3 scripts/validate_schema_pre_migration.py
```

---

## Related Documentation

- [Migration Guide](./MIGRATION_GUIDE.md)
- [Database Schema Reference](./SCHEMA_REFERENCE.md)
- [Alembic Configuration](../../alembic.ini)
- [Pre-Migration Validation Report](./PRE_MIGRATION_VALIDATION_REPORT.md)

---

**Last Updated:** 2025-11-16
**Maintained By:** Database Team
**Agent:** Agent 33 - Database Schema Validator
