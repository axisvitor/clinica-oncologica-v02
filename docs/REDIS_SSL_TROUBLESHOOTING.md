# Redis SSL Troubleshooting - Railway Deployment

## 🔍 Problem Summary

**Error:** `[SSL] record layer failure (_ssl.c:1032)`
**Status:** Persists even with `REDIS_SSL_CERT_REQS="none"`
**Impact:** Redis monitoring disabled, running in degraded mode

---

## 📊 Troubleshooting Timeline

### Attempt 1: Remove `ssl_context` parameter
**Change:** Removed `ssl_context` kwarg, used `ssl_cert_reqs` instead
**Result:** ❌ Still failing with record layer failure

### Attempt 2: Set `CERT_NONE` for managed Redis
**Change:** Changed `REDIS_SSL_CERT_REQS="required"` to `"none"`
**Result:** ❌ Still failing - not a certificate validation issue

### Attempt 3: Force TLS 1.2 protocol version ✅ IMPLEMENTED
**Hypothesis:** Redis Cloud TLS version incompatible with Python 3.13 SSL module
**Change:** Added `REDIS_SSL_MIN_VERSION=TLSv1_2` environment variable
**Implementation:** Updated `redis_manager.py` to enforce TLS 1.2 minimum version
**Status:** Awaiting Railway deployment with new environment variable

---

## 🎯 Possible Root Causes

### 1. TLS Protocol Version Mismatch
- Redis Cloud may require TLS 1.2 minimum
- Python 3.13 SSL module may have different defaults
- **Test:** Set explicit `ssl_min_version=TLSVersion.TLSv1_2`

### 2. Redis Cloud ACL/Firewall Rules
- Railway IP not whitelisted in Redis Cloud
- **Test:** Check Redis Cloud dashboard for connection logs
- **Fix:** Add Railway IPs to whitelist

### 3. Incorrect Connection Parameters
- URL format issue (port, password encoding)
- **Current URL:** `rediss://default:***@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149`
- **Test:** Try without SSL first (redis://)

### 4. Python 3.13 SSL Module Changes
- Python 3.13 may have stricter SSL defaults
- OpenSSL version compatibility
- **Test:** Check OpenSSL version in Railway

---

## 🔧 Next Debugging Steps

### Step 1: Test without SSL
```python
# Temporarily disable SSL to test raw connectivity
REDIS_SSL=false
REDIS_URL=redis://default:***@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149
```

### Step 2: Check OpenSSL version
```bash
python -c "import ssl; print(ssl.OPENSSL_VERSION)"
```

### Step 3: Add explicit TLS version
```python
import ssl
connection_kwargs['ssl_min_version'] = ssl.TLSVersion.TLSv1_2
connection_kwargs['ssl_max_version'] = ssl.TLSVersion.TLSv1_3
```

### Step 4: Enable SSL debug logging
```python
import logging
logging.getLogger('ssl').setLevel(logging.DEBUG)
```

---

## 📝 Redis Cloud Requirements

From Redis Cloud documentation:
- **TLS Version:** TLS 1.2+ required
- **Cipher Suites:** Modern ciphers only
- **SNI:** Server Name Indication required
- **ALPN:** May be required for some endpoints

---

## 🚨 Temporary Workaround

If SSL continues failing, consider:

1. **Disable Redis for monitoring** (already happening)
2. **Use non-SSL Redis** (if Redis Cloud allows)
3. **Switch to Railway Redis plugin** (built-in, no SSL issues)
4. **Use Upstash Redis** (alternative managed Redis)

---

## 📞 Support Contacts

- **Redis Cloud Support:** https://redis.com/company/support/
- **Railway Support:** https://railway.app/help
- **Python SSL Issues:** https://docs.python.org/3/library/ssl.html
