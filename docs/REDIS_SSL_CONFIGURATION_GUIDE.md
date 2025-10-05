# 🔐 Redis SSL/TLS Configuration Guide - Complete Reference

## 📋 Table of Contents
1. [Overview](#overview)
2. [Critical Security Changes](#critical-security-changes)
3. [Environment Files Updated](#environment-files-updated)
4. [Configuration Parameters](#configuration-parameters)
5. [Railway Deployment Steps](#railway-deployment-steps)
6. [Verification & Testing](#verification-testing)
7. [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

This guide documents the comprehensive Redis SSL/TLS configuration updates across all environment files in the project. These changes ensure secure, encrypted connections to Redis Cloud in production environments.

### What Changed?
- ✅ All `redis://` URLs changed to `rediss://` (SSL/TLS)
- ✅ SSL certificate validation enabled (`REDIS_SSL_CERT_REQS=required`)
- ✅ Explicit SSL context for async Redis clients (fixed "[SSL] record layer failure")
- ✅ Consistent configuration across all deployment templates

---

## 🚨 Critical Security Changes

### Before (INSECURE):
```bash
REDIS_URL=redis://default:PASSWORD@HOST:PORT  # ❌ Unencrypted
REDIS_SSL_CERT_REQS=none  # ❌ No certificate validation
```

### After (SECURE):
```bash
REDIS_URL=rediss://default:PASSWORD@HOST:PORT  # ✅ Encrypted with SSL/TLS
REDIS_SSL_CERT_REQS=required  # ✅ Certificate validation enabled
```

### Why This Matters:
1. **Data Encryption**: All Redis data in transit is now encrypted
2. **Certificate Validation**: Prevents man-in-the-middle attacks
3. **Compliance**: Meets security standards for healthcare data (LGPD)
4. **Production Ready**: Proper SSL/TLS for Railway deployment

---

## 📁 Environment Files Updated

### 1. Production Environment (HIGH PRIORITY)
**File**: `backend-hormonia/.env`
- ✅ Changed `REDIS_SSL_CERT_REQS` from `"none"` to `"required"`
- ⚠️ **Action Required**: Update Railway environment variables

### 2. Template Files (MEDIUM PRIORITY)
Updated for future deployments and developer onboarding:

**File**: `backend-hormonia/.env.example`
```bash
# Before
REDIS_URL=redis://default:YOUR_PASSWORD@YOUR_HOST:YOUR_PORT
REDIS_SSL=false
REDIS_SSL_CERT_REQS=none

# After
REDIS_URL=rediss://default:YOUR_PASSWORD@YOUR_HOST:YOUR_PORT
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required
```

**File**: `backend-hormonia/.env.railway.template`
```bash
# Before
REDIS_URL=redis://default:REPLACE_WITH_REDIS_PASSWORD@...
REDIS_SSL_CERT_REQS=none

# After
REDIS_URL=rediss://default:REPLACE_WITH_REDIS_PASSWORD@...
REDIS_SSL_CERT_REQS=required
```

**File**: `backend-hormonia/worker/.env.example`
```bash
# Added new SSL configuration
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required
```

**File**: `backend-hormonia/beat/.env.example`
```bash
# Added new SSL configuration
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required
```

---

## ⚙️ Configuration Parameters

### Redis Connection Settings

| Parameter | Development | Production | Description |
|-----------|------------|------------|-------------|
| `REDIS_URL` | `redis://...` | `rediss://...` | Use `rediss://` for SSL/TLS |
| `REDIS_SSL` | `false` | `true` | Enable SSL/TLS encryption |
| `REDIS_SSL_CERT_REQS` | `none` | `required` | Certificate validation level |
| `CELERY_BROKER_URL` | `redis://...` | `rediss://...` | Celery broker with SSL |
| `CELERY_RESULT_BACKEND` | `redis://...` | `rediss://...` | Result backend with SSL |

### SSL Certificate Validation Modes

```bash
# Development Only - NO certificate validation (INSECURE)
REDIS_SSL_CERT_REQS=none

# Optional - Validates if certificate is present
REDIS_SSL_CERT_REQS=optional

# Production - REQUIRED certificate validation (SECURE)
REDIS_SSL_CERT_REQS=required
```

### Complete Production Configuration
```bash
# ===================================
# REDIS PRODUCTION CONFIGURATION
# ===================================

# Primary Connection (use rediss:// for SSL)
REDIS_URL=rediss://default:YOUR_PASSWORD@YOUR_HOST:YOUR_PORT

# SSL/TLS Settings
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required  # CRITICAL: Certificate validation

# Connection Pool
REDIS_MAX_CONNECTIONS=25
REDIS_SOCKET_TIMEOUT=10.0

# Celery Configuration (also use rediss://)
CELERY_BROKER_URL=rediss://default:YOUR_PASSWORD@YOUR_HOST:YOUR_PORT/0
CELERY_RESULT_BACKEND=rediss://default:YOUR_PASSWORD@YOUR_HOST:YOUR_PORT/0
```

---

## 🚀 Railway Deployment Steps

### Step 1: Update Environment Variables in Railway Dashboard

Navigate to your Railway project → Backend service → Variables tab:

```bash
# Update these variables:
REDIS_URL=rediss://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149

CELERY_BROKER_URL=rediss://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0

CELERY_RESULT_BACKEND=rediss://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0

# Add new variables:
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required
AUTO_PROVISION_SUPABASE_USERS=true
```

### Step 2: Verify Deployment Logs

After Railway redeploys, check logs for:

✅ **Success Indicators:**
```
Redis async SSL: Certificate verification REQUIRED
Redis async SSL: Enabled with rediss:// scheme
Supabase client initialized successfully
```

❌ **Error Indicators (should NOT appear):**
```
[SSL] record layer failure
SSL handshake failed
```

### Step 3: Test Redis Connection

```bash
# In Railway backend logs, look for:
INFO:app.core.redis_manager:Redis async SSL: Certificate verification REQUIRED
INFO:app.core.redis_manager:Redis connection pool initialized successfully
```

---

## ✅ Verification & Testing

### 1. Verify SSL Configuration

```python
# Run this in Railway backend shell or local environment
python -c "
import ssl
from app.core.redis_manager import RedisManager
from app.config import settings

# Check SSL mode
print(f'REDIS_SSL: {settings.REDIS_SSL}')
print(f'REDIS_SSL_CERT_REQS: {settings.REDIS_SSL_CERT_REQS}')
print(f'REDIS_URL: {settings.REDIS_URL[:20]}...')  # Partial URL

# Test connection
redis_manager = RedisManager()
client = redis_manager.get_async_client()
print('✅ Async Redis client created successfully with SSL')
"
```

### 2. Test Celery Tasks

```bash
# Verify Celery can connect to Redis broker
celery -A app.celery_app inspect ping

# Expected output:
# -> celery@worker: OK
```

### 3. Monitor Dashboard

```bash
# Check monitoring system uses SSL
curl https://clinica-oncologica-v02-production.up.railway.app/api/v1/monitoring/health

# Look for Redis health check: "status": "healthy"
```

---

## 🔧 Troubleshooting

### Issue 1: "[SSL] record layer failure"

**Cause**: Async Redis client missing explicit SSL context

**Solution**: Already fixed in `redis_manager.py` (lines 111-151)
```python
# Explicit SSL context for async clients
ssl_context = ssl.create_default_context()
ssl_context.verify_mode = ssl.CERT_REQUIRED
connection_kwargs['ssl'] = ssl_context
```

**Verify**: Check Railway logs for:
```
Redis async SSL: Certificate verification REQUIRED
```

### Issue 2: "SSL: CERTIFICATE_VERIFY_FAILED"

**Cause**: Redis Cloud certificate not trusted

**Solution 1**: Verify `certifi` package is installed
```bash
pip show certifi
# Should show: certifi>=2023.7.22
```

**Solution 2**: Temporarily disable cert validation (DEV ONLY)
```bash
REDIS_SSL_CERT_REQS=none  # ⚠️ NEVER use in production
```

### Issue 3: Connection Timeout

**Cause**: Wrong URL scheme or firewall

**Checklist**:
- ✅ URL starts with `rediss://` (not `redis://`)
- ✅ Port 14149 is accessible
- ✅ Password is correct
- ✅ Redis Cloud instance is running

**Test Connection**:
```bash
# Test from Railway backend shell
redis-cli -h redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com \
  -p 14149 \
  -a 6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR \
  --tls \
  ping
# Expected: PONG
```

### Issue 4: "ModuleNotFoundError: No module named 'certifi'"

**Cause**: Missing SSL certificate bundle

**Solution**:
```bash
# Add to requirements.txt
certifi>=2023.7.22,<2025.0.0

# Install
pip install certifi
```

---

## 📊 Configuration Summary Table

| Environment File | Redis URL Scheme | SSL Enabled | Cert Validation | Status |
|-----------------|------------------|-------------|-----------------|---------|
| `backend-hormonia/.env` | `rediss://` | ✅ true | ✅ required | ✅ Updated |
| `backend-hormonia/.env.example` | `rediss://` | ✅ true | ✅ required | ✅ Updated |
| `backend-hormonia/.env.railway.template` | `rediss://` | ✅ true | ✅ required | ✅ Updated |
| `backend-hormonia/worker/.env.example` | `rediss://` | ✅ true | ✅ required | ✅ Updated |
| `backend-hormonia/beat/.env.example` | `rediss://` | ✅ true | ✅ required | ✅ Updated |
| `backend-hormonia/monitoring/.env.example` | `redis://` | ❌ false | ❌ n/a | ℹ️ Local Dev |

---

## 🔗 Related Documentation

- [HIVE_MIND_REDIS_ANALYSIS.md](./HIVE_MIND_REDIS_ANALYSIS.md) - Comprehensive Redis TLS analysis
- [RAILWAY_REDIS_SSL_FIX.md](./RAILWAY_REDIS_SSL_FIX.md) - Initial SSL troubleshooting
- [AUTO_PROVISIONING_SETUP.md](./AUTO_PROVISIONING_SETUP.md) - Firebase/Supabase sync guide

---

## 📝 Commit History

**Commit 1**: `fix(backend): Fix Redis async SSL/TLS failures and eliminate duplicate initializations`
- Fixed async Redis SSL context (critical fix)
- Updated all .env templates with rediss:// URLs
- Enabled SSL certificate validation

**Commit 2**: `docs(redis): Update all .env files with secure SSL/TLS configuration`
- Updated production .env with CERT_REQUIRED
- Updated all template files for consistency
- Created comprehensive configuration guide

---

## ✨ Best Practices

### Development Environment
```bash
# Local Redis without SSL
REDIS_URL=redis://localhost:6379
REDIS_SSL=false
REDIS_SSL_CERT_REQS=none
```

### Staging Environment
```bash
# Redis Cloud with SSL (optional cert validation)
REDIS_URL=rediss://default:PASSWORD@HOST:PORT
REDIS_SSL=true
REDIS_SSL_CERT_REQS=optional
```

### Production Environment
```bash
# Redis Cloud with SSL (required cert validation)
REDIS_URL=rediss://default:PASSWORD@HOST:PORT
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required  # MANDATORY
```

---

## 🎯 Deployment Checklist

Before deploying to Railway:

- [ ] Verified `.env` has `rediss://` URLs
- [ ] Set `REDIS_SSL_CERT_REQS=required` in Railway
- [ ] Updated `CELERY_BROKER_URL` to `rediss://`
- [ ] Updated `CELERY_RESULT_BACKEND` to `rediss://`
- [ ] Added `AUTO_PROVISION_SUPABASE_USERS=true`
- [ ] Verified `certifi` package in `requirements.txt`
- [ ] Pushed latest code to GitHub
- [ ] Monitored Railway deployment logs
- [ ] Verified "Redis async SSL: Certificate verification REQUIRED"
- [ ] Tested Celery tasks execution
- [ ] Checked monitoring dashboard health

---

**Last Updated**: 2025-10-05
**Authors**: Hive-Mind Multi-Agent System
**Version**: 2.0.0
**Status**: ✅ Production Ready
