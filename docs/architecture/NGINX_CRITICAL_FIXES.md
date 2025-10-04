# Nginx Critical Fixes - Implementation Guide
**Priority:** P0 - Must fix before production deployment
**Estimated Time:** 1.5 hours
**Date:** 2025-10-04

---

## Overview

This document provides step-by-step instructions to fix the 4 critical issues found in the Nginx configuration review.

### Critical Issues to Fix
1. ✅ Missing Content-Security-Policy (CSP) header
2. ✅ Missing Strict-Transport-Security (HSTS) header
3. ✅ Hardcoded runtime config in `/api/config.js`
4. ✅ Missing worker processes configuration

---

## Fix 1: Add Content-Security-Policy (CSP)

**File:** `frontend-hormonia/nginx.conf`
**Time:** 30 minutes
**Priority:** P0 - CRITICAL

### Problem
No CSP header configured, leaving the application vulnerable to XSS attacks.

### Solution

Add the following to the security headers section (after line 18):

```nginx
# Security headers
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;

# Content-Security-Policy (NEW)
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://apis.google.com https://www.gstatic.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src 'self' data: https: blob:; font-src 'self' data: https://fonts.gstatic.com; connect-src 'self' https://*.railway.app wss://*.railway.app https://*.supabase.co wss://*.supabase.co https://*.firebaseio.com https://*.googleapis.com https://*.cloudfunctions.net; frame-src 'self' https://*.firebaseapp.com; frame-ancestors 'self'; base-uri 'self'; form-action 'self'; object-src 'none';" always;
```

### Explanation

- `default-src 'self'` - Only allow resources from same origin by default
- `script-src` - Allow scripts from self, inline (React), Google APIs
- `style-src` - Allow styles from self, inline (styled-components), Google Fonts
- `img-src` - Allow images from self, data URIs, HTTPS, blobs
- `font-src` - Allow fonts from self, data URIs, Google Fonts
- `connect-src` - Allow connections to backend (Railway), Supabase, Firebase
- `frame-src` - Allow iframes from Firebase
- `frame-ancestors 'self'` - Prevent clickjacking
- `base-uri 'self'` - Prevent base tag injection
- `form-action 'self'` - Prevent form submission to external sites
- `object-src 'none'` - Block plugins (Flash, etc.)
- `always` - Include header even on error responses

### Testing

After deployment, verify CSP header:

```bash
curl -I https://your-frontend.railway.app/ | grep -i content-security-policy
```

Should return:
```
content-security-policy: default-src 'self'; script-src 'self' 'unsafe-inline' ...
```

### Customization

Adjust based on your actual third-party services:

- **If using Sentry:** Add `https://*.sentry.io` to `connect-src`
- **If using Google Analytics:** Add `https://www.google-analytics.com` to `connect-src`
- **If using Stripe:** Add `https://js.stripe.com` to `script-src` and `https://api.stripe.com` to `connect-src`
- **If camera/mic needed:** This is controlled by Permissions-Policy (see Phase 2)

---

## Fix 2: Add Strict-Transport-Security (HSTS)

**File:** `frontend-hormonia/nginx.conf`
**Time:** 5 minutes
**Priority:** P0 - CRITICAL

### Problem
No HSTS header configured, vulnerable to SSL stripping attacks.

### Solution

Add after the CSP header (around line 26):

```nginx
# Strict-Transport-Security (NEW)
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
```

### Explanation

- `max-age=31536000` - Force HTTPS for 1 year (31,536,000 seconds)
- `includeSubDomains` - Apply to all subdomains
- `preload` - Allow submission to HSTS preload list
- `always` - Include on all responses (including errors)

### Testing

After deployment:

```bash
curl -I https://your-frontend.railway.app/ | grep -i strict-transport-security
```

Should return:
```
strict-transport-security: max-age=31536000; includeSubDomains; preload
```

### HSTS Preload (Optional)

After 90 days of successful deployment, submit to HSTS preload list:
https://hstspreload.org/

This will hardcode HTTPS enforcement in browsers permanently.

---

## Fix 3: Fix Runtime Config Substitution

**Files:**
- `frontend-hormonia/public/api/config.js.template` (NEW)
- `frontend-hormonia/Dockerfile` (MODIFY)
- `frontend-hormonia/public/api/config.js` (DELETE after build)

**Time:** 45 minutes
**Priority:** P0 - CRITICAL

