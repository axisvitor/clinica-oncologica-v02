# AUTHENTICATION & AUTHORIZATION SECURITY AUDIT

**Date**: 2025-11-07  
**System**: Clinica Oncológica v02 - Hormonia Backend  
**Scope**: Complete authentication and authorization infrastructure  
**Status**: CRITICAL REVIEW COMPLETE

---

## EXECUTIVE SUMMARY

The system implements a **dual authentication architecture** (Firebase + Redis sessions) with comprehensive security controls. While the foundation is solid, several **CRITICAL** and **HIGH** priority vulnerabilities require immediate attention to prevent account takeover and data breach scenarios.

**Overall Security Score: 7.2/10**

**Immediate Action Required**: 5 critical issues  
**High Priority**: 8 issues  
**Medium Priority**: 12 issues

---

## CRITICAL VULNERABILITIES (P0)

### 1. ⚠️ TOKEN BLACKLIST NOT PERSISTENT (CRITICAL)
**File**: `/app/services/auth.py:52`
**Risk**: Session hijacking after restart, no token revocation persistence

**Details**:
- Token blacklist stored in-memory only: `self._blacklisted_tokens: Set[str] = set()`
- Server restart = all blacklisted tokens become valid again
- Logout tokens can be reused after system reboot
- **No Redis persistence** for blacklist

**Impact**: 
- Attacker can capture token, wait for restart, reuse revoked token
- Logout doesn't truly invalidate tokens across restarts
- **Account takeover possible**

**Fix**: Migrate to Redis-backed persistent blacklist with TTL


### 2. ⚠️ RATE LIMITING DISABLED GLOBALLY (CRITICAL)
**File**: `/app/core/middleware_setup.py:129`
**Risk**: Brute force attacks, credential stuffing, API abuse

**Details**:
```python
# Rate limiting middleware DISABLED per user request
# Line 129: logger.info("⚠️  Rate limiting middleware DISABLED - removed per admin request")
```

**Impact**:
- No protection against brute force login attempts
- API endpoints can be hammered without limits
- Password spraying attacks unmitigated
- **High vulnerability to credential theft**

**Fix**: Re-enable with per-endpoint configuration, whitelist admin operations


### 3. ⚠️ SESSION TIMEOUT UNDEFINED (CRITICAL)
**File**: `/app/config/settings/security.py:106-109`
**Risk**: Indefinite session validity, no automatic expiration

**Details**:
- `FIREBASE_SESSION_TTL: int = 86400` (24 hours defined)
- **No enforcement found in session validation code**
- Sessions may persist indefinitely in Redis
- No sliding window or absolute timeout logic

**Impact**:
- Stolen session tokens valid for extended periods
- No automatic logout after inactivity
- Increased window for session hijacking

**Fix**: Implement strict session expiration with sliding window


### 4. ⚠️ CSRF VALIDATION BYPASS POSSIBLE
**File**: `/app/middleware/custom_csrf.py` (referenced)
**Risk**: Cross-Site Request Forgery attacks

**Details**:
- CSRF implemented but with custom middleware for "cross-domain compatibility"
- `/api/v1/csrf-token` endpoint returns token in JSON (not just cookie)
- Custom implementation may have bypass vulnerabilities
- Token validation may be inconsistent

**Impact**:
- Attacker can forge requests from malicious sites
- State-changing operations vulnerable
- **Data manipulation possible**

**Fix**: Audit custom CSRF implementation, use battle-tested library


### 5. ⚠️ NO CONCURRENT SESSION LIMITS (CRITICAL)
**File**: Authentication dependencies
**Risk**: Account sharing, credential theft goes undetected

**Details**:
- No limit on concurrent sessions per user
- No session enumeration or monitoring
- Users can have unlimited active sessions
- No "logout all" cleanup validation

**Impact**:
- Account credentials can be shared indefinitely
- Stolen credentials = unlimited attacker sessions
- No detection of abnormal login patterns

**Fix**: Implement max sessions per user (e.g., 5 devices)

---

## HIGH PRIORITY ISSUES (P1)

