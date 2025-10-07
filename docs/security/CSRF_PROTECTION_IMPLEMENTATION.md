# CSRF Protection Implementation

**Security Fix:** SEC-002 - Implement CSRF protection middleware
**Status:** ✅ Implemented
**Priority:** CRITICAL - Blocking Production Deployment

## Overview

CSRF (Cross-Site Request Forgery) protection has been implemented to secure session-based authentication endpoints from unauthorized cross-site requests.

## What is CSRF?

CSRF is an attack that tricks the user's browser into making unwanted requests to a web application in which the user is currently authenticated. Without CSRF protection, attackers can:

1. Create malicious websites that submit forms to your API
2. Trick authenticated users into executing unwanted actions
3. Create/manipulate sessions without user consent

## Implementation Details

### 1. Dependencies

**Added to requirements.txt:**
```python
fastapi-csrf-protect>=0.3.4,<1.0.0  # CSRF protection for session endpoints
```

**Installation:**
```bash
pip install -r requirements.txt
```

### 2. Backend Components

#### **CSRF Middleware** (`backend-hormonia/app/middleware/csrf.py`)

Core CSRF protection module with:
- Token generation and validation
- Cookie security configuration (httpOnly, secure, SameSite)
- Configurable secret key from environment
- Exempt endpoint management

**Key Functions:**
```python
# Get CSRF token from backend
get_csrf_token(request) -> str

# Validate CSRF token in request
validate_csrf_token(request) -> None

# Set CSRF cookie in response
set_csrf_cookie(request, response) -> None

# Check if endpoint is exempt
is_csrf_exempt(path) -> bool
```

#### **Configuration** (`backend-hormonia/app/config.py`)

**Added Settings:**
```python
CSRF_SECRET_KEY: Optional[str] = Field(
    default=None,
    description="Secret key for CSRF token generation"
)
```

**Environment Variable (.env):**
```bash
# Generate secure key with:
# python -c "import secrets; print(secrets.token_urlsafe(32))"
CSRF_SECRET_KEY=your-secure-random-key-here
```

#### **Application Factory** (`backend-hormonia/app/core/application_factory.py`)

**CSRF Exception Handler:**
```python
@app.exception_handler(CsrfProtectError)
async def csrf_protect_exception_handler(request, exc):
    return JSONResponse(
        status_code=403,
        content={
            "error": "csrf_validation_failed",
            "message": "CSRF token validation failed. Please refresh and try again."
        }
    )
```

**CSRF Token Endpoint:**
```
GET /api/v1/csrf-token
```

Returns:
```json
{
  "csrf_token": "eyJ...",
  "expires_in": 3600,
  "usage": "Include this token in X-CSRF-Token header for POST/PUT/DELETE requests"
}
```

### 3. Protected Endpoints

**Session Management Routes** (will be enforced after testing):

- `POST /api/v1/session` - Create session
- `DELETE /api/v1/session/logout` - Single session logout
- `DELETE /api/v1/session/logout-all` - Global logout

**Implementation Notes:**
- Routes currently have empty `dependencies=[]` placeholders
- CSRF validation will be enforced after comprehensive testing
- To enforce: `dependencies=[Depends(validate_csrf_token)]`

### 4. Exempt Endpoints

**Read-Only Endpoints** (no CSRF required):

- `GET /api/v1/session/validate` - Session validation
- `GET /api/v1/session/active` - List active sessions
- `GET /api/v1/session/stats` - Cache statistics
- `GET /api/v1/csrf-token` - Token generation
- `/docs`, `/redoc`, `/openapi.json` - Documentation

**Why Exempt?**
- GET/HEAD/OPTIONS requests don't modify state
- CSRF attacks exploit state-changing operations (POST/PUT/DELETE)

### 5. Frontend Integration

#### **API Client** (`frontend-hormonia/src/lib/api-client.ts`)

**Added Methods:**
```typescript
// Fetch CSRF token on app init
async fetchCsrfToken(): Promise<void>

// Get current CSRF token
getCsrfToken(): string | null
```

**Automatic Token Injection:**
```typescript
// Add CSRF token for state-changing requests
const method = (fetchOptions.method || 'GET').toUpperCase()
if (['POST', 'PUT', 'DELETE'].includes(method) && this.csrfToken) {
  headers['X-CSRF-Token'] = this.csrfToken
}
```

#### **Frontend Workflow**

1. **App Initialization:**
   ```typescript
   // Fetch CSRF token on app load
   await apiClient.fetchCsrfToken()
   ```

2. **Session Creation:**
   ```typescript
   // Token automatically included in POST requests
   const response = await apiClient.post('/api/v1/session', {
     firebase_token: idToken
   })
   ```

3. **Subsequent Requests:**
   - CSRF token stored in memory (apiClient.csrfToken)
   - Automatically included in all POST/PUT/DELETE requests
   - CSRF cookie automatically sent by browser

## Security Features

### 1. Cookie Security

**Flags Set:**
- `httpOnly=true` - Prevents JavaScript access (XSS protection)
- `secure=true` - Requires HTTPS in production
- `SameSite=Strict` - Prevents cross-site cookie sending (CSRF protection)

