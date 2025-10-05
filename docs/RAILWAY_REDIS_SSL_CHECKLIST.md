# Railway Redis SSL/TLS Deployment Checklist

**Last Updated**: 2025-10-05
**Status**: Production-Ready Guide
**Applies To**: Redis Cloud, Railway Redis, Python 3.13+

---

## 📋 Table of Contents

1. [Critical Port Verification](#1-critical-port-verification)
2. [Environment Variables Required](#2-environment-variables-required)
3. [Certificate Deployment Options](#3-certificate-deployment-options)
4. [Validation Steps](#4-validation-steps)
5. [Troubleshooting Guide](#5-troubleshooting-guide)
6. [Quick Reference](#6-quick-reference)

---

## 1. CRITICAL: Port Verification

### 🔴 Redis Cloud Port Types

Redis Cloud typically provides **TWO ports per database**:

| Port Type | Example | TLS Support | Use Case |
|-----------|---------|-------------|----------|
| **Standard Port** | 14149 | ❌ NO TLS | Non-SSL connections |
| **TLS Port** | 14150 | ✅ TLS 1.2/1.3 | SSL/TLS connections |

### ⚠️ How to Check Which Port Supports TLS

#### Method 1: OpenSSL Test (Recommended)
```bash
# Test for TLS support on port 14149
openssl s_client -connect redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149 -tls1_2

# Test for TLS support on port 14150
openssl s_client -connect redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14150 -tls1_2
```

**Expected Results**:
- **TLS Port**: Shows certificate details, connection established
- **Non-TLS Port**: `SSL handshake error` or connection refused

#### Method 2: Redis CLI Test
```bash
# Test non-TLS port (14149)
redis-cli -h redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com -p 14149 \
  -a YOUR_PASSWORD ping

# Test TLS port (14150) - requires --tls flag
redis-cli -h redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com -p 14150 \
  -a YOUR_PASSWORD --tls ping
```

#### Method 3: Redis Cloud Dashboard
1. Login to [Redis Cloud Console](https://app.redislabs.com/)
2. Select your database
3. Check **"Configuration"** tab:
   - **Public Endpoint**: Shows non-TLS port (e.g., 14149)
   - **SSL/TLS Endpoint**: Shows TLS port (if available)

### 🎯 Correct URL Format for Each Scenario

#### Scenario A: Port 14149 (No TLS Support)
```bash
# ✅ CORRECT
REDIS_URL=redis://default:PASSWORD@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149
REDIS_SSL=false
REDIS_SSL_CERT_REQS=none
```

#### Scenario B: Port 14150 (TLS Support)
```bash
# ✅ CORRECT
REDIS_URL=rediss://default:PASSWORD@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14150
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required
REDIS_SSL_MIN_VERSION=TLSV1_2
```

#### Scenario C: Mixed Setup (Legacy)
```bash
# If you must use non-TLS but want SSL flag (NOT RECOMMENDED)
REDIS_URL=redis://default:PASSWORD@host:14149
REDIS_SSL=false  # CRITICAL: Must be false
```

---

## 2. Environment Variables Required

### 📝 Complete Variable List

#### Core Redis Configuration
```bash
# Connection URL - CRITICAL: Use correct scheme (redis:// vs rediss://)
REDIS_URL=rediss://default:PASSWORD@HOST:PORT

# SSL/TLS Toggle - MUST match URL scheme
REDIS_SSL=true  # true if using rediss://, false if using redis://

# Certificate Validation Level
REDIS_SSL_CERT_REQS=required  # Options: none, optional, required

# TLS Version (for Python 3.13 + Redis Cloud compatibility)
REDIS_SSL_MIN_VERSION=TLSV1_2  # Options: TLSV1_2, TLSV1_3

# Optional: Custom CA Certificate Path
REDIS_SSL_CA_CERTS=certs/redis_ca.pem  # Leave empty to use certifi
```

#### Celery Configuration (if using Celery)
```bash
# Broker URL - MUST use same SSL settings as REDIS_URL
CELERY_BROKER_URL=rediss://default:PASSWORD@HOST:PORT/0

# Result Backend - MUST use same SSL settings
CELERY_RESULT_BACKEND=rediss://default:PASSWORD@HOST:PORT/1
```

### 🔐 SSL Certificate Requirements Options

| Setting | Value | Description | When to Use |
|---------|-------|-------------|-------------|
| `REDIS_SSL_CERT_REQS` | `none` | ⚠️ No certificate validation | Testing only, not production |
| `REDIS_SSL_CERT_REQS` | `optional` | Certificate validated if present | Transitional deployments |
| `REDIS_SSL_CERT_REQS` | `required` | ✅ Strict certificate validation | **Production (recommended)** |

### 🔧 TLS Version Configuration

**Why This Matters**: Python 3.13 + OpenSSL 3.x defaults to TLS 1.3, but some Redis Cloud instances require TLS 1.2.

```bash
# Force TLS 1.2 (most compatible with Redis Cloud)
REDIS_SSL_MIN_VERSION=TLSV1_2

# Allow TLS 1.3 (if Redis Cloud supports it)
REDIS_SSL_MIN_VERSION=TLSV1_3

# Auto-negotiate (default, may fail on some Redis Cloud instances)
# Leave empty or omit this variable
```

### 📦 Optional: Custom CA Certificate

```bash
# Option 1: Use certifi (automatic, recommended)
# No configuration needed - certifi is auto-detected

# Option 2: Custom CA certificate file
REDIS_SSL_CA_CERTS=certs/redis_ca.pem  # Relative to BASE_DIR

# Option 3: Absolute path
REDIS_SSL_CA_CERTS=/app/certs/redis_ca.pem
```

**Download Redis Cloud CA Certificate**:
1. Visit: https://redis.io/docs/latest/operate/rc/security/database-security/tls-ssl/
2. Download: `redis_ca.pem`
3. Upload to Railway:
   - Place in `backend-hormonia/certs/` directory
   - Commit to repository
   - Or mount as volume (Railway Volumes feature)

---

## 3. Certificate Deployment Options

### Option A: Using certifi (Automatic - Recommended)

**Advantages**:
- ✅ No manual certificate management
- ✅ Automatically updated with package updates
- ✅ Works with most SSL providers

**Setup**:

1. **Add to requirements.txt**:
```python
certifi>=2024.2.2,<2025.0.0  # CA certificates for Redis SSL
```

2. **Install**:
```bash
pip install certifi
```

3. **Environment Variables**:
```bash
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required
# No REDIS_SSL_CA_CERTS needed - certifi auto-detected
```

4. **Code handles it automatically** (already implemented in `redis_manager.py`):
```python
# Fallback to certifi if no custom CA specified
if not ssl_ca_certs:
    try:
        import certifi
        connection_kwargs['ssl_ca_certs'] = certifi.where()
        logger.info(f"Redis async SSL: Using certifi CA bundle: {certifi.where()}")
    except ImportError:
        logger.warning("Redis async SSL: certifi not available")
```

### Option B: Custom CA Certificate Upload

**Advantages**:
- ✅ Explicit certificate pinning
- ✅ Works in air-gapped environments
- ✅ Version control friendly

**Setup**:

1. **Download Certificate**:
```bash
# From Redis Cloud dashboard or documentation
curl -o redis_ca.pem https://redis.io/path/to/ca/cert.pem
```

2. **Create Directory Structure**:
```bash
mkdir -p backend-hormonia/certs
mv redis_ca.pem backend-hormonia/certs/
```

3. **Update .gitignore** (if certificate has secrets):
```bash
# Add to .gitignore
certs/*.pem
!certs/redis_ca.pem  # Allow public CA cert
```

4. **Configure Environment**:
```bash
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required
REDIS_SSL_CA_CERTS=certs/redis_ca.pem  # Relative path
```

5. **Deploy to Railway**:
```bash
git add certs/redis_ca.pem
git commit -m "Add Redis Cloud CA certificate"
git push
```

### Option C: Railway Volumes (For Sensitive Certificates)

**Use when**: Certificate contains secrets or is dynamically rotated

1. **Create Railway Volume**:
```bash
railway volumes create redis-certs --mount /app/certs
```

2. **Upload Certificate via Railway CLI**:
```bash
railway run --volume redis-certs:/app/certs cp local_redis_ca.pem /app/certs/
```

3. **Configure Environment**:
```bash
REDIS_SSL_CA_CERTS=/app/certs/redis_ca.pem  # Absolute path in volume
```

---

## 4. Validation Steps

### ✅ Pre-Deployment Checklist

#### Step 1: Verify Port and TLS Support
```bash
# Test with OpenSSL
openssl s_client -connect YOUR_REDIS_HOST:YOUR_PORT -tls1_2

# Expected: Certificate details and "Verify return code: 0 (ok)"
```

#### Step 2: Validate Environment Variables
```bash
# Check Railway environment
railway variables

# Verify:
# ✅ REDIS_URL scheme matches REDIS_SSL (rediss:// = true, redis:// = false)
# ✅ REDIS_SSL_CERT_REQS is set (none/optional/required)
# ✅ REDIS_SSL_MIN_VERSION is set for Python 3.13
```

#### Step 3: Test Connection Locally (Optional)
```python
# test_redis_connection.py
import redis
import ssl

url = "rediss://default:PASSWORD@HOST:PORT"
client = redis.from_url(
    url,
    ssl_cert_reqs=ssl.CERT_REQUIRED,
    ssl_min_version=ssl.TLSVersion.TLSv1_2
)
print(client.ping())  # Should return True
```

### 📊 Expected Log Messages for Success

#### With TLS (rediss://) + CERT_NONE
```log
INFO - Redis async SSL: Certificate verification DISABLED (CERT_NONE)
INFO - Async Redis client connected successfully
```

#### With TLS (rediss://) + CERT_REQUIRED + certifi
```log
INFO - Redis async SSL: Using certifi CA bundle: /path/to/certifi/cacert.pem
INFO - Redis async SSL: Certificate verification REQUIRED
INFO - Async Redis client connected successfully
```

#### With TLS (rediss://) + CERT_REQUIRED + Custom CA
```log
INFO - Redis async SSL: Using CA certificate from certs/redis_ca.pem
INFO - Redis async SSL: Certificate verification REQUIRED
INFO - Async Redis client connected successfully
```

#### Without TLS (redis://)
```log
INFO - Redis async: Using non-SSL connection
INFO - Async Redis client connected successfully
```

### 🔍 Health Check Endpoints to Test

#### 1. Backend Health Check
```bash
curl https://YOUR_RAILWAY_DOMAIN.railway.app/health

# Expected Response:
{
  "status": "healthy",
  "timestamp": "2025-10-05T...",
  "services": {
    "redis": {
      "status": "healthy",
      "async_ping": true,
      "sync_ping": true
    }
  }
}
```

#### 2. Redis-Specific Health Check
```bash
curl https://YOUR_RAILWAY_DOMAIN.railway.app/api/v1/health/redis

# Expected Response:
{
  "status": "healthy",
  "redis_url": "rediss://***@HOST:PORT",
  "max_connections": 50,
  "ssl_enabled": true
}
```

#### 3. Celery Worker Status (if using Celery)
```bash
# Check Railway logs for Celery
railway logs --service backend-hormonia --filter celery

# Expected:
[2025-10-05 XX:XX:XX] celery.worker.consumer - INFO - Connected to redis://***@HOST:PORT/0
```

---

## 5. Troubleshooting Guide

### 🔴 Error: "[SSL] record layer failure"

**Cause**: Wrong port - using non-TLS port (e.g., 14149) with `rediss://` scheme

**Solution**:
```bash
# Option A: Use TLS port
REDIS_URL=rediss://default:PASSWORD@HOST:14150  # Port 14150 (TLS)
REDIS_SSL=true
REDIS_SSL_MIN_VERSION=TLSV1_2

# Option B: Use non-TLS port
REDIS_URL=redis://default:PASSWORD@HOST:14149  # Port 14149 (non-TLS)
REDIS_SSL=false
```

**Verification**:
```bash
# Test port for TLS support
openssl s_client -connect HOST:PORT -tls1_2
```

### 🟠 Error: "certificate verify failed"

**Cause**: Wrong or missing CA certificate

**Solution**:

1. **Use certifi (easiest)**:
```bash
pip install certifi
# Remove REDIS_SSL_CA_CERTS from .env
railway variables set REDIS_SSL_CERT_REQS=required
```

2. **Use correct CA certificate**:
```bash
# Download from Redis Cloud
curl -o certs/redis_ca.pem https://redis.io/docs/.../redis_ca.pem

# Update environment
REDIS_SSL_CA_CERTS=certs/redis_ca.pem
```

3. **Temporarily disable validation (testing only)**:
```bash
REDIS_SSL_CERT_REQS=none  # ⚠️ Not for production
```

**Verification**:
```bash
# Check if CA cert is loaded
railway logs | grep "Using CA certificate"
# Should see: "Using certifi CA bundle" or "Using CA certificate from certs/..."
```

### 🟡 Error: "Connection timeout"

**Cause**: Firewall blocking port, wrong host, or network issue

**Solution**:

1. **Verify connectivity**:
```bash
# From Railway environment (via railway run)
railway run --service backend-hormonia nc -zv REDIS_HOST REDIS_PORT

# Expected: "Connection to REDIS_HOST REDIS_PORT port [tcp/*] succeeded!"
```

2. **Check Redis Cloud Firewall**:
   - Login to Redis Cloud dashboard
   - Go to **"Security"** → **"CIDR whitelist"**
   - Ensure `0.0.0.0/0` (allow all) or add Railway's IP ranges

3. **Verify host resolution**:
```bash
railway run --service backend-hormonia nslookup REDIS_HOST
```

### 🟢 Error: "SSL: WRONG_VERSION_NUMBER"

**Cause**: TLS version mismatch - Python 3.13 defaults to TLS 1.3, Redis Cloud requires TLS 1.2

**Solution**:
```bash
# Force TLS 1.2
REDIS_SSL_MIN_VERSION=TLSV1_2
```

**Verification**:
```bash
# Check logs for TLS version
railway logs | grep "TLS version"
# Should see: "Enforcing minimum TLS version 1.2"
```

### 🔵 Error: "Max connections reached"

**Cause**: Connection pool exhausted (default max: 50)

**Solution**:

1. **Increase pool size** (temporary):
```bash
# Add to .env
REDIS_MAX_CONNECTIONS=100
```

2. **Fix connection leaks** (permanent):
```python
# Ensure connections are properly closed
async with redis_transaction() as pipe:
    # ... operations
    pass  # Auto-cleanup
```

3. **Monitor pool usage**:
```bash
curl https://YOUR_DOMAIN/api/v1/health/redis
# Check "active_connections" field
```

---

## 6. Quick Reference

### 🎯 Common Scenarios Quick Guide

#### Scenario 1: Redis Cloud Port 14149 (No TLS)
```bash
REDIS_URL=redis://default:PASSWORD@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149
REDIS_SSL=false
REDIS_SSL_CERT_REQS=none
```

#### Scenario 2: Redis Cloud Port 14150 (TLS 1.2)
```bash
REDIS_URL=rediss://default:PASSWORD@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14150
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required
REDIS_SSL_MIN_VERSION=TLSV1_2
# certifi auto-detected (pip install certifi)
```

#### Scenario 3: Railway Redis Plugin (No TLS)
```bash
REDIS_URL=${{Redis.REDIS_URL}}  # Railway provides this
REDIS_SSL=false
REDIS_SSL_CERT_REQS=none
```

#### Scenario 4: Custom Redis with TLS 1.3
```bash
REDIS_URL=rediss://default:PASSWORD@custom-redis.com:6380
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required
REDIS_SSL_MIN_VERSION=TLSV1_3
REDIS_SSL_CA_CERTS=certs/custom_ca.pem
```

### 📋 Deployment Checklist (Copy-Paste)

```markdown
## Pre-Deployment
- [ ] Verified port TLS support (`openssl s_client -connect HOST:PORT -tls1_2`)
- [ ] URL scheme matches SSL setting (`rediss://` = `REDIS_SSL=true`)
- [ ] Certificate source configured (`certifi` OR `REDIS_SSL_CA_CERTS`)
- [ ] TLS version set for Python 3.13 (`REDIS_SSL_MIN_VERSION=TLSV1_2`)
- [ ] Celery URLs match Redis settings (if applicable)

## Post-Deployment
- [ ] No `[SSL] record layer failure` in logs
- [ ] No `certificate verify failed` in logs
- [ ] `/health` endpoint shows `"redis": "healthy"`
- [ ] `/api/v1/health/redis` returns connection details
- [ ] Celery workers connected (if applicable)
- [ ] Test WhatsApp notification (if applicable)
- [ ] Monitor logs for 5 minutes for stability

## Monitoring
- [ ] Setup alert for Redis connection failures
- [ ] Track connection pool usage metrics
- [ ] Monitor SSL handshake errors
- [ ] Check Celery task queue length
```

### 🔗 Useful Links

- **Redis Cloud Dashboard**: https://app.redislabs.com/
- **Redis TLS Docs**: https://redis.io/docs/latest/operate/rc/security/database-security/tls-ssl/
- **Railway Variables**: `railway variables --service backend-hormonia`
- **Project Docs**:
  - [ENV_VARIABLES_GUIDE.md](./ENV_VARIABLES_GUIDE.md) - Complete env var reference
  - [HIVE_MIND_REDIS_ANALYSIS.md](./HIVE_MIND_REDIS_ANALYSIS.md) - Root cause analysis
  - [REDIS_CONFIGURATION_REVIEW.md](./REDIS_CONFIGURATION_REVIEW.md) - Configuration patterns

### 🆘 Emergency Rollback

If deployment fails and you need immediate rollback:

```bash
# Option 1: Disable SSL validation (temporary)
railway variables set REDIS_SSL_CERT_REQS=none

# Option 2: Switch to non-TLS port
railway variables set REDIS_URL=redis://default:PASSWORD@HOST:14149
railway variables set REDIS_SSL=false

# Option 3: Rollback to previous deployment
railway rollback
```

---

## 📝 Change Log

| Date | Change | Reason |
|------|--------|--------|
| 2025-10-05 | Initial checklist created | Based on production debugging session |
| 2025-10-05 | Added port verification section | Critical finding: port 14149 vs 14150 |
| 2025-10-05 | Added Python 3.13 TLS version fix | OpenSSL 3.x compatibility |
| 2025-10-05 | Added certifi auto-detection | Automatic CA certificate management |

---

**Status**: ✅ Production-Tested
**Last Verified**: Railway deployment on 2025-10-05
**Applies To**: Redis Cloud, Railway Redis, Upstash, AWS ElastiCache
**Python Version**: 3.13+
**redis-py Version**: 6.0+
