#!/bin/sh
# Railway Runtime Configuration Generator
# This script runs in the Railway container at startup to inject environment variables

set -e

echo "[Runtime Config] Generating runtime configuration from environment variables..."

# Path to the config file
CONFIG_FILE="/usr/share/nginx/html/api/config"
CONFIG_JS_FILE="/usr/share/nginx/html/api/config.js"

# Generate JSON configuration
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

echo "[Runtime Config] ✅ Runtime configuration generated successfully!"
echo "[Runtime Config] Config file: $CONFIG_FILE"
echo "[Runtime Config] Config.js file: $CONFIG_JS_FILE"

# Display loaded configuration (without sensitive keys)
echo "[Runtime Config] Loaded configuration:"
echo "  - API URL: ${VITE_API_URL:-http://localhost:8000/api/v1}"
echo "  - API Base: ${VITE_API_BASE_URL:-http://localhost:8000}"
echo "  - WS URL: ${VITE_WS_BASE_URL:-ws://localhost:8000/ws}"
echo "  - Environment: ${VITE_ENVIRONMENT:-production}"
echo "  - Supabase URL: ${VITE_SUPABASE_URL:-[not set]}"
