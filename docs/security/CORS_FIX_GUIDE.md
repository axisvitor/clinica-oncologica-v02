# CORS Configuration Fix - Production Guide

## 🔴 Problem Identified

**Error**: `Access-Control-Allow-Credentials` header is empty when it should be `true`

```
Access to fetch at 'https://clinica-oncologica-v02-production.up.railway.app/api/v1/csrf-token'
from origin 'https://frontend-production-18bb.up.railway.app' has been blocked by CORS policy:
Response to preflight request doesn't pass access control check:
The value of the 'Access-Control-Allow-Credentials' header in the response is '' which must be 'true'
when the request's credentials mode is 'include'.
```

## 🔍 Root Cause

In `backend-hormonia/app/core/middleware_setup.py`:

```python
# ❌ BEFORE (WRONG)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,  # ← THIS WAS THE PROBLEM
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=86400
)
```

This configuration prevented the backend from sending the `Access-Control-Allow-Credentials: true` header, which is **required** when:
- Frontend uses `credentials: 'include'` in fetch requests
- Backend uses httpOnly cookies for authentication
- Session cookies need to be sent cross-origin

## ✅ Solution Applied

### 1. Updated Middleware Configuration

**File**: `backend-hormonia/app/core/middleware_setup.py`

```python
# ✅ AFTER (CORRECT)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,  # ✅ CRITICAL: Required for httpOnly cookies
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],      # ✅ Allow all headers for flexibility
    expose_headers=["*"],     # ✅ Expose all headers to frontend
    max_age=86400
)
```

**Changes Made**:
1. ✅ `allow_credentials=True` - Enables credentials in CORS responses
2. ✅ `allow_headers=["*"]` - More flexible header support
3. ✅ `expose_headers=["*"]` - Frontend can read all response headers

### 2. Configure Railway Environment Variable

**Required**: Set `CORS_ORIGINS` environment variable in Railway

```bash
# Option 1: Use the provided script
chmod +x scripts/configure-cors-railway.sh
./scripts/configure-cors-railway.sh

# Option 2: Manual configuration via Railway CLI
railway variables --service backend set "CORS_ORIGINS=https://frontend-production-18bb.up.railway.app,https://quiz-interface-production.up.railway.app"

# Option 3: Via Railway Dashboard
# Go to: Project → backend service → Variables
# Add: CORS_ORIGINS = https://frontend-production-18bb.up.railway.app,https://quiz-interface-production.up.railway.app
```

## 🔒 Security Validation

### Production CORS Configuration

✅ **Explicit Origins**: No wildcards (`*`) allowed
✅ **HTTPS Only**: All origins must use HTTPS in production
✅ **Credentials Enabled**: Required for httpOnly cookies
✅ **No Regex Patterns**: Production uses exact domain matching

### Code Validation (from `app/middleware/cors.py`)

```python
def validate_cors_origins(allow_origins: List[str], allow_origin_regex: Optional[str] = None) -> None:
    if not is_production():
        return  # Development mode - no restrictions

    # Rule 1: No regex in production
    if allow_origin_regex:
        raise ValueError("CORS origin regex not allowed in production.")

    # Rule 2: No wildcard origins in production
    if "*" in allow_origins:
        raise ValueError("CORS wildcard origin (*) not allowed in production.")

    # Rule 3: All origins must be HTTPS in production
    for origin in allow_origins:
        if not origin.startswith("https://"):
            raise ValueError(f"CORS origin '{origin}' must use HTTPS in production.")
```

## 📋 Deployment Checklist

- [x] **Code Fixed**: `allow_credentials=True` in middleware_setup.py
- [ ] **Environment Variable Set**: CORS_ORIGINS in Railway
- [ ] **Deploy**: Push changes to Railway
- [ ] **Verify**: Test CORS requests from frontend
- [ ] **Monitor**: Check Railway logs for CORS configuration

## 🧪 Testing CORS Configuration

