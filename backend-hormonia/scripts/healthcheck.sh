#!/bin/bash
set -e

# healthcheck.sh - Unified Health Check Script
# Depends on SERVICE_TYPE environment variable being set in Railway/Docker
# Default: api

TYPE=${SERVICE_TYPE:-api}

if [ "$TYPE" = "api" ]; then
    # Check HTTP endpoint
    curl -f http://localhost:${PORT:-8000}/health || exit 1

elif [ "$TYPE" = "worker" ]; then
    # Check if Celery worker is responsive
    # Note: This requires the worker to be running and app to be importable
    python -c "from app.celery_app import celery_app; celery_app.control.inspect().active()" || exit 1

elif [ "$TYPE" = "beat" ]; then
    # Check if Beat scheduler is running (process check or file check)
    # Beat writes a schedule file periodically
    # A simple check is to verify the python process is running, but here we check the schedule file existence/write
    # or just exit 0 if we assume process manager handles crashes.
    # Let's use a simple python check for the pid file or similar
    if [ -f "/tmp/celerybeat.pid" ]; then
        exit 0
    else
        exit 1
    fi

else
    echo "Unknown SERVICE_TYPE: $TYPE"
    exit 1
fi
