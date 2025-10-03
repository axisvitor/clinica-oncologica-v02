# Database Migrations Guide - Backend

## Migration Files Overview

The Backend uses SQL migrations stored in `Backend/migrations/` directory. These migrations must be applied manually to the Supabase database.

## Current Migration Files

### Validated Migration Files (in Backend/migrations/)

1. **001_create_admin_tables.sql** (13,206 bytes)
   - Creates base admin user tables and schemas
   - Defines user roles and permissions structure
   - Sets up initial RLS policies

2. **fix_user_role_enum.sql** (2,637 bytes)
   - Fixes user role enum type
   - Updates role constraints
   - Ensures data consistency

3. **001_create_admin_users.sql** (8,377 bytes)
   - Creates initial admin user accounts
   - Sets up default permissions
   - Configures role assignments

4. **002_cleanup_test_data.sql** (4,090 bytes)
   - Removes test data from database
   - Cleans up development artifacts
   - Prepares database for production

5. **supabase_admin_system_complete.sql** (29,084 bytes)
   - Complete admin system setup
   - Comprehensive RLS policies
   - Full permission system

## Migration Directory Structure

```
Backend/
├── migrations/
│   ├── 001_create_admin_tables.sql       ✅ Base schema
│   ├── fix_user_role_enum.sql            ✅ Enum fixes
│   ├── 001_create_admin_users.sql        ✅ Initial users
│   ├── 002_cleanup_test_data.sql         ✅ Cleanup
│   └── supabase_admin_system_complete.sql ✅ Complete setup
└── migrations/sql/                        ❌ DEPRECATED (if exists)
```

**Note:** There is NO `migrations/sql/` subdirectory. All migrations are in the root `migrations/` directory.

## Migration Application Order

**CRITICAL:** Apply migrations in this exact order:

```sql
-- Step 1: Base schema
\i Backend/migrations/001_create_admin_tables.sql

-- Step 2: Enum fixes
\i Backend/migrations/fix_user_role_enum.sql

-- Step 3: Initial users
\i Backend/migrations/001_create_admin_users.sql

-- Step 4: Cleanup
\i Backend/migrations/002_cleanup_test_data.sql

-- Step 5: Complete setup
\i Backend/migrations/supabase_admin_system_complete.sql
```

## Applying Migrations to Supabase

### Method 1: Supabase SQL Editor (Recommended)

1. **Navigate to Supabase Dashboard:**
   - Go to https://supabase.com/dashboard
   - Select your project
   - Click "SQL Editor" in left sidebar

2. **Apply Each Migration:**
   ```sql
   -- Copy content from Backend/migrations/001_create_admin_tables.sql
   -- Paste into SQL Editor
   -- Click "Run"

   -- Repeat for each migration in order
   ```

3. **Verify Success:**
   ```sql
   -- Check tables created
   SELECT tablename FROM pg_tables WHERE schemaname = 'public';

   -- Check roles
   SELECT rolname FROM pg_roles;

   -- Check RLS policies
   SELECT * FROM pg_policies;
   ```

### Method 2: Railway CLI + Supabase CLI

**Prerequisites:**
```bash
# Install Supabase CLI
npm install -g supabase

# Install Railway CLI
npm install -g @railway/cli
```

**Apply Migrations:**
```bash
# Set Supabase credentials
export SUPABASE_URL="https://rszpypytdciggybbpnrp.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="<your-service-role-key>"

# Apply migrations (in order)
supabase db execute --file Backend/migrations/001_create_admin_tables.sql
supabase db execute --file Backend/migrations/fix_user_role_enum.sql
supabase db execute --file Backend/migrations/001_create_admin_users.sql
supabase db execute --file Backend/migrations/002_cleanup_test_data.sql
supabase db execute --file Backend/migrations/supabase_admin_system_complete.sql
```

### Method 3: psql Direct Connection

**Connect to Supabase:**
```bash
# Connection string from DATABASE_URL
psql "postgresql://postgres.rszpypytdciggybbpnrp:PASSWORD@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"

# Run migrations
\i Backend/migrations/001_create_admin_tables.sql
\i Backend/migrations/fix_user_role_enum.sql
\i Backend/migrations/001_create_admin_users.sql
\i Backend/migrations/002_cleanup_test_data.sql
\i Backend/migrations/supabase_admin_system_complete.sql

# Exit
\q
```

## Pre-Deployment Migration Checklist

**Before Railway deployment, verify:**

- [ ] All 5 migration files exist in `Backend/migrations/`
- [ ] No duplicate migrations in `migrations/sql/` subdirectory
- [ ] Migrations applied in correct order
- [ ] No SQL syntax errors
- [ ] RLS policies enabled
- [ ] Admin users created successfully

