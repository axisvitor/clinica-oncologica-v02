# Frontend CORS Pattern Analysis Report

**Date**: 2025-10-05
**Scope**: HTTP client configurations and CORS implications
**Environment**: Development and Production

---

## Executive Summary

This analysis identifies **critical CORS configuration issues** in both frontend applications and provides recommendations for development environment setup. The primary issues stem from inconsistent base URL resolution, missing `credentials` configuration, and Docker-specific CORS triggers.

### Critical Findings

1. ✅ **GOOD**: Neither frontend uses `credentials: 'include'` (correct for Bearer token auth)
2. ⚠️ **WARNING**: Docker Compose uses `http://backend:8000` which causes browser CORS errors
3. ⚠️ **WARNING**: Nginx may add duplicate CORS headers (conflicts with backend)
4. ✅ **GOOD**: Both frontends use proper Bearer token authentication
5. ⚠️ **ISSUE**: Inconsistent URL resolution across environments

---

## Detailed Analysis

### 1. Frontend Hormonia (`api-client.ts`)

#### Base URL Resolution
```typescript
const getApiUrl = () => {
  return API_BASE_URL || import.meta.env['VITE_API_URL'] || 'http://localhost:8000'
}
```

**Analysis**:
- ✅ Fallback chain is logical
- ❌ No runtime URL validation
- ❌ Docker uses `http://backend:8000` (internal network) → browser cannot resolve

#### HTTP Request Configuration
```typescript
const response = await fetch(url, {
  ...fetchOptions,
  headers,
  signal: controller.signal
})
```

**CORS Analysis**:
- ✅ **NO `credentials: 'include'`** - correct for Bearer tokens
- ✅ Uses `Authorization: Bearer ${token}` header
- ✅ Sets `Content-Type: application/json` (simple request for GET/POST without custom headers)
- ⚠️ Authorization header triggers **preflight OPTIONS** requests
- ✅ Timeout handling with AbortController

**Headers Sent**:
```
Content-Type: application/json
Authorization: Bearer <token>  // Triggers CORS preflight
```

#### Issues Identified

**Issue 1: Docker Environment CORS**
```yaml
# docker-compose.yml
environment:
  - VITE_API_URL=http://backend:8000  # ❌ Browser cannot resolve
```

**Problem**:
- `backend:8000` is Docker's internal network hostname
- Browser tries to connect to `http://backend:8000` → DNS resolution fails
- Should use same-origin `/api` or external hostname

**Recommendation**:
```yaml
# Development
- VITE_API_URL=http://localhost:8000

# Or use Nginx proxy
- VITE_API_URL=/api  # Same-origin, no CORS
```

**Issue 2: No Credentials Flag**
```typescript
// ✅ CURRENT (CORRECT for Bearer tokens)
const response = await fetch(url, {
  headers: {
    'Authorization': `Bearer ${token}`
  }
})

// ❌ WRONG (would be for cookie-based auth)
const response = await fetch(url, {
  credentials: 'include',  // Don't use with Bearer tokens
  headers: { 'Authorization': `Bearer ${token}` }
})
```

**Status**: ✅ Correctly implemented

---

### 2. Quiz Interface (`lib/api.ts`)

#### Base URL Resolution
```typescript
function resolveApiBaseUrl(): string {
  // Priority 1: Explicit full API URL
  const explicit = process.env.NEXT_PUBLIC_QUIZ_PUBLIC_API_URL
  if (explicit) return explicit.replace(/\/$/, '')

  // Priority 2: Base URL with auto-constructed path
  const legacy = process.env.NEXT_PUBLIC_API_URL
  if (legacy) {
    let trimmed = legacy.replace(/\/$/, '')
    if (!trimmed.includes('/api/v1')) {
      trimmed = `${trimmed}/api/v1`
    }
    return trimmed.endsWith('/monthly-quiz-public')
      ? trimmed
      : `${trimmed}/monthly-quiz-public`
  }

  // Priority 3: Fallback
  return 'http://localhost:8000/api/v1/monthly-quiz-public'
}
```

**Analysis**:
- ✅ Explicit priority order (NEXT_PUBLIC_QUIZ_PUBLIC_API_URL preferred)
- ✅ Automatic path construction for legacy env vars
- ✅ Debug logging available
- ❌ No validation for production URLs
- ❌ Fallback to localhost may fail in production

#### HTTP Request Configuration
```typescript
const response = await fetchWithTimeout(
  url,
  {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ token }),
  },
  timeout
)
```

**CORS Analysis**:
- ✅ **NO `credentials: 'include'`** - correct
- ✅ Only sets `Content-Type: application/json`
- ✅ No Authorization header (uses token in body for public API)
- ✅ Simple POST requests (no preflight for public endpoints)

**Headers Sent**:
```
Content-Type: application/json
```

**CORS Behavior**:
- Simple request for non-authenticated endpoints
- Browser sends **preflight OPTIONS** only if custom headers added
- Current configuration should NOT trigger preflight

