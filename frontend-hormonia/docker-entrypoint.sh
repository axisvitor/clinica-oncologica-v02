#!/bin/sh
set -e

# Simple entrypoint: substitute env vars and start nginx
envsubst '${BACKEND_HOST} ${BACKEND_PORT}' < /etc/nginx/nginx.conf > /tmp/nginx.conf
mv /tmp/nginx.conf /etc/nginx/nginx.conf

# Start nginx
exec nginx -g 'daemon off;'
