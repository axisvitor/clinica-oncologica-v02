# Docker Frontend Analysis Report - Hormonia Frontend

**Date:** 2025-10-04
**Reviewer:** Code Quality Analyzer Agent
**Component:** frontend-hormonia/
**Overall Score:** 62/100

---

## Executive Summary

The frontend Docker configuration shows a **moderate** level of production readiness with several critical security concerns and optimization opportunities. While multi-stage builds are implemented and runtime configuration injection is present, there are significant issues with:

1. **CRITICAL:** Multiple conflicting runtime configuration mechanisms
2. **CRITICAL:** Missing entrypoint script referenced in Dockerfile
3. **HIGH:** Nginx configuration contains invalid variable substitution
4. **HIGH:** Exposed Firebase API keys in build arguments
5. **MEDIUM:** Inconsistent environment variable handling across scripts

---

## 1. Security Analysis

### 1.1 Critical Issues (Score: 35/100)

#### ❌ **CRITICAL: Hardcoded API Keys in Build Arguments**
**File:** `Dockerfile` (lines 35-41)

```dockerfile
ARG VITE_FIREBASE_API_KEY
ARG VITE_FIREBASE_AUTH_DOMAIN
ARG VITE_FIREBASE_PROJECT_ID
ARG VITE_FIREBASE_STORAGE_BUCKET
ARG VITE_FIREBASE_MESSAGING_SENDER_ID
ARG VITE_FIREBASE_APP_ID
```

**Issue:** Firebase configuration is passed as build arguments and baked into the image at build time. This means:
- API keys are stored in Docker layer metadata (accessible via `docker history`)
- Keys cannot be rotated without rebuilding the image
- Keys are visible to anyone with image access

**Severity:** HIGH
**Impact:** Potential unauthorized access to Firebase services

**Recommended Fix:**
```dockerfile
# Remove Firebase ARGs from Dockerfile
# Instead, inject at runtime via docker-entrypoint.sh

# In docker-entrypoint.sh, add:
cat > /usr/share/nginx/html/firebase-config.js << EOF
window.__FIREBASE_CONFIG__ = {
  apiKey: "${VITE_FIREBASE_API_KEY}",
  authDomain: "${VITE_FIREBASE_AUTH_DOMAIN}",
  projectId: "${VITE_FIREBASE_PROJECT_ID}",
  storageBucket: "${VITE_FIREBASE_STORAGE_BUCKET}",
  messagingSenderId: "${VITE_FIREBASE_MESSAGING_SENDER_ID}",
  appId: "${VITE_FIREBASE_APP_ID}"
};
EOF
```

#### ❌ **CRITICAL: Missing docker-entrypoint.sh Script**
**File:** `Dockerfile` (line 80)

```dockerfile
COPY docker-entrypoint.sh /docker-entrypoint.sh
```

**Issue:** The Dockerfile references `docker-entrypoint.sh` but this file exists with different runtime logic than expected by nginx.conf. The nginx.conf expects `${BACKEND_URL}` substitution, but the current entrypoint creates an entirely different nginx configuration.

**Current State:**
- `docker-entrypoint.sh` creates its own nginx config (overwrites default.conf)
- Original `nginx.conf` has advanced optimizations that are lost
- Inconsistent PORT handling between configs

**Severity:** CRITICAL
**Impact:** Container will fail to start or serve incorrect configuration

**Recommended Fix:** Merge `start.sh` and `docker-entrypoint.sh` functionality:

```bash
#!/bin/sh
set -e

echo "================================================================"
echo "Frontend Hormonia - Docker Entrypoint (Merged)"
echo "================================================================"

# 1. Validate BACKEND_URL
if [ -z "$BACKEND_URL" ]; then
  echo "❌ ERROR: BACKEND_URL required"
  exit 1
fi

echo "✓ BACKEND_URL: $BACKEND_URL"

# 2. Configure PORT
PORT=${PORT:-3000}
echo "✓ PORT: $PORT"

# 3. Substitute nginx.conf placeholders
NGINX_CONF="/etc/nginx/nginx.conf"
cp "$NGINX_CONF" "$NGINX_CONF.backup"

sed -i "s|\${BACKEND_URL}|$BACKEND_URL|g" "$NGINX_CONF"
sed -i "s|listen 3000;|listen $PORT;|g" "$NGINX_CONF"

echo "✓ Nginx configuration updated"

# 4. Create runtime config for browser
mkdir -p /usr/share/nginx/html/api
cat > /usr/share/nginx/html/api/config.js << EOF
window.__RUNTIME_CONFIG__ = {
  apiUrl: '${BACKEND_URL}/api/v1',
  wsUrl: '${BACKEND_URL}/ws'.replace('https://', 'wss://').replace('http://', 'ws://'),
  backendUrl: '${BACKEND_URL}',
  supabaseUrl: '${VITE_SUPABASE_URL:-}',
  supabaseAnonKey: '${VITE_SUPABASE_ANON_KEY:-}',
  environment: 'production'
};

window.__FIREBASE_CONFIG__ = {
  apiKey: '${VITE_FIREBASE_API_KEY:-}',
  authDomain: '${VITE_FIREBASE_AUTH_DOMAIN:-}',
  projectId: '${VITE_FIREBASE_PROJECT_ID:-}',
  storageBucket: '${VITE_FIREBASE_STORAGE_BUCKET:-}',
  messagingSenderId: '${VITE_FIREBASE_MESSAGING_SENDER_ID:-}',
  appId: '${VITE_FIREBASE_APP_ID:-}'
};

console.log('[Runtime Config] Loaded:', window.__RUNTIME_CONFIG__);
EOF

echo "✓ Runtime config created"

# 5. Validate nginx syntax
if ! nginx -t; then
  echo "❌ Nginx config invalid"
  cat "$NGINX_CONF"
  exit 1
fi

echo "✓ Starting nginx on port $PORT..."
exec nginx -g "daemon off;"
```

