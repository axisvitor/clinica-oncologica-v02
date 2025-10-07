# Environment Variables - Quick Reference Summary

## 📋 Critical Variables That Need Specific Formats

### 1. DATABASE_URL ⚠️ **Must have `?sslmode=require`**
```bash
# ✅ CORRECT
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db?sslmode=require

# ❌ WRONG (missing SSL mode)
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db
```

### 2. REDIS_URL ⚠️ **Must use `rediss://` (double 's')**
```bash
# ✅ CORRECT (with SSL)
REDIS_URL=rediss://default:password@host:6379

# ❌ WRONG (without SSL)
REDIS_URL=redis://default:password@host:6379
```

### 3. CELERY URLs ⚠️ **Must use `rediss://` (double 's')**
```bash
# ✅ CORRECT
CELERY_BROKER_URL=rediss://default:password@host:6379/0
CELERY_RESULT_BACKEND=rediss://default:password@host:6379/0

# ❌ WRONG
CELERY_BROKER_URL=redis://default:password@host:6379/0
```

### 4. FRONTEND_URL / QUIZ_URL ⚠️ **Must have `https://` (not `https:`)**
```bash
# ✅ CORRECT
FRONTEND_URL=https://frontend-production.up.railway.app
QUIZ_URL=https://quiz-production.up.railway.app

# ❌ WRONG (missing //)
FRONTEND_URL=https:frontend-production.up.railway.app

# ❌ WRONG (trailing slash)
FRONTEND_URL=https://frontend-production.up.railway.app/
```

### 5. ALLOWED_ORIGINS ⚠️ **Comma-separated, no spaces, no trailing slashes**
```bash
# ✅ CORRECT
ALLOWED_ORIGINS=https://frontend.up.railway.app,https://quiz.up.railway.app

# ❌ WRONG (spaces after comma)
ALLOWED_ORIGINS=https://frontend.up.railway.app, https://quiz.up.railway.app

# ❌ WRONG (trailing slashes)
ALLOWED_ORIGINS=https://frontend.up.railway.app/,https://quiz.up.railway.app/
```

---

## 📝 Complete Variable List for Railway Production

### Required Variables
```bash
# Database
DATABASE_URL=postgresql+psycopg://...?sslmode=require
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=40

# Redis
REDIS_URL=rediss://default:PASSWORD@HOST:6379
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required

# Celery
CELERY_BROKER_URL=rediss://default:PASSWORD@HOST:6379/0
CELERY_RESULT_BACKEND=rediss://default:PASSWORD@HOST:6379/0

# CORS
ENVIRONMENT=production
FRONTEND_URL=https://frontend-production.up.railway.app
QUIZ_URL=https://quiz-production.up.railway.app
ALLOWED_ORIGINS=https://frontend.up.railway.app,https://quiz.up.railway.app

# Security
SECRET_KEY=<generate-with-openssl-rand-hex-32>
JWT_SECRET_KEY=<your-jwt-secret>
DEBUG=false

# Firebase
FIREBASE_PROJECT_ID=<your-project-id>
FIREBASE_CREDENTIALS=<json-string-or-base64>
FIREBASE_WEB_API_KEY=<your-api-key>

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=<your-anon-key>
SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>
SUPABASE_JWT_SECRET=<your-jwt-secret>

# Application
PORT=8000
PYTHONPATH=/app
PYTHONUNBUFFERED=1
LOG_LEVEL=INFO
```

---

## 🔍 Validation Quick Check

### Run This in Railway Dashboard

1. **Check DATABASE_URL**
   - Must end with `?sslmode=require`
   - Should start with `postgresql+psycopg://`

2. **Check REDIS_URL**
   - Must start with `rediss://` (double 's')
   - Must NOT start with `redis://` (single 's')

3. **Check CELERY URLs**
   - Both must start with `rediss://`
   - Both must end with `/0` (database number)

4. **Check CORS URLs**
   - Must start with `https://` (not `https:`)
   - Must NOT end with `/` (no trailing slash)

5. **Check ALLOWED_ORIGINS**
   - No spaces after commas
   - No trailing slashes
   - All URLs start with `https://`

---

## 🧪 Test Commands

### Test Database Connection
```bash
curl https://your-backend.railway.app/api/v1/health/database
```

### Test CORS Configuration
```bash
curl https://your-backend.railway.app/api/v1/health/cors
```

### Test Redis Connection
```bash
curl https://your-backend.railway.app/api/v1/health/redis
```

### Test Full System
```bash
curl https://your-backend.railway.app/api/v1/health
```

---

## 📚 Documentation References

| Document | Purpose |
|----------|---------|
| [RAILWAY_ENVIRONMENT_VARIABLES.md](./RAILWAY_ENVIRONMENT_VARIABLES.md) | Complete guide with all details |
| [QUICK_FIX_DATABASE_CORS.md](./QUICK_FIX_DATABASE_CORS.md) | Quick fix for current issues |
| [SSL_CERTIFICATE_SOLUTION.md](./SSL_CERTIFICATE_SOLUTION.md) | SSL troubleshooting |
| [AUTHENTICATION_TIMEOUT_FIX.md](./AUTHENTICATION_TIMEOUT_FIX.md) | Auth timeout fixes |

---

## ⚡ Common Errors and Solutions

| Error | Cause | Fix |
|-------|-------|-----|
| `SSL connection has been closed` | Missing `?sslmode=require` | Add to DATABASE_URL |
| `CORS policy: No Access-Control-Allow-Origin` | Wrong FRONTEND_URL format | Change `https:` to `https://` |
| `ConnectionError: Error connecting to Redis` | Using `redis://` instead of `rediss://` | Add extra 's' to protocol |
| `Allowed origins: ['https:frontend...']` | Missing `//` in URL | Fix to `https://frontend...` |

---

Last Updated: 2025-10-07
Version: 1.0.0
