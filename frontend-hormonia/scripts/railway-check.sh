#!/bin/bash

###############################################################################
# Railway Environment Variables Checker (Production)
#
# This script checks if the frontend is properly configured in Railway
# by testing critical endpoints and environment variables.
#
# Usage:
#   chmod +x scripts/railway-check.sh
#   ./scripts/railway-check.sh
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
FRONTEND_URL="https://frontend-production-c59bc.up.railway.app"
BACKEND_URL="https://clinica-oncologica-v02-production.up.railway.app"

echo -e "${BLUE}🔍 Checking Railway Deployment Status...${NC}\n"

# Function to check HTTP endpoint
check_endpoint() {
  local url=$1
  local description=$2
  
  echo -e "${BLUE}Checking: ${description}${NC}"
  echo -e "${BLUE}URL: ${url}${NC}"
  
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$url" || echo "000")
  
  if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ Status: ${HTTP_CODE} OK${NC}\n"
    return 0
  elif [ "$HTTP_CODE" = "000" ]; then
    echo -e "${RED}❌ Status: Connection failed${NC}\n"
    return 1
  else
    echo -e "${YELLOW}⚠️  Status: ${HTTP_CODE}${NC}\n"
    return 1
  fi
}

# Function to check if JavaScript is loading
check_javascript() {
  local url=$1
  
  echo -e "${BLUE}Checking: JavaScript Loading${NC}"
  echo -e "${BLUE}URL: ${url}${NC}"
  
  CONTENT=$(curl -s "$url")
  
  if echo "$CONTENT" | grep -q "main.*\.js"; then
    echo -e "${GREEN}✅ JavaScript bundle found${NC}\n"
    return 0
  else
    echo -e "${RED}❌ JavaScript bundle not found${NC}\n"
    return 1
  fi
}

# Check Backend Health
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Backend API Check${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

check_endpoint "${BACKEND_URL}/api/v2/health" "Backend Health Endpoint"
BACKEND_STATUS=$?

# Check Frontend
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Frontend Check${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

check_endpoint "${FRONTEND_URL}" "Frontend Root"
FRONTEND_STATUS=$?

check_javascript "${FRONTEND_URL}"
JS_STATUS=$?

# Check if backend is reachable from frontend perspective
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Cross-Origin Check (CORS)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

echo -e "${BLUE}Checking: CORS Headers${NC}"
CORS_HEADERS=$(curl -s -I -H "Origin: ${FRONTEND_URL}" "${BACKEND_URL}/api/v2/health" | grep -i "access-control-allow-origin" || echo "")

if [ -n "$CORS_HEADERS" ]; then
  echo -e "${GREEN}✅ CORS headers present${NC}"
  echo -e "${GREEN}   ${CORS_HEADERS}${NC}\n"
else
  echo -e "${YELLOW}⚠️  CORS headers not found${NC}"
  echo -e "${YELLOW}   This might cause issues if frontend and backend are on different domains${NC}\n"
fi

# Summary
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

TOTAL_CHECKS=3
PASSED_CHECKS=0

if [ $BACKEND_STATUS -eq 0 ]; then
  echo -e "${GREEN}✅ Backend API: Healthy${NC}"
  ((PASSED_CHECKS++))
else
  echo -e "${RED}❌ Backend API: Failed${NC}"
fi

if [ $FRONTEND_STATUS -eq 0 ]; then
  echo -e "${GREEN}✅ Frontend: Accessible${NC}"
  ((PASSED_CHECKS++))
else
  echo -e "${RED}❌ Frontend: Failed${NC}"
fi

if [ $JS_STATUS -eq 0 ]; then
  echo -e "${GREEN}✅ JavaScript: Loading${NC}"
  ((PASSED_CHECKS++))
else
  echo -e "${RED}❌ JavaScript: Not Found${NC}"
fi

echo ""

if [ $PASSED_CHECKS -eq $TOTAL_CHECKS ]; then
  echo -e "${GREEN}🎉 All checks passed! (${PASSED_CHECKS}/${TOTAL_CHECKS})${NC}"
  echo -e "${GREEN}Your deployment is healthy.${NC}\n"
  exit 0
elif [ $PASSED_CHECKS -gt 0 ]; then
  echo -e "${YELLOW}⚠️  Some checks failed (${PASSED_CHECKS}/${TOTAL_CHECKS})${NC}"
  echo -e "${YELLOW}Please review the errors above.${NC}\n"
  exit 1
else
  echo -e "${RED}🚨 All checks failed! (${PASSED_CHECKS}/${TOTAL_CHECKS})${NC}"
  echo -e "${RED}Your deployment needs immediate attention.${NC}\n"
  
  echo -e "${BLUE}Troubleshooting Steps:${NC}"
  echo -e "${BLUE}1. Check Railway logs:${NC}"
  echo -e "   ${BLUE}railway logs --service frontend-production${NC}"
  echo -e "   ${BLUE}railway logs --service backend-production${NC}\n"
  
  echo -e "${BLUE}2. Verify environment variables in Railway Dashboard${NC}\n"
  
  echo -e "${BLUE}3. Redeploy services if needed${NC}\n"
  
  exit 1
fi