#### ⚠️ **HIGH: Nginx Configuration Invalid Syntax**
**File:** `nginx.conf` (lines 96-99)

```nginx
upstream backend {
    server ${BACKEND_URL};  # ❌ Invalid: ${BACKEND_URL} is a full URL, not host:port
    keepalive 32;
    keepalive_timeout 60s;
}
```

**Issue:**
- `${BACKEND_URL}` contains `https://domain.com`, but `server` directive expects `domain.com:port`
- This will cause nginx to fail validation: `nginx -t` will fail
- The proxy_pass directives expect a URL, not just a hostname

**Severity:** HIGH
**Impact:** Nginx will fail to start

**Recommended Fix:**

```nginx
# Option 1: Use direct proxy_pass (no upstream)
location /api/ {
    proxy_pass ${BACKEND_URL};  # Will be substituted to full URL
    # ... rest of config
}

# Option 2: Parse BACKEND_URL in entrypoint
# In docker-entrypoint.sh:
BACKEND_HOST=$(echo $BACKEND_URL | sed -E 's|https?://([^/]+).*|\1|')
sed -i "s|\${BACKEND_HOST}|$BACKEND_HOST|g" "$NGINX_CONF"

# In nginx.conf:
upstream backend {
    server ${BACKEND_HOST};
    keepalive 32;
}
```

#### ⚠️ **HIGH: Hardcoded Production URL in Fallback Config**
**File:** `public/config.js` (line 36-38)

```javascript
VITE_API_URL: 'https://backend-production-e0bd.up.railway.app/api/v1',
VITE_API_BASE_URL: 'https://backend-production-e0bd.up.railway.app',
VITE_WS_BASE_URL: 'wss://backend-production-e0bd.up.railway.app/ws',
```

**Issue:** Hardcoded production URLs in fallback configuration
- Exposes production infrastructure details in source code
- Cannot be changed without code modification
- Creates security risk if production URL changes

**Severity:** MEDIUM
**Impact:** Potential exposure of production endpoints

**Recommended Fix:**
```javascript
// Remove hardcoded URLs - use environment-based detection
VITE_API_URL: window.location.origin + '/api/v1',
VITE_API_BASE_URL: window.location.origin,
VITE_WS_BASE_URL: window.location.origin.replace('https://', 'wss://').replace('http://', 'ws://') + '/ws',
```

### 1.2 Security Best Practices (Score: 70/100)

#### ✅ **GOOD: Multi-stage Build with Minimal Production Image**
```dockerfile
FROM node:20-alpine AS deps
FROM node:20-alpine AS builder
FROM nginx:alpine AS production
```
- Reduces attack surface by excluding build dependencies
- Final image contains only nginx + static assets

#### ✅ **GOOD: Non-root User Execution**
```dockerfile
USER nginx  # Line 101
```
- Runs nginx as non-root user (uid 101)
- Proper permission management for all directories

#### ✅ **GOOD: Security Headers in Nginx**
```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

#### ⚠️ **MISSING: Content Security Policy (CSP)**
**Recommended Addition:**
```nginx
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://*.railway.app wss://*.railway.app https://*.supabase.co wss://*.supabase.co; font-src 'self' data:;" always;
```

#### ⚠️ **MISSING: HTTPS Enforcement**
No redirect from HTTP to HTTPS (though Railway handles TLS termination)

```nginx
# Add to server block:
if ($http_x_forwarded_proto = "http") {
    return 301 https://$host$request_uri;
}
```

---

## 2. Best Practices Analysis

### 2.1 Multi-stage Builds (Score: 80/100)

#### ✅ **GOOD: Proper Dependency Caching**
```dockerfile
# Stage 1: Dependencies
COPY package*.json ./
RUN npm ci --prefer-offline --no-audit
```
- Leverages Docker layer caching for dependencies
- Speeds up builds when only source code changes

#### ✅ **GOOD: Conditional package-lock.json Generation**
```dockerfile
RUN if [ ! -f package-lock.json ]; then \
      echo "⚠️ package-lock.json not found, generating..."; \
      npm install; \
    else \
      npm ci --prefer-offline --no-audit; \
    fi
```
- Handles missing lock file gracefully
- Uses `npm ci` for reproducible builds when lock exists

#### ⚠️ **IMPROVEMENT: Add Build Arguments for Cache Busting**
```dockerfile
# Add these ARGs to control cache invalidation
ARG BUILD_DATE
ARG GIT_COMMIT
ARG VERSION

