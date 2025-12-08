# Database Backup & Restore Guide

**Status:** ✅ Production Ready
**Last Updated:** 2025-11-16
**Priority:** P0 (CRITICAL)

## Overview

Complete backup and restore solution for production PostgreSQL database with:
- Full schema backup (tables, indexes, constraints, foreign keys)
- Complete data backup (all tables with row-level data)
- Alembic version tracking (CRITICAL for migrations)
- Integrity verification (SHA256 checksums)
- Safety features (confirmation prompts, dry-run mode)

## Critical Components

### 1. Alembic Version Backup
**MOST CRITICAL:** The `alembic_version` table tracks which migrations have been applied. Without this, you cannot safely apply new migrations.

**Backed up:** ✅ Yes, first priority in backup process
**Verified:** ✅ Yes, checksum validation included

### 2. Schema Backup
Complete table definitions including:
- Column names, types, nullability
- Primary keys and foreign keys
- Indexes (including GIN indexes for JSONB)
- Constraints and defaults

### 3. Data Backup
All table data with:
- Sensitive data redaction (passwords, API keys)
- JSONB data preservation
- Timestamp conversion (ISO format)
- NULL handling

## Database Statistics

**Production Database:** AWS RDS PostgreSQL
**Estimated Size:** ~500MB
**Tables:** 47 tables
**Columns:** 594 columns
**Indexes:** 265 indexes

### Key Tables (by row count estimate)

| Table | Estimated Rows | Critical |
|-------|----------------|----------|
| messages | 50,000+ | Yes |
| quiz_responses | 30,000+ | Yes |
| patients | 5,000+ | Yes |
| patient_flow_states | 5,000+ | Yes |
| alembic_version | 1 | **CRITICAL** |

## Backup Script Usage

### Basic Backup (JSON format)

```bash
# Set environment
export DATABASE_URL="postgresql+psycopg://user:pass@host:5432/db?sslmode=require"

# Run backup
python scripts/backup_production_database.py

# Output:
# - backups/backup_prod_TIMESTAMP.json
# - backups/backup_prod_TIMESTAMP.json.sha256
# - backups/BACKUP_REPORT_TIMESTAMP.md
```

### SQL Format Backup

```bash
python scripts/backup_production_database.py --format sql

# Output:
# - backups/backup_prod_TIMESTAMP.sql
# - backups/backup_prod_TIMESTAMP.sql.sha256
# - backups/BACKUP_REPORT_TIMESTAMP.md
```

### Custom Backup Directory

```bash
python scripts/backup_production_database.py --backup-dir /secure/backups
```

## Backup Process Flow

```
1. Connect to Database
   └─> Verify connection with pool_pre_ping

2. Backup Alembic Version (CRITICAL)
   └─> Query: SELECT version_num FROM alembic_version
   └─> Store in backup metadata

3. Discover Tables
   └─> Get all table names from schema
   └─> Filter out temporary tables (sessions, celery_*)

4. For Each Table:
   ├─> Get Schema Definition
   │   ├─> Columns (name, type, nullable, default)
   │   ├─> Indexes (name, columns, unique)
   │   ├─> Foreign Keys (source, target)
   │   └─> Primary Keys
   │
   └─> Get Table Data
       ├─> Count rows
       ├─> Fetch all rows
       ├─> Redact sensitive columns
       └─> Store in backup

5. Generate Checksums
   └─> SHA256 hash of backup file

6. Create Report
   └─> Markdown summary with statistics
```

## Restore Script Usage

### Dry Run (Safe - No Changes)

```bash
python scripts/restore_database_backup.py \
  --backup backups/backup_prod_20251116_120000.json \
  --dry-run
```

### Interactive Restore (with confirmation)

```bash
python scripts/restore_database_backup.py \
  --backup backups/backup_prod_20251116_120000.json

# Will prompt:
# ⚠️  WARNING: This will DELETE all data in the database!
#    Database: clinica_oncologica
#    Backup:   backup_prod_20251116_120000.json
#    Tables:   47
#    Rows:     85,347
#
# ❓ Type 'RESTORE' to continue:
```

### Automatic Restore (DANGEROUS - No confirmation)

```bash
python scripts/restore_database_backup.py \
  --backup backups/backup_prod_20251116_120000.json \
  --yes
```

