# Environment Configuration Audit - Production Readiness Assessment
**Date:** 2025-10-09
**Task ID:** env-config
**Status:** ⚠️ **CRITICAL ISSUES FOUND**

## Executive Summary

Comprehensive audit of environment configuration for production deployment reveals **critical security and configuration gaps** that must be addressed before production launch.

### Critical Issues Summary
- ✅ **Frontend:** Well-configured with Railway production URLs
- ❌ **Backend:** Multiple critical security keys using placeholder values
- ⚠️ **Database:** Migrations need validation (alembic command not found)
- ⚠️ **Redis:** Configuration present but SSL certificates need verification
- ❌ **Security:** CSRF, webhook, and session secrets not properly configured

---

## 1. Frontend Environment Configuration

### ✅ Status: **PRODUCTION READY** (with minor recommendations)

### Configuration Files Analyzed
- `frontend-hormonia/.env` ✅
- `frontend-hormonia/.env.example` ✅
- `frontend-hormonia/vite.config.ts` ✅
- `frontend-hormonia/src/lib/api-client.ts` ✅
- `frontend-hormonia/src/lib/runtime-config.ts` ✅

### API & Backend URLs
```env
# Production URLs - CORRECTLY CONFIGURED
VITE_API_BASE_URL=https://clinica-oncologica-v02-production.up.railway.app
VITE_API_URL=https://clinica-oncologica-v02-production.up.railway.app/api/v1
VITE_WS_BASE_URL=wss://clinica-oncologica-v02-production.up.railway.app/ws/connect
VITE_WS_URL=wss://clinica-oncologica-v02-production.up.railway.app/ws/connect
```

✅ **Strengths:**
- HTTPS enforcement for production (see `api-client.ts:99-111`)
- Runtime configuration fallback mechanism (`runtime-config.ts:72-116`)
- Vite build-time env variable injection (`vite.config.ts:49-56`)
- Security headers and CORS properly configured

### Firebase Configuration
```env
# Firebase Client SDK - PUBLIC CONFIG (SAFE)
VITE_FIREBASE_API_KEY=AIzaSyDbZHMNV2eZQty03TgA4yNo_3L6UDSpHdI
VITE_FIREBASE_AUTH_DOMAIN=sistema-oncologico-auth.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=sistema-oncologico-auth
VITE_FIREBASE_STORAGE_BUCKET=sistema-oncologico-auth.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=608742835827
VITE_FIREBASE_APP_ID=1:608742835827:web:fa12840b0bd4949b7c8c06
VITE_FIREBASE_MEASUREMENT_ID=G-2QZQFKJMH2
```

✅ **Status:** Properly configured for client-side Firebase authentication
⚠️ **Note:** These are public client credentials (intended for browser use)

### Supabase Configuration (Legacy/Optional)
```env
# Supabase (Optional - Firebase is primary auth)
VITE_SUPABASE_URL=https://rszpypytdciggybbpnrp.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
VITE_SUPABASE_AUTH_ENABLED=false
VITE_SUPABASE_REALTIME_ENABLED=false
```

✅ **Status:** Properly disabled (Firebase is primary authentication)

### Security Features
```env
# Security Settings - PRODUCTION MODE
VITE_ENVIRONMENT=production
VITE_DEBUG_MODE=false
VITE_ENABLE_CSP=true
VITE_FORCE_HTTPS=true
VITE_SECURITY_HEADERS_ENABLED=true
```

✅ **Status:** All security features properly enabled for production

### ⚠️ Recommendations for Frontend

1. **Environment Variable Validation** (Minor)
   - Add runtime validation for critical URLs in `config-initializer.tsx`
   - Implement health check endpoint before app initialization

2. **Build Optimization**
   - Current chunk splitting is good (`vite.config.ts:79-100`)
   - Consider adding service worker for offline support

3. **Monitoring**
   ```env
   VITE_SENTRY_DSN=  # ⚠️ EMPTY - Add if error tracking needed
   ```

---

## 2. Backend Environment Configuration

