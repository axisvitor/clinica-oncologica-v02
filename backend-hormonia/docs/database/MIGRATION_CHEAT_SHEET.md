# Migration Cheat Sheet - Quick Reference Card

**Database:** AWS RDS PostgreSQL (Production)
**Current State:** alembic_version = NULL (No migrations applied)
**Date:** 2025-10-09

---

## ⚡ Quick Commands

### Check Current Status
```bash
# View current migration version
alembic current

# View migration history
alembic history --verbose

# Check production database state
python scripts/analyze_production_state.py
```

### Apply Migrations
```bash
# Stamp at specific migration (doesn't run migration)
alembic stamp <migration_id>

# Upgrade to next migration
alembic upgrade +1

# Upgrade to head (latest)
alembic upgrade head

# Downgrade one migration
alembic downgrade -1
```

### Create Migrations
```bash
# Create new migration
alembic revision -m "description"

# Auto-generate from model changes
alembic revision --autogenerate -m "description"
```

---

## 🎯 Production Database Facts

| Metric | Value |
|--------|-------|
| Total Tables | 38 |
| Alembic Version | NULL |
| Tables Matching Migrations | ~25 (66%) |
| Extra Tables (not in migrations) | 13 |
| Missing Tables (in migrations) | 6 |
| Schema Mismatch | webhook_events (47% match) |

---

## 📊 Table Status at a Glance

```
✅ = Exists and matches migration
⚠️ = Exists but schema mismatch
❌ = Missing (migration not applied)
➕ = Extra (not in any migration)
```

### Core System (✅ OK)
- users, patients, messages, alerts, medical_reports
- flow_states, quiz_templates, quiz_responses, quiz_sessions
- audit_log_entries, flow_kinds, flow_template_versions

### Webhook System (⚠️ MISMATCH)
- message_status_events ✅
- webhook_events ⚠️ (schema different)

### A/B Testing (❌ MISSING)
- ab_experiments, ab_variant_assignments, ab_experiment_metrics
- ab_experiment_results, ab_experiment_audit, ab_experiment_monitoring

### Recent Features (❌ MISSING)
- quiz_questions
- whatsapp_delivery_failures
- webhook_idempotency

### Admin System (➕ EXTRA)
- admin_users, admin_roles, admin_permissions, admin_sessions
- admin_security_events, admin_ip_whitelist, admin_ip_blacklist
- admin_audit_log, admin_role_permissions, admin_user_permissions

---

## 🚀 Recommended Migration Path

### Option A: Safe & Conservative (RECOMMENDED)

```bash
# 1. Backup
pg_dump production > backup.sql

# 2. Stamp at baseline
alembic stamp 018_message_status_events

# 3. Create alignment migration
alembic revision -m "align_webhook_events"
# Edit: Fix webhook_events schema (see MIGRATION_ACTION_PLAN.md)

# 4. Apply
alembic upgrade align_webhook_events
alembic stamp 019_webhook_events  # Skip recreation
alembic upgrade head

# 5. Verify
alembic current  # Should show: head
```

### Option B: Direct Stamp (RISKY - NOT RECOMMENDED)

```bash
# Stamp at head (will miss schema fixes)
alembic stamp head

# Then fix webhook_events manually
# NOT RECOMMENDED: leaves inconsistencies
```

---

## ⚠️ Common Issues & Fixes

### Issue: "Table already exists"
```bash
# Check which table
\d <table_name>

# Skip that migration
alembic stamp <next_migration_id>
```

### Issue: "ENUM type already exists"
```sql
-- Check ENUMs
SELECT typname FROM pg_type WHERE typname LIKE '%_type';

-- Drop if needed
DROP TYPE IF EXISTS <enum_name> CASCADE;
```

### Issue: "Foreign key constraint fails"
```sql
-- Find orphaned records
SELECT COUNT(*) FROM <table>
WHERE <fk_column> IS NOT NULL
  AND <fk_column> NOT IN (SELECT id FROM <referenced_table>);

-- Fix orphaned records
UPDATE <table> SET <fk_column> = NULL
WHERE <fk_column> NOT IN (SELECT id FROM <referenced_table>);
```

---

## 📋 Pre-Migration Checklist

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

## 🔧 Troubleshooting Commands

### Check Database State
```sql
-- List all tables
SELECT tablename FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;

-- Check table structure
\d+ <table_name>

-- Check ENUM types
SELECT typname, enum_range(NULL::typname)
FROM pg_type WHERE typtype = 'e';

-- Check indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = '<table_name>';
```

### Check Migration State
```bash
# View migration files
ls -la backend-hormonia/alembic/versions/

# Show current migration
alembic current --verbose

# Show migration SQL (dry run)
alembic upgrade head --sql > migration_preview.sql
```

---

## 🎯 Key Migration IDs (Quick Reference)

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

## 🔥 Emergency Rollback

### If Migration Fails:
```bash
# 1. STOP everything
# 2. Restore from backup
psql -d postgres < backup.sql

# 3. Reset alembic version
psql -d postgres -c "UPDATE alembic_version SET version_num = NULL;"

# 4. Investigate error
alembic history --verbose
cat migration_error.log
```

### If Data Corrupted:
```bash
# Full restore
psql -d postgres < backup.sql

# Partial restore (specific tables)
pg_restore -t <table_name> backup.sql
```

---

## 📞 Quick Reference Links

| Document | Purpose |
|----------|---------|
| [PRODUCTION_MIGRATION_MAPPING.md](./PRODUCTION_MIGRATION_MAPPING.md) | Full analysis |
| [MIGRATION_ACTION_PLAN.md](./MIGRATION_ACTION_PLAN.md) | Step-by-step guide |
| [MIGRATION_STATUS_SUMMARY.md](./MIGRATION_STATUS_SUMMARY.md) | Visual overview |

---

## 💡 Pro Tips

1. **Always backup before migrating**
2. **Test on local copy first**
3. **Use stamp, don't force**
4. **One migration at a time when debugging**
5. **Check alembic current after each step**
6. **Never delete migration files**
7. **Document manual SQL changes**
8. **Use --sql flag to preview migrations**

---

## 🚫 Don't Do This

❌ `DROP TABLE` without backup
❌ `alembic stamp head` without understanding
❌ Manual SQL schema changes without migrations
❌ Delete migration files
❌ Force push database changes
❌ Migrate production without testing
❌ Skip backups ("just this once")

---

## ✅ Do This Instead

✅ Create migrations for ALL schema changes
✅ Test migrations on local copy
✅ Backup before every migration
✅ Use alembic commands exclusively
✅ Document manual changes
✅ Review migration SQL with --sql flag
✅ Follow the recommended migration path

---

**Last Updated:** 2025-10-09
**Version:** 1.0
**Status:** 🔴 Production requires action

---

**Print this page and keep it handy during migration!**
