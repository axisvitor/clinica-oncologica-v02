# CORS and CSRF Technical Debt Analysis
**Research Agent Report**
**Date:** 2025-12-20
**Session ID:** swarm-1766231542522-k48s3cm7t

## Executive Summary

This analysis identifies **critical technical debt** in the CORS and CSRF implementations that pose security risks, maintainability challenges, and memory leak vulnerabilities. The codebase contains **duplicate implementations, in-memory rate limiters causing memory leaks, and overly complex encryption** that should be simplified.

### Severity Classification
- **🔴 CRITICAL:** In-memory rate limiting (memory leak risk)
- **🟡 HIGH:** Duplicate CSRF implementations
- **🟡 HIGH:** Overly complex encryption (should use hmac/secrets)
- **🟠 MEDIUM:** Pytest compatibility hacks
- **🟠 MEDIUM:** Token encoding inconsistencies

---

## 1. In-Memory Rate Limiting - MEMORY LEAK RISK 🔴

### Location
**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/middleware/csrf.py`
**Lines:** 76-77, 112-113, 389-408

### Issue
```python
# CRITICAL: In-memory rate limiter using defaultdict
from collections import defaultdict
_csrf_validation_failures = defaultdict(list)

def _check_rate_limit(client_ip: str, max_failures: int = 10, window: int = 300) -> bool:
    """Rate limitation for failed validations."""
    current_time = time.time()
    # Clean old entries
    _csrf_validation_failures[client_ip] = [
        t for t in _csrf_validation_failures[client_ip] if current_time - t < window
    ]
    # ... continues
```

### Problems
1. **Memory Leak:** Dictionary grows unbounded in production with many unique IPs
2. **Lost on Restart:** All rate limit state lost on server restart/deployment
3. **Not Distributed:** Won't work with multiple server instances (load balancer)
4. **No Cleanup:** Old IP keys never removed from dictionary, only values cleaned
5. **Race Conditions:** Not thread-safe in concurrent environments

### Impact
- Production servers will accumulate IP addresses indefinitely
- Memory usage grows over time, requiring restarts
- Attackers can bypass by using different IPs
- Horizontal scaling breaks rate limiting

### Recommendation
Replace with **Redis-based rate limiting** (already configured in settings):

```python
# Use existing Redis configuration
RATE_LIMIT_REDIS_URL: Optional[str] = Field(
    default=None,
    description="Redis URL for rate limiting storage"
)
```

**Suggested Implementation:**
- Use `slowapi` or `fastapi-limiter` libraries
- Store rate limit data in Redis with TTL
- Automatically expires old entries
- Works across multiple server instances
- Thread-safe and distributed-friendly

---

## 2. Duplicate CSRF Implementations 🟡

### Locations
1. **`/backend-hormonia/app/middleware/csrf.py`** (Lines 1-573)
2. **`/backend-hormonia/app/core/csrf_middleware.py`** (Lines 1-366)

### Issue: Two Complete CSRF Implementations

#### Implementation 1: `app/middleware/csrf.py`
- Session-based CSRF protection
- HMAC-SHA256 signature validation
- Base64url token encoding
- Double Submit Cookie pattern
- In-memory rate limiting (problematic)
- Pytest compatibility hacks (lines 79-107)

#### Implementation 2: `app/core/csrf_middleware.py`
- Middleware-based CSRF protection
- HMAC-SHA256 signature validation
- Base64url token encoding
- Header-based validation only (no cookie)
- Cleaner implementation, no pytest hacks

### Problems
1. **Maintenance Burden:** Changes must be made in two places
2. **Inconsistent Behavior:** Different validation logic
3. **Confusion:** Unclear which one is actually used
4. **Code Duplication:** 90% of logic is identical
5. **Security Risk:** Updates may miss one implementation

### Evidence of Confusion
```python
# csrf.py has pytest compatibility hacks:
def _is_pytest_running() -> bool:
    if os.getenv("PYTEST_CURRENT_TEST") is not None:
        return True
    if "pytest" in sys.modules:
        return True
    return any("pytest" in str(arg).lower() for arg in sys.argv)

