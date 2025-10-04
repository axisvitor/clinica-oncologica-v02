# Nginx Configuration Review - Frontend Hormonia
**Review Date:** 2025-10-04
**Reviewer:** System Architecture Designer
**Environment:** Production (Railway Deployment)
**Nginx Version:** nginx:alpine (latest)

---

## Executive Summary

The Nginx configuration for `frontend-hormonia` has been reviewed with focus on security, performance, and production readiness for Railway deployment. The configuration is **MOSTLY SOLID** with some **CRITICAL GAPS** that must be addressed before production deployment.

### Overall Rating: 🟡 **7.2/10** (Good, needs improvements)

**Critical Issues Found:** 3
**Warnings:** 5
**Best Practices Missed:** 7

---

## 1. Proxy Configuration Analysis

### ✅ **GOOD PRACTICES IMPLEMENTED**

#### 1.1 API Proxy Configuration (`/api/`)
```nginx
location /api/ {
    proxy_pass ${BACKEND_URL};
    proxy_http_version 1.1;

    # SNI for HTTPS upstream
    proxy_ssl_server_name on;
    proxy_ssl_name $proxy_host;

    # Standard proxy headers
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Timeouts
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;

    # Disable buffering for real-time
    proxy_buffering off;
    proxy_request_buffering off;
}
```

**Strengths:**
- ✅ Proper SNI configuration for HTTPS backends (Railway)
- ✅ HTTP/1.1 protocol enabled
- ✅ Correct forwarding headers (X-Real-IP, X-Forwarded-For, X-Forwarded-Proto)
- ✅ Buffering disabled for real-time data
- ✅ Reasonable timeouts (60s)

#### 1.2 WebSocket Proxy Configuration (`/ws`)
```nginx
location /ws {
    proxy_pass ${BACKEND_URL};
    proxy_http_version 1.1;
    proxy_ssl_server_name on;
    proxy_ssl_name $proxy_host;

    # WebSocket upgrade headers
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";

    # Long timeouts for persistent connections
    proxy_connect_timeout 7d;
    proxy_send_timeout 7d;
    proxy_read_timeout 7d;
}
```

**Strengths:**
- ✅ Correct WebSocket upgrade headers
- ✅ Very long timeouts (7 days) for persistent connections
- ✅ SNI support for HTTPS WebSocket (wss://)

### 🟡 **WARNINGS**

#### W1: Missing `X-Forwarded-Host` Header
**Impact:** Medium
**Location:** Both `/api/` and `/ws` locations

The `X-Forwarded-Host` header should be set to preserve the original host requested by the client.

**Recommendation:**
```nginx
proxy_set_header X-Forwarded-Host $host;
```

#### W2: Missing `X-Forwarded-Port` Header
**Impact:** Low
**Location:** Both `/api/` and `/ws` locations

**Recommendation:**
```nginx
proxy_set_header X-Forwarded-Port $server_port;
```

#### W3: Hardcoded Connection Header for API
**Impact:** Low
**Location:** `/api/` location

The API proxy sets WebSocket upgrade headers even though it's primarily for HTTP/REST.

**Current:**
```nginx
location /api/ {
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

**Should be conditional:**
```nginx
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection $connection_upgrade;
```

With mapping at server level:
```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}
```

---

## 2. Security Headers Analysis

### ✅ **IMPLEMENTED HEADERS**

```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

**Strengths:**
- ✅ `always` directive ensures headers sent even on error responses
- ✅ X-Frame-Options protects against clickjacking
- ✅ X-Content-Type-Options prevents MIME sniffing
- ✅ Referrer-Policy protects privacy

### 🔴 **CRITICAL MISSING HEADERS**

#### C1: Missing Content-Security-Policy (CSP)
**Severity:** CRITICAL
**Impact:** HIGH - Vulnerable to XSS attacks

**Current:** Not implemented
**Required for Production:**

```nginx
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://apis.google.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https://backend-production-e0bd.up.railway.app wss://backend-production-e0bd.up.railway.app https://*.supabase.co https://*.firebaseio.com https://*.googleapis.com; frame-ancestors 'self'; base-uri 'self'; form-action 'self';" always;
```

