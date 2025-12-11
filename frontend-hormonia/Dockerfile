# =============================================================================
# Frontend Dockerfile - React/Vite + Nginx (Railway Compatible)
# =============================================================================

# Stage 1: Build
FROM node:18-alpine AS builder
WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install --legacy-peer-deps

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Stage 2: Production
FROM nginx:alpine

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Create nginx config template with PORT variable
RUN cat > /etc/nginx/nginx.conf.template << 'EOF'
worker_processes auto;
pid /tmp/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    access_log /dev/stdout;
    error_log /dev/stderr;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;

    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/json application/xml;

    client_body_temp_path /tmp/client_temp;
    proxy_temp_path /tmp/proxy_temp;
    fastcgi_temp_path /tmp/fastcgi_temp;
    uwsgi_temp_path /tmp/uwsgi_temp;
    scgi_temp_path /tmp/scgi_temp;

    server {
        listen ${PORT:-3000};
        server_name _;
        root /usr/share/nginx/html;
        index index.html;

        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;

        location / {
            try_files $uri $uri/ /index.html;
        }

        location /health {
            access_log off;
            return 200 '{"status":"healthy"}';
            add_header Content-Type application/json;
        }

        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }
}
EOF

# Create startup script
RUN cat > /docker-entrypoint.sh << 'EOF'
#!/bin/sh
set -e
export PORT=${PORT:-3000}
echo "Starting nginx on port $PORT..."
envsubst '${PORT}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf
exec nginx -g 'daemon off;'
EOF

RUN chmod +x /docker-entrypoint.sh

ENV PORT=3000
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:${PORT:-3000}/health || exit 1

RUN addgroup -S appgroup && adduser -S appuser -G appgroup && \
    chown -R appuser:appgroup /usr/share/nginx/html /var/cache/nginx /tmp /etc/nginx && \
    mkdir -p /tmp/nginx.pid && touch /tmp/nginx.pid && chown appuser:appgroup /tmp/nginx.pid

USER appuser

CMD ["/docker-entrypoint.sh"]