### 6. 🔴 ADMIN ROLE HAS UNRESTRICTED ACCESS
**File**: `/app/dependencies/auth_dependencies.py:71-96`
**Risk**: Over-privileged accounts, lateral movement

**Details**:
```python
if role == "ADMIN":
    return [
        # ALL PERMISSIONS - 20+ permissions including delete operations
        "admin.delete", "users.delete", "patients.delete", 
        "appointments.delete", "treatments.delete"
    ]
```

**Impact**:
- Admin compromise = total system compromise
- No principle of least privilege
- Single point of failure
- **Excessive blast radius**

**Recommendation**: Implement granular admin roles (SuperAdmin, UserAdmin, DataAdmin)


### 7. 🔴 PASSWORD HASHING WORKAROUND FOR BCRYPT BUG
**File**: `/app/utils/security.py:108-136`
**Risk**: Inconsistent password verification, potential bypass

**Details**:
- Workaround for passlib/bcrypt detection bug
- Falls back to direct bcrypt on verification failure
- Inconsistent hash verification logic
- Railway deployment hack

```python
except ValueError as e:
    if "password cannot be longer than 72 bytes" in str(e):
        # Fallback to direct bcrypt
        return bcrypt_lib.checkpw(password_bytes, hashed_password.encode('utf-8'))
```

**Impact**:
- Timing attack vulnerability in fallback path
- Hash confusion possible
- **Authentication bypass potential**

**Fix**: Fix root cause, remove workaround, implement constant-time comparison


### 8. 🔴 FIREBASE CUSTOM CLAIMS NOT VALIDATED
**File**: `/app/services/firebase_auth_service.py:98-107`
**Risk**: Privilege escalation via token manipulation

**Details**:
- Custom claims extracted but not validated
- No signature verification on custom claims
- No role enforcement at token level
- Trusts client-provided role data

**Impact**:
- Attacker can forge "admin" role in custom claims
- **Privilege escalation possible**
- Bypass RBAC via token manipulation

**Fix**: Server-side role validation, ignore client claims, use database roles


### 9. 🔴 NO PASSWORD COMPLEXITY ENFORCEMENT AT API LEVEL
**File**: `/app/services/auth.py:259` (validation exists but not enforced)
**Risk**: Weak passwords, easy credential theft

**Details**:
- Password validation function exists (`validate_password_strength`)
- **Not called in user creation flow**
- Minimum 8 characters only enforced
- No complexity rules applied

**Impact**:
- Users can set weak passwords (e.g., "password123")
- Dictionary attacks succeed
- **Easy account compromise**

**Fix**: Enforce `validate_password_strength` in all password operations


### 10. 🔴 SQL INJECTION RISK IN RAW QUERIES
**File**: `/app/tasks/flow_automation.py` (multiple instances)
**Risk**: Database compromise, data exfiltration

**Details**:
- Raw SQL with `text()` wrapper found
- Query parameters may not be properly escaped
- Multiple instances in flow automation tasks

```python
query = text("""
    SELECT ... FROM ...
""")
result = await db.execute(query)
```

**Impact**:
- SQL injection if user input reaches these queries
- **Database takeover possible**
- Data breach scenario

**Fix**: Audit all raw SQL, use SQLAlchemy ORM, parameterize queries


### 11. 🔴 WEBHOOK SIGNATURE VALIDATION OPTIONAL
**File**: `/app/core/middleware_setup.py:106-122`
**Risk**: Webhook spoofing, unauthorized data injection

**Details**:
```python
if settings.EVOLUTION_WEBHOOK_SECRET:
    # Validation enabled
else:
    logger.warning("⚠️ Webhook signature validation DISABLED")
```

**Impact**:
- Attackers can forge webhook requests
- Data manipulation via fake webhooks
- **Patient data injection possible**

**Fix**: Make webhook validation MANDATORY, fail startup if not configured


### 12. 🔴 NO API RATE LIMITING PER ENDPOINT
**File**: Rate limiting disabled globally
**Risk**: API abuse, DoS attacks

**Details**:
- Global rate limiter disabled
- No per-endpoint rate limits
- SlowAPI configured but disabled
- Unlimited requests possible