### ❌ Status: **CRITICAL SECURITY ISSUES DETECTED**

### Configuration Files Analyzed
- `backend-hormonia/app/config.py` ✅
- `backend-hormonia/.env.example` ✅
- `backend-hormonia/.env.railway.template` ✅

### 🚨 **CRITICAL: Placeholder Security Keys Detected**

The `config.py` validator (lines 359-367) explicitly **blocks placeholder values** in production:

```python
# Validate security keys are not placeholders
for field in ['SECRET_KEY', 'JWT_SECRET_KEY', 'ENCRYPTION_KEY']:
    if field in data:
        v = data[field]
        if v and ('CHANGE_THIS' in v.upper() or 'YOUR_' in v.upper()):
            raise ValueError(
                f"{field} must be changed from placeholder value. "
                f"Never use default/example values in production."
            )
```

#### Current Template Values (`.env.railway.template`)
```env
# ❌ CRITICAL: These MUST be replaced
SECRET_KEY=REPLACE_WITH_64_CHARACTER_SECRET_KEY
MONTHLY_QUIZ_TOKEN_SECRET=REPLACE_WITH_QUIZ_TOKEN_SECRET_DIFFERENT_FROM_MAIN_SECRET
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require
REDIS_URL=rediss://default:YOUR_PASSWORD@YOUR_HOST:YOUR_PORT
```

### Required Security Keys

#### 1. CSRF Protection
```env
# CRITICAL: CSRF_SECRET_KEY
# Purpose: CSRF token generation and validation
# Location: Used in app/middleware/csrf.py:111
# Validation: app/utils/security_validation.py:133-212
# Required Length: ≥32 characters
# Entropy Requirement: ≥4.0 bits/char

# ❌ Current Status: NOT CONFIGURED (Optional[str] = None)
CSRF_SECRET_KEY=<MUST_GENERATE>

# Generate with:
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Impact if not set:**
- CSRF protection disabled (see `config.py:467-471`)
- Application will log warning but continue
- Production deployment **WILL FAIL** validation (line 450-456)

#### 2. Evolution API Webhook Secret
```env
# CRITICAL: EVOLUTION_WEBHOOK_SECRET
# Purpose: WhatsApp webhook signature validation
# Location: Used in app/middleware/webhook_validator.py:19
# Referenced in: app/api/v1/webhooks_secure.py:44

# ❌ Current Status: NOT CONFIGURED (Optional[str] = None)
EVOLUTION_WEBHOOK_SECRET=<MUST_GENERATE>

# Generate with:
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Impact if not set:**
- Webhook signature validation disabled
- Application accepts unsigned webhooks (security risk)
- Warning logged: "WEBHOOK SECURITY: No secret configured" (webhook_validator.py:104)

#### 3. Session Secret Key
```env
# CRITICAL: SECRET_KEY (Main Application Secret)
# Purpose: JWT signing, session encryption, general cryptography
# Location: app/config.py:18
# Required: MUST NOT contain 'CHANGE_THIS' or 'YOUR_'

# ❌ Current Template: REPLACE_WITH_64_CHARACTER_SECRET_KEY
SECRET_KEY=<MUST_GENERATE>

# Generate 64-character secret:
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

#### 4. JWT Secret Key
```env
# RECOMMENDED: JWT_SECRET_KEY (Fallback to SECRET_KEY if not set)
# Purpose: JWT token signing (can use SECRET_KEY)
# Location: app/config.py:19

JWT_SECRET_KEY=<OPTIONAL_BUT_RECOMMENDED>
```

#### 5. Encryption Key
```env
# RECOMMENDED: ENCRYPTION_KEY
# Purpose: Sensitive data encryption (e.g., patient data)
# Validation: Checked for placeholders (config.py:359-367)

ENCRYPTION_KEY=<OPTIONAL_BUT_RECOMMENDED>
```

### Database Configuration

#### PostgreSQL Connection String
```env
# Current Template (MUST be replaced)
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require

