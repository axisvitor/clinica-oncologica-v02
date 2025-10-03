#!/bin/bash

# E2E Test Runner for Quiz System
# Runs complete E2E test suite with coverage and reporting

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "  Quiz System E2E Test Suite"
echo "=========================================="
echo ""

# Check if Redis is running
echo -n "Checking Redis connection... "
if redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
    echo ""
    echo "Redis is not running. Please start Redis first:"
    echo "  docker run -d -p 6379:6379 redis:7-alpine"
    echo "  OR"
    echo "  brew services start redis"
    exit 1
fi

# Check if database is accessible
echo -n "Checking database connection... "
if psql $DATABASE_URL -c "SELECT 1" > /dev/null 2>&1; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}WARNING${NC}"
    echo "Could not connect to database. Tests may fail."
    echo "DATABASE_URL: $DATABASE_URL"
fi

echo ""
echo "Running E2E tests..."
echo ""

# Run tests with coverage
pytest tests/e2e/ \
    -v \
    --tb=short \
    --cov=app.services.quiz \
    --cov=app.services.quiz_flow_integration \
    --cov=app.services.webhook_processor \
    --cov=app.services.unified_whatsapp_service \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    --durations=10 \
    "$@"

TEST_EXIT_CODE=$?

echo ""
echo "=========================================="

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo "Coverage report generated at: htmlcov/index.html"
    echo "Open with: open htmlcov/index.html"
else
    echo -e "${RED}✗ Some tests failed${NC}"
    echo ""
    echo "Review the output above for details."
    exit $TEST_EXIT_CODE
fi

echo ""
echo "Next steps:"
echo "  1. Review coverage report: open htmlcov/index.html"
echo "  2. Deploy monitoring stack: cd monitoring && docker-compose -f docker-compose.monitoring.yml up -d"
echo "  3. View Grafana dashboard: http://localhost:3000"
echo ""
