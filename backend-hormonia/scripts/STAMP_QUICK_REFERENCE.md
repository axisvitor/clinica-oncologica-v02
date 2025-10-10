# Stamp Production DB - Quick Reference

## TL;DR - Common Commands

### 1. Get Recommendation (Start Here)
```bash
python scripts/stamp_production_db.py --analyze
```

### 2. Preview Stamp (Safe, No Changes)
```bash
python scripts/stamp_production_db.py --stamp 5479068ccdaa --dry-run
```

### 3. Actual Stamp (Requires 2 Confirmations)
```bash
python scripts/stamp_production_db.py --stamp 5479068ccdaa
```

### 4. Verify Success
```sql
SELECT * FROM alembic_version;  -- Should show: 5479068ccdaa
```

---

## When to Use This Script

✅ **USE WHEN:**
- Database created manually (SQL dump, schema.sql)
- alembic_version is empty/missing
- alembic_version shows old revision but schema is newer
- Migrated database from another environment

❌ **DON'T USE WHEN:**
- Alembic migrations already working correctly
- Uncertain about database state
- Haven't tested in staging first

---

## Quick Workflow

```bash
# Step 1: Analyze (get recommendation)
python scripts/stamp_production_db.py --analyze

# Step 2: Preview (dry run - SAFE)
python scripts/stamp_production_db.py --stamp RECOMMENDED_REVISION --dry-run

# Step 3: Backup (ALWAYS!)
pg_dump $DATABASE_URL > backup.sql

# Step 4: Stamp (requires confirmations)
python scripts/stamp_production_db.py --stamp RECOMMENDED_REVISION

# Step 5: Verify
alembic current
alembic history --verbose
```

---

## Troubleshooting

### Schema Validation Failed
```bash
# See what's wrong
python scripts/stamp_production_db.py --analyze

# Fix schema issues first, then re-run
# OR stamp with older revision that matches
```

### Wrong Revision Stamped
```sql
-- Fix it:
DELETE FROM alembic_version;

-- Then re-stamp with correct revision
```

### Can't Connect
```bash
# Check database URL
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL -c "SELECT 1;"
```

---

## Safety Checklist

Before stamping production:

- [ ] Ran `--analyze` to get recommendation
- [ ] Ran `--dry-run` to preview
- [ ] Backed up database (`pg_dump`)
- [ ] Tested in staging environment
- [ ] Understand which revision represents current state
- [ ] Have rollback plan ready
- [ ] Know how to verify success

---

## After Stamping

1. **Verify alembic_version:**
   ```sql
   SELECT * FROM alembic_version;
   ```

2. **Check Alembic sees it:**
   ```bash
   alembic current  # Should show stamped revision
   ```

3. **Check for pending migrations:**
   ```bash
   alembic upgrade head --sql  # Review SQL output
   ```

4. **Test upgrade path:**
   ```bash
   alembic upgrade head  # Apply if needed
   ```

---

## Rollback

If something goes wrong:

```sql
-- Delete wrong stamp
DELETE FROM alembic_version;

-- Restore from backup (if needed)
psql $DATABASE_URL < backup.sql

-- Re-stamp with correct revision
-- (Use --analyze to find correct one)
```

---

## Common Revisions

Latest migrations (as of 2025-10-10):

```
5479068ccdaa         - Rename audit_log.metadata → event_metadata
20251010_000000      - Add unique quiz session constraint
20251009_235900      - Add delivery status
20251009_235500      - Add webhook idempotency
20251009_230000      - Add WhatsApp delivery failures
```

Check all available:
```bash
python scripts/stamp_production_db.py --show-migrations
```

---

## Emergency Contact

**Before stamping production:**
1. Review this guide
2. Test in staging
3. Consult DBA if uncertain

**If stamp fails:**
1. Don't panic
2. Don't run more migrations
3. Check rollback procedure above
4. Restore from backup if needed

---

## Key Points

🔴 **NEVER** use `--force` unless absolutely necessary
🟡 **ALWAYS** run `--dry-run` first
🟢 **ALWAYS** backup before stamping

**Remember:** Stamping tells Alembic what state the database is in. Wrong stamp = migration chaos!