**Justification:**
- Protects against XSS by restricting resource origins
- `unsafe-inline` and `unsafe-eval` needed for Vite/React apps
- `connect-src` includes backend API, Supabase, Firebase
- Should be customized based on actual domains

#### C2: Missing Strict-Transport-Security (HSTS)
**Severity:** CRITICAL
**Impact:** HIGH - Vulnerable to SSL stripping attacks

**Current:** Not implemented
**Required for Production:**

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
```

**Justification:**
- Forces HTTPS for 1 year (31536000 seconds)
- `includeSubDomains` protects all subdomains
- `preload` enables HSTS preload list submission

#### C3: Missing Permissions-Policy
**Severity:** MEDIUM
**Impact:** MEDIUM - No control over browser features

**Recommendation:**
```nginx
add_header Permissions-Policy "geolocation=(), microphone=(), camera=(), payment=()" always;
```

Adjust based on features needed (e.g., if telemedicine needs camera/mic).

### 🟡 **DEPRECATED HEADER**

#### W4: X-XSS-Protection is Deprecated
**Impact:** Low
**Status:** Deprecated in modern browsers

**Current:**
```nginx
add_header X-XSS-Protection "1; mode=block" always;
```

**Recommendation:** Remove (CSP is the modern replacement)

---

## 3. Performance Configuration Analysis

### ✅ **GOOD PRACTICES IMPLEMENTED**

#### 3.1 Gzip Compression
```nginx
gzip on;
gzip_vary on;
gzip_min_length 1024;
gzip_types text/plain text/css text/xml application/javascript application/json application/xml+rss application/rss+xml application/atom+xml image/svg+xml application/x-font-ttf application/vnd.ms-fontobject font/opentype;
```

**Strengths:**
- ✅ Comprehensive MIME types covered
- ✅ `gzip_vary on` for proper caching with/without compression
- ✅ Minimum size threshold (1024 bytes)

#### 3.2 Static Asset Caching
```nginx
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

**Strengths:**
- ✅ 1-year expiration for static assets (best practice)
- ✅ `immutable` directive for aggressive caching

#### 3.3 HTML No-Cache
```nginx
location ~* \.(html)$ {
    expires -1;
    add_header Cache-Control "no-cache, no-store, must-revalidate";
}
```

**Strengths:**
- ✅ Prevents HTML caching (good for SPA updates)

### 🔴 **CRITICAL MISSING: Worker Configuration**

**Current:** Uses nginx:alpine defaults
**Problem:** Not optimized for Railway containers

**Required at top of nginx.conf:**
```nginx
worker_processes auto;
worker_rlimit_nofile 4096;

events {
    worker_connections 2048;
    use epoll;
    multi_accept on;
}
```

**Justification:**
- `worker_processes auto` matches CPU cores
- `worker_connections 2048` handles concurrent connections
- `epoll` is efficient on Linux
- `multi_accept on` improves throughput

### 🟡 **MISSING OPTIMIZATIONS**

#### W5: No Keepalive Configuration
**Impact:** Medium - Extra connection overhead

**Recommendation:**
```nginx
keepalive_timeout 65;
keepalive_requests 100;
```

#### W6: Missing Gzip Compression Level
**Impact:** Low - Not tuned

**Current:** Uses default (level 6)
**Recommendation:**
```nginx
gzip_comp_level 6;  # Explicit is better
```

#### W7: No Brotli Compression
**Impact:** Low - Better compression than gzip

**Recommendation:** Add Brotli module (requires nginx build)
```nginx
brotli on;
brotli_comp_level 6;
brotli_types text/plain text/css application/javascript application/json;
```

---

## 4. SPA Routing Analysis

### ✅ **CORRECT IMPLEMENTATION**

```nginx
location / {
    try_files $uri $uri/ /index.html;
}

error_page 404 /index.html;
error_page 500 502 503 504 /index.html;
```

**Strengths:**
- ✅ Perfect for React Router
- ✅ Handles client-side routing correctly
- ✅ Error pages fallback to index.html

**No issues found in SPA routing.**

---

## 5. Runtime Configuration Analysis

### ✅ **GOOD: Docker Entrypoint Script**