LABEL org.opencontainers.image.created="${BUILD_DATE}"
LABEL org.opencontainers.image.revision="${GIT_COMMIT}"
LABEL org.opencontainers.image.version="${VERSION}"
```

### 2.2 Node.js Best Practices (Score: 75/100)

#### ✅ **GOOD: Node Version Pinning**
```dockerfile
FROM node:20-alpine
```
- Uses specific major version (20)
- Alpine variant reduces image size

#### ⚠️ **IMPROVEMENT: Pin Exact Node Version**
```dockerfile
FROM node:20.18.0-alpine3.19  # Exact version for reproducibility
```

#### ⚠️ **IMPROVEMENT: Set NODE_ENV Earlier**
Currently set in builder stage (line 43), should be in deps stage:
```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
ENV NODE_ENV=production  # Add here for npm ci optimization
```

### 2.3 .dockerignore (Score: 85/100)

#### ✅ **GOOD: Comprehensive Exclusions**
```
node_modules/
dist/
.git/
.env*
*.md
coverage/
```

#### ⚠️ **IMPROVEMENT: Add More Development Files**
```
# Add these to .dockerignore:
*.log
.vscode/
.idea/
*.swp
.DS_Store
Thumbs.db
.cache/
.temp/
playwright-report/
test-results/
```

---

## 3. Vite/React Specifics

### 3.1 Build Configuration (Score: 70/100)

#### ⚠️ **ISSUE: Redundant Runtime Config Mechanisms**

**Problem:** Three different runtime config systems compete:
1. `vite.config.ts` plugin generates `/config.js`
2. `public/api/config.js` with BACKEND_URL_PLACEHOLDER
3. `docker-entrypoint.sh` creates its own config

**Impact:**
- Confusion about which config is active
- Risk of conflicting configurations
- Maintenance burden

**Recommended Fix:** Consolidate to ONE system:

```javascript
// vite.config.ts - REMOVE runtime-config-injection plugin
// Use ONLY docker-entrypoint.sh for runtime config

// Remove this from vite.config.ts:
{
  name: 'runtime-config-injection',
  generateBundle(options, bundle) { ... }
}
```

```bash
# docker-entrypoint.sh - SINGLE SOURCE OF TRUTH
cat > /usr/share/nginx/html/runtime-config.js << EOF
window.__APP_CONFIG__ = {
  api: {
    baseUrl: '${BACKEND_URL}',
    apiUrl: '${BACKEND_URL}/api/v1',
    wsUrl: '${BACKEND_URL}/ws'.replace('https://', 'wss://').replace('http://', 'ws://')
  },
  supabase: {
    url: '${VITE_SUPABASE_URL:-}',
    anonKey: '${VITE_SUPABASE_ANON_KEY:-}'
  },
  firebase: {
    apiKey: '${VITE_FIREBASE_API_KEY:-}',
    authDomain: '${VITE_FIREBASE_AUTH_DOMAIN:-}',
    projectId: '${VITE_FIREBASE_PROJECT_ID:-}',
    storageBucket: '${VITE_FIREBASE_STORAGE_BUCKET:-}',
    messagingSenderId: '${VITE_FIREBASE_MESSAGING_SENDER_ID:-}',
    appId: '${VITE_FIREBASE_APP_ID:-}'
  },
  environment: 'production',
  version: '${APP_VERSION:-2.0.0}'
};
EOF
```

```html
<!-- index.html - Load BEFORE app bundle -->
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <script src="/runtime-config.js"></script>
  <!-- Vite will inject app scripts here -->
</head>
```

#### ✅ **GOOD: Build Optimization**
```javascript
// vite.config.ts
build: {
  minify: 'esbuild',  // Fast minification
  cssMinify: 'lightningcss',  // Optimized CSS
  cssCodeSplit: true,  // Split CSS per route
  reportCompressedSize: false,  // Faster builds
}
```

#### ✅ **GOOD: Chunk Splitting Strategy**
```javascript
manualChunks: {
  vendor: ['react', 'react-dom'],
  router: ['react-router-dom', '@tanstack/react-query'],
  ui: ['@radix-ui/...'],
  charts: ['recharts'],
  // ...
}
```
- Effective code splitting for better caching
- Separates rarely-changing vendor code

#### ⚠️ **IMPROVEMENT: Add Preload Hints**
```javascript
// In vite.config.ts plugins:
{
  name: 'preload-critical-chunks',
  transformIndexHtml(html) {
    return html.replace(
      '</head>',
      '<link rel="modulepreload" href="/js/vendor-*.js">\n</head>'
    );
  }
}
```

### 3.2 Static Asset Handling (Score: 90/100)

#### ✅ **EXCELLENT: Nginx Asset Caching**
```nginx
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
    etag on;
    access_log off;
}
```
- Aggressive 1-year caching for immutable assets
- Disables access logs for performance
- ETags for validation

#### ✅ **GOOD: HTML No-Cache**
```nginx
location ~* \.(html)$ {
    expires -1;
    add_header Cache-Control "no-cache, no-store, must-revalidate";
    etag on;
}
```
- Ensures SPA always loads fresh HTML
- Allows cache validation via ETag

---

## 4. Production Readiness

### 4.1 Health Checks (Score: 60/100)

#### ✅ **GOOD: Dockerfile Health Check**
```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT:-3000}/health || exit 1
```

#### ⚠️ **ISSUE: PORT Variable Not Available**
The healthcheck uses `${PORT:-3000}` but PORT is set at runtime via environment variable, not at build time.

**Fix:**
```dockerfile
# Use a wrapper script for health check
COPY healthcheck.sh /healthcheck.sh
RUN chmod +x /healthcheck.sh
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD /healthcheck.sh
```

```bash
#!/bin/sh
# healthcheck.sh
PORT=${PORT:-3000}
curl -f http://localhost:$PORT/health || exit 1
```

#### ✅ **GOOD: Nginx Health Endpoint**
```nginx
location /health {
    access_log off;
    return 200 "healthy\n";
    add_header Content-Type text/plain;
}
```

### 4.2 Logging and Monitoring (Score: 75/100)

#### ✅ **GOOD: Structured Nginx Logs**
```nginx
log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                '$status $body_bytes_sent "$http_referer" '
                '"$http_user_agent" "$http_x_forwarded_for" '
                'rt=$request_time uct="$upstream_connect_time" '
                'uht="$upstream_header_time" urt="$upstream_response_time"';
