# =============================================================================
# Frontend Dockerfile - React/Vite + Nginx
# =============================================================================

# Stage 1: Build
FROM node:18-alpine AS builder
WORKDIR /app
COPY packages/shared-types ./packages/shared-types
COPY frontend-hormonia ./frontend-hormonia
WORKDIR /app/frontend-hormonia
RUN npm install && npm run build

# Stage 2: Production
FROM nginx:alpine

# Install envsubst
RUN apk add --no-cache gettext

# Copy built files
COPY --from=builder /app/frontend-hormonia/dist /usr/share/nginx/html
COPY --from=builder /app/frontend-hormonia/nginx.conf /etc/nginx/nginx.conf.template

# Create directories
RUN mkdir -p /var/cache/nginx/api /usr/share/nginx/html/api

# Simple nginx config without template variables
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