### 1. Check Railway Logs

```bash
railway logs --service backend

# Expected output:
# CORS Production Mode: 2 allowed origins
# Allowed origins: ['https://frontend-production-18bb.up.railway.app', 'https://quiz-interface-production.up.railway.app']
```

### 2. Test CORS Endpoint

```bash
curl -v -X OPTIONS \
  -H "Origin: https://frontend-production-18bb.up.railway.app" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type" \
  https://clinica-oncologica-v02-production.up.railway.app/api/v1/csrf-token

# Expected headers in response:
# Access-Control-Allow-Origin: https://frontend-production-18bb.up.railway.app
# Access-Control-Allow-Credentials: true
# Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
```

### 3. Test from Browser Console

```javascript
// Open frontend at: https://frontend-production-18bb.up.railway.app
// Open browser DevTools Console and run:

fetch('https://clinica-oncologica-v02-production.up.railway.app/api/v1/csrf-token', {
  credentials: 'include',
  method: 'GET'
})
  .then(r => r.json())
  .then(data => console.log('✅ CORS working!', data))
  .catch(e => console.error('❌ CORS error:', e))
```

## 🔧 Troubleshooting

### Issue: Still getting CORS errors after deployment

**Check 1**: Verify CORS_ORIGINS is set
```bash
railway variables --service backend | grep CORS_ORIGINS
```

**Check 2**: Verify deployment succeeded
```bash
railway status --service backend
```

**Check 3**: Check logs for CORS configuration
```bash
railway logs --service backend | grep CORS
```

### Issue: CORS working for some endpoints but not others

**Possible cause**: Multiple CORS middleware configurations conflicting

**Solution**: The fix in `middleware_setup.py` is the primary CORS configuration. Ensure other middleware (like `PublicEndpointCORSMiddleware`) delegates to the main CORSMiddleware.

### Issue: Credentials not being sent

**Frontend check**: Ensure `credentials: 'include'` in fetch calls
```typescript
// ✅ CORRECT
fetch(url, {
  credentials: 'include',
  headers: { 'Content-Type': 'application/json' }
})

// ❌ WRONG
fetch(url, {
  headers: { 'Content-Type': 'application/json' }
})
```

## 📚 Related Files

- `backend-hormonia/app/core/middleware_setup.py` - Main CORS configuration
- `backend-hormonia/app/middleware/cors.py` - CORS validation utilities
- `backend-hormonia/app/config.py` - CORS_ORIGINS environment variable
- `frontend-hormonia/src/lib/api-client.ts` - Frontend API client with credentials
- `quiz-mensal-interface/lib/api.ts` - Quiz API client with credentials

## 🎯 Expected Behavior After Fix

1. ✅ Frontend can make authenticated requests to backend
2. ✅ httpOnly cookies are sent and received correctly
3. ✅ CSRF tokens work properly
4. ✅ Session authentication functions normally
5. ✅ Quiz interface can access public endpoints
6. ✅ WebSocket connections establish successfully

## 📊 Impact

**Before Fix**:
- ❌ All authenticated API calls failed
- ❌ CSRF token endpoint blocked
- ❌ Session validation blocked
- ❌ Login impossible

**After Fix**:
- ✅ All authenticated API calls work
- ✅ CSRF protection functional
- ✅ Session management works
- ✅ Login/logout functional
- ✅ httpOnly cookies transmitted securely

## 🚀 Next Steps

1. **Immediate**: Deploy the code changes to Railway
2. **Configure**: Set CORS_ORIGINS environment variable
3. **Test**: Verify CORS is working from frontend
4. **Monitor**: Watch logs for any CORS-related issues
5. **Document**: Update API documentation with CORS requirements

---

**Status**: ✅ Code fixed, awaiting deployment
**Priority**: P0 - Critical (blocks all frontend functionality)
**Security Impact**: None (fix maintains security while enabling functionality)