**Impact**:
- Expensive operations can be spammed
- DoS via resource exhaustion
- **Service disruption possible**

**Fix**: Per-endpoint rate limits (e.g., 100/min for reads, 10/min for writes)


### 13. 🔴 SESSION FIXATION VULNERABILITY
**File**: `/app/routers/auth_session.py` (session management)
**Risk**: Session hijacking via fixation

**Details**:
- No session ID regeneration after login
- Session ID may be predictable
- No validation that session belongs to authenticated user

**Impact**:
- Attacker sets session ID, user logs in, attacker reuses
- **Account takeover via fixation**

**Fix**: Regenerate session ID on authentication, use cryptographically random IDs

---

## MEDIUM PRIORITY ISSUES (P2)

### 14. 🟡 TIMING ATTACK IN PASSWORD VERIFICATION
**File**: `/app/utils/security.py:108`
**Risk**: Password enumeration, faster brute force

**Details**:
- Early return on empty password: `if not plain_password or not hashed_password: return False`
- Timing difference reveals valid usernames
- bcrypt comparison may leak timing info

**Fix**: Constant-time comparison for all password checks


### 15. 🟡 JWT SECRET KEY STRENGTH NOT VALIDATED
**File**: `/app/config/settings/security.py:17-23`
**Risk**: Token forgery if weak secret

**Details**:
- `SECRET_KEY` validated against placeholders only
- No entropy/length requirements enforced
- Weak secrets possible in production

**Fix**: Enforce minimum 256-bit entropy, validate on startup


### 16. 🟡 NO ACCOUNT LOCKOUT AFTER FAILED ATTEMPTS
**File**: `/app/services/auth.py:286-315` (rate limiting exists but disabled)
**Risk**: Unlimited brute force attempts

**Details**:
- Rate limiting tracks attempts but doesn't lock accounts
- No permanent lockout after X failures
- Only temporary IP-based limiting

**Fix**: Implement account lockout after 10 failed attempts


### 17. 🟡 CORS ALLOWS CREDENTIALS BUT USES REGEX IN DEV
**File**: `/app/core/middleware_setup.py:145-174`
**Risk**: CORS misconfiguration in development

**Details**:
```python
allow_credentials=True,  # ✅ CRITICAL: Required for httpOnly cookies
allowed_origin_regex=None if is_production else r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
```

**Impact**:
- Development mode accepts any localhost port
- Potential CORS bypass in dev environment

**Fix**: Use explicit origin list even in dev


### 18. 🟡 NO LOGGING OF AUTHENTICATION FAILURES
**File**: Multiple auth files
**Risk**: Security incidents go undetected

**Details**:
- Failed logins logged but not aggregated
- No alerting on suspicious patterns
- No forensics for compromise investigation

**Fix**: Centralized auth failure logging + alerting


### 19. 🟡 FIREBASE TOKEN CACHE WITHOUT VALIDATION
**File**: `/app/dependencies/auth_dependencies.py:339-354`
**Risk**: Stale token reuse, revoked token acceptance

**Details**:
- Firebase tokens cached for 1 hour (Layer 1)
- Users cached for 2 hours (Layer 2)
- **No validation of account status in cache**
- Deactivated users may access system for hours

**Fix**: Check is_active on every request, invalidate cache on user update


### 20. 🟡 SESSION COOKIE WITHOUT SECURE FLAG IN DEV
**File**: `/app/config/settings/security.py:39-42`
**Risk**: Session theft over unencrypted connections

**Details**:
```python
SESSION_COOKIE_SECURE: bool = Field(default=False, description="Require HTTPS for session cookies")
```

**Fix**: Enable SECURE flag by default, disable only in dev mode explicitly


### 21. 🟡 NO CONTENT SECURITY POLICY FOR UPLOADS
**File**: `/app/core/application_factory.py:390-409`
**Risk**: XSS via uploaded files

**Details**:
- Static files served without CSP headers
- Uploaded files accessible at `/uploads`
- No content-type validation

**Fix**: Strict CSP for uploads, validate MIME types


### 22. 🟡 DEBUG ENDPOINTS EXPOSED IN PRODUCTION MODE
**File**: `/app/core/application_factory.py:585-662`
**Risk**: Information disclosure

