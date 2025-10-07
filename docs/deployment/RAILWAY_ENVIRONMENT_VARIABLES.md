# Railway Environment Variables - Complete Configuration Guide

## 🚨 Critical Issues Fixed

### Issue 1: DATABASE_URL Missing SSL Mode
**Problem:** Supabase requires SSL connections, causing errors:
```
psycopg.OperationalError: SSL connection has been closed unexpectedly
```

**Solution:** Add `?sslmode=require` parameter to DATABASE_URL

### Issue 2: CORS Origins Missing `//` after `https:`
**Problem:** Malformed URLs in ALLOWED_ORIGINS causing CORS failures:
```
Allowed origins: ['https:frontend-production-18bb...']  # WRONG
```

**Solution:** Ensure proper URL format with `https://`

---

## 📋 Required Environment Variables

### 🔐 1. Database Configuration (PostgreSQL/Supabase)

#### DATABASE_URL (REQUIRED)
**Format:** `postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require`

**CRITICAL: Must include `?sslmode=require` for Supabase/Railway PostgreSQL**

```bash
# ✅ CORRECT FORMAT (with SSL)
DATABASE_URL=postgresql+psycopg://postgres.xyz:password@aws-0-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require

# ❌ WRONG (missing sslmode parameter)
DATABASE_URL=postgresql+psycopg://postgres.xyz:password@aws-0-sa-east-1.pooler.supabase.com:5432/postgres
```

**Connection Pool Settings:**
```bash
DB_POOL_SIZE=30          # Default pool size
DB_MAX_OVERFLOW=40       # Maximum overflow connections
DB_POOL_TIMEOUT=30       # Pool timeout in seconds
DB_POOL_RECYCLE=3600     # Connection recycle time
```

**SSL Mode Options:**
- `require` - Required for production (Supabase/Railway)
- `verify-full` - Full certificate verification (most secure)
- `verify-ca` - Verify CA certificate
- `prefer` - Use SSL if available (not recommended for production)
- `disable` - No SSL (NEVER use in production)

---

### 🌐 2. CORS Configuration

#### FRONTEND_URL and QUIZ_URL (REQUIRED for Production)
**Format:** `https://subdomain.domain.com` (NO trailing slash)

```bash
# ✅ CORRECT FORMAT
FRONTEND_URL=https://frontend-production-18bb.up.railway.app
QUIZ_URL=https://quiz-production-xyz.up.railway.app

# ❌ WRONG FORMATS
FRONTEND_URL=https:frontend-production-18bb.up.railway.app  # Missing //
FRONTEND_URL=https://frontend.com/                          # Trailing slash
FRONTEND_URL=http://frontend.com                            # HTTP in production
```

#### ALLOWED_ORIGINS (Optional Override)
**Format:** Comma-separated list of full URLs

```bash
# ✅ CORRECT (comma-separated, no spaces, no trailing slashes)
ALLOWED_ORIGINS=https://frontend-production.up.railway.app,https://quiz-production.up.railway.app,https://app.hormonia.io

# ❌ WRONG FORMATS
ALLOWED_ORIGINS=https:frontend.com,https://quiz.com         # Missing // on first URL
ALLOWED_ORIGINS=https://frontend.com/, https://quiz.com     # Trailing slash and spaces
ALLOWED_ORIGINS=["https://frontend.com","https://quiz.com"] # JSON format (not supported)
```

**How CORS Works:**
- **Production Mode (`ENVIRONMENT=production`):**
  - Uses explicit domain list from `FRONTEND_URL` + `QUIZ_URL`
  - If `ALLOWED_ORIGINS` is set, it overrides auto-detection
  - All URLs must use `https://` protocol

- **Development Mode (`ENVIRONMENT=development`):**
  - Uses regex pattern: `^https?://(localhost|127\.0\.0\.1)(:\d+)?$`
  - Allows any port on localhost/127.0.0.1
  - Both HTTP and HTTPS allowed

