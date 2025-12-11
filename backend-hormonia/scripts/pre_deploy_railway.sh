#!/bin/bash
# =============================================================================
# PRE-DEPLOY VALIDATION SCRIPT FOR RAILWAY
# =============================================================================
# Run this script locally before deploying to Railway to validate configuration
# Usage: ./scripts/pre_deploy_railway.sh
# =============================================================================

set -e

echo "=============================================="
echo "🚀 Railway Pre-Deploy Validation"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

# Function to check if file exists
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} $2 exists"
        return 0
    else
        echo -e "${RED}✗${NC} $2 missing: $1"
        return 1
    fi
}

# Function to check if command exists
check_command() {
    if command -v "$1" &> /dev/null; then
        echo -e "${GREEN}✓${NC} $1 is installed"
        return 0
    else
        echo -e "${YELLOW}⚠${NC} $1 is not installed (optional)"
        return 1
    fi
}

echo ""
echo "📁 Checking required files..."
echo "---------------------------------------------"

# Check Dockerfiles
check_file "Dockerfile" "Main Dockerfile" || ((ERRORS++))
check_file "Dockerfile.worker" "Worker Dockerfile" || ((ERRORS++))
check_file "Dockerfile.beat" "Beat Dockerfile" || ((ERRORS++))

# Check Railway configs
check_file "railway.toml" "Main railway.toml" || ((ERRORS++))
check_file "worker/railway.toml" "Worker railway.toml" || ((WARNINGS++))
check_file "beat/railway.toml" "Beat railway.toml" || ((WARNINGS++))

# Check scripts
check_file "scripts/entrypoint.sh" "Entrypoint script" || ((ERRORS++))
check_file "scripts/healthcheck.sh" "Healthcheck script" || ((ERRORS++))

# Check requirements
check_file "requirements.txt" "Requirements file" || ((ERRORS++))

# Check env template
check_file ".env.railway.template" "Railway env template" || ((WARNINGS++))

echo ""
echo "🐍 Checking Python syntax..."
echo "---------------------------------------------"

# Check Python syntax
if command -v python3 &> /dev/null; then
    # Check main app module
    if python3 -m py_compile app/main.py 2>/dev/null; then
        echo -e "${GREEN}✓${NC} app/main.py syntax OK"
    else
        echo -e "${RED}✗${NC} app/main.py has syntax errors"
        ((ERRORS++))
    fi

    # Check config module
    if python3 -m py_compile app/config/__init__.py 2>/dev/null; then
        echo -e "${GREEN}✓${NC} app/config syntax OK"
    else
        echo -e "${RED}✗${NC} app/config has syntax errors"
        ((ERRORS++))
    fi
else
    echo -e "${YELLOW}⚠${NC} Python3 not found, skipping syntax check"
    ((WARNINGS++))
fi

echo ""
echo "🐳 Checking Docker configuration..."
echo "---------------------------------------------"

# Check Dockerfile syntax (basic)
if grep -q "FROM python:3.13" Dockerfile; then
    echo -e "${GREEN}✓${NC} Dockerfile uses Python 3.13"
else
    echo -e "${YELLOW}⚠${NC} Dockerfile may not use Python 3.13"
    ((WARNINGS++))
fi

if grep -q "HEALTHCHECK" Dockerfile; then
    echo -e "${GREEN}✓${NC} Dockerfile has HEALTHCHECK"
else
    echo -e "${YELLOW}⚠${NC} Dockerfile missing HEALTHCHECK"
    ((WARNINGS++))
fi

if grep -q "USER appuser" Dockerfile; then
    echo -e "${GREEN}✓${NC} Dockerfile uses non-root user"
else
    echo -e "${RED}✗${NC} Dockerfile should use non-root user"
    ((ERRORS++))
fi

echo ""
echo "📝 Checking .dockerignore..."
echo "---------------------------------------------"

if check_file ".dockerignore" ".dockerignore"; then
    # Check critical exclusions
    if grep -q "venv/" .dockerignore; then
        echo -e "${GREEN}✓${NC} venv excluded from Docker build"
    else
        echo -e "${RED}✗${NC} venv NOT excluded - will bloat image!"
        ((ERRORS++))
    fi

    if grep -q "^\.env$" .dockerignore; then
        echo -e "${GREEN}✓${NC} .env excluded from Docker build"
    else
        echo -e "${RED}✗${NC} .env NOT excluded - security risk!"
        ((ERRORS++))
    fi

    # Check that Dockerfile is NOT excluded
    if grep -q "^Dockerfile\*$" .dockerignore; then
        echo -e "${RED}✗${NC} Dockerfile excluded - Railway build will fail!"
        ((ERRORS++))
    else
        echo -e "${GREEN}✓${NC} Dockerfile NOT excluded"
    fi
fi

echo ""
echo "🔐 Checking security configuration..."
echo "---------------------------------------------"

# Check for hardcoded secrets in code (basic check)
# Look for actual hardcoded secret values (not validation checks)
SECRETS_FOUND=$(grep -rn "SECRET_KEY.*=.*['\"].*['\"]" app/ --include="*.py" 2>/dev/null | grep -v "os\.\|environ\|getenv\|settings\.\|CHANGE_THIS\|REPLACE\|example\|template" | head -1)
if [ -n "$SECRETS_FOUND" ]; then
    echo -e "${YELLOW}⚠${NC} Possible hardcoded secrets found in code"
    echo "    $SECRETS_FOUND"
    ((WARNINGS++))
else
    echo -e "${GREEN}✓${NC} No hardcoded secrets found in code"
fi

# Check .env is in .gitignore
if grep -q "^\.env$" .gitignore 2>/dev/null; then
    echo -e "${GREEN}✓${NC} .env is in .gitignore"
else
    echo -e "${RED}✗${NC} .env should be in .gitignore"
    ((ERRORS++))
fi

echo ""
echo "📦 Checking dependencies..."
echo "---------------------------------------------"

# Check critical dependencies
REQUIRED_DEPS=("fastapi" "uvicorn" "celery" "redis" "sqlalchemy" "psycopg")
for dep in "${REQUIRED_DEPS[@]}"; do
    if grep -qi "$dep" requirements.txt; then
        echo -e "${GREEN}✓${NC} $dep in requirements.txt"
    else
        echo -e "${RED}✗${NC} $dep missing from requirements.txt"
        ((ERRORS++))
    fi
done

echo ""
echo "=============================================="
echo "📊 Validation Summary"
echo "=============================================="
echo -e "Errors:   ${RED}$ERRORS${NC}"
echo -e "Warnings: ${YELLOW}$WARNINGS${NC}"
echo ""

if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}❌ Pre-deploy validation FAILED${NC}"
    echo "Please fix the errors above before deploying."
    exit 1
else
    if [ $WARNINGS -gt 0 ]; then
        echo -e "${YELLOW}⚠️  Pre-deploy validation PASSED with warnings${NC}"
    else
        echo -e "${GREEN}✅ Pre-deploy validation PASSED${NC}"
    fi
    echo ""
    echo "Next steps:"
    echo "1. Ensure Railway environment variables are set"
    echo "2. Run: railway up"
    echo ""
    exit 0
fi
