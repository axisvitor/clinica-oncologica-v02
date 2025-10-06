# User Sync Log Migration Fix

## Problem

The `user_sync_log` table was created by migration `20250930_add_firebase_fields.py` but was missing the `updated_at` column. This caused INSERT failures because:

1. The `UserSyncLog` model inherits from `BaseModel`
2. `BaseModel` defines `updated_at` as a required column
3. Every INSERT into `user_sync_log` failed with: **"column user_sync_log.updated_at does not exist"**

## Root Cause

In migration `20250930_add_firebase_fields.py` (lines 69-80):
- Only `created_at` was included when creating the table
- `updated_at` was omitted, breaking the model-database contract

```python
# Original migration (INCOMPLETE)
op.create_table(
    'user_sync_log',
    sa.Column('id', sa.UUID(), primary_key=True),
    # ... other columns ...
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    # ❌ updated_at MISSING!
)
```

## Solution

Created follow-up migration `20251006_add_user_sync_log_updated_at.py` that:

### 1. Adds updated_at Column
```sql
ALTER TABLE user_sync_log
ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
```

### 2. Creates Auto-Update Trigger
```sql
CREATE OR REPLACE FUNCTION update_user_sync_log_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_user_sync_log_updated_at
BEFORE UPDATE ON user_sync_log
FOR EACH ROW
EXECUTE FUNCTION update_user_sync_log_updated_at();
```

### 3. Adds Performance Index
```sql
CREATE INDEX idx_user_sync_log_updated_at ON user_sync_log (updated_at);
```

## Migration Details

**File:** `backend-hormonia/alembic/versions/20251006_add_user_sync_log_updated_at.py`

**Revision ID:** `20251006_add_user_sync_log_updated_at`

**Revises:** `add_firebase_fields`

**Features:**
- ✅ Adds `updated_at` column with timezone support
- ✅ Sets default value to `NOW()` for existing rows
- ✅ Creates trigger for automatic updates on row modifications
- ✅ Adds index for query performance
- ✅ Includes proper downgrade path

## Deployment Instructions

### Apply Migration
```bash
cd backend-hormonia
alembic upgrade head
```

### Verify Migration
```sql
-- Check column exists
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'user_sync_log' AND column_name = 'updated_at';

-- Check trigger exists
SELECT trigger_name, event_manipulation, event_object_table
FROM information_schema.triggers
WHERE trigger_name = 'trigger_user_sync_log_updated_at';

-- Check index exists
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'user_sync_log' AND indexname = 'idx_user_sync_log_updated_at';
```

### Test Functionality
```python
# Test INSERT (should work now)
from app.models.user_sync_log import UserSyncLog
from app.database import get_db

log = UserSyncLog(
    firebase_uid="test_uid",
    operation="create",
    sync_direction="firebase_to_pg",
    success=True
)
db.add(log)
db.commit()
# ✅ Should succeed with both created_at and updated_at set

# Test UPDATE (trigger should auto-update updated_at)
log.success = False
db.commit()
# ✅ updated_at should be automatically updated to current timestamp
```

## Impact

### Before Fix
- ❌ All `UserSyncLog` inserts failed
- ❌ Firebase-PostgreSQL sync logging broken
- ❌ No audit trail for sync operations

### After Fix
- ✅ `UserSyncLog` inserts work correctly
- ✅ Sync audit trail functional
- ✅ Automatic timestamp tracking
- ✅ Query performance optimized with index

## Related Files

- **Model:** `backend-hormonia/app/models/user_sync_log.py`
- **Base Model:** `backend-hormonia/app/models/base.py`
- **Original Migration:** `backend-hormonia/alembic/versions/20250930_add_firebase_fields.py`
- **Fix Migration:** `backend-hormonia/alembic/versions/20251006_add_user_sync_log_updated_at.py`

## Prevention

To prevent similar issues in the future:

1. **Always check BaseModel inheritance** when creating tables in migrations
2. **Include all inherited columns** (`id`, `created_at`, `updated_at`)
3. **Add triggers** for `updated_at` auto-updates
4. **Test migrations** with actual model inserts before deploying

## Status

✅ **COMPLETED** - Migration created and ready for deployment
