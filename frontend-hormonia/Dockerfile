# Frontend Dockerfile - React/Vite
# Rebuilt: 2024-12-10-v3
FROM node:18-alpine AS builder
WORKDIR /app

# Copy shared packages first
COPY packages/shared-types ./packages/shared-types

# Copy frontend files
COPY frontend-hormonia ./frontend-hormonia

# Install and build
WORKDIR /app/frontend-hormonia
RUN npm install
RUN npm run build

# Production stage
FROM nginx:alpine
RUN apk add --no-cache python3 gettext

# Copy build output
COPY --from=builder /app/frontend-hormonia/dist /usr/share/nginx/html

# Copy nginx config from builder (already in context)
COPY --from=builder /app/frontend-hormonia/nginx.conf /etc/nginx/nginx.conf.template

# Create entrypoint script inline using printf to avoid heredoc issues
RUN printf '%s\n' \
  '#!/bin/sh' \
  'set -e' \
  'echo "[Entrypoint] Starting frontend container..."' \
  'export BACKEND_HOST="${BACKEND_HOST:-backend-clinica-production-161d.up.railway.app}"' \
  'export BACKEND_PORT="${BACKEND_PORT:-443}"' \
  'export BACKEND_SCHEME="${BACKEND_SCHEME:-https}"' \
  'export PORT="${PORT:-3000}"' \
  'echo "[Config] BACKEND_HOST=${BACKEND_HOST}"' \
  'echo "[Config] BACKEND_PORT=${BACKEND_PORT}"' \
  'echo "[Config] BACKEND_SCHEME=${BACKEND_SCHEME}"' \
  'echo "[Config] PORT=${PORT}"' \
  'mkdir -p /usr/share/nginx/html/api' \
  'cat > /usr/share/nginx/html/api/config << CFGEOF' \
  '{' \
  '  "VITE_API_URL": "${VITE_API_URL:-https://${BACKEND_HOST}/api/v2}",' \
  '  "VITE_API_BASE_URL": "${VITE_API_BASE_URL:-https://${BACKEND_HOST}}",' \
  '  "VITE_WS_BASE_URL": "${VITE_WS_BASE_URL:-wss://${BACKEND_HOST}/ws}",' \
  '  "VITE_ENVIRONMENT": "${VITE_ENVIRONMENT:-production}",' \
  '  "VITE_DEBUG_MODE": "${VITE_DEBUG_MODE:-false}"' \
  '}' \
  'CFGEOF' \
  'cat > /usr/share/nginx/html/api/config.js << JSEOF' \
  'window.__ENV_CONFIG__ = {' \
  '  "VITE_API_URL": "${VITE_API_URL:-https://${BACKEND_HOST}/api/v2}",' \
  '  "VITE_API_BASE_URL": "${VITE_API_BASE_URL:-https://${BACKEND_HOST}}",' \
  '  "VITE_WS_BASE_URL": "${VITE_WS_BASE_URL:-wss://${BACKEND_HOST}/ws}",' \
  '  "VITE_ENVIRONMENT": "${VITE_ENVIRONMENT:-production}",' \
  '  "VITE_DEBUG_MODE": "${VITE_DEBUG_MODE:-false}"' \
  '};' \
  'JSEOF' \
  'echo "[Config] Runtime config generated"' \
  'envsubst '"'"'${BACKEND_HOST} ${BACKEND_PORT} ${BACKEND_SCHEME} ${PORT}'"'"' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf' \
  'echo "[Entrypoint] Starting nginx on port ${PORT}..."' \
  'exec nginx -g "daemon off;"' \
  > /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh

# Create nginx cache directory
RUN mkdir -p /var/cache/nginx/api

ENV PORT=3000
EXPOSE 3000

ENTRYPOINT ["/docker-entrypoint.sh"]