# Production Format (PostgreSQL 13+, Python 3.13 compatible)
# Driver: psycopg v3 (not psycopg2)
DATABASE_URL=postgresql+psycopg://app_user:PASSWORD@db.PROJECT.supabase.co:5432/postgres?sslmode=require

# Connection Pool Settings (config.py:lines 233-237)
DB_POOL_SIZE=30           # Max connections in pool
DB_MAX_OVERFLOW=40        # Additional connections when pool full
DB_POOL_TIMEOUT=30        # Seconds to wait for connection
DB_POOL_RECYCLE=3600      # Recycle connections after 1 hour
```

✅ **Strengths:**
- SSL mode correctly enforced (`?sslmode=require`)
- Modern `psycopg` driver (Python 3.13 compatible)
- Connection pooling properly configured

⚠️ **Issue:** Cannot verify migrations without alembic CLI access

### Redis Configuration

#### Connection Settings
```env
# Current Template (MUST be replaced)
REDIS_URL=rediss://default:YOUR_PASSWORD@YOUR_HOST:YOUR_PORT
REDIS_PASSWORD=YOUR_PASSWORD
REDIS_HOST=YOUR_HOST
REDIS_PORT=6379

# SSL/TLS Configuration (config.py:88-100)
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required         # ✅ CORRECT for production
REDIS_SSL_MIN_VERSION=TLSV1_2        # Optional: Force TLS 1.2
REDIS_SSL_CA_CERTS=certs/redis_ca.pem # Path to CA certificate
```

✅ **Strengths:**
- SSL enforcement (`rediss://` scheme)
- Certificate validation enabled (`required`)
- Database isolation configured (lines 117-122)

⚠️ **Concerns:**
1. **CA Certificate Path:** `REDIS_SSL_CA_CERTS` references `certs/redis_ca.pem`
   - Must verify certificate exists in Railway deployment
   - Alternative: Use `certifi` package (auto-detects system CA bundle)

2. **TLS Version:** `REDIS_SSL_MIN_VERSION=TLSV1_2`
   - Required for Redis Cloud compatibility
   - Python 3.13 + OpenSSL 3.x defaults to TLS 1.3

#### Database Isolation
```env
# Database Number Allocation (config.py:117-122)
REDIS_ENABLE_DB_ISOLATION=true
REDIS_CACHE_DB=1          # Application cache
REDIS_BROKER_DB=0         # Celery broker
REDIS_SESSION_DB=2        # User sessions
REDIS_RATE_LIMIT_DB=3     # Rate limiting
```

✅ **Status:** Properly configured for production

### CORS Configuration

```python
# Dynamic CORS (config.py:189-192)
FRONTEND_URL=http://localhost:5173
QUIZ_URL=http://localhost:3001
ALLOWED_ORIGINS=[]  # Auto-built from FRONTEND_URL + QUIZ_URL in production
```

✅ **Implementation:** `config.py:504-523` - Smart CORS handling
- **Production:** Uses `FRONTEND_URL` + `QUIZ_URL` (domain-only)
- **Development:** Empty list (regex-based in middleware)

⚠️ **Production Requirement:**
```env
# MUST set for Railway deployment
FRONTEND_URL=https://frontend-production-c59bc.up.railway.app
QUIZ_URL=https://quiz-production.up.railway.app
```

### AI Services Configuration

```env
# Google Gemini AI (config.py:156-165)
GEMINI_API_KEY=<MUST_SET>           # ❌ Required for AI features
GEMINI_MODEL=gemini-2.0-flash-exp
GEMINI_TEMPERATURE=0.7
GEMINI_MAX_OUTPUT_TOKENS=500
GEMINI_TIMEOUT=30
GEMINI_MAX_RETRIES=3
```

⚠️ **Status:** Required if AI humanization is enabled (`AI_HUMANIZATION_ENABLED=true`)

---

## 3. Database Migration Status

### ❌ **CRITICAL: Cannot Verify Migration Status**

#### Issue
```bash
$ cd backend-hormonia && alembic current
/usr/bin/bash: line 1: alembic: command not found
```