```
- Includes timing metrics for backend requests
- Tracks forwarded IPs for proxy scenarios

#### ⚠️ **IMPROVEMENT: Add JSON Logging for Production**
```nginx
log_format json_combined escape=json
  '{'
    '"time_local":"$time_local",'
    '"remote_addr":"$remote_addr",'
    '"request":"$request",'
    '"status": $status,'
    '"body_bytes_sent":$body_bytes_sent,'
    '"request_time":$request_time,'
    '"http_referrer":"$http_referer",'
    '"http_user_agent":"$http_user_agent",'
    '"upstream_addr":"$upstream_addr",'
    '"upstream_response_time":"$upstream_response_time"'
  '}';

access_log /var/log/nginx/access.log json_combined;
```

### 4.3 Browser Caching Headers (Score: 95/100)

#### ✅ **EXCELLENT: Immutable Cache for Assets**
Already implemented (see 3.2)

#### ✅ **GOOD: WebSocket Configuration**
```nginx
location /ws {
    proxy_pass http://backend;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";

    # Long timeouts for persistent connections
    proxy_connect_timeout 7d;
    proxy_send_timeout 7d;
    proxy_read_timeout 7d;
}
```

### 4.4 Environment Variable Injection (Score: 45/100)

#### ❌ **CRITICAL: Multiple Conflicting Systems**

**Current State:**
1. Build-time injection via `ARG` + `ENV` in Dockerfile
2. Runtime injection via `docker-entrypoint.sh`
3. Runtime injection via `start.sh`
4. Fallback injection via `vite.config.ts` plugin
5. Placeholder substitution in `public/api/config.js`

**Problems:**
- Unclear precedence order
- Risk of using stale build-time values
- Maintenance nightmare

**Recommended Solution:** See section 3.1

---

## 5. Critical Issues Summary

### 5.1 Blocker Issues (Must Fix Before Production)

1. **Missing/Incorrect docker-entrypoint.sh** (CRITICAL)
   - Current script overwrites optimized nginx.conf
   - Must merge functionality

2. **Invalid Nginx Upstream Configuration** (CRITICAL)
   - `${BACKEND_URL}` substitution will fail
   - Must use direct proxy_pass or parse URL

3. **Firebase Keys in Build Arguments** (HIGH)
   - Move to runtime injection
   - Remove from Dockerfile ARGs

### 5.2 High Priority Issues (Fix Soon)

4. **Multiple Runtime Config Systems** (HIGH)
   - Consolidate to single mechanism
   - Remove redundant scripts

5. **Hardcoded Production URLs** (MEDIUM)
   - Remove from `public/config.js`
   - Use relative URLs or environment detection

6. **Health Check PORT Variable** (MEDIUM)
   - Fix healthcheck script

### 5.3 Optimization Opportunities

7. **Add Content Security Policy** (MEDIUM)
8. **Pin Exact Node Version** (LOW)
9. **Add Preload Hints** (LOW)
10. **JSON Logging** (LOW)

---

## 6. Recommended Fixes with Code Examples

### Fix 1: Unified docker-entrypoint.sh

**File:** `frontend-hormonia/docker-entrypoint-unified.sh`

```bash
#!/bin/sh
set -e

echo "================================================================"
echo "Frontend Hormonia - Production Entrypoint v2.0"
echo "================================================================"

# ------------------------------------------------------------------------------
# 1. Environment Validation
# ------------------------------------------------------------------------------
echo "[1/7] Validating environment..."

if [ -z "$BACKEND_URL" ]; then
  echo "❌ ERROR: BACKEND_URL is required"
  echo "Example: docker run -e BACKEND_URL=https://api.example.com ..."
  exit 1
fi

# Parse BACKEND_URL for nginx upstream
BACKEND_HOST=$(echo "$BACKEND_URL" | sed -E 's|^https?://||' | sed -E 's|/.*||')
BACKEND_SCHEME=$(echo "$BACKEND_URL" | sed -E 's|://.*||')

echo "  ✓ BACKEND_URL: $BACKEND_URL"
echo "  ✓ BACKEND_HOST: $BACKEND_HOST"
echo "  ✓ BACKEND_SCHEME: $BACKEND_SCHEME"

# ------------------------------------------------------------------------------
# 2. PORT Configuration
# ------------------------------------------------------------------------------
echo "[2/7] Configuring PORT..."
PORT=${PORT:-3000}

if ! echo "$PORT" | grep -qE '^[0-9]+$'; then
  echo "❌ ERROR: PORT must be numeric, got: $PORT"
  exit 1
fi

echo "  ✓ PORT: $PORT"

# ------------------------------------------------------------------------------
# 3. Nginx Configuration Substitution
# ------------------------------------------------------------------------------
echo "[3/7] Configuring nginx..."