### Problem
`public/api/config.js` has hardcoded backend URLs, defeating runtime configuration.

### Solution - Part A: Create Template File

**Create:** `frontend-hormonia/public/api/config.js.template`

```javascript
/**
 * Runtime Environment Configuration Template
 *
 * This file is processed by the Docker entrypoint script at container startup.
 * Environment variables are substituted using envsubst.
 *
 * DO NOT edit config.js directly - it will be overwritten at runtime.
 */

(function() {
  'use strict';

  // Runtime environment configuration
  window.__ENV_CONFIG__ = {
    // Backend API URLs (substituted at runtime)
    VITE_API_BASE_URL: '${VITE_API_BASE_URL}',
    VITE_WS_BASE_URL: '${VITE_WS_BASE_URL}',

    // Supabase configuration (substituted at runtime)
    VITE_SUPABASE_URL: '${VITE_SUPABASE_URL}',
    VITE_SUPABASE_ANON_KEY: '${VITE_SUPABASE_ANON_KEY}',

    // Firebase configuration (substituted at runtime)
    VITE_FIREBASE_API_KEY: '${VITE_FIREBASE_API_KEY}',
    VITE_FIREBASE_AUTH_DOMAIN: '${VITE_FIREBASE_AUTH_DOMAIN}',
    VITE_FIREBASE_PROJECT_ID: '${VITE_FIREBASE_PROJECT_ID}',
    VITE_FIREBASE_STORAGE_BUCKET: '${VITE_FIREBASE_STORAGE_BUCKET}',
    VITE_FIREBASE_MESSAGING_SENDER_ID: '${VITE_FIREBASE_MESSAGING_SENDER_ID}',
    VITE_FIREBASE_APP_ID: '${VITE_FIREBASE_APP_ID}',

    // WhatsApp configuration
    VITE_WHATSAPP_INSTANCE_NAME: '${VITE_WHATSAPP_INSTANCE_NAME:-hormonia-instance}',

    // Application configuration
    VITE_ENVIRONMENT: '${VITE_ENVIRONMENT:-production}',
    VITE_DEBUG_MODE: '${VITE_DEBUG_MODE:-false}',

    // Session configuration
    VITE_SESSION_TIMEOUT: '${VITE_SESSION_TIMEOUT:-3600000}',
    VITE_TOKEN_REFRESH_THRESHOLD: '${VITE_TOKEN_REFRESH_THRESHOLD:-300000}',

    // File upload configuration
    VITE_MAX_FILE_SIZE: '${VITE_MAX_FILE_SIZE:-10485760}',
    VITE_SUPPORTED_FILE_TYPES: '${VITE_SUPPORTED_FILE_TYPES:-image/jpeg,image/png,image/gif,application/pdf}'
  };

  // Convert string 'true'/'false' to boolean
  ['VITE_DEBUG_MODE'].forEach(function(key) {
    if (window.__ENV_CONFIG__[key] === 'true') {
      window.__ENV_CONFIG__[key] = true;
    } else if (window.__ENV_CONFIG__[key] === 'false') {
      window.__ENV_CONFIG__[key] = false;
    }
  });

  // Convert string numbers to integers
  ['VITE_SESSION_TIMEOUT', 'VITE_TOKEN_REFRESH_THRESHOLD', 'VITE_MAX_FILE_SIZE'].forEach(function(key) {
    var value = window.__ENV_CONFIG__[key];
    if (value && !isNaN(value)) {
      window.__ENV_CONFIG__[key] = parseInt(value, 10);
    }
  });

  // Debug logging (only if debug mode enabled)
  if (window.__ENV_CONFIG__.VITE_DEBUG_MODE) {
    console.log('[Config] Runtime environment loaded:', {
      environment: window.__ENV_CONFIG__.VITE_ENVIRONMENT,
      apiUrl: window.__ENV_CONFIG__.VITE_API_BASE_URL,
      wsUrl: window.__ENV_CONFIG__.VITE_WS_BASE_URL,
      supabaseConfigured: !!window.__ENV_CONFIG__.VITE_SUPABASE_URL,
      firebaseConfigured: !!window.__ENV_CONFIG__.VITE_FIREBASE_API_KEY
    });
  }
})();
```

### Solution - Part B: Update Dockerfile Entrypoint

**File:** `frontend-hormonia/Dockerfile`

