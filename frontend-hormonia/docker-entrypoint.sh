#!/bin/sh
set -e

# ==============================================================================
# Docker Entrypoint Script - Frontend Hormonia
# ==============================================================================
# Purpose: Runtime configuration substitution for Docker containers
# Features:
# - Validates required environment variables
# - Substitutes BACKEND_URL in nginx.conf and /api/config.js
# - Configures dynamic PORT (Railway/Cloud Run compatible)
# - Robust error handling and validation
# - Comprehensive logging for debugging
# ==============================================================================

echo "================================================================"
echo "Frontend Hormonia - Docker Entrypoint"
echo "================================================================"

# ------------------------------------------------------------------------------
# 1. Environment Variable Validation
# ------------------------------------------------------------------------------

echo "[Entrypoint] Step 1: Validating environment variables..."

if [ -z "$BACKEND_URL" ]; then
  echo "❌ ERROR: BACKEND_URL environment variable is required"
  echo ""
  echo "Usage:"
  echo "  docker run -e BACKEND_URL=https://backend-production-xxx.up.railway.app ..."
  echo ""
  echo "Example values:"
  echo "  - Production: https://backend-production-abc123.up.railway.app"
  echo "  - Staging: https://backend-staging-xyz789.up.railway.app"
  echo "  - Development: http://localhost:8000"
  echo ""
  exit 1
fi

# Validate BACKEND_URL format (basic URL validation)
if ! echo "$BACKEND_URL" | grep -qE '^https?://[a-zA-Z0-9.-]+(:[0-9]+)?$'; then
  echo "⚠️  WARNING: BACKEND_URL format may be invalid: $BACKEND_URL"
  echo "Expected format: http(s)://domain.com or http(s)://domain.com:port"
  echo "Proceeding anyway..."
fi

echo "✓ BACKEND_URL: $BACKEND_URL"

# ------------------------------------------------------------------------------
# 2. PORT Configuration (Railway/Cloud Run Dynamic Ports)
# ------------------------------------------------------------------------------

echo "[Entrypoint] Step 2: Configuring PORT..."

PORT=${PORT:-3000}

# Validate PORT is a number
if ! echo "$PORT" | grep -qE '^[0-9]+$'; then
  echo "❌ ERROR: PORT must be a numeric value, got: $PORT"
  exit 1
fi

# Validate PORT range (1024-65535)
if [ "$PORT" -lt 1024 ] || [ "$PORT" -gt 65535 ]; then
  echo "⚠️  WARNING: PORT $PORT is outside recommended range (1024-65535)"
fi

echo "✓ PORT: $PORT"

# ------------------------------------------------------------------------------
# 3. Nginx Configuration Substitution
# ------------------------------------------------------------------------------

echo "[Entrypoint] Step 3: Configuring Nginx proxy..."

NGINX_CONF="/etc/nginx/conf.d/default.conf"

# Check if nginx.conf exists
if [ ! -f "$NGINX_CONF" ]; then
  echo "❌ ERROR: Nginx configuration file not found: $NGINX_CONF"
  exit 1
fi

# Backup original nginx.conf for debugging
cp "$NGINX_CONF" "$NGINX_CONF.backup"
echo "✓ Backed up nginx.conf to $NGINX_CONF.backup"

# Substitute BACKEND_URL placeholder
echo "  Substituting \${BACKEND_URL} with $BACKEND_URL..."
sed -i "s|\${BACKEND_URL}|$BACKEND_URL|g" "$NGINX_CONF"

# Substitute PORT placeholder
echo "  Substituting PORT placeholder with $PORT..."
sed -i "s|listen 3000;|listen $PORT;|g" "$NGINX_CONF"
sed -i "s|listen \${PORT};|listen $PORT;|g" "$NGINX_CONF"

# ------------------------------------------------------------------------------
# 4. Validate Nginx Configuration Substitutions
# ------------------------------------------------------------------------------

echo "[Entrypoint] Step 4: Validating Nginx configuration..."

