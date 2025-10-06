# Firebase-Only Environment Configuration Cleanup

## Executive Summary

This document provides a comprehensive audit and migration plan to remove Supabase-related environment variables and ensure proper Firebase-only configuration for production deployment on Railway.

**Status**: Ready for implementation
**Impact**: Medium (environment configuration only, no code changes)
**Risk**: Low (documentation only, actual .env files untouched)

---

## Issues Identified

### Backend Issues

1. **Security Risk**: `FIREBASE_BLOCK_PUBLIC_DOMAINS=false` (should be `true` in production)
2. **Unused Variables**: Supabase configuration variables still present despite Firebase-only deployment
3. **Auto-Provisioning**: `AUTO_PROVISION_SUPABASE_USERS=true` flag exists but is unused

### Frontend Issues

1. **Misleading Flag**: `VITE_SUPABASE_AUTH_ENABLED=true` (should be `false` for Firebase-only)
2. **Unused Variables**: Supabase client configuration still present

---

## Backend Environment Variables to Remove

### Supabase Authentication & API

```bash
# Remove these from Railway backend service:
SUPABASE_URL
SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
AUTO_PROVISION_SUPABASE_USERS
```

### Supabase RLS (Row-Level Security)

```bash
# Remove these from Railway backend service:
SUPABASE_USE_SERVICE_ROLE
SUPABASE_BYPASS_RLS
SUPABASE_JWT_HEADER_NAME
SUPABASE_JWT_PREFIX
```

### Total Backend Variables to Remove: **8**

---

## Frontend Environment Variables to Remove

### Supabase Client Configuration

```bash
# Remove these from Railway frontend service:
VITE_SUPABASE_URL
VITE_SUPABASE_ANON_KEY
VITE_SUPABASE_AUTH_ENABLED
VITE_SUPABASE_REALTIME_ENABLED
```

### Total Frontend Variables to Remove: **4**

---

## Required Firebase Variables (Backend)

### Firebase Admin SDK (Server-Side Authentication)

```bash
# ✅ REQUIRED - Keep these in Railway backend service:
FIREBASE_ADMIN_PROJECT_ID=your-firebase-project-id
FIREBASE_ADMIN_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
FIREBASE_ADMIN_CLIENT_EMAIL=firebase-adminsdk-xxxxx@your-project.iam.gserviceaccount.com
```

### Firebase Security Configuration

```bash
# ✅ REQUIRED - Security enforcement:
FIREBASE_BLOCK_PUBLIC_DOMAINS=true  # 🚨 MUST BE TRUE IN PRODUCTION
FIREBASE_REQUIRE_CUSTOM_CLAIMS=true
FIREBASE_ENABLE_AUDIT_LOGGING=true

# ✅ REQUIRED - Allowed domains (corporate/clinic emails only):
FIREBASE_ALLOWED_DOMAINS=["clinicahormonia.com.br", "hormonia.med.br"]

# ✅ REQUIRED - Allowed roles:
FIREBASE_ALLOWED_ROLES=["admin", "super_admin", "doctor", "medico"]

# ✅ OPTIONAL - Public domain blocklist (default includes gmail, yahoo, hotmail):
FIREBASE_PUBLIC_DOMAINS_BLOCKLIST=["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com"]
```

---

## Required Firebase Variables (Frontend)

### Firebase Client SDK (Browser-Side Authentication)

```bash
# ✅ REQUIRED - Keep these in Railway frontend service:
VITE_FIREBASE_API_KEY=AIzaSy...
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-project.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789
VITE_FIREBASE_APP_ID=1:123456789:web:abcdef
VITE_FIREBASE_MEASUREMENT_ID=G-XXXXXXXXXX
```

---

## Security Recommendations

### 🚨 Critical Security Settings

#### 1. Block Public Email Domains

**Current Issue**: `FIREBASE_BLOCK_PUBLIC_DOMAINS=false` in backend

```bash
# ❌ WRONG (Current):
FIREBASE_BLOCK_PUBLIC_DOMAINS=false

# ✅ CORRECT (Required):
FIREBASE_BLOCK_PUBLIC_DOMAINS=true
```

**Impact**: Prevents unauthorized user creation with gmail.com, yahoo.com, etc.

#### 2. Require Custom Claims

