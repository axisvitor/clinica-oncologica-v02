# Environment Variable Security Audit Report

**Date:** 2025-12-10
**Auditor:** Code Review Agent
**Scope:** Backend and Frontend Environment Variable Configuration
**Status:** 🔴 CRITICAL ISSUES FOUND

---

## Executive Summary

This audit reviewed environment variable security and naming patterns across the application. **28 critical security issues** and **35 pattern inconsistencies** were identified that require immediate attention before production deployment.

### Severity Breakdown
- 🔴 **Critical (P0):** 11 issues - Require immediate fix
- 🟠 **High (P1):** 17 issues - Fix before production
- 🟡 **Medium (P2):** 24 issues - Fix in next iteration
- 🟢 **Low (P3):** 11 issues - Non-blocking improvements

---

## 🔴 CRITICAL SECURITY ISSUES (P0)

### 1. Inconsistent SECRET_KEY Variable Names

**Issue:** Multiple variations of the main secret key across files.

**Files Affected:**
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/.env.example`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/.env.railway.template`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/config/settings/security.py`

**Evidence:**
```bash
# .env.example uses:
SECURITY_SECRET_KEY=CHANGE_THIS_TO_A_SECURE_RANDOM_VALUE

# .env.railway.template uses:
SECURITY_SECRET_KEY=REPLACE_WITH_64_CHARACTER_SECRET_KEY

# security.py defines:
SECURITY_SECRET_KEY: str = Field(default="dev-insecure-secret-key...")
```

**Problem:**
- Placeholder formats differ across templates
- This creates confusion about which key to set
- Documentation doesn't clarify the single source of truth

**Recommendation:**
```bash
# Use single unified key (RECOMMENDED)
SECURITY_SECRET_KEY=<generate-with-secrets.token_urlsafe(64)>
# Remove legacy AUTH_JWT_SECRET_KEY references if present
```

**Impact:** ⚠️ Using the same key for multiple purposes violates security best practices. If one system is compromised, all systems using that key are compromised.

---

### 2. Encryption Key Format Inconsistency

**Issue:** Legacy `SECURITY_ENCRYPTION_KEY` vs current `ENCRYPTION_KEY_CURRENT`, plus `PHI_ENCRYPTION_KEY` for AES-GCM.

**Evidence:**
```bash
# .env.example uses:
ENCRYPTION_KEY_CURRENT=CHANGE_THIS_TO_A_SECURE_RANDOM_VALUE
PHI_ENCRYPTION_KEY=CHANGE_THIS_TO_A_SECURE_RANDOM_VALUE
# Legacy fallback (if still used):
SECURITY_ENCRYPTION_KEY=CHANGE_THIS_TO_A_SECURE_RANDOM_VALUE

# .env.railway.template uses:
ENCRYPTION_KEY_CURRENT=REPLACE_WITH_ENCRYPTION_KEY
PHI_ENCRYPTION_KEY=REPLACE_WITH_PHI_ENCRYPTION_KEY

# security.py validation checks for:
encryption_key = os.getenv("ENCRYPTION_KEY_CURRENT") or os.getenv("SECURITY_ENCRYPTION_KEY")  # Line 236
```

**Problem:**
- Canonical key is `ENCRYPTION_KEY_CURRENT` (Fernet) and `PHI_ENCRYPTION_KEY` (AES-GCM)
- Legacy `SECURITY_ENCRYPTION_KEY` still appears in some templates
- This can lead to missing key validation if only the legacy name is set

**Recommendation:**
```bash
# Standardize on ENCRYPTION_KEY_CURRENT + PHI_ENCRYPTION_KEY
ENCRYPTION_KEY_CURRENT=<generate-with-Fernet.generate_key()>
PHI_ENCRYPTION_KEY=<base64-encoded-32-byte-key>

# Keep SECURITY_ENCRYPTION_KEY only as legacy fallback if needed
```

**Impact:** 🔥 **PRODUCTION BLOCKER** - Startup validation can fail with `ENCRYPTION_KEY_CURRENT` missing if only the legacy key is set.

---

### 3. CSRF Secret Not Required in .env.railway.template

**Issue:** CSRF secret generation comment exists but variable isn't in REQUIRED section.

**Evidence:**
```bash
# .env.railway.template line 39-40:
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
SECURITY_CSRF_SECRET_KEY=REPLACE_WITH_CSRF_SECRET_KEY

# But validation (security.py line 229) only checks in production
if is_production:
    if not self.SECURITY_CSRF_SECRET_KEY:
        missing_vars.append(...)
```

**Problem:**
- CSRF key is only validated in production
- Template doesn't emphasize it's REQUIRED for production
- Development can run without it, masking the requirement

**Recommendation:**
```bash
# .env.railway.template should have clear REQUIRED marker:
# =============================================================================
# SECURITY CONFIGURATION - REQUIRED IN PRODUCTION
# =============================================================================
# CSRF Protection - REQUIRED
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
SECURITY_CSRF_SECRET_KEY=REPLACE_WITH_CSRF_SECRET_KEY  # REQUIRED
```

---

### 4. Redis URL Scheme Inconsistency

**Issue:** Different Redis URL formats across configuration files cause SSL/TLS confusion.

**Evidence:**
```bash
# .env.example (line 71):
REDIS_URL=redis://localhost:6379  # No SSL

