# Multi-stage Dockerfile optimized for Railway
# Stage 1: Dependencies
FROM node:20-alpine AS deps
WORKDIR /app

# Copy package files
COPY package*.json ./

# Generate package-lock.json if it doesn't exist
RUN if [ ! -f package-lock.json ]; then \
      echo "⚠️ package-lock.json not found, generating..."; \
      npm install; \
    else \
      echo "✓ package-lock.json found"; \
      npm ci --prefer-offline --no-audit; \
    fi

# Stage 2: Builder
FROM node:20-alpine AS builder
WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/package*.json ./

# Copy source code
COPY . .

# Build arguments for Railway
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ARG VITE_API_URL
ARG VITE_API_BASE_URL
ARG VITE_WS_BASE_URL

# Set environment variables for build
ENV NODE_ENV=production \
    VITE_SUPABASE_URL=${VITE_SUPABASE_URL} \
    VITE_SUPABASE_ANON_KEY=${VITE_SUPABASE_ANON_KEY} \
    VITE_API_URL=${VITE_API_URL} \
    VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_WS_BASE_URL=${VITE_WS_BASE_URL}

# Debug: Print environment variables (without sensitive data)
RUN echo "🔨 Building with environment:" && \
    echo "  VITE_SUPABASE_URL=${VITE_SUPABASE_URL:+[SET]}" && \
    echo "  VITE_API_URL=${VITE_API_URL:+[SET]}" && \
    echo "  VITE_API_BASE_URL=${VITE_API_BASE_URL:+[SET]}" && \
    echo "  VITE_WS_BASE_URL=${VITE_WS_BASE_URL:+[SET]}"

# Build application
RUN npm run build || npm run build:prod

FROM nginx:alpine AS production

# Install curl for health checks
RUN apk add --no-cache curl

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Create runtime config script placeholder
# Configuration will be loaded from /api/config endpoint at runtime
RUN echo 'window.ENV_CONFIG = {};' > /usr/share/nginx/html/config.js && \
    echo '// Configuration loaded dynamically from /api/config' >> /usr/share/nginx/html/config.js

# Create startup script
RUN printf '#!/bin/sh\n\
set -e\n\
\n\
# Update nginx port if PORT is set (Railway sets this)\n\
if [ -n "$PORT" ]; then\n\
  sed -i "s/listen 3000;/listen $PORT;/g" /etc/nginx/conf.d/default.conf\n\
  echo " Configured nginx to listen on port $PORT"\n\
fi\n\
\n\
# Configure BACKEND_URL for proxy_pass\n\
if [ -z "$BACKEND_URL" ] && [ -n "$VITE_API_BASE_URL" ]; then\n\
  BACKEND_URL="$VITE_API_BASE_URL"\n\
fi\n\
\n\
if [ -z "$BACKEND_URL" ]; then\n\
  BACKEND_URL="http://backend:8000"\n\
  echo " BACKEND_URL not set; defaulting to $BACKEND_URL"\n\
fi\n\
\n\
# Substitute placeholder in nginx config\n\
sed -i "s|\\${BACKEND_URL}|$BACKEND_URL|g" /etc/nginx/conf.d/default.conf\n\
echo " Configured BACKEND_URL to $BACKEND_URL in nginx config"\n\
\n\
echo " Starting nginx..."\n\
exec nginx -g "daemon off;"\n' > /docker-entrypoint.sh && \
    chmod +x /docker-entrypoint.sh

# Expose port (Railway will override with PORT env var)
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT:-3000}/health || exit 1

# Start nginx
ENTRYPOINT ["/docker-entrypoint.sh"]