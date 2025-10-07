# 🚨 CRITICAL: Database Schema Missing

**Date**: 2025-10-07 21:50 UTC
**Issue**: messagestatus enum does NOT exist in production database
**Impact**: Migration failing, application cannot start

---

## 🔍 Problem Discovery

**Error in Railway Logs**:
```
psycopg.errors.UndefinedObject: type "messagestatus" does not exist
CONTEXT: SQL statement "ALTER TYPE messagestatus ADD VALUE 'sending' AFTER 'scheduled'"
```

**What This Means**:
- The production PostgreSQL database is **EMPTY** or **INCOMPLETE**
- The `messagestatus` enum type does NOT exist
- Either:
  1. We're connecting to wrong database
  2. Schema was never deployed to production
  3. Database was reset/wiped

---

## ⚠️ IMMEDIATE ACTION REQUIRED

### Step 1: Verify Database Connection

**Check DATABASE_URL in Railway**:
```bash
railway variables --service backend | grep DATABASE_URL
```

**Expected**: Should point to your AWS RDS PostgreSQL instance
```
DATABASE_URL=postgresql+psycopg://user:pass@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require
```

**Verify**:
- ✅ Hostname matches your RDS endpoint
- ✅ Database name is correct
- ✅ Credentials are valid

### Step 2: Check Database Contents

**Connect to database**:
```bash
# Via Railway
railway run --service backend psql $DATABASE_URL

# Or directly
psql "postgresql://user:pass@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require"
```

**Run diagnostic queries**:
```sql
-- Check if any tables exist
\dt

-- Check if any enums exist
SELECT typname FROM pg_type WHERE typtype = 'e';

-- Check specifically for messagestatus
SELECT EXISTS (
    SELECT 1 FROM pg_type WHERE typname = 'messagestatus'
);
```

**Expected Results**:
- If database is empty: `\dt` shows nothing
- If database has schema: Should see tables like `messages`, `patients`, etc.
- If enum exists: `messagestatus` should appear in enum list

---

## 🔧 Resolution Options

### Option A: Database is Empty (Most Likely)

**Cause**: Schema was never deployed to production PostgreSQL

**Solution 1 - Deploy via Alembic** (Automated):
```bash
# The updated run_migrations.sh will handle this
railway up --service backend
# It will detect empty database and run: alembic upgrade head
```

**Solution 2 - Deploy via SQL** (Manual):
```bash
# Export schema from Supabase or local
pg_dump -s local_db > schema.sql

# Import to Railway database
psql $DATABASE_URL < schema.sql
```

**Solution 3 - Use Master Schema File**:
```bash
# If you have SCHEMA_MASTER_COMPLETO.sql
psql $DATABASE_URL < backend-hormonia/sql/SCHEMA_MASTER_COMPLETO.sql
```

### Option B: Wrong Database Connected

**Cause**: DATABASE_URL points to different/test database

**Solution**:
1. Verify DATABASE_URL in Railway dashboard
2. Update to correct production database URL
3. Redeploy

### Option C: Database Was Reset

**Cause**: Someone reset/dropped the production database

**Solution**:
1. Restore from backup (if available)
2. Or redeploy schema (Option A above)

---

## ✅ Updated Migration Strategy

I've updated `run_migrations.sh` to be **smart and adaptive**:

```bash
#!/bin/bash
# Smart migration - detects database state

# Check if messagestatus enum exists
if enum_does_not_exist; then
    # Database is empty/incomplete
    echo "Running full Alembic migrations..."
    python -m alembic upgrade head
else
    # Database has schema, just add SENDING value
    ALTER TYPE messagestatus ADD VALUE 'sending' AFTER 'scheduled';
fi
```

**This will automatically**:
- ✅ Detect if database is empty
- ✅ Run full Alembic migrations if needed
- ✅ Or just add SENDING value if schema exists

---

## 📋 Next Steps

### Immediate (NOW):

1. **Check DATABASE_URL**:
   ```bash
   railway variables --service backend | grep DATABASE_URL
   ```

2. **Verify database contents**:
   ```bash
   railway run --service backend psql $DATABASE_URL -c "\dt"
   ```

3. **Based on results**:
   - If empty → Deploy with latest code (Alembic will run)
   - If wrong DB → Fix DATABASE_URL
   - If reset → Restore from backup or redeploy schema

### After Database Fixed:

4. **Redeploy**:
   ```bash
   railway up --service backend
   ```

5. **Monitor logs** for:
   ```
   ✅ Alembic migrations completed
   # OR
   ✅ SENDING status added successfully
   ```

6. **Verify schema**:
   ```sql
   SELECT unnest(enum_range(NULL::messagestatus)) as status;
   ```

---

## 🔍 Diagnostic Checklist

- [ ] DATABASE_URL verified (correct hostname/database)
- [ ] Database connection successful
- [ ] Database contents checked (`\dt` command)
- [ ] Enum types listed (`SELECT typname FROM pg_type WHERE typtype = 'e'`)
- [ ] Root cause identified (empty/wrong/reset)
- [ ] Resolution applied (Alembic/SQL/restore)
- [ ] Application redeployed
- [ ] Schema verified (messagestatus exists)
- [ ] SENDING value verified

---

## 📊 Current Status

**Build**: Latest (daec8a4) with smart migration script
**Database**: ❌ MISSING SCHEMA
**Action**: REQUIRES MANUAL DATABASE VERIFICATION
**Next**: Follow diagnostic checklist above

---

## 🔗 Related Files

- Migration script: `backend-hormonia/run_migrations.sh`
- Latest commit: `daec8a4`
- Alembic migrations: `backend-hormonia/alembic/versions/`
- Master schema: `backend-hormonia/sql/SCHEMA_MASTER_COMPLETO.sql` (if exists)

---

**Created**: 2025-10-07 21:50 UTC
**Priority**: 🚨 CRITICAL
**Requires**: Manual database investigation
**Blocking**: Application deployment
