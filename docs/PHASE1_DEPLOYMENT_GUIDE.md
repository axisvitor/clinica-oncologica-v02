# 🚀 PHASE 1 DEPLOYMENT GUIDE - Emergency Fixes

**Date:** 2025-11-07
**Priority:** P0 - CRITICAL
**Estimated Effort:** 40-48 hours
**Status:** In Progress

---

## 📋 CRITICAL ACTIONS REQUIRED

### 🔴 1. QUIZ SESSION SECRET (5 minutes) - MUST DO BEFORE DEPLOYMENT

**Status:** ⚠️ **ACTION REQUIRED**

**Issue:** Default HMAC secret allows session forgery (CVSS 9.1)

**Steps:**

```bash
# 1. Generate secure secret
cd quiz-mensal-interface
openssl rand -base64 32

# 2. Add to .env.local (NEVER commit this file)
echo "QUIZ_SESSION_SECRET=<generated-secret-here>" >> .env.local

# 3. For production deployment, set environment variable:
# Railway/Vercel/AWS: Add QUIZ_SESSION_SECRET to environment variables
# Docker: Add to docker-compose.yml secrets or .env file (git-ignored)

# 4. Verify the secret is set
grep QUIZ_SESSION_SECRET .env.local

# Example generated secret (DO NOT USE THIS - GENERATE YOUR OWN):
# QUIZ_SESSION_SECRET=D1+pnuekTfzK8fBx5SCe9hacutCcL5GPBM8x34Gss7o=
```

**Verification:**
```bash
# The app should fail to start if using default secret in production
# Check logs for: "⚠️  WARNING: Using default QUIZ_SESSION_SECRET"
```

---

## 🔧 AUTOMATED FIXES APPLIED

### ✅ 1.1 Quiz Session Configuration

**Files Modified:**
- `quiz-mensal-interface/.env.example` - Updated with security configuration

**Changes:**
- Added comprehensive environment variable documentation
- Added security warnings for QUIZ_SESSION_SECRET
- Configured session duration and cookie security settings

---

## 🛠️ MANUAL FIXES REQUIRED

### 1.2 Remove CSRF Workaround (2-4 hours) - HIGH PRIORITY

**File:** `backend-hormonia/app/middleware/csrf.py`
**Lines:** 262-274

**Current Code (REMOVE):**
```python
# Lines 262-274 - REMOVE THIS WORKAROUND
if csrf_header and not csrf_cookie and "Missing Cookie" in str(e):
    # Cross-domain scenario: accept valid header token format
    if len(csrf_header) > 50 and '.' in csrf_header:
        return  # ⚠️ BYPASSES CSRF VALIDATION
```

**Replacement:**
```python
# Configure proper CORS + SameSite cookies instead
# In app/config/settings/security.py, ensure:
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True  # In production

# In app/middleware/cors.py, configure allowed origins:
ALLOWED_ORIGINS = [
    "https://your-frontend-domain.com",
    # Add other trusted origins
]
```

**Testing:**
```bash
# Test CSRF protection works
curl -X POST http://localhost:8000/api/v1/patients \
  -H "Content-Type: application/json" \
  -d '{"name": "Test"}' \
  # Should return 403 Forbidden (CSRF token missing)

# With valid CSRF token
curl -X POST http://localhost:8000/api/v1/patients \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: <valid-token>" \
  -d '{"name": "Test"}' \
  # Should succeed
```

---

### 1.3 Fix SQL Injection (6-8 hours) - HIGH PRIORITY

**File:** `backend-hormonia/app/repositories/flow_template_version.py`
**Lines:** 50, 74, 122, 140, 184, 202, 234

**Issue:** Raw SQL with `text()` without proper parameterization

**Example Fix:**

**BEFORE (Vulnerable):**
```python
# Line 74 - VULNERABLE
result = self.db.execute(text("""
    SELECT id, version, kind_id, ...
    FROM flow_template_versions
    WHERE is_current = true
"""))
```

**AFTER (Secure):**
```python
from sqlalchemy.orm import selectinload

# Use ORM queries instead
result = self.db.query(FlowTemplateVersion).filter(
    FlowTemplateVersion.is_current == True
).options(
    selectinload(FlowTemplateVersion.kind),
    selectinload(FlowTemplateVersion.template)
).all()
```

**For parameterized updates (Line 184):**

**BEFORE:**
```python
# Line 184 - VULNERABLE TO KEY INJECTION
self.db.execute(text(query), updates)
```

**AFTER:**
```python
# Whitelist allowed fields
ALLOWED_UPDATE_FIELDS = {'version', 'kind_id', 'template_data', 'is_current'}

# Validate update keys
invalid_keys = set(updates.keys()) - ALLOWED_UPDATE_FIELDS
if invalid_keys:
    raise ValueError(f"Invalid update fields: {invalid_keys}")

# Use ORM update
self.db.query(FlowTemplateVersion).filter(
    FlowTemplateVersion.id == version_id
).update(updates)
```