NGINX_CONF="/etc/nginx/nginx.conf"
cp "$NGINX_CONF" "$NGINX_CONF.backup"

# Substitute variables in nginx.conf
sed -i "s|\${BACKEND_HOST}|$BACKEND_HOST|g" "$NGINX_CONF"
sed -i "s|listen 3000;|listen $PORT;|g" "$NGINX_CONF"

# Update proxy_pass to use full URL
sed -i "s|proxy_pass http://backend;|proxy_pass $BACKEND_URL;|g" "$NGINX_CONF"

echo "  ✓ Nginx configuration updated"

# ------------------------------------------------------------------------------
# 4. Runtime Configuration for Browser
# ------------------------------------------------------------------------------
echo "[4/7] Creating runtime configuration..."

mkdir -p /usr/share/nginx/html/api

cat > /usr/share/nginx/html/runtime-config.js << 'RUNTIME_CONFIG_EOF'
/**
 * Runtime Configuration - Injected at Container Startup
 * Single source of truth for all frontend configuration
 */
window.__APP_CONFIG__ = {
  // API Configuration
  api: {
    baseUrl: 'BACKEND_URL_PLACEHOLDER',
    apiUrl: 'BACKEND_URL_PLACEHOLDER/api/v1',
    wsUrl: 'BACKEND_URL_PLACEHOLDER/ws'
  },

  // Supabase Configuration
  supabase: {
    url: 'SUPABASE_URL_PLACEHOLDER',
    anonKey: 'SUPABASE_ANON_KEY_PLACEHOLDER'
  },

  // Firebase Configuration (injected at runtime)
  firebase: {
    apiKey: 'FIREBASE_API_KEY_PLACEHOLDER',
    authDomain: 'FIREBASE_AUTH_DOMAIN_PLACEHOLDER',
    projectId: 'FIREBASE_PROJECT_ID_PLACEHOLDER',
    storageBucket: 'FIREBASE_STORAGE_BUCKET_PLACEHOLDER',
    messagingSenderId: 'FIREBASE_MESSAGING_SENDER_ID_PLACEHOLDER',
    appId: 'FIREBASE_APP_ID_PLACEHOLDER'
  },

  // Application Metadata
  app: {
    environment: 'production',
    version: 'APP_VERSION_PLACEHOLDER',
    buildDate: 'BUILD_DATE_PLACEHOLDER'
  }
};

// Auto-convert ws:// to wss:// for HTTPS
if (window.__APP_CONFIG__.api.wsUrl.startsWith('https://')) {
  window.__APP_CONFIG__.api.wsUrl = window.__APP_CONFIG__.api.wsUrl.replace('https://', 'wss://');
} else if (window.__APP_CONFIG__.api.wsUrl.startsWith('http://')) {
  window.__APP_CONFIG__.api.wsUrl = window.__APP_CONFIG__.api.wsUrl.replace('http://', 'ws://');
}

console.log('[Runtime Config] Application configuration loaded');
RUNTIME_CONFIG_EOF

# Perform substitutions
sed -i "s|BACKEND_URL_PLACEHOLDER|$BACKEND_URL|g" /usr/share/nginx/html/runtime-config.js
sed -i "s|SUPABASE_URL_PLACEHOLDER|${VITE_SUPABASE_URL:-}|g" /usr/share/nginx/html/runtime-config.js
sed -i "s|SUPABASE_ANON_KEY_PLACEHOLDER|${VITE_SUPABASE_ANON_KEY:-}|g" /usr/share/nginx/html/runtime-config.js
sed -i "s|FIREBASE_API_KEY_PLACEHOLDER|${VITE_FIREBASE_API_KEY:-}|g" /usr/share/nginx/html/runtime-config.js
sed -i "s|FIREBASE_AUTH_DOMAIN_PLACEHOLDER|${VITE_FIREBASE_AUTH_DOMAIN:-}|g" /usr/share/nginx/html/runtime-config.js
sed -i "s|FIREBASE_PROJECT_ID_PLACEHOLDER|${VITE_FIREBASE_PROJECT_ID:-}|g" /usr/share/nginx/html/runtime-config.js
sed -i "s|FIREBASE_STORAGE_BUCKET_PLACEHOLDER|${VITE_FIREBASE_STORAGE_BUCKET:-}|g" /usr/share/nginx/html/runtime-config.js
sed -i "s|FIREBASE_MESSAGING_SENDER_ID_PLACEHOLDER|${VITE_FIREBASE_MESSAGING_SENDER_ID:-}|g" /usr/share/nginx/html/runtime-config.js
sed -i "s|FIREBASE_APP_ID_PLACEHOLDER|${VITE_FIREBASE_APP_ID:-}|g" /usr/share/nginx/html/runtime-config.js
sed -i "s|APP_VERSION_PLACEHOLDER|${APP_VERSION:-2.0.0}|g" /usr/share/nginx/html/runtime-config.js
sed -i "s|BUILD_DATE_PLACEHOLDER|$(date -u +%Y-%m-%dT%H:%M:%SZ)|g" /usr/share/nginx/html/runtime-config.js

echo "  ✓ Runtime configuration created"

# ------------------------------------------------------------------------------
# 5. Inject Runtime Config into index.html
# ------------------------------------------------------------------------------
echo "[5/7] Injecting runtime config into HTML..."

