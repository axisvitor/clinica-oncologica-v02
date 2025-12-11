#!/bin/bash
# =============================================================================
# PRE-DEPLOY VALIDATION SCRIPT FOR RAILWAY - Frontend Hormonia
# =============================================================================
# Run this script locally before deploying to Railway to validate configuration
# Usage: ./scripts/pre_deploy_railway.sh
# =============================================================================

set -e

echo "=============================================="
echo "🚀 Frontend Railway Pre-Deploy Validation"
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

echo ""
echo "📁 Checking required files..."
echo "---------------------------------------------"

# Check Dockerfile
check_file "Dockerfile" "Dockerfile" || ((ERRORS++))

# Check Railway config
check_file "railway.toml" "railway.toml" || ((ERRORS++))

# Check package.json
check_file "package.json" "package.json" || ((ERRORS++))

# Check .dockerignore
check_file ".dockerignore" ".dockerignore" || ((WARNINGS++))

echo ""
echo "🐳 Checking Docker configuration..."
echo "---------------------------------------------"

# Check Dockerfile uses correct base image
if grep -q "FROM node:18-alpine" Dockerfile; then
    echo -e "${GREEN}✓${NC} Dockerfile uses Node 18 Alpine"
else
    echo -e "${YELLOW}⚠${NC} Dockerfile may not use Node 18 Alpine"
    ((WARNINGS++))
fi

# Check for nginx in production stage
if grep -q "nginx:alpine" Dockerfile; then
    echo -e "${GREEN}✓${NC} Dockerfile uses nginx for production"
else
    echo -e "${YELLOW}⚠${NC} Dockerfile may not use nginx"
    ((WARNINGS++))
fi

# Check for HEALTHCHECK
if grep -q "HEALTHCHECK" Dockerfile; then
    echo -e "${GREEN}✓${NC} Dockerfile has HEALTHCHECK"
else
    echo -e "${YELLOW}⚠${NC} Dockerfile missing HEALTHCHECK"
    ((WARNINGS++))
fi

# Check for non-root user
if grep -q "USER" Dockerfile; then
    echo -e "${GREEN}✓${NC} Dockerfile uses non-root user"
else
    echo -e "${RED}✗${NC} Dockerfile should use non-root user"
    ((ERRORS++))
fi

# Check for dynamic PORT
if grep -q '\${PORT' Dockerfile || grep -q 'envsubst' Dockerfile; then
    echo -e "${GREEN}✓${NC} Dockerfile supports dynamic PORT"
else
    echo -e "${RED}✗${NC} Dockerfile should support dynamic PORT (Railway sets PORT env var)"
    ((ERRORS++))
fi

echo ""
echo "📝 Checking .dockerignore..."
echo "---------------------------------------------"

if [ -f ".dockerignore" ]; then
    # Check critical exclusions
    if grep -q "node_modules" .dockerignore; then
        echo -e "${GREEN}✓${NC} node_modules excluded from Docker build"
    else
        echo -e "${RED}✗${NC} node_modules NOT excluded - will bloat image!"
        ((ERRORS++))
    fi

    if grep -q "\.env" .dockerignore; then
        echo -e "${GREEN}✓${NC} .env excluded from Docker build"
    else
        echo -e "${RED}✗${NC} .env NOT excluded - security risk!"
        ((ERRORS++))
    fi

    # Check that Dockerfile is NOT excluded
    if grep -q "^Dockerfile\*$" .dockerignore 2>/dev/null; then
        echo -e "${RED}✗${NC} Dockerfile excluded - Railway build will fail!"
        ((ERRORS++))
    else
        echo -e "${GREEN}✓${NC} Dockerfile NOT excluded"
    fi
fi

echo ""
echo "🔐 Checking security configuration..."
echo "---------------------------------------------"

# Check .env is in .gitignore
if [ -f ".gitignore" ] && grep -q "\.env" .gitignore; then
    echo -e "${GREEN}✓${NC} .env is in .gitignore"
else
    echo -e "${YELLOW}⚠${NC} .env should be in .gitignore"
    ((WARNINGS++))
fi

echo ""
echo "📦 Checking package.json..."
echo "---------------------------------------------"

# Check for build script
if grep -q '"build"' package.json; then
    echo -e "${GREEN}✓${NC} build script exists"
else
    echo -e "${RED}✗${NC} build script missing"
    ((ERRORS++))
fi

# Check for React
if grep -q '"react"' package.json; then
    echo -e "${GREEN}✓${NC} React dependency present"
else
    echo -e "${RED}✗${NC} React dependency missing"
    ((ERRORS++))
fi

# Check for Vite
if grep -q '"vite"' package.json; then
    echo -e "${GREEN}✓${NC} Vite build tool present"
else
    echo -e "${YELLOW}⚠${NC} Vite not found (using different build tool?)"
    ((WARNINGS++))
fi

echo ""
echo "🌐 Checking Vite configuration..."
echo "---------------------------------------------"

if [ -f "vite.config.ts" ] || [ -f "vite.config.js" ]; then
    echo -e "${GREEN}✓${NC} Vite config file exists"
else
    echo -e "${YELLOW}⚠${NC} Vite config file not found"
    ((WARNINGS++))
fi

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
    echo "1. Ensure Railway environment variables are set:"
    echo "   - VITE_API_URL"
    echo "   - VITE_SUPABASE_URL"
    echo "   - VITE_SUPABASE_ANON_KEY"
    echo "2. Run: railway up"
    echo ""
    exit 0
fi
