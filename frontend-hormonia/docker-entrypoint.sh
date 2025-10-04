#!/bin/sh
set -e

# Debug: Show current user and permissions
echo "🔍 Debug info:"
echo "   Current user: $(whoami)"
echo "   User ID: $(id -u)"
id
ls -la /etc/nginx/nginx.conf.template || echo "❌ Template not found"
ls -la /etc/nginx/nginx.conf 2>/dev/null || echo "⚠️ nginx.conf doesn't exist yet (expected)"

# Process nginx.conf template with environment variables
# CRITICAL FIX: Write directly to /etc/nginx/nginx.conf without using /tmp/
# Reason: nginx user doesn't have write permission to /tmp/ in Alpine Linux
envsubst '${BACKEND_HOST} ${BACKEND_PORT}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

# Debug: show final backend configuration
echo "🔗 Backend configured:"
echo "   BACKEND_HOST=${BACKEND_HOST:-backend}"
echo "   BACKEND_PORT=${BACKEND_PORT:-8000}"

# Verify nginx config was created successfully
if [ ! -f /etc/nginx/nginx.conf ]; then
    echo "❌ ERROR: Failed to create nginx.conf"
    exit 1
fi

echo "✅ nginx.conf created successfully"

# Start nginx
exec nginx -g 'daemon off;'
