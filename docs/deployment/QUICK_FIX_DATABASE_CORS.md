# Quick Fix: DATABASE_URL SSL and CORS Configuration Issues

## 🚨 Two Critical Issues to Fix Immediately

### Issue 1: DATABASE_URL Missing SSL Mode ⚠️

**Current (WRONG):**
```bash
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/postgres
```

**Error You're Getting:**
```
psycopg.OperationalError: SSL connection has been closed unexpectedly
```

**Fix (CORRECT):**
```bash
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/postgres?sslmode=require
```

**What Changed:** Added `?sslmode=require` at the end

---

### Issue 2: CORS Origins Missing `//` After `https:` ⚠️

**Current Logs Show:**
```
Allowed origins: ['https:frontend-production-18bb...']
```

**Problem:** Missing `//` after `https:` - should be `https://`

**Fix (CORRECT):**
```bash
FRONTEND_URL=https://frontend-production-18bb.up.railway.app
QUIZ_URL=https://quiz-production-xyz.up.railway.app
ALLOWED_ORIGINS=https://frontend-production.up.railway.app,https://quiz-production.up.railway.app
```

**What Changed:**
- Changed `https:frontend...` to `https://frontend...`
- Added `//` after the colon in protocol

---

## ✅ Railway Environment Variables Checklist

### 1. Database Configuration
```bash
# Add ?sslmode=require to your DATABASE_URL
DATABASE_URL=postgresql+psycopg://postgres.rszpypytdciggybbpnrp:PASSWORD@aws-0-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require
```

### 2. CORS Configuration
```bash
# Ensure proper https:// format (not https:)
ENVIRONMENT=production
FRONTEND_URL=https://frontend-production-18bb.up.railway.app
QUIZ_URL=https://quiz-production-xyz.up.railway.app
```

### 3. Redis Configuration
```bash
# Use rediss:// (double 's') for SSL
REDIS_URL=rediss://default:PASSWORD@redis-host:6379
CELERY_BROKER_URL=rediss://default:PASSWORD@redis-host:6379/0
CELERY_RESULT_BACKEND=rediss://default:PASSWORD@redis-host:6379/0
```

---

## 🔧 How to Apply Fixes on Railway

### Method 1: Railway Dashboard (Recommended)

1. **Go to Railway Dashboard**
   - Navigate to your project
   - Click on your backend service
   - Go to "Variables" tab

2. **Fix DATABASE_URL**
   - Find `DATABASE_URL` variable
   - Click "Edit"
   - Add `?sslmode=require` to the end of the URL
   - Click "Save"

3. **Fix CORS Variables**
   - Find `FRONTEND_URL` variable
   - Verify it has `https://` (not `https:`)
   - Repeat for `QUIZ_URL`
   - If you have `ALLOWED_ORIGINS`, verify it's comma-separated with no spaces

4. **Deploy Changes**
   - Railway will automatically redeploy when you save variables
   - Wait 2-3 minutes for deployment

### Method 2: Railway CLI

```bash
# Set DATABASE_URL with SSL
railway variables set DATABASE_URL="postgresql+psycopg://user:pass@host:5432/postgres?sslmode=require"

# Set CORS variables
railway variables set FRONTEND_URL="https://frontend-production-18bb.up.railway.app"
railway variables set QUIZ_URL="https://quiz-production-xyz.up.railway.app"
railway variables set ALLOWED_ORIGINS="https://frontend-production.up.railway.app,https://quiz-production.up.railway.app"

# Redeploy
railway up
```

---

## 🧪 Verify Fixes

### 1. Check Database Connection
```bash
curl https://your-backend.railway.app/api/v1/health/database
```

**Expected (Success):**
```json
{
  "status": "healthy",
  "details": {
    "connection_time_ms": 45,
    "database_url_configured": true
  }
}
```

**Before Fix (Error):**
```json
{
  "status": "unhealthy",
  "error": "SSL connection has been closed unexpectedly"
}
```

### 2. Check CORS Configuration
```bash
curl https://your-backend.railway.app/api/v1/health/cors
```

**Expected (Success):**
```json
{
  "cors_mode": "production",
  "allowed_origins": [
    "https://frontend-production-18bb.up.railway.app",
    "https://quiz-production-xyz.up.railway.app"
  ]
}
```

**Before Fix (Error):**
```json
{
  "allowed_origins": [
    "https:frontend-production-18bb.up.railway.app"
  ]
}
```

### 3. Test Actual CORS Request
```bash
# Test from your frontend URL
curl -X OPTIONS https://your-backend.railway.app/api/v1/health \
  -H "Origin: https://frontend-production-18bb.up.railway.app" \
  -H "Access-Control-Request-Method: GET" \
  -v
```