---

### 3. Nginx Configuration Analysis

#### Main Config (`nginx.conf`)

**Upstream Configuration**:
```nginx
upstream backend {
    server ${BACKEND_HOST}:${BACKEND_PORT};
    keepalive 32;
    keepalive_timeout 60s;
}
```

**API Proxy**:
```nginx
location /api/ {
    proxy_pass http://backend;
    proxy_http_version 1.1;

    # Standard proxy headers
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Keepalive to backend
    proxy_set_header Connection "";
}
```

**CORS Analysis**:
- ✅ No `add_header Access-Control-*` directives (good - backend handles CORS)
- ✅ Proxy headers correctly forwarded
- ✅ HTTP/1.1 with keepalive
- ❌ **RISK**: If backend adds CORS headers, Nginx doesn't interfere

**Potential Issue**:
```nginx
# ❌ WRONG (if added)
add_header Access-Control-Allow-Origin "*" always;

# Backend also adds:
Access-Control-Allow-Origin: https://example.com

# Result: Duplicate headers → CORS failure
```

**Current Status**: ✅ No duplicate headers detected

#### Server Config (`nginx.server.conf`)

**Simple Configuration**:
```nginx
server {
    listen $PORT;
    server_name _;
    root /usr/share/nginx/html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

**Analysis**:
- ✅ No CORS headers added
- ✅ SPA routing configured correctly
- ❌ No `/api/` proxy (expects different deployment setup)

---

### 4. Docker Compose Configuration

```yaml
frontend:
  environment:
    - VITE_API_URL=http://backend:8000  # ❌ PROBLEM

backend:
  ports:
    - "8000:8000"
```

**Critical Issue**: Browser CORS Violation

**Problem Flow**:
```
1. Browser loads http://localhost:80 (frontend)
2. Frontend reads VITE_API_URL=http://backend:8000
3. Browser tries to fetch http://backend:8000/api/...
4. ❌ DNS lookup fails: "backend" not resolvable in browser
5. OR if somehow resolves:
   - Origin: http://localhost:80
   - Request: http://backend:8000
   - ❌ CORS error: Different origins
```

**Why This Happens**:
- Docker Compose creates network where `backend` is resolvable **inside containers**
- Browser runs on host machine, **cannot resolve** `backend` hostname
- Even if DNS resolved, `localhost:80` ≠ `backend:8000` → CORS error

**Solutions**:

**Option 1: Same-Origin via Nginx Proxy** (RECOMMENDED for dev)
```yaml
frontend:
  environment:
    - VITE_API_URL=/api  # Same-origin, no CORS
  # Nginx proxies /api/ to backend:8000
```

**Option 2: Host Network for Dev**
```yaml
frontend:
  environment:
    - VITE_API_URL=http://localhost:8000
backend:
  ports:
    - "8000:8000"
  # Backend accessible at localhost:8000
```

**Option 3: External URL for Production**
```yaml
frontend:
  environment:
    - VITE_API_URL=https://api.example.com
  # Production backend with CORS configured
```

---

## CORS Flow Diagrams

### Current Docker Setup (BROKEN)

```
Browser                    Docker Network
  │                             │
  │  GET http://backend:8000    │
  ├────────────────────────────>│
  │                             │
  │  ❌ DNS Error or CORS       │
  │<────────────────────────────┤
  │                             │
```

### Recommended: Same-Origin Proxy

```
Browser                  Nginx (Frontend)          Backend
  │                           │                      │
  │  GET /api/patients        │                      │
  ├──────────────────────────>│                      │
  │                           │  Proxy to backend:8000
  │                           ├─────────────────────>│
  │                           │                      │
  │                           │  200 OK              │
  │                           │<─────────────────────┤
  │  200 OK                   │                      │
  │<──────────────────────────┤                      │
  │  ✅ Same-origin            │                      │
```

### Production: CORS Enabled

```
Browser                       Backend (CORS Headers)
  │                                   │
  │  OPTIONS /api/patients            │
  │  Origin: https://frontend.com     │
  ├──────────────────────────────────>│
  │                                   │
  │  200 OK                           │
  │  Access-Control-Allow-Origin: ... │
  │<──────────────────────────────────┤
  │                                   │
  │  GET /api/patients                │
  │  Authorization: Bearer <token>    │
  ├──────────────────────────────────>│
  │                                   │
  │  200 OK                           │
  │  Access-Control-Allow-Origin: ... │
  │<──────────────────────────────────┤
  │  ✅ CORS passed                    │
```

---

## Recommendations

### 1. Development Environment (Docker Compose)

**Change `docker-compose.yml`**:

```yaml
# OPTION A: Same-origin via Nginx proxy (RECOMMENDED)
frontend:
  environment:
    - VITE_API_URL=/api  # Use Nginx proxy
    - NEXT_PUBLIC_API_URL=/api

# OPTION B: Localhost resolution
frontend:
  environment:
    - VITE_API_URL=http://localhost:8000
    - NEXT_PUBLIC_API_URL=http://localhost:8000
  network_mode: host  # Share host network