**Dockerfile Entrypoint (embedded):**
```bash
#!/bin/sh
set -e

# Dynamic PORT from Railway
if [ -n "$PORT" ]; then
  sed -i "s/listen 3000;/listen $PORT;/g" /etc/nginx/conf.d/default.conf
fi

# BACKEND_URL substitution
if [ -z "$BACKEND_URL" ] && [ -n "$VITE_API_BASE_URL" ]; then
  BACKEND_URL="$VITE_API_BASE_URL"
fi

if [ -z "$BACKEND_URL" ]; then
  BACKEND_URL="http://backend:8000"
fi

sed -i "s|\${BACKEND_URL}|$BACKEND_URL|g" /etc/nginx/conf.d/default.conf

exec nginx -g "daemon off;"
```

**Strengths:**
- ✅ Handles Railway's dynamic `$PORT` variable
- ✅ Fallback to `VITE_API_BASE_URL` if `BACKEND_URL` not set
- ✅ Final fallback to `http://backend:8000`
- ✅ Uses `sed` for runtime substitution
- ✅ `set -e` for error handling

### 🟡 **POTENTIAL ISSUE: Missing Validation**

**W8: No validation of substitution success**

**Recommendation:**
```bash
# After sed substitution
if grep -q '\${BACKEND_URL}' /etc/nginx/conf.d/default.conf; then
  echo "ERROR: BACKEND_URL substitution failed!"
  exit 1
fi
```

---

## 6. Runtime Config Endpoint Analysis

### ✅ **IMPLEMENTED: `/api/config` Endpoint**

```nginx
location = /api/config {
    access_log off;
    default_type application/json;
    add_header Cache-Control "no-store" always;
    try_files /api/config /api/config.json =404;
}
```

**Strengths:**
- ✅ Serves local file (no backend proxy)
- ✅ No caching (`no-store`)
- ✅ Proper content-type (application/json)

**File:** `public/api/config.js`

### 🔴 **CRITICAL ISSUE: Static Config Values**

**Current `public/api/config.js`:**
```javascript
window.__ENV_CONFIG__ = {
    VITE_API_BASE_URL: 'https://backend-production-e0bd.up.railway.app',  // HARDCODED!
    VITE_WS_BASE_URL: 'wss://backend-production-e0bd.up.railway.app/ws/connect',  // HARDCODED!
    // ...
};
```

**Problem:** Backend URL is hardcoded, defeats purpose of runtime config

**Solution:** Entrypoint should substitute environment variables in config.js

**Add to entrypoint script:**
```bash
# Substitute environment variables in config.js
if [ -f /usr/share/nginx/html/api/config.js ]; then
  envsubst < /usr/share/nginx/html/api/config.js.template > /usr/share/nginx/html/api/config.js
fi
```

**Create `public/api/config.js.template`:**
```javascript
window.__ENV_CONFIG__ = {
    VITE_API_BASE_URL: '${VITE_API_BASE_URL}',
    VITE_WS_BASE_URL: '${VITE_WS_BASE_URL}',
    // ...
};
```

---

## 7. Health Check Analysis

### ✅ **PROPERLY IMPLEMENTED**

**Nginx Location:**
```nginx
location /health {
    access_log off;
    return 200 "healthy\n";
    add_header Content-Type text/plain;
}
```

**Dockerfile Healthcheck:**
```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT:-3000}/health || exit 1
```

**Strengths:**
- ✅ Lightweight (no access logging)
- ✅ Uses dynamic `$PORT` variable
- ✅ Reasonable intervals (30s)
- ✅ Quick timeout (3s)
- ✅ Start period allows nginx to start

**No issues found.**

---

## 8. Comparison with Nginx Best Practices

| Best Practice | Status | Notes |
|---------------|--------|-------|
| Worker processes optimization | 🔴 Missing | No worker config |
| Gzip compression | ✅ Good | Comprehensive types |
| Static asset caching | ✅ Excellent | 1 year + immutable |
| Security headers (CSP) | 🔴 Missing | Critical gap |
| Security headers (HSTS) | 🔴 Missing | Critical gap |
| WebSocket support | ✅ Excellent | Proper upgrade headers |
| SPA routing | ✅ Perfect | Correct try_files |
| Proxy headers | 🟡 Good | Missing X-Forwarded-Host |
| Buffering disabled | ✅ Good | For real-time data |
| Keepalive connections | 🟡 Missing | Uses defaults |
| Error handling | ✅ Good | SPA-aware |
| Health checks | ✅ Excellent | Docker + nginx endpoint |
| SSL/TLS config | N/A | Handled by Railway |
| Rate limiting | 🔴 Missing | Should be considered |
| Request size limits | 🟡 Default | Should be explicit |