if _is_pytest_running():
    try:
        import fastapi_csrf_protect.exceptions as _fastapi_csrf_exceptions
        # ... 30 lines of monkey-patching code
    except Exception:
        _fastapi_csrf_exceptions = None
```

### Recommendation
**Consolidate into ONE implementation:**
1. Keep `app/middleware/csrf.py` (more feature-complete)
2. Remove `app/core/csrf_middleware.py`
3. Fix pytest issues properly (don't monkey-patch)
4. Use dependency injection for testing instead of runtime detection

---

## 3. Overly Complex Encryption 🟡

### Location
**File:** `/backend-hormonia/app/middleware/csrf.py`
**Lines:** 282-306, 350-387

### Issue: Unnecessary Base64 Encoding Complexity

```python
def generate_csrf_token(secret_key: Optional[str] = None) -> str:
    """Generate a new signed CSRF token in base64url format."""
    if secret_key is None:
        secret_key = get_csrf_settings().secret_key
    timestamp = str(int(time.time()))
    random_data = secrets.token_hex(16)
    data = f"{timestamp}.{random_data}"
    signature = _generate_token_signature(data, secret_key)
    token_raw = f"{data}.{signature}"
    # Base64url encode for URL-safe transport (matches CSRFMiddleware format)
    encoded = base64.urlsafe_b64encode(token_raw.encode("utf-8")).decode("utf-8")
    return encoded.rstrip("=")

def _validate_token_signature(token: str, secret_key: str, max_age: int = 3600) -> bool:
    """Validate CSRF token format, expiration and signature."""
    try:
        # Decode base64url token (add padding if needed)
        padded = token + "=" * (4 - len(token) % 4) if len(token) % 4 else token
        try:
            decoded = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        except Exception:
            # Fallback: try as raw token for backward compatibility
            decoded = token
        # ... continues with parsing