```bash
# ✅ CORRECT (Verify this is set):
FIREBASE_REQUIRE_CUSTOM_CLAIMS=true
```

**Impact**: Ensures all users have valid roles before account creation.

#### 3. Enable Audit Logging

```bash
# ✅ CORRECT (Verify this is set):
FIREBASE_ENABLE_AUDIT_LOGGING=true
```

**Impact**: Comprehensive logging of user provisioning for security audits.

#### 4. Restrict Allowed Domains

```bash
# ✅ CORRECT (Customize for your clinic):
FIREBASE_ALLOWED_DOMAINS=["clinicahormonia.com.br", "hormonia.med.br"]
```

**Impact**: Only corporate/clinic email addresses can create accounts.

---

## Migration Checklist

### Phase 1: Backend Railway Service

- [ ] **Remove Supabase Variables** (8 total)
  - [ ] `SUPABASE_URL`
  - [ ] `SUPABASE_ANON_KEY`
  - [ ] `SUPABASE_SERVICE_ROLE_KEY`
  - [ ] `AUTO_PROVISION_SUPABASE_USERS`
  - [ ] `SUPABASE_USE_SERVICE_ROLE`
  - [ ] `SUPABASE_BYPASS_RLS`
  - [ ] `SUPABASE_JWT_HEADER_NAME`
  - [ ] `SUPABASE_JWT_PREFIX`

- [ ] **Verify Firebase Admin SDK Variables** (3 required)
  - [ ] `FIREBASE_ADMIN_PROJECT_ID` is set
  - [ ] `FIREBASE_ADMIN_PRIVATE_KEY` is set (with proper line breaks)
  - [ ] `FIREBASE_ADMIN_CLIENT_EMAIL` is set

- [ ] **Update Firebase Security Variables** (Critical)
  - [ ] Set `FIREBASE_BLOCK_PUBLIC_DOMAINS=true` (🚨 **CRITICAL**)
  - [ ] Set `FIREBASE_REQUIRE_CUSTOM_CLAIMS=true`
  - [ ] Set `FIREBASE_ENABLE_AUDIT_LOGGING=true`
  - [ ] Configure `FIREBASE_ALLOWED_DOMAINS` with clinic domains
  - [ ] Verify `FIREBASE_ALLOWED_ROLES` contains correct roles

### Phase 2: Frontend Railway Service

- [ ] **Remove Supabase Variables** (4 total)
  - [ ] `VITE_SUPABASE_URL`
  - [ ] `VITE_SUPABASE_ANON_KEY`
  - [ ] `VITE_SUPABASE_AUTH_ENABLED`
  - [ ] `VITE_SUPABASE_REALTIME_ENABLED`

- [ ] **Verify Firebase Client SDK Variables** (7 required)
  - [ ] `VITE_FIREBASE_API_KEY` is set
  - [ ] `VITE_FIREBASE_AUTH_DOMAIN` is set
  - [ ] `VITE_FIREBASE_PROJECT_ID` is set
  - [ ] `VITE_FIREBASE_STORAGE_BUCKET` is set
  - [ ] `VITE_FIREBASE_MESSAGING_SENDER_ID` is set
  - [ ] `VITE_FIREBASE_APP_ID` is set
  - [ ] `VITE_FIREBASE_MEASUREMENT_ID` is set

### Phase 3: Deployment & Testing

- [ ] **Deploy Backend**
  - [ ] Redeploy backend service on Railway
  - [ ] Check Railway logs for Firebase initialization success
  - [ ] Verify no Supabase-related errors in logs

- [ ] **Deploy Frontend**
  - [ ] Redeploy frontend service on Railway
  - [ ] Test login with Firebase authentication
  - [ ] Verify no Supabase-related console errors

- [ ] **Security Testing**
  - [ ] Attempt login with public email (should be blocked)
  - [ ] Verify custom claims are required
  - [ ] Check audit logs for user provisioning

---

## Railway Deployment Commands

### Backend Service Variable Removal

