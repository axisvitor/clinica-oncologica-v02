# 🚨 CRITICAL: Railway Authentication Fix - Firebase + Database

## ❌ Current Production Errors (High Severity)

### Error 1: Firebase Custom Claims Missing Role
```
Missing role in custom claims
Invalid role in custom claims: {}
HTTP 401 (every authenticated request)
Request time: ~5-7 seconds
```

**Impact**: ALL protected endpoints reject tokens. Authentication completely broken.

### Error 2: Supabase Audit Logging Failure
```
psycopg.OperationalError: connection failed: SCRAM exchange: Wrong password
```

**Impact**: Security audit logs not persisting. Compliance violation (LGPD).

---

## 🔍 Root Cause Analysis

### Problem 1: Firebase Token Missing Required Claims

**Current State**:
- Firebase Admin SDK issues tokens without `role` field in custom claims
- Backend expects `custom_claims.role` to be present
- Validation fails at [firebase_user_sync_service.py:213-218](../../backend-hormonia/app/services/firebase_user_sync_service.py#L213)

**Code Location**:
```python
# app/services/firebase_user_sync_service.py:211-218
role = custom_claims.get('role')

if not role:
    logger.warning(
        "Missing role in custom claims",
        extra={"custom_claims": custom_claims, "reason": "missing_role"}
    )
    return False  # ❌ Rejects all tokens without role
```

### Problem 2: Railway DATABASE_URL Still Using Old Password

**Current State**:
- Local `.env` has correct DATABASE_URL (updated in commit `acf1026`)
- Railway environment variable NOT updated yet
- Every database operation fails with "Wrong password"

**Evidence from Logs**:
```
05:52:31 - First auth request → creates DB session
05:52:31 - Firebase validation fails → tries to log to audit table
05:52:31 - Postgres connection: SCRAM exchange: Wrong password
05:52:36 - Request times out after ~5 seconds (401)
```

---

## ✅ Solution Part 1: Fix Firebase Custom Claims

### Step 1: Run Firebase Custom Claims Script

**Location**: `backend-hormonia/scripts/fix_firebase_custom_claims.py`

**What it does**:
- Loads Firebase Admin SDK credentials
- Sets custom claims for admin user `xrqu2gDVL6eGfyNUiwxJlwVBbb73`
- Adds required `role`, `roles`, `permissions`, `email_verified` fields

**Execute Locally** (requires service account key):

```bash
cd backend-hormonia

# Verify Firebase credentials are set
echo $FIREBASE_ADMIN_PROJECT_ID  # Should output: sistema-oncologico-auth
echo $FIREBASE_ADMIN_CLIENT_EMAIL  # Should output: firebase-adminsdk-fbsvc@...

# Run the script
python scripts/fix_firebase_custom_claims.py
```

**Expected Output**:
```
✅ Custom claims set successfully for xrqu2gDVL6eGfyNUiwxJlwVBbb73
Role: admin
Roles: ['admin', 'super_admin']
Permissions: ['read', 'write', 'delete', 'admin']
```

### Step 2: Verify Custom Claims

**Test with Firebase Token**:
```bash
# Get a fresh token after running the script
# Decode token at https://jwt.io

# Custom claims should now include:
{
  "role": "admin",
  "roles": ["admin", "super_admin"],
  "permissions": ["read", "write", "delete", "admin"],
  "email_verified": true,
  "system": "neoplasias-litoral",
  "created_by": "admin_script"
}
```

---

## ✅ Solution Part 2: Update Railway DATABASE_URL

### Critical: DATABASE_URL Must Use psycopg Driver

**❌ Current Railway Variable** (WRONG - causes connection errors):
```bash
# This has the OLD password that doesn't work
DATABASE_URL=postgresql://...  # Wrong password + wrong driver
```

**✅ Required Railway Variable** (CORRECT):
```bash
DATABASE_URL=postgresql+psycopg://postgres.rszpypytdciggybbpnrp:NvbKfi1xMY7wzNof@aws-0-sa-east-1.pooler.supabase.com:5432/postgres
```

### Update in Railway Dashboard

1. **Navigate to**: Railway Project → Backend Service → Variables
2. **Find**: `DATABASE_URL` variable
3. **Replace with**:
   ```
   postgresql+psycopg://postgres.rszpypytdciggybbpnrp:NvbKfi1xMY7wzNof@aws-0-sa-east-1.pooler.supabase.com:5432/postgres
   ```
4. **Save** and wait for auto-redeploy

### Why Both Changes Are Required

| Component | Requirement | Reason |
|-----------|-------------|--------|
| `+psycopg` | Python 3.13 compatibility | Avoids `psycopg2` import error |
| New password | Supabase credentials | Old password is invalid |
| Pooler URL | Production performance | Better connection management |

---

## 📋 Complete Deployment Checklist

### Phase 1: Local Setup (Do This First)

- [ ] **1.1** Verify `.env` files are correct (already updated in commit `acf1026`)
  ```bash
  cd backend-hormonia
  grep DATABASE_URL .env
  # Should show: postgresql+psycopg://postgres.rszpypytdciggybbpnrp:...
  ```

- [ ] **1.2** Run Firebase custom claims script locally
  ```bash
  python scripts/fix_firebase_custom_claims.py
  # Verify output shows ✅ success
  ```

- [ ] **1.3** Test Firebase token has role claim
  ```bash
  # Login to frontend/quiz app
  # Copy access token from browser DevTools
  # Decode at https://jwt.io
  # Verify "role": "admin" is present
  ```

### Phase 2: Railway Deployment

- [ ] **2.1** Update DATABASE_URL in Railway dashboard
  ```
  DATABASE_URL=postgresql+psycopg://postgres.rszpypytdciggybbpnrp:NvbKfi1xMY7wzNof@aws-0-sa-east-1.pooler.supabase.com:5432/postgres
  ```

- [ ] **2.2** Wait for Railway auto-redeploy (2-3 minutes)

- [ ] **2.3** Monitor Railway logs for successful startup
  ```
  ✅ Expected logs:
  INFO:     Application startup complete.
  INFO:     Uvicorn running on http://0.0.0.0:8080
  DEBUG:    Database engine initialized: postgresql+psycopg://postgres.***
  ```

### Phase 3: Verification

- [ ] **3.1** Test authenticated endpoint
  ```bash
  curl -H "Authorization: Bearer <firebase-token>" \
       https://clinica-oncologica-v02-production.up.railway.app/api/v1/auth/me

  # ✅ Expected: HTTP 200 (not 401)
  # ✅ Expected response time: < 1 second (not 5-7 seconds)
  ```

- [ ] **3.2** Verify audit logging works
  ```bash
  # Login to Supabase dashboard
  # Check audit_log_entries table
  # Verify new entries are being created (timestamp recent)
  ```

- [ ] **3.3** Test WebSocket authentication
  ```bash
  # Connect via frontend
  # WebSocket should connect with 101 status
  # Verify authentication succeeds (not "invalid token")
  ```

- [ ] **3.4** Check Railway logs for no errors
  ```
  ❌ Should NOT see:
  - "Wrong password"
  - "Invalid role in custom claims: {}"
  - "Missing role in custom claims"
  - Request time > 1s
  ```

---

## 🔧 Technical Details

### Firebase Custom Claims Schema

**Required Structure**:
```json
{
  "role": "admin",              // ✅ REQUIRED - Primary role
  "roles": ["admin", "super_admin"],  // ✅ REQUIRED - Role array
  "permissions": ["read", "write", "delete", "admin"],  // ✅ REQUIRED
  "email_verified": true,       // ✅ REQUIRED
  "system": "neoplasias-litoral",  // Optional metadata
  "created_by": "admin_script"  // Optional metadata
}
```

**Validation Logic** ([firebase_user_sync_service.py:197-230](../../backend-hormonia/app/services/firebase_user_sync_service.py#L197)):
```python
def _validate_custom_claims(self, custom_claims: Dict[str, Any]) -> bool:
    # Check if require_custom_claims is enabled (default: true)
    if not self._security_config['require_custom_claims']:
        return True

    # Extract role field
    role = custom_claims.get('role')

    # ❌ FAIL if missing
    if not role:
        return False

    # ❌ FAIL if not in allowed_roles
    allowed_roles = ['admin', 'super_admin', 'doctor', 'medico']
    if role.lower() not in allowed_roles:
        return False

    return True  # ✅ PASS
```

### Database Connection Flow

**Request Lifecycle**:
```
1. HTTP Request arrives (e.g., GET /api/v1/auth/me)
2. FastAPI creates DB session using DATABASE_URL
3. Firebase token validation fails (missing role)
4. Tries to log rejection to audit_log_entries table
5. Uses same DB session → tries to connect with DATABASE_URL
6. ❌ Connection fails: Wrong password
7. Request times out (~5s) → returns 401
```

**Why Audit Logging Fails**:
- Uses `self.db.execute()` from request session
- Session configured with Railway's DATABASE_URL
- Railway's DATABASE_URL has old/wrong password
- Every audit write fails with SCRAM authentication error

---

## 🚨 Common Mistakes to Avoid

### ❌ DON'T: Copy-paste without reading

```bash
# WRONG - Missing +psycopg driver
DATABASE_URL=postgresql://postgres.rszpypytdciggybbpnrp:...

# WRONG - Old password
DATABASE_URL=postgresql+psycopg://postgres.rszpypytdciggybbpnrp:OLD_PASSWORD@...
```

### ❌ DON'T: Skip Firebase script

```
Without custom claims fix:
- All auth requests will fail with 401
- WebSocket authentication will fail
- Audit logs will show "invalid_claims" errors
```

### ❌ DON'T: Test before Railway redeploys

```
After updating DATABASE_URL:
1. Wait for "Deployment successful" in Railway
2. THEN test endpoints
3. Otherwise you'll test against old deployment
```

### ✅ DO: Follow exact order

```
Order matters:
1. Run Firebase script FIRST (local)
2. Update DATABASE_URL in Railway
3. Wait for redeploy
4. Test authentication
5. Verify audit logs
```

---

## 📊 Expected Performance After Fix

### Before Fix
| Metric | Value | Status |
|--------|-------|--------|
| Auth Request Time | 5-7 seconds | ❌ Timeout |
| HTTP Status | 401 Unauthorized | ❌ Rejected |
| Audit Logs | Failed (wrong password) | ❌ No logs |
| WebSocket Auth | Failed (invalid token) | ❌ Rejected |

### After Fix
| Metric | Value | Status |
|--------|-------|--------|
| Auth Request Time | < 1 second | ✅ Fast |
| HTTP Status | 200 OK | ✅ Success |
| Audit Logs | Persisted to database | ✅ Working |
| WebSocket Auth | Success (101 Switching Protocols) | ✅ Connected |

---

## 🔗 Related Documentation

- [RAILWAY_PSYCOPG_FIX.md](RAILWAY_PSYCOPG_FIX.md) - psycopg v3 migration details
- [RAILWAY_VARIABLES_COMPLETE.md](RAILWAY_VARIABLES_COMPLETE.md) - Complete environment variables
- [backend-hormonia/scripts/README.md](../../backend-hormonia/scripts/README.md) - Firebase script usage
- [RAILWAY_LOGS_REVIEW.md](RAILWAY_LOGS_REVIEW.md) - Initial log analysis

---

## 📝 Summary

| Issue | Root Cause | Solution | Status |
|-------|-----------|----------|--------|
| Auth 401 Errors | Firebase tokens missing `role` claim | Run `fix_firebase_custom_claims.py` | ⏳ Pending |
| Audit Log Failures | Railway DATABASE_URL has old password | Update to `postgresql+psycopg://...` | ⏳ Pending |
| Slow Requests | Timeout waiting for failed DB connection | Fixed by updating DATABASE_URL | ⏳ Auto-fixed |
| WebSocket Auth | Same as Auth 401 (missing claims) | Fixed by Firebase script | ⏳ Pending |

**Critical Path**:
1. ✅ Local `.env` files updated (commit `acf1026`)
2. ⏳ **YOU**: Run Firebase script locally
3. ⏳ **YOU**: Update Railway DATABASE_URL
4. ⏳ **Railway**: Auto-redeploy (2-3 min)
5. ✅ **System**: Authentication working, audit logs persisting

---

**Last Updated**: 2025-10-06
**Severity**: 🔴 CRITICAL - Production auth completely broken
**ETA to Fix**: ~10 minutes (5 min Firebase script + 5 min Railway redeploy)