---

## 9. Critical Issues Summary

### 🔴 **MUST FIX BEFORE PRODUCTION**

1. **Missing Content-Security-Policy (CSP)**
   - **Risk:** XSS vulnerabilities
   - **Priority:** P0
   - **Effort:** 30 minutes

2. **Missing Strict-Transport-Security (HSTS)**
   - **Risk:** SSL stripping attacks
   - **Priority:** P0
   - **Effort:** 5 minutes

3. **Hardcoded Config in `/api/config.js`**
   - **Risk:** Cannot change backend URL without rebuild
   - **Priority:** P0
   - **Effort:** 45 minutes

4. **Missing Worker Processes Configuration**
   - **Risk:** Poor performance under load
   - **Priority:** P1
   - **Effort:** 10 minutes

---

## 10. Recommendations by Priority

### P0: Critical (Fix Before Production)

1. **Add Content-Security-Policy**
   ```nginx
   add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://apis.google.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https://*.railway.app wss://*.railway.app https://*.supabase.co https://*.firebaseio.com; frame-ancestors 'self'; base-uri 'self'; form-action 'self';" always;
   ```

2. **Add HSTS**
   ```nginx
   add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
   ```

3. **Fix Runtime Config Substitution**
   - Convert `public/api/config.js` to template
   - Add `envsubst` to entrypoint script

### P1: High Priority

4. **Add Worker Configuration**
   ```nginx
   worker_processes auto;
   worker_rlimit_nofile 4096;

   events {
       worker_connections 2048;
       use epoll;
       multi_accept on;
   }
   ```

5. **Add Keepalive Settings**
   ```nginx
   keepalive_timeout 65;
   keepalive_requests 100;
   ```

6. **Add Missing Proxy Headers**
   ```nginx
   proxy_set_header X-Forwarded-Host $host;
   proxy_set_header X-Forwarded-Port $server_port;
   ```

### P2: Medium Priority

7. **Add Request Size Limits**
   ```nginx
   client_max_body_size 10M;
   client_body_buffer_size 128k;
   ```

8. **Add Permissions-Policy**
   ```nginx
   add_header Permissions-Policy "geolocation=(), microphone=(), camera=(), payment=()" always;
   ```

9. **Add Connection Upgrade Mapping**
   ```nginx
   map $http_upgrade $connection_upgrade {
       default upgrade;
       '' close;
   }
   ```

10. **Add Rate Limiting (if needed)**
    ```nginx
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;
        # ... rest of config
    }
    ```

---

## 11. Post-Deploy Validation Checklist

### Functional Tests

- [ ] **Health endpoint returns 200**
  ```bash
  curl -f https://frontend-production.railway.app/health
  ```

- [ ] **API proxy works**
  ```bash
  curl -I https://frontend-production.railway.app/api/v1/health
  ```

- [ ] **WebSocket connects**
  ```bash
  wscat -c wss://frontend-production.railway.app/ws
  ```

- [ ] **Runtime config loads**
  ```bash
  curl https://frontend-production.railway.app/api/config
  ```

- [ ] **Static assets cached (1 year)**
  ```bash
  curl -I https://frontend-production.railway.app/assets/index-abc123.js
  # Check: Cache-Control: public, immutable
  # Check: Expires: (1 year from now)
  ```

- [ ] **HTML not cached**
  ```bash
  curl -I https://frontend-production.railway.app/
  # Check: Cache-Control: no-cache, no-store, must-revalidate
  ```

- [ ] **SPA routing works**
  ```bash
  curl -I https://frontend-production.railway.app/pacientes
  # Should return 200 with index.html
  ```

### Security Tests

- [ ] **CSP header present**
  ```bash
  curl -I https://frontend-production.railway.app/ | grep -i content-security-policy
  ```