## Restore Process Flow

```
1. Verify Checksum
   └─> Compare SHA256 hash with .sha256 file
   └─> Abort if mismatch

2. Load Backup Data
   └─> Parse JSON backup file

3. Confirmation (unless --yes)
   └─> Display backup info
   └─> Require user to type 'RESTORE'

4. Disable Triggers
   └─> SET session_replication_role = 'replica'
   └─> Prevents foreign key checks during restore

5. Restore Alembic Version
   └─> DELETE FROM alembic_version
   └─> INSERT backup version

6. For Each Table:
   ├─> TRUNCATE TABLE CASCADE
   └─> INSERT rows in batches (1000 rows/batch)

7. Re-enable Triggers
   └─> SET session_replication_role = 'origin'

8. Verify Restore
   ├─> Check alembic version
   ├─> Verify row counts for all tables
   └─> Report any discrepancies
```

## Security Features

### 1. Sensitive Data Redaction

The following column types are automatically redacted:
- `password_hash` → `[REDACTED]`
- `firebase_uid` → `[REDACTED]`
- `api_key` → `[REDACTED]`
- `secret_key` → `[REDACTED]`
- `private_key` → `[REDACTED]`

### 2. Integrity Verification

- SHA256 checksums for all backup files
- Checksum validation before restore
- Post-restore verification (row counts)

### 3. Safety Prompts

- Confirmation required before restore
- Clear warnings about data deletion
- Dry-run mode for testing

## Excluded Tables

These temporary/cache tables are NOT backed up:

- `sessions` - User session data (temporary)
- `celery_taskmeta` - Celery task metadata (temporary)
- `celery_tasksetmeta` - Celery task set metadata (temporary)

## Backup Report Example

Each backup generates a markdown report:

```markdown
# Production Database Backup Report

**Generated:** 2025-11-16 12:00:00
**Database:** clinica_oncologica
**Alembic Version:** 018_seed_flow_templates_for_onboarding

## Statistics

- **Total Tables:** 47
- **Total Rows:** 85,347

## Tables Backed Up

| Table Name | Row Count | Columns | Indexes |
|------------|-----------|---------|---------|
| patients | 5,234 | 15 | 8 |
| messages | 52,891 | 12 | 6 |
| quiz_responses | 31,456 | 10 | 5 |
...
```

## Production Deployment Workflow

### BEFORE Applying Migrations

```bash
# 1. Create backup
export DATABASE_URL="postgresql+psycopg://..."
python scripts/backup_production_database.py

# 2. Verify backup created
ls -lh backups/backup_prod_*.json

# 3. Verify checksum
cat backups/backup_prod_*.json.sha256

# 4. Store backup securely (S3, encrypted storage)
aws s3 cp backups/backup_prod_*.json s3://secure-backups/

# 5. NOW safe to apply migrations
alembic upgrade head
```

### IF Migration Fails

```bash
# 1. Stop application
systemctl stop backend-hormonia

# 2. Restore from backup
python scripts/restore_database_backup.py \
  --backup backups/backup_prod_TIMESTAMP.json

# 3. Verify restore
python -c "from sqlalchemy import create_engine, text; \
  engine = create_engine('$DATABASE_URL'); \
  with engine.connect() as conn: \
    version = conn.execute(text('SELECT version_num FROM alembic_version')).scalar(); \
    print(f'Alembic version: {version}')"

# 4. Restart application
systemctl start backend-hormonia
```

## Performance Considerations

### Backup Performance

- **Time Estimate:** 2-5 minutes for 500MB database
- **CPU Usage:** Low (mostly I/O bound)
- **Memory Usage:** ~100-200MB (batch processing)
- **Network:** Minimal (unless remote database)

### Restore Performance

- **Time Estimate:** 5-10 minutes for 500MB database
- **CPU Usage:** Moderate (JSON parsing, batch inserts)
- **Memory Usage:** ~200-500MB (larger batches)
- **Downtime Required:** Yes (database must be offline)

### Optimization Tips

1. **Batch Size:** Default 1000 rows/batch
   - Increase for faster restore: Modify `batch_size` in code
   - Decrease for lower memory: Reduce batch size

2. **Parallel Restore:** Not implemented (sequential safer)
   - Could parallelize table restores in future