#### Migration Files Found
Total migrations: **67 files** in `alembic/versions/`

**Recent migrations (Sprint 2 - Phase 2.5):**
1. ✅ `20251009_210800_add_gin_indexes_for_search.py` - GIN indexes for JSONB search
2. ✅ `20251009_225600_add_quiz_session_to_alerts.py` - Alert system enhancements
3. ✅ `20251009_230000_add_whatsapp_delivery_failures.py` - WhatsApp retry tracking
4. ✅ `20251009_235500_add_webhook_idempotency.py` - Duplicate webhook prevention
5. ✅ `20251009_235900_add_delivery_status.py` - Message delivery tracking

#### Action Required
```bash
# Install alembic in backend environment
cd backend-hormonia
pip install alembic

# Check current migration status
alembic current

# Verify all migrations applied
alembic history --verbose

# Apply pending migrations (if any)
alembic upgrade head
```

### Migration Validation Checklist
- [ ] Verify database connection: `alembic current`
- [ ] Check for pending migrations: `alembic heads`
- [ ] Validate schema consistency
- [ ] Test rollback capability: `alembic downgrade -1` (then `upgrade head`)
- [ ] Verify GIN indexes created (PostgreSQL 13+ required)

---

## 4. Security Configuration Deep Dive

### CSRF Protection Implementation

#### Validation Flow (`app/utils/security_validation.py:133-212`)

```python
def validate_csrf_secret(csrf_secret: str, log_validation: bool = False) -> None:
    """
    Validates CSRF secret key strength with comprehensive entropy checking.

    Validation Checks:
    1. Minimum length: ≥32 characters
    2. Not a placeholder (no 'CHANGE', 'YOUR', 'REPLACE', 'EXAMPLE')
    3. Sufficient entropy: ≥4.0 bits/char
    4. Not sequential pattern (e.g., '123456', 'abcdef')
    5. Not in common weak password dictionary

    Raises:
        ValueError: If any validation check fails
    """
```

**Current Status:**
```env
CSRF_SECRET_KEY=None  # ❌ NOT SET - Production will FAIL if DEBUG=False
```

**Production Behavior (`config.py:449-456`):**
```python
if self.ENVIRONMENT.lower() == 'production':
    # CSRF secret validation failed in production: {error}
    raise ValueError(...)
else:
    # Development: just warn but allow startup
    logger.warning("⚠️  Continuing in development mode with weak CSRF secret.")
```

#### Generation Command
```bash
# Secure CSRF secret generation
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Example output (43 characters, URL-safe Base64):
# xK3mP9vN2qW8tRfYzHjC5bS7uGvXwLmN4pQaTdEiFo
```

### Firebase Admin SDK Configuration

```env
# Backend Firebase Admin SDK (config.py:36-48)
FIREBASE_ADMIN_PROJECT_ID=sistema-oncologico-auth
FIREBASE_ADMIN_PRIVATE_KEY=<PRIVATE_KEY_JSON>
FIREBASE_ADMIN_CLIENT_EMAIL=firebase-adminsdk-xyz@sistema-oncologico-auth.iam.gserviceaccount.com
```

✅ **Security Features Configured:**
```env
# Firebase Security (config.py:51-75)
FIREBASE_ALLOWED_DOMAINS=[]              # Restrict to corporate domains
FIREBASE_REQUIRE_CUSTOM_CLAIMS=true      # Require role claim
FIREBASE_ALLOWED_ROLES=['admin', 'super_admin', 'doctor', 'medico']
FIREBASE_ENABLE_AUDIT_LOGGING=true       # Log all provisioning
FIREBASE_BLOCK_PUBLIC_DOMAINS=true       # Block gmail.com, yahoo.com
FIREBASE_PUBLIC_DOMAINS_BLOCKLIST=['gmail.com', 'yahoo.com', ...]
```

⚠️ **Private Key Security:**
- Store in Railway secrets (not `.env` file)
- Format: JSON key with `\n` for newlines
- Validate at startup (`config.py:385-408`)

### Production Security Validation