```bash
# Remove Supabase variables
railway variables delete SUPABASE_URL --service backend-hormonia
railway variables delete SUPABASE_ANON_KEY --service backend-hormonia
railway variables delete SUPABASE_SERVICE_ROLE_KEY --service backend-hormonia
railway variables delete AUTO_PROVISION_SUPABASE_USERS --service backend-hormonia
railway variables delete SUPABASE_USE_SERVICE_ROLE --service backend-hormonia
railway variables delete SUPABASE_BYPASS_RLS --service backend-hormonia
railway variables delete SUPABASE_JWT_HEADER_NAME --service backend-hormonia
railway variables delete SUPABASE_JWT_PREFIX --service backend-hormonia
```

### Backend Service Firebase Security Update

```bash
# Update Firebase security settings (🚨 CRITICAL)
railway variables set FIREBASE_BLOCK_PUBLIC_DOMAINS=true --service backend-hormonia
railway variables set FIREBASE_REQUIRE_CUSTOM_CLAIMS=true --service backend-hormonia
railway variables set FIREBASE_ENABLE_AUDIT_LOGGING=true --service backend-hormonia

# Set allowed domains (customize for your clinic)
railway variables set FIREBASE_ALLOWED_DOMAINS='["clinicahormonia.com.br"]' --service backend-hormonia

# Set allowed roles
railway variables set FIREBASE_ALLOWED_ROLES='["admin","super_admin","doctor","medico"]' --service backend-hormonia
```

### Frontend Service Variable Removal

```bash
# Remove Supabase variables
railway variables delete VITE_SUPABASE_URL --service frontend-hormonia
railway variables delete VITE_SUPABASE_ANON_KEY --service frontend-hormonia
railway variables delete VITE_SUPABASE_AUTH_ENABLED --service frontend-hormonia
railway variables delete VITE_SUPABASE_REALTIME_ENABLED --service frontend-hormonia
```

### Redeploy Services

```bash
# Redeploy backend
railway service deploy backend-hormonia

# Redeploy frontend
railway service deploy frontend-hormonia
```

---

## Code Cleanup (Future)

### Files to Review (Do NOT modify now, document only)

The following files still contain Supabase references and should be cleaned up in a future refactor:

#### Backend Files

1. **Configuration Files**:
   - `backend-hormonia/app/config.py` - Supabase fields in Settings class
   - `backend-hormonia/app/config.py.backup` - Backup with Supabase config
   - `backend-hormonia/.env.railway.template` - Template with Supabase vars
   - `backend-hormonia/.env.quiz.example` - Quiz service with Supabase
   - `backend-hormonia/beat/.env.example` - Celery beat with Supabase
   - `backend-hormonia/worker/.env.example` - Celery worker with Supabase

2. **Dependencies**:
   - `backend-hormonia/package.json` - `@supabase/supabase-js` dependency
   - `backend-hormonia/package-lock.json` - Supabase packages locked
   - `backend-hormonia/requirements.txt` - `supabase>=2.3.4` Python package

3. **Database/Migration Files**:
   - `backend-hormonia/migrations/supabase_admin_system_complete.sql`
   - `backend-hormonia/alembic/versions/001_initial_migration.py`
   - `backend-hormonia/sql/SCHEMA_MASTER_COMPLETO.sql` - User sync log with Supabase

4. **Documentation**:
   - `backend-hormonia/README.md` - References Supabase
   - `backend-hormonia/DEPLOY.md` - Deployment with Supabase
   - `backend-hormonia/RLS_DEPLOYMENT_COMMANDS.md` - RLS setup commands

5. **Scripts/Tests**:
   - `backend-hormonia/test_idempotent.py` - Supabase client tests
   - `backend-hormonia/scripts/database_analysis.py` - Supabase analysis

#### Frontend Files

1. **Environment Templates**:
   - `frontend-hormonia/.env.example` - Contains Supabase client config (lines 51-58)

---

## Testing Checklist

### Functional Testing

- [ ] **Firebase Authentication Works**
  - [ ] Admin can login with corporate email
  - [ ] Doctor can login with clinic email
  - [ ] Public email (gmail.com) is rejected
  - [ ] User without custom claims is rejected

- [ ] **API Authentication Works**
  - [ ] Frontend can call backend API with Firebase token
  - [ ] Invalid tokens are rejected
  - [ ] Expired tokens are handled properly

- [ ] **WebSocket Authentication Works**
  - [ ] WebSocket connections authenticate with Firebase token
  - [ ] Real-time updates work after authentication

### Security Testing

