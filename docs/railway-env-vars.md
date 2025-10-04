# Railway Environment Variables - Frontend Nginx

## 🚨 CRITICAL FIX APPLIED: envsubst Variable Substitution

### Problem Solved
- **Issue**: `envsubst` doesn't understand Bash default syntax `${VAR:-default}`
- **Solution**: Expand variables with defaults in shell BEFORE running envsubst
- **Result**: nginx.conf.template uses simple `${VAR}` syntax, defaults handled in entrypoint

---

## 📋 Required Environment Variables

### Backend Connection (CRITICAL)

```bash
# Railway Service Configuration
BACKEND_HOST=backend-service-name.railway.internal
BACKEND_PORT=8000
```

**How to set in Railway:**
1. Go to Frontend service settings
2. Navigate to "Variables" tab
3. Add these variables:
   - `BACKEND_HOST` → Your backend Railway service name (e.g., `backend-production`)
   - `BACKEND_PORT` → `8000` (or your backend port)

**Defaults (if not set):**
- `BACKEND_HOST` → `backend` (fallback)
- `BACKEND_PORT` → `8000` (fallback)

---

## 🔍 How It Works

### Before (BROKEN):
```nginx
# nginx.conf.template
upstream backend {
    server ${BACKEND_HOST:-backend}:${BACKEND_PORT:-8000};  # ❌ envsubst can't parse this
}
```

```bash
# docker-entrypoint.sh
envsubst '${BACKEND_HOST} ${BACKEND_PORT}' < template > nginx.conf
# Result: Variables not replaced, nginx gets literal "${BACKEND_HOST:-backend}"
```

### After (FIXED):
```nginx
# nginx.conf.template (now nginx.conf)
upstream backend {
    server ${BACKEND_HOST}:${BACKEND_PORT};  # ✅ Simple syntax
}
```

```bash
# docker-entrypoint.sh
export BACKEND_HOST="${BACKEND_HOST:-backend}"  # Apply defaults FIRST
export BACKEND_PORT="${BACKEND_PORT:-8000}"
envsubst '${BACKEND_HOST} ${BACKEND_PORT}' < template > nginx.conf
# Result: Variables properly replaced with actual values
```

---

## 📊 Verification

**Check logs after deployment:**
```
🔍 Debug info:
   Current user: nginx
   User ID: 101
uid=101(nginx) gid=101(nginx) groups=101(nginx)
-rw-r--r-- 1 nginx nginx 7928 /etc/nginx/nginx.conf.template

🔗 Backend configuration (with defaults applied):
   BACKEND_HOST=backend-production
   BACKEND_PORT=8000

✅ nginx.conf created successfully
```

**Verify nginx.conf was generated correctly:**
```bash
# In Railway logs, look for:
upstream backend {
    server backend-production:8000;  # ✅ Real values, not variables
}
```

---

## 🎯 Railway Setup Checklist

- [ ] Frontend service: Set `BACKEND_HOST` variable
- [ ] Frontend service: Set `BACKEND_PORT` variable
- [ ] Backend service: Ensure it's named correctly (matches `BACKEND_HOST`)
- [ ] Verify logs show: "Backend configuration (with defaults applied)"
- [ ] Confirm nginx starts without errors
- [ ] Test API proxy: `curl https://your-frontend.railway.app/api/health`

---

## 🔧 Troubleshooting

### Error: "invalid port in upstream"
**Cause**: Variables not being substituted
**Fix**: Applied in this commit - expand variables before envsubst

### Error: "Permission denied"
**Cause**: nginx user can't write to /tmp/
**Fix**: Already fixed - write directly to /etc/nginx/nginx.conf

### Backend 502/504 errors
**Cause**: Wrong `BACKEND_HOST` value
**Fix**: Use Railway internal DNS name: `service-name.railway.internal`

---

## 📝 Implementation Details

**Files modified:**
1. `frontend-hormonia/nginx.conf` (template)
   - Changed: `${BACKEND_HOST:-backend}` → `${BACKEND_HOST}`
   - Added: Comments explaining envsubst behavior

2. `frontend-hormonia/docker-entrypoint.sh`
   - Added: `export BACKEND_HOST="${BACKEND_HOST:-backend}"`
   - Added: `export BACKEND_PORT="${BACKEND_PORT:-8000}"`
   - Improved: Debug output shows values BEFORE substitution

**Testing:**
```bash
# Simulate Railway environment
docker run --rm \
  -e BACKEND_HOST=api-service \
  -e BACKEND_PORT=3000 \
  your-frontend-image

# Test with defaults
docker run --rm your-frontend-image
# Should use: backend:8000
```
