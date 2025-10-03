# Firebase-PostgreSQL Synchronization Implementation

## Overview

Complete Firebase Authentication integration with PostgreSQL database synchronization. This implementation supports:

- **Dual Authentication**: Both Firebase and local authentication
- **Auto User Creation**: Firebase users automatically synced to PostgreSQL
- **Role Management**: 2 roles only (ADMIN, DOCTOR)
- **Audit Trail**: Complete sync operation logging
- **Domain Validation**: Email domain whitelisting

## Files Created

### 1. Database Migration
**Location**: `alembic/versions/20250930_add_firebase_fields.py`

Adds 9 Firebase fields to users table:
- `firebase_uid` - Firebase user ID (unique, indexed)
- `auth_provider` - Authentication provider (local/firebase)
- `firebase_last_sign_in` - Last sign-in timestamp
- `firebase_created_at` - Firebase account creation
- `firebase_email_verified` - Email verification status
- `firebase_display_name` - Display name from Firebase
- `firebase_photo_url` - Profile photo URL
- `firebase_custom_claims` - JSONB custom claims (roles)
- `last_firebase_sync` - Last sync timestamp

Also creates `user_sync_log` audit table.

### 2. User Model Update
**Location**: `app/models/user.py`

**Changes**:
- Reduced roles from 7 to 2: `ADMIN`, `DOCTOR`
- Added `AuthProvider` enum: `LOCAL`, `FIREBASE`
- Added Firebase authentication fields
- Made `hashed_password` nullable (Firebase users don't need it)

### 3. Sync Service
**Location**: `app/services/firebase_user_sync_service.py`

**Class**: `FirebaseUserSyncService`

**Key Methods**:
- `sync_firebase_user()` - Main sync entry point
- `_create_user_from_firebase()` - Create new users
- `_update_user_from_firebase()` - Update existing users
- `_link_firebase_to_user()` - Link Firebase to local users
- `get_or_create_user()` - Convenience method
- `validate_firebase_user()` - Validate user and role

### 4. Sync Log Model
**Location**: `app/models/user_sync_log.py`

**Class**: `UserSyncLog`

Audit trail table tracking all sync operations with:
- Firebase UID and PostgreSQL user ID
- Operation type (create, update, link, sync)
- Sync direction (firebase_to_pg, pg_to_firebase)
- Changes made (JSONB)
- Success/failure status
- Error messages

## Database Schema

### Updated `users` Table

```sql
-- Existing fields
email VARCHAR(255) UNIQUE NOT NULL
hashed_password VARCHAR(255) NULL  -- NOW NULLABLE
full_name VARCHAR(255)
role user_role NOT NULL DEFAULT 'doctor'  -- ONLY admin, doctor
is_active BOOLEAN DEFAULT true

-- New Firebase fields
firebase_uid VARCHAR(255) UNIQUE
auth_provider auth_provider DEFAULT 'local'
firebase_last_sign_in TIMESTAMP WITH TIME ZONE
firebase_created_at TIMESTAMP WITH TIME ZONE
firebase_email_verified BOOLEAN DEFAULT false
firebase_display_name VARCHAR(255)
firebase_photo_url VARCHAR(500)
firebase_custom_claims JSONB DEFAULT '{}'
last_firebase_sync TIMESTAMP WITH TIME ZONE

-- Indexes
CREATE INDEX idx_users_firebase_uid ON users(firebase_uid);
CREATE INDEX idx_users_auth_provider ON users(auth_provider);
```

### New `user_sync_log` Table

```sql
CREATE TABLE user_sync_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firebase_uid VARCHAR(255) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    operation VARCHAR(50) NOT NULL,
    sync_direction VARCHAR(20) NOT NULL,
    changes JSONB DEFAULT '{}',
    success BOOLEAN NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_user_sync_log_firebase_uid ON user_sync_log(firebase_uid);
CREATE INDEX idx_user_sync_log_user_id ON user_sync_log(user_id);
CREATE INDEX idx_user_sync_log_created_at ON user_sync_log(created_at);
```

## User Roles (SIMPLIFIED)

**Only 2 roles supported** (reduced from 7):

1. **ADMIN** - Full system access
   - User management
   - System configuration
   - All data access

2. **DOCTOR** - Clinical operations
   - Patient management
   - Medical reports
   - Clinical workflows

**Role Mapping from Firebase**:
- `admin` or `super_admin` → `ADMIN`
- Any other role → `DOCTOR` (default)

## Email Domain Whitelist

**Authorized domains** (configured in `firebase_user_sync_service.py`):
```python
AUTHORIZED_DOMAINS = [
    'neoplasiaslitoral.com',  # Hospital domain
    'hospital.local',          # Development
    'gmail.com'                # Testing only - REMOVE IN PRODUCTION
]
```

**Important**: Remove `gmail.com` before production deployment!

## Sync Flow

### 1. First-Time User (Auto-Creation)

```
Firebase Login
    ↓
Firebase JWT Token
    ↓
verify_token() → Extract user data
    ↓
sync_firebase_user(auto_create=True)
    ↓
Validate email domain
    ↓
Create user in PostgreSQL
    ↓
Set role from custom claims
    ↓
Log to user_sync_log
    ↓
Return User object
```

### 2. Existing User (Update)

```
Firebase Login
    ↓
Find user by firebase_uid
    ↓
Update metadata (email, name, photo)
    ↓
Update last_sign_in timestamp
    ↓
Log to user_sync_log
    ↓
Return User object
```

### 3. Migration (Link Local to Firebase)

```
Local user exists
    ↓
Firebase login with same email
    ↓
Find by email (not firebase_uid)
    ↓
Link firebase_uid to user
    ↓
Update auth_provider to 'firebase'
    ↓
Log to user_sync_log
    ↓
Return User object
```

## Usage Examples

### Example 1: Sync User from Firebase Token

```python
from app.services.firebase_user_sync_service import FirebaseUserSyncService
from app.services.firebase_auth_service import get_firebase_auth_service

# Initialize services
firebase_auth = get_firebase_auth_service(
    project_id="your-project",
    private_key="...",
    client_email="..."
)
sync_service = FirebaseUserSyncService(db, firebase_auth)

# Verify token and sync user
firebase_data = await firebase_auth.verify_token(token)
user, created = await sync_service.sync_firebase_user(
    firebase_uid=firebase_data['uid'],
    firebase_data=firebase_data,
    auto_create=True
)

if created:
    print(f"Created new user: {user.email}")
else:
    print(f"Updated existing user: {user.email}")
```

### Example 2: Get or Create User

```python
# Simplified version - always creates if not found
user = await sync_service.get_or_create_user(
    firebase_uid=firebase_data['uid'],
    firebase_data=firebase_data
)
```

### Example 3: Validate User with Role

```python
# Validate user exists and has required role
user = await sync_service.validate_firebase_user(
    firebase_uid="firebase-uid-123",
    required_role=UserRole.ADMIN
)

if user:
    print(f"Valid admin user: {user.email}")
else:
    print("User not found or insufficient permissions")
```

### Example 4: Link Local User to Firebase

```python
# User exists with local auth, now linking to Firebase
user, created = await sync_service.sync_firebase_user(
    firebase_uid="new-firebase-uid",
    firebase_data=firebase_data,
    auto_create=False  # Don't create, only link
)
# User's auth_provider is now 'firebase'
```

## Integration with Authentication

### Update Authentication Dependencies

**File**: `app/dependencies/auth.py` (if it exists)

```python
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.services.firebase_auth_service import get_firebase_auth_service
from app.services.firebase_user_sync_service import FirebaseUserSyncService
from app.database import get_db
from app.models.user import User

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user from Firebase token."""

    # Verify Firebase token
    firebase_auth = get_firebase_auth_service(...)
    firebase_data = await firebase_auth.verify_token(token)

    # Sync to database
    sync_service = FirebaseUserSyncService(db, firebase_auth)
    user, _ = await sync_service.sync_firebase_user(
        firebase_uid=firebase_data['uid'],
        firebase_data=firebase_data,
        auto_create=True
    )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account disabled")

    return user

async def require_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """Require ADMIN role."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
```

## Running the Migration

### Step 1: Backup Database

```bash
cd c:\exclusivo\clinica-oncologica-v01\Backend

# Backup PostgreSQL database
pg_dump -U postgres -d oncology_clinic > backup_$(date +%Y%m%d).sql
```

### Step 2: Run Migration

```bash
# Activate virtual environment
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Run migration
alembic upgrade head

# Verify migration
alembic current
# Should show: add_firebase_fields
```

### Step 3: Verify Database Changes

```sql
-- Check users table structure
\d users;

-- Check new columns exist
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'users'
AND column_name LIKE 'firebase%';

-- Check user_sync_log table
\d user_sync_log;

-- Check user roles (should only be admin, doctor)
SELECT DISTINCT role FROM users;
```

### Step 4: Test Sync

```python
# Test script: test_firebase_sync.py
import asyncio
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.services.firebase_user_sync_service import FirebaseUserSyncService
from app.services.firebase_auth_service import get_firebase_auth_service

async def test_sync():
    db = SessionLocal()

    firebase_auth = get_firebase_auth_service(
        project_id="your-project-id",
        private_key="...",
        client_email="..."
    )

    sync_service = FirebaseUserSyncService(db, firebase_auth)

    # Test data (simulate Firebase token data)
    test_data = {
        'uid': 'test-firebase-uid-123',
        'email': 'doctor@neoplasiaslitoral.com',
        'name': 'Dr. Test User',
        'email_verified': True,
        'custom_claims': {'role': 'doctor'},
        'auth_time': 1727654400
    }

    user, created = await sync_service.sync_firebase_user(
        firebase_uid=test_data['uid'],
        firebase_data=test_data,
        auto_create=True
    )

    print(f"User: {user.email}")
    print(f"Created: {created}")
    print(f"Role: {user.role.value}")
    print(f"Auth Provider: {user.auth_provider.value}")
    print(f"Firebase UID: {user.firebase_uid}")

if __name__ == "__main__":
    asyncio.run(test_sync())
```

## Rollback Plan

If issues occur:

```bash
# Rollback migration
alembic downgrade -1

# Or rollback to specific version
alembic downgrade 20250930_011500

# Restore from backup if needed
psql -U postgres -d oncology_clinic < backup_20250930.sql
```

## Monitoring and Logging

### Check Sync Operations

```sql
-- View recent sync operations
SELECT
    firebase_uid,
    operation,
    success,
    error_message,
    created_at
FROM user_sync_log
ORDER BY created_at DESC
LIMIT 50;

-- Count operations by type
SELECT
    operation,
    sync_direction,
    success,
    COUNT(*) as count
FROM user_sync_log
GROUP BY operation, sync_direction, success;

-- Find failed syncs
SELECT *
FROM user_sync_log
WHERE success = false
ORDER BY created_at DESC;
```

### Application Logs

Check application logs for sync issues:

```bash
# Watch logs
tail -f logs/app.log | grep "Firebase\|sync"

# Search for errors
grep -i "error.*firebase" logs/app.log
```

## Security Considerations

1. **Domain Whitelist**: Only authorized email domains can auto-create accounts
2. **Email Verification**: Track Firebase email verification status
3. **Audit Trail**: All sync operations logged with success/failure
4. **Role Validation**: Roles validated and mapped from Firebase custom claims
5. **Token Verification**: All tokens verified against Firebase before sync

## Performance Notes

1. **Indexes**: Firebase UID and auth provider indexed for fast lookups
2. **Nullable Password**: Firebase users don't store passwords (saves hashing overhead)
3. **Sync Timestamps**: Track last sync to avoid unnecessary updates
4. **Batch Operations**: Audit logging doesn't block main sync flow

## Production Checklist

- [ ] Remove `gmail.com` from AUTHORIZED_DOMAINS
- [ ] Configure proper Firebase service account
- [ ] Set up monitoring for failed syncs
- [ ] Create dashboard for sync statistics
- [ ] Document role assignment process
- [ ] Train admins on user management
- [ ] Set up alerts for sync failures
- [ ] Test migration on staging environment
- [ ] Backup production database before migration
- [ ] Plan rollback strategy
- [ ] Schedule maintenance window
- [ ] Notify users of authentication changes

## Troubleshooting

### Issue: User creation fails with domain error

**Solution**: Add domain to AUTHORIZED_DOMAINS or use existing authorized domain

### Issue: Role not syncing correctly

**Solution**: Check Firebase custom claims format:
```json
{
  "custom_claims": {
    "role": "admin"  // or "doctor"
  }
}
```

### Issue: Migration fails with constraint error

**Solution**: Check for existing users without emails or with invalid roles

### Issue: Duplicate users created

**Solution**: Migration should find by email first - check `sync_firebase_user()` logic

## Support and Maintenance

### Regular Maintenance Tasks

1. **Weekly**: Review sync logs for failures
2. **Monthly**: Analyze sync patterns and performance
3. **Quarterly**: Review and update AUTHORIZED_DOMAINS

### Contact

For issues or questions:
- Check logs: `logs/app.log`
- Review audit: `user_sync_log` table
- Contact: Backend development team

---

**Implementation Date**: 2025-09-30
**Migration Version**: add_firebase_fields
**Previous Version**: 20250930_011500
**Roles Supported**: ADMIN, DOCTOR (2 roles only)
