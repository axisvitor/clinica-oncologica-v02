#!/bin/bash

# Firebase Authentication Validation Script
# Tests Firebase configuration and basic authentication flow

set -e  # Exit on error

echo "🔥 Firebase Authentication Validation"
echo "======================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:5173}"

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Helper functions
pass_test() {
    echo -e "${GREEN}✓ $1${NC}"
    PASSED=$((PASSED + 1))
}

fail_test() {
    echo -e "${RED}✗ $1${NC}"
    FAILED=$((FAILED + 1))
}

warn_test() {
    echo -e "${YELLOW}⚠ $1${NC}"
    WARNINGS=$((WARNINGS + 1))
}

info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Test 1: Backend Configuration
echo "📋 Test 1: Backend Firebase Configuration"
echo "-------------------------------------------"

cd backend-hormonia 2>/dev/null || {
    fail_test "Backend directory not found"
    exit 1
}

# Check if .env exists
if [ -f ".env" ]; then
    pass_test ".env file exists"

    # Check Firebase env vars
    if grep -q "FIREBASE_ADMIN_PROJECT_ID" .env && [ -n "$(grep FIREBASE_ADMIN_PROJECT_ID .env | cut -d'=' -f2)" ]; then
        pass_test "FIREBASE_ADMIN_PROJECT_ID configured"
    else
        fail_test "FIREBASE_ADMIN_PROJECT_ID not configured"
    fi

    if grep -q "FIREBASE_ADMIN_PRIVATE_KEY" .env && [ -n "$(grep FIREBASE_ADMIN_PRIVATE_KEY .env | cut -d'=' -f2)" ]; then
        pass_test "FIREBASE_ADMIN_PRIVATE_KEY configured"
    else
        fail_test "FIREBASE_ADMIN_PRIVATE_KEY not configured"
    fi

    if grep -q "FIREBASE_ADMIN_CLIENT_EMAIL" .env && [ -n "$(grep FIREBASE_ADMIN_CLIENT_EMAIL .env | cut -d'=' -f2)" ]; then
        pass_test "FIREBASE_ADMIN_CLIENT_EMAIL configured"
    else
        fail_test "FIREBASE_ADMIN_CLIENT_EMAIL not configured"
    fi
else
    fail_test ".env file not found"
    info "Copy .env.example to .env and configure Firebase credentials"
fi

echo ""

# Test 2: Backend Health Check
echo "📋 Test 2: Backend Health Check"
echo "-------------------------------------------"

# Check if backend is running
if curl -f -s "$BACKEND_URL/health" > /dev/null 2>&1; then
    pass_test "Backend is running at $BACKEND_URL"

    # Get health status
    HEALTH_RESPONSE=$(curl -s "$BACKEND_URL/health")
    if echo "$HEALTH_RESPONSE" | grep -q '"status":"healthy"'; then
        pass_test "Backend health status is healthy"
    else
        warn_test "Backend health status may have issues"
        info "Response: $HEALTH_RESPONSE"
    fi
else
    fail_test "Backend is not running at $BACKEND_URL"
    info "Start backend with: cd backend-hormonia && uvicorn app.main:app --reload"
fi

echo ""

# Test 3: Authentication Endpoint Tests
echo "📋 Test 3: Authentication Endpoints"
echo "-------------------------------------------"

# Test 3.1: Missing token returns 401
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/api/v1/auth/me" 2>/dev/null || echo "000")
if [ "$STATUS" -eq 401 ] || [ "$STATUS" -eq 403 ]; then
    pass_test "Missing token correctly returns 401/403"
else
    if [ "$STATUS" -eq 000 ]; then
        fail_test "Cannot reach backend (connection failed)"
    else
        warn_test "Expected 401, got $STATUS for missing token"
    fi
fi

# Test 3.2: Invalid token returns 401
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/api/v1/auth/me" \
    -H "Authorization: Bearer invalid-token-12345" 2>/dev/null || echo "000")
if [ "$STATUS" -eq 401 ] || [ "$STATUS" -eq 403 ]; then
    pass_test "Invalid token correctly returns 401/403"
else
    if [ "$STATUS" -eq 000 ]; then
        fail_test "Cannot reach backend"
    else
        warn_test "Expected 401, got $STATUS for invalid token"
    fi
fi

# Test 3.3: Login endpoint is deprecated (should return 410)
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/api/v1/auth/login" \
    -X POST -H "Content-Type: application/json" \
    -d '{"username":"test","password":"test"}' 2>/dev/null || echo "000")
if [ "$STATUS" -eq 410 ]; then
    pass_test "Local login correctly disabled (410 Gone)"
else
    warn_test "Local login endpoint status: $STATUS (expected 410)"
fi

echo ""

# Test 4: CORS Configuration
echo "📋 Test 4: CORS Configuration"
echo "-------------------------------------------"

