# Railway Redis SSL/TLS - Quick Start Card

**⚡ 2-Minute Setup Guide** | [Full Checklist](./RAILWAY_REDIS_SSL_CHECKLIST.md)

---

## 🎯 Step 1: Identify Your Port Type (30 seconds)

```bash
# Test if your Redis port supports TLS
openssl s_client -connect YOUR_REDIS_HOST:YOUR_PORT -tls1_2
```

**Result**:
- ✅ **Certificate shown** = TLS port → Go to Scenario A
- ❌ **Error/refused** = Non-TLS port → Go to Scenario B

---

## 📝 Step 2: Configure Environment (1 minute)

### Scenario A: TLS Port (14150) ✅ Recommended
```bash
# Railway Variables
REDIS_URL=rediss://default:PASSWORD@HOST:14150
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required
REDIS_SSL_MIN_VERSION=TLSV1_2

# Install certifi
pip install certifi
```

### Scenario B: Non-TLS Port (14149)
```bash
# Railway Variables
REDIS_URL=redis://default:PASSWORD@HOST:14149
REDIS_SSL=false
REDIS_SSL_CERT_REQS=none
```

---

## ✅ Step 3: Verify (30 seconds)

```bash
# Check Railway logs
railway logs --service backend-hormonia | grep -i redis

# Expected Success Messages:
# ✅ "Redis async SSL: Certificate verification REQUIRED"
# ✅ "Async Redis client connected successfully"

# Check health
curl https://YOUR_DOMAIN/health | jq .services.redis
# Expected: {"status": "healthy", "async_ping": true}
```

---

## 🔴 Common Errors & Instant Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `[SSL] record layer failure` | Wrong port (non-TLS with `rediss://`) | Use `redis://` OR switch to TLS port |
| `certificate verify failed` | Missing certifi | `pip install certifi` |
| `Connection timeout` | Wrong host/firewall | Check Redis Cloud dashboard → Security |
| `WRONG_VERSION_NUMBER` | TLS version mismatch | Add `REDIS_SSL_MIN_VERSION=TLSV1_2` |

---

## 🚀 Deploy Commands

```bash
# Set Railway variables
railway variables set REDIS_URL="rediss://default:PASSWORD@HOST:14150"
railway variables set REDIS_SSL=true
railway variables set REDIS_SSL_CERT_REQS=required
railway variables set REDIS_SSL_MIN_VERSION=TLSV1_2

# Deploy
git add .
git commit -m "Configure Redis SSL/TLS"
git push

# Monitor
railway logs --follow
```

---

## 📚 Full Documentation

- **Complete Checklist**: [RAILWAY_REDIS_SSL_CHECKLIST.md](./RAILWAY_REDIS_SSL_CHECKLIST.md)
- **Executive Summary**: [RAILWAY_REDIS_SSL_SUMMARY.md](./RAILWAY_REDIS_SSL_SUMMARY.md)
- **Root Cause Analysis**: [HIVE_MIND_REDIS_ANALYSIS.md](./HIVE_MIND_REDIS_ANALYSIS.md)

---

**Last Updated**: 2025-10-05 | **Status**: Production-Tested ✅