---

### 🔴 3. Redis Configuration

#### REDIS_URL (REQUIRED)
**Format:** `rediss://default:PASSWORD@HOST:PORT` (note the double 's' in `rediss://`)

```bash
# ✅ CORRECT FORMAT (rediss:// with SSL)
REDIS_URL=rediss://default:password@redis-12345.railway.app:6379

# ❌ WRONG (redis:// without SSL in production)
REDIS_URL=redis://default:password@redis-12345.railway.app:6379
```

**Additional Redis Settings:**
```bash
ENABLE_REDIS=true                    # Enable/disable Redis
REDIS_SSL=true                       # Enable SSL (required for production)
REDIS_SSL_CERT_REQS=required         # Certificate validation: required|optional|none
REDIS_MAX_CONNECTIONS=50             # Connection pool size
REDIS_SOCKET_TIMEOUT=10.0            # Socket timeout (seconds)
REDIS_SOCKET_CONNECT_TIMEOUT=5.0     # Connection timeout (seconds)
REDIS_HEALTH_CHECK_INTERVAL=30       # Health check interval (seconds)

# Database isolation (0-15 available)
REDIS_CACHE_DB=1                     # Application cache
REDIS_BROKER_DB=0                    # Celery broker
REDIS_SESSION_DB=2                   # User sessions
REDIS_RATE_LIMIT_DB=3                # Rate limiting
```

---

### 🔄 4. Celery Configuration

#### CELERY_BROKER_URL and CELERY_RESULT_BACKEND
**Format:** Same as REDIS_URL with `/DB_NUMBER` suffix

```bash
# ✅ CORRECT FORMAT (rediss:// with SSL and DB number)
CELERY_BROKER_URL=rediss://default:password@redis-12345.railway.app:6379/0
CELERY_RESULT_BACKEND=rediss://default:password@redis-12345.railway.app:6379/0

# ❌ WRONG (redis:// without SSL)
CELERY_BROKER_URL=redis://default:password@redis-12345.railway.app:6379/0
```

**Celery Worker Settings:**
```bash
CELERY_WORKER_CONCURRENCY=4          # Number of worker processes
CELERY_WORKER_MAX_TASKS_PER_CHILD=1000
CELERY_WORKER_TIME_LIMIT=300         # Hard timeout (seconds)
CELERY_WORKER_SOFT_TIME_LIMIT=240    # Soft timeout (seconds)
CELERY_QUEUES=celery,flows,quiz,maintenance,monitoring
```

---

### 🔑 5. Firebase Authentication

#### Firebase Credentials (REQUIRED)
```bash
# Firebase project configuration
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_STORAGE_BUCKET=your-project.appspot.com

# Firebase Admin SDK (JSON string or base64)
FIREBASE_CREDENTIALS={"type":"service_account","project_id":"..."}
# OR base64 encoded:
FIREBASE_CREDENTIALS_BASE64=eyJ0eXBlIjoic2VydmljZV9hY2NvdW50Ii...

# Firebase Web API Key
FIREBASE_WEB_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXX
```

**Important Notes:**
- `FIREBASE_CREDENTIALS` can be:
  1. JSON string (minified, no newlines)
  2. Base64-encoded JSON (use `FIREBASE_CREDENTIALS_BASE64`)
  3. Path to credentials file (not recommended on Railway)

---

### 🔐 6. Supabase Configuration

```bash
# Supabase project URL
SUPABASE_URL=https://your-project.supabase.co

# Supabase anonymous key (for client-side access)
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Supabase service role key (for server-side admin access)
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# JWT Secret (for verifying tokens)
SUPABASE_JWT_SECRET=your-jwt-secret-key-here
```

---

### 🔐 7. Security & Secrets

```bash
# Application secret key (generate with: openssl rand -hex 32)
SECRET_KEY=your-super-secret-key-at-least-32-characters-long

# JWT Configuration
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=30
JWT_REFRESH_EXPIRATION_DAYS=7

# API Keys
API_KEY=your-api-key-for-external-services
```

