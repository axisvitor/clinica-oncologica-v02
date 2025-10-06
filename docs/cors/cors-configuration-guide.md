# CORS Configuration Guide

**System**: Hormonia Healthcare Platform
**Last Updated**: October 6, 2025
**Version**: 2.0 (Post-PatternCORSMiddleware Fix)

---

## Table of Contents

1. [Overview](#overview)
2. [Production Setup](#production-setup)
3. [Development Setup](#development-setup)
4. [Environment Variables](#environment-variables)
5. [Middleware Configuration](#middleware-configuration)
6. [Testing CORS](#testing-cors)
7. [Troubleshooting](#troubleshooting)
8. [Security Best Practices](#security-best-practices)

---

## Overview

CORS (Cross-Origin Resource Sharing) is a security mechanism that controls which domains can access your API. The Hormonia platform uses FastAPI's standard `CORSMiddleware` to manage cross-origin requests between:

- **Frontend**: React application (Vite dev server)
- **Quiz Interface**: Monthly quiz standalone application
- **Backend API**: FastAPI REST endpoints
- **WebSocket**: Real-time notifications and analytics

### Why CORS Matters

Without proper CORS configuration:
- ❌ Frontend cannot fetch data from backend API
- ❌ Preflight OPTIONS requests fail
- ❌ WebSocket connections are rejected
- ❌ Authentication tokens cannot be shared across origins

---

## Production Setup

### 1. Railway Environment Variables

Configure the `ALLOWED_ORIGINS` environment variable in your Railway backend service:

**Railway Dashboard → Backend Service → Variables**

```env
ALLOWED_ORIGINS=["https://frontend-production-18bb.up.railway.app","https://quiz-interface-production.up.railway.app","https://clinica-oncologica-v02-production.up.railway.app"]
```

**Important**:
- Use JSON array format (square brackets)
- Include all production domains
- No wildcards (`*`) in production for security
- HTTPS only for production URLs

### 2. Verify Configuration

After deployment, check CORS configuration:

```bash
# Check backend health
curl https://clinica-oncologica-v02-production.up.railway.app/api/v1/health/detailed

# Look for CORS section in response:
{
  "cors": {
    "enabled": true,
    "allowed_origins_count": 3,
    "allowed_origins": [
      "https://frontend-production-18bb.up.railway.app",
      "https://quiz-interface-production.up.railway.app",
      "https://clinica-oncologica-v02-production.up.railway.app"
    ]
  }
}
```

### 3. Add New Production Origins

When deploying new frontend instances:

1. Note the new Railway URL (e.g., `https://new-frontend-xyz.up.railway.app`)
2. Update `ALLOWED_ORIGINS` in Railway:
   ```env
   ALLOWED_ORIGINS=["https://frontend-production-18bb.up.railway.app","https://quiz-interface-production.up.railway.app","https://new-frontend-xyz.up.railway.app"]
   ```
3. Redeploy backend or restart service
4. Test CORS from new origin

---

## Development Setup

### 1. Local Environment (.env file)

For local development, the backend `.env` file should include:

```env
# Development CORS - localhost and 127.0.0.1
ALLOWED_ORIGINS=[
  "http://localhost:3000",
  "http://localhost:5173",
  "http://localhost:5174",
  "http://localhost:5175",
  "http://localhost:5176",
  "http://localhost:5177",
  "http://localhost:5178",
  "http://localhost:5179",
  "http://localhost:3001",
  "http://localhost:8080",
  "http://127.0.0.1:3000",
  "http://127.0.0.1:5173",
  "http://127.0.0.1:5174",
  "http://127.0.0.1:5175",
  "http://127.0.0.1:5176",
  "http://127.0.0.1:5177",
  "http://127.0.0.1:5178",
  "http://127.0.0.1:5179",
  "http://127.0.0.1:3001",
  "http://127.0.0.1:5174",
  "http://127.0.0.1:8000",
  "http://127.0.0.1:8080"
]
```

**Why both localhost and 127.0.0.1?**
- Windows browsers may resolve to either
- Frontend config uses both formats
- Ensures compatibility across all scenarios

**Why multiple ports (5173-5179)?**
- Vite automatically increments port if occupied
- Supports multiple dev servers running simultaneously
- Prevents CORS errors when switching projects

### 2. Start Development Servers

```bash
# Terminal 1 - Backend
cd backend-hormonia
source venv/bin/activate  # or venv\Scripts\activate on Windows
uvicorn app.main:app --reload --port 8000

# Terminal 2 - Frontend
cd frontend-hormonia
npm run dev  # Starts on port 5173 (or next available)

# Terminal 3 - Quiz Interface (optional)
cd quiz-mensal-interface
npm run dev  # Starts on port 5174 (or next available)
```

### 3. Verify Local CORS

```bash
# Test from frontend origin
curl -X OPTIONS \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: GET" \
  http://localhost:8000/api/v1/auth/me \
  -v

# Should return CORS headers:
# Access-Control-Allow-Origin: http://localhost:5173
# Access-Control-Allow-Methods: *
# Access-Control-Allow-Headers: *
```

---

## Environment Variables

### ALLOWED_ORIGINS

**Type**: JSON Array or Comma-Separated String
**Required**: Yes
**Default**: Development origins (localhost + 127.0.0.1)

**Formats Supported**:

#### JSON Array (Recommended)
```env
ALLOWED_ORIGINS=["https://frontend.example.com","https://quiz.example.com"]
```

#### Comma-Separated String
```env
ALLOWED_ORIGINS=https://frontend.example.com,https://quiz.example.com
```

**Validation**:
- The backend uses `@field_validator` to parse both formats
- Empty strings are filtered out
- Whitespace is trimmed
- Invalid JSON arrays fall back to comma-separated parsing

### Example Configurations

#### Development (.env)
```env
ALLOWED_ORIGINS=[
  "http://localhost:3000",
  "http://localhost:5173",
  "http://127.0.0.1:3000",
  "http://127.0.0.1:5173"
]
```

#### Production - Railway (.env.railway.template)
```env
ALLOWED_ORIGINS=["https://frontend-production-18bb.up.railway.app","https://quiz-interface-production.up.railway.app"]
```

#### Production - Custom Domain
```env
ALLOWED_ORIGINS=["https://app.neoplasiaslitoral.com.br","https://quiz.neoplasiaslitoral.com.br","https://api.neoplasiaslitoral.com.br"]
```

---

## Middleware Configuration

### Current Implementation (Standard CORSMiddleware)

**File**: `backend-hormonia/app/core/middleware_setup.py`

```python
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.utils.logging import get_logger

def setup_middleware(app: FastAPI) -> None:
    logger = get_logger(__name__)

    # ... other middleware ...

    # CORS middleware - Standard FastAPI implementation
    logger.info(f"Configuring CORS with {len(settings.ALLOWED_ORIGINS)} allowed origins")
    logger.info(f"Allowed origins: {settings.ALLOWED_ORIGINS}")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,  # From environment variable
        allow_credentials=True,                  # Allow cookies/auth headers
        allow_methods=["*"],                     # Allow all HTTP methods
        allow_headers=["*"],                     # Allow all headers
        expose_headers=[                         # Custom headers exposed to frontend
            "X-Request-ID",
            "X-Correlation-ID",
            "X-Process-Time",
            "X-Quiz-Session-ID",
            "X-Quiz-Progress",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "X-Query-Count",
            "X-DB-Time-Ms",
            "X-Request-Duration"
        ],
        max_age=86400  # Preflight cache: 24 hours
    )

    logger.info("Standard CORS middleware configured successfully")
```

### Configuration Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `allow_origins` | `settings.ALLOWED_ORIGINS` | List of allowed origins from environment |
| `allow_credentials` | `true` | Allows cookies and authorization headers |
| `allow_methods` | `["*"]` | Allows all HTTP methods (GET, POST, PUT, DELETE, OPTIONS, PATCH) |
| `allow_headers` | `["*"]` | Allows all request headers |
| `expose_headers` | Custom list | Headers frontend can read from response |
| `max_age` | `86400` | Preflight response cache duration (24 hours) |

### Exposed Custom Headers

The backend exposes these custom headers for frontend consumption:

```javascript
// Frontend can access these headers from response
const requestId = response.headers.get('X-Request-ID');
const rateLimit = response.headers.get('X-RateLimit-Remaining');
const queryTime = response.headers.get('X-DB-Time-Ms');
```

**Healthcare-Specific Headers**:
- `X-Quiz-Session-ID`: Monthly quiz session tracking
- `X-Quiz-Progress`: User progress percentage
- `X-Query-Count`: Database query count for monitoring
- `X-DB-Time-Ms`: Database operation duration

---

## Testing CORS

### 1. Manual Testing with curl

#### Test Preflight OPTIONS
```bash
curl -X OPTIONS \
  -H "Origin: https://frontend-production-18bb.up.railway.app" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: authorization,content-type" \
  https://clinica-oncologica-v02-production.up.railway.app/api/v1/auth/me \
  -v
```

**Expected Response Headers**:
```
HTTP/2 200
access-control-allow-origin: https://frontend-production-18bb.up.railway.app
access-control-allow-credentials: true
access-control-allow-methods: *
access-control-allow-headers: *
access-control-max-age: 86400
```

#### Test Actual GET Request
```bash
curl -X GET \
  -H "Origin: https://frontend-production-18bb.up.railway.app" \
  -H "Authorization: Bearer <token>" \
  https://clinica-oncologica-v02-production.up.railway.app/api/v1/auth/me \
  -v
```

**Expected Response Headers**:
```
HTTP/2 200
access-control-allow-origin: https://frontend-production-18bb.up.railway.app
access-control-allow-credentials: true
access-control-expose-headers: X-Request-ID,X-RateLimit-Limit,...
```

### 2. CORS Test Endpoint

The backend provides a dedicated CORS testing endpoint:

```bash
# Test CORS configuration
curl https://clinica-oncologica-v02-production.up.railway.app/api/v1/health/cors-test

# Response:
{
  "message": "CORS GET test successful",
  "origin": "https://frontend-production-18bb.up.railway.app",
  "timestamp": "2025-10-06T12:00:00Z",
  "cors_configured": true,
  "allowed_origins": ["..."]
}
```

### 3. Browser Testing

Open browser DevTools (F12) → Network tab:

```javascript
// In browser console
fetch('https://clinica-oncologica-v02-production.up.railway.app/api/v1/health/cors-test', {
  method: 'GET',
  headers: {
    'Content-Type': 'application/json'
  }
})
  .then(res => res.json())
  .then(data => console.log('CORS Success:', data))
  .catch(err => console.error('CORS Error:', err));
```

**Success Indicators**:
- ✅ No CORS errors in console
- ✅ Network tab shows OPTIONS request (preflight) with 200 status
- ✅ GET request completes with response data
- ✅ Response headers include `Access-Control-Allow-Origin`

### 4. Automated Testing Script

Create a CORS test script:

**File**: `scripts/test-cors.sh`

```bash
#!/bin/bash

BACKEND_URL="https://clinica-oncologica-v02-production.up.railway.app"
FRONTEND_ORIGIN="https://frontend-production-18bb.up.railway.app"

echo "Testing CORS Configuration..."
echo "========================================"

# Test 1: Preflight OPTIONS
echo -e "\n1. Testing Preflight OPTIONS request..."
curl -X OPTIONS \
  -H "Origin: $FRONTEND_ORIGIN" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: authorization" \
  "$BACKEND_URL/api/v1/auth/me" \
  -s -D - -o /dev/null | grep -i "access-control"

# Test 2: GET with Origin
echo -e "\n2. Testing GET request with Origin header..."
curl -X GET \
  -H "Origin: $FRONTEND_ORIGIN" \
  "$BACKEND_URL/api/v1/health/cors-test" \
  -s -D - -o /dev/null | grep -i "access-control"

# Test 3: Health Check
echo -e "\n3. Checking CORS configuration..."
curl -s "$BACKEND_URL/api/v1/health/detailed" | jq '.cors'

echo -e "\n========================================"
echo "CORS testing complete!"
```

Usage:
```bash
chmod +x scripts/test-cors.sh
./scripts/test-cors.sh
```

---

## Troubleshooting

### Issue 1: CORS Blocked - No Access-Control-Allow-Origin Header

**Symptoms**:
```
Access to fetch at 'https://backend.railway.app/api/v1/auth/me'
from origin 'https://frontend.railway.app'
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present
```

**Causes**:
1. Origin not in `ALLOWED_ORIGINS` environment variable
2. `ALLOWED_ORIGINS` not loaded (environment variable missing)
3. CORS middleware not registered
4. Backend not running

**Solutions**:

1. **Check environment variable**:
   ```bash
   # Railway Dashboard → Backend → Variables → ALLOWED_ORIGINS
   # Verify frontend URL is in the list
   ```

2. **Check backend logs**:
   ```bash
   railway logs --service backend-hormonia | grep "CORS"

   # Should see:
   # "Configuring CORS with X allowed origins"
   # "Allowed origins: [...]"
   # "Standard CORS middleware configured successfully"
   ```

3. **Verify backend is running**:
   ```bash
   curl https://backend.railway.app/test
   # Should return: {"message": "Server is working", ...}
   ```

4. **Add missing origin**:
   ```env
   # Add to ALLOWED_ORIGINS
   ALLOWED_ORIGINS=["https://frontend.railway.app","https://backend.railway.app"]
   ```

---

### Issue 2: CORS Works for Some Requests but Not Others

**Symptoms**:
- Simple GET requests work
- POST/PUT/DELETE requests fail with CORS error
- Requests with custom headers fail

**Cause**: Preflight OPTIONS request failing

**Solutions**:

1. **Verify OPTIONS is allowed**:
   ```python
   # In middleware_setup.py
   allow_methods=["*"]  # Includes OPTIONS
   ```

2. **Test preflight separately**:
   ```bash
   curl -X OPTIONS \
     -H "Origin: https://frontend.railway.app" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: authorization,content-type" \
     https://backend.railway.app/api/v1/auth/login \
     -v
   ```

3. **Check custom headers are allowed**:
   ```python
   # In middleware_setup.py
   allow_headers=["*"]  # Allows all headers
   ```

---

### Issue 3: CORS Works Locally but Not in Production

**Symptoms**:
- Local development: CORS works fine
- Production (Railway): CORS blocked

**Causes**:
1. Production origin not in `ALLOWED_ORIGINS`
2. HTTP vs HTTPS mismatch
3. Environment variable not set in Railway
4. Middleware not initialized in production mode

**Solutions**:

1. **Check production origins**:
   ```bash
   # Production should use HTTPS
   ALLOWED_ORIGINS=["https://frontend-production.railway.app"]

   # NOT http://
   ```

2. **Verify Railway environment variables**:
   ```bash
   # Railway Dashboard → Backend → Variables
   # Ensure ALLOWED_ORIGINS is set
   ```

3. **Check production logs**:
   ```bash
   railway logs --service backend-hormonia --tail 100 | grep "CORS"
   ```

4. **Test with production URL**:
   ```bash
   curl -X OPTIONS \
     -H "Origin: https://frontend-production.railway.app" \
     https://backend-production.railway.app/api/v1/auth/me \
     -v
   ```

---

### Issue 4: WebSocket CORS Errors (502 Bad Gateway)

**Symptoms**:
```
WebSocket connection to 'wss://backend.railway.app/ws' failed:
Unexpected server response: 502
```

**Causes**:
1. WebSocket endpoint not configured
2. CORS headers missing for WebSocket upgrade
3. Railway WebSocket support not enabled
4. Preflight failing for WebSocket origin

**Solutions**:

1. **Verify WebSocket endpoint exists**:
   ```bash
   # Check API docs
   curl https://backend.railway.app/docs
   # Look for /ws or /ws/connect endpoint
   ```

2. **Check Railway WebSocket support**:
   ```
   Railway Dashboard → Backend → Settings → Networking
   → Enable WebSocket Support
   ```

3. **Test WebSocket CORS**:
   ```javascript
   // In browser console
   const ws = new WebSocket('wss://backend.railway.app/ws/connect?token=test');
   ws.onopen = () => console.log('Connected');
   ws.onerror = (e) => console.error('Error:', e);
   ```

4. **Ensure origin in ALLOWED_ORIGINS**:
   ```env
   ALLOWED_ORIGINS=["https://frontend.railway.app","wss://frontend.railway.app"]
   ```

---

### Issue 5: Localhost vs 127.0.0.1 CORS Failures

**Symptoms**:
- `http://localhost:5173` works
- `http://127.0.0.1:5173` fails (or vice versa)

**Cause**: Windows/browser may resolve to either address

**Solution**: Include both in development ALLOWED_ORIGINS

```env
ALLOWED_ORIGINS=[
  "http://localhost:3000",
  "http://localhost:5173",
  "http://127.0.0.1:3000",
  "http://127.0.0.1:5173"
]
```

---

### Issue 6: Multiple Vite Dev Servers Port Conflicts

**Symptoms**:
- First dev server (port 5173) works
- Second dev server (port 5174) has CORS errors
- Port keeps incrementing (5175, 5176...)

**Cause**: Vite automatically uses next available port

**Solution**: Include all common Vite ports

```env
ALLOWED_ORIGINS=[
  "http://localhost:5173",
  "http://localhost:5174",
  "http://localhost:5175",
  "http://localhost:5176",
  "http://localhost:5177",
  "http://localhost:5178",
  "http://localhost:5179"
]
```

---

## Security Best Practices

### 1. Never Use Wildcards in Production

**❌ BAD**:
```env
# NEVER do this in production
ALLOWED_ORIGINS=["*"]
```

**✅ GOOD**:
```env
# Explicitly list all production origins
ALLOWED_ORIGINS=["https://app.yourdomain.com","https://api.yourdomain.com"]
```

**Why**: Wildcard `*` allows any website to access your API, exposing sensitive data.

---

### 2. Use HTTPS in Production

**❌ BAD**:
```env
# Insecure in production
ALLOWED_ORIGINS=["http://app.yourdomain.com"]
```

**✅ GOOD**:
```env
# Always use HTTPS
ALLOWED_ORIGINS=["https://app.yourdomain.com"]
```

**Why**: HTTP is unencrypted and vulnerable to man-in-the-middle attacks.

---

### 3. Limit Allowed Origins

**❌ BAD**:
```env
# Too permissive
ALLOWED_ORIGINS=["https://*.yourdomain.com"]
```

**✅ GOOD**:
```env
# Explicit subdomains only
ALLOWED_ORIGINS=["https://app.yourdomain.com","https://admin.yourdomain.com"]
```

**Why**: Subdomain wildcards can expose APIs to compromised subdomains.

---

### 4. Separate Development and Production

**Development (.env.local)**:
```env
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:5173","http://127.0.0.1:3000"]
```

**Production (Railway Variables)**:
```env
ALLOWED_ORIGINS=["https://app.yourdomain.com","https://api.yourdomain.com"]
```

**Why**: Development needs broad access for testing; production should be restrictive.

---

### 5. Monitor CORS Errors

Set up logging and alerts for CORS failures:

```python
# In middleware_setup.py
logger.info(f"CORS request from origin: {request.headers.get('origin')}")

# Monitor for unauthorized origins
if origin not in settings.ALLOWED_ORIGINS:
    logger.warning(f"CORS rejected for origin: {origin}")
```

**Alert Conditions**:
- CORS rejection rate > 1%
- Repeated rejections from same origin (possible attack)
- Sudden spike in CORS errors (configuration issue)

---

### 6. Regular Security Audits

**Quarterly Review Checklist**:
- [ ] Review `ALLOWED_ORIGINS` list
- [ ] Remove deprecated/unused origins
- [ ] Verify all production URLs are HTTPS
- [ ] Check for wildcard patterns
- [ ] Test CORS from all production domains
- [ ] Review CORS error logs
- [ ] Update documentation

---

### 7. Credential Handling

The backend allows credentials (cookies, authorization headers):

```python
allow_credentials=True
```

**Security Implications**:
- ✅ Required for authentication tokens
- ⚠️ Must pair with explicit origin list (never `*`)
- ✅ Enables secure cookie sharing
- ⚠️ Increases CSRF risk (mitigated by SameSite cookies)

**CSRF Protection** (already implemented):
```python
# In config.py
COOKIE_SAMESITE = "lax"  # Prevents CSRF attacks
COOKIE_SECURE = True     # HTTPS only
COOKIE_HTTPONLY = True   # No JavaScript access
```

---

### 8. Rate Limiting CORS Requests

Apply rate limiting to prevent CORS abuse:

```python
# Already implemented in EnhancedRateLimitMiddleware
@limiter.limit("100/minute")
async def cors_protected_endpoint():
    # Prevents CORS probing attacks
    pass
```

---

## Quick Reference

### Common Commands

```bash
# Test CORS locally
curl -X OPTIONS -H "Origin: http://localhost:5173" http://localhost:8000/api/v1/auth/me -v

# Test CORS in production
curl -X OPTIONS -H "Origin: https://frontend.railway.app" https://backend.railway.app/api/v1/auth/me -v

# Check CORS configuration
curl https://backend.railway.app/api/v1/health/detailed | jq '.cors'

# View CORS logs
railway logs --service backend-hormonia | grep "CORS"

# Test WebSocket CORS
wscat -c wss://backend.railway.app/ws/connect --origin https://frontend.railway.app
```

### Environment Variable Templates

**Development**:
```env
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:5173","http://127.0.0.1:3000","http://127.0.0.1:5173"]
```

**Production (Railway)**:
```env
ALLOWED_ORIGINS=["https://app.yourdomain.com","https://api.yourdomain.com"]
```

**Production (Custom Domain)**:
```env
ALLOWED_ORIGINS=["https://hormonia.neoplasiaslitoral.com.br","https://api.neoplasiaslitoral.com.br"]
```

---

## Related Documentation

- [CORS Audit Report](./cors-audit-report.md) - Security audit findings
- [CORS Testing Guide](./cors-testing-guide.md) - Comprehensive testing procedures
- [Security Best Practices](../security/SECURITY_BEST_PRACTICES.md) - Overall security guidelines
- [Railway Deployment Guide](../deployment/RAILWAY_DEPLOYMENT.md) - Production deployment
- [Environment Variables Guide](../deployment/ENVIRONMENT_VARIABLES.md) - All environment variables

---

**Last Updated**: October 6, 2025
**Maintained By**: Backend Team
**Review Frequency**: Quarterly