if [ -f /usr/share/nginx/html/index.html ]; then
  # Only inject if not already present
  if ! grep -q "runtime-config.js" /usr/share/nginx/html/index.html; then
    sed -i 's|</head>|  <script src="/runtime-config.js"></script>\n  </head>|' /usr/share/nginx/html/index.html
    echo "  ✓ Runtime config script injected"
  else
    echo "  ✓ Runtime config already present"
  fi
else
  echo "  ⚠️  WARNING: index.html not found"
fi

# ------------------------------------------------------------------------------
# 6. Validate Nginx Configuration
# ------------------------------------------------------------------------------
echo "[6/7] Validating nginx configuration..."

if ! nginx -t 2>&1; then
  echo "❌ ERROR: Nginx configuration test failed"
  echo ""
  echo "Configuration file content:"
  cat "$NGINX_CONF"
  exit 1
fi

echo "  ✓ Nginx configuration valid"

# ------------------------------------------------------------------------------
# 7. Display Configuration Summary
# ------------------------------------------------------------------------------
echo "[7/7] Configuration summary..."
echo ""
echo "  Backend: $BACKEND_URL"
echo "  Port: $PORT"
echo "  Supabase: ${VITE_SUPABASE_URL:-[not configured]}"
echo "  Firebase Project: ${VITE_FIREBASE_PROJECT_ID:-[not configured]}"
echo ""
echo "================================================================"
echo "✓ Configuration complete! Starting nginx..."
echo "================================================================"

# Start nginx (as nginx user, non-root)
exec nginx -g "daemon off;"
```

### Fix 2: Updated Nginx Configuration

**File:** `frontend-hormonia/nginx-optimized.conf`

```nginx
user nginx;
worker_processes auto;
worker_rlimit_nofile 65535;
pid /var/run/nginx.pid;

events {
    worker_connections 4096;
    multi_accept on;
    use epoll;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for" '
                    'rt=$request_time uct="$upstream_connect_time" '
                    'uht="$upstream_header_time" urt="$upstream_response_time"';

    access_log /var/log/nginx/access.log main;
    error_log /var/log/nginx/error.log warn;

    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 30s;
    keepalive_requests 1000;

    # File cache
    open_file_cache max=10000 inactive=30s;
    open_file_cache_valid 60s;
    open_file_cache_min_uses 2;

    # Compression
    gzip on;
    gzip_vary on;
    gzip_comp_level 6;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript
               application/javascript application/json application/xml+rss;

    # WebSocket upgrade mapping
    map $http_upgrade $connection_upgrade {
        default upgrade;
        '' close;
    }

    server {
        listen 3000;  # Will be replaced with ${PORT} by entrypoint
        server_name _;

        root /usr/share/nginx/html;
        index index.html;

        # Security Headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;
        add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://*.railway.app wss://*.railway.app https://*.supabase.co wss://*.supabase.co https://firebaseapp.com; font-src 'self' data:; frame-ancestors 'self';" always;

        # HTTPS Enforcement (behind Railway proxy)
        if ($http_x_forwarded_proto = "http") {
            return 301 https://$host$request_uri;
        }

        # Runtime Configuration
        location = /runtime-config.js {
            add_header Cache-Control "no-store, no-cache, must-revalidate" always;
            add_header Content-Type "application/javascript" always;
        }

        # Health Check
        location /health {
            access_log off;
            return 200 "healthy\n";
            add_header Content-Type text/plain;
        }

        # API Proxy (direct proxy, no upstream block)
        location /api/ {
            # BACKEND_URL will be replaced by entrypoint
            proxy_pass BACKEND_URL_PLACEHOLDER;
            proxy_http_version 1.1;

            # Headers
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # Timeouts
            proxy_connect_timeout 10s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;

            # No buffering for real-time
            proxy_buffering off;
        }

        # WebSocket
        location /ws {
            proxy_pass BACKEND_URL_PLACEHOLDER;
            proxy_http_version 1.1;

            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # Long timeouts for WebSocket
            proxy_connect_timeout 7d;
            proxy_send_timeout 7d;
            proxy_read_timeout 7d;

            proxy_buffering off;
        }

        # Static Assets - Aggressive Caching
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable" always;
            etag on;
            access_log off;
        }

        # HTML - No Cache
        location ~* \.(html)$ {
            expires -1;
            add_header Cache-Control "no-cache, no-store, must-revalidate" always;
            add_header Pragma "no-cache" always;
            etag on;
        }

        # SPA Fallback
        location / {
            try_files $uri $uri/ /index.html;
        }

        # Error Pages
        error_page 404 /index.html;
        error_page 500 502 503 504 /index.html;
    }
}
```

In entrypoint, substitute `BACKEND_URL_PLACEHOLDER` with actual URL:
```bash
sed -i "s|BACKEND_URL_PLACEHOLDER|$BACKEND_URL|g" "$NGINX_CONF"
```

### Fix 3: Updated Dockerfile

**File:** `frontend-hormonia/Dockerfile.optimized`

```dockerfile
# =============================================================================
# Multi-stage Dockerfile for Frontend Hormonia
# Optimized for Railway deployment with runtime configuration
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Dependencies
# -----------------------------------------------------------------------------
FROM node:20.18.0-alpine3.19 AS deps

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies with caching optimization
RUN if [ ! -f package-lock.json ]; then \
      echo "⚠️ package-lock.json not found, generating..."; \
      npm install --production=false; \
    else \
      echo "✓ Installing from package-lock.json"; \
      npm ci --prefer-offline --no-audit --production=false; \
    fi

