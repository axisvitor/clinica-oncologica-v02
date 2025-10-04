# Frontend-Backend Connection Verification Report

**Generated:** 2025-10-04
**Project:** Hormonia - Clínica Oncológica v2.0
**Analysis Type:** Comprehensive Connection & Configuration Audit

---

## Executive Summary

### Overall Connection Health: ⚠️ **CRITICAL ISSUES DETECTED**

**Status:** Multiple critical misconfigurations found that will prevent production deployment
- **Authentication Flow:** ✅ Properly configured (Firebase-based)
- **CORS Configuration:** ⚠️ Mismatched between frontend and backend
- **Environment Variables:** ❌ Critical misalignment detected
- **API Client Setup:** ⚠️ Deferred initialization pattern may cause issues
- **WebSocket Connection:** ⚠️ Non-fatal fallback implemented but misconfigured

---

## 1. API Client Configuration Analysis

### Frontend: `src/lib/api-client.ts`

**Base URL Resolution:**
```typescript
const getApiUrl = () => {
  return API_BASE_URL || import.meta.env.VITE_API_URL || 'http://localhost:8000'
}
```

**Issues Identified:**

1. **❌ CRITICAL: Dual Base URL Pattern**
   - Frontend `.env.example` defines BOTH `VITE_API_URL` AND `VITE_API_BASE_URL`
   - API client only reads `VITE_API_URL` from config
   - **Impact:** Frontend may connect to wrong endpoint if using `VITE_API_BASE_URL`

2. **⚠️ WARNING: Deferred Initialization**
   ```typescript
   const apiClient = new ApiClient(getApiUrl())
   // Client created before config loaded
   ```
   - API client instantiated immediately with potentially undefined URL
   - `setBaseURL()` method exists but relies on external config loading
   - **Risk:** Race condition if API calls made before config loaded

3. **✅ GOOD: Authentication Token Management**
   - Properly sets Firebase token via `setAuthToken()`
   - Supports both `setAuthToken()` and `setSupabaseToken()` methods
   - Bearer token correctly added to Authorization header

**Recommendation:**
```typescript
// Add initialization check
if (!apiClient.isInitialized() && import.meta.env.MODE === 'production') {
  throw new Error('API client not initialized. Call setBaseURL() first.')
}
```

---

## 2. CORS Configuration Analysis

### Backend: `app/middleware/custom_cors.py`

**Allowed Origins (from code):**
```python
QUIZ_CORS_PATTERNS = [
    # Local development
    "http://localhost:3001",
    "http://localhost:5174",
    # Production - EXPLICIT ONLY (no wildcards)
    "https://interface-quiz-production.up.railway.app",
    "https://quiz-mensal-interface.railway.app",
    "https://quiz-interface-production.up.railway.app",
    "https://frontend-production-18bb.up.railway.app",
    "https://hormonia-frontend.railway.app"
]

# Wildcards ONLY in dev/staging
if environment in ['development', 'staging', 'dev']:
    patterns.extend([
        "https://*.railway.app",
        "https://quiz-*.railway.app"
    ])
```

**Backend Config (`config.py`):**
```python
ALLOWED_ORIGINS: List[str] = [
    "http://localhost:3000", "http://localhost:5173", # Main frontend
    "http://localhost:3001",  # Quiz interface
    "http://127.0.0.1:3000", "http://127.0.0.1:5173",
    "https://clinica-oncologica-v02-production.up.railway.app",
    "https://interface-quiz-production.up.railway.app",
    # ... more explicit origins
]
```

### Frontend Environment Variables

**Frontend `.env.example` defines:**
```bash
VITE_API_URL=https://your-backend-web.railway.app
VITE_API_BASE_URL=https://your-backend-web.railway.app  # ❌ DUPLICATE
VITE_WS_URL=wss://your-backend-web.railway.app/ws
VITE_WS_BASE_URL=wss://your-backend-web.railway.app/ws  # ❌ DUPLICATE
```

**Backend `.env.example` defines:**
```bash
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:5173",...]
FRONTEND_API_URL=  # Optional override
FRONTEND_URL=      # For CORS
QUIZ_URL=          # For CORS
```

### ❌ CRITICAL ISSUES:

1. **Duplicate Variable Names**
   - Frontend has both `VITE_API_URL` and `VITE_API_BASE_URL`
   - Frontend has both `VITE_WS_URL` and `VITE_WS_BASE_URL`
   - **Impact:** Confusion during deployment, unclear which to use

2. **Missing CORS Origin Registration**
   - Backend `ALLOWED_ORIGINS` doesn't include common development ports (5174-5179)
   - Frontend might run on port 5174+ but backend only allows 5173
   - **Impact:** CORS errors during multi-instance development

