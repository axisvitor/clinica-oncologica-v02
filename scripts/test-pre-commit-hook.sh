#!/bin/bash
# Test script for pre-commit hook validation
# Created: 2025-10-09
# Purpose: Comprehensive testing of pre-commit security checks

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Testing pre-commit hook scenarios...${NC}"
echo ""

# Track test results
TESTS_PASSED=0
TESTS_FAILED=0

# ============================================================================
# Setup test environment
# ============================================================================
TEST_DIR=$(mktemp -d)
ORIGINAL_DIR=$(pwd)

cleanup() {
    cd "$ORIGINAL_DIR"
    rm -rf "$TEST_DIR"
}

trap cleanup EXIT

echo "Setting up test repository in $TEST_DIR"
cd "$TEST_DIR"

# Initialize git repo
git init -q
git config user.email "test@example.com"
git config user.name "Test User"

# Copy pre-commit script
mkdir -p scripts
cp "$ORIGINAL_DIR/scripts/pre-commit-check.sh" scripts/
chmod +x scripts/pre-commit-check.sh

# Install hook
mkdir -p .git/hooks
cp scripts/pre-commit-check.sh .git/hooks/pre-commit

# ============================================================================
# Test 1: .env file detection
# ============================================================================
echo -e "${BLUE}Test 1: .env file detection${NC}"

echo "TEST_VAR=value" > .env
git add .env

if git commit -m "test" 2>&1 | grep -q "ERROR: .env file"; then
    echo -e "${GREEN}✅ PASS: .env file correctly blocked${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAIL: .env file not detected${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

git reset HEAD .env
rm .env
echo ""

# ============================================================================
# Test 2: Hardcoded API key detection
# ============================================================================
echo -e "${BLUE}Test 2: Hardcoded API key detection${NC}"

cat > config.js << 'EOF'
const config = {
  api_key: "sk_test_1234567890abcdefghijklmnop"
};
EOF

git add config.js

if git commit -m "test" 2>&1 | grep -q "WARNING: Possible hardcoded secret"; then
    echo -e "${GREEN}✅ PASS: Hardcoded API key correctly detected${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAIL: Hardcoded API key not detected${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

git reset HEAD config.js
rm config.js
echo ""

# ============================================================================
# Test 3: localStorage token usage detection
# ============================================================================
echo -e "${BLUE}Test 3: localStorage token usage detection${NC}"

mkdir -p frontend-hormonia/src
cat > frontend-hormonia/src/auth.js << 'EOF'
function storeToken(token) {
  localStorage.setItem('auth_token', token);
}
EOF

git add frontend-hormonia/src/auth.js

if git commit -m "test" 2>&1 | grep -q "ERROR: Insecure token storage"; then
    echo -e "${GREEN}✅ PASS: localStorage token usage correctly blocked${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAIL: localStorage token usage not detected${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

git reset HEAD frontend-hormonia/src/auth.js
rm -rf frontend-hormonia
echo ""

# ============================================================================
# Test 4: AWS credentials detection
# ============================================================================
echo -e "${BLUE}Test 4: AWS credentials detection${NC}"

cat > aws-config.js << 'EOF'
const awsConfig = {
  accessKeyId: "AKIAIOSFODNN7EXAMPLE"
};
EOF

git add aws-config.js

if git commit -m "test" 2>&1 | grep -q "ERROR: Cloud provider credentials"; then
    echo -e "${GREEN}✅ PASS: AWS credentials correctly detected${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAIL: AWS credentials not detected${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

git reset HEAD aws-config.js
rm aws-config.js
echo ""

# ============================================================================
# Test 5: Private key detection
# ============================================================================
echo -e "${BLUE}Test 5: Private key detection${NC}"

cat > private-key.pem << 'EOF'
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA1234567890abcdef
-----END RSA PRIVATE KEY-----
EOF

git add private-key.pem

if git commit -m "test" 2>&1 | grep -q "ERROR: Private key detected"; then
    echo -e "${GREEN}✅ PASS: Private key correctly detected${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAIL: Private key not detected${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

git reset HEAD private-key.pem
rm private-key.pem
echo ""

# ============================================================================
# Test 6: Database connection string detection
# ============================================================================
echo -e "${BLUE}Test 6: Database connection string detection${NC}"

cat > db-config.js << 'EOF'
const dbUrl = "postgres://user:password@localhost:5432/db";
EOF

git add db-config.js

if git commit -m "test" 2>&1 | grep -q "WARNING: Database connection string"; then
    echo -e "${GREEN}✅ PASS: Database connection string correctly detected${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAIL: Database connection string not detected${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

git reset HEAD db-config.js
rm db-config.js
echo ""

# ============================================================================
# Test 7: Safe commit (should pass all checks)
# ============================================================================
echo -e "${BLUE}Test 7: Safe commit (should pass)${NC}"

cat > safe-file.js << 'EOF'
// Safe configuration using environment variables
const config = {
  apiUrl: process.env.API_URL,
  databaseUrl: process.env.DATABASE_URL
};

export default config;
EOF

git add safe-file.js

if git commit -m "Add safe configuration" 2>&1 | grep -q "All pre-commit checks passed"; then
    echo -e "${GREEN}✅ PASS: Safe commit correctly allowed${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAIL: Safe commit was blocked${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo ""

# ============================================================================
# Test Results Summary
# ============================================================================
TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}Test Results:${NC}"
echo ""
echo "Total tests: $TOTAL_TESTS"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    echo ""
    exit 0
else
    echo -e "${RED}❌ Some tests failed!${NC}"
    echo ""
    exit 1
fi