#### Enforced Settings (`config.py:473-502`)
```python
if self.ENVIRONMENT.lower() == 'production':
    errors = []

    # ❌ WILL FAIL if not set:
    if self.DEBUG:
        errors.append("DEBUG must be False in production")

    if not self.SESSION_COOKIE_SECURE:
        errors.append("SESSION_COOKIE_SECURE must be True")

    if not self.SECURE_SSL_REDIRECT:
        errors.append("SECURE_SSL_REDIRECT must be True")

    # Redis SSL validation
    if self.REDIS_SSL and not self.REDIS_URL.startswith('rediss://'):
        print("⚠️  WARNING: REDIS_SSL=True but URL doesn't use rediss://")

    if errors:
        raise ValueError(f"Production validation failed:\n" + ...)
```

**Required Production Settings:**
```env
ENVIRONMENT=production
DEBUG=false                    # ❌ CRITICAL: Must be false
SESSION_COOKIE_SECURE=true     # ❌ CRITICAL: HTTPS cookies only
SECURE_SSL_REDIRECT=true       # ❌ CRITICAL: Force HTTPS
```

---

## 5. Production Readiness Checklist

### 🔴 **CRITICAL - BLOCKING DEPLOYMENT**

- [ ] **Generate CSRF_SECRET_KEY**
  ```bash
  python -c "import secrets; print('CSRF_SECRET_KEY=' + secrets.token_urlsafe(32))"
  ```

- [ ] **Generate EVOLUTION_WEBHOOK_SECRET**
  ```bash
  python -c "import secrets; print('EVOLUTION_WEBHOOK_SECRET=' + secrets.token_urlsafe(32))"
  ```

- [ ] **Replace SECRET_KEY placeholder**
  ```bash
  python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(64))"
  ```

- [ ] **Configure DATABASE_URL with actual credentials**
  - Replace `USER`, `PASSWORD`, `HOST`, `PORT`, `DATABASE`
  - Ensure `?sslmode=require` is present

- [ ] **Configure REDIS_URL with actual credentials**
  - Replace `YOUR_PASSWORD`, `YOUR_HOST`, `YOUR_PORT`
  - Ensure `rediss://` scheme is used (SSL)

- [ ] **Set Production URLs for CORS**
  ```env
  FRONTEND_URL=https://your-frontend.railway.app
  QUIZ_URL=https://your-quiz.railway.app
  ```

- [ ] **Verify Firebase Admin SDK credentials**
  - `FIREBASE_ADMIN_PROJECT_ID`
  - `FIREBASE_ADMIN_PRIVATE_KEY`
  - `FIREBASE_ADMIN_CLIENT_EMAIL`

### ⚠️ **HIGH PRIORITY - RECOMMENDED**

- [ ] **Verify Redis CA Certificate**
  - Check if `certs/redis_ca.pem` exists
  - Or remove `REDIS_SSL_CA_CERTS` to use `certifi`

- [ ] **Configure Gemini API Key** (if AI features enabled)
  ```env
  GEMINI_API_KEY=<your-google-gemini-api-key>
  ```

- [ ] **Set Monitoring/Sentry DSN** (optional but recommended)
  ```env
  VITE_SENTRY_DSN=https://your-sentry-dsn@sentry.io/project
  SENTRY_DSN=https://your-backend-sentry-dsn@sentry.io/project
  ```

- [ ] **Validate Database Migrations**
  ```bash
  cd backend-hormonia
  alembic current
  alembic upgrade head
  ```

### 📋 **MEDIUM PRIORITY - NICE TO HAVE**

- [ ] **Configure JWT_SECRET_KEY** (separate from SECRET_KEY)
  ```bash
  python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(64))"
  ```

- [ ] **Configure ENCRYPTION_KEY** (for sensitive data)
  ```bash
  python -c "import secrets; print('ENCRYPTION_KEY=' + secrets.token_urlsafe(64))"
  ```

- [ ] **Set Clinic Information**
  ```env
  CLINIC_NAME=Clínica Hormonia
  CLINIC_ADDRESS=<your-address>
  CLINIC_PHONE=<your-phone>
  CLINIC_EMAIL=<your-email>
  ```