**REPLACE** the embedded entrypoint script (lines 83-107) with:

```dockerfile
# Create startup script with envsubst for runtime config
RUN printf '#!/bin/sh\n\
set -e\n\
\n\
echo "=== Nginx Startup Script ==="\n\
\n\
# Configure dynamic PORT from Railway\n\
if [ -n "$PORT" ]; then\n\
  echo "✓ Configuring nginx to listen on port $PORT"\n\
  sed -i "s/listen 3000;/listen $PORT;/g" /etc/nginx/conf.d/default.conf\n\
else\n\
  echo "ℹ Using default port 3000"\n\
fi\n\
\n\
# Configure BACKEND_URL for proxy_pass\n\
if [ -z "$BACKEND_URL" ] && [ -n "$VITE_API_BASE_URL" ]; then\n\
  BACKEND_URL="$VITE_API_BASE_URL"\n\
  echo "ℹ Using VITE_API_BASE_URL as BACKEND_URL: $BACKEND_URL"\n\
fi\n\
\n\
if [ -z "$BACKEND_URL" ]; then\n\
  BACKEND_URL="http://backend:8000"\n\
  echo "⚠ BACKEND_URL not set, using default: $BACKEND_URL"\n\
else\n\
  echo "✓ BACKEND_URL configured: $BACKEND_URL"\n\
fi\n\
\n\
# Substitute BACKEND_URL in nginx config\n\
sed -i "s|\\${BACKEND_URL}|$BACKEND_URL|g" /etc/nginx/conf.d/default.conf\n\
\n\
# Verify substitution succeeded\n\
if grep -q "\\${BACKEND_URL}" /etc/nginx/conf.d/default.conf; then\n\
  echo "✗ ERROR: BACKEND_URL substitution failed!"\n\
  exit 1\n\
fi\n\
\n\
# Process runtime config template\n\
CONFIG_TEMPLATE="/usr/share/nginx/html/api/config.js.template"\n\
CONFIG_OUTPUT="/usr/share/nginx/html/api/config.js"\n\
\n\
if [ -f "$CONFIG_TEMPLATE" ]; then\n\
  echo "✓ Processing runtime config template..."\n\
  \n\
  # Set defaults for missing environment variables\n\
  export VITE_ENVIRONMENT="${VITE_ENVIRONMENT:-production}"\n\
  export VITE_DEBUG_MODE="${VITE_DEBUG_MODE:-false}"\n\
  export VITE_WHATSAPP_INSTANCE_NAME="${VITE_WHATSAPP_INSTANCE_NAME:-hormonia-instance}"\n\
  export VITE_SESSION_TIMEOUT="${VITE_SESSION_TIMEOUT:-3600000}"\n\
  export VITE_TOKEN_REFRESH_THRESHOLD="${VITE_TOKEN_REFRESH_THRESHOLD:-300000}"\n\
  export VITE_MAX_FILE_SIZE="${VITE_MAX_FILE_SIZE:-10485760}"\n\
  export VITE_SUPPORTED_FILE_TYPES="${VITE_SUPPORTED_FILE_TYPES:-image/jpeg,image/png,image/gif,application/pdf}"\n\
  \n\
  # Substitute environment variables in template\n\
  envsubst < "$CONFIG_TEMPLATE" > "$CONFIG_OUTPUT"\n\
  \n\
  # Verify critical variables were substituted\n\
  if grep -q "\\${VITE_API_BASE_URL}" "$CONFIG_OUTPUT"; then\n\
    echo "✗ ERROR: VITE_API_BASE_URL not substituted in config.js!"\n\
    echo "  Make sure VITE_API_BASE_URL environment variable is set."\n\
    exit 1\n\
  fi\n\
  \n\
  echo "✓ Runtime config generated successfully"\n\
  \n\
  # Debug: Show first few lines of config (non-sensitive)\n\
  if [ "$VITE_DEBUG_MODE" = "true" ]; then\n\
    echo "  Config preview:"\n\
    head -n 5 "$CONFIG_OUTPUT" | sed "s/^/    /"\n\
  fi\n\
else\n\
  echo "⚠ WARNING: Runtime config template not found at $CONFIG_TEMPLATE"\n\
  echo "  Runtime configuration will not be available."\n\
fi\n\
\n\
echo "✓ Starting nginx..."\n\
exec nginx -g "daemon off;"\n' > /docker-entrypoint.sh && \
    chmod +x /docker-entrypoint.sh
```

