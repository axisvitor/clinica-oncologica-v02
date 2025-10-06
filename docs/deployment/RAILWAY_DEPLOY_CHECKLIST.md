# Railway Deployment Checklist - Production Ready

## 🎯 Quick Start (10 Minutes to Fix)

### Prerequisites
- [x] All code changes committed (✅ Done - commit `acf1026`)
- [x] Local `.env` files updated (✅ Done)
- [ ] Access to Railway dashboard
- [ ] Access to local terminal (for Firebase script)

---

## Step 1: Fix Firebase Custom Claims (5 minutes)

### 1.1 Run Firebase Script Locally

```bash
# Navigate to backend directory
cd backend-hormonia

# Run the script (loads .env automatically)
python scripts/fix_firebase_custom_claims.py
```

**Expected Output**:
```
================================================================================
Firebase Custom Claims Fix Script
================================================================================
🔍 Validating environment variables...
✅ All required environment variables are set
🔧 Initializing Firebase Admin SDK...
✅ Firebase initialized for project: sistema-oncologico-auth

🎯 Target user:
   Email: admin@neoplasiaslitoral.com
   UID: xrqu2gDVL6eGfyNUiwxJlwVBbb73

👤 Setting custom claims for: admin@neoplasiaslitoral.com
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
```

### 1.2 Troubleshooting

**If you see "Missing environment variables"**:
```bash
# Make sure you're in backend-hormonia directory
pwd  # Should show: .../clinica-oncologica-v02/backend-hormonia

# Check .env file exists
ls -la .env

# Manually load .env if needed (Linux/Mac)
export $(cat .env | grep -v '^#' | xargs)

# Or on Windows PowerShell
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2])
    }
}
```

**If you see "User not found"**:
- User might not exist in Firebase yet
- Run `list_users()` option in script to see all users
- Contact admin to verify Firebase user exists

---

## Step 2: Update Railway DATABASE_URL (2 minutes)

### 2.1 Copy the Correct URL

**Copy this exact value** (including `+psycopg`):
```
postgresql+psycopg://postgres.rszpypytdciggybbpnrp:NvbKfi1xMY7wzNof@aws-0-sa-east-1.pooler.supabase.com:5432/postgres
```

### 2.2 Update in Railway Dashboard

1. Open Railway dashboard: https://railway.app
2. Select project: `clinica-oncologica-v02`
3. Click on **Backend Service**
4. Go to **Variables** tab
5. Find `DATABASE_URL` variable
6. Click **Edit**
7. **Paste** the URL from step 2.1 (replace entire value)
8. Click **Save**

### 2.3 Wait for Redeploy

Railway will automatically redeploy (takes ~2-3 minutes):

- Watch the **Deployments** tab
- Wait for status: ✅ **Success**
- Check logs for startup message

**Expected logs**:
```
INFO:     Started server process [1]
INFO:     Waiting for application startup.
DEBUG:    Database engine initialized: postgresql+psycopg://postgres.***
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080
```

---

## Step 3: Verify Fix Works (3 minutes)

### 3.1 Test Authentication Endpoint

```bash
# Get a fresh Firebase token (login to frontend)
# Copy token from browser DevTools → Application → Local Storage

# Test authenticated endpoint
curl -X GET \
  'https://clinica-oncologica-v02-production.up.railway.app/api/v1/auth/me' \
  -H 'Authorization: Bearer YOUR_FIREBASE_TOKEN_HERE'
```

**✅ Expected Response** (HTTP 200):
```json
{
  "id": "...",
  "email": "admin@neoplasiaslitoral.com",
  "role": "admin",
  "firebase_uid": "xrqu2gDVL6eGfyNUiwxJlwVBbb73"
}
```

**❌ If you still get 401**:
1. Make sure user logged out and back in (to get fresh token)
2. Check Railway logs for "Invalid role" errors
3. Verify Firebase script actually ran successfully

### 3.2 Check Railway Logs

Open Railway → Backend Service → **Logs**

**✅ Look for these SUCCESS indicators**:
```
✅ Auth request succeeded: 200 OK
✅ Database connection successful
✅ Audit log persisted to database
✅ Request completed in < 1 second
```