**Verification Queries:**

```sql
-- 1. Check admin tables exist
SELECT COUNT(*) FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('admin_users', 'admin_roles', 'admin_permissions');

-- Expected: 3

-- 2. Check RLS policies
SELECT COUNT(*) FROM pg_policies
WHERE schemaname = 'public';

-- Expected: > 0

-- 3. Check admin users
SELECT id, email, role, active FROM admin_users;

-- Expected: At least 1 admin user

-- 4. Check enum types
SELECT typname, enumlabel
FROM pg_type
JOIN pg_enum ON pg_type.oid = pg_enum.enumtypid
WHERE typname = 'user_role';

-- Expected: admin, doctor, patient roles
```

## Migration Rollback

**If migration fails, rollback procedure:**

1. **Identify failed migration:**
   ```sql
   -- Check last applied migration
   SELECT * FROM schema_migrations ORDER BY version DESC LIMIT 1;
   ```

2. **Drop created objects:**
   ```sql
   -- Drop tables (cascades to constraints)
   DROP TABLE IF EXISTS admin_users CASCADE;
   DROP TABLE IF EXISTS admin_roles CASCADE;
   DROP TABLE IF EXISTS admin_permissions CASCADE;

   -- Drop types
   DROP TYPE IF EXISTS user_role CASCADE;
   ```

3. **Re-apply migrations from start:**
   - Follow "Migration Application Order" above
   - Apply one at a time
   - Verify each step

## Railway Deployment Migration Commands

**Add to Railway deployment script:**

```bash
# Option 1: Pre-deployment hook (if supported)
# .railway/deploy.sh
#!/bin/bash
echo "Applying database migrations..."
supabase db execute --file Backend/migrations/001_create_admin_tables.sql
supabase db execute --file Backend/migrations/fix_user_role_enum.sql
supabase db execute --file Backend/migrations/001_create_admin_users.sql
supabase db execute --file Backend/migrations/002_cleanup_test_data.sql
supabase db execute --file Backend/migrations/supabase_admin_system_complete.sql
echo "Migrations complete!"
```

**Option 2: Manual application before deployment**
- Apply migrations via Supabase SQL Editor
- Verify with health check endpoint
- Then deploy to Railway

## Troubleshooting

### Common Migration Issues

**1. "relation already exists" error**
```sql
-- Solution: Drop existing table
DROP TABLE IF EXISTS admin_users CASCADE;

-- Re-run migration
\i Backend/migrations/001_create_admin_tables.sql
```

**2. "type already exists" error**
```sql
-- Solution: Drop existing type
DROP TYPE IF EXISTS user_role CASCADE;

-- Re-run migration
\i Backend/migrations/fix_user_role_enum.sql
```

**3. "permission denied" error**
```sql
-- Solution: Use service role key
-- Set SUPABASE_SERVICE_ROLE_KEY environment variable
-- Or use Supabase dashboard SQL Editor (has admin privileges)
```

**4. RLS policy conflicts**
```sql
-- Solution: Drop all policies first
DROP POLICY IF EXISTS admin_users_select_policy ON admin_users;
DROP POLICY IF EXISTS admin_users_insert_policy ON admin_users;

-- Re-run migration
\i Backend/migrations/supabase_admin_system_complete.sql
```

## Post-Migration Verification

**After applying all migrations:**

1. **Test admin login:**
   ```bash
   curl -X POST https://<domain>.railway.app/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"admin@example.com","password":"admin_password"}'
   ```

2. **Check database health:**
   ```bash
   curl https://<domain>.railway.app/api/v1/database/health
   ```

3. **Verify RLS policies:**
   ```sql
   -- Should return policies for admin tables
   SELECT schemaname, tablename, policyname
   FROM pg_policies
   WHERE schemaname = 'public';
   ```

## Migration Best Practices

1. **Always backup before migrations:**
   ```bash
   # Supabase auto-backups, but verify
   # Dashboard > Database > Backups
   ```

2. **Test migrations locally first:**
   - Use local Supabase instance
   - Test all migrations in order
   - Verify data integrity

3. **Use transactions:**
   ```sql
   BEGIN;
   \i Backend/migrations/001_create_admin_tables.sql
   -- Check results
   COMMIT;  -- or ROLLBACK if issues
   ```

4. **Document migration changes:**
   - Update this guide for new migrations
   - Include rollback procedures
   - Note breaking changes

---

**Last Updated:** 2025-10-01
**Version:** 2.0.0