- [ ] **Enable Monitoring**
  ```env
  MONITORING_ENABLED=true
  MONITORING_DEBUG=false
  ```

---

## 6. Environment Variables Summary

### Frontend Environment Variables (Production)
```env
# API & Backend
VITE_API_BASE_URL=https://clinica-oncologica-v02-production.up.railway.app
VITE_API_URL=https://clinica-oncologica-v02-production.up.railway.app/api/v1
VITE_WS_BASE_URL=wss://clinica-oncologica-v02-production.up.railway.app/ws/connect
VITE_WS_URL=wss://clinica-oncologica-v02-production.up.railway.app/ws/connect

# Firebase Client (Public - Safe for Browser)
VITE_FIREBASE_API_KEY=AIzaSyDbZHMNV2eZQty03TgA4yNo_3L6UDSpHdI
VITE_FIREBASE_AUTH_DOMAIN=sistema-oncologico-auth.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=sistema-oncologico-auth
VITE_FIREBASE_STORAGE_BUCKET=sistema-oncologico-auth.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=608742835827
VITE_FIREBASE_APP_ID=1:608742835827:web:fa12840b0bd4949b7c8c06

# Security & Environment
VITE_ENVIRONMENT=production
VITE_DEBUG_MODE=false
VITE_ENABLE_CSP=true
VITE_FORCE_HTTPS=true
VITE_SECURITY_HEADERS_ENABLED=true
```

### Backend Environment Variables (Required)
```env
# Core Application
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<GENERATE_WITH_secrets.token_urlsafe(64)>
JWT_SECRET_KEY=<OPTIONAL_OR_FALLBACK_TO_SECRET_KEY>
ENCRYPTION_KEY=<RECOMMENDED_FOR_SENSITIVE_DATA>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
BCRYPT_ROUNDS=12

# Security Keys (CRITICAL)
CSRF_SECRET_KEY=<GENERATE_WITH_secrets.token_urlsafe(32)>
EVOLUTION_WEBHOOK_SECRET=<GENERATE_WITH_secrets.token_urlsafe(32)>
SESSION_COOKIE_SECURE=true
SECURE_SSL_REDIRECT=true

# Database (PostgreSQL)
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=40
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600

# Redis
REDIS_URL=rediss://default:PASSWORD@HOST:PORT
REDIS_PASSWORD=<YOUR_PASSWORD>
REDIS_HOST=<YOUR_HOST>
REDIS_PORT=6379
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required
REDIS_SSL_MIN_VERSION=TLSV1_2
REDIS_MAX_CONNECTIONS=50
REDIS_ENABLE_DB_ISOLATION=true

# Firebase Admin SDK (Backend)
FIREBASE_ADMIN_PROJECT_ID=sistema-oncologico-auth
FIREBASE_ADMIN_PRIVATE_KEY=<SERVICE_ACCOUNT_PRIVATE_KEY_JSON>
FIREBASE_ADMIN_CLIENT_EMAIL=firebase-adminsdk-xyz@sistema-oncologico-auth.iam.gserviceaccount.com

# CORS
FRONTEND_URL=https://your-frontend.railway.app
QUIZ_URL=https://your-quiz.railway.app

# AI Services (if enabled)
GEMINI_API_KEY=<GOOGLE_GEMINI_API_KEY>
AI_HUMANIZATION_ENABLED=true
```

---

## 7. Next Steps & Action Items

### Immediate Actions (Before Deployment)

1. **Generate Security Secrets** (5 minutes)
   ```bash
   # Run in backend-hormonia directory
   echo "CSRF_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" >> .env
   echo "EVOLUTION_WEBHOOK_SECRET=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" >> .env
   echo "SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(64))')" >> .env
   echo "JWT_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(64))')" >> .env
   ```

