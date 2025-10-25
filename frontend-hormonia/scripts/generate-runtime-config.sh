#!/bin/sh
set -e

echo "[Runtime Config] Generating runtime configuration from environment variables..."

sanitize_url_py() {
python3 - "$@" <<'PY'
import os
from urllib.parse import urlsplit, urlunsplit

api_base = os.environ.get('VITE_API_BASE_URL', '').strip()
api_url = os.environ.get('VITE_API_URL', '').strip()
ws_url = os.environ.get('VITE_WS_BASE_URL', os.environ.get('VITE_WS_URL', '')).strip()
api_base_path = os.environ.get('VITE_API_BASE_PATH', 'api/v1').strip('/') or 'api/v1'

# helper functions (same as entrypoint)
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

def normalize_api(url: str) -> tuple[str,str]:
    parts = urlsplit(url)
    base = urlunsplit((parts.scheme, parts.netloc, '', '', ''))
    return base, url

def normalize_ws(url: str, api_base_url: str) -> str:
    if not url and api_base_url:
        url = api_base_url.replace('https://', 'wss://').replace('http://', 'ws://')
    url = ensure_scheme(url, 'wss')
    parts = urlsplit(url)
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

api_base = ensure_scheme(api_base, 'https') if api_base else ''
api_url = ensure_scheme(api_url, 'https') if api_url else ''
if not api_url and api_base:
    api_url = api_base
api_url = ensure_path(api_url, api_base_path)
base_from_url, full_api = normalize_api(api_url)
if not api_base:
    api_base = base_from_url
ws_full = normalize_ws(ws_url, api_base)
api_path = '/' + api_base_path.strip('/')

print(f"export VITE_API_BASE_URL='{api_base}'")
print(f"export VITE_API_URL='{full_api}'")
print(f"export VITE_WS_BASE_URL='{ws_full}'")
print(f"export VITE_WS_URL='{ws_full}'")
print(f"export VITE_API_BASE_PATH='{api_path}'")

mime_list = normalize_mimes(os.environ.get('VITE_SUPPORTED_FILE_TYPES'))
if mime_list:
    print(f"export VITE_SUPPORTED_FILE_TYPES='{mime_list}'")
PY
}

sanitize_url_py

CONFIG_FILE="/usr/share/nginx/html/api/config"
CONFIG_JS_FILE="/usr/share/nginx/html/api/config.js"
mkdir -p /usr/share/nginx/html/api

cat > "$CONFIG_FILE" << EOF
{
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

if [ -f "$CONFIG_FILE" ] && [ -f "$CONFIG_JS_FILE" ]; then
  echo "[Runtime Config] Files generated successfully."
  echo "  - API URL: ${VITE_API_URL}"
  echo "  - API Base: ${VITE_API_BASE_URL}"
  echo "  - WS URL: ${VITE_WS_BASE_URL}"
else
  echo "[Warn] Runtime config files may not have been created properly"
fi
