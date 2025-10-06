#!/bin/bash
# CORS Test Suite Runner

set -e

echo "🧪 CORS Test Suite Runner"
echo "=========================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
BACKEND_URL=${BACKEND_URL:-"http://localhost:8000"}
FRONTEND_URL=${FRONTEND_URL:-"http://localhost:3000"}
VERBOSE=${VERBOSE:-""}

echo "📋 Configuration:"
echo "  Backend URL:  $BACKEND_URL"
echo "  Frontend URL: $FRONTEND_URL"
echo ""

# Check if backend is running
echo "🔍 Checking backend availability..."
if curl -s -f "$BACKEND_URL/api/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend is running at $BACKEND_URL${NC}"
else
    echo -e "${RED}❌ Backend is not accessible at $BACKEND_URL${NC}"
    echo "Please start the backend server first."
    exit 1
fi
echo ""

# Run coordination hooks
echo "🔗 Running coordination hooks..."
npx claude-flow@alpha hooks pre-task --description "CORS test execution" || true
echo ""

# Function to run test category
run_test_category() {
    local category=$1
    local description=$2

    echo -e "${YELLOW}▶ $description${NC}"
    if pytest "tests/e2e/cors/$category" -v $VERBOSE; then
        echo -e "${GREEN}✅ $description passed${NC}"
        echo ""
        return 0
    else
        echo -e "${RED}❌ $description failed${NC}"
        echo ""
        return 1
    fi
}

# Test execution
FAILED=0

echo "🧪 Running CORS Test Suite..."
echo ""

# 1. Preflight tests
run_test_category "test_cors_preflight.py" "Preflight (OPTIONS) Tests" || FAILED=1

# 2. Actual request tests
run_test_category "test_cors_actual_requests.py" "Actual Request Tests" || FAILED=1

# 3. Disallowed origin tests
run_test_category "test_cors_disallowed_origins.py" "Disallowed Origin Tests" || FAILED=1

# 4. Invalid combination tests
run_test_category "test_cors_invalid_combinations.py" "Invalid Combination Tests" || FAILED=1

# Backend unit tests
echo -e "${YELLOW}▶ Backend Middleware Unit Tests${NC}"
if pytest "tests/backend/cors/test_cors_middleware.py" -v $VERBOSE; then
    echo -e "${GREEN}✅ Backend unit tests passed${NC}"
    echo ""
else
    echo -e "${RED}❌ Backend unit tests failed${NC}"
    echo ""
    FAILED=1
fi

# Summary
echo "=========================="
echo "📊 Test Summary"
echo "=========================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All CORS tests passed!${NC}"

    # Run completion hooks
    echo ""
    echo "🔗 Running completion hooks..."
    npx claude-flow@alpha hooks post-task --task-id "cors-test-execution" || true

    exit 0
else
    echo -e "${RED}❌ Some CORS tests failed${NC}"
    echo "Please review the output above for details."
    exit 1
fi
