# Database Migrations Guide

**Date**: 2025-10-11
**Status**: Production database has 38 tables, alembic_version = NULL
**Current HEAD**: 5479068ccdaa_rename_audit_log_metadata_to_event_.py

---

## Quick Start

### Essential Commands

```bash
# Check current migration status
alembic current

# View migration history
alembic history --verbose

# Apply migrations to head
alembic upgrade head

# Create new migration
alembic revision -m "description"

# Auto-generate from model changes
alembic revision --autogenerate -m "description"
```

### Pre-Flight Checklist

```
[ ] Backup created (full dump)
[ ] Schema backup created
[ ] Tested on local copy
[ ] Maintenance window scheduled
[ ] Team notified
[ ] Rollback plan ready
[ ] No active webhook processing
[ ] Database connections minimal
```

---

## Current Migration Status

### Critical Issues (Fix Immediately)

1. **Type Hints in Recent Migrations** - CRITICAL
   - Files: `20251009_230000_add_whatsapp_delivery_failures.py`, `20251009_235500_add_webhook_idempotency.py`
   - Problem: Python 3.10+ type hint syntax breaks Alembic parsing
   - Fix: Remove type hints from revision identifiers

2. **Broken Migration Chains** - HIGH
   - 3 separate root migrations (should be 1)
   - 5 orphaned migrations not in main chain
   - webhook_events schema mismatch (47% match)

3. **Production Alignment** - HIGH
   - Production has 38 tables but alembic_version = NULL
   - 13 extra tables created manually
   - 6 tables missing from migrations

### Quick Fixes Required

```python
# Fix type hints in broken files
# Change from:
revision: str = '20251009_230000'
down_revision: Union[str, None] = '20251009_210800'

# To:
revision = '20251009_230000'
down_revision = '20251009_210800'
```

---

## Production Migration Strategy

### Recommended Approach (Safe & Conservative)

```bash
# 1. Backup first
pg_dump production > backup_$(date +%Y%m%d).sql

# 2. Stamp at baseline
alembic stamp 018_message_status_events

# 3. Create alignment migration
alembic revision -m "align_webhook_events"
# Edit: Fix webhook_events schema

# 4. Apply migrations
alembic upgrade align_webhook_events
alembic stamp 019_webhook_events  # Skip recreation
alembic upgrade head

# 5. Verify
alembic current  # Should show: head
```

### What Each Migration Will Do

| Migration | Action | Risk | Notes |
|-----------|--------|------|-------|
| align_webhook_events | Fix webhook_events schema | ⚠️ MEDIUM | Data preserved in JSONB |
| 019 (skip) | Create webhook_events | ✅ SAFE | Table already exists (stamped) |
| 020-021 | Add indexes | ✅ SAFE | Indexes only |
| 022-028 | Create A/B testing tables | ✅ SAFE | New tables |
| 029 | Create quiz_questions table | ⚠️ CHECK | Verify doesn't exist |
| 030-039 | Add indexes | ✅ SAFE | Performance only |
| 20251009_230000 | Create whatsapp_delivery_failures | ✅ SAFE | New table |
| 20251009_235500 | Create webhook_idempotency | ✅ SAFE | New table |

---

## Migration Naming Convention

### Current Standard (2025+)
- Format: `YYYYMMDD_HHMMSS_description.py`
- Example: `20251009_210800_add_gin_indexes_for_search.py`

### Legacy Formats
- Old numbered: `001_description.py` (deprecated)
- Descriptive: `add_feature.py` (deprecated)

### Creating New Migrations

```bash
# Use date-based format
alembic revision -m "$(date +%Y%m%d_%H%M%S)_your_description"

# Always include clear description
alembic revision -m "20251011_150000_add_patient_consent_tracking"
```

---

## Troubleshooting

### Common Issues & Fixes

#### Issue: "Table already exists"
```bash
# Check which table
\d <table_name>

# Skip that migration
alembic stamp <next_migration_id>
```

#### Issue: "ENUM type already exists"
```sql
-- Check ENUMs
SELECT typname FROM pg_type WHERE typname LIKE '%_type';

-- Drop if needed
DROP TYPE IF EXISTS <enum_name> CASCADE;
```

#### Issue: "Foreign key constraint fails"
```sql
-- Find orphaned records
SELECT COUNT(*) FROM <table>
WHERE <fk_column> IS NOT NULL
  AND <fk_column> NOT IN (SELECT id FROM <referenced_table>);

-- Fix orphaned records
UPDATE <table> SET <fk_column> = NULL
WHERE <fk_column> NOT IN (SELECT id FROM <referenced_table>);
```

### Emergency Rollback

```bash
# If migration fails:
# 1. STOP everything
# 2. Restore from backup
psql -d postgres < backup.sql

# 3. Reset alembic version
psql -d postgres -c "UPDATE alembic_version SET version_num = NULL;"

# 4. Investigate error
alembic history --verbose
cat migration_error.log
```

---

## Best Practices

### Do This ✅
- Create migrations for ALL schema changes
- Test migrations on local copy
- Backup before every migration
- Use alembic commands exclusively
- Document manual changes
- Review migration SQL with --sql flag
- Follow the recommended migration path

### Don't Do This ❌
- `DROP TABLE` without backup
- `alembic stamp head` without understanding
- Manual SQL schema changes without migrations
- Delete migration files
- Force push database changes
- Migrate production without testing
- Skip backups ("just this once")

---

## Migration Health Metrics

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Total migrations | 69 | 69 | ✓ OK |
| Root migrations | 3 | 1 | ✗ FIX REQUIRED |
| Orphaned migrations | 5 | 1 (HEAD only) | ✗ FIX REQUIRED |
| Broken migrations | 2 | 0 | ✗ FIX REQUIRED |
| Main chain health | 66/69 | 69/69 | ✗ NEEDS WORK |

---

## Key Migration IDs (Quick Reference)

| ID | Migration | Action |
|----|-----------|--------|
| 001_initial | Initial schema | Core tables |
| 018_message_status_events | Message tracking | **BASELINE** |
| 019_webhook_events | Webhook events | **SKIP** (exists) |
| align_webhook_events | Fix schema | **CRITICAL** |
| 022-028 | A/B testing | New tables |
| 029_quiz_questions | Quiz questions | New table |
| 20251009_230000 | WhatsApp failures | New table |
| 20251009_235500 | Webhook idempotency | New table |

---

## Support & Resources

- **Detailed Analysis**: [SCHEMA_EVOLUTION.md](./SCHEMA_EVOLUTION.md)
- **Alembic Docs**: [Alembic Documentation](https://alembic.sqlalchemy.org/)
- **Migration Cheat Sheet**: Keep in project root for quick reference

---

**Document Version**: 1.0
**Last Updated**: 2025-10-11
**Status**: 🔴 Production requires immediate action
