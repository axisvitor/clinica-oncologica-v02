#!/bin/sh
set -e

# Debug info
echo "[Debug] User info: $(whoami) (uid=$(id -u))"
id
ls -la /etc/nginx/nginx.conf.template || echo "[Warn] nginx.conf.template not found"
ls -la /etc/nginx/nginx.conf 2>/dev/null || echo "[Info] nginx.conf will be generated"

# helper to sanitize env values
sanitize_url_py() {
python3 - "$@" <<'PY'
import os, sys
from urllib.parse import urlsplit, urlunsplit

# normalize base url
api_base = os.environ.get('VITE_API_BASE_URL', '').strip()
api_url = os.environ.get('VITE_API_URL', '').strip()
ws_base = os.environ.get('VITE_WS_BASE_URL', os.environ.get('VITE_WS_URL', '')).strip()
api_base_path = os.environ.get('VITE_API_BASE_PATH', 'api/v2').strip('/') or 'api/v2'

# helper functions
def ensure_scheme(url: str, scheme: str) -> str:
    if not url:
        return ''
    url = url.strip()
    if url.startswith('http://') or url.startswith('https://') or url.startswith('ws://') or url.startswith('wss://'):
        return url
    if url.startswith('//'):
        return f"{scheme}:{url}"
    if ':' in url and not url.startswith(f"{scheme}://"):
        prefix, rest = url.split(':', 1)
        rest = rest.lstrip('/')
        return f"{scheme}://{rest}"
    return f"{scheme}://{url}"

def normalize_api(url: str) -> tuple[str,str]:
    if not url:
        return '',''
    parts = urlsplit(url)
    path = parts.path or ''
    query = parts.query or ''
    frag = parts.fragment or ''
    base = urlunsplit((parts.scheme, parts.netloc, '', '', ''))
    return base, urlunsplit((parts.scheme, parts.netloc, path, query, frag))

def ensure_path(url: str, required: str) -> str:
    if not url:
        return ''
    required = '/' + required.strip('/')
    parts = urlsplit(url)
    path = parts.path or ''
    if not path or path == '/':
        path = required
    elif required.strip('/') not in path.strip('/'):
        if path.endswith('/'):
            path = path.rstrip('/')
        path = path + required
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))

def normalize_ws(url: str, api_base_url: str) -> str:
    url = url.strip()
    if not url and api_base_url:
        url = api_base_url.replace('https://', 'wss://').replace('http://', 'ws://')
    url = ensure_scheme(url, 'wss') if url.startswith('wss') or url.startswith('ws') else ensure_scheme(url, 'wss')
    parts = urlsplit(url)
    path = parts.path or ''
    if not path or path == '/':
        path = '/ws/connect'
    elif 'ws' not in path:
        if path.endswith('/'):
            path = path.rstrip('/')
        path = path + '/ws/connect'
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))

api_base = ensure_scheme(api_base, 'https') if api_base else ''
api_url = ensure_scheme(api_url, 'https') if api_url else ''
if not api_url and api_base:
    api_url = api_base
api_url = ensure_path(api_url, api_base_path)
base_from_url, full_api = normalize_api(api_url)
if not api_base:
    api_base = base_from_url
ws_full = normalize_ws(ws_base, api_base)
api_path = '/' + api_base_path.strip('/')

print(f"export VITE_API_BASE_URL='{api_base}'")
print(f"export VITE_API_URL='{full_api}'")
print(f"export VITE_WS_BASE_URL='{ws_full}'")
print(f"export VITE_WS_URL='{ws_full}'")
print(f"export VITE_API_BASE_PATH='{api_path}'")
PY
}

# Execute sanitizer and apply exports to current shell
eval "$(sanitize_url_py)"

echo "[Debug] Sanitized frontend env:"
echo "   VITE_API_BASE_URL=${VITE_API_BASE_URL}"
echo "   VITE_API_URL=${VITE_API_URL}"
echo "   VITE_API_BASE_PATH=${VITE_API_BASE_PATH}"
echo "   VITE_WS_BASE_URL=${VITE_WS_BASE_URL}"

export BACKEND_HOST="${BACKEND_HOST:-clinica-oncologica-v02.railway.internal}"
export BACKEND_PORT="${BACKEND_PORT:-80}"
export PORT="${PORT:-8080}"

echo "[Debug] Backend configuration:"
echo "   BACKEND_HOST=${BACKEND_HOST}"
echo "   BACKEND_PORT=${BACKEND_PORT}"
echo "   PORT=${PORT}"

CONFIG_FILE="/usr/share/nginx/html/api/config"
CONFIG_JS_FILE="/usr/share/nginx/html/api/config.js"
mkdir -p /usr/share/nginx/html/api

cat > "$CONFIG_FILE" << EOF
{
  "VITE_API_URL": "${VITE_API_URL:-http://localhost:8000/api/v2}",
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
  "VITE_API_URL": "${VITE_API_URL:-http://localhost:8000/api/v2}",
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

envsubst '${BACKEND_HOST} ${BACKEND_PORT} ${PORT}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

exec nginx -g 'daemon off;'