### Solution - Part C: Update .dockerignore (if needed)

**File:** `frontend-hormonia/.dockerignore`

Ensure the template is NOT ignored:

```
# Allow config template
!public/api/config.js.template
```

### Solution - Part D: Update nginx.conf

**File:** `frontend-hormonia/nginx.conf`

Update the `/api/config` location (line 41-46):

```nginx
# Runtime config endpoint (serve locally)
location = /api/config {
    access_log off;
    default_type application/javascript;  # Changed from application/json
    add_header Cache-Control "no-store" always;
    add_header Content-Type "application/javascript" always;  # NEW
    try_files /api/config.js =404;  # Changed from config.json
}
```

### Testing

After deployment:

```bash
# 1. Check config.js is served
curl https://your-frontend.railway.app/api/config.js

# 2. Verify variables were substituted (no ${VITE_...} placeholders)
curl https://your-frontend.railway.app/api/config.js | grep '\${VITE'
# Should return NOTHING (no placeholders)

# 3. Check BACKEND_URL is correct
curl https://your-frontend.railway.app/api/config.js | grep VITE_API_BASE_URL
# Should show actual Railway backend URL

# 4. Test in browser console
# Open https://your-frontend.railway.app/
# Browser console:
console.log(window.__ENV_CONFIG__);
# Should show object with actual values, not placeholders
```

---

## Fix 4: Add Worker Processes Configuration

**File:** `frontend-hormonia/nginx.conf`
**Time:** 10 minutes
**Priority:** P1 - HIGH

### Problem
No worker processes configuration, nginx uses defaults which may not be optimal for Railway containers.

### Solution

**ADD** at the very beginning of `nginx.conf` (before `server {`):

```nginx
# Worker configuration
worker_processes auto;
worker_rlimit_nofile 4096;

events {
    worker_connections 2048;
    use epoll;
    multi_accept on;
}

# HTTP context
http {
    # Connection upgrade mapping
    map $http_upgrade $connection_upgrade {
        default upgrade;
        '' close;
    }

    # Server block
    server {
        listen 3000;
        # ... rest of existing config
```

**IMPORTANT:** The `http {` block must wrap the entire existing `server {` block. If nginx.conf doesn't have `http {`, add it. If it already has `http {`, add the worker config BEFORE it.

### Explanation

- `worker_processes auto` - Automatically match CPU cores (Railway containers usually have 1-2 vCPUs)
- `worker_rlimit_nofile 4096` - Allow up to 4096 open file descriptors per worker
- `worker_connections 2048` - Handle up to 2048 concurrent connections per worker
- `use epoll` - Use efficient epoll event model on Linux
- `multi_accept on` - Accept multiple connections at once
- `map $http_upgrade` - Conditionally set Connection header (fixes W3 from review)

### Testing

After deployment, check nginx is using correct worker count:

```bash
# SSH into Railway container (if possible) or check logs
railway logs

# Should see in startup logs:
# "worker process 1234 started" (for each vCPU)
```

**Alternative: Check with curl**

```bash
# Perform 100 concurrent requests to test connection handling
ab -n 1000 -c 100 https://your-frontend.railway.app/

# Should complete without connection errors
```

---

## Implementation Checklist

### Pre-Implementation
- [ ] Backup current nginx.conf
- [ ] Backup current Dockerfile
- [ ] Review Railway environment variables set

### Implementation
- [ ] **Fix 1:** Add CSP header to nginx.conf
- [ ] **Fix 2:** Add HSTS header to nginx.conf
- [ ] **Fix 3a:** Create `public/api/config.js.template`
- [ ] **Fix 3b:** Update Dockerfile entrypoint script
- [ ] **Fix 3c:** Update nginx.conf `/api/config` location
- [ ] **Fix 4:** Add worker configuration to nginx.conf

### Testing (Local)
- [ ] Build Docker image locally: `docker build -t frontend-test .`
- [ ] Run container: `docker run -p 3000:3000 -e VITE_API_BASE_URL=http://localhost:8000 frontend-test`
- [ ] Check health: `curl http://localhost:3000/health`
- [ ] Check config: `curl http://localhost:3000/api/config.js`
- [ ] Verify no placeholders: `curl http://localhost:3000/api/config.js | grep '\${VITE'`
- [ ] Check headers: `curl -I http://localhost:3000/`