# Test allowed origin
RESPONSE=$(curl -s -I -H "Origin: http://localhost:5173" "$BACKEND_URL/health" 2>/dev/null)
if echo "$RESPONSE" | grep -qi "Access-Control-Allow-Origin"; then
    pass_test "CORS headers present"

    if echo "$RESPONSE" | grep -q "Access-Control-Allow-Origin: http://localhost:5173"; then
        pass_test "CORS allows localhost:5173"
    elif echo "$RESPONSE" | grep -q "Access-Control-Allow-Origin: \*"; then
        warn_test "CORS allows all origins (not recommended for production)"
    else
        warn_test "CORS configured but may not allow localhost:5173"
    fi
else
    warn_test "CORS headers not found (check ALLOWED_ORIGINS in .env)"
fi

echo ""

# Test 5: Frontend Configuration
echo "📋 Test 5: Frontend Firebase Configuration"
echo "-------------------------------------------"

cd ../frontend-hormonia 2>/dev/null || {
    warn_test "Frontend directory not found"
}

if [ -d "../frontend-hormonia" ]; then
    cd ../frontend-hormonia

    if [ -f ".env" ]; then
        pass_test "Frontend .env file exists"

        # Check frontend Firebase vars
        if grep -q "VITE_FIREBASE_API_KEY" .env && [ -n "$(grep VITE_FIREBASE_API_KEY .env | cut -d'=' -f2)" ]; then
            pass_test "VITE_FIREBASE_API_KEY configured"
        else
            fail_test "VITE_FIREBASE_API_KEY not configured"
        fi

        if grep -q "VITE_FIREBASE_PROJECT_ID" .env && [ -n "$(grep VITE_FIREBASE_PROJECT_ID .env | cut -d'=' -f2)" ]; then
            pass_test "VITE_FIREBASE_PROJECT_ID configured"
        else
            fail_test "VITE_FIREBASE_PROJECT_ID not configured"
        fi

        if grep -q "VITE_FIREBASE_AUTH_DOMAIN" .env && [ -n "$(grep VITE_FIREBASE_AUTH_DOMAIN .env | cut -d'=' -f2)" ]; then
            pass_test "VITE_FIREBASE_AUTH_DOMAIN configured"
        else
            fail_test "VITE_FIREBASE_AUTH_DOMAIN not configured"
        fi
    else
        fail_test "Frontend .env file not found"
        info "Copy .env.example to .env and configure Firebase credentials"
    fi
fi

echo ""

# Test 6: File Structure
echo "📋 Test 6: Required Files Exist"
echo "-------------------------------------------"

cd ..

# Backend files
if [ -f "backend-hormonia/app/services/firebase_auth_service.py" ]; then
    pass_test "Firebase auth service exists"
else
    fail_test "Firebase auth service not found"
fi

if [ -f "backend-hormonia/app/dependencies/auth_dependencies.py" ]; then
    pass_test "Auth dependencies exist"
else
    fail_test "Auth dependencies not found"
fi

# Frontend files
if [ -f "frontend-hormonia/src/lib/firebase-client.ts" ]; then
    pass_test "Firebase client exists"
else
    fail_test "Firebase client not found"
fi

if [ -f "frontend-hormonia/contexts/MedicoAuthContext.tsx" ]; then
    pass_test "MedicoAuthContext exists"
else
    fail_test "MedicoAuthContext not found"
fi

echo ""

# Test 7: Python Dependencies
echo "📋 Test 7: Python Dependencies"
echo "-------------------------------------------"

cd backend-hormonia

if command -v python3 &> /dev/null; then
    pass_test "Python3 is installed"

    # Check if firebase-admin is installed
    if python3 -c "import firebase_admin" 2>/dev/null; then
        pass_test "firebase-admin package installed"
    else
        fail_test "firebase-admin package not installed"
        info "Install with: pip install firebase-admin"
    fi

    # Check if fastapi is installed
    if python3 -c "import fastapi" 2>/dev/null; then
        pass_test "fastapi package installed"
    else
        fail_test "fastapi package not installed"
        info "Install with: pip install -r requirements.txt"
    fi
else
    fail_test "Python3 is not installed"
fi

cd ..

echo ""

# Summary
echo "======================================"
echo "📊 Test Summary"
echo "======================================"
echo -e "${GREEN}Passed:  $PASSED${NC}"
echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
echo -e "${RED}Failed:  $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All critical tests passed!${NC}"
    echo ""
    echo "🚀 Next Steps:"
    echo "1. Run backend: cd backend-hormonia && uvicorn app.main:app --reload"
    echo "2. Run frontend: cd frontend-hormonia && npm run dev"
    echo "3. Test login: Open http://localhost:5173/medico/login"
    exit 0
else
    echo -e "${RED}❌ Some tests failed. Please fix the issues above.${NC}"
    echo ""
    echo "📚 Common Fixes:"
    echo "1. Configure .env files (copy from .env.example)"
    echo "2. Install dependencies: pip install -r requirements.txt"
    echo "3. Start backend: uvicorn app.main:app --reload"
    echo "4. Check Firebase credentials in .env"
    exit 1
fi