2. **Configure Railway Variables** (10 minutes)
   ```bash
   # Set in Railway Dashboard → backend-hormonia → Variables
   # Or use Railway CLI:
   railway variables set CSRF_SECRET_KEY="<value>"
   railway variables set EVOLUTION_WEBHOOK_SECRET="<value>"
   railway variables set SECRET_KEY="<value>"
   ```

3. **Update Database & Redis URLs** (5 minutes)
   - Replace placeholders in `.env.railway.template`
   - Copy to Railway environment variables

4. **Verify Migrations** (10 minutes)
   ```bash
   cd backend-hormonia
   pip install alembic
   alembic current
   alembic upgrade head
   ```

### Validation Testing (30 minutes)

1. **Backend Health Check**
   ```bash
   curl https://clinica-oncologica-v02-production.up.railway.app/health
   ```

2. **CSRF Token Endpoint**
   ```bash
   curl -v https://clinica-oncologica-v02-production.up.railway.app/api/v1/csrf-token
   ```

3. **Database Connection**
   ```bash
   # In backend container
   python -c "from app.database import get_db; next(get_db())"
   ```

4. **Redis Connection**
   ```bash
   # In backend container
   python -c "from app.utils.cache import redis_client; redis_client.ping()"
   ```

### Documentation Updates

1. **Update `.env.example`**
   - Add new required variables
   - Document generation commands
   - Add security warnings

2. **Create Railway Deployment Guide**
   - Document required environment variables
   - Add troubleshooting section
   - Include validation checklist

3. **Update README.md**
   - Add production deployment section
   - Document environment variable requirements
   - Add security best practices

---

## 8. Security Recommendations

### Immediate Security Fixes

1. **Never Commit Secrets to Git**
   ```bash
   # Verify .gitignore covers:
   .env
   .env.local
   .env.*.local
   .env.production
   *.pem
   *.key
   firebase-adminsdk-*.json
   ```

2. **Use Railway Secrets for Sensitive Data**
   - Store in Railway Variables (encrypted at rest)
   - Never in `Dockerfile` or `docker-compose.yml`
   - Use separate secrets per environment (dev/staging/prod)

3. **Rotate Secrets Regularly**
   - CSRF_SECRET_KEY: Every 90 days
   - EVOLUTION_WEBHOOK_SECRET: Every 90 days
   - SECRET_KEY: Every 180 days (requires re-login for all users)

4. **Enable Audit Logging**
   ```env
   FIREBASE_ENABLE_AUDIT_LOGGING=true
   MONITORING_ENABLED=true
   ```

### Long-term Security Improvements

1. **Implement Secret Management Service**
   - Consider AWS Secrets Manager / HashiCorp Vault
   - Automatic rotation
   - Access control and audit trails

2. **Add Rate Limiting**
   ```env
   RATE_LIMIT_ENABLED=true
   RATE_LIMIT_DEFAULT=100/minute
   RATE_LIMIT_LOGIN=5/minute
   ```

3. **Enable HTTPS Everywhere**
   - Enforce HTTPS redirects
   - Set HSTS headers
   - Use secure cookies only

4. **Implement Security Headers**
   - CSP (Content Security Policy)
   - X-Frame-Options
   - X-Content-Type-Options
   - Referrer-Policy

---

## 9. Monitoring & Observability

### Recommended Setup

1. **Application Performance Monitoring**
   ```env
   # Sentry (Error Tracking)
   SENTRY_DSN=https://your-dsn@sentry.io/project
   SENTRY_ENVIRONMENT=production
   SENTRY_SAMPLE_RATE=0.1

   # APM Metrics
   APM_APDEX_THRESHOLD=0.5
   APM_SLOW_REQUEST_THRESHOLD=1.0
   MONITORING_ENABLED=true
   ```

2. **Database Query Monitoring**
   ```env
   DB_SLOW_QUERY_THRESHOLD=1.0
   MONITORING_DEBUG=false
   ```

3. **Resource Monitoring**
   ```env
   RESOURCE_SAMPLE_INTERVAL=10.0
   RESOURCE_CPU_THRESHOLD=80.0
   RESOURCE_MEMORY_THRESHOLD=85.0
   ```