### Deployment (Railway)
- [ ] Commit changes to git
- [ ] Push to Railway
- [ ] Monitor build logs for errors
- [ ] Check deployment logs for nginx startup messages

### Testing (Production)
- [ ] Verify CSP header: `curl -I https://your-app.railway.app/ | grep -i content-security-policy`
- [ ] Verify HSTS header: `curl -I https://your-app.railway.app/ | grep -i strict-transport-security`
- [ ] Verify runtime config: `curl https://your-app.railway.app/api/config.js`
- [ ] Test in browser: Check `window.__ENV_CONFIG__` in console
- [ ] Test API proxy: `curl https://your-app.railway.app/api/v1/health`
- [ ] Test WebSocket: `wscat -c wss://your-app.railway.app/ws`

---

## Rollback Plan

If deployment fails:

### Immediate Rollback (Railway)
1. Go to Railway dashboard
2. Find previous deployment
3. Click "Redeploy"

### Git Rollback
```bash
git revert HEAD
git push origin main
```

### Manual Fix
If only config.js template is broken:

1. SSH into Railway container (if possible)
2. Manually create `/usr/share/nginx/html/api/config.js`:
```javascript
window.__ENV_CONFIG__ = {
  VITE_API_BASE_URL: 'https://backend-production-e0bd.up.railway.app',
  // ... hardcoded values as temporary fix
};
```
3. Restart nginx: `nginx -s reload`

---

## Environment Variables Required

Ensure these are set in Railway:

### Critical (Required)
- `VITE_API_BASE_URL` - Backend API URL (e.g., `https://backend-prod.railway.app`)
- `VITE_WS_BASE_URL` - WebSocket URL (e.g., `wss://backend-prod.railway.app/ws`)

### Authentication (Required if using)
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_FIREBASE_API_KEY`
- `VITE_FIREBASE_AUTH_DOMAIN`
- `VITE_FIREBASE_PROJECT_ID`
- `VITE_FIREBASE_STORAGE_BUCKET`
- `VITE_FIREBASE_MESSAGING_SENDER_ID`
- `VITE_FIREBASE_APP_ID`

### Optional (Have Defaults)
- `VITE_ENVIRONMENT` (default: `production`)
- `VITE_DEBUG_MODE` (default: `false`)
- `VITE_WHATSAPP_INSTANCE_NAME` (default: `hormonia-instance`)
- `VITE_SESSION_TIMEOUT` (default: `3600000`)
- `VITE_TOKEN_REFRESH_THRESHOLD` (default: `300000`)
- `VITE_MAX_FILE_SIZE` (default: `10485760`)

---

## Common Issues & Solutions

### Issue 1: "BACKEND_URL substitution failed"

**Symptom:** Build fails with error message
**Cause:** `$BACKEND_URL` or `$VITE_API_BASE_URL` not set
**Solution:** Set `VITE_API_BASE_URL` in Railway environment variables

### Issue 2: "config.js shows ${VITE_API_BASE_URL}"

**Symptom:** Runtime config has placeholders
**Cause:** `envsubst` didn't run or environment variables not exported
**Solution:** Check entrypoint script exports environment variables before `envsubst`

### Issue 3: "CSP blocks Firebase/Supabase"

**Symptom:** Console errors: "Blocked by Content-Security-Policy"
**Cause:** CSP too restrictive
**Solution:** Add specific domains to `connect-src`:
```nginx
connect-src 'self' https://specific-domain.com
```

### Issue 4: "nginx won't start after worker config"

**Symptom:** Container crashes on startup
**Cause:** Syntax error in nginx.conf
**Solution:** Validate config locally:
```bash
docker run --rm -v $(pwd)/nginx.conf:/etc/nginx/conf.d/default.conf nginx:alpine nginx -t
```

---

## Next Steps After Critical Fixes

After successfully deploying these 4 critical fixes:

### Phase 2: High Priority (Week 1)
1. Add keepalive settings
2. Add missing proxy headers (`X-Forwarded-Host`, `X-Forwarded-Port`)
3. Add request size limits

See **NGINX_CONFIGURATION_REVIEW.md** Section 10 for full details.

---

**Document Version:** 1.0
**Last Updated:** 2025-10-04
**Owner:** System Architecture Designer
