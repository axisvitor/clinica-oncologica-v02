# Railway Environment Variables - REQUIRED

**Status:** 🚨 URGENT - Application won't start without these
**Date:** 2025-10-05

## 🚨 Critical Missing Variables

The application is currently failing to start in Railway due to missing security environment variables.

### Error Message
```
ValueError: Production environment security validation failed:
  - SESSION_COOKIE_SECURE must be True in production environment
  - SECURE_SSL_REDIRECT must be True in production environment
```

## ✅ Required Variables to Add in Railway

### 1. Security Settings (CRITICAL)

```bash
# Session Security
SESSION_COOKIE_SECURE=true

# SSL/HTTPS Redirect
SECURE_SSL_REDIRECT=true
```

### 2. Redis Configuration (WARNING FIX)

```bash
# Current Warning: "REDIS_SSL=True but URL doesn't use rediss://"
# Solution: Set REDIS_SSL to false OR change URL to rediss://

# Option 1: Disable SSL (if Redis Cloud port doesn't use SSL)
REDIS_SSL=false

# Option 2: Use SSL URL (if Redis Cloud port uses SSL)
REDIS_URL=rediss://default:PASSWORD@HOST:PORT
REDIS_SSL=true
```

## 📋 Complete Railway Environment Variables Checklist

### Security (REQUIRED in Production)
- [ ] `SESSION_COOKIE_SECURE=true`
- [ ] `SECURE_SSL_REDIRECT=true`
- [ ] `DEBUG=false`

### Redis (REQUIRED)
- [ ] `ENABLE_REDIS=true`
- [ ] `REDIS_URL=redis://...` (or rediss:// for SSL)
- [ ] `REDIS_PASSWORD=your_password`
- [ ] `REDIS_HOST=your_host`
- [ ] `REDIS_PORT=your_port`
- [ ] `REDIS_SSL=false` (or true if using rediss://)
- [ ] `REDIS_SSL_CERT_REQS=none`
- [ ] `REDIS_MAX_CONNECTIONS=50`
- [ ] `REDIS_SOCKET_TIMEOUT=10.0`
- [ ] `REDIS_SOCKET_CONNECT_TIMEOUT=5.0`
- [ ] `REDIS_RETRY_ON_TIMEOUT=true`
- [ ] `REDIS_HEALTH_CHECK_INTERVAL=30`

### Database (REQUIRED)
- [ ] `DATABASE_URL=postgresql+psycopg://...`
- [ ] `DB_POOL_SIZE=20`
- [ ] `DB_MAX_OVERFLOW=10`

### Application (REQUIRED)
- [ ] `ENVIRONMENT=production`
- [ ] `SECRET_KEY=your_secret_key`
- [ ] `JWT_SECRET_KEY=your_jwt_secret`

### Celery (if using background tasks)
- [ ] `CELERY_BROKER_URL=redis://...`
- [ ] `CELERY_RESULT_BACKEND=redis://...`

## 🚀 How to Add Variables in Railway

### Via Railway Dashboard:
1. Go to your project in Railway
2. Select the backend service
3. Click on "Variables" tab
4. Click "Add Variable" or "Raw Editor"
5. Add the variables listed above
6. Click "Deploy" to restart with new variables

### Via Railway CLI:
```bash
# Set individual variables
railway variables set SESSION_COOKIE_SECURE=true
railway variables set SECURE_SSL_REDIRECT=true
railway variables set REDIS_SSL=false

# Or import from .env file
railway variables set --from-env-file .env
```

## 🔍 Current Issues & Solutions

### Issue 1: SESSION_COOKIE_SECURE Missing
**Error:** `SESSION_COOKIE_SECURE must be True in production`
**Solution:** Add `SESSION_COOKIE_SECURE=true` to Railway variables

### Issue 2: SECURE_SSL_REDIRECT Missing
**Error:** `SECURE_SSL_REDIRECT must be True in production`
**Solution:** Add `SECURE_SSL_REDIRECT=true` to Railway variables

### Issue 3: Redis SSL Mismatch
**Warning:** `REDIS_SSL=True but URL doesn't use rediss://`
**Solution:** Set `REDIS_SSL=false` (most Redis Cloud instances don't use SSL on standard ports)

## 📝 Minimal Working Configuration

If you just want to get the app running quickly, add these **minimum** variables:

```bash
# Security (minimum required)
SESSION_COOKIE_SECURE=true
SECURE_SSL_REDIRECT=true
DEBUG=false
ENVIRONMENT=production

# Redis (fix SSL warning)
REDIS_SSL=false

# The rest should already be configured
```

## ⚠️ Important Notes

1. **SESSION_COOKIE_SECURE=true**: Requires HTTPS (Railway provides this automatically)
2. **SECURE_SSL_REDIRECT=true**: Redirects HTTP to HTTPS (Railway handles this)
3. **REDIS_SSL=false**: Most Redis Cloud free tier instances don't use SSL
4. **Don't commit secrets**: Never commit .env files with real credentials to git

## 🔗 Documentation Links

- [Railway Environment Variables](https://docs.railway.app/develop/variables)
- [Railway CLI](https://docs.railway.app/develop/cli)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

## 📊 Validation Checklist

After adding variables, verify:
- [ ] Application starts without errors
- [ ] No security validation errors in logs
- [ ] Redis connects successfully (no SSL warnings)
- [ ] HTTPS redirects work
- [ ] Session cookies are secure

---

**Last Updated:** 2025-10-05
**Status:** 🚨 URGENT - Required for deployment