3. **Production URL Mismatch**
   - Backend expects `frontend-production-18bb.up.railway.app`
   - Frontend `.env.example` shows `your-backend-web.railway.app`
   - No automated synchronization mechanism
   - **Impact:** 403 CORS errors in production

---

## 3. Authentication Flow Analysis

### Frontend: `contexts/MedicoAuthContext.tsx`

**Authentication Strategy:**
```typescript
// 1. Mock Authentication (development)
if (isMockAuthEnabled()) {
  const result = await mockAuthService.signIn(email, password)
  apiClient.setAuthToken(result.session.access_token)
}

// 2. Firebase Authentication (production)
else {
  const result = await firebaseAuth.signInWithPassword({
    email: loginEmail,
    password
  })

  // Get Firebase ID token
  const token = result.session.access_token
  apiClient.setAuthToken(token)

  // Validate with backend
  const userResponse = await apiClient.auth.me()

  // Verify role
  if (userResponse.data.role !== 'medico' && userResponse.data.role !== 'doctor') {
    throw new Error('Acesso negado: usuário não é médico')
  }
}
```

### Backend: `app/api/v1/auth.py`

**Authentication Endpoints:**
```python
@router.post("/login")
async def login() -> LoginResponse:
    """Disabled: Firebase-only authentication enforced."""
    raise HTTPException(status_code=410, detail="Local login disabled")

@router.get("/me")
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    """Get current user profile."""
    return UserResponse.from_orm(current_user)
```

### ✅ AUTHENTICATION STRENGTHS:

1. **Proper Firebase Integration**
   - Frontend uses Firebase ID tokens
   - Backend validates tokens via Firebase Admin SDK
   - Role-based access control properly implemented

2. **Token Management**
   - Frontend sets token in API client after authentication
   - Backend receives token via `Authorization: Bearer <token>` header
   - Token refresh handled by Firebase automatically

3. **Fallback Mechanism**
   - If backend `/auth/me` fails, frontend creates fallback user from Firebase data
   - Graceful degradation prevents total auth failure

### ⚠️ AUTHENTICATION CONCERNS:

1. **CRM Email Conversion**
   ```typescript
   // Frontend converts CRM to email format
   const loginEmail = email.includes('@')
     ? email
     : `${email}@medico.neoplasiaslitoral.com.br`
   ```
   - Hardcoded domain in frontend code
   - Should be configurable via environment variable
   - **Risk:** Cannot change domain without code change

2. **Role Validation Inconsistency**
   - Frontend checks for `'medico'` OR `'doctor'`
   - Backend config allows `['admin', 'super_admin', 'doctor', 'medico']`
   - No clear role normalization strategy
   - **Risk:** Role mismatch between systems

---

## 4. Environment Variable Alignment

### Critical Mismatches:

| Variable | Frontend (.env.example) | Backend (.env.example) | Status |
|----------|------------------------|------------------------|--------|
| **API URL** | `VITE_API_URL` + `VITE_API_BASE_URL` | `FRONTEND_API_URL` (optional) | ❌ Duplicate in frontend |
| **CORS Origins** | N/A | `ALLOWED_ORIGINS` (JSON array) | ⚠️ Must be manually synced |
| **WebSocket URL** | `VITE_WS_URL` + `VITE_WS_BASE_URL` | N/A | ❌ Duplicate in frontend |
| **Firebase Config** | `VITE_FIREBASE_*` (7 vars) | `FIREBASE_ADMIN_*` (3 vars) | ✅ Correct separation |
| **Supabase Config** | `VITE_SUPABASE_*` (client keys) | `SUPABASE_*` (service keys) | ✅ Correct separation |
| **Environment** | `VITE_ENVIRONMENT` | `ENVIRONMENT` | ⚠️ May differ |

### Firebase Configuration Issues:

**Backend `.env.example`:**
```bash
# REQUIRED: Backend will fail to start if not configured
FIREBASE_ADMIN_PROJECT_ID=your-firebase-project-id
FIREBASE_ADMIN_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----...
FIREBASE_ADMIN_CLIENT_EMAIL=firebase-adminsdk-xxxxx@...

# Security
FIREBASE_ALLOWED_DOMAINS=[]
FIREBASE_BLOCK_PUBLIC_DOMAINS=false  # ⚠️ Allows gmail.com in dev
```