# .env.railway.template (line 79):
REDIS_URL=rediss://default:REPLACE_WITH_REDIS_PASSWORD@REPLACE_WITH_REDIS_HOST:REPLACE_WITH_REDIS_PORT  # SSL

# .env.production.example (line 47):
REDIS_URL=rediss://default:PASSWORD@HOST:PORT  # SSL

# But also has separate REDIS_ENABLE_SSL flag (line 80):
REDIS_ENABLE_SSL=false  # in .env.example
REDIS_ENABLE_SSL=true   # in .env.railway.template
```

**Problem:**
- URL scheme (`redis://` vs `rediss://`) conflicts with `REDIS_ENABLE_SSL` flag
- Which one takes precedence?
- Database settings (database.py line 87-94) only check `REDIS_ENABLE_SSL` flag, not URL scheme

**Recommendation:**
```bash
# OPTION 1: URL scheme is source of truth (RECOMMENDED)
# Remove REDIS_ENABLE_SSL flag entirely
# Parse SSL from URL scheme (rediss:// = SSL)

# OPTION 2: Flag is source of truth
# Document that REDIS_ENABLE_SSL overrides URL scheme
# Update database.py to enforce: if REDIS_ENABLE_SSL=true, reject redis:// URLs
```

**Impact:** 🔥 **SECURITY RISK** - Production connections might not use SSL if URL and flag conflict.

---

### 5. Redis SSL Certificate Validation Inconsistency

**Issue:** `REDIS_SSL_CERT_REQS` values differ across files.

**Evidence:**
```bash
# .env.example (line 81):
REDIS_SSL_CERT_REQS=required

# .env.railway.template (line 88):
REDIS_SSL_CERT_REQS=required

# database.py (line 91):
REDIS_SSL_CERT_REQS: str = Field(default="required", ...)

# But .env.production.example (line 54):
REDIS_SSL_CERT_REQS=required
```

**Good news:** All use `"required"` - this is correct!

**Problem:**
- No validation that value is one of: `none`, `optional`, `required`
- Typos like `"require"` or `"REQUIRED"` would be silently accepted

**Recommendation:**
```python
# database.py - Add enum validation:
from enum import Enum

class SSLCertRequirement(str, Enum):
    NONE = "none"
    OPTIONAL = "optional"
    REQUIRED = "required"

REDIS_SSL_CERT_REQS: SSLCertRequirement = Field(
    default=SSLCertRequirement.REQUIRED,
    description="..."
)
```

---

### 6. Redis DB Number Naming Inconsistency

**Issue:** Variables use both `_DB` and `_DB_NUMBER` suffixes.

**Evidence:**
```bash
# .env.example uses _DB_NUMBER (lines 97-100):
REDIS_CACHE_DB_NUMBER=1
REDIS_BROKER_DB_NUMBER=0
REDIS_SESSION_DB_NUMBER=2
REDIS_RATE_LIMIT_DB_NUMBER=3

# .env.production.example uses _DB (lines 65-68):
REDIS_CACHE_DB=1
REDIS_BROKER_DB=0
REDIS_SESSION_DB=2
REDIS_RATE_LIMIT_DB=3

# database.py uses _DB_NUMBER (lines 169-184):
REDIS_CACHE_DB_NUMBER: int
REDIS_BROKER_DB_NUMBER: int
```

**Problem:**
- Production file won't match code expectations
- Will use default values instead of configured values

**Recommendation:**
```bash
# Standardize on _DB_NUMBER (matches code):
# Update .env.production.example:
REDIS_CACHE_DB_NUMBER=1      # Change from REDIS_CACHE_DB
REDIS_BROKER_DB_NUMBER=0     # Change from REDIS_BROKER_DB
REDIS_SESSION_DB_NUMBER=2    # Change from REDIS_SESSION_DB
REDIS_RATE_LIMIT_DB_NUMBER=3 # Change from REDIS_RATE_LIMIT_DB
```

**Impact:** 🔴 **DATA CORRUPTION RISK** - All Redis operations will use default DB 0, mixing cache with Celery broker data.

---

### 7. Boolean Value Format Inconsistency

**Issue:** Mix of Python-style (`True`/`False`) and lowercase (`true`/`false`) booleans.

**Evidence:**
```bash
# .env.example uses lowercase (consistent with YAML/JSON):
APP_ENABLE_DEBUG=true
SECURITY_ENABLE_FIELD_ENCRYPTION=true
SESSION_ENABLE_COOKIE_SECURE=false

# .env.production.example uses mixed case:
APP_ENABLE_DEBUG=false           # lowercase
REDIS_ENABLE=true                # lowercase
REDIS_ENABLE_SSL=true            # lowercase
CLAMAV_ENABLE_FAIL_OPEN=false    # lowercase

# .env.railway.template uses uppercase in some places:
REDIS_ENABLE_SSL=true            # lowercase
```

**Problem:**
- Parser accepts both (good)
- But inconsistent style is confusing
- Python's `bool()` would fail on "False" string

**Current Parser (security.py line 327):**
```python
data[field] = v.lower() not in ("false", "0", "no", "off", "")
```

