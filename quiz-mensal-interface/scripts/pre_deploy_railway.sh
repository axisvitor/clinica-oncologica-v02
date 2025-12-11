#!/bin/bash
# =============================================================================
# PRE-DEPLOY VALIDATION SCRIPT FOR RAILWAY - Quiz Mensal Interface
# =============================================================================
# Run this script locally before deploying to Railway to validate configuration
# Usage: ./scripts/pre_deploy_railway.sh
# =============================================================================

set -e

echo "=============================================="
echo "🚀 Quiz Interface Railway Pre-Deploy Validation"
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

# Check Next.js config
check_file "next.config.mjs" "next.config.mjs" || check_file "next.config.js" "next.config.js" || ((ERRORS++))

echo ""
echo "🐳 Checking Docker configuration..."
echo "---------------------------------------------"

# Check Dockerfile uses correct base image
if grep -q "FROM node:20-alpine" Dockerfile; then
    echo -e "${GREEN}✓${NC} Dockerfile uses Node 20 Alpine"
else
    echo -e "${YELLOW}⚠${NC} Dockerfile may not use Node 20 Alpine"
    ((WARNINGS++))
fi

# Check for multi-stage build
STAGES=$(grep -c "^FROM" Dockerfile 2>/dev/null || echo "0")
if [ "$STAGES" -ge 2 ]; then
    echo -e "${GREEN}✓${NC} Dockerfile uses multi-stage build ($STAGES stages)"
else
    echo -e "${YELLOW}⚠${NC} Dockerfile should use multi-stage build"
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

# Check for standalone output usage
if grep -q "standalone" Dockerfile; then
    echo -e "${GREEN}✓${NC} Dockerfile uses Next.js standalone output"
else
    echo -e "${YELLOW}⚠${NC} Dockerfile may not use standalone output (larger image)"
    ((WARNINGS++))
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

    # Check that Dockerfile is NOT excluded (CRITICAL!)
    if grep -q "^Dockerfile\*$" .dockerignore 2>/dev/null; then
        echo -e "${RED}✗${NC} Dockerfile excluded - Railway build will fail!"
        ((ERRORS++))
    else
        echo -e "${GREEN}✓${NC} Dockerfile NOT excluded"
    fi

    if grep -q "\.next" .dockerignore; then
        echo -e "${GREEN}✓${NC} .next build cache excluded"
    else
        echo -e "${YELLOW}⚠${NC} .next should be excluded from build context"
        ((WARNINGS++))
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

# Check for Next.js
if grep -q '"next"' package.json; then
    echo -e "${GREEN}✓${NC} Next.js dependency present"
else
    echo -e "${RED}✗${NC} Next.js dependency missing"
    ((ERRORS++))
fi

# Check for React
if grep -q '"react"' package.json; then
    echo -e "${GREEN}✓${NC} React dependency present"
else
    echo -e "${RED}✗${NC} React dependency missing"
    ((ERRORS++))
fi

echo ""
echo "⚙️  Checking Next.js configuration..."
echo "---------------------------------------------"

CONFIG_FILE=""
if [ -f "next.config.mjs" ]; then
    CONFIG_FILE="next.config.mjs"
elif [ -f "next.config.js" ]; then
    CONFIG_FILE="next.config.js"
fi

if [ -n "$CONFIG_FILE" ]; then
    # Check for standalone output
    if grep -q "output.*standalone" "$CONFIG_FILE"; then
        echo -e "${GREEN}✓${NC} Next.js standalone output enabled"
    else
        echo -e "${YELLOW}⚠${NC} Next.js standalone output not enabled (larger image)"
        ((WARNINGS++))
    fi

    # Check for compression
    if grep -q "compress.*true" "$CONFIG_FILE"; then
        echo -e "${GREEN}✓${NC} Compression enabled"
    else
        echo -e "${YELLOW}⚠${NC} Compression may not be enabled"
        ((WARNINGS++))
    fi

    # Check for poweredByHeader
    if grep -q "poweredByHeader.*false" "$CONFIG_FILE"; then
        echo -e "${GREEN}✓${NC} X-Powered-By header disabled (security)"
    else
        echo -e "${YELLOW}⚠${NC} X-Powered-By header should be disabled"
        ((WARNINGS++))
    fi
fi

echo ""
echo "🏥 Checking health endpoint..."
echo "---------------------------------------------"

# Check for health API route
if [ -d "app/api/health" ] || [ -f "app/api/health/route.ts" ] || [ -f "pages/api/health.ts" ] || [ -f "pages/api/health.js" ]; then
    echo -e "${GREEN}✓${NC} Health endpoint found"
else
    echo -e "${YELLOW}⚠${NC} Health endpoint not found (required for Railway health checks)"
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
    echo "   - NEXT_PUBLIC_API_URL"
    echo "   - NEXT_PUBLIC_SUPABASE_URL"
    echo "   - NEXT_PUBLIC_SUPABASE_ANON_KEY"
    echo "   - QUIZ_SESSION_SECRET (min 32 chars)"
    echo "2. Run: railway up"
    echo ""
    exit 0
fi