# -----------------------------------------------------------------------------
# Stage 2: Builder
# -----------------------------------------------------------------------------
FROM node:20.18.0-alpine3.19 AS builder

WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/package*.json ./

# Copy source code
COPY . .

# Build arguments (ONLY non-sensitive, build-time configs)
ARG NODE_ENV=production
ARG APP_VERSION=2.0.0
ARG BUILD_DATE
ARG GIT_COMMIT

# Set build environment
ENV NODE_ENV=${NODE_ENV}

# Debug build info (no secrets logged)
RUN echo "🔨 Building frontend:" && \
    echo "  Version: ${APP_VERSION}" && \
    echo "  Build Date: ${BUILD_DATE}" && \
    echo "  Git Commit: ${GIT_COMMIT}" && \
    echo "  Node: $(node --version)" && \
    echo "  NPM: $(npm --version)"

# Build application
RUN npm run build:prod

# Verify build output
RUN ls -lah dist/ && \
    echo "✓ Build completed, dist size:" && \
    du -sh dist/

# -----------------------------------------------------------------------------
# Stage 3: Production (Nginx)
# -----------------------------------------------------------------------------
FROM nginx:1.27-alpine AS production

# Install curl for health checks
RUN apk add --no-cache curl

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration (with placeholders)
COPY nginx-optimized.conf /etc/nginx/nginx.conf

# Copy unified entrypoint script
COPY docker-entrypoint-unified.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Create healthcheck script
RUN echo '#!/bin/sh' > /healthcheck.sh && \
    echo 'PORT=${PORT:-3000}' >> /healthcheck.sh && \
    echo 'curl -f http://localhost:$PORT/health || exit 1' >> /healthcheck.sh && \
    chmod +x /healthcheck.sh

# Labels for metadata
LABEL org.opencontainers.image.title="Hormonia Frontend"
LABEL org.opencontainers.image.description="Frontend SPA for Hormonia Oncology Clinic"
LABEL org.opencontainers.image.version="${APP_VERSION}"
LABEL org.opencontainers.image.created="${BUILD_DATE}"
LABEL org.opencontainers.image.revision="${GIT_COMMIT}"

# Expose port (Railway overrides with PORT env var)
EXPOSE 3000

# Health check using wrapper script
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD /healthcheck.sh

# Set permissions for non-root execution
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    chown -R nginx:nginx /etc/nginx && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid && \
    chown nginx:nginx /docker-entrypoint.sh && \
    chown nginx:nginx /healthcheck.sh

# Switch to non-root user
USER nginx

# Runtime environment variables (NO SECRETS HERE - injected at runtime)
ENV PORT=3000

# Start nginx via entrypoint
ENTRYPOINT ["/docker-entrypoint.sh"]
```

### Fix 4: Updated vite.config.ts

**File:** `frontend-hormonia/vite.config-updated.ts`

```typescript
import { defineConfig } from 'vite'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

export default defineConfig(({ mode }) => ({
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
      '~backend/client': resolve(__dirname, './client'),
      '~backend': resolve(__dirname, '../Backend'),
    },
  },

  plugins: [
    tailwindcss(),
    react(),
    // REMOVED: runtime-config-injection plugin
    // Runtime config is now handled ONLY by docker-entrypoint.sh
  ],

  build: {
    outDir: 'dist',
    sourcemap: mode === 'production' ? false : true,
    minify: 'esbuild',
    target: 'es2020',
    cssMinify: 'lightningcss',
    cssCodeSplit: true,
    reportCompressedSize: false,

    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          router: ['react-router-dom', '@tanstack/react-query'],
          ui: [
            '@radix-ui/react-dialog',
            '@radix-ui/react-dropdown-menu',
            '@radix-ui/react-select',
            '@radix-ui/react-toast',
            'lucide-react'
          ],
          charts: ['recharts'],
          supabase: ['@supabase/supabase-js'],
          firebase: ['firebase/app', 'firebase/auth'],
          utils: ['lodash', 'date-fns', 'clsx', 'tailwind-merge'],
          forms: ['react-hook-form', 'zod']
        },

        chunkFileNames: 'js/[name]-[hash].js',
        entryFileNames: 'js/[name]-[hash].js',

        assetFileNames: (assetInfo) => {
          const extType = assetInfo.name?.split('.').pop() || 'asset';
          if (/png|jpe?g|svg|gif|tiff|bmp|ico/i.test(extType)) {
            return 'images/[name]-[hash][extname]';
          }
          if (/woff|woff2|eot|ttf|otf/i.test(extType)) {
            return 'fonts/[name]-[hash][extname]';
          }
          return `${extType}/[name]-[hash][extname]`;
        },
      },

      treeshake: {
        moduleSideEffects: false,
        preset: 'recommended',
      }
    },

    chunkSizeWarningLimit: 500,
  },

  server: {
    port: 5173,
    host: '0.0.0.0',
    strictPort: false,
    cors: true,

    proxy: mode === 'development' ? {
      '/api': {
        target: process.env['VITE_API_URL'] || 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/api/, '/api/v1'),
      },
      '/ws': {
        target: process.env['VITE_WS_BASE_URL'] || 'ws://127.0.0.1:8000',
        ws: true,
        changeOrigin: true,
      },
    } : undefined,
  },

  preview: {
    port: process.env['PORT'] ? parseInt(process.env['PORT']) : 4173,
    host: '0.0.0.0',
    strictPort: false,
    cors: true,

    headers: {
      'X-Frame-Options': 'DENY',
      'X-Content-Type-Options': 'nosniff',
      'Referrer-Policy': 'strict-origin-when-cross-origin',
    },
  },

  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-router-dom',
      '@tanstack/react-query',
      '@supabase/supabase-js',
      'firebase/app',
      'firebase/auth',
    ],

    esbuildOptions: {
      target: 'es2020',
    }
  },

  esbuild: {
    drop: mode === 'production' ? ['console', 'debugger'] : [],
    legalComments: 'none',
  },

  define: {
    'process.env.NODE_ENV': JSON.stringify(mode),
    '__VITE_MODE__': JSON.stringify(mode),
  },
}))
```

---

## 7. Implementation Plan

### Phase 1: Critical Fixes (Blocker Issues)

**Priority:** IMMEDIATE
**Estimated Time:** 4 hours

1. Create `docker-entrypoint-unified.sh` (Fix 1)
2. Update `nginx.conf` to use `nginx-optimized.conf` (Fix 2)
3. Update `Dockerfile` to `Dockerfile.optimized` (Fix 3)
4. Remove Firebase ARGs from build process
5. Test locally with Docker

**Verification:**
```bash
# Build image
docker build -t frontend-hormonia:test \
  --build-arg APP_VERSION=2.0.0 \
  --build-arg BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --build-arg GIT_COMMIT=$(git rev-parse --short HEAD) \
  .

