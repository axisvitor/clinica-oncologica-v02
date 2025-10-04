#!/bin/sh
set -e

# Debug: Show current user and permissions
echo "🔍 Debug info:"
echo "   Current user: $(whoami)"
echo "   User ID: $(id -u)"
id
ls -la /etc/nginx/nginx.conf.template || echo "❌ Template not found"
ls -la /etc/nginx/nginx.conf 2>/dev/null || echo "⚠️ nginx.conf doesn't exist yet (expected)"

# CRITICAL FIX: Expand variables with defaults BEFORE envsubst
# This allows nginx.conf.template to use simple ${VAR} syntax
# while still providing default values when Railway env vars are missing
# Railway Internal Network: use .railway.internal domain (no port needed)
export BACKEND_HOST="${BACKEND_HOST:-clinica-oncologica-v02.railway.internal}"
export BACKEND_PORT="${BACKEND_PORT:-80}"
export PORT="${PORT:-3000}"

# Debug: show backend configuration BEFORE substitution
echo "🔗 Backend configuration (with defaults applied):"
echo "   BACKEND_HOST=${BACKEND_HOST}"
echo "   BACKEND_PORT=${BACKEND_PORT}"
echo "   PORT=${PORT}"

# ============================================
# RUNTIME CONFIGURATION GENERATION
# ============================================
echo "🔧 Generating runtime configuration from Railway environment variables..."

# Path to the config files
CONFIG_FILE="/usr/share/nginx/html/api/config"
CONFIG_JS_FILE="/usr/share/nginx/html/api/config.js"

# Ensure api directory exists
mkdir -p /usr/share/nginx/html/api

# Generate JSON configuration from Railway environment variables
cat > "$CONFIG_FILE" << EOF
{
  "VITE_SUPABASE_URL": "${VITE_SUPABASE_URL:-}",
  "VITE_SUPABASE_ANON_KEY": "${VITE_SUPABASE_ANON_KEY:-}",
  "VITE_API_URL": "${VITE_API_URL:-http://localhost:8000/api/v1}",
  "VITE_API_BASE_URL": "${VITE_API_BASE_URL:-http://localhost:8000}",
  "VITE_WS_BASE_URL": "${VITE_WS_BASE_URL:-ws://localhost:8000/ws}",
  "VITE_WHATSAPP_INSTANCE_NAME": "${VITE_WHATSAPP_INSTANCE_NAME:-hormonia-instance}",
  "VITE_ENVIRONMENT": "${VITE_ENVIRONMENT:-production}",
  "VITE_DEBUG_MODE": "${VITE_DEBUG_MODE:-false}",
  "VITE_SESSION_TIMEOUT": "${VITE_SESSION_TIMEOUT:-3600000}",
  "VITE_TOKEN_REFRESH_THRESHOLD": "${VITE_TOKEN_REFRESH_THRESHOLD:-300000}",
  "VITE_MAX_FILE_SIZE": "${VITE_MAX_FILE_SIZE:-10485760}",
  "VITE_SUPPORTED_FILE_TYPES": "${VITE_SUPPORTED_FILE_TYPES:-image/jpeg,image/png,image/gif,application/pdf}"
}
EOF

# Generate JavaScript version
cat > "$CONFIG_JS_FILE" << EOF
window.__ENV_CONFIG__ = {
  "VITE_SUPABASE_URL": "${VITE_SUPABASE_URL:-}",
  "VITE_SUPABASE_ANON_KEY": "${VITE_SUPABASE_ANON_KEY:-}",
  "VITE_API_URL": "${VITE_API_URL:-http://localhost:8000/api/v1}",
  "VITE_API_BASE_URL": "${VITE_API_BASE_URL:-http://localhost:8000}",
  "VITE_WS_BASE_URL": "${VITE_WS_BASE_URL:-ws://localhost:8000/ws}",
  "VITE_WHATSAPP_INSTANCE_NAME": "${VITE_WHATSAPP_INSTANCE_NAME:-hormonia-instance}",
  "VITE_ENVIRONMENT": "${VITE_ENVIRONMENT:-production}",
  "VITE_DEBUG_MODE": "${VITE_DEBUG_MODE:-false}",
  "VITE_SESSION_TIMEOUT": "${VITE_SESSION_TIMEOUT:-3600000}",
  "VITE_TOKEN_REFRESH_THRESHOLD": "${VITE_TOKEN_REFRESH_THRESHOLD:-300000}",
  "VITE_MAX_FILE_SIZE": "${VITE_MAX_FILE_SIZE:-10485760}",
  "VITE_SUPPORTED_FILE_TYPES": "${VITE_SUPPORTED_FILE_TYPES:-image/jpeg,image/png,image/gif,application/pdf}"
};
console.log('[Runtime Config] Configuration loaded from Railway environment');
EOF

# Display loaded configuration (without sensitive keys)
echo "✅ Runtime configuration generated successfully!"
echo "   - API URL: ${VITE_API_URL:-http://localhost:8000/api/v1}"
echo "   - API Base: ${VITE_API_BASE_URL:-http://localhost:8000}"
echo "   - WS URL: ${VITE_WS_BASE_URL:-ws://localhost:8000/ws}"
echo "   - Environment: ${VITE_ENVIRONMENT:-production}"
echo "   - Supabase URL: ${VITE_SUPABASE_URL:+[SET]}"

# Verify config files were created
if [ ! -f "$CONFIG_FILE" ] || [ ! -f "$CONFIG_JS_FILE" ]; then
    echo "⚠️ WARNING: Runtime config files may not have been created properly"
fi

# ============================================
# NGINX CONFIGURATION
# ============================================

# Process nginx.conf template with environment variables
# Write directly to /etc/nginx/nginx.conf (nginx user has write permission)
envsubst '${BACKEND_HOST} ${BACKEND_PORT} ${PORT}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

# Verify nginx config was created successfully
if [ ! -f /etc/nginx/nginx.conf ]; then
    echo "❌ ERROR: Failed to create nginx.conf"
    exit 1
fi

echo "✅ nginx.conf created successfully"

# Start nginx
exec nginx -g 'daemon off;'
