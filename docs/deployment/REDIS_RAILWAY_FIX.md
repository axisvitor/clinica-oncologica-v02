# Redis Railway Configuration Fix

## Problem Identified

Railway logs show:
```
[SSL] record layer failure
Redis client for session manager: available
WebSocket events service initialized with Redis at rediss://...:14149
```

**Root cause**: Redis Cloud port **14149 does NOT support TLS/SSL**, but environment is configured with `rediss://` scheme and `REDIS_SSL=true` with TLS 1.2.

## Solution: Use Non-TLS Connection on Port 14149

### Required Railway Environment Variables

Replace **ALL** Redis-related variables with these exact values:

```bash
# Main Redis connection (NO SSL on port 14149)
REDIS_URL=redis://default:YOUR_REDIS_PASSWORD@YOUR_REDIS_HOST:14149

# SSL Configuration (DISABLED for port 14149)
REDIS_SSL=false
# Remove or leave empty:
REDIS_SSL_MIN_VERSION=
REDIS_SSL_CERT_REQS=none

# Connection settings (keep existing)
REDIS_HOST=YOUR_REDIS_HOST
REDIS_PORT=14149
REDIS_PASSWORD=YOUR_REDIS_PASSWORD

# Celery (must match main Redis - NO SSL)
CELERY_BROKER_URL=redis://default:YOUR_REDIS_PASSWORD@YOUR_REDIS_HOST:14149/0
CELERY_RESULT_BACKEND=redis://default:YOUR_REDIS_PASSWORD@YOUR_REDIS_HOST:14149/1

# Rate limiting (uses same Redis)
RATE_LIMIT_REDIS_URL=redis://default:YOUR_REDIS_PASSWORD@YOUR_REDIS_HOST:14149/3
```

### Step-by-Step Railway Configuration

1. **Navigate to Railway Backend Service**
   - Go to Variables tab

2. **Update These Variables** (copy-paste exact values from your Redis Cloud):
   ```bash
   REDIS_URL=redis://default:PASSWORD@HOST:14149
   REDIS_SSL=false
   REDIS_SSL_MIN_VERSION=  # Empty or delete
   REDIS_SSL_CERT_REQS=none
   CELERY_BROKER_URL=redis://default:PASSWORD@HOST:14149/0
   CELERY_RESULT_BACKEND=redis://default:PASSWORD@HOST:14149/1
   RATE_LIMIT_REDIS_URL=redis://default:PASSWORD@HOST:14149/3
   ```

3. **Delete These Variables** (if present):
   - `REDIS_SSL_CA_CERTS`
   - `REDIS_SSL_CHECK_HOSTNAME`

4. **Redeploy Backend**
   - Railway will auto-redeploy on variable change
   - Or trigger manual redeploy

## Alternative: Use TLS Port (If Available)

If your Redis Cloud instance has a **TLS-enabled port** (check Redis Cloud console):

```bash
# Use TLS port (typically different from 14149)
REDIS_URL=rediss://default:PASSWORD@HOST:TLS_PORT
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required
REDIS_SSL_MIN_VERSION=TLSV1_2

# Update Celery to use TLS port
CELERY_BROKER_URL=rediss://default:PASSWORD@HOST:TLS_PORT/0
CELERY_RESULT_BACKEND=rediss://default:PASSWORD@HOST:TLS_PORT/1
RATE_LIMIT_REDIS_URL=rediss://default:PASSWORD@HOST:TLS_PORT/3
```

**Note**: Redis Cloud Free tier typically only provides **non-TLS ports**. Check your plan.

## Verification After Deployment

### 1. Check Redis Health Endpoint
```bash
curl https://backend-production-90c3.up.railway.app/api/v1/redis/health
```

Expected response:
```json
{
  "status": "healthy",
  "latency_ms": 5.2,
  "timestamp": "2025-10-06T...",
  "mode": "async"
}
```

### 2. Check Railway Logs
```bash
# Should see:
✅ Redis client initialized successfully (no SSL errors)
✅ CORS Production Mode: 2 allowed origins
✅ Firebase Admin SDK initialized successfully
✅ WebSocket events service initialized with Redis

# Should NOT see:
❌ [SSL] record layer failure
❌ SSL/TLS connection failed
```

### 3. Test WebSocket Connection
```bash
# Use valid JWT token
wscat -c "wss://backend-production-90c3.up.railway.app/ws/connect?token=YOUR_JWT"
```

Expected: `101 Switching Protocols`

### 4. Test API with Authentication
```bash
curl -H "Authorization: Bearer YOUR_JWT" \
  https://backend-production-90c3.up.railway.app/api/v1/patients/
```

Expected: `200 OK` with patient data

## Code References

- Redis configuration: [backend-hormonia/app/config.py:166-180](cci:7://file:///c:/Meu%20Projetos/clinica-oncologica-v02/backend-hormonia/app/config.py:166:0-180:0)
- Redis manager: [backend-hormonia/app/core/redis_manager.py:111-186](cci:7://file:///c:/Meu%20Projetos/clinica-oncologica-v02/backend-hormonia/app/core/redis_manager.py:111:0-186:0)
- Config validation: [backend-hormonia/app/config.py:424-436](cci:1://file:///c:/Meu%20Projetos/clinica-oncologica-v02/backend-hormonia/app/config.py:424:4-436:96)

## Common Issues

### Issue: "ALLOWED_ORIGINS is empty!" warning
**Cause**: Startup validation runs before production mode activates
**Impact**: None - CORS correctly applies `FRONTEND_URL` + `QUIZ_URL` in production
**Fix**: Optional - can suppress by setting `ALLOWED_ORIGINS` explicitly or adjust validation logic

### Issue: Still seeing SSL errors after changing to `redis://`
**Cause**: Old environment variable cached or not saved
**Fix**:
1. Verify Railway Variables tab shows `redis://` (not `rediss://`)
2. Trigger manual redeploy
3. Check `/api/v1/health` endpoint for applied config

### Issue: Connection timeout
**Cause**: Firewall or incorrect host/port
**Fix**: Verify Redis Cloud console shows same host:port and allows Railway IP range

## Health Check Checklist

- [ ] `REDIS_URL` starts with `redis://` (not `rediss://`)
- [ ] `REDIS_SSL=false`
- [ ] `CELERY_BROKER_URL` uses same scheme as `REDIS_URL`
- [ ] `/api/v1/redis/health` returns `"status": "healthy"`
- [ ] Railway logs show no SSL errors
- [ ] WebSocket connects successfully (101 status)
- [ ] API endpoints return 200 with valid JWT

## Next Steps After Fix

1. ✅ Fix Redis configuration (this document)
2. ⏳ Monitor logs for 10 minutes post-deploy
3. ⏳ Test all critical endpoints (patients, quiz, WebSocket)
4. ⏳ Run E2E tests against production
5. ⏳ Document final production environment variables

---

**Last Updated**: 2025-10-06
**Status**: Ready for deployment
**Related Docs**:
- [RAILWAY_DEPLOY_CHECKLIST.md](RAILWAY_DEPLOY_CHECKLIST.md)
- [RAILWAY_DEPLOY_ANALYSIS.md](../RAILWAY_DEPLOY_ANALYSIS.md)