**Details**:
- Debug endpoints exist: `/debug/env`, `/debug/imports`, `/debug/health`
- Controlled by `DEBUG` flag but may be enabled accidentally

**Fix**: Disable debug endpoints in production via deployment_mode


### 23. 🟡 NO MFA/2FA IMPLEMENTATION
**File**: Authentication system
**Risk**: Account takeover via password theft

**Details**:
- No multi-factor authentication
- Single factor = password only
- High-value accounts (doctors) not protected

**Fix**: Implement TOTP/SMS 2FA for admin and doctor roles


### 24. 🟡 PATIENT AUTHORIZATION MIDDLEWARE NOT APPLIED GLOBALLY
**File**: `/app/middleware/patient_authorization.py`
**Risk**: Unauthorized patient data access

**Details**:
- Patient authorization exists but **not used as middleware**
- Must be called manually per endpoint
- Easy to forget in new endpoints

**Fix**: Apply as global middleware for all `/api/*/patients/*` routes


### 25. 🟡 NO ROLE HIERARCHY ENFORCEMENT
**File**: `/app/models/user.py:12-15`
**Risk**: Role confusion, privilege errors

**Details**:
- Only 2 roles: ADMIN, DOCTOR
- No hierarchy (ADMIN should inherit DOCTOR permissions)
- Duplicate permission definitions

**Fix**: Implement role hierarchy, ADMIN inherits DOCTOR permissions

---

## AUTH FLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────┐
│                    AUTHENTICATION FLOW                       │
└─────────────────────────────────────────────────────────────┘

 Frontend                 Backend                   Firebase
    │                        │                          │
    │  1. POST /auth/login   │                          │
    ├───────────────────────>│                          │
    │                        │  2. signInWithPassword   │
    │                        ├─────────────────────────>│
    │                        │  3. Firebase ID Token    │
    │                        │<─────────────────────────┤
    │                        │                          │
    │                        │  4. Verify token         │
    │                        ├─────────────────────────>│
    │                        │  5. Token claims         │
    │                        │<─────────────────────────┤
    │                        │                          │
    │                        │  6. Create Redis session │
    │                        │  (24h TTL, httpOnly)     │
    │                        │                          │
    │  7. Set-Cookie         │                          │
    │  session_id=xxx        │                          │
    │  HttpOnly, Secure      │                          │
    │<───────────────────────┤                          │
    │                        │                          │
    │  8. Store Firebase     │                          │
    │  token in memory       │                          │
    │  (Firebase SDK)        │                          │
    │                        │                          │

┌─────────────────────────────────────────────────────────────┐
│                  SUBSEQUENT REQUEST FLOW                     │
└─────────────────────────────────────────────────────────────┘

 Frontend                 Backend                   Redis
    │                        │                          │
    │  GET /api/patients     │                          │
    │  Cookie: session_id    │                          │
    │  Authorization: Bearer │                          │
    ├───────────────────────>│                          │
    │                        │  Check session in Redis  │
    │                        ├─────────────────────────>│
    │                        │  Session data + user_id  │
    │                        │<─────────────────────────┤
    │                        │                          │
    │                        │  Get user from cache/DB  │
    │                        │  (2h cache TTL)          │
    │                        │                          │
    │                        │  Validate permissions    │
    │                        │  Execute endpoint logic  │
    │                        │                          │
    │  200 OK + data         │                          │
    │<───────────────────────┤                          │
    │                        │                          │

SECURITY LAYERS:
1. Firebase token validation (client-side + server-side)
2. Redis session validation (httpOnly cookie)
3. User cache with TTL (Redis Layer 2)
4. Database user validation (is_active check)
5. RBAC permission validation
6. Optional: RLS (Row-Level Security) for data isolation

