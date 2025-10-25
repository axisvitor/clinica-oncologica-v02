#!/bin/sh

# Railway Runtime Environment Injection Script (Firebase + AWS backend)
set -e

echo "🚀 Starting Frontend with Runtime Environment Configuration..."

if [ -z "$VITE_API_URL" ]; then
    echo "⚠️ Critical environment variable missing!"
    echo "VITE_API_URL: ${VITE_API_URL:-'NOT SET'}"
    echo "Attempting to start with built-in fallback configuration..."
else
    echo "✅ Environment variables configuradas:"
    echo "VITE_API_URL: ${VITE_API_URL}"
    echo "VITE_API_BASE_URL: ${VITE_API_BASE_URL}"
    echo "VITE_WS_BASE_URL: ${VITE_WS_BASE_URL}"
    echo "VITE_FIREBASE_PROJECT_ID: ${VITE_FIREBASE_PROJECT_ID}"
fi

cat > /usr/share/nginx/html/runtime-config.js << EOF
window.RUNTIME_CONFIG = {
  VITE_API_URL: "${VITE_API_URL}",
  VITE_API_BASE_URL: "${VITE_API_BASE_URL}",
  VITE_WS_BASE_URL: "${VITE_WS_BASE_URL}",
  VITE_FIREBASE_PROJECT_ID: "${VITE_FIREBASE_PROJECT_ID}",
  VITE_FIREBASE_API_KEY: "${VITE_FIREBASE_API_KEY}",
  NODE_ENV: "production"
};
EOF

echo "🧩 Runtime configuration created"

if [ -f "/usr/share/nginx/html/index.html" ]; then
    sed -i 's|</head>|  <script src="/runtime-config.js"></script>\n  </head>|g' /usr/share/nginx/html/index.html
    echo "✅ Runtime config script injected into index.html"
fi

PORT=${PORT:-3000}

cat > /etc/nginx/conf.d/default.conf << EOF
server {
    listen ${PORT};
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }

    location /runtime-config.js {
        add_header Cache-Control "no-store, no-cache, must-revalidate";
        add_header Content-Type "application/javascript";
    }

    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

echo "🧾 Nginx configured for PORT ${PORT}"
echo "🚦 Starting nginx..."
exec nginx -g "daemon off;"
