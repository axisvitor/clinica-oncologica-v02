#!/bin/sh

# Railway Runtime Environment Injection Script
# This script handles cases where Docker buildArgs don't work properly

echo "🚀 Starting Frontend with Runtime Environment Configuration..."

# Check if we have the required environment variables
if [ -z "$VITE_SUPABASE_URL" ] || [ -z "$VITE_API_URL" ]; then
    echo "❌ Critical environment variables missing!"
    echo "VITE_SUPABASE_URL: ${VITE_SUPABASE_URL:-'NOT SET'}"
    echo "VITE_API_URL: ${VITE_API_URL:-'NOT SET'}"
    echo "Attempting to start with built-in fallback configuration..."
else
    echo "✅ Environment variables configured:"
    echo "VITE_SUPABASE_URL: ${VITE_SUPABASE_URL}"
    echo "VITE_API_URL: ${VITE_API_URL}"
    echo "VITE_API_BASE_URL: ${VITE_API_BASE_URL}"
    echo "VITE_WS_BASE_URL: ${VITE_WS_BASE_URL}"
fi

# Create runtime configuration file for SPA
cat > /usr/share/nginx/html/runtime-config.js << EOF
window.RUNTIME_CONFIG = {
  VITE_SUPABASE_URL: "${VITE_SUPABASE_URL}",
  VITE_SUPABASE_ANON_KEY: "${VITE_SUPABASE_ANON_KEY}",
  VITE_API_URL: "${VITE_API_URL}",
  VITE_API_BASE_URL: "${VITE_API_BASE_URL}",
  VITE_WS_BASE_URL: "${VITE_WS_BASE_URL}",
  NODE_ENV: "production"
};
EOF

echo "📝 Runtime configuration created"

# Update index.html to load runtime config
if [ -f "/usr/share/nginx/html/index.html" ]; then
    # Add runtime config script to head
    sed -i 's|</head>|  <script src="/runtime-config.js"></script>\n  </head>|g' /usr/share/nginx/html/index.html
    echo "✅ Runtime config script added to index.html"
fi

# Configure nginx to serve on Railway's PORT
PORT=${PORT:-3000}

# Update nginx configuration for Railway PORT
cat > /etc/nginx/conf.d/default.conf << EOF
server {
    listen ${PORT};
    root /usr/share/nginx/html;
    index index.html;

    # SPA routing
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }

    # Runtime config endpoint
    location /runtime-config.js {
        add_header Cache-Control "no-store, no-cache, must-revalidate";
        add_header Content-Type "application/javascript";
    }

    # Static assets caching
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

echo "🌐 Nginx configured for PORT ${PORT}"

# Start nginx
echo "🏁 Starting nginx..."
exec nginx -g "daemon off;"