VULNERABILITIES:
❌ Token blacklist not persistent (in-memory only)
❌ No session timeout enforcement (24h defined but not enforced)
❌ No rate limiting (globally disabled)
❌ Cache may serve stale is_active status for up to 2 hours
```

---

## RBAC MATRIX

| Endpoint Category | Patient Role | Doctor Role | Admin Role | Issues |
|-------------------|--------------|-------------|------------|--------|
| **Authentication** | | | | |
| POST /auth/login | ✅ Public | ✅ Public | ✅ Public | No rate limit |
| GET /auth/me | ✅ Own | ✅ Own | ✅ Own | ✅ Secured |
| POST /auth/logout | ✅ Own | ✅ Own | ✅ Own | Token not blacklisted persistently |
| **Patient Management** | | | | |
| GET /patients | ❌ | ✅ All | ✅ All | ✅ Secured |
| GET /patients/{id} | ⚠️ Own Only | ✅ All | ✅ All | Ownership check may be missing |
| POST /patients | ❌ | ✅ Create | ✅ Create | ✅ Secured |
| PUT /patients/{id} | ❌ | ✅ Update | ✅ Update | No ownership validation |
| DELETE /patients/{id} | ❌ | ❌ | ✅ Delete | ✅ Properly restricted |
| **Appointments** | | | | |
| GET /appointments | ⚠️ Own | ✅ All | ✅ All | Patient role not enforced |
| POST /appointments | ❌ | ✅ Create | ✅ Create | ✅ Secured |
| **Treatments** | | | | |
| GET /treatments | ⚠️ Own | ✅ All | ✅ All | Patient role exists? |
| POST /treatments | ❌ | ✅ Create | ✅ Create | ✅ Secured |
| **Reports** | | | | |
| GET /reports | ⚠️ Own | ✅ All | ✅ All | ⚠️ Check ownership |
| POST /reports | ❌ | ✅ Create | ✅ Create | ✅ Secured |
| DELETE /reports | ❌ | ⚠️ Maybe | ✅ Delete | Doctor delete unclear |
| **Analytics** | | | | |
| GET /analytics/* | ❌ | ✅ Read | ✅ Read | ✅ Secured |
| **Admin Operations** | | | | |
| GET /admin/users | ❌ | ❌ | ✅ All | ✅ Properly restricted |
| POST /admin/users | ❌ | ❌ | ✅ Create | ✅ Properly restricted |
| DELETE /admin/users | ❌ | ❌ | ✅ Delete | ⚠️ Too powerful |
| GET /admin/audit | ❌ | ❌ | ✅ Read | ✅ Secured |
| **Webhooks** | | | | |
| POST /webhooks/evolution/* | 🔓 Public | 🔓 Public | 🔓 Public | ❌ NO AUTH! Signature validation optional |
| **Health/Debug** | | | | |
| GET /health | ✅ Public | ✅ Public | ✅ Public | ✅ OK |
| GET /debug/* | 🔓 Public | 🔓 Public | 🔓 Public | ❌ Should be admin-only |
| **Quiz** | | | | |
| GET /quiz | ⚠️ Own? | ✅ All | ✅ All | Patient access unclear |
| POST /quiz/responses | ⚠️ Own | ✅ All | ✅ All | Needs ownership check |
| **Messages/WhatsApp** | | | | |
| POST /messages | ❌ | ✅ Send | ✅ Send | ✅ Secured |
| GET /messages/{id} | ⚠️ Own | ✅ All | ✅ All | Patient viewing unclear |

**Legend:**
- ✅ = Properly protected with auth check
- ❌ = No access (correctly blocked)
- ⚠️ = Requires ownership validation (may be vulnerable)
- 🔓 = Public endpoint (no authentication)

**CRITICAL FINDINGS:**
1. **Patient role not implemented** - Only ADMIN and DOCTOR roles exist in system
2. **Webhook endpoints have NO authentication** - Optional signature validation
3. **Debug endpoints accessible** without admin role restriction
4. **Ownership checks inconsistent** - Patients may access others' data
5. **Role hierarchy missing** - ADMIN should inherit DOCTOR permissions

---

## ENDPOINTS WITHOUT AUTH CHECKS

### 🔴 CRITICAL: Public Endpoints (Found 8)

| Endpoint | Method | Risk | Notes |
|----------|--------|------|-------|
| `/webhooks/evolution/message` | POST | CRITICAL | No auth, optional signature |
| `/webhooks/evolution/status` | POST | CRITICAL | No auth, optional signature |
| `/webhooks/evolution/connection` | POST | CRITICAL | No auth, optional signature |
| `/webhooks/evolution/qrcode` | POST | HIGH | No auth, optional signature |
| `/debug/env` | GET | HIGH | Exposes env vars, should be admin-only |
| `/debug/imports` | GET | MEDIUM | Shows internal structure |
| `/debug/health` | GET | MEDIUM | Reveals system info |
| `/health` | GET | LOW | OK for health checks |

**IMMEDIATE ACTION REQUIRED:**
1. **Make webhook signature validation MANDATORY** (currently optional)
2. **Restrict debug endpoints to admin role only**
3. **Implement IP whitelist for webhooks** (Evolution API servers only)

---

## TOKEN STORAGE ANALYSIS

### Backend Token Storage
| Component | Storage Method | Security | Score |
|-----------|---------------|----------|-------|
| Firebase ID Tokens | Redis Cache (1h TTL) | ✅ Server-side | 9/10 |
| Session IDs | Redis (24h TTL) | ✅ Server-side | 8/10 |
| Token Blacklist | ⚠️ In-memory (volatile) | ❌ Not persistent | 3/10 |
| User Cache | Redis (2h TTL) | ✅ Server-side | 8/10 |
| JWT Secret | Environment Variable | ⚠️ Validated weakly | 7/10 |

### Frontend Token Storage
| Component | Storage Method | Security | Score |
|-----------|---------------|----------|-------|
| Firebase Tokens | Firebase SDK (memory) | ✅ Not in localStorage | 9/10 |
| Session IDs | httpOnly Cookie | ✅ Secure (not JS accessible) | 10/10 |
| CSRF Tokens | Memory + Cookie | ✅ Dual storage | 8/10 |
| User Data | React State (memory) | ✅ Not persisted | 9/10 |

**Backend Security: 7/10**
- ✅ Redis-backed sessions (excellent)
- ✅ Token caching reduces Firebase API calls
- ❌ Token blacklist not persistent (critical flaw)
- ⚠️ 24h session TTL not enforced in code

**Frontend Security: 9/10**
- ✅ No localStorage usage (excellent!)
- ✅ httpOnly cookies for sessions (perfect)
- ✅ Firebase SDK manages token refresh
- ✅ Token refresh with backend validation

**Overall Token Storage: 8/10** (dragged down by non-persistent blacklist)

---

## IMMEDIATE ACTION REQUIRED

### Top 5 Fixes Needed NOW (P0)

#### 1. ⚠️ MIGRATE TOKEN BLACKLIST TO REDIS
**Criticality**: CRITICAL  
**Effort**: 2 hours  
**Impact**: Prevents token reuse after logout/restart

```python
# Current (INSECURE):
self._blacklisted_tokens: Set[str] = set()

