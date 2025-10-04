# Frontend API Client Analysis - Hive Mind Report

**Agent**: Frontend Developer
**Date**: 2025-10-04
**Mission**: Analyze frontend API client, WebSocket, and configuration

---

## 1. API CLIENT CONFIGURATION

### Primary API Client: `api-client.ts`

**Base URL Resolution** (Lines 46-48):
```typescript
const getApiUrl = () => {
  return API_BASE_URL || import.meta.env.VITE_API_URL || 'http://localhost:8000'
}
```

**Initialization**:
- Default: Uses fallback URL immediately
- Can be set dynamically via `apiClient.setBaseURL(url)`
- Has deferred initialization flag (line 76: `initialized: boolean = false`)

**Authentication**:
- Token stored in `authToken` property (line 75)
- Methods:
  - `setAuthToken(token)` - Manual token set
  - `setSupabaseToken(session)` - Extract from Supabase session
- Header injection (lines 170-172):
  ```typescript
  if (this.authToken) {
    headers['Authorization'] = `Bearer ${this.authToken}`
  }
  ```

**Request Timeout**: 30 seconds (line 176)

**Error Handling**:
- Network errors → Status 0
- Timeout errors → Status 408
- Generic errors → Status 500
- Custom `ApiError` class with status, data, message

---

## 2. CONFIGURATION SYSTEM

### Runtime Configuration (`runtime-config.ts`)

**Configuration Loading Priority**:
1. `/api/config` endpoint (5 second timeout)
2. `window.__ENV_CONFIG__` (server-injected)
3. `window.__RUNTIME_CONFIG__`
4. `import.meta.env` (Vite build-time vars)
5. Production fallback config

**Critical Finding**:
- Frontend attempts to fetch `/api/config` from backend (lines 203-227)
- This is served locally in dev mode to prevent 499 errors
- Backend should respond with runtime environment variables

### Environment Variables (`.env`):

**API Configuration**:
```bash
VITE_API_URL=https://clinica-oncologica-v02-production.up.railway.app
VITE_API_BASE_URL=https://clinica-oncologica-v02-production.up.railway.app
VITE_API_BASE_PATH=/api/v1
VITE_API_TIMEOUT=30000
```

**WebSocket Configuration**:
```bash
VITE_WS_URL=wss://clinica-oncologica-v02-production.up.railway.app/ws/connect
VITE_WS_BASE_URL=wss://clinica-oncologica-v02-production.up.railway.app/ws/connect
```

**Authentication**:
```bash
VITE_SESSION_TIMEOUT=3600000
VITE_TOKEN_REFRESH_THRESHOLD=300000
VITE_JWT_STORAGE_KEY=hormonia_access_token
VITE_JWT_REFRESH_KEY=hormonia_refresh_token
```

**Firebase Auth** (PUBLIC keys):
```bash
VITE_FIREBASE_API_KEY=AIzaSyDbZHMNV2eZQty03TgA4yNo_3L6UDSpHdI
VITE_FIREBASE_AUTH_DOMAIN=sistema-oncologico-auth.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=sistema-oncologico-auth
```

