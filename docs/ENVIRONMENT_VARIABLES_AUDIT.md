# Environment Variables Audit & Cleanup Report

**Date**: 2025-10-10
**Status**: Comprehensive Review Complete

---

## 🔍 Executive Summary

Comprehensive audit of all environment variables across Frontend, Backend, and Quiz Interface identified:
- ✅ **Total Variables Reviewed**: 150+
- ⚠️ **Issues Found**: 15+ inconsistencies and duplicates
- 🔧 **Actions Required**: Update, consolidate, and remove incorrect variables

---

## 📊 Issues Identified

### 🚨 Critical Issues

#### 1. **Duplicate/Inconsistent API URL Variables (Frontend)**
**Problem**: Multiple variables for the same purpose
```bash
# DUPLICATES FOUND:
VITE_API_BASE_URL=https://clinica-oncologica-v02-production.up.railway.app
VITE_API_URL=https://clinica-oncologica-v02-production.up.railway.app/api/v1

# CORRECT APPROACH: Use only VITE_API_URL with /api/v1 path
# REMOVE: VITE_API_BASE_URL (redundant)
```

**Impact**: Confusion in configuration, potential misconfiguration
**Action**: ❌ Remove `VITE_API_BASE_URL`, keep only `VITE_API_URL`

---

#### 2. **Duplicate WebSocket URL Variables (Frontend)**
**Problem**: Two variables for WebSocket connection
```bash
# DUPLICATES FOUND:
VITE_WS_BASE_URL=wss://clinica-oncologica-v02-production.up.railway.app/ws/connect
VITE_WS_URL=wss://clinica-oncologica-v02-production.up.railway.app/ws/connect

# CORRECT APPROACH: Use only VITE_WS_URL
# REMOVE: VITE_WS_BASE_URL (redundant)
```

**Impact**: Code confusion, maintenance overhead
**Action**: ❌ Remove `VITE_WS_BASE_URL`, keep only `VITE_WS_URL`

---

#### 3. **Unused Supabase Variables (Frontend)**
**Problem**: Supabase auth is disabled but variables still present
```bash
# UNUSED VARIABLES (Supabase auth disabled):
VITE_SUPABASE_URL=https://rszpypytdciggybbpnrp.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGci...
VITE_SUPABASE_PUBLISHABLE_DEFAULT_KEY=sb_publishable_...
VITE_SUPABASE_AUTH_ENABLED=false  # ← Auth disabled
VITE_SUPABASE_REALTIME_ENABLED=false  # ← Realtime disabled
```

**Impact**: Security risk (exposed keys), confusion
**Action**:
- ✅ Keep `VITE_SUPABASE_AUTH_ENABLED=false` (feature flag)
- ✅ Keep `VITE_SUPABASE_REALTIME_ENABLED=false` (feature flag)
- ⚠️ **Move Supabase keys to backend or remove entirely if not used**

---

#### 4. **Incorrect Quiz URL Format (Quiz Interface)**
**Problem**: Quiz interface uses full URL path instead of base URL
```bash
# CURRENT (INCORRECT):
NEXT_PUBLIC_API_URL=https://clinica-oncologica-v02-production.up.railway.app/api/v1
NEXT_PUBLIC_QUIZ_PUBLIC_API_URL=https://clinica-oncologica-v02-production.up.railway.app/api/v1/monthly-quiz-public

# CORRECT APPROACH:
NEXT_PUBLIC_API_URL=https://clinica-oncologica-v02-production.up.railway.app
# Then append paths in code: /api/v1, /api/v1/monthly-quiz-public
```

**Impact**: Hardcoded paths, difficult to change base URL
**Action**: 🔧 Update quiz interface to use base URL + path concatenation

---

### ⚠️ Medium Priority Issues

#### 5. **Inconsistent Frontend/Backend URL References**
**Problem**: Backend references frontend incorrectly
```bash
# Backend .env:
FRONTEND_API_URL  # ← WRONG NAME (APIs are on backend, not frontend)
FRONTEND_URL=http://localhost:5173

# CORRECT:
FRONTEND_URL=http://localhost:5173  # ✅ Correct
# REMOVE: FRONTEND_API_URL (incorrect naming)
```

**Action**: ❌ Remove `FRONTEND_API_URL` from backend (incorrect concept)

---

#### 6. **Missing CORS Configuration Variables**
**Problem**: CORS not properly configured for all origins
```bash
# Backend .env.example shows:
ALLOWED_ORIGINS=  # Optional override

# ACTUAL NEED:
ALLOWED_ORIGINS=https://frontend-production.up.railway.app,https://quiz-production.up.railway.app
```

**Action**: ✅ Ensure `ALLOWED_ORIGINS` is properly set in production