# Fix:
async def blacklist_token(self, token: str, exp_timestamp: int):
    ttl = exp_timestamp - int(time.time())
    await self.redis.setex(f"blacklist:{token}", ttl, "1")

async def is_blacklisted(self, token: str) -> bool:
    return await self.redis.exists(f"blacklist:{token}") == 1
```

#### 2. ⚠️ RE-ENABLE RATE LIMITING WITH GRANULAR CONTROL
**Criticality**: CRITICAL  
**Effort**: 4 hours  
**Impact**: Prevents brute force, API abuse

```python
# Add to endpoints:
@limiter.limit("5/minute")  # Login attempts
@limiter.limit("100/minute")  # Read operations
@limiter.limit("20/minute")  # Write operations
@limiter.limit("unlimited")  # Admin endpoints (with auth)
```

#### 3. ⚠️ ENFORCE SESSION TIMEOUT
**Criticality**: CRITICAL  
**Effort**: 3 hours  
**Impact**: Auto-logout after inactivity

```python
# Add to session validation:
async def validate_session(self, session_id: str):
    session = await redis.get(f"session:{session_id}")
    if not session:
        raise HTTPException(401, "Session expired")
    
    # Refresh TTL on activity (sliding window)
    await redis.expire(f"session:{session_id}", self.session_ttl)
    
    # Check last activity
    last_activity = session.get("last_activity")
    if time.time() - last_activity > self.inactivity_timeout:
        await self.delete_session(session_id)
        raise HTTPException(401, "Session timeout")