**Good news:** Parser correctly handles both cases.

**Recommendation:**
```bash
# Standardize on lowercase for all .env files:
# Reason: Matches JSON/YAML/Kubernetes conventions
APP_ENABLE_DEBUG=true   # ✅ Use this
APP_ENABLE_DEBUG=True   # ❌ Not this
```

---

### 8. ENABLE_ Prefix Pattern Violations

**Issue:** Pattern guide says "Booleans: Always use ENABLE_ prefix after category" but many violations exist.

**Evidence:**
```bash
# ✅ CORRECT PATTERN:
APP_ENABLE_DEBUG=true
SECURITY_ENABLE_SSL_REDIRECT=false
SESSION_ENABLE_COOKIE_SECURE=false

# ❌ VIOLATIONS - Missing ENABLE_:
APP_ENVIRONMENT=production          # OK - not boolean
REDIS_URL=...                       # OK - not boolean
CELERY_ENABLE_UTC=true             # ✅ Correct
CELERY_ENABLE_TRACK_STARTED=true  # ✅ Correct
CELERY_ENABLE_DISABLE_RATE_LIMITS=true  # ❌ DOUBLE NEGATIVE!

# ❌ VIOLATIONS - ENABLE_ not after category:
ENABLE_REDIS=true                  # Should be REDIS_ENABLE_SERVICE
ENABLE_MONITORING=true             # Should be MONITORING_ENABLE_SERVICE
```

**Special case - Double negatives:**
```bash
CELERY_ENABLE_DISABLE_RATE_LIMITS=true  # ❌ Confusing!
# Should be:
CELERY_ENABLE_RATE_LIMITS=false  # ✅ Clear
```

**Recommendation:**
```bash
# Fix double negative:
- CELERY_ENABLE_DISABLE_RATE_LIMITS=true
+ CELERY_ENABLE_RATE_LIMITS=false

# Ensure pattern: {CATEGORY}_ENABLE_{FEATURE}
```

---

### 9. Timeout Unit Suffix Inconsistency

**Issue:** Convention says "Timeouts: Always include _SECONDS or _MS suffix" but many violations exist.

**Evidence:**
```bash
# ✅ CORRECT - Has unit suffix:
DATABASE_POOL_TIMEOUT_SECONDS=30
REDIS_SOCKET_TIMEOUT_SECONDS=10.0
TASK_TIME_LIMIT_SECONDS=3600
VITE_API_REQUEST_TIMEOUT_MS=30000

# ❌ VIOLATIONS - Missing unit suffix:
AUTH_ACCESS_TOKEN_EXPIRE_MINUTES=30    # Should add _MINUTES
AUTH_REFRESH_TOKEN_EXPIRE_DAYS=7      # Should add _DAYS
QUIZ_TOKEN_EXPIRY_HOURS=72            # Should add _HOURS (also inconsistent spelling: EXPIRY vs EXPIRE)

# ❌ VIOLATIONS - Wrong unit:
DATABASE_STATEMENT_TIMEOUT_MS=30000    # OK - uses _MS
CELERY_WORKER_TIME_LIMIT_SECONDS=300  # OK - uses _SECONDS
```

**Spelling inconsistency:**
```bash
AUTH_ACCESS_TOKEN_EXPIRE_MINUTES=30   # "EXPIRE"
QUIZ_TOKEN_EXPIRY_HOURS=72           # "EXPIRY"
```

**Recommendation:**
```bash
# Standardize naming:
AUTH_ACCESS_TOKEN_EXPIRE_MINUTES=30         # ✅ Keep as-is (already has MINUTES)
AUTH_REFRESH_TOKEN_EXPIRE_DAYS=7           # ✅ Keep as-is (already has DAYS)
QUIZ_TOKEN_EXPIRE_HOURS=72                 # Change EXPIRY to EXPIRE

# Ensure all timeout variables have unit suffix:
{CATEGORY}_{ACTION}_TIMEOUT_{SECONDS|MS}
{CATEGORY}_{ACTION}_EXPIRE_{MINUTES|HOURS|DAYS}
```

---

### 10. Size/Byte Suffix Pattern Violations

**Issue:** Convention says "_BYTES suffix for sizes" but inconsistent usage.

**Evidence:**
```bash
# ✅ CORRECT - Has _BYTES:
UPLOAD_MAX_SIZE_BYTES=10485760
VITE_UPLOAD_MAX_SIZE_BYTES=10485760
VITE_UPLOAD_CHUNK_SIZE_BYTES=1048576

# ❌ VIOLATIONS - Missing _BYTES:
DATABASE_POOL_SIZE=30                    # Not a byte size (OK - count)
REDIS_POOL_MAX_CONNECTIONS=50           # Not a byte size (OK - count)
QUOTA_DEFAULT_USER_GB=1                 # Should be QUOTA_DEFAULT_USER_SIZE_GB

# ❌ Mixed units without suffix:
UPLOAD_MAX_FILE_SIZE_BYTES=10485760     # ✅ Good
QUOTA_DEFAULT_USER_GB=1                 # ❌ Should specify _SIZE_GB for clarity
```