**Testing:**
```python
# tests/repositories/test_flow_template_version.py
def test_no_sql_injection():
    """Ensure SQL injection is prevented"""
    malicious_input = "'; DROP TABLE flow_template_versions; --"

    # Should raise error or escape properly
    with pytest.raises(ValueError):
        repo.update(version_id=1, updates={"malicious_field": malicious_input})
```

**Files to Fix:**
1. `app/repositories/flow_template_version.py` (7 instances)
2. `app/repositories/flow_kind.py` (4 instances)

---

### 1.4 Add Input Sanitization (2 hours)

**Quiz Interface:** Add DOMPurify

```bash
cd quiz-mensal-interface
npm install isomorphic-dompurify
```

**File:** `quiz-mensal-interface/components/quiz/QuestionRenderer/TextQuestion.tsx`

**Add sanitization:**
```typescript
import DOMPurify from 'isomorphic-dompurify'

// Sanitize user input before storing
const sanitizeInput = (input: string): string => {
  return DOMPurify.sanitize(input, {
    ALLOWED_TAGS: [],  // No HTML allowed
    ALLOWED_ATTR: []
  })
}

// In component
const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
  const sanitized = sanitizeInput(e.target.value)
  setAnswer(sanitized)
}
```

**Add max length validation:**
```typescript
const MAX_TEXT_LENGTH = 5000

<Textarea
  maxLength={MAX_TEXT_LENGTH}
  value={answer}
  onChange={handleTextChange}
/>
```

---

### 1.5 Fix Encryption Salt (2-4 hours)

**File:** `backend-hormonia/app/services/phi_encryption_service.py`
**Line:** 46

**BEFORE:**
```python
salt = b'hormonia_phi_salt_2025'  # ⚠️ Hard-coded
```

**AFTER:**
```python
import os
from app.config.settings import settings

# Generate unique salt per deployment
ENCRYPTION_SALT = os.environ.get('PHI_ENCRYPTION_SALT')
if not ENCRYPTION_SALT:
    raise ValueError(
        "PHI_ENCRYPTION_SALT environment variable not set. "
        "Generate with: openssl rand -hex 16"
    )

salt = ENCRYPTION_SALT.encode()
```

**Environment Setup:**
```bash
# Generate unique salt
openssl rand -hex 16

# Add to .env (NEVER commit)
PHI_ENCRYPTION_SALT=<generated-salt>
```

**Migration Required:**
```python
# If existing data encrypted with old salt, need migration script
# backend-hormonia/scripts/migrate_phi_encryption_salt.py
```

---

### 2.1 Install TypeScript Types (5 minutes)

```bash
cd frontend-hormonia
npm install @types/react@^19.2.0 @types/react-dom@^19.2.0 --save-dev
npm run typecheck  # Verify compilation works
```

---

### 2.2-2.3 Remove @ts-nocheck (4-6 hours each)

**Files:**
1. `frontend-hormonia/src/lib/auth-context-helpers.ts` (443 lines)
2. `frontend-hormonia/src/lib/api-client-wrapper.ts` (495 lines)

**Steps for each file:**

1. **Remove `@ts-nocheck` directive**
2. **Fix type errors progressively:**

```typescript
// BEFORE
// @ts-nocheck
type User = any  // ❌

// AFTER
import { User as FirebaseUser } from 'firebase/auth'

interface User {
  uid: string
  email: string | null
  displayName: string | null
  photoURL: string | null
  // ... other Firebase User properties
}
```

3. **Replace `@ts-expect-error` with proper types**
4. **Test thoroughly** - auth is critical!

---

### 3.3 Re-enable Rate Limiting (4-6 hours)

**File:** `backend-hormonia/app/core/middleware_setup.py`
**Lines:** 128-130

**BEFORE:**
```python
# Rate limiting middleware DISABLED per user request
logger.info("⚠️  Rate limiting middleware DISABLED")
```

**AFTER:**
```python
from app.middleware.distributed_rate_limiter import setup_rate_limiting

# Re-enable with tiered limits
setup_rate_limiting(
    app,
    limits={
        "default": "100/minute",
        "auth": "10/minute",
        "api": "60/minute"
    },
    whitelist_ips=[
        "127.0.0.1",  # localhost
        # Add admin IPs if needed
    ]
)
```

**Testing:**
```bash
# Test rate limiting works
for i in {1..101}; do
  curl http://localhost:8000/api/v1/patients
done
# Last request should return 429 Too Many Requests
```

---