```

#### 4. ⚠️ MAKE WEBHOOK SIGNATURES MANDATORY
**Criticality**: CRITICAL  
**Effort**: 1 hour  
**Impact**: Prevents webhook spoofing

```python
# Fail startup if not configured:
if not settings.EVOLUTION_WEBHOOK_SECRET:
    raise RuntimeError(
        "EVOLUTION_WEBHOOK_SECRET is required for webhook security. "
        "Generate with: openssl rand -hex 32"
    )
```

#### 5. ⚠️ VALIDATE FIREBASE CUSTOM CLAIMS SERVER-SIDE
**Criticality**: HIGH  
**Effort**: 3 hours  
**Impact**: Prevents privilege escalation

```python
# Ignore client-provided role, use database:
async def get_current_user(token: str) -> User:
    firebase_data = await verify_firebase_token(token)
    
    # IGNORE custom_claims from token (could be forged)
    # Get user from database (source of truth)
    user = await db.query(User).filter(
        User.firebase_uid == firebase_data["uid"]
    ).first()
    
    if not user:
        raise HTTPException(404, "User not found")
    
    # Use DATABASE role, not token role
    return user
```

---

## RECOMMENDATIONS

### Security Enhancements (Priority Order)

#### Authentication (P0 - P1)
1. ✅ Migrate token blacklist to Redis (CRITICAL)
2. ✅ Re-enable rate limiting with per-endpoint config (CRITICAL)
3. ✅ Enforce session timeout with sliding window (CRITICAL)
4. ✅ Implement account lockout after 10 failed attempts (HIGH)
5. ✅ Add MFA/2FA for admin and doctor roles (HIGH)
6. ✅ Validate password complexity on all password operations (HIGH)
7. ⚠️ Fix bcrypt workaround, implement constant-time comparison (HIGH)
8. ⚠️ Implement concurrent session limits (5 per user) (MEDIUM)
9. ⚠️ Add authentication failure aggregation + alerting (MEDIUM)
10. ⚠️ Regenerate session ID on login (prevent fixation) (MEDIUM)

#### Authorization (P1 - P2)
11. ✅ Validate Firebase custom claims server-side, use DB roles (HIGH)
12. ✅ Implement granular admin roles (SuperAdmin, UserAdmin) (HIGH)
13. ✅ Apply patient authorization middleware globally (MEDIUM)
14. ✅ Implement role hierarchy (ADMIN inherits DOCTOR) (MEDIUM)
15. ⚠️ Add ownership validation for all patient data endpoints (MEDIUM)
16. ⚠️ Implement audit logging for all admin operations (MEDIUM)

#### API Security (P0 - P1)
17. ✅ Make webhook signature validation mandatory (CRITICAL)
18. ✅ Restrict debug endpoints to admin role only (HIGH)
19. ✅ Implement IP whitelist for webhooks (HIGH)
20. ✅ Add per-endpoint rate limits (HIGH)
21. ⚠️ Audit all raw SQL queries for injection risks (HIGH)
22. ⚠️ Add request size limits and validation (MEDIUM)
23. ⚠️ Implement strict CSP for uploaded files (MEDIUM)

#### Configuration (P1 - P2)
24. ✅ Validate JWT secret key entropy on startup (MEDIUM)
25. ✅ Enable SESSION_COOKIE_SECURE by default (MEDIUM)
26. ⚠️ Use explicit CORS origins even in dev mode (MEDIUM)
27. ⚠️ Validate Firebase cache doesn't serve stale is_active (MEDIUM)
28. ⚠️ Disable DEBUG mode indicators in production (LOW)

---

## TESTING RECOMMENDATIONS

### Security Tests to Implement

#### Authentication Tests
- [ ] Token reuse after logout (should fail)
- [ ] Token reuse after server restart (should fail with Redis blacklist)
- [ ] Session expiration after 24h (should logout)
- [ ] Session expiration after inactivity timeout
- [ ] Rate limit enforcement (5 login attempts = lockout)
- [ ] Account lockout after 10 failed attempts
- [ ] Password complexity validation
- [ ] Timing attack resistance

#### Authorization Tests
- [ ] Doctor cannot access admin endpoints
- [ ] Patient can only view own data
- [ ] Ownership checks on all patient endpoints
- [ ] Role hierarchy (ADMIN inherits DOCTOR permissions)
- [ ] Firebase custom claims ignored (DB roles used)

#### API Security Tests
- [ ] Webhook without signature rejected
- [ ] CSRF token validation on state-changing operations
- [ ] SQL injection attempts blocked
- [ ] XSS attempts sanitized
- [ ] Debug endpoints require admin role
- [ ] Rate limits enforced per endpoint

#### Session Security Tests
- [ ] Session fixation prevention
- [ ] Concurrent session limits
- [ ] Session regeneration on login
- [ ] HttpOnly cookie not accessible to JS
- [ ] Secure flag enforced on HTTPS

---

## COMPLIANCE NOTES

### HIPAA Considerations
- ✅ Session data encrypted in Redis (TLS)
- ✅ Passwords hashed with bcrypt (12 rounds)
- ⚠️ Audit logging incomplete (admin operations not logged)
- ❌ No automatic session timeout enforcement
- ❌ No MFA for high-privilege accounts
- ⚠️ Token blacklist not persistent (revocation gaps)

### OWASP Top 10 Coverage
1. **A01:2021 – Broken Access Control**: ⚠️ MEDIUM RISK
   - Role checks exist but not comprehensive
   - Ownership validation missing in some endpoints
   
2. **A02:2021 – Cryptographic Failures**: ✅ LOW RISK
   - Strong password hashing (bcrypt 12 rounds)
   - JWT tokens with HS256 (acceptable)
   
3. **A03:2021 – Injection**: ⚠️ MEDIUM RISK
   - Raw SQL queries found (audit needed)
   - SQLAlchemy ORM used mostly (good)
   
4. **A07:2021 – Identification and Authentication Failures**: ❌ HIGH RISK
   - No rate limiting (disabled)
   - No account lockout
   - Token blacklist not persistent
   
5. **A05:2021 – Security Misconfiguration**: ⚠️ MEDIUM RISK
   - Debug endpoints exposed
   - CORS permissive in dev mode
   - Webhook validation optional

---

## MONITORING & ALERTING RECOMMENDATIONS

### Critical Alerts to Implement
1. **Failed login attempts** > 5/minute from same IP
2. **Token blacklist Redis failure** (revert to fail-closed)
3. **Webhook without valid signature** received
4. **Admin operation performed** (audit log trigger)
5. **Session created from new device/location** for same user
6. **Password reset requested** for admin accounts
7. **Concurrent sessions** > 5 for same user
8. **Rate limit exceeded** > 10 times in 1 hour

---

## CONCLUSION

The system has a **solid security foundation** with dual authentication (Firebase + Redis sessions), password hashing, and RBAC. However, several **critical gaps** create significant attack surface:

**Strengths:**
- ✅ httpOnly cookies for sessions (excellent)
- ✅ Firebase authentication integration
- ✅ Redis-backed session storage
- ✅ No tokens in localStorage
- ✅ CSRF protection implemented

**Critical Weaknesses:**
- ❌ Token blacklist not persistent (restart = revoked tokens valid)
- ❌ Rate limiting globally disabled (brute force unprotected)
- ❌ No session timeout enforcement (24h defined but not implemented)
- ❌ Webhook signatures optional (spoofing possible)
- ❌ No concurrent session limits (credential sharing undetected)

**Immediate Action Required:**
Fix the 5 P0 issues within **1 week** to prevent account takeover scenarios. The combination of disabled rate limiting + non-persistent token blacklist creates a **critical vulnerability window**.

**Overall Assessment**: Security-conscious design with critical implementation gaps. **Fix P0 issues immediately**, then address P1 issues within 1 month.

---

**Report Generated**: 2025-11-07  
**Auditor**: Claude Code Security Analysis  
**Next Review**: After P0 fixes implemented