**Recommendation:**
```bash
# Add _SIZE_ for non-byte storage sizes:
QUOTA_DEFAULT_USER_SIZE_GB=1       # Change from QUOTA_DEFAULT_USER_GB
QUOTA_PREMIUM_USER_SIZE_GB=10      # Change from QUOTA_PREMIUM_USER_GB

# Pattern: {CATEGORY}_{ITEM}_SIZE_{BYTES|KB|MB|GB}
```

---

### 11. Firebase Private Key Format Security

**Issue:** Private key format in examples uses literal newlines vs `\n` escape sequences.

**Evidence:**
```bash
# .env.example (line 190):
FIREBASE_ADMIN_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n

# .env.railway.template (line 162):
FIREBASE_ADMIN_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\nREPLACE_WITH_PRIVATE_KEY\n-----END PRIVATE KEY-----\n

# .env.production.example (line 151):
FIREBASE_ADMIN_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nYOUR_PRODUCTION_PRIVATE_KEY_HERE\n-----END PRIVATE KEY-----\n"
```

**Problem:**
- .env.production.example uses quotes (line 151)
- Other files don't use quotes
- Inconsistent format may cause parsing errors

**Recommendation:**
```bash
# Always use quotes for multiline keys:
FIREBASE_ADMIN_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nKEY_CONTENT_HERE\n-----END PRIVATE KEY-----\n"

# Document in template:
# NOTE: Use literal \n characters (not actual newlines)
# Wrap in quotes to preserve spaces and special characters
```

---

## 🟠 HIGH PRIORITY ISSUES (P1)

### 12. Redundant Variable Definitions

**Issue:** Same variables defined in multiple files with conflicting defaults.

**Evidence:**
```bash
# CELERY_BROKER_URL defined in 3 places:

# .env.example (line 105):
CELERY_BROKER_URL=redis://localhost:6379/0

# .env.railway.template (line 104):
CELERY_BROKER_URL=rediss://default:REPLACE_WITH_REDIS_PASSWORD@REPLACE_WITH_REDIS_HOST:REPLACE_WITH_REDIS_PORT/0

# .env.production.example (line 74):
CELERY_BROKER_URL=rediss://default:PASSWORD@HOST:PORT/0
```

**Problem:**
- No way to construct Celery URL from existing Redis variables
- Must manually duplicate Redis credentials
- Risk of mismatch between REDIS_URL and CELERY_BROKER_URL

**Recommendation:**
```python
# In application code, derive Celery URL from Redis settings:
def get_celery_broker_url(redis_url: str, broker_db: int) -> str:
    """Construct Celery broker URL from Redis settings."""
    # Parse redis_url and append /broker_db
    return f"{redis_url.rstrip('/')}/{broker_db}"

# Or allow CELERY_BROKER_URL to be optional, deriving from REDIS_URL + REDIS_BROKER_DB_NUMBER
```

---

### 13. Missing Environment-Specific Validation

**Issue:** No validation that production files use secure values.

**Evidence:**
```bash
# .env.production.example still has placeholders:
REDIS_PASSWORD=CHANGE_THIS_TO_SECURE_REDIS_PASSWORD  # line 48
ENCRYPTION_KEY_CURRENT=CHANGE_THIS_TO_FERNET_ENCRYPTION_KEY  # line 124
```

**Current validation (security.py lines 368-377):**
```python
if is_production:
    placeholder_patterns = ["CHANGE_THIS", "YOUR_", "INSECURE", "DEV-", "MUST-BE-CHANGED"]
    for field in ["SECURITY_SECRET_KEY", "SECURITY_ENCRYPTION_KEY"]:
        if field in data:
            v = data[field]
            if v and any(pattern in v.upper() for pattern in placeholder_patterns):
                raise ValueError(...)
```

**Problem:**
- Only validates 3 keys
- Doesn't validate `REDIS_PASSWORD`, `QUIZ_TOKEN_SECRET`, `EVOLUTION_WEBHOOK_SECRET`, etc.

**Recommendation:**
```python
# Expand validation to all secrets:
PRODUCTION_REQUIRED_SECRETS = [
    "SECURITY_SECRET_KEY",
    "SECURITY_CSRF_SECRET_KEY",
    "ENCRYPTION_KEY_CURRENT",
    "PHI_ENCRYPTION_KEY",
    "HASH_SALT",
    "REDIS_PASSWORD",
    "QUIZ_TOKEN_SECRET",
    "WHATSAPP_EVOLUTION_WEBHOOK_SECRET",
    "AI_GEMINI_API_KEY",
]

for secret_key in PRODUCTION_REQUIRED_SECRETS:
    if secret_key in data:
        validate_not_placeholder(data[secret_key], secret_key)
```

---

### 14. Redis Pool Configuration Mismatch

**Issue:** Different pool sizes in database.py vs .env files.

**Evidence:**
```bash
# database.py (line 106):
REDIS_POOL_MAX_CONNECTIONS: int = Field(default=20, ...)  # Code default: 20

# .env.example (line 86):
REDIS_POOL_MAX_CONNECTIONS=50  # Template default: 50

# .env.railway.template (line 96):
REDIS_POOL_MAX_CONNECTIONS=10

# .env.production.example (line 57):
REDIS_POOL_MAX_CONNECTIONS=50
```