**Expected Headers:**
```
< Access-Control-Allow-Origin: https://frontend-production-18bb.up.railway.app
< Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
< Access-Control-Allow-Headers: *
```

---

## 📋 Complete Environment Variables Template

Copy this and update with your actual values:

```bash
# ============================================================================
# DATABASE (MUST HAVE ?sslmode=require)
# ============================================================================
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=40

# ============================================================================
# REDIS (MUST USE rediss:// WITH DOUBLE 'S')
# ============================================================================
REDIS_URL=rediss://default:PASSWORD@HOST:6379
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required

# ============================================================================
# CELERY (MUST USE rediss:// WITH DOUBLE 'S')
# ============================================================================
CELERY_BROKER_URL=rediss://default:PASSWORD@HOST:6379/0
CELERY_RESULT_BACKEND=rediss://default:PASSWORD@HOST:6379/0

# ============================================================================
# CORS (MUST HAVE https:// NOT https:)
# ============================================================================
ENVIRONMENT=production
FRONTEND_URL=https://frontend-production-18bb.up.railway.app
QUIZ_URL=https://quiz-production-xyz.up.railway.app
# Optional (comma-separated, NO SPACES, NO TRAILING SLASHES):
ALLOWED_ORIGINS=https://frontend.up.railway.app,https://quiz.up.railway.app

# ============================================================================
# OTHER REQUIRED VARIABLES
# ============================================================================
DEBUG=false
SECRET_KEY=generate-with-openssl-rand-hex-32
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_CREDENTIALS={"type":"service_account"...}
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...
```

---

## 🚨 Common Mistakes to Avoid

### ❌ DATABASE_URL Mistakes
```bash
# WRONG - Missing sslmode
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/postgres

# WRONG - Using http:// or other protocols
DATABASE_URL=http://user:pass@host:5432/postgres

# CORRECT
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/postgres?sslmode=require
```

### ❌ CORS URL Mistakes
```bash
# WRONG - Missing //
FRONTEND_URL=https:frontend.com

# WRONG - Trailing slash
FRONTEND_URL=https://frontend.com/

# WRONG - Using http in production
FRONTEND_URL=http://frontend.com

# WRONG - Spaces in ALLOWED_ORIGINS
ALLOWED_ORIGINS=https://frontend.com, https://quiz.com

# CORRECT
FRONTEND_URL=https://frontend.com
ALLOWED_ORIGINS=https://frontend.com,https://quiz.com
```

### ❌ Redis URL Mistakes
```bash
# WRONG - Single 's' (no SSL)
REDIS_URL=redis://default:pass@host:6379

# CORRECT - Double 's' (with SSL)
REDIS_URL=rediss://default:pass@host:6379
```

---

## 📞 Still Having Issues?

### Check Railway Logs
```bash
railway logs
```

Look for:
- `SSL connection has been closed` → DATABASE_URL needs `?sslmode=require`
- `CORS policy: No 'Access-Control-Allow-Origin'` → Fix FRONTEND_URL format
- `Allowed origins: ['https:frontend...']` → Missing `//` in URL

### Health Check Endpoints
```bash
# Database health
curl https://your-backend.railway.app/api/v1/health/database

# Redis health
curl https://your-backend.railway.app/api/v1/health/redis

# CORS configuration
curl https://your-backend.railway.app/api/v1/health/cors

# Full system health
curl https://your-backend.railway.app/api/v1/health
```

---

## 📚 Related Documentation

For complete details, see:
- [RAILWAY_ENVIRONMENT_VARIABLES.md](./RAILWAY_ENVIRONMENT_VARIABLES.md) - Full environment variable guide
- [SSL_CERTIFICATE_SOLUTION.md](./SSL_CERTIFICATE_SOLUTION.md) - SSL troubleshooting
- [AUTHENTICATION_TIMEOUT_FIX.md](./AUTHENTICATION_TIMEOUT_FIX.md) - Auth issues

---

**Quick Reference Card:**

| Variable | Must Have | Example |
|----------|-----------|---------|
| DATABASE_URL | `?sslmode=require` | `postgresql+psycopg://...?sslmode=require` |
| REDIS_URL | `rediss://` (double s) | `rediss://default:pass@host:6379` |
| FRONTEND_URL | `https://` | `https://frontend.up.railway.app` |
| ALLOWED_ORIGINS | No spaces, no trailing / | `https://a.com,https://b.com` |

---

Last Updated: 2025-10-07
