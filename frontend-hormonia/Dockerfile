# =============================================================================
# Frontend Dockerfile - React/Vite + Nginx
# Build context: frontend-hormonia/ (not project root)
# =============================================================================

# Stage 1: Build
FROM node:18-alpine AS builder
WORKDIR /app

# Copy shared-types first (from parent directory via build context workaround)
# Railway builds from frontend-hormonia/, so we copy from current dir
COPY package.json package-lock.json* ./

# Create a stub for shared-types to satisfy npm install
# The actual types are only needed for TypeScript compilation, not runtime
RUN mkdir -p /app/packages/shared-types && \
    echo '{"name":"@hormonia/shared-types","version":"1.0.0","main":"dist/index.js","types":"dist/index.d.ts"}' > /app/packages/shared-types/package.json && \
    mkdir -p /app/packages/shared-types/dist && \
    echo 'export {};' > /app/packages/shared-types/dist/index.js && \
    echo 'export {};' > /app/packages/shared-types/dist/index.d.ts

# Update package.json to use the stub path
RUN sed -i 's|"file:../packages/shared-types"|"file:/app/packages/shared-types"|g' package.json

# Install dependencies
RUN npm install --legacy-peer-deps

# Copy source code
COPY . .

# Build the application (TypeScript will use the stub types)
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