**Generate Secure Keys:**
```bash
# Python
python -c "import secrets; print(secrets.token_hex(32))"

# OpenSSL
openssl rand -hex 32

# Node.js
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

---

### ⚙️ 8. Application Configuration

```bash
# Environment mode
ENVIRONMENT=production               # production | development

# Debug mode (NEVER enable in production)
DEBUG=false

# Server configuration
PORT=8000                            # Application port
HOST=0.0.0.0                         # Bind to all interfaces

# Python configuration
PYTHONPATH=/app                      # Python module search path
PYTHONUNBUFFERED=1                   # Disable output buffering

# Logging
LOG_LEVEL=INFO                       # DEBUG | INFO | WARNING | ERROR | CRITICAL
```

---

## 📝 Complete .env Example for Railway Production

```bash
# ============================================================================
# RAILWAY PRODUCTION ENVIRONMENT VARIABLES
# ============================================================================

# ----------------------------------------------------------------------------
# 1. DATABASE (PostgreSQL + Supabase) - SSL REQUIRED
# ----------------------------------------------------------------------------
DATABASE_URL=postgresql+psycopg://postgres.xyz:PASSWORD@aws-0-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=40

# ----------------------------------------------------------------------------
# 2. REDIS (Cache + Celery) - SSL REQUIRED
# ----------------------------------------------------------------------------
ENABLE_REDIS=true
REDIS_URL=rediss://default:PASSWORD@redis-production.railway.app:6379
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required
REDIS_MAX_CONNECTIONS=50

# ----------------------------------------------------------------------------
# 3. CELERY (Background Tasks)
# ----------------------------------------------------------------------------
CELERY_BROKER_URL=rediss://default:PASSWORD@redis-production.railway.app:6379/0
CELERY_RESULT_BACKEND=rediss://default:PASSWORD@redis-production.railway.app:6379/0
CELERY_WORKER_CONCURRENCY=4

# ----------------------------------------------------------------------------
# 4. CORS CONFIGURATION - PROPER HTTPS:// FORMAT
# ----------------------------------------------------------------------------
ENVIRONMENT=production
FRONTEND_URL=https://frontend-production-18bb.up.railway.app
QUIZ_URL=https://quiz-production-xyz.up.railway.app
# Optional override:
# ALLOWED_ORIGINS=https://frontend-production.up.railway.app,https://quiz-production.up.railway.app

# ----------------------------------------------------------------------------
# 5. FIREBASE AUTHENTICATION
# ----------------------------------------------------------------------------
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_STORAGE_BUCKET=your-project.appspot.com
FIREBASE_CREDENTIALS={"type":"service_account","project_id":"..."}
FIREBASE_WEB_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXX

# ----------------------------------------------------------------------------
# 6. SUPABASE
# ----------------------------------------------------------------------------
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_JWT_SECRET=your-jwt-secret

# ----------------------------------------------------------------------------
# 7. SECURITY & SECRETS
# ----------------------------------------------------------------------------
SECRET_KEY=generate-with-openssl-rand-hex-32
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ALGORITHM=HS256

# ----------------------------------------------------------------------------
# 8. APPLICATION
# ----------------------------------------------------------------------------
DEBUG=false
PORT=8000
PYTHONPATH=/app
PYTHONUNBUFFERED=1
LOG_LEVEL=INFO
```

---

## 🔍 Validation Checklist

### Before Deploying to Railway:

- [ ] **DATABASE_URL** includes `?sslmode=require` parameter
- [ ] **REDIS_URL** uses `rediss://` (double 's') protocol
- [ ] **CELERY_BROKER_URL** uses `rediss://` protocol
- [ ] **CELERY_RESULT_BACKEND** uses `rediss://` protocol
- [ ] **FRONTEND_URL** uses `https://` (not `https:`)
- [ ] **QUIZ_URL** uses `https://` (not `https:`)
- [ ] **ALLOWED_ORIGINS** has no trailing slashes
- [ ] **ALLOWED_ORIGINS** has proper `https://` protocol
- [ ] **ENVIRONMENT** set to `production`
- [ ] **DEBUG** set to `false`
- [ ] **SECRET_KEY** is at least 32 characters
- [ ] **FIREBASE_CREDENTIALS** is valid JSON or base64
- [ ] All passwords are properly URL-encoded
- [ ] No spaces in comma-separated lists
- [ ] No trailing slashes in URLs

