# Backend Scripts

## Firebase Custom Claims Fix

### Purpose
Adds required custom claims (role, permissions) to Firebase users for Railway production deployment.

### Problem It Solves
Railway logs show:
```
ERROR - Invalid role in custom claims: {}
WARNING - User provisioning rejected: invalid_claims
```

This causes 401 Unauthorized on all authenticated endpoints.

### Usage

```bash
# From backend-hormonia directory
python scripts/fix_firebase_custom_claims.py
```

### What It Does

1. **Initializes Firebase Admin SDK** using environment variables
2. **Sets custom claims** for admin user:
   ```json
   {
     "role": "admin",
     "roles": ["admin", "super_admin"],
     "permissions": ["read", "write", "delete", "admin"],
     "email_verified": true
   }
   ```
3. **Verifies** the claims were set correctly
4. **Lists all users** (optional) for debugging

### Target User

- **UID**: `xrqu2gDVL6eGfyNUiwxJlwVBbb73`
- **Email**: `admin@neoplasiaslitoral.com`

### Requirements

Environment variables must be set (from `.env`):
- `FIREBASE_ADMIN_PROJECT_ID`
- `FIREBASE_ADMIN_PRIVATE_KEY`
- `FIREBASE_ADMIN_CLIENT_EMAIL`

### Expected Output

```
================================================================================
Firebase Custom Claims Fix Script
================================================================================
🔧 Initializing Firebase Admin SDK...
✅ Firebase initialized for project: sistema-oncologico-auth

🎯 Target user:
   Email: admin@neoplasiaslitoral.com
   UID: xrqu2gDVL6eGfyNUiwxJlwVBbb73

👤 Setting custom claims for: admin@neoplasiaslitoral.com (UID: xrqu2gDVL6eGfyNUiwxJlwVBbb73)
✅ Custom claims set successfully

📋 Verified custom claims:
{
  "role": "admin",
  "roles": ["admin", "super_admin"],
  "permissions": ["read", "write", "delete", "admin"],
  "email_verified": true,
  "system": "neoplasias-litoral",
  "created_by": "admin_script"
}

================================================================================
✅ SUCCESS - Custom claims updated!
================================================================================

📝 Next steps:
1. User must log out and log back in for changes to take effect
2. Verify in Railway logs that authentication succeeds (200 instead of 401)
3. Test endpoints:
   - GET /api/v1/auth/me
   - GET /api/v1/auth/notifications
   - GET /api/v1/analytics/dashboard
```

### After Running

1. **User must log out and log back in** (Firebase caches tokens)
2. **Check Railway logs** for successful authentication:
   ```
   ✅ User authenticated successfully (role: admin)
   ✅ REQUEST | GET /api/v1/auth/me | Status: 200
   ```
3. **Test authenticated endpoints** - should return 200 OK

### Troubleshooting

#### Import Error
```bash
# Make sure you're in backend-hormonia directory
cd backend-hormonia
python scripts/fix_firebase_custom_claims.py
```

#### Firebase Credentials Error
```bash
# Verify .env file has correct Firebase credentials
cat .env | grep FIREBASE_ADMIN
```

#### User Not Found
```bash
# List all users to find correct UID
python scripts/fix_firebase_custom_claims.py
# Choose option to list all users
```

### Alternative: Firebase Console UI

If script fails, you can set custom claims via Firebase Console:

1. Go to Firebase Console → Authentication
2. Select user `admin@neoplasiaslitoral.com`
3. Click "Edit user"
4. Under "Custom claims", add:
   ```json
   {"role":"admin","roles":["admin","super_admin"],"permissions":["read","write","delete","admin"],"email_verified":true}
   ```

### Related Documentation

- [RAILWAY_LOGS_REVIEW.md](../../docs/deployment/RAILWAY_LOGS_REVIEW.md)
- [RAILWAY_VARIABLES_COMPLETE.md](../../docs/deployment/RAILWAY_VARIABLES_COMPLETE.md)