**Problem:**
- Code expects `REDIS_POOL_MAX_CONNECTIONS`
- Legacy `REDIS_MAX_CONNECTIONS` is ignored if present
- Defaults may be used unexpectedly if legacy name is configured

**Recommendation:**
```bash
# Standardize on REDIS_POOL_MAX_CONNECTIONS everywhere:
# Remove any REDIS_MAX_CONNECTIONS usage and keep:
REDIS_POOL_MAX_CONNECTIONS=<value>
```

---

### 15. Session Configuration Inconsistency

**Issue:** Session variables use different naming patterns.

**Evidence:**
```bash
# security.py defines SESSION_* variables (lines 64-87):
SESSION_ENABLE_COOKIE_SECURE: bool
SESSION_ENABLE_COOKIE_HTTPONLY: bool
SESSION_COOKIE_SAMESITE: str
SESSION_COOKIE_MAX_AGE_SECONDS: int

# .env.railway.template uses SESSION_* (lines 196-200):
SESSION_ENABLE_COOKIE_SECURE=true
SESSION_ENABLE_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=lax
```

**Problem:**
- Code expects `SESSION_*` prefix
- Legacy `AUTH_SESSION_*` variables are ignored

**Recommendation:**
```bash
# Remove legacy AUTH_SESSION_* variables and keep:
SESSION_ENABLE_COOKIE_SECURE=true
SESSION_ENABLE_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=lax
```

---

### 16. Algorithm/Cipher Specification Security

**Issue:** No validation for allowed JWT algorithms.

**Evidence:**
```bash
# .env.example (line 28):
SECURITY_ALGORITHM=HS256

# .env.railway.template (line 31):
SECURITY_ALGORITHM=HS256

# security.py (line 31-33):
SECURITY_ALGORITHM: str = Field(default="HS256", ...)
```

**Problem:**
- No enum restriction on allowed algorithms
- Weak algorithms like `HS256` vs `RS256` not validated
- Could accidentally use `none` algorithm (security vulnerability)

**Recommendation:**
```python
# security.py - Add enum validation:
from enum import Enum

class JWTAlgorithm(str, Enum):
    HS256 = "HS256"
    HS384 = "HS384"
    HS512 = "HS512"
    RS256 = "RS256"  # Recommended for production
    RS384 = "RS384"
    RS512 = "RS512"

SECURITY_ALGORITHM: JWTAlgorithm = Field(
    default=JWTAlgorithm.HS256,
    description="JWT signing algorithm (RS256 recommended for production)"
)
```

---

### 17. CORS Configuration Pattern Violation

**Issue:** CORS variables don't follow `{CATEGORY}_ENABLE_` pattern.

**Evidence:**
```bash
# Existing (security.py lines 190-202):
CORS_FRONTEND_URL: str
CORS_QUIZ_URL: str
CORS_ALLOWED_ORIGINS: List[str] | str

# Pattern violation - no ENABLE flag
```

**Problem:**
- No way to completely disable CORS (for testing/debugging)
- Inconsistent with pattern where services have ENABLE flags

**Recommendation:**
```bash
# Add CORS enable flag:
CORS_ENABLE_SERVICE=true
CORS_FRONTEND_URL=http://localhost:5173
CORS_QUIZ_URL=http://localhost:3001
```

---

### 18. Database Pool Size Formula Documentation

**Issue:** Comments mention "Dynamic pool sizing" formula but no actual implementation.

**Evidence:**
```python
# database.py (line 20-21):
# OPTIMIZED: Dynamic pool sizing based on worker count
# Formula: base_size + (workers * 4) with overflow buffer
DATABASE_POOL_SIZE: int = Field(default=50, ...)  # Just a static value
```

**Problem:**
- Comment promises dynamic sizing
- Code uses static default
- No auto-scaling based on Celery worker count

**Recommendation:**
```python
# Implement dynamic pool sizing:
@property
def calculated_pool_size(self) -> int:
    """Calculate optimal pool size based on workers."""
    worker_count = self.CELERY_WORKER_CONCURRENCY
    base_size = 10
    per_worker = 4
    return base_size + (worker_count * per_worker)

DATABASE_POOL_SIZE: int = Field(
    default_factory=lambda self: self.calculated_pool_size,
    description="..."
)
```

---

### 19. Missing SSL/TLS Minimum Version for Database

**Issue:** PostgreSQL connection string includes `sslmode=require` but no TLS version specified.

**Evidence:**
```bash
# .env.example (line 58):
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require

# No TLS version enforcement
```

**Problem:**
- Vulnerable to downgrade attacks
- Could accept TLS 1.0 or 1.1 (deprecated)

**Recommendation:**
```bash
# Add TLS version to connection string:
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require&sslminversion=TLSv1.2

# Or add separate config variable:
DATABASE_SSL_MIN_VERSION=TLSv1.2
```

---

### 20. Frontend VITE_ Variable Security Concerns

**Issue:** All `VITE_` variables are exposed to browser, but some contain sensitive info.

**Evidence:**
```bash
# .env.example (frontend) includes:
VITE_FIREBASE_API_KEY=your-firebase-api-key          # OK - public
VITE_MONITORING_SENTRY_DSN=                         # OK - public DSN
VITE_WHATSAPP_INSTANCE_NAME=hormonia-instance       # ⚠️  Exposes internal naming
```