# Check if BACKEND_URL substitution was successful
if grep -q "\${BACKEND_URL}" "$NGINX_CONF"; then
  echo "❌ ERROR: Failed to substitute \${BACKEND_URL} in nginx.conf"
  echo ""
  echo "Showing lines with unsubstituted placeholders:"
  grep -n "\${BACKEND_URL}" "$NGINX_CONF" || true
  echo ""
  exit 1
fi

# Check if PORT substitution was successful
if grep -q "listen 3000;" "$NGINX_CONF" && [ "$PORT" != "3000" ]; then
  echo "⚠️  WARNING: PORT substitution may have failed (still showing 3000)"
fi

echo "✓ Nginx configuration validated successfully"

# ------------------------------------------------------------------------------
# 5. Runtime Config Substitution (/api/config.js)
# ------------------------------------------------------------------------------

echo "[Entrypoint] Step 5: Configuring runtime config..."

RUNTIME_CONFIG="/usr/share/nginx/html/api/config.js"

if [ -f "$RUNTIME_CONFIG" ]; then
  echo "  Found runtime config: $RUNTIME_CONFIG"

  # Backup original config
  cp "$RUNTIME_CONFIG" "$RUNTIME_CONFIG.backup"

  # Substitute BACKEND_URL placeholder
  echo "  Substituting BACKEND_URL_PLACEHOLDER with $BACKEND_URL..."
  sed -i "s|BACKEND_URL_PLACEHOLDER|$BACKEND_URL|g" "$RUNTIME_CONFIG"
  sed -i "s|\${BACKEND_URL}|$BACKEND_URL|g" "$RUNTIME_CONFIG"

  # Validate substitution
  if grep -q "BACKEND_URL_PLACEHOLDER" "$RUNTIME_CONFIG"; then
    echo "❌ ERROR: Failed to substitute BACKEND_URL_PLACEHOLDER in config.js"
    echo ""
    echo "Showing config.js content:"
    cat "$RUNTIME_CONFIG"
    echo ""
    exit 1
  fi

  echo "✓ Runtime config updated successfully"
else
  echo "⚠️  WARNING: Runtime config not found at $RUNTIME_CONFIG"
  echo "  This may be expected if not using /api/config.js pattern"
fi

# ------------------------------------------------------------------------------
# 6. Display Final Configuration (for debugging)
# ------------------------------------------------------------------------------

echo "[Entrypoint] Step 6: Final configuration summary..."
echo ""
echo "Configuration Summary:"
echo "  BACKEND_URL: $BACKEND_URL"
echo "  PORT: $PORT"
echo "  Nginx Config: $NGINX_CONF"
echo "  Runtime Config: $RUNTIME_CONFIG"
echo ""

# Show relevant nginx config lines for debugging
echo "Nginx Proxy Configuration:"
echo "---"
grep -A 5 "location /api" "$NGINX_CONF" || echo "  No /api location block found"
echo "---"
echo ""

# Show runtime config for debugging
if [ -f "$RUNTIME_CONFIG" ]; then
  echo "Runtime Config Content:"
  echo "---"
  cat "$RUNTIME_CONFIG"
  echo "---"
  echo ""
fi

# ------------------------------------------------------------------------------
# 7. Validate Nginx Configuration Syntax
# ------------------------------------------------------------------------------

echo "[Entrypoint] Step 7: Testing Nginx configuration syntax..."

if ! nginx -t; then
  echo "❌ ERROR: Nginx configuration syntax test failed"
  echo ""
  echo "Showing nginx.conf for debugging:"
  cat "$NGINX_CONF"
  echo ""
  exit 1
fi

echo "✓ Nginx configuration syntax valid"

# ------------------------------------------------------------------------------
# 8. Start Nginx
# ------------------------------------------------------------------------------

echo "================================================================"
echo "✓ Configuration complete! Starting Nginx..."
echo "================================================================"
echo ""
echo "Container is ready to accept connections on port $PORT"
echo "API requests will be proxied to: $BACKEND_URL"
echo ""

# Start nginx in foreground (required for Docker)
# Run as nginx user (not root) for security
exec nginx -g "daemon off;"