3. **Compression:** Not implemented
   - JSON files compress well with gzip
   - `gzip backups/backup_prod_*.json`

## Storage Recommendations

### Backup Storage Requirements

- **JSON Format:** ~1.5-2x database size (readable, debuggable)
- **SQL Format:** ~2-3x database size (includes INSERT statements)
- **Compressed:** ~30-40% of original size

### Retention Policy

- **Daily Backups:** Keep last 7 days
- **Weekly Backups:** Keep last 4 weeks
- **Monthly Backups:** Keep last 12 months
- **Pre-Migration Backups:** Keep indefinitely (tagged)

### Storage Locations

1. **Local:** `/backups/` directory (temporary)
2. **S3 Bucket:** `s3://clinic-backups/production/`
3. **Encrypted Storage:** AWS S3 with server-side encryption
4. **Offsite:** Replicated to secondary region

## Error Handling

### Common Errors

#### 1. Connection Timeout

```
❌ Error: Connection timeout
Solution: Check DATABASE_URL and network connectivity
```

#### 2. Permission Denied

```
❌ Error: Permission denied for table X
Solution: Ensure database user has SELECT/INSERT permissions
```

#### 3. Disk Space

```
❌ Error: No space left on device
Solution: Free up disk space or use --backup-dir with more space
```

#### 4. Checksum Mismatch

```
❌ CHECKSUM MISMATCH!
Solution: Backup file corrupted, create new backup
```

### Recovery from Failed Restore

1. **Stop immediately** - Don't continue with partial restore
2. **Check logs** - Identify which table failed
3. **Restore from backup** - Use previous known-good backup
4. **Contact DBA** - If data corruption suspected

## Testing

### Test Backup

```bash
# 1. Backup test database
export DATABASE_URL="postgresql+psycopg://localhost/test_db"
python scripts/backup_production_database.py --backup-dir test_backups

# 2. Verify backup created
ls -lh test_backups/

# 3. Verify checksum
sha256sum -c test_backups/backup_prod_*.json.sha256
```

### Test Restore

```bash
# 1. Dry run (no changes)
python scripts/restore_database_backup.py \
  --backup test_backups/backup_prod_*.json \
  --dry-run

# 2. Restore to test database
python scripts/restore_database_backup.py \
  --backup test_backups/backup_prod_*.json \
  --yes

# 3. Verify data
psql $DATABASE_URL -c "SELECT COUNT(*) FROM patients;"
```

## Monitoring

### Backup Monitoring

```bash
# Check backup age
find backups/ -name "backup_prod_*.json" -mtime +1

# Check backup size
du -sh backups/backup_prod_*.json

# Verify latest backup
ls -lt backups/ | head -n 5
```

### Automation (Cron)

```bash
# Add to crontab
# Daily backup at 2 AM
0 2 * * * cd /app && /usr/bin/python3 scripts/backup_production_database.py && /usr/local/bin/aws s3 sync backups/ s3://clinic-backups/production/
```

## Troubleshooting

### Backup Script Won't Run

1. Check Python version: `python --version` (3.11+ required)
2. Check dependencies: `pip install sqlalchemy psycopg[binary]`
3. Check DATABASE_URL: `echo $DATABASE_URL`
4. Check permissions: `ls -l scripts/backup_production_database.py`

### Restore Script Won't Run

1. Check backup file exists: `ls -l backups/backup_prod_*.json`
2. Check checksum file: `ls -l backups/backup_prod_*.json.sha256`
3. Check database connectivity: `psql $DATABASE_URL -c "SELECT 1"`
4. Check disk space: `df -h`

## Related Documentation

- [Database Schema Reference](/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/docs/architecture/database/SCHEMA.md)
- [Database Performance Guide](/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/docs/architecture/database/PERFORMANCE.md)
- [Alembic Migration Guide](/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/docs/archive/quick-references/MIGRATION_QUICK_REFERENCE.md)
- [Production Deployment Guide](/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/docs/P0_DEPLOYMENT_GUIDE.md)

## Support

For backup/restore issues:
1. Check logs: `tail -f backups/backup_*.log`
2. Check database logs: AWS RDS console
3. Contact DevOps team
4. Emergency: Restore from most recent known-good backup

---

**Remember:** Always backup BEFORE applying migrations!