**Supabase** (PUBLIC keys):
```bash
VITE_SUPABASE_URL=https://rszpypytdciggybbpnrp.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## 3. WEBSOCKET CLIENT (`websocket.ts`)

### Connection Strategy:

**URL Resolution** (lines 4-17):
```typescript
function resolveWsBaseUrl(): string | null {
  const envUrl = import.meta.env.VITE_WS_BASE_URL
  if (envUrl && envUrl.length) return envUrl

  const runtime = getRuntimeConfigSync()
  if (runtime?.VITE_WS_BASE_URL) return runtime.VITE_WS_BASE_URL

  // Fallback to current host proxy
  if (typeof window !== 'undefined') {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return `${proto}://${window.location.host}/ws/connect`
  }
  return null
}
```

**Connection URL** (line 93):
```typescript
const wsUrl = `${base}?token=${token}`
```

**Reconnection**:
- Max attempts: 5 (configurable)
- Delay: Exponential backoff (1000ms * 2^attempt)
- Auto-reconnect on disconnect (unless manual)

**Protocol Mapping**:
Frontend event → Backend type:
- `join:patient` → `join_room`
- `leave:patient` → `leave_room`
- `subscribe:quiz` → `subscribe`
- `subscribe:flow` → `subscribe`
- `ping` → `ping`
- `pong` → `pong`

**Backend to Frontend Event Conversion** (lines 217-243):
- `patient_updated` → `patient:updated`
- `flow_state_changed` → `flow:state_changed`
- `quiz_started` → `quiz:started`
- `new_message` → `message:new`

### Room Management:

**Patient Room**:
```typescript
joinPatientRoom(patientId: string) {
  this.send('join:patient', { patient_id: patientId })
}
```

**Quiz Events**:
```typescript
subscribeToQuizEvents(sessionId: string) {
  this.send('subscribe:quiz', {
    channel: `quiz:${sessionId}`,
    session_id: sessionId
  })
}
```

---

## 4. AUTHENTICATION FLOW (`AuthContext.tsx`)

### Firebase Authentication:

**Login Process**:
1. Call `firebaseAuth.signInWithPassword({ email, password })`
2. Get Firebase user and token
3. Call backend `/api/v1/auth/me` with token
4. Set user state and session
5. Connect WebSocket with token

**Token Refresh**:
- Firebase auto-refreshes tokens
- `onIdTokenChanged` listener updates WebSocket and API client
- Lines 150-166

**WebSocket Integration**:
- Connect on login (line 215)
- Disconnect on logout (line 243)
- Update token on refresh (line 157)

### Backend `/api/v1/auth/me` Call:

From `api-client.ts` lines 275-297:
```typescript
me: async () => {
  const user = await this.request<{
    id: string;
    email: string;
    full_name: string;
    role: string;
    is_active: boolean;
  }>('/api/v1/auth/me');

  return {
    data: {
      id: user['id'],
      email: user['email'],
      full_name: user['full_name'],
      role: user['role'],
      is_active: user.is_active,
      permissions: [],
      created_at: new Date().toISOString()
    }
  };
}
```

---

## 5. ALL API ENDPOINTS CALLED

### Authentication (`/api/v1/auth/*`):
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `GET /api/v1/auth/notifications`

### Patients (`/api/v1/patients/*`):
- `GET /api/v1/patients` (list with pagination)
- `GET /api/v1/patients/{id}`
- `POST /api/v1/patients`
- `PUT /api/v1/patients/{id}`
- `DELETE /api/v1/patients/{id}`
- `GET /api/v1/patients/{id}/timeline`
- `POST /api/v1/patients/{id}/activate`
- `POST /api/v1/patients/{id}/deactivate`

### Messages (`/api/v1/messages/*`):
- `GET /api/v1/messages`
- `POST /api/v1/messages/send`
- `POST /api/v1/messages/{id}/retry`

### Flows (`/api/v1/flows/*`):
- `GET /api/v1/flows`
- `POST /api/v1/flows/start`
- `GET /api/v1/flows/{patientId}/state`
- `POST /api/v1/flows/{patientId}/advance`
- `POST /api/v1/flows/{patientId}/pause`
- `POST /api/v1/flows/{patientId}/resume`
- `POST /api/v1/flows/{patientId}/response`
- `GET /api/v1/flows/templates`
- `POST /api/v1/flows/templates`
- `PUT /api/v1/flows/templates/{id}`
- `DELETE /api/v1/flows/templates/{id}`
- `GET /api/v1/flows/analytics/flow-performance`

### Analytics (`/api/v1/analytics/*`):
- `GET /api/v1/analytics/dashboard`
- `GET /api/v1/analytics/patients`
- `GET /api/v1/analytics/engagement`

### Alerts (`/api/v1/alerts/*`):
- `GET /api/v1/alerts`
- `POST /api/v1/alerts`
- `POST /api/v1/alerts/{id}/acknowledge`
- `POST /api/v1/alerts/{id}/resolve`

### Reports (`/api/v1/reports/*`):
- `GET /api/v1/reports`
- `POST /api/v1/reports/generate`
- `GET /api/v1/reports/{id}`
- `GET /api/v1/reports/{id}/preview`
- `GET /api/v1/reports/{id}/download`

### Quiz (`/api/v1/quiz/*`):
- `GET /api/v1/quiz/templates`
- `POST /api/v1/quiz/sessions`
- `GET /api/v1/quiz/sessions/{id}`
- `POST /api/v1/quiz/sessions/{id}/submit`
- `GET /api/v1/quiz/sessions`
- `POST /api/v1/quiz/templates`
- `PUT /api/v1/quiz/templates/{id}`
- `DELETE /api/v1/quiz/templates/{id}`
- `GET /api/v1/quiz/templates/{id}/analytics`

### Monthly Quiz (`/api/v1/monthly-quiz/*`):
- `POST /api/v1/monthly-quiz/links`
- `POST /api/v1/monthly-quiz/links/bulk`
- `GET /api/v1/monthly-quiz/links/{sessionId}/status`
- `GET /api/v1/monthly-quiz/patients/{patientId}/status`
- `GET /api/v1/monthly-quiz/patients/{patientId}/history`
- `GET /api/v1/monthly-quiz/stats/dashboard`
- `GET /api/v1/monthly-quiz/links/active`
- `POST /api/v1/monthly-quiz/links/{sessionId}/resend`
- `POST /api/v1/monthly-quiz/links/{sessionId}/cancel`

### Admin Users (`/api/v1/admin/users/*`):
- `GET /api/v1/admin/users`
- `GET /api/v1/admin/users/{id}`
- `POST /api/v1/admin/users`
- `PUT /api/v1/admin/users/{id}`
- `DELETE /api/v1/admin/users/{id}`
- `POST /api/v1/admin/users/{id}/activate`
- `POST /api/v1/admin/users/{id}/deactivate`
- `PUT /api/v1/admin/users/{id}/permissions`
- `PUT /api/v1/admin/users/{id}/role`
- `GET /api/v1/admin/users/{id}/activity`
- `POST /api/v1/admin/users/{id}/reset-password`
- `POST /api/v1/admin/users/{id}/unlock`
- `POST /api/v1/admin/users/{id}/2fa/enable`
- `POST /api/v1/admin/users/{id}/2fa/disable`

### AI (`/api/v1/ai/*`):
- `POST /api/v1/ai/chat`
- `POST /api/v1/ai/analyze`
- `POST /api/v1/ai/generate-response`
- `POST /api/v1/ai/sentiment`
- `GET /api/v1/ai/insights/{patientId}`
- `GET /api/v1/ai/recommendations/{patientId}`

---

## 6. CRITICAL ISSUES & FINDINGS

### ⚠️ Issue 1: /api/config Endpoint Required
**File**: `runtime-config.ts` lines 203-227
**Problem**: Frontend expects backend to serve `/api/config` with runtime environment variables
**Impact**: Without this endpoint, frontend falls back to build-time vars (may not work in Railway)
**Solution**: Backend MUST implement `/api/config` endpoint

### ⚠️ Issue 2: Dual Base URL Configuration
**Files**: `.env` lines 12-14
**Problem**: Both `VITE_API_URL` and `VITE_API_BASE_URL` are set to the same value
**Expected**: `VITE_API_BASE_URL` should be base domain, `VITE_API_BASE_PATH` is `/api/v1`
**Current**: Both point to full Railway URL without path
**Impact**: May cause double `/api/v1` in URLs

### ⚠️ Issue 3: WebSocket Auto-Fallback
**File**: `websocket.ts` lines 12-15
**Behavior**: If `VITE_WS_BASE_URL` not set, falls back to current host + `/ws/connect`
**Impact**: May work in dev, but could fail in production if proxy not configured

### ⚠️ Issue 4: Authentication Error Handling
**File**: `api-client.ts` lines 267-272
**Finding**: Local authentication explicitly disabled (410 Gone)
**Expected**: Firebase auth only
**Current**: Throws error if trying to use local auth

### ✅ Positive Finding: Token Refresh
**File**: `AuthContext.tsx` lines 150-166
**Implementation**: Proper Firebase token refresh with WebSocket update
**Quality**: Well-implemented automatic token rotation

### ✅ Positive Finding: Error Handling
**File**: `api-client.ts` lines 174-229
**Features**:
- 30-second timeout with AbortController
- Network error detection
- Timeout error handling
- Portuguese error messages

---

## 7. HTTP INTERCEPTORS

**Request Interceptor** (implicit in `request()` method):
- Adds `Content-Type: application/json` (unless FormData)
- Adds `Authorization: Bearer ${token}` if token present
- Handles query parameters
- 30-second timeout

**Response Interceptor**:
- Content-Type detection (JSON, text, or raw)
- Empty response handling (204, 205, 304)
- Error transformation to `ApiError`

---

## 8. HARDCODED URLs

**None found** ✅ - All URLs use environment variables or dynamic config

---

## 9. AUTHENTICATION TOKEN STORAGE

**Storage**: In-memory only (not localStorage/sessionStorage)
**Managed by**: Firebase Auth SDK + React Context
**Refresh**: Automatic via Firebase `onIdTokenChanged`
**Lifecycle**:
1. Login → Firebase token → Store in context
2. Set in `apiClient.authToken` and WebSocket
3. Auto-refresh by Firebase
4. Update API client + WebSocket on refresh
5. Logout → Clear all tokens

---

## 10. CONFIGURATION MISMATCH ANALYSIS

### Expected Backend URL:
From `.env`: `https://clinica-oncologica-v02-production.up.railway.app`

### Actual API Base:
- No `/api/v1` prefix in `VITE_API_URL` or `VITE_API_BASE_URL`
- Hardcoded in endpoint methods (e.g., `/api/v1/auth/me`)

### WebSocket URL:
`wss://clinica-oncologica-v02-production.up.railway.app/ws/connect`

**Verdict**: URLs appear correctly configured for Railway deployment

---

## 11. RECOMMENDATIONS FOR BACKEND TEAM

1. **CRITICAL**: Implement `/api/config` endpoint returning:
   ```json
   {
     "VITE_API_URL": "https://...",
     "VITE_API_BASE_URL": "https://...",
     "VITE_WS_BASE_URL": "wss://...",
     "VITE_SUPABASE_URL": "...",
     "VITE_SUPABASE_ANON_KEY": "..."
   }
   ```

2. **HIGH**: Verify `/api/v1/auth/me` endpoint:
   - Accepts `Authorization: Bearer ${firebase_token}`
   - Returns user object with `id, email, full_name, role, is_active`

3. **HIGH**: Verify WebSocket endpoint `/ws/connect`:
   - Accepts `?token=${firebase_token}` query parameter
   - Supports bidirectional protocol mapping
   - Emits events in backend format (`type`, `data`)

4. **MEDIUM**: All 60+ API endpoints must:
   - Accept Firebase JWT in `Authorization` header
   - Return responses in expected format
   - Handle pagination with `page`, `size` params

5. **LOW**: Consider implementing request logging to debug 499 errors

---

## 12. FILES ANALYZED

- `frontend-hormonia/src/lib/api-client.ts` (718 lines)
- `frontend-hormonia/src/lib/websocket.ts` (477 lines)
- `frontend-hormonia/src/lib/runtime-config.ts` (387 lines)
- `frontend-hormonia/src/contexts/AuthContext.tsx` (270 lines)
- `frontend-hormonia/src/lib/api-client-wrapper.ts` (491 lines)
- `frontend-hormonia/src/config.ts` (261 lines)
- `frontend-hormonia/.env` (217 lines)

**Total Lines Analyzed**: 2,821 lines

---

## CONCLUSION

Frontend API client is well-architected with:
- ✅ Proper authentication flow (Firebase → Backend → WebSocket)
- ✅ Comprehensive error handling
- ✅ Runtime configuration loading
- ✅ Automatic token refresh
- ✅ WebSocket reconnection logic
- ✅ 60+ API endpoints defined

**Critical Dependency**: Backend MUST serve `/api/config` endpoint for Railway deployment to work correctly.

**Next Step**: Await Backend Developer analysis to compare endpoint implementations.

---

**Generated by**: Frontend Developer Agent
**Coordination**: Hive Mind Review System
**Stored in Memory**: `hive/frontend/api-client` and `hive/frontend/websocket-client`