### Health Check Endpoints

```bash
# Backend Health
GET /health
# Response: {"status": "healthy", "database": "ok", "redis": "ok"}

# Frontend Health
GET /
# Should load without errors

# WebSocket Health
WS wss://clinica-oncologica-v02-production.up.railway.app/ws/connect
# Should connect successfully
```

---

## 10. Production Deployment Validation

### Pre-Deployment Checklist

#### Configuration
- [ ] All environment variables set in Railway
- [ ] No placeholder values (CHANGE_THIS, YOUR_, REPLACE_)
- [ ] Security secrets generated and validated
- [ ] CORS origins configured correctly
- [ ] SSL/TLS certificates verified

#### Database
- [ ] PostgreSQL connection string verified
- [ ] All migrations applied (`alembic upgrade head`)
- [ ] Connection pooling configured
- [ ] SSL mode enforced (`?sslmode=require`)

#### Redis
- [ ] Redis connection string verified
- [ ] SSL/TLS enabled (`rediss://`)
- [ ] Certificate validation configured
- [ ] Database isolation enabled

#### Security
- [ ] CSRF protection enabled with strong secret
- [ ] Webhook signature validation enabled
- [ ] Firebase Admin SDK configured
- [ ] Session cookies set to secure
- [ ] HTTPS redirect enabled
- [ ] Security headers configured

#### Monitoring
- [ ] Sentry/error tracking configured
- [ ] APM metrics enabled
- [ ] Health check endpoints accessible
- [ ] Logging configured correctly

### Post-Deployment Validation

```bash
# 1. Health Check
curl -f https://clinica-oncologica-v02-production.up.railway.app/health

# 2. CSRF Token
curl -v https://clinica-oncologica-v02-production.up.railway.app/api/v1/csrf-token \
  -H "Origin: https://frontend-production-c59bc.up.railway.app"

# 3. Frontend Load
curl -f https://frontend-production-c59bc.up.railway.app

# 4. WebSocket Connection
wscat -c wss://clinica-oncologica-v02-production.up.railway.app/ws/connect

# 5. Authentication Flow
# Test Firebase login → Backend session creation → Protected endpoint access
```

---

## 11. Conclusion

### Critical Findings

1. **✅ Frontend:** Production-ready with proper HTTPS, Firebase, and security settings
2. **❌ Backend:** Multiple critical security keys require generation before deployment
3. **⚠️ Database:** Cannot verify migration status without alembic CLI
4. **⚠️ Redis:** Configuration present but CA certificate needs verification
5. **❌ Security:** CSRF, webhook secrets, and main SECRET_KEY not configured

### Deployment Blockers

**CANNOT DEPLOY until these are resolved:**

1. Generate and set `CSRF_SECRET_KEY` (32+ chars, high entropy)
2. Generate and set `EVOLUTION_WEBHOOK_SECRET` (32+ chars)
3. Replace `SECRET_KEY` placeholder (64+ chars)
4. Configure actual `DATABASE_URL` with credentials
5. Configure actual `REDIS_URL` with credentials
6. Set production `FRONTEND_URL` and `QUIZ_URL` for CORS
7. Verify database migrations applied (`alembic upgrade head`)

### Timeline Estimate

- **Immediate fixes (secrets & URLs):** 30 minutes
- **Database migration verification:** 15 minutes
- **Deployment testing:** 30 minutes
- **Total:** ~1.5 hours

### Risk Assessment

**Current Risk Level:** 🔴 **CRITICAL**

**After fixes:** 🟢 **PRODUCTION READY**

---

## Memory Coordination

```bash
npx claude-flow@alpha memory store --key "swarm/integration/environment" --value "Environment audit complete: Critical security secrets required for deployment"
npx claude-flow@alpha hooks post-task --task-id "env-config"
```

---

**Report Generated:** 2025-10-09T23:56:13Z
**Author:** Code Analyzer Agent (Claude Flow)
**Task:** Environment Configuration Audit
**Session ID:** task-1760054173468-nypptkssm