---

## 🚀 Testing Your Configuration

### 1. Check Database Connection
```bash
curl https://your-backend.railway.app/api/v1/health/database
```

Expected response:
```json
{
  "status": "healthy",
  "details": {
    "connection_time_ms": 45,
    "database_url_configured": true
  }
}
```

### 2. Check Redis Connection
```bash
curl https://your-backend.railway.app/api/v1/health/redis
```

### 3. Check CORS Configuration
```bash
curl https://your-backend.railway.app/api/v1/health/cors
```

Expected response:
```json
{
  "cors_mode": "production",
  "allowed_origins": [
    "https://frontend-production-18bb.up.railway.app",
    "https://quiz-production-xyz.up.railway.app"
  ],
  "allow_credentials": false
}
```

### 4. Test CORS Preflight
```bash
curl -X OPTIONS https://your-backend.railway.app/api/v1/health \
  -H "Origin: https://frontend-production-18bb.up.railway.app" \
  -H "Access-Control-Request-Method: GET" \
  -v
```

Look for these headers in response:
- `Access-Control-Allow-Origin: https://frontend-production-18bb.up.railway.app`
- `Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS`

---

## 🐛 Troubleshooting

### SSL Connection Errors
**Error:** `SSL connection has been closed unexpectedly`

**Solution:**
1. Add `?sslmode=require` to DATABASE_URL
2. Verify SSL certificate validation: `REDIS_SSL_CERT_REQS=required`
3. Check that `rediss://` (double 's') is used for Redis

### CORS Errors
**Error:** `CORS policy: No 'Access-Control-Allow-Origin' header`

**Solution:**
1. Verify `FRONTEND_URL` has proper `https://` format (not `https:`)
2. Check `ALLOWED_ORIGINS` has no trailing slashes
3. Verify `ENVIRONMENT=production` is set
4. Check Railway logs: `Allowed origins: [...]`

### Authentication Timeouts
**Error:** `Request timed out during Firebase verification`

**Solution:**
1. Verify `FIREBASE_CREDENTIALS` is valid JSON
2. Check `FIREBASE_PROJECT_ID` matches your Firebase project
3. Increase timeout: Add `FIREBASE_TIMEOUT=30` to env vars
4. Review logs for specific Firebase errors

### Redis Connection Issues
**Error:** `ConnectionError: Error connecting to Redis`

**Solution:**
1. Verify `REDIS_URL` uses `rediss://` protocol
2. Check `REDIS_SSL=true` is set
3. Verify Redis service is running on Railway
4. Test connection with health endpoint

---

## 📚 Additional Resources

- [Railway Environment Variables Guide](https://docs.railway.app/guides/variables)
- [Supabase Connection Strings](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Redis SSL/TLS Configuration](https://redis.io/docs/manual/security/encryption/)
- [FastAPI CORS Documentation](https://fastapi.tiangolo.com/tutorial/cors/)
- [Celery Configuration](https://docs.celeryq.dev/en/stable/userguide/configuration.html)

---

## 📞 Support

For issues or questions:
1. Check Railway logs: `railway logs`
2. Verify health endpoints: `/api/v1/health/*`
3. Review environment variables in Railway dashboard
4. Check this guide for proper formatting

Last Updated: 2025-10-07
Version: 1.0.0
