# Railway Deployment Guide - Backend FastAPI

## Overview
This guide covers deploying the Hormonia Backend FastAPI application to Railway production environment.

## Pre-Deployment Checklist

### 1. Required Environment Variables

**Critical Production Variables:**
```bash
# Application
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<generate-secure-random-key>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Database (Supabase PostgreSQL)
DATABASE_URL=<supabase-connection-string>
SUPABASE_URL=<supabase-project-url>
SUPABASE_ANON_KEY=<supabase-anon-key>
SUPABASE_SERVICE_ROLE_KEY=<supabase-service-role-key>

# Redis (Required for caching and Celery)
REDIS_URL=<redis-connection-string>
REDIS_PASSWORD=<redis-password>
REDIS_HOST=<redis-host>
REDIS_PORT=<redis-port>
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required

# CORS Configuration
ALLOWED_ORIGINS=["https://<frontend-domain>.railway.app","https://<quiz-domain>.railway.app"]

# Optional: Custom API URL for frontend
FRONTEND_API_URL=https://<backend-domain>.railway.app
RAILWAY_PUBLIC_DOMAIN=<backend-domain>.railway.app
```

**Optional but Recommended:**
```bash
# AI Services
GEMINI_API_KEY=<google-gemini-api-key>
GEMINI_MODEL=gemini-2.5-flash-preview-09-2025

# Evolution API (WhatsApp)
ENABLE_EVOLUTION=true
EVOLUTION_API_URL=<evolution-api-url>
EVOLUTION_API_KEY=<evolution-api-key>
EVOLUTION_INSTANCE_NAME=<instance-name>

# Monitoring
MONITORING_ENABLED=true
LOG_LEVEL=INFO
SENTRY_DSN=<sentry-dsn>
```

### 2. CORS Configuration for Railway

**Important:** Railway assigns dynamic domains. Configure CORS to support Railway patterns:

**Option 1: Explicit URLs (Most Secure)**
```bash
ALLOWED_ORIGINS=["https://frontend-production.up.railway.app","https://quiz-interface.up.railway.app","https://backend-production.up.railway.app"]
```

**Option 2: Environment Variable Override**
In Railway dashboard, set `ALLOWED_ORIGINS` as:
```json
["https://your-frontend.railway.app","https://your-quiz.railway.app"]
```

**Note:** The backend automatically adds WebSocket CORS headers for Railway domains.

### 3. Database Migrations

**Before deployment, ensure migrations are applied via Supabase:**

**All migrations are managed through Supabase Dashboard:**
- Navigate to Supabase Dashboard → SQL Editor
- 54 migrations already applied (see [../db/BANCO_DE_DADOS_COMPLETO.md](../db/BANCO_DE_DADOS_COMPLETO.md) for full history)
- Current schema documented in `../../SCHEMA_MASTER_COMPLETO.sql` (reference only)

**For new migrations:**
1. Create migration in Supabase Dashboard → SQL Editor
2. Test in development environment first
3. Apply to production via Dashboard
4. Document in migration history

**Python migrations (Alembic):**
```bash
# Apply Python-specific migrations (if any)
alembic upgrade head
```

**Important:** Do NOT use old migration files (`001_create_admin_tables.sql`, etc.) - these have been consolidated into Supabase migrations.
```bash
alembic upgrade head
```

### 4. Health Check Endpoints

**Verify these endpoints after deployment:**

```bash
# Primary health check (Railway uses this)
GET https://<domain>.railway.app/health

# Detailed health check
GET https://<domain>.railway.app/api/v1/health

# Configuration endpoint (verify VITE_ URLs)
GET https://<domain>.railway.app/config
GET https://<domain>.railway.app/api/v1/config

# Database health
GET https://<domain>.railway.app/api/v1/database/health

# Redis health
GET https://<domain>.railway.app/api/v1/redis/health
```

**Expected Response (Healthy):**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-01T19:00:00Z",
  "version": "2.0.0",
  "environment": "production"
}
```

### 5. Security Verification

**Post-Deployment Security Checks:**

1. **Verify SUPABASE_ANON_KEY is NOT exposed:**
   ```bash
   # This should NOT contain SUPABASE_ANON_KEY
   curl https://<domain>.railway.app/config
   ```
   ✅ Should return only: `VITE_API_BASE_URL`, `VITE_WS_BASE_URL`, `ENVIRONMENT`

2. **Verify CORS headers:**
   ```bash
   curl -H "Origin: https://your-frontend.railway.app" \
        -H "Access-Control-Request-Method: GET" \
        -X OPTIONS https://<domain>.railway.app/api/v1/patients
   ```
   ✅ Should return `Access-Control-Allow-Origin` header

3. **Verify HTTPS redirect:**
   ```bash
   curl -I http://<domain>.railway.app/health
   ```
   ✅ Should redirect to HTTPS (301/302)

### 6. Performance Testing

**Run performance tests before promoting to production:**

```bash
# Load test health endpoint
ab -n 1000 -c 10 https://<domain>.railway.app/health