```

**Update `frontend-hormonia/nginx.conf`** (if using OPTION A):

Ensure `/api/` proxy is configured:
```nginx
location /api/ {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Don't add CORS headers - let backend handle it
}
```

### 2. Production Environment

**Railway/Cloud Deployment**:

```bash
# Frontend env vars
VITE_API_URL=https://api.yourdomain.com
NEXT_PUBLIC_API_URL=https://api.yourdomain.com

# Backend CORS configuration
ALLOWED_ORIGINS=https://frontend.yourdomain.com,https://www.yourdomain.com
```

**Backend CORS Middleware** (verify exists):
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://frontend.yourdomain.com"],
    allow_credentials=False,  # ❌ Not needed with Bearer tokens
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["Content-Type"],
)
```

### 3. Frontend Code Improvements

**Add URL Validation** (`api-client.ts`):

```typescript
const getApiUrl = () => {
  const url = API_BASE_URL || import.meta.env['VITE_API_URL'] || 'http://localhost:8000'

  // Validate URL format
  try {
    new URL(url)
  } catch (err) {
    console.error('[ApiClient] Invalid API URL:', url)
    throw new Error(`Invalid API URL configuration: ${url}`)
  }

  return url
}
```

**Add Environment Detection** (`api-client.ts`):

```typescript
private buildUrl(endpoint: string, params?: Record<string, string | number | boolean>): string {
  // Detect Docker environment
  if (this.baseURL.includes('backend:') && typeof window !== 'undefined') {
    console.error('[ApiClient] Docker hostname detected in browser - this will fail!')
    console.error('[ApiClient] Use /api prefix or localhost:8000 instead')
  }

  const url = new URL(`${this.baseURL}${endpoint}`)
  // ... rest of implementation
}
```

### 4. Testing CORS Setup

**Test Script** (`docs/test-cors.sh`):

```bash
#!/bin/bash

echo "=== Testing CORS Configuration ==="

# Test 1: Preflight request
echo "\n1. Testing OPTIONS preflight..."
curl -X OPTIONS http://localhost:8000/api/v1/patients \
  -H "Origin: http://localhost:80" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: Authorization" \
  -v

# Test 2: Actual request
echo "\n2. Testing GET with Authorization..."
curl -X GET http://localhost:8000/api/v1/patients \
  -H "Origin: http://localhost:80" \
  -H "Authorization: Bearer test-token" \
  -v

# Test 3: Same-origin proxy
echo "\n3. Testing Nginx proxy..."
curl -X GET http://localhost:80/api/v1/patients \
  -H "Authorization: Bearer test-token" \
  -v

echo "\n=== CORS Test Complete ==="
```

---

## Summary of Issues

| Issue | Severity | File | Fix |
|-------|----------|------|-----|
| Docker uses `backend:8000` hostname | 🔴 Critical | `docker-compose.yml` | Use `/api` or `localhost:8000` |
| No URL validation | 🟡 Medium | `api-client.ts` | Add URL format validation |
| Missing environment detection | 🟡 Medium | `api-client.ts` | Warn if Docker hostname in browser |
| No duplicate CORS header check | 🟢 Low | `nginx.conf` | Already OK, document best practice |
| Quiz API fallback to localhost | 🟡 Medium | `quiz-mensal-interface/lib/api.ts` | Add production URL validation |

---

## Code Quality Scores

### Frontend Hormonia `api-client.ts`
- **Overall**: 7.5/10
- **CORS Handling**: 8/10 (✅ No credentials, ✅ Bearer tokens)
- **Environment Config**: 6/10 (❌ No validation, ❌ Docker issues)
- **Error Handling**: 9/10 (✅ Retry logic, ✅ Timeout handling)

### Quiz Interface `lib/api.ts`
- **Overall**: 8/10
- **CORS Handling**: 9/10 (✅ Simple requests, ✅ No auth headers)
- **Environment Config**: 7/10 (✅ Good fallbacks, ❌ No production validation)
- **Error Handling**: 8/10 (✅ Retry logic, ✅ Health checks)

---

## Next Steps

1. **Immediate** (Critical):
   - [ ] Fix `docker-compose.yml` to use `/api` or `localhost:8000`
   - [ ] Test CORS with updated configuration

2. **Short-term** (This Sprint):
   - [ ] Add URL validation to both frontends
   - [ ] Document environment variable requirements
   - [ ] Create CORS testing script

3. **Long-term** (Future):
   - [ ] Implement environment detection warnings
   - [ ] Add runtime configuration validation
   - [ ] Create deployment checklist with CORS verification

---

## References

- [MDN: CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
- [FastAPI CORS Middleware](https://fastapi.tiangolo.com/tutorial/cors/)
- [Nginx Proxy Configuration](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)

---

**Analysis completed by**: Claude Code Agent (Code Quality Analyzer)
**Memory stored**: `hive-mind/frontend/cors-patterns`