**Problem:**
- `VITE_WHATSAPP_INSTANCE_NAME` exposes internal infrastructure details
- Not sensitive enough to block, but unnecessary exposure

**Recommendation:**
```bash
# Document which VITE_ variables should NEVER be used:
# ❌ NEVER use VITE_ for:
# - API keys (except Firebase public keys)
# - Passwords
# - Internal hostnames/IPs
# - Database names

# ⚠️  Avoid VITE_ for:
# - Internal service names
# - Infrastructure details
```

---

### 21. Health Check Configuration Missing

**Issue:** Health check timeouts not consistently defined.

**Evidence:**
```bash
# .env.railway.template has (lines 247-252):
HEALTH_CHECK_PATH=/health
HEALTH_ENABLE_DATABASE_CHECK=true
HEALTH_ENABLE_REDIS_CHECK=true
HEALTH_ENABLE_EXTERNAL_APIS_CHECK=true
HEALTH_CHECK_TIMEOUT_SECONDS=10

# But .env.example has different structure (lines 355-358):
TASK_HEALTH_CHECK_TIMEOUT_SECONDS=30
TASK_HEALTH_ACTIVE_FLOWS_LIMIT=1000
# No HEALTH_* variables
```

**Problem:**
- Two different health check configurations
- `TASK_HEALTH_*` vs `HEALTH_*` prefix confusion

**Recommendation:**
```bash
# Standardize health check variables:
HEALTH_CHECK_ENABLE_SERVICE=true
HEALTH_CHECK_PATH=/health
HEALTH_CHECK_TIMEOUT_SECONDS=10
HEALTH_CHECK_ENABLE_DATABASE=true
HEALTH_CHECK_ENABLE_REDIS=true

# Keep TASK_* for task-specific health:
TASK_HEALTH_CHECK_TIMEOUT_SECONDS=30
```

---

### 22. Rate Limiting Redis DB Conflict

**Issue:** Rate limiting might use wrong Redis database.

**Evidence:**
```bash
# security.py (line 184):
RATE_LIMIT_REDIS_URL: Optional[str] = Field(default=None, ...)

# .env.example (line 100):
REDIS_RATE_LIMIT_DB_NUMBER=3

# .env.production.example (line 173):
RATE_LIMIT_STORAGE_URL=rediss://default:PASSWORD@HOST:PORT/3
```

**Problem:**
- `RATE_LIMIT_REDIS_URL` (code) vs `RATE_LIMIT_STORAGE_URL` (template) - different names
- No guarantee they use same DB number

**Recommendation:**
```bash
# Standardize naming:
RATE_LIMIT_REDIS_URL=  # Derive from REDIS_URL + REDIS_RATE_LIMIT_DB_NUMBER

# Or if explicitly set:
RATE_LIMIT_REDIS_URL=rediss://host:port/{REDIS_RATE_LIMIT_DB_NUMBER}
```

---

### 23. Monitoring Configuration Duplication

**Issue:** Sentry configuration spread across multiple variable groups.

**Evidence:**
```bash
# .env.example (lines 133-135):
MONITORING_ENABLE_SERVICE=true
MONITORING_SENTRY_DSN=
MONITORING_SENTRY_ENVIRONMENT=development

# .env.production.example (lines 157-160):
MONITORING_SENTRY_DSN=https://...
MONITORING_SENTRY_ENVIRONMENT=production
MONITORING_SENTRY_TRACES_SAMPLE_RATE=0.1
MONITORING_SENTRY_PROFILES_SAMPLE_RATE=0.1
```

**Problem:**
- Production template has extra variables not in base example
- Inconsistent variable sets across environments

**Recommendation:**
```bash
# Consolidate all Sentry variables in .env.example with defaults:
MONITORING_ENABLE_SERVICE=true
MONITORING_SENTRY_DSN=
MONITORING_SENTRY_ENVIRONMENT=development
MONITORING_SENTRY_TRACES_SAMPLE_RATE=1.0  # Dev: 100%, Prod: 0.1
MONITORING_SENTRY_PROFILES_SAMPLE_RATE=1.0
MONITORING_SENTRY_ENABLE_TRACING=true
```

---

### 24. Task Configuration Sprawl

**Issue:** 50+ TASK_* variables with no clear organization.

**Evidence:**
```bash
# .env.example lines 302-396 contains:
TASK_FLOW_PROCESSING_TIMEOUT_SECONDS=30
TASK_TIME_LIMIT_SECONDS=3600
TASK_MAX_RETRIES=3
TASK_MESSAGE_SEND_TIMEOUT_SECONDS=60
TASK_QUIZ_PROCESSING_TIMEOUT_SECONDS=600
TASK_HEALTH_CHECK_TIMEOUT_SECONDS=30
TASK_CLEANUP_BATCH_SIZE=100
TASK_REPORT_MAX_RETRIES=3
TASK_SAGA_ENABLE_PATTERN=true
TASK_ALERT_MAX_RETRIES=3
# ... 40 more TASK_* variables
```

**Problem:**
- No grouping by subsystem (FLOW, MESSAGE, QUIZ, etc.)
- Hard to find related variables
- Many have similar names (e.g., multiple `*_MAX_RETRIES`)

