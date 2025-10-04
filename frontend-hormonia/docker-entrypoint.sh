#!/bin/sh
set -e

# Debug: Show current user and permissions
echo "🔍 Debug info:"
echo "   Current user: $(whoami)"
echo "   User ID: $(id -u)"
id
ls -la /etc/nginx/nginx.conf.template || echo "❌ Template not found"
ls -la /etc/nginx/nginx.conf 2>/dev/null || echo "⚠️ nginx.conf doesn't exist yet (expected)"

# CRITICAL FIX: Expand variables with defaults BEFORE envsubst
# This allows nginx.conf.template to use simple ${VAR} syntax
# while still providing default values when Railway env vars are missing
export BACKEND_HOST="${BACKEND_HOST:-backend}"
export BACKEND_PORT="${BACKEND_PORT:-8000}"

# Debug: show backend configuration BEFORE substitution
echo "🔗 Backend configuration (with defaults applied):"
echo "   BACKEND_HOST=${BACKEND_HOST}"
echo "   BACKEND_PORT=${BACKEND_PORT}"

# Process nginx.conf template with environment variables
# Write directly to /etc/nginx/nginx.conf (nginx user has write permission)
envsubst '${BACKEND_HOST} ${BACKEND_PORT}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

# Verify nginx config was created successfully
if [ ! -f /etc/nginx/nginx.conf ]; then
    echo "❌ ERROR: Failed to create nginx.conf"
    exit 1
fi

echo "✅ nginx.conf created successfully"

# Start nginx
exec nginx -g 'daemon off;'