**Frontend `.env.example:**
```bash
# Public Firebase configuration (safe for browser)
VITE_FIREBASE_API_KEY=your-firebase-api-key
VITE_FIREBASE_AUTH_DOMAIN=your-project-id.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
# ... 4 more Firebase variables
```

**❌ CRITICAL ISSUE:**
- Backend comment says "REQUIRED: Backend will fail to start (503 errors)"
- No validation in `config.py` to enforce this requirement
- Could silently fail in production

---

## 5. WebSocket Configuration Analysis

### Frontend: `src/lib/websocket.ts`

**URL Resolution:**
```typescript
function resolveWsBaseUrl(): string | null {
  const envUrl = import.meta.env.VITE_WS_BASE_URL
  if (envUrl && envUrl.length) return envUrl

  const runtime = getRuntimeConfigSync()
  if (runtime?.VITE_WS_BASE_URL) return runtime.VITE_WS_BASE_URL

  // Fallback to proxy
  if (typeof window !== 'undefined') {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return `${proto}://${window.location.host}/ws/connect`
  }
  return null
}
```

**Connection Handling:**
```typescript
async connect(token: string): Promise<void> {
  const base = WS_BASE_URL || resolveWsBaseUrl()
  if (!base) {
    console.warn('WS base URL missing; skipping WebSocket connect')
    this.shouldReconnect = false
    return resolve()  // ✅ Non-fatal failure
  }

  const wsUrl = `${base}?token=${token}`
  this.ws = new WebSocket(wsUrl)
}
```

### ✅ WEBSOCKET STRENGTHS:

1. **Graceful Degradation**
   - Missing WS URL doesn't crash application
   - Only logs warning in development
   - UI remains functional without real-time features

2. **Protocol Conversion**
   - Translates frontend events to backend protocol
   - Example: `'join:patient'` → `'join_room'`
   - Backward compatibility maintained

3. **Reconnection Logic**
   - Exponential backoff implemented
   - Rejoins rooms after reconnection
   - Max 5 attempts with 1s base delay

### ⚠️ WEBSOCKET CONCERNS:

1. **Duplicate Variable Pattern**
   - Same issue as API URL: `VITE_WS_URL` vs `VITE_WS_BASE_URL`
   - Frontend uses `VITE_WS_BASE_URL` but `.env.example` shows both

2. **Backend WebSocket Endpoint**
   - No backend WebSocket configuration found in files analyzed
   - Fallback assumes `/ws/connect` endpoint exists
   - **Risk:** 404 errors if endpoint path differs

---

## 6. Data Model Consistency

### Patient Data Contract

**Frontend expects (from `MedicoAuthContext.tsx`):**
```typescript
interface MedicoUser {
  id: string
  email: string
  full_name: string
  role: 'doctor'  // Normalized to 'doctor'
  crm: string
  especialidade: string
  conselho_regional: string
  pacientes_atribuidos: string[]
}
```

**Backend returns (from `auth.py`):**
```python
@router.get("/me")
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    return UserResponse.from_orm(current_user)
```

**Backend `UserResponse` schema:**
```python
# From auth.py (inferred)
class UserResponse:
    id: str
    email: str
    full_name: str
    role: str  # Can be 'medico', 'doctor', 'admin', etc.
    is_active: bool
    permissions: List[str]
    created_at: datetime