- [ ] **HSTS header present**
  ```bash
  curl -I https://frontend-production.railway.app/ | grep -i strict-transport-security
  ```

- [ ] **X-Frame-Options present**
  ```bash
  curl -I https://frontend-production.railway.app/ | grep -i x-frame-options
  ```

- [ ] **X-Content-Type-Options present**
  ```bash
  curl -I https://frontend-production.railway.app/ | grep -i x-content-type-options
  ```

- [ ] **Referrer-Policy present**
  ```bash
  curl -I https://frontend-production.railway.app/ | grep -i referrer-policy
  ```

### Performance Tests

- [ ] **Gzip compression active**
  ```bash
  curl -H "Accept-Encoding: gzip" -I https://frontend-production.railway.app/
  # Check: Content-Encoding: gzip
  ```

- [ ] **Response time < 200ms (static)**
  ```bash
  curl -w "@curl-format.txt" -o /dev/null -s https://frontend-production.railway.app/
  ```

- [ ] **WebSocket latency < 100ms**

### Configuration Tests

- [ ] **PORT dynamic from Railway**
  ```bash
  # Check Railway logs for: "Configured nginx to listen on port XXXX"
  ```

- [ ] **BACKEND_URL substituted**
  ```bash
  # Check Railway logs for: "Configured BACKEND_URL to https://..."
  # Verify no ${BACKEND_URL} in nginx config
  railway run cat /etc/nginx/conf.d/default.conf | grep proxy_pass
  ```

- [ ] **Environment variables in config.js**
  ```bash
  curl https://frontend-production.railway.app/api/config | jq .VITE_API_BASE_URL
  # Should match Railway env var, not hardcoded value
  ```

---

## 12. Architecture Decision Records (ADRs)

### ADR-001: Use Nginx as Static File Server + Reverse Proxy

**Status:** Accepted
**Context:** Need to serve React SPA and proxy API/WebSocket to backend
**Decision:** Use nginx:alpine with embedded config
**Consequences:**
- ✅ Lightweight (alpine)
- ✅ Battle-tested for static files
- ✅ Excellent proxy performance
- ⚠️ Requires runtime variable substitution

### ADR-002: Runtime Config via `/api/config` Endpoint

**Status:** Accepted (needs fix)
**Context:** Vite build-time env vars not suitable for Railway dynamic deployments
**Decision:** Serve runtime config as JSON endpoint
**Consequences:**
- ✅ Can change backend URL without rebuild
- ✅ Environment-specific configs
- 🔴 Current implementation is hardcoded (needs fix)

### ADR-003: WebSocket Proxy on Same Domain

**Status:** Accepted
**Context:** Avoid CORS issues with WebSocket connections
**Decision:** Proxy `/ws` through nginx to backend
**Consequences:**
- ✅ No CORS preflight for WebSocket
- ✅ Single domain for frontend + backend
- ✅ SSL/TLS handled by Railway

### ADR-004: Long WebSocket Timeouts (7 days)

**Status:** Accepted
**Context:** WhatsApp integration requires persistent connections
**Decision:** Set 7-day timeouts for `/ws` location
**Consequences:**
- ✅ Supports long-lived connections
- ⚠️ Keeps connections open (monitor resource usage)

---

## 13. Nginx Configuration Template (Recommended)