**Cookie Name:** `fastapi-csrf-token`

### 2. Token Security

**Token Properties:**
- Cryptographically secure generation
- 1-hour expiration
- Signed with secret key (prevents tampering)
- Unique per request

### 3. Environment-Based Configuration

**Development Mode:**
- `cookie_secure=false` (allows HTTP)
- Enhanced logging for debugging
- Full error details in responses

**Production Mode:**
- `cookie_secure=true` (requires HTTPS)
- Minimal error details
- Production-grade logging

## Testing

### Test Suite (`tests/test_csrf_protection.py`)

**Coverage:**
1. ✅ CSRF token generation and validation
2. ✅ Protected endpoint behavior
3. ✅ Exempt endpoint behavior
4. ✅ Cookie security flags
5. ✅ Configuration validation
6. ✅ Error handling
7. ✅ Integration workflows

**Run Tests:**
```bash
cd backend-hormonia
pytest tests/test_csrf_protection.py -v
```

**Test Categories:**
- `TestCsrfTokenGeneration` - Token generation
- `TestCsrfProtectedEndpoints` - Endpoint protection
- `TestCsrfExemptEndpoints` - Exempt endpoints
- `TestCsrfConfiguration` - Settings validation
- `TestCsrfSecurityValidation` - Security checks
- `TestCsrfEnforcement` - Future tests (post-enforcement)

### Manual Testing

**1. Get CSRF Token:**
```bash
curl -X GET http://localhost:8000/api/v1/csrf-token \
  -c cookies.txt
```

**2. Create Session (without CSRF - currently allowed):**
```bash
curl -X POST http://localhost:8000/api/v1/session \
  -H "Content-Type: application/json" \
  -d '{"firebase_token": "test-token"}'
```

**3. Create Session (with CSRF - recommended):**
```bash
curl -X POST http://localhost:8000/api/v1/session \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: YOUR_TOKEN_HERE" \
  -b cookies.txt \
  -d '{"firebase_token": "test-token"}'
```

## Deployment Checklist

### Before Production Deployment

- [ ] Generate secure `CSRF_SECRET_KEY`
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

- [ ] Add to Railway environment variables:
  ```
  CSRF_SECRET_KEY=<generated-key>
  ```

- [ ] Verify production mode settings:
  ```env
  ENVIRONMENT=production
  SESSION_COOKIE_SECURE=true
  SECURE_SSL_REDIRECT=true
  ```

- [ ] Enable CSRF enforcement on session routes:
  ```python
  @router.post(
      "/",
      dependencies=[Depends(validate_csrf_token)]  # Uncomment/enable
  )
  ```

- [ ] Run full test suite:
  ```bash
  pytest tests/test_csrf_protection.py -v
  ```

- [ ] Test CSRF flow in staging environment

- [ ] Update frontend to call `fetchCsrfToken()` on app init

### Post-Deployment Verification

1. **Verify CSRF token endpoint:**
   ```bash
   curl https://your-api.railway.app/api/v1/csrf-token
   ```

2. **Verify CSRF cookie is set:**
   - Check response headers for `Set-Cookie: fastapi-csrf-token`
   - Verify flags: `HttpOnly; Secure; SameSite=Strict`

3. **Test session creation with CSRF:**
   - Should succeed with valid token
   - Should fail (403) without token (after enforcement)

4. **Monitor logs for CSRF errors:**
   ```
   CSRF validation failed: ...
   ```

## Known Limitations

1. **CSRF Not Yet Enforced:**
   - Currently implemented but not enforced on endpoints
   - `dependencies=[]` placeholders in routes
   - Will be enforced after comprehensive testing

2. **Testing Required:**
   - Need to test with actual Firebase tokens
   - Need to verify frontend integration
   - Need to test in staging environment

3. **Token Storage:**
   - CSRF token stored in memory (not localStorage)
   - Token lost on page refresh (requires re-fetch)
   - Consider session storage for persistence

## Future Enhancements

1. **CSRF Token Persistence:**
   - Store in sessionStorage for page refresh persistence
   - Implement automatic token refresh on expiration

2. **Enhanced Logging:**
   - Log CSRF validation attempts
   - Track CSRF attack patterns
   - Alert on repeated failures

3. **Rate Limiting:**
   - Limit CSRF token generation requests
   - Prevent token enumeration attacks

4. **Token Rotation:**
   - Automatic token rotation after use
   - Double-submit cookie pattern

## References

- **fastapi-csrf-protect:** https://github.com/aekasitt/fastapi-csrf-protect
- **OWASP CSRF Prevention:** https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
- **SameSite Cookies:** https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie/SameSite

## Support

For issues or questions:
- Review test suite: `tests/test_csrf_protection.py`
- Check middleware implementation: `app/middleware/csrf.py`
- See configuration: `app/config.py`

---

**Status:** ✅ CSRF protection implemented and ready for enforcement
**Last Updated:** 2025-01-07
**Severity:** CRITICAL - SEC-002
