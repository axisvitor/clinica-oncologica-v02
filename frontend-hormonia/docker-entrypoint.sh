#!/bin/sh
set -e

# Debug: Show current user and permissions
echo "[Debug] User info:"
echo "   Current user: $(whoami)"
echo "   User ID: $(id -u)"
id
ls -la /etc/nginx/nginx.conf.template || echo "[Warn] nginx.conf.template not found"
ls -la /etc/nginx/nginx.conf 2>/dev/null || echo "[Info] nginx.conf will be generated"

# Helper: sanitize critical URLs coming from environment variables
sanitize_env_urls() {
  SANITIZED_EXPORTS=$(python3 - <<'PY'
import os
from urllib.parse import urlsplit, urlunsplit

def normalize(url: str, scheme: str, default: str) -> str:
    if not url:
        return default
    url = url.strip()
    lower_scheme = scheme.lower()
    if url.startswith(f"{scheme}://") or url.startswith(f"{lower_scheme}://"):
        return url
    if url.startswith(f"{scheme}:") or url.startswith(f"{lower_scheme}:"):
        return f"{scheme}://" + url[len(scheme)+1:].lstrip('/')
    if url.startswith('//'):
        return f"{scheme}:{url}"
    if '://' not in url:
        return f"{scheme}://{url}"
    return url

def ensure_path(url: str, required_path: str) -> str:
    if not url:
        return url
    required_path = '/' + required_path.strip('/')
    parts = urlsplit(url)
    path = parts.path or ''
    if not path or path == '/':
        path = required_path
    elif required_path.strip('/') not in path.strip('/'):
        if path.endswith('/'):
            path = path.rstrip('/')
        path = path + required_path
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))

def normalize_ws(url: str, default: str) -> str:
    normalized = normalize(url, 'wss', default)
    if not normalized:
        return normalized
    parts = urlsplit(normalized)
    path = parts.path or ''
    if not path or path == '/':
        path = '/ws/connect'
    elif 'ws' not in path:
        if path.endswith('/'):
            path = path.rstrip('/')
        path = path + '/ws/connect'
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))

def normalize_mimes(value: str) -> str:
    if not value:
        return value
    items = []
    for raw in value.split(','):
        itm = raw.strip()
        if not itm:
            continue
        if '/' not in itm:
            for prefix in ('image', 'application', 'text', 'audio', 'video'):
                if itm.startswith(prefix):
                    rest = itm[len(prefix):].lstrip('/-_')
                    itm = f"{prefix}/{rest}" if rest else prefix
                    break
        items.append(itm)
    return ','.join(items)

api_base = normalize(os.environ.get('VITE_API_BASE_URL'), 'https', 'http://localhost:8000')
api_url = normalize(os.environ.get('VITE_API_URL'), 'https', 'http://localhost:8000/api/v1')
if not api_url and api_base:
    api_url = api_base
api_url = ensure_path(api_url, os.environ.get('VITE_API_BASE_PATH') or 'api/v1')
parts = urlsplit(api_url)
if not api_base:
    api_base = urlunsplit((parts.scheme, parts.netloc, '', '', ''))
ws_base = normalize_ws(os.environ.get('VITE_WS_BASE_URL') or os.environ.get('VITE_WS_URL') or '', '')
if not ws_base:
    ws_base = normalize_ws(api_base.replace('https://', 'wss://').replace('http://', 'ws://'), 'wss://localhost/ws/connect')
api_base_path = os.environ.get('VITE_API_BASE_PATH') or '/api/v1'
if not api_base_path.startswith('/'):
    api_base_path = '/' + api_base_path
mime_list = normalize_mimes(os.environ.get('VITE_SUPPORTED_FILE_TYPES'))
exports = {
    'VITE_API_BASE_URL': api_base,
    'VITE_API_URL': api_url,
    'VITE_WS_BASE_URL': ws_base,
    'VITE_WS_URL': ws_base,
    'VITE_API_BASE_PATH': api_base_path,
}
if mime_list:
    exports['VITE_SUPPORTED_FILE_TYPES'] = mime_list
for key, value in exports.items():
    if value:
        safe = value.replace("'", "'\\''")
        print(f"export {key}='{safe}'")
PY
)
  if [ -n "${SANITIZED_EXPORTS}" ]; then
    eval "${SANITIZED_EXPORTS}"
  fi
}

sanitize_env_urls

# Debug after sanitation
echo "[Debug] Sanitized frontend env:" 
echo "   VITE_API_BASE_URL=${VITE_API_BASE_URL}"
echo "   VITE_API_URL=${VITE_API_URL}"
echo "   VITE_API_BASE_PATH=${VITE_API_BASE_PATH}"
echo "   VITE_WS_BASE_URL=${VITE_WS_BASE_URL}"

# CRITICAL FIX: Expand variables with defaults BEFORE envsubst
export BACKEND_HOST="${BACKEND_HOST:-clinica-oncologica-v02.railway.internal}"
export BACKEND_PORT="${BACKEND_PORT:-80}"
export PORT="${PORT:-3000}"

echo "[Debug] Backend configuration:"
echo "   BACKEND_HOST=${BACKEND_HOST}"
echo "   BACKEND_PORT=${BACKEND_PORT}"
echo "   PORT=${PORT}"

echo "[Runtime Config] Generating runtime configuration from environment variables..."
CONFIG_FILE="/usr/share/nginx/html/api/config"
CONFIG_JS_FILE="/usr/share/nginx/html/api/config.js"
mkdir -p /usr/share/nginx/html/api

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

echo "[Runtime Config] API URL: ${VITE_API_URL}"
echo "[Runtime Config] API Base: ${VITE_API_BASE_URL}"
echo "[Runtime Config] WS URL: ${VITE_WS_BASE_URL}"
echo "[Runtime Config] Environment: ${VITE_ENVIRONMENT:-production}"

if [ ! -f "$CONFIG_FILE" ] || [ ! -f "$CONFIG_JS_FILE" ]; then
    echo "[Warn] Runtime config files were not generated as expected"
fi

envsubst '${BACKEND_HOST} ${BACKEND_PORT} ${PORT}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

if [ ! -f /etc/nginx/nginx.conf ]; then
    echo "[Error] Failed to create nginx.conf"
    exit 1
fi

echo "[Info] nginx.conf created successfully"
exec nginx -g 'daemon off;'