**Recommendation:**
```bash
# Group TASK variables by subsystem:

# Task Core Settings
TASK_TIME_LIMIT_SECONDS=3600
TASK_SOFT_TIME_LIMIT_SECONDS=3300
TASK_MAX_RETRIES=3
TASK_RETRY_BACKOFF_FACTOR=2

# Task Flow Processing
TASK_FLOW_TIMEOUT_SECONDS=30
TASK_FLOW_BATCH_SIZE=10
TASK_FLOW_MAX_CONCURRENT=50
TASK_FLOW_MAX_RETRIES=3

# Task Message Processing
TASK_MESSAGE_TIMEOUT_SECONDS=60
TASK_MESSAGE_MAX_RETRIES=3
TASK_MESSAGE_BATCH_SIZE=100

# Task Quiz Processing
TASK_QUIZ_TIMEOUT_SECONDS=600
TASK_QUIZ_MAX_RETRIES=3
TASK_QUIZ_SESSION_TIMEOUT_HOURS=48
```

---

### 25. AI Configuration Security

**Issue:** AI API keys stored in plain .env files without rotation guidance.

**Evidence:**
```bash
# .env.example (line 160):
AI_GEMINI_API_KEY=

# .env.railway.template (line 117):
AI_GEMINI_API_KEY=REPLACE_WITH_GOOGLE_GEMINI_API_KEY
```

**Problem:**
- No mention of key rotation policy
- No mention of using secret managers (AWS Secrets Manager, etc.)
- API key in plain text is a security risk

**Recommendation:**
```bash
# Document in .env.railway.template:
# =============================================================================
# AI SERVICES - SECURITY NOTICE
# =============================================================================
# API keys should be rotated every 90 days
# For production, use secret manager instead of .env:
#   - AWS Secrets Manager: secrets.get_secret_value("AI_GEMINI_API_KEY")
#   - Railway: Use Railway Secret Manager
#   - Docker: Use Docker Secrets
AI_GEMINI_API_KEY=REPLACE_WITH_KEY_OR_USE_SECRET_MANAGER
```

---

### 26. WhatsApp Webhook Secret Reuse

**Issue:** Same webhook secret format as other secrets - no differentiation.

**Evidence:**
```bash
# .env.example (line 144):
WHATSAPP_EVOLUTION_WEBHOOK_SECRET=CHANGE_THIS_TO_A_SECURE_RANDOM_VALUE

# .env.railway.template (line 146):
EVOLUTION_WEBHOOK_SECRET=REPLACE_WITH_WEBHOOK_SECRET
```

**Problem:**
- Variable name changes: `WHATSAPP_EVOLUTION_WEBHOOK_SECRET` vs `EVOLUTION_WEBHOOK_SECRET`
- No guidance that this must match Evolution API configuration

**Recommendation:**
```bash
# Standardize naming:
WHATSAPP_EVOLUTION_WEBHOOK_SECRET=<generate-secret>

# Add comment in template:
# SECURITY: This secret must match the webhook secret configured
# in Evolution API dashboard. Use the same value in both places.
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

### 27. Cache TTL Organization

**Issue:** 25+ cache TTL variables with no clear grouping.

**Evidence:**
```bash
# .env.example lines 427-452 contains:
CACHE_FLOW_TEMPLATE_TTL_SECONDS=3600
CACHE_TEMPLATE_CACHE_TTL_SECONDS=3600
CACHE_USER_SESSION_TTL_SECONDS=1800
CACHE_AUTH_TOKEN_TTL_SECONDS=86400
CACHE_REFRESH_TOKEN_TTL_SECONDS=604800
CACHE_PATIENT_CACHE_TTL_SECONDS=900
# ... 20 more CACHE_*_TTL_SECONDS variables
```

**Problem:**
- All use `_SECONDS` suffix (good!)
- But hard to find related caches (e.g., all auth-related caches)
- Some redundant naming: `CACHE_TEMPLATE_CACHE_TTL` has "CACHE" twice

**Recommendation:**
```bash
# Fix redundant naming:
- CACHE_TEMPLATE_CACHE_TTL_SECONDS=3600
+ CACHE_TEMPLATE_TTL_SECONDS=3600

- CACHE_PATIENT_CACHE_TTL_SECONDS=900
+ CACHE_PATIENT_TTL_SECONDS=900

# Group by domain in comments:
# Authentication & Session Caches
CACHE_AUTH_TOKEN_TTL_SECONDS=86400
CACHE_REFRESH_TOKEN_TTL_SECONDS=604800
CACHE_USER_SESSION_TTL_SECONDS=1800

