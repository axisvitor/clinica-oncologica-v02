#!/bin/sh
set -e

# Process nginx.conf template with environment variables
# Template file: /etc/nginx/nginx.conf.template
# Output file: /etc/nginx/nginx.conf (nginx user now has write permission)
envsubst '${BACKEND_HOST} ${BACKEND_PORT}' < /etc/nginx/nginx.conf.template > /tmp/nginx.conf
mv /tmp/nginx.conf /etc/nginx/nginx.conf

# Debug: show final backend configuration
echo "🔗 Backend configured:"
echo "   BACKEND_HOST=${BACKEND_HOST:-backend}"
echo "   BACKEND_PORT=${BACKEND_PORT:-8000}"

# Start nginx
exec nginx -g 'daemon off;'
