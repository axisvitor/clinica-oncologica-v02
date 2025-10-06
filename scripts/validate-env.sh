#!/bin/bash
# ============================================================================
# ENV VALIDATION SCRIPT - Railway Deploy Checklist
# ============================================================================
# Validates environment variables before Railway deployment
# Usage: ./scripts/validate-env.sh [frontend|backend]
# ============================================================================

set -e

SERVICE=${1:-"both"}
ERRORS=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔍 Validating Environment Variables for Railway Deploy"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ============================================================================
# FRONTEND VALIDATION
# ============================================================================
validate_frontend() {
  echo ""
  echo "📦 FRONTEND Variables (frontend-hormonia/.env)"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  if [ ! -f "frontend-hormonia/.env" ]; then
    echo -e "${RED}❌ frontend-hormonia/.env not found${NC}"
    ERRORS=$((ERRORS+1))
    return
  fi

  source frontend-hormonia/.env

  # Check VITE_API_URL format
  if [[ $VITE_API_URL =~ ^https:// ]]; then
    echo -e "${GREEN}✅${NC} VITE_API_URL: $VITE_API_URL"
  else
    echo -e "${RED}❌ VITE_API_URL missing https://${NC}"
    echo "   Current: $VITE_API_URL"
    echo "   Expected: https://clinica-oncologica-v02-production.up.railway.app/api/v1"
    ERRORS=$((ERRORS+1))
  fi

  # Check VITE_WS_URL format
  if [[ $VITE_WS_URL =~ ^wss:// ]]; then
    echo -e "${GREEN}✅${NC} VITE_WS_URL: $VITE_WS_URL"
  else
    echo -e "${RED}❌ VITE_WS_URL missing wss://${NC}"
    echo "   Current: $VITE_WS_URL"
    echo "   Expected: wss://clinica-oncologica-v02-production.up.railway.app/ws/connect"
    ERRORS=$((ERRORS+1))
  fi

  # Check VITE_WS_BASE_URL format
  if [[ $VITE_WS_BASE_URL =~ ^wss:// ]]; then
    echo -e "${GREEN}✅${NC} VITE_WS_BASE_URL: $VITE_WS_BASE_URL"
  else
    echo -e "${RED}❌ VITE_WS_BASE_URL missing wss://${NC}"
    echo "   Current: $VITE_WS_BASE_URL"
    ERRORS=$((ERRORS+1))
  fi

  # Check Firebase enabled
  if [ "$VITE_FIREBASE_ENABLED" = "true" ]; then
    echo -e "${GREEN}✅${NC} Firebase enabled"
  else
    echo -e "${YELLOW}⚠️${NC}  Firebase disabled (expected: true)"
  fi

  # Check Supabase disabled
  if [ "$VITE_SUPABASE_AUTH_ENABLED" = "false" ]; then
    echo -e "${GREEN}✅${NC} Supabase auth disabled (correct)"
  else
    echo -e "${YELLOW}⚠️${NC}  Supabase auth enabled (should be false)"
  fi
}

# ============================================================================
# BACKEND VALIDATION
# ============================================================================
validate_backend() {
  echo ""
  echo "🔧 BACKEND Variables (backend-hormonia/.env)"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  if [ ! -f "backend-hormonia/.env" ]; then
    echo -e "${RED}❌ backend-hormonia/.env not found${NC}"
    ERRORS=$((ERRORS+1))
    return
  fi

  source backend-hormonia/.env

  # Check DATABASE_URL SSL mode
  if [[ $DATABASE_URL =~ sslmode=require ]]; then
    echo -e "${GREEN}✅${NC} DATABASE_URL has sslmode=require"
  else
    echo -e "${RED}❌ DATABASE_URL missing ?sslmode=require${NC}"
    echo "   Current: ${DATABASE_URL%\?*}"
    echo "   Add: ?sslmode=require"
    echo "   Fix prevents: psycopg.OperationalError: SSL connection closed"
    ERRORS=$((ERRORS+1))
  fi

  # Check ALLOWED_ORIGINS
  if [ ! -z "$ALLOWED_ORIGINS" ]; then
    echo -e "${GREEN}✅${NC} ALLOWED_ORIGINS configured"
    if [[ $ALLOWED_ORIGINS =~ frontend-production.*railway\.app ]]; then
      echo -e "${GREEN}✅${NC} Contains Railway frontend domain"
    else
      echo -e "${YELLOW}⚠️${NC}  Missing Railway frontend domain"
    fi
  else
    echo -e "${RED}❌ ALLOWED_ORIGINS is empty${NC}"
    ERRORS=$((ERRORS+1))
  fi

  # Check Firebase block public domains
  if [ "$FIREBASE_BLOCK_PUBLIC_DOMAINS" = "false" ]; then
    echo -e "${GREEN}✅${NC} FIREBASE_BLOCK_PUBLIC_DOMAINS=false (Railway requirement)"
  else
    echo -e "${YELLOW}⚠️${NC}  FIREBASE_BLOCK_PUBLIC_DOMAINS should be false for Railway"
  fi

  # Check environment
  if [ "$ENVIRONMENT" = "production" ]; then
    echo -e "${GREEN}✅${NC} Environment: production"
  else
    echo -e "${YELLOW}⚠️${NC}  Environment: $ENVIRONMENT (expected: production)"
  fi
}

# ============================================================================
# RAILWAY SPECIFIC CHECKS
# ============================================================================
validate_railway_readiness() {
  echo ""
  echo "🚂 Railway Deployment Readiness"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  # Check git status
  if [ -z "$(git status --porcelain)" ]; then
    echo -e "${GREEN}✅${NC} Git working tree clean"
  else
    echo -e "${YELLOW}⚠️${NC}  Uncommitted changes detected"
    git status --short
  fi

  # Check latest commit
  LATEST_COMMIT=$(git log -1 --oneline)
  echo -e "${GREEN}✅${NC} Latest commit: $LATEST_COMMIT"

  # Check branch
  CURRENT_BRANCH=$(git branch --show-current)
  echo -e "${GREEN}✅${NC} Current branch: $CURRENT_BRANCH"
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================
case $SERVICE in
  frontend)
    validate_frontend
    ;;
  backend)
    validate_backend
    ;;
  both)
    validate_frontend
    validate_backend
    validate_railway_readiness
    ;;
  *)
    echo "Usage: $0 [frontend|backend|both]"
    exit 1
    ;;
esac

# ============================================================================
# SUMMARY
# ============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $ERRORS -eq 0 ]; then
  echo -e "${GREEN}✅ All validations passed!${NC}"
  echo "   Safe to deploy to Railway"
  exit 0
else
  echo -e "${RED}❌ $ERRORS validation error(s) found${NC}"
  echo "   Fix errors before deploying to Railway"
  echo ""
  echo "📚 Documentation:"
  echo "   docs/deployment/RAILWAY_ENV_VARS_CORRECT.md"
  exit 1
fi