**❌ Should NOT see these ERRORS**:
```
❌ Missing role in custom claims
❌ Invalid role in custom claims: {}
❌ SCRAM exchange: Wrong password
❌ Request took 5-7 seconds
❌ HTTP 401 Unauthorized
```

### 3.3 Test WebSocket Connection

1. Open frontend application
2. Login with admin credentials
3. Check browser console for WebSocket connection

**✅ Expected**:
```
WebSocket connected: wss://clinica-oncologica-v02-production.up.railway.app/ws/connect
Status: 101 Switching Protocols
Authentication: SUCCESS
```

**❌ If connection fails**:
- Check Railway logs for "invalid token" errors
- Verify Firebase token has custom claims (decode at https://jwt.io)
- Make sure user logged out and back in

### 3.4 Verify Audit Logging

1. Open Supabase dashboard: https://supabase.com
2. Go to **SQL Editor**
3. Run query:
   ```sql
   SELECT * FROM audit_log_entries
   ORDER BY created_at DESC
   LIMIT 10;
   ```

**✅ Expected**: Recent entries with `created_at` timestamps from last few minutes

**❌ If empty**: Check Railway logs for database connection errors

---

## 🚨 Rollback Plan (If Something Goes Wrong)

### If Firebase Script Fails
```bash
# No rollback needed - script is read-only if it fails
# Just fix the error and run again
```

### If Railway Deployment Fails

1. **Revert DATABASE_URL** to old value (if you saved it)
2. **Or** use this temporary URL (old password, may not work):
   ```
   postgresql://postgres.rszpypytdciggybbpnrp:OLD_PASSWORD@...
   ```
3. **Contact support** if database connection is completely broken

### Emergency Contact
- Check Railway status: https://status.railway.app
- Check Supabase status: https://status.supabase.com
- Review logs in [RAILWAY_LOGS_REVIEW.md](RAILWAY_LOGS_REVIEW.md)

---

## ✅ Success Criteria

After completing all steps, verify:

- [ ] **Firebase script succeeded** (shows custom claims in output)
- [ ] **Railway redeployed successfully** (status: ✅ Success)
- [ ] **Auth endpoint returns 200** (not 401)
- [ ] **Request time < 1 second** (not 5-7 seconds)
- [ ] **WebSocket connects** (101 status)
- [ ] **Audit logs persist** (visible in Supabase)
- [ ] **No "Wrong password" errors** in Railway logs

---

## 📊 Performance Comparison

### Before Fix
- Auth request time: **5-7 seconds**
- HTTP status: **401 Unauthorized**
- Database errors: **SCRAM exchange: Wrong password**
- WebSocket auth: **Failed**
- Audit logs: **Not persisting**

### After Fix
- Auth request time: **< 1 second** ✅
- HTTP status: **200 OK** ✅
- Database errors: **None** ✅
- WebSocket auth: **Success** ✅
- Audit logs: **Persisting** ✅

---

## 🔗 Related Documentation

- [RAILWAY_AUTH_FIX_CRITICAL.md](RAILWAY_AUTH_FIX_CRITICAL.md) - Detailed technical explanation
- [RAILWAY_PSYCOPG_FIX.md](RAILWAY_PSYCOPG_FIX.md) - psycopg v3 migration details
- [RAILWAY_VARIABLES_COMPLETE.md](RAILWAY_VARIABLES_COMPLETE.md) - All environment variables
- [backend-hormonia/scripts/README.md](../../backend-hormonia/scripts/README.md) - Firebase scripts

---

## 📝 Post-Deployment Notes

After successful deployment, add to your team documentation:

1. **Firebase Custom Claims**: All new admin users must have custom claims set
2. **DATABASE_URL Format**: Always use `postgresql+psycopg://` for Python 3.13
3. **Token Refresh**: Users must logout/login after claim changes
4. **Audit Logs**: Check Supabase weekly for security events

---

**Last Updated**: 2025-10-06
**Estimated Time**: 10 minutes total
**Difficulty**: Easy (copy-paste and verify)
