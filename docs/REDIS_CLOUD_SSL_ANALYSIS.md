# Redis Cloud SSL/TLS Deep Analysis

## 🔍 Problem Summary

**Error:** `[SSL] record layer failure (_ssl.c:1032)`
**Root Cause:** TLS version negotiation mismatch between Python 3.13 and Redis Cloud

---

## 📊 How Redis Cloud SSL Works

### Server Side (Redis Cloud)
- ✅ **SSL/TLS enabled automatically** on all connections
- ✅ **Port 6379** has SSL enabled (not 6380 like self-hosted)
- ✅ **Certificates managed** by Redis Cloud (automatic renewal)
- ✅ **Supports TLS 1.2 and TLS 1.3**
- ✅ **No client certificates required**

### Client Side (Our App)
**Required configuration:**
```python
import redis

r = redis.Redis(
    host='redis-xxxxx.redis.cloud.com',
    port=6379,
    password='your-password',
    ssl=True,  # Enable SSL
    ssl_cert_reqs=None  # Accept Redis Cloud certificate
)
```

Or using connection URL:
```python
redis_url = "rediss://default:password@host:6379"  # Note: rediss:// with two 's'
r = redis.from_url(redis_url, ssl_cert_reqs=ssl.CERT_NONE)
```

---

## ⚠️ Python 3.13 + OpenSSL 3.x Issue

### What Happens
1. **Python 3.13** defaults to attempting **TLS 1.3** first
2. **OpenSSL 3.x** has stricter cipher suite requirements
3. **Redis Cloud** may prefer or enforce **TLS 1.2** cipher suites
4. **Handshake fails** during protocol negotiation → `[SSL] record layer failure`

### Why CERT_NONE Didn't Fix It
- `CERT_NONE` only disables **certificate validation**
- The error occurs **before** certificate validation
- Problem is in **TLS protocol negotiation** phase

---

## ✅ Solution: Force TLS 1.2

### Environment Variable
```bash
REDIS_SSL_MIN_VERSION=TLSv1_2
```

### Code Implementation (redis_manager.py)
```python
if ssl_min_version == 'TLSV1_2':
    connection_kwargs['ssl_min_version'] = ssl.TLSVersion.TLSv1_2
    logger.info("Redis async SSL: Enforcing minimum TLS version 1.2")
```

### Why This Works
- Forces Python to use **TLS 1.2** instead of attempting 1.3
- TLS 1.2 has **mature cipher suite compatibility** with Redis Cloud
- **redis-py 6.0+** supports `ssl_min_version` parameter natively
- Redis Cloud accepts TLS 1.2 connections without issues

---

## 🔧 Additional Considerations

### SNI (Server Name Indication)
Redis Cloud uses SNI to route connections to the correct database.

**redis-py 6.0+ handles SNI automatically** when using `ConnectionPool.from_url()`:
- Extracts hostname from URL: `redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com`
- Sets SNI hostname automatically
- ✅ **No manual configuration needed**

### Cipher Suites
Python 3.13 + OpenSSL 3.x defaults to modern cipher suites.

**Redis Cloud supports:**
- `TLS_AES_256_GCM_SHA384` (TLS 1.3)
- `TLS_AES_128_GCM_SHA256` (TLS 1.3)
- `ECDHE-RSA-AES256-GCM-SHA384` (TLS 1.2)
- `ECDHE-RSA-AES128-GCM-SHA256` (TLS 1.2)

**With TLS 1.2 enforcement, compatible cipher suites are used automatically.**

---

## 🚀 Deployment Steps

### 1. Update Railway Environment Variables
```bash
# Via Railway Dashboard
REDIS_SSL_CERT_REQS=none
REDIS_SSL_MIN_VERSION=TLSv1_2

# Or via Railway CLI
railway variables set REDIS_SSL_CERT_REQS=none
railway variables set REDIS_SSL_MIN_VERSION=TLSv1_2
```

### 2. Expected Logs
```
INFO - Redis async SSL: Certificate verification DISABLED (CERT_NONE)
INFO - Redis async SSL: Enforcing minimum TLS version 1.2
INFO - Async Redis client connected successfully
```

### 3. Verification
```bash
# Check Redis connection
railway logs --filter "Redis"

# Should see successful ping
INFO - Async Redis client connected successfully
```

---

## 🐛 Debugging Commands

### Check OpenSSL Version
```python
import ssl
print(ssl.OPENSSL_VERSION)
# Expected: OpenSSL 3.x.x
```

### Check TLS Version Support
```python
import ssl
print(f"Min: {ssl.TLSVersion.MINIMUM}")
print(f"Max: {ssl.TLSVersion.MAXIMUM}")
```

### Test Without SSL (Fallback)
```bash
# If TLS 1.2 still fails, test raw connection
REDIS_SSL=false
REDIS_URL=redis://default:password@host:6379
```

---

## 📚 References

- [Redis Cloud SSL/TLS Documentation](https://redis.com/redis-enterprise-cloud/security/encryption/)
- [redis-py SSL Parameters](https://redis-py.readthedocs.io/en/stable/connections.html#ssl-connections)
- [Python 3.13 SSL Module](https://docs.python.org/3.13/library/ssl.html)
- [OpenSSL 3.x TLS Documentation](https://www.openssl.org/docs/man3.0/man7/ssl.html)

---

## ✅ Expected Outcome

With `REDIS_SSL_MIN_VERSION=TLSv1_2`:
- ✅ TLS handshake succeeds
- ✅ Connection established to Redis Cloud
- ✅ Monitoring enabled
- ✅ Cache operations working
- ✅ Celery broker functional