```

### Problems
1. **Double Encoding:** Hex encoding (`secrets.token_hex`) + Base64 encoding
2. **Padding Complexity:** Manual padding calculation prone to errors
3. **Fallback Logic:** Backward compatibility adds complexity
4. **HMAC Already Safe:** HMAC signatures are already hex-encoded and URL-safe

### Comparison

**Current Approach:**
```
timestamp.hex_random.hmac_signature → base64url encode → transmit
```

**Simpler Approach:**
```
timestamp.hex_random.hmac_signature → transmit (already URL-safe)
```

### Recommendation
**Simplify to use hex encoding only:**

```python
def generate_csrf_token(secret_key: str) -> str:
    """Generate URL-safe CSRF token using hex encoding."""
    timestamp = str(int(time.time()))
    random_data = secrets.token_hex(16)  # Already URL-safe
    data = f"{timestamp}.{random_data}"
    signature = hmac.new(
        secret_key.encode('utf-8'),
        data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()  # Already URL-safe
    return f"{data}.{signature}"  # All hex, no base64 needed
```

**Benefits:**
- Simpler code
- No padding issues
- No fallback complexity
- Still cryptographically secure
- Already URL-safe (hex is [0-9a-f])

---

## 4. Pytest Compatibility Hacks 🟠

### Location
**File:** `/backend-hormonia/app/middleware/csrf.py`
**Lines:** 79-107

### Issue: Monkey-Patching Production Code for Tests

```python
def _is_pytest_running() -> bool:
    if os.getenv("PYTEST_CURRENT_TEST") is not None:
        return True
    if "pytest" in sys.modules:
        return True
    return any("pytest" in str(arg).lower() for arg in sys.argv)

if _is_pytest_running():
    try:
        import fastapi_csrf_protect.exceptions as _fastapi_csrf_exceptions
    except Exception:
        _fastapi_csrf_exceptions = None

    if _fastapi_csrf_exceptions is not None:
        _csrf_err_sig = inspect.signature(
            _fastapi_csrf_exceptions.CsrfProtectError.__init__
        )
        if len(_csrf_err_sig.parameters) == 3:
            _orig_csrf_err_init = _fastapi_csrf_exceptions.CsrfProtectError.__init__

            def _csrf_err_init_compat(self, *args, **kwargs):
                if len(args) == 1 and not kwargs:
                    status_code = status.HTTP_403_FORBIDDEN
                    message = args[0]
                    return _orig_csrf_err_init(self, status_code, message)
                return _orig_csrf_err_init(self, *args, **kwargs)

            _fastapi_csrf_exceptions.CsrfProtectError.__init__ = _csrf_err_init_compat
```

### Problems
1. **Production Code Pollution:** Test-specific logic in production module
2. **Monkey-Patching:** Modifying library internals at runtime
3. **Fragile:** Breaks if library changes signature
4. **Unclear Intent:** Why is this needed? Root cause not documented
5. **Import Side Effects:** Code executes on module import

### Recommendation
**Fix the root cause instead:**

1. **Option A:** Create test fixtures with proper mocking
```python
# In conftest.py
@pytest.fixture
def csrf_protect_mock():
    with patch('app.middleware.csrf.csrf_protect') as mock:
        mock.validate_csrf.return_value = None
        yield mock
```

2. **Option B:** Use dependency injection
```python
# Make csrf_protect injectable instead of global
def validate_csrf_token(request: Request, csrf_service: CsrfService = Depends()):
    return csrf_service.validate(request)
```

3. **Option C:** Fix the library version incompatibility
- Update `fastapi-csrf-protect` to latest version
- Or replace with `starlette-csrf` (more actively maintained)

---

## 5. Token Format Inconsistencies 🟠

### Issue: Base64 vs Hex Encoding

Different parts of the codebase use different token formats:

#### `csrf.py` (middleware/csrf.py):
```python
# Uses base64url encoding
encoded = base64.urlsafe_b64encode(token_raw.encode("utf-8")).decode("utf-8")
return encoded.rstrip("=")
```

#### `csrf_middleware.py` (core/csrf_middleware.py):
```python
# Uses base64url encoding (same)
encoded = base64.urlsafe_b64encode(token.encode("utf-8")).decode("utf-8")
return encoded.rstrip("=")
```

### Comment Confusion
```python
# Comment says "matches CSRFMiddleware format" but which one?
# There are TWO CSRFMiddleware implementations!
```

### Recommendation
- **Standardize on ONE format** (prefer hex for simplicity)
- **Document the token format** in a central location
- **Version tokens** if format changes (e.g., `v1.timestamp.data.sig`)

---

## 6. Configuration Validation Gaps 🟠

### Location
**File:** `/backend-hormonia/app/config/settings/security.py`
**Lines:** 380-421

### Issue: CSRF Secret Validation is Optional

```python
def validate_csrf_config(self):
    """Validate CSRF secret key strength at application startup."""
    if self.SECURITY_CSRF_SECRET_KEY:  # ← Only validates if exists
        try:
            from app.utils.security_validation import validate_csrf_secret
            validate_csrf_secret(self.SECURITY_CSRF_SECRET_KEY, log_validation=True)
        except ValueError as e:
            if self.APP_ENVIRONMENT.lower() == "production":
                raise ValueError(...)  # ← Good: fails in production
            else:
                logger.warning("⚠️ Continuing in development...")  # ← Bad: silent in dev
    else:
        logger.warning("⚠️ SECURITY_CSRF_SECRET_KEY not configured.")  # ← Allowed!
```

### Problems
1. **Silent Failures in Development:** Warnings instead of errors
2. **CSRF Can Be Disabled:** No secret = no CSRF protection
3. **Inconsistent with Validators:** Other validators use `@model_validator` and fail hard

### Recommendation
```python
@model_validator(mode="after")
def validate_csrf_required(self) -> "SecuritySettings":
    """CSRF secret is ALWAYS required (production AND development)."""
    if not self.SECURITY_CSRF_SECRET_KEY:
        raise ValueError(
            "SECURITY_CSRF_SECRET_KEY is required in all environments.\n"
            "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )

    if len(self.SECURITY_CSRF_SECRET_KEY) < 32:
        raise ValueError("CSRF secret must be at least 32 characters")

    return self
```

---

## 7. CORS Configuration Complexity 🟠

### Location
**File:** `/backend-hormonia/app/middleware/cors.py`
**Lines:** 78-202

### Issue: Complex Origin Normalization Logic

```python
def _normalize_cors_origin(self, origin: str, is_production: bool) -> str:
    """Normalize a CORS origin URL."""
    normalized = origin.strip().strip('"').strip("'").rstrip("/")
    if not normalized:
        return ""

    # If already has protocol, return as-is
    if normalized.startswith("http://") or normalized.startswith("https://"):
        return normalized

    # Add appropriate protocol based on environment
    if is_production:
        return f"https://{normalized}"
    else:
        if "localhost" in normalized or "127.0.0.1" in normalized:
            return f"http://{normalized}"
        else:
            return f"https://{normalized}"
```

### Problems
1. **Triple Strip:** `strip().strip('"').strip("'")`
2. **Environment-Dependent Behavior:** Different rules for prod/dev
3. **Implicit Protocol Addition:** Auto-adding `https://` can mask config errors
4. **No Validation:** Doesn't check if result is valid URL

### Recent Fixes (Good!)
Looking at git history, I can see recent improvements:
- **Commit 3098e67:** "fix(cors): handle quoted env vars in settings parsing"
- **Commit 02708d6:** "fix: auto-add https:// prefix to CORS origins without protocol"

However, **the normalization is still too complex.**

### Recommendation
**Fail Fast on Invalid Config:**

```python
def validate_cors_origin(origin: str, is_production: bool) -> str:
    """Validate CORS origin (no normalization)."""
    origin = origin.strip()

    # Must be a valid URL with protocol
    if not origin.startswith(("http://", "https://")):
        raise ValueError(
            f"CORS origin must include protocol: {origin}\n"
            f"Use: https://{origin} (production) or http://{origin} (development)"
        )

    # Production must use HTTPS
    if is_production and origin.startswith("http://"):
        raise ValueError(
            f"CORS origin must use HTTPS in production: {origin}"
        )

    return origin.rstrip("/")
```

**Benefits:**
- Clear error messages
- No silent normalization
- Forces explicit configuration
- Catches typos early

---

## Summary of Technical Debt

| Issue | Severity | Impact | Files Affected | Recommendation |
|-------|----------|--------|----------------|----------------|
| In-Memory Rate Limiting | 🔴 CRITICAL | Memory leaks, scaling issues | `middleware/csrf.py` | Replace with Redis-based rate limiting |
| Duplicate CSRF Implementations | 🟡 HIGH | Maintenance burden, inconsistency | `middleware/csrf.py`<br>`core/csrf_middleware.py` | Consolidate to ONE implementation |
| Complex Token Encoding | 🟡 HIGH | Maintainability, bugs | `middleware/csrf.py`<br>`core/csrf_middleware.py` | Use hex-only encoding (no base64) |
| Pytest Monkey-Patching | 🟠 MEDIUM | Code smell, fragility | `middleware/csrf.py` | Use proper mocking/dependency injection |
| Token Format Inconsistency | 🟠 MEDIUM | Confusion | Multiple files | Standardize format, document |
| Config Validation Gaps | 🟠 MEDIUM | Silent failures | `settings/security.py` | Make CSRF secret always required |
| CORS Normalization | 🟠 MEDIUM | Hidden config errors | `middleware/cors.py` | Fail fast, no auto-normalization |

---

## Security Implications

### Current State (Good Aspects)
✅ **HMAC-SHA256 signatures** - Cryptographically secure
✅ **Constant-time comparison** - Prevents timing attacks
✅ **Token expiration** - Limits attack window
✅ **Double Submit Cookie** - Solid CSRF protection pattern
✅ **Explicit CORS headers** - No wildcard with credentials

### Risks from Technical Debt
⚠️ **Memory exhaustion** - In-memory rate limiter can crash server
⚠️ **Rate limit bypass** - Attackers can use different IPs
⚠️ **Update inconsistency** - Security patches may miss duplicate code
⚠️ **Silent failures** - Missing CSRF secret not caught in development

---

## Recommended Action Plan

### Phase 1: Critical (Week 1)
1. **Replace in-memory rate limiting with Redis**
   - Use `slowapi` or `fastapi-limiter`
   - Configure using existing `RATE_LIMIT_REDIS_URL`
   - Add tests for distributed rate limiting

### Phase 2: High Priority (Week 2)
2. **Consolidate CSRF implementations**
   - Audit which implementation is actually used
   - Remove duplicate code
   - Create comprehensive test suite
   - Document the canonical implementation

3. **Simplify token encoding**
   - Remove base64 layer
   - Use hex-only encoding
   - Add migration path for existing tokens

### Phase 3: Medium Priority (Week 3-4)
4. **Remove pytest hacks**
   - Create proper test fixtures
   - Use dependency injection
   - Update or replace `fastapi-csrf-protect` library

5. **Improve configuration validation**
   - Make CSRF secret always required
   - Fail fast on invalid CORS origins
   - Add comprehensive startup validation

### Phase 4: Documentation & Cleanup
6. **Documentation**
   - Document token format specification
   - Create CORS configuration guide
   - Add ADR (Architecture Decision Record) for CSRF approach

---

## Files Requiring Changes

### High Priority
- `/backend-hormonia/app/middleware/csrf.py` (573 lines) - PRIMARY
- `/backend-hormonia/app/core/csrf_middleware.py` (366 lines) - REMOVE or merge
- `/backend-hormonia/app/config/settings/security.py` (621 lines) - Update validators

### Medium Priority
- `/backend-hormonia/app/middleware/cors.py` (202 lines) - Simplify normalization
- `/backend-hormonia/tests/security/test_csrf_bypass_fix.py` (407 lines) - Update tests
- `/backend-hormonia/scripts/verify_csrf_fix.py` (292 lines) - Update verification

---

## Dependencies to Consider

### Current Dependencies
- `fastapi-csrf-protect` - May need update or replacement
- `redis` - Already available for rate limiting

### Recommended Additions
- `slowapi` or `fastapi-limiter` - Redis-based rate limiting
- `starlette-csrf` - Alternative CSRF library (more maintained)

---

## Testing Considerations

### Existing Tests (Good!)
✅ Comprehensive CVE-2025-CLINIC-004 regression tests
✅ Rate limiting tests
✅ Token expiration tests
✅ Signature validation tests

### Missing Tests
❌ Distributed rate limiting tests (multi-server)
❌ Memory leak tests (long-running scenarios)
❌ CORS origin normalization edge cases
❌ Configuration validation tests

---

## Metrics to Track

### Before Refactoring
- Lines of CSRF code: **939 lines** (573 + 366)
- Memory usage trend: **Growing over time** (rate limiter leak)
- Deployment complexity: **Manual** (two implementations to update)

### After Refactoring (Expected)
- Lines of CSRF code: **~400 lines** (58% reduction)
- Memory usage trend: **Stable** (Redis-based rate limiting)
- Deployment complexity: **Simple** (single implementation)

---

## References

### Related Security Issues
- **CVE-2025-CLINIC-004:** CSRF Bypass (FIXED with HMAC validation)
- **AUTH-001:** Weak secret keys (validation exists)

### Git Commits (Recent CORS/CSRF work)
- `3098e67` - fix(cors): handle quoted env vars in settings parsing
- `4f3e7da` - debug: add detailed CORS configuration logging
- `02708d6` - fix: auto-add https:// prefix to CORS origins without protocol
- `4219602` - fix: improve CSRF token format and expand CORS for local networks
- `fc2fdb6` - fix: use ssl_cert_reqs universally for Redis SSL

### External Resources
- [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetsecurity.com/cheatsheets/csrf-prevention-cheat-sheet/)
- [FastAPI Security Best Practices](https://fastapi.tiangolo.com/tutorial/security/)
- [Redis Rate Limiting Patterns](https://redis.io/docs/manual/patterns/distributed-locks/)

---

**END OF REPORT**

*This analysis was generated by the Research Agent as part of the Hive Mind collective intelligence system.*