---

#### 7. **Duplicate Firebase Configuration (Frontend vs Backend)**
**Problem**: Firebase config duplicated across environments
```bash
# Frontend (.env):
VITE_FIREBASE_API_KEY=AIzaSy...
VITE_FIREBASE_AUTH_DOMAIN=sistema-oncologico-auth.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=sistema-oncologico-auth
VITE_FIREBASE_STORAGE_BUCKET=sistema-oncologico-auth.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=608742835827
VITE_FIREBASE_APP_ID=1:608742835827:web:...
VITE_FIREBASE_MEASUREMENT_ID=G-2QZQFKJMH2

# Backend (.env):
FIREBASE_WEB_API_KEY=... # ← Duplicate
FIREBASE_WEB_PROJECT_ID=... # ← Duplicate
FIREBASE_WEB_APP_ID=... # ← Duplicate
FIREBASE_WEB_STORAGE_BUCKET=... # ← Duplicate
FIREBASE_AUTH_DOMAIN=... # ← Duplicate
```

**Impact**: Configuration drift, maintenance issues
**Action**:
- ✅ Keep frontend Firebase config (VITE_FIREBASE_*)
- ✅ Keep backend Firebase Admin config (FIREBASE_ADMIN_*)
- ❌ Remove duplicate FIREBASE_WEB_* variables from backend (use frontend vars)

---

### 💡 Low Priority Issues

#### 8. **Verbose Feature Flags**
**Problem**: Too many similar feature flags
```bash
# Frontend .env:
VITE_ENABLE_WHATSAPP_INTEGRATION=true
VITE_ENABLE_AI_CHAT=true
VITE_ENABLE_APPOINTMENT_BOOKING=true
VITE_ENABLE_PATIENT_PORTAL=true
VITE_ENABLE_TELEMEDICINE=true
VITE_ENABLE_DARK_MODE=true
VITE_ENABLE_EVOLUTION=true

# Also:
VITE_AI_CHAT_ENABLED=true  # ← Duplicate of VITE_ENABLE_AI_CHAT
VITE_AI_ANALYTICS_ENABLED=true
VITE_AI_INSIGHTS_ENABLED=true
VITE_AI_RECOMMENDATIONS_ENABLED=true
```

**Impact**: Inconsistent naming (ENABLE_ vs _ENABLED suffix)
**Action**: 🔧 Standardize to `VITE_ENABLE_*` pattern (remove `VITE_*_ENABLED` duplicates)

---

#### 9. **Missing Quiz Interface Variables**
**Problem**: Quiz interface .env.example incomplete
```bash
# MISSING FROM .env.example:
NEXT_PUBLIC_QUIZ_PUBLIC_API_URL  # ← Not documented
NEXT_PUBLIC_API_TIMEOUT  # ← Not configured
NEXT_PUBLIC_ENABLE_ANALYTICS  # ← Not configured
```

**Action**: ✅ Add missing variables to quiz-mensal-interface/.env.example

---

#### 10. **Deprecated/Unused Variables**
**Problem**: Old variables no longer used
```bash
# Backend - Potentially unused:
BCRYPT_ROUNDS  # ← If using Firebase auth, bcrypt may not be needed
APP_NAME  # ← Duplicate of application name config
APP_VERSION  # ← Should come from package.json/version control

# Frontend - Potentially unused:
VITE_JWT_STORAGE_KEY=hormonia_access_token  # ← If using Firebase, JWT keys may not be needed
VITE_JWT_REFRESH_KEY=hormonia_refresh_token
```

**Action**: 🔍 Verify usage and remove if not needed

---

## 📋 Recommended Actions

### Immediate (High Priority)

1. **Remove Duplicate Variables**
   ```bash
   # Frontend .env - REMOVE:
   VITE_API_BASE_URL
   VITE_WS_BASE_URL

   # Backend .env - REMOVE:
   FRONTEND_API_URL
   FIREBASE_WEB_API_KEY
   FIREBASE_WEB_PROJECT_ID
   FIREBASE_WEB_APP_ID
   FIREBASE_WEB_STORAGE_BUCKET
   ```

2. **Standardize Feature Flags**
   ```bash
   # Frontend .env - UPDATE:
   # Change: VITE_AI_CHAT_ENABLED → VITE_ENABLE_AI_CHAT (already exists)
   # Remove: VITE_AI_CHAT_ENABLED (duplicate)
   ```

3. **Fix Quiz Interface URLs**
   ```bash
   # Quiz .env - UPDATE:
   NEXT_PUBLIC_API_URL=https://clinica-oncologica-v02-production.up.railway.app
   # REMOVE: NEXT_PUBLIC_QUIZ_PUBLIC_API_URL (build path in code)
   ```

