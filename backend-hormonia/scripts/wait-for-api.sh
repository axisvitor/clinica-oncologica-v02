#!/bin/bash
###############################################################################
# Wait for API to be Ready
# Purpose: Helper script for CI/CD to wait for API to start
# Usage: ./wait-for-api.sh [URL] [TIMEOUT]
###############################################################################

set -e

API_URL="${1:-http://localhost:8000}"
TIMEOUT="${2:-60}"
HEALTH_ENDPOINT="${API_URL}/api/v2/health"

echo "Waiting for API to be ready at: $HEALTH_ENDPOINT"
echo "Timeout: ${TIMEOUT}s"

elapsed=0
while [ $elapsed -lt $TIMEOUT ]; do
    if curl -s -f "$HEALTH_ENDPOINT" > /dev/null 2>&1; then
        echo "✓ API is ready!"
        exit 0
    fi

    echo "Waiting... (${elapsed}s / ${TIMEOUT}s)"
    sleep 2
    elapsed=$((elapsed + 2))
done

echo "✗ Timeout waiting for API"
exit 1