- [ ] **Public Domain Blocking**
  - [ ] Attempt registration with gmail.com (should fail)
  - [ ] Attempt registration with yahoo.com (should fail)
  - [ ] Verify error message is clear

- [ ] **Custom Claims Validation**
  - [ ] User with valid role can access system
  - [ ] User without custom claims cannot access
  - [ ] Invalid roles are rejected

- [ ] **Audit Logging**
  - [ ] User registration is logged
  - [ ] Failed login attempts are logged
  - [ ] Security events are recorded

### Performance Testing

- [ ] **No Supabase Errors**
  - [ ] Check Railway logs for Supabase-related errors
  - [ ] Verify no timeout errors from removed variables
  - [ ] Confirm clean startup logs

---

## Rollback Plan

If issues occur after cleanup:

### 1. Immediate Rollback (Railway Console)

```bash
# Restore previous deployment
railway deployment rollback --service backend-hormonia
railway deployment rollback --service frontend-hormonia
```

### 2. Re-add Critical Variables (if needed)

```bash
# Only re-add if absolutely necessary for debugging
railway variables set SUPABASE_URL="https://your-project.supabase.co" --service backend-hormonia
```

### 3. Contact Support

- **Railway Support**: https://railway.app/support
- **Firebase Support**: https://firebase.google.com/support

---

## Post-Cleanup Verification

### Backend Logs to Check

```bash
# Check Railway logs for:
✅ "Firebase Admin SDK initialized successfully"
✅ "FIREBASE_BLOCK_PUBLIC_DOMAINS: true"
❌ No "Supabase" errors
❌ No "Missing SUPABASE_URL" warnings
```

### Frontend Console to Check

```bash
# Browser console should show:
✅ Firebase SDK initialized
✅ Authentication state changes work
❌ No Supabase-related errors
❌ No "VITE_SUPABASE_URL undefined" warnings
```

---

## Dependencies to Remove (Future Code Cleanup)

### Backend Dependencies

```bash
# Remove from package.json:
npm uninstall @supabase/supabase-js

# Remove from requirements.txt:
# Delete line: supabase>=2.3.4,<3.0.0
```

**⚠️ Note**: Do NOT remove these now. This requires code changes to remove Supabase imports.

---

## Summary

### Immediate Actions Required

1. **Update Railway backend variables**:
   - Remove 8 Supabase variables
   - Set `FIREBASE_BLOCK_PUBLIC_DOMAINS=true` (**CRITICAL**)
   - Configure Firebase security settings

2. **Update Railway frontend variables**:
   - Remove 4 Supabase variables
   - Verify Firebase client SDK variables

3. **Redeploy and test**:
   - Deploy both services
   - Test authentication flow
   - Verify security enforcement

### Long-Term Actions (Future Sprints)

1. **Code cleanup**:
   - Remove Supabase imports from Python/TypeScript code
   - Update config.py to remove Supabase fields
   - Remove Supabase dependencies from package.json/requirements.txt

2. **Documentation update**:
   - Update README files to remove Supabase references
   - Update deployment guides for Firebase-only
   - Archive old Supabase migration docs

---

## Questions & Support

### Common Questions

**Q: Will removing Supabase variables break the application?**
A: No. The application is already using Firebase for authentication. Supabase variables are unused and safe to remove.

**Q: What happens if I forget to set `FIREBASE_BLOCK_PUBLIC_DOMAINS=true`?**
A: **SECURITY RISK**: Anyone with a gmail.com or public email can create admin accounts. This MUST be set to `true` in production.

**Q: Can I remove Supabase dependencies from package.json now?**
A: Not yet. The code still imports Supabase modules. Dependencies should be removed after code refactoring in a future sprint.

---

## Document Metadata

- **Created**: 2025-10-06
- **Author**: Code Analyzer Agent
- **Version**: 1.0
- **Status**: Ready for Implementation
- **Related**: `FIREBASE_SECURITY_README.md`, `RAILWAY_ENV_VARS_COMPLETE.md`
- **Impact**: Environment configuration cleanup (no code changes)
- **Risk Level**: Low (documentation only)
- **Estimated Time**: 30 minutes (Railway variable updates + redeployment)

---

**Next Steps**: Share this document with the DevOps team for Railway variable cleanup during the next maintenance window.
