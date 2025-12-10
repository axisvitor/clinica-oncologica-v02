# =============================================================================
# Frontend Dockerfile - React/Vite + Nginx
# Build context: frontend-hormonia/
# =============================================================================

# Stage 1: Build
FROM node:18-alpine AS builder
WORKDIR /app

# Copy shared-types first and build it
COPY shared-types ./shared-types
WORKDIR /app/shared-types
RUN npm install && npm run build

# Copy frontend package files
WORKDIR /app
COPY package.json package-lock.json* ./

# Install dependencies (shared-types will be linked from ./shared-types)
RUN npm install --legacy-peer-deps

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Stage 2: Production
FROM nginx:alpine

# Install envsubst for runtime config
RUN apk add --no-cache gettext

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Create directories
RUN mkdir -p /var/cache/nginx/api /usr/share/nginx/html/api

# Simple nginx config
RUN echo 'worker_processes 1;' > /etc/nginx/nginx.conf && \
    echo 'events { worker_connections 1024; }' >> /etc/nginx/nginx.conf && \
    echo 'http {' >> /etc/nginx/nginx.conf && \
    echo '    include /etc/nginx/mime.types;' >> /etc/nginx/nginx.conf && \
    echo '    default_type application/octet-stream;' >> /etc/nginx/nginx.conf && \
    echo '    sendfile on;' >> /etc/nginx/nginx.conf && \
    echo '    gzip on;' >> /etc/nginx/nginx.conf && \
    echo '    server {' >> /etc/nginx/nginx.conf && \
    echo '        listen 3000;' >> /etc/nginx/nginx.conf && \
    echo '        root /usr/share/nginx/html;' >> /etc/nginx/nginx.conf && \
    echo '        location / { try_files $uri $uri/ /index.html; }' >> /etc/nginx/nginx.conf && \
    echo '        location /health { return 200 "ok"; }' >> /etc/nginx/nginx.conf && \
    echo '    }' >> /etc/nginx/nginx.conf && \
    echo '}' >> /etc/nginx/nginx.conf

ENV PORT=3000
EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