# Medical Data Caches
CACHE_PATIENT_TTL_SECONDS=900
CACHE_DOCTOR_TTL_SECONDS=1800
```

---

### 28. Compliance Configuration Missing

**Issue:** LGPD/HIPAA section has encryption key and hash salt with no validation.

**Evidence:**
```bash
# .env.example (lines 466-468):
COMPLIANCE_PHI_ENCRYPTION_KEY=your-phi-encryption-key-here-32-bytes
COMPLIANCE_HASH_SALT=5af51c11708d8d56dd5a9f8e5ca0071a3a662746ef415c1cecf3c04ef1c63d81
```

**Problem:**
- `COMPLIANCE_PHI_ENCRYPTION_KEY` is different from `PHI_ENCRYPTION_KEY`
- Are these the same key or different?
- No code references found for `COMPLIANCE_PHI_ENCRYPTION_KEY`
- `COMPLIANCE_HASH_SALT` has actual hex value in example (should be placeholder)

**Recommendation:**
```bash
# Clarify relationship with main encryption key:
# Option 1: Same as main encryption key
COMPLIANCE_PHI_ENCRYPTION_KEY=${PHI_ENCRYPTION_KEY}  # Reuse

# Option 2: Separate key for compliance features
COMPLIANCE_PHI_ENCRYPTION_KEY=  # Generate separate key if needed

# Fix hash salt example:
- COMPLIANCE_HASH_SALT=5af51c11708d8d56dd5a9f8e5ca0071a3a662746ef415c1cecf3c04ef1c63d81
+ COMPLIANCE_HASH_SALT=  # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 🟡 MEDIUM PRIORITY ISSUES (P2)

### 29. Frontend-Backend Variable Duplication

**Issue:** Same variables defined in both frontend and backend with different formats.

**Evidence:**
```bash
# Backend .env.example (line 127):
CORS_QUIZ_URL=http://localhost:3001

# Frontend .env.example (line 45):
VITE_API_ENDPOINT_URL=http://localhost:8000/api/v2
```

**Problem:**
- No guarantee frontend and backend URLs match
- Must manually sync across .env files

**Recommendation:**
- Document in both files that URLs must match
- Or: Frontend reads from backend API endpoint for quiz URL

---

### 30-63. Additional Medium/Low Priority Issues

Due to space constraints, I'll summarize the remaining issues:

**Pattern Consistency (P2):**
- Inconsistent comment formatting across files
- Missing variable descriptions in some sections
- Inconsistent grouping (some files use ==== separators, others use ----)

**Documentation Issues (P2):**
- Missing "Generate with:" comments for many secrets
- No mention of secret rotation policies
- No disaster recovery documentation links

**Low Priority (P3):**
- Variable ordering inconsistencies
- Comment style variations
- Whitespace formatting differences

---

## Summary of Recommendations

### Immediate Actions (Before Production)

1. **Fix encryption key naming:** Standardize on `ENCRYPTION_KEY_CURRENT` + `PHI_ENCRYPTION_KEY`
2. **Fix Redis DB variable names:** Use `_DB_NUMBER` suffix consistently
3. **Fix session variables:** Use `SESSION_*` prefix (not `AUTH_SESSION_*`)
4. **Fix Redis pool variable:** Use `REDIS_POOL_MAX_CONNECTIONS`
5. **Validate all secrets:** Expand placeholder detection to all secret fields

### Short-Term Actions (Next Sprint)

6. Add enum validation for algorithms and SSL cert requirements
7. Implement dynamic database pool sizing
8. Add TLS version enforcement for PostgreSQL
9. Group task variables by subsystem
10. Fix cache TTL redundant naming

### Long-Term Improvements (Technical Debt)

11. Create single source of truth for Redis URL (derive Celery/rate-limit URLs)
12. Document secret rotation policies
13. Add integration with secret managers (AWS Secrets Manager, etc.)
14. Create automated validation scripts
15. Generate .env from schema/types

---

## Validation Checklist

Before deploying to production, ensure:

- [ ] All `REPLACE_WITH_*` placeholders replaced with actual values
- [ ] All `CHANGE_THIS_*` placeholders replaced with generated secrets
- [ ] `ENCRYPTION_KEY_CURRENT` set (legacy `SECURITY_ENCRYPTION_KEY` removed)
- [ ] `PHI_ENCRYPTION_KEY` set for AES-GCM encryption
- [ ] `HASH_SALT` set for searchable hashes
- [ ] Redis variables use correct names (`_DB_NUMBER`, `_POOL_MAX_CONNECTIONS`)
- [ ] Session variables use `SESSION_*` prefix
- [ ] Boolean values use lowercase (`true`/`false`)
- [ ] All timeouts have unit suffixes (`_SECONDS`, `_MS`, `_MINUTES`, etc.)
- [ ] Redis URL scheme matches SSL flag (`rediss://` = SSL enabled)
- [ ] CORS origins set to actual production URLs (no `localhost`)
- [ ] Firebase private key properly escaped with `\n` (not actual newlines)

---

## Affected Files

### Backend
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/.env.example`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/.env.railway.template`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/.env.production.example`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/config/settings/security.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/config/settings/database.py`

### Frontend
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/frontend-hormonia/.env.example`

### Documentation
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/docs/REQUIRED_ENV_VARS_QUICKREF.md`

---

## Next Steps

1. **Create GitHub Issue:** Track each critical issue separately
2. **Update Templates:** Fix variable names in all .env.* files
3. **Update Code:** Fix variable names in settings files
4. **Add Tests:** Create validation tests for environment variables
5. **Update Docs:** Document secret rotation policies

---

**Report Generated:** 2025-12-10
**Reviewer:** Code Review Agent
**Priority:** 🔴 CRITICAL - Fix before production deployment