```nginx
# Worker configuration (add at top of file)
worker_processes auto;
worker_rlimit_nofile 4096;

events {
    worker_connections 2048;
    use epoll;
    multi_accept on;
}

# HTTP block
http {
    # Connection upgrade mapping
    map $http_upgrade $connection_upgrade {
        default upgrade;
        '' close;
    }

    # Rate limiting (optional)
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

    # Server block
    server {
        listen 3000;
        server_name _;

        root /usr/share/nginx/html;
        index index.html;

        # Request size limits
        client_max_body_size 10M;
        client_body_buffer_size 128k;

        # Keepalive
        keepalive_timeout 65;
        keepalive_requests 100;

        # Compression
        gzip on;
        gzip_vary on;
        gzip_min_length 1024;
        gzip_comp_level 6;
        gzip_types text/plain text/css text/xml application/javascript application/json application/xml+rss application/rss+xml application/atom+xml image/svg+xml application/x-font-ttf application/vnd.ms-fontobject font/opentype;

        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
        add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://apis.google.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https://*.railway.app wss://*.railway.app https://*.supabase.co https://*.firebaseio.com https://*.googleapis.com; frame-ancestors 'self'; base-uri 'self'; form-action 'self';" always;
        add_header Permissions-Policy "geolocation=(), microphone=(), camera=(), payment=()" always;

        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }

        # Don't cache HTML files
        location ~* \.(html)$ {
            expires -1;
            add_header Cache-Control "no-cache, no-store, must-revalidate";
        }

        # Health check endpoint
        location /health {
            access_log off;
            return 200 "healthy\n";
            add_header Content-Type text/plain;
        }

        # Runtime config endpoint (serve locally)
        location = /api/config {
            access_log off;
            default_type application/json;
            add_header Cache-Control "no-store" always;
            try_files /api/config.json =404;
        }

        # Proxy API calls to backend
        location /api/ {
            # Rate limiting (optional)
            # limit_req zone=api_limit burst=20 nodelay;

            proxy_pass ${BACKEND_URL};
            proxy_http_version 1.1;

            # SNI for HTTPS upstream
            proxy_ssl_server_name on;
            proxy_ssl_name $proxy_host;

            # Conditional WebSocket support
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;

            # Standard proxy headers
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Forwarded-Host $host;
            proxy_set_header X-Forwarded-Port $server_port;

            # Timeouts
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;

            # Disable buffering for real-time data
            proxy_buffering off;
            proxy_request_buffering off;
        }

        # WebSocket support for WhatsApp and real-time features
        location /ws {
            proxy_pass ${BACKEND_URL};
            proxy_http_version 1.1;
            proxy_ssl_server_name on;
            proxy_ssl_name $proxy_host;

            # WebSocket upgrade headers
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";

            # Standard proxy headers
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Forwarded-Host $host;
            proxy_set_header X-Forwarded-Port $server_port;

            # WebSocket specific timeouts (7 days)
            proxy_connect_timeout 7d;
            proxy_send_timeout 7d;
            proxy_read_timeout 7d;
        }

        # SPA fallback
        location / {
            try_files $uri $uri/ /index.html;
        }

        # Custom error pages
        error_page 404 /index.html;
        error_page 500 502 503 504 /index.html;
    }
}
```

---

## 14. Summary & Action Plan

### Current State
- **Proxy Configuration:** ✅ Solid (minor improvements needed)
- **WebSocket Support:** ✅ Excellent
- **SPA Routing:** ✅ Perfect
- **Performance:** 🟡 Good (missing worker config)
- **Security:** 🔴 Critical gaps (CSP, HSTS)
- **Runtime Config:** 🔴 Broken (hardcoded values)

### Action Plan

**Phase 1: Critical Fixes (Before Production Deploy)**
1. Add CSP header *(30 min)*
2. Add HSTS header *(5 min)*
3. Fix runtime config substitution *(45 min)*
4. Add worker processes config *(10 min)*

**Phase 2: High Priority (Week 1)**
5. Add keepalive settings *(5 min)*
6. Add missing proxy headers *(10 min)*
7. Add request size limits *(5 min)*

**Phase 3: Nice-to-Have (Week 2+)**
8. Add Permissions-Policy *(10 min)*
9. Add connection upgrade mapping *(15 min)*
10. Consider rate limiting *(60 min)*

### Estimated Total Effort
- **Phase 1 (Critical):** ~1.5 hours
- **Phase 2 (High):** ~30 minutes
- **Phase 3 (Optional):** ~1.5 hours

---

## 15. References

- [Nginx Reverse Proxy Guide](https://docs.nginx.com/nginx/admin-guide/web-server/reverse-proxy/)
- [Nginx WebSocket Proxying](https://nginx.org/en/docs/http/websocket.html)
- [OWASP Secure Headers Project](https://owasp.org/www-project-secure-headers/)
- [MDN Content-Security-Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP)
- [Railway Nginx Deployment](https://docs.railway.app/guides/dockerfiles)
- [React Router with Nginx](https://create-react-app.dev/docs/deployment/#nginx)

---

**Review Completed:** 2025-10-04
**Next Review:** After implementing Phase 1 fixes
**Reviewer:** System Architecture Designer
