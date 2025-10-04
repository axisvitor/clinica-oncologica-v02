# Multi-stage Dockerfile optimized for Railway
# Stage 1: Dependencies
FROM node:20-alpine@sha256:2d07db07a2df6830718ae2a47db6fedce6745f5bcd174c398f2acdda90a11c03 AS deps
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
FROM node:20-alpine@sha256:2d07db07a2df6830718ae2a47db6fedce6745f5bcd174c398f2acdda90a11c03 AS builder
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
# Firebase build args removed - loaded at runtime via /api/config
# ARG VITE_FIREBASE_API_KEY
# ARG VITE_FIREBASE_AUTH_DOMAIN
# ARG VITE_FIREBASE_PROJECT_ID
# ARG VITE_FIREBASE_STORAGE_BUCKET
# ARG VITE_FIREBASE_MESSAGING_SENDER_ID
# ARG VITE_FIREBASE_APP_ID

# Set environment variables for build
ENV NODE_ENV=production \
    VITE_SUPABASE_URL=${VITE_SUPABASE_URL} \
    VITE_SUPABASE_ANON_KEY=${VITE_SUPABASE_ANON_KEY} \
    VITE_API_URL=${VITE_API_URL} \
    VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_WS_BASE_URL=${VITE_WS_BASE_URL}
    # Firebase env vars removed - loaded at runtime

# Debug: Print environment variables (without sensitive data)
RUN echo "🔨 Building with environment:" && \
    echo "  VITE_SUPABASE_URL=${VITE_SUPABASE_URL:+[SET]}" && \
    echo "  VITE_API_URL=${VITE_API_URL:+[SET]}" && \
    echo "  VITE_API_BASE_URL=${VITE_API_BASE_URL:+[SET]}" && \
    echo "  VITE_WS_BASE_URL=${VITE_WS_BASE_URL:+[SET]}" && \
    echo "  Firebase vars loaded at runtime"

# Build application with runtime config generation
RUN npm run build:runtime

FROM nginx:alpine@sha256:2140dad235c130ac861018a4e13a6bc8aea3a35f3a40e20c1b060d51a7efd250 AS production

# Install curl for health checks
RUN apk add --no-cache curl

COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration as template
COPY nginx.conf /etc/nginx/nginx.conf.template

# Copy robust entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Expose port (Railway will set PORT env var dynamically)
EXPOSE ${PORT:-3000}

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT:-3000}/health || exit 1

# Set permissions for non-root execution
# Note: nginx:alpine already has nginx user (uid 101)
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    chown -R nginx:nginx /etc/nginx/conf.d && \
    chown nginx:nginx /etc/nginx/nginx.conf.template && \
    touch /etc/nginx/nginx.conf && \
    chown nginx:nginx /etc/nginx/nginx.conf && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid && \
    chown nginx:nginx /docker-entrypoint.sh

# Switch to non-root user
USER nginx

# Start nginx
ENTRYPOINT ["/docker-entrypoint.sh"]