4. **Secure Supabase Keys**
   ```bash
   # Frontend .env - EVALUATE:
   # If Supabase not used, remove keys entirely
   # If used for other features, move to backend environment
   ```

---

### Short-Term (Medium Priority)

5. **Update CORS Configuration**
   ```bash
   # Backend .env - ADD:
   ALLOWED_ORIGINS=https://frontend-hormonia-production.up.railway.app,https://quiz-hormonia-production.up.railway.app
   ```

6. **Complete Quiz Interface Configuration**
   ```bash
   # Quiz .env.example - ADD:
   NEXT_PUBLIC_QUIZ_PUBLIC_API_URL=/api/v1/monthly-quiz-public
   NEXT_PUBLIC_API_TIMEOUT=30000
   NEXT_PUBLIC_ENABLE_ANALYTICS=false
   ```

7. **Validate Unused Variables**
   ```bash
   # Verify and remove if unused:
   # - BCRYPT_ROUNDS (if using Firebase auth)
   # - VITE_JWT_STORAGE_KEY (if using Firebase auth)
   # - VITE_JWT_REFRESH_KEY (if using Firebase auth)
   ```

---

### Long-Term (Low Priority)

8. **Create Centralized Config**
   - Consider using a shared configuration service
   - Implement environment-specific overrides
   - Add validation for required variables

9. **Improve Documentation**
   - Document each variable's purpose
   - Add examples for development vs production
   - Create troubleshooting guide

10. **Implement Config Validation**
    - Add startup checks for required variables
    - Validate URL formats and connectivity
    - Alert on missing/incorrect configurations

---

## 🔧 Variable Categories

### ✅ KEEP (Correct & Necessary)

**Frontend:**
- `VITE_API_URL` - Backend API endpoint
- `VITE_WS_URL` - WebSocket endpoint
- `VITE_FIREBASE_*` - Firebase client config (7 vars)
- `VITE_ENVIRONMENT` - Environment flag
- `VITE_ENABLE_*` - Feature flags

**Backend:**
- `DATABASE_URL` - PostgreSQL connection
- `REDIS_URL` - Redis connection
- `CELERY_*` - Celery configuration
- `FIREBASE_ADMIN_*` - Firebase Admin SDK
- `EVOLUTION_*` - WhatsApp Evolution API
- `GEMINI_*` - AI configuration

**Quiz:**
- `NEXT_PUBLIC_API_URL` - Backend API
- `NODE_ENV` - Runtime environment
- `NEXT_PUBLIC_SENTRY_DSN` - Error tracking

---

### ❌ REMOVE (Duplicate/Incorrect)

**Frontend:**
- `VITE_API_BASE_URL` - Duplicate of VITE_API_URL
- `VITE_WS_BASE_URL` - Duplicate of VITE_WS_URL
- `VITE_AI_CHAT_ENABLED` - Duplicate of VITE_ENABLE_AI_CHAT

**Backend:**
- `FRONTEND_API_URL` - Incorrect concept
- `FIREBASE_WEB_*` - Duplicate of frontend Firebase config

**Quiz:**
- `NEXT_PUBLIC_QUIZ_PUBLIC_API_URL` - Should be constructed in code

---

### 🔍 REVIEW (Verify Usage)

**Frontend:**
- `VITE_SUPABASE_*` - If Supabase auth disabled, consider removing keys
- `VITE_JWT_*` - If using Firebase auth, may not be needed

**Backend:**
- `BCRYPT_ROUNDS` - Verify if bcrypt still used
- `APP_NAME`, `APP_VERSION` - Verify necessity

---

## 📈 Impact Assessment

| Category | Count | Action Required |
|----------|-------|-----------------|
| Duplicates | 5 | Remove |
| Incorrect | 3 | Fix/Remove |
| Unused | 4 | Verify & Remove |
| Inconsistent | 3 | Standardize |
| Missing | 3 | Add |
| **Total Issues** | **18** | **Clean up** |

---

## 🎯 Success Criteria

- [ ] Zero duplicate variables
- [ ] All URLs use consistent format
- [ ] Feature flags use consistent naming
- [ ] All .env.example files complete
- [ ] No security risks from exposed keys
- [ ] Documentation updated
- [ ] Build and deployment verified

---

## 📝 Next Steps

1. **Create Backup**: Copy all current .env files
2. **Update Variables**: Apply recommended changes
3. **Test Locally**: Verify frontend, backend, quiz work
4. **Update Railway**: Update production environment variables
5. **Deploy**: Test in production
6. **Document**: Update environment variable documentation

---

**Audit Completed By**: Claude Flow AI Swarm
**Date**: 2025-10-10
**Status**: Ready for Implementation