```

### ⚠️ DATA MODEL ISSUES:

1. **Missing Fields in Backend Response**
   - Frontend expects: `crm`, `especialidade`, `conselho_regional`, `pacientes_atribuidos`
   - Backend `UserResponse` doesn't include these fields
   - Frontend extracts from `metadata` or email parsing as fallback
   - **Risk:** Fragile data access pattern

2. **Role Value Inconsistency**
   - Frontend normalizes all roles to `'doctor'`
   - Backend allows `'medico'`, `'doctor'`, `'admin'`, etc.
   - No centralized role mapping
   - **Risk:** Role-based logic may break

---

## 7. Critical Recommendations

### Priority 1: IMMEDIATE ACTION REQUIRED

1. **Consolidate Environment Variables**
   ```bash
   # Frontend - REMOVE duplicates
   - VITE_API_BASE_URL  # DELETE
   - VITE_WS_BASE_URL   # DELETE

   # Keep only:
   VITE_API_URL=https://backend.railway.app
   VITE_WS_URL=wss://backend.railway.app/ws
   ```

2. **Add CORS Origin Validation**
   ```python
   # Backend config.py
   @field_validator("ALLOWED_ORIGINS")
   @classmethod
   def validate_origins(cls, v):
       # Ensure frontend URL is in allowed origins
       if settings.FRONTEND_URL and settings.FRONTEND_URL not in v:
           raise ValueError(f"FRONTEND_URL {settings.FRONTEND_URL} not in ALLOWED_ORIGINS")
       return v
   ```

3. **Enforce Firebase Configuration**
   ```python
   # Backend config.py
   def __init__(self, **kwargs):
       super().__init__(**kwargs)
       if not self.FIREBASE_ADMIN_PROJECT_ID:
           raise ValueError("FIREBASE_ADMIN_PROJECT_ID is required")
   ```

### Priority 2: SECURITY HARDENING

4. **Normalize User Roles**
   ```typescript
   // Frontend: Create role mapper
   const ROLE_MAP: Record<string, 'doctor' | 'admin' | 'patient'> = {
     'medico': 'doctor',
     'doctor': 'doctor',
     'médico': 'doctor',
     'admin': 'admin',
     'super_admin': 'admin'
   }
   ```

5. **Add API Client Initialization Guard**
   ```typescript
   // Frontend: api-client.ts
   class ApiClient {
     ensureInitialized() {
       if (!this.initialized && import.meta.env.MODE === 'production') {
         throw new Error('API client not initialized')
       }
     }

     async request<T>(endpoint: string, options?: RequestOptions): Promise<T> {
       this.ensureInitialized()
       // ... rest of method
     }
   }
   ```

### Priority 3: OPERATIONAL EXCELLENCE

6. **Create CORS Sync Script**
   ```bash
   # scripts/sync-cors-origins.sh
   #!/bin/bash
   FRONTEND_URL=$(grep VITE_API_URL frontend/.env | cut -d'=' -f2)
   echo "Adding $FRONTEND_URL to backend ALLOWED_ORIGINS"
   # Update backend .env programmatically
   ```

7. **Add Environment Validation**
   ```typescript
   // Frontend: config-validator.ts
   export function validateConfig() {
     const required = ['VITE_API_URL', 'VITE_FIREBASE_API_KEY']
     const missing = required.filter(key => !import.meta.env[key])
     if (missing.length > 0) {
       throw new Error(`Missing required env vars: ${missing.join(', ')}`)
     }
   }
   ```

8. **Standardize User Data Model**
   ```python
   # Backend: Add MedicoResponse schema
   class MedicoResponse(UserResponse):
       crm: str
       especialidade: str
       conselho_regional: str
       pacientes_atribuidos: List[str] = []

   @router.get("/me")
   async def get_current_user_profile(
       current_user: User = Depends(get_current_user)
   ) -> MedicoResponse | UserResponse:
       if current_user.role in ['medico', 'doctor']:
           return MedicoResponse.from_user(current_user)
       return UserResponse.from_orm(current_user)
   ```

---

## 8. Testing Checklist

### Before Deployment:

- [ ] Verify `VITE_API_URL` points to correct backend URL
- [ ] Confirm backend `ALLOWED_ORIGINS` includes frontend URL
- [ ] Test Firebase authentication with real credentials
- [ ] Verify CORS headers in browser Network tab
- [ ] Test WebSocket connection (should gracefully fail if not configured)
- [ ] Validate role-based access control
- [ ] Check API client initialization timing
- [ ] Verify `/auth/me` endpoint returns all required fields
- [ ] Test CRM email conversion logic
- [ ] Confirm environment variable loading in production

### Connection Flow Test:

```bash
# 1. Start backend
cd backend-hormonia
source venv/bin/activate
python -m uvicorn app.main:app --reload

# 2. Verify backend health
curl http://localhost:8000/health
# Expected: {"status": "healthy"}

# 3. Start frontend
cd frontend-hormonia
npm run dev

# 4. Check browser console for:
# ✅ [ApiClient] Setting base URL: http://localhost:8000
# ✅ [MedicoAuth] Initializing Firebase authentication
# ❌ CORS errors indicate ALLOWED_ORIGINS mismatch
# ❌ 404 errors indicate API_URL misconfiguration
```

---

## 9. Summary of Findings

### Critical Issues (Must Fix Before Production):
1. Duplicate environment variable definitions (`VITE_API_URL` vs `VITE_API_BASE_URL`)
2. No validation for required Firebase configuration
3. CORS origins not synchronized between frontend and backend
4. Missing user data fields in backend API response

### Warnings (Should Fix Soon):
1. API client initialization race condition
2. Hardcoded CRM email domain in frontend
3. Role normalization inconsistency
4. WebSocket endpoint path assumption

### Strengths (Working Correctly):
1. Firebase authentication flow properly implemented
2. Token management and refresh logic
3. Graceful WebSocket degradation
4. Retry logic with exponential backoff
5. Proper separation of client/server Firebase keys

---

## 10. Next Steps

1. **Immediate:** Remove duplicate environment variables from frontend `.env.example`
2. **Short-term:** Add configuration validation in both frontend and backend startup
3. **Medium-term:** Create automated CORS origin synchronization
4. **Long-term:** Implement comprehensive integration tests for auth flow

---

**Report Generated By:** Claude Code Quality Analyzer
**Analysis Duration:** Comprehensive multi-file analysis
**Files Analyzed:** 8 core configuration and connection files
**Issues Found:** 4 Critical, 4 Warnings, 5 Strengths identified