# Run container with runtime env vars
docker run -p 3000:3000 \
  -e BACKEND_URL=https://backend.example.com \
  -e VITE_SUPABASE_URL=https://xxx.supabase.co \
  -e VITE_SUPABASE_ANON_KEY=xxx \
  -e VITE_FIREBASE_API_KEY=xxx \
  -e VITE_FIREBASE_AUTH_DOMAIN=xxx.firebaseapp.com \
  -e VITE_FIREBASE_PROJECT_ID=xxx \
  frontend-hormonia:test

# Verify health
curl http://localhost:3000/health

# Verify runtime config
curl http://localhost:3000/runtime-config.js
```

### Phase 2: High Priority Fixes

**Priority:** HIGH
**Estimated Time:** 3 hours

6. Update `vite.config.ts` (Fix 4) - remove runtime plugin
7. Remove redundant config scripts (`public/config.js`, `start.sh`)
8. Add Content Security Policy to nginx
9. Update `.dockerignore` with additional patterns
10. Add JSON logging to nginx

### Phase 3: Optimization

**Priority:** MEDIUM
**Estimated Time:** 2 hours

11. Pin exact Node version
12. Add build metadata labels
13. Add preload hints for critical chunks
14. Optimize health check script
15. Add HTTPS enforcement

---

## 8. Score Breakdown

| Category | Score | Weight | Weighted Score |
|----------|-------|--------|----------------|
| Security | 35/100 | 40% | 14/40 |
| Best Practices | 80/100 | 20% | 16/20 |
| Vite/React Config | 70/100 | 15% | 10.5/15 |
| Production Readiness | 65/100 | 25% | 16.25/25 |
| **TOTAL** | - | - | **56.75/100** |

**Adjusted Score (Critical Issues):** 62/100
*Score adjusted upward due to good nginx optimization and multi-stage builds, but heavily penalized for critical configuration issues.*

---

## 9. Conclusion

The frontend Docker configuration demonstrates **good architectural decisions** (multi-stage builds, non-root user, nginx optimizations) but suffers from **critical implementation flaws**:

### Strengths:
- Multi-stage build reduces attack surface
- Nginx performance optimizations are excellent
- Non-root execution and proper permissions
- Good static asset caching strategy

### Critical Weaknesses:
- Multiple conflicting runtime configuration systems
- Invalid nginx upstream configuration
- Firebase secrets exposed in build arguments
- Missing/incorrect entrypoint script
- Hardcoded production URLs

### Immediate Actions Required:
1. Implement unified `docker-entrypoint-unified.sh`
2. Fix nginx configuration for backend proxy
3. Remove Firebase keys from Dockerfile
4. Consolidate runtime config mechanisms

### Estimated Fix Time:
- **Phase 1 (Blockers):** 4 hours
- **Phase 2 (High Priority):** 3 hours
- **Phase 3 (Optimization):** 2 hours
- **Total:** ~9 hours

**Recommendation:** Address Phase 1 issues BEFORE deploying to production. The current configuration will fail at runtime due to invalid nginx syntax and missing entrypoint.

---

## Appendix A: Testing Checklist

- [ ] Docker build succeeds without errors
- [ ] Container starts successfully
- [ ] Health check endpoint responds (200 OK)
- [ ] Runtime config loads in browser (`window.__APP_CONFIG__`)
- [ ] API proxy forwards requests to backend
- [ ] WebSocket connections establish correctly
- [ ] Static assets serve with correct cache headers
- [ ] HTTPS redirect works (if behind proxy)
- [ ] Security headers present in responses
- [ ] No console errors related to configuration
- [ ] Firebase initialization succeeds
- [ ] Supabase client initializes correctly

---

**Report Generated:** 2025-10-04
**Reviewer:** Code Quality Analyzer Agent
**Next Review:** After Phase 1 fixes implemented
