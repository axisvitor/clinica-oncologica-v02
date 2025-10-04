#!/bin/bash

# Authentication Tests Runner
# Quick script to run all authentication tests

set -e  # Exit on error

echo "🧪 Running Authentication Tests"
echo "================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_step() {
    echo -e "${BLUE}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Get project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend-hormonia"
FRONTEND_DIR="$PROJECT_ROOT/frontend-hormonia"

# Parse arguments
RUN_BACKEND=true
RUN_FRONTEND=true
RUN_E2E=false
COVERAGE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --backend-only)
            RUN_FRONTEND=false
            RUN_E2E=false
            shift
            ;;
        --frontend-only)
            RUN_BACKEND=false
            RUN_E2E=false
            shift
            ;;
        --e2e-only)
            RUN_BACKEND=false
            RUN_FRONTEND=false
            RUN_E2E=true
            shift
            ;;
        --coverage)
            COVERAGE=true
            shift
            ;;
        --all)
            RUN_BACKEND=true
            RUN_FRONTEND=true
            RUN_E2E=true
            shift
            ;;
        --help)
            echo "Usage: ./run-auth-tests.sh [options]"
            echo ""
            echo "Options:"
            echo "  --backend-only    Run only backend tests"
            echo "  --frontend-only   Run only frontend unit tests"
            echo "  --e2e-only        Run only E2E tests"
            echo "  --coverage        Generate coverage reports"
            echo "  --all             Run all tests including E2E"
            echo "  --help            Show this help message"
            echo ""
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Backend Tests
if [ "$RUN_BACKEND" = true ]; then
    print_step "Running Backend Authentication Tests"
    cd "$BACKEND_DIR"

    if [ "$COVERAGE" = true ]; then
        pytest tests/unit/services/test_firebase_auth_service.py -v \
            --cov=app.services.firebase_auth_service \
            --cov-report=term-missing \
            --cov-report=html:htmlcov/auth
        print_success "Backend tests completed with coverage"
        echo "   Coverage report: $BACKEND_DIR/htmlcov/auth/index.html"
    else
        pytest tests/unit/services/test_firebase_auth_service.py -v
        print_success "Backend tests completed"
    fi
    echo ""
fi

# Frontend Unit Tests
if [ "$RUN_FRONTEND" = true ]; then
    print_step "Running Frontend Unit Tests"
    cd "$FRONTEND_DIR"

    if [ "$COVERAGE" = true ]; then
        npm run test -- tests/unit/lib/test_firebase_client.ts --coverage
        print_success "Frontend unit tests completed with coverage"
        echo "   Coverage report: $FRONTEND_DIR/coverage/index.html"
    else
        npm run test -- tests/unit/lib/test_firebase_client.ts
        print_success "Frontend unit tests completed"
    fi
    echo ""
fi

# E2E Tests
if [ "$RUN_E2E" = true ]; then
    print_step "Running E2E Authentication Tests"
    cd "$FRONTEND_DIR"

    # Check if Playwright is installed
    if ! npx playwright --version &> /dev/null; then
        print_step "Installing Playwright browsers..."
        npx playwright install
    fi

    npx playwright test tests/e2e/auth/login.spec.ts --reporter=list

    print_success "E2E tests completed"
    echo "   View report: npx playwright show-report"
    echo ""
fi

# Summary
echo "================================"
print_success "Test execution completed!"
echo ""

if [ "$COVERAGE" = true ]; then
    echo "📊 Coverage Reports:"
    [ "$RUN_BACKEND" = true ] && echo "   Backend:  file://$BACKEND_DIR/htmlcov/auth/index.html"
    [ "$RUN_FRONTEND" = true ] && echo "   Frontend: file://$FRONTEND_DIR/coverage/index.html"
    echo ""
fi

echo "📚 Next Steps:"
echo "   - Review test results above"
[ "$COVERAGE" = true ] && echo "   - Open coverage reports in browser"
[ "$RUN_E2E" = true ] && echo "   - View E2E report: cd frontend-hormonia && npx playwright show-report"
echo "   - Fix any failing tests"
echo ""