### 3.4 Fix Webhook Validation (2-4 hours)

**File:** `backend-hormonia/app/services/whatsapp_unified.py`
**Lines:** 518-526

**BEFORE:**
```python
def _validate_webhook_signature(self, webhook_data: Dict[str, Any]) -> bool:
    # TODO: Implement actual signature validation
    return True  # ⚠️ ALWAYS RETURNS TRUE!
```

**AFTER:**
```python
import hmac
import hashlib
from app.config.settings import settings

def _validate_webhook_signature(
    self,
    webhook_data: Dict[str, Any],
    received_signature: str
) -> bool:
    """Validate webhook signature using HMAC-SHA256"""

    if not settings.EVOLUTION_WEBHOOK_SECRET:
        logger.error("EVOLUTION_WEBHOOK_SECRET not configured")
        return False

    # Create signature
    webhook_str = json.dumps(webhook_data, sort_keys=True)
    expected_signature = hmac.new(
        key=settings.EVOLUTION_WEBHOOK_SECRET.encode(),
        msg=webhook_str.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()

    # Timing-safe comparison
    return hmac.compare_digest(expected_signature, received_signature)
```

**Configuration:**
```bash
# .env
EVOLUTION_WEBHOOK_SECRET=<your-evolution-api-secret>
```

---

## 📦 AUTOMATED TASKS (Done by Scripts)

### 3.1 Remove 209 Legacy Files

**Script:** Will be created to identify and remove legacy files

**Pattern Detection:**
- Files ending with `_ORIGINAL_BACKUP.py`
- Files ending with `_old.py`
- Files ending with `_backup.py`
- Files ending with `.backup`

---

### 3.2 Add Code Quality Rules

**Backend:** `.pylintrc` or `pyproject.toml`
```toml
[tool.pylint.format]
max-line-length = 100
max-file-lines = 500

[tool.pylint.design]
max-args = 7
max-locals = 15
max-returns = 6
max-branches = 12
```

**Frontend:** `eslint.config.js`
```javascript
rules: {
  'max-lines': ['warn', { max: 300, skipBlankLines: true }],
  'max-lines-per-function': ['warn', 50],
  'complexity': ['warn', 10]
}
```

---

## ✅ VERIFICATION CHECKLIST

After completing all fixes:

- [ ] QUIZ_SESSION_SECRET set in production environment
- [ ] CSRF workaround removed and tested
- [ ] SQL injection fixed in all repositories
- [ ] DOMPurify integrated and tested
- [ ] PHI encryption salt unique per deployment
- [ ] TypeScript compiles without errors
- [ ] @ts-nocheck removed from auth files
- [ ] Rate limiting re-enabled and tested
- [ ] Webhook signature validation working
- [ ] Legacy files removed (209 files)
- [ ] Code quality rules enforced
- [ ] All tests passing
- [ ] Security scan clean (no critical vulnerabilities)

---

## 🧪 TESTING AFTER PHASE 1

```bash
# Backend
cd backend-hormonia
pytest tests/ --cov=app --cov-report=html
pylint app/ --rcfile=.pylintrc

# Frontend
cd frontend-hormonia
npm run typecheck
npm run lint
npm run test
npm run test:e2e

# Quiz Interface
cd quiz-mensal-interface
npm run typecheck
npm run lint
npm run test
```

---

## 🚀 DEPLOYMENT STEPS

1. **Set all environment variables** (QUIZ_SESSION_SECRET, PHI_ENCRYPTION_SALT, etc.)
2. **Run database migrations** if needed
3. **Deploy backend** with new fixes
4. **Deploy frontend** with TypeScript fixes
5. **Deploy quiz interface** with session secret
6. **Monitor logs** for any issues
7. **Run smoke tests** on production

---

## 📊 SUCCESS METRICS

After Phase 1:

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| **Critical Vulnerabilities** | 3 | 0 | ✅ 0 |
| **TypeScript Errors** | Many | 0 | ✅ 0 |
| **@ts-nocheck Files** | 2 | 0 | ✅ 0 |
| **Legacy Files** | 209 | 0 | ✅ 0 |
| **Security Score** | 7.5/10 | 8.5/10 | ✅ >8.0 |

---

## 🆘 TROUBLESHOOTING

### Issue: CSRF token validation failing

**Solution:** Check CORS configuration and cookie SameSite settings

### Issue: TypeScript errors after removing @ts-nocheck

**Solution:** Fix types incrementally, use proper Firebase types

### Issue: Rate limiting blocking legitimate requests

**Solution:** Adjust limits or whitelist specific IPs

---

**Document Version:** 1.0
**Last Updated:** 2025-11-07
**Next Phase:** Phase 2 - High Priority Improvements (Weeks 2-3)