# Test database connection pool
ab -n 100 -c 5 https://<domain>.railway.app/api/v1/database/health

# Monitor response times
curl -w "@curl-format.txt" -o /dev/null -s https://<domain>.railway.app/api/v1/health
```

**Expected Response Times:**
- `/health` - < 50ms
- `/api/v1/health` - < 200ms
- `/api/v1/database/health` - < 500ms

### 7. Pytest Coverage Requirements

**Before deployment, ensure test coverage > 80%:**

```bash
# Run tests with coverage
cd Backend
pytest --cov=app --cov-report=term --cov-report=html

# Minimum requirements:
# - Overall coverage: > 80%
# - Critical modules (auth, patients, flows): > 90%
# - API endpoints: > 85%
```

## Deployment Steps

### Step 1: Configure Railway Service

1. **Create Railway Service:**
   - Connect GitHub repository
   - Select `Backend` directory as root path
   - Set `PORT=8000` (Railway auto-assigns)

2. **Set Environment Variables:**
   - Add all required variables from checklist
   - Use Railway's secret management
   - Enable auto-deployment on main branch

### Step 2: Configure Build & Start Commands

**Railway Configuration:**
```json
{
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "pip install -r requirements.txt"
  },
  "deploy": {
    "startCommand": "gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 120",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 100,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

**Alternative: Use Procfile (in Backend directory)**
```
web: gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 120
```

### Step 3: Deploy and Monitor

```bash
# Deploy via Railway CLI
railway up

# Or push to main branch for auto-deployment
git push origin main

# Monitor deployment logs
railway logs --follow
```

### Step 4: Post-Deployment Verification

**Run full verification suite:**

```bash
# 1. Health checks
curl https://<domain>.railway.app/health
curl https://<domain>.railway.app/api/v1/database/health
curl https://<domain>.railway.app/api/v1/redis/health

# 2. Configuration endpoint
curl https://<domain>.railway.app/config | jq

# 3. Authentication flow
curl -X POST https://<domain>.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}'

# 4. WebSocket connection
wscat -c wss://<domain>.railway.app/ws
```

## Rollback Procedure

**If deployment fails:**

1. **Immediate rollback via Railway dashboard:**
   - Navigate to Deployments
   - Select previous stable deployment
   - Click "Redeploy"

2. **Via Railway CLI:**
   ```bash
   railway rollback
   ```

3. **Emergency fix:**
   - Set `ENVIRONMENT=development` temporarily
   - Enable debug endpoints: `ENABLE_DEBUG_ENDPOINTS=true`
   - Check `/debug/env` and `/debug/health`

## Troubleshooting

### Common Issues

**1. Database Connection Failures**
```bash
# Check DATABASE_URL format
echo $DATABASE_URL | grep -o "postgresql://.*"

# Verify Supabase connection pooler
# Should use port 6543 (pooler) not 5432 (direct)
```

**2. Redis Connection Errors**
```bash
# Check Redis SSL configuration
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required

# Test Redis connection
redis-cli -u $REDIS_URL ping
```

**3. CORS Errors**
```bash
# Add frontend domain to ALLOWED_ORIGINS
# Railway format: https://<service>.railway.app
ALLOWED_ORIGINS=["https://frontend.railway.app"]
```

**4. 502 Bad Gateway**
```bash
# Check worker timeout
# Increase in start command:
--timeout 120

# Check memory limits in Railway dashboard
# Recommended: 1GB+ for production
```

## Monitoring

**Set up monitoring endpoints:**

```bash
# Prometheus metrics
GET https://<domain>.railway.app/metrics

# Application performance
GET https://<domain>.railway.app/api/v1/monitoring/apm

# Resource usage
GET https://<domain>.railway.app/api/v1/monitoring/resources
```

**Configure alerts:**
- CPU > 80% for 5 minutes
- Memory > 85% for 5 minutes
- Response time > 2s for 1 minute
- Error rate > 5% for 2 minutes

## Support

**For issues:**
1. Check Railway logs: `railway logs --follow`
2. Review health endpoints
3. Check Supabase logs
4. Contact DevOps team

---

**Last Updated:** 2025-10-01
**Version:** 2.0.0
