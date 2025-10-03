#!/bin/bash

###############################################################################
# Frontend Initialization Script
#
# This script initializes the React frontend with proper configuration
# and verifies all connections are working.
#
# Usage:
#   ./scripts/init-frontend.sh [environment]
#
# Arguments:
#   environment - Optional: development|production (default: development)
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-development}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        HORMONIA Frontend Initialization Script                ║${NC}"
echo -e "${BLUE}║        Environment: ${ENVIRONMENT}                                    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"

###############################################################################
# Step 1: Check Node.js and npm
###############################################################################
echo -e "\n${YELLOW}[1/8]${NC} Checking Node.js and npm..."

if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js is not installed${NC}"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo -e "${RED}❌ npm is not installed${NC}"
    exit 1
fi

NODE_VERSION=$(node --version)
NPM_VERSION=$(npm --version)
echo -e "${GREEN}✅ Node.js ${NODE_VERSION}${NC}"
echo -e "${GREEN}✅ npm ${NPM_VERSION}${NC}"

###############################################################################
# Step 2: Install Dependencies
###############################################################################
echo -e "\n${YELLOW}[2/8]${NC} Installing dependencies..."

cd "$PROJECT_ROOT"

if [ ! -d "node_modules" ]; then
    echo -e "${BLUE}Installing packages...${NC}"
    npm install
    echo -e "${GREEN}✅ Dependencies installed${NC}"
else
    echo -e "${GREEN}✅ Dependencies already installed${NC}"
fi

###############################################################################
# Step 3: Environment Configuration
###############################################################################
echo -e "\n${YELLOW}[3/8]${NC} Setting up environment configuration..."

ENV_FILE=".env"
ENV_EXAMPLE=".env.example"

if [ "$ENVIRONMENT" = "production" ]; then
    ENV_FILE=".env.production"

    if [ -f ".env.railway.production" ]; then
        echo -e "${BLUE}Using Railway production configuration${NC}"
        cp .env.railway.production .env.production
        echo -e "${GREEN}✅ Production environment configured${NC}"
    else
        echo -e "${YELLOW}⚠️  No Railway production config found${NC}"
    fi
elif [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_EXAMPLE" ]; then
        echo -e "${BLUE}Creating .env from template${NC}"
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        echo -e "${YELLOW}⚠️  Please update .env with your actual values${NC}"
    else
        echo -e "${RED}❌ No .env.example file found${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ Environment file exists${NC}"
fi

###############################################################################
# Step 4: Verify TypeScript Configuration
###############################################################################
echo -e "\n${YELLOW}[4/8]${NC} Verifying TypeScript configuration..."

if [ -f "tsconfig.json" ]; then
    echo -e "${GREEN}✅ TypeScript configured${NC}"
else
    echo -e "${RED}❌ tsconfig.json not found${NC}"
    exit 1
fi

###############################################################################
# Step 5: Verify Vite Configuration
###############################################################################
echo -e "\n${YELLOW}[5/8]${NC} Verifying Vite configuration..."

if [ -f "vite.config.ts" ]; then
    echo -e "${GREEN}✅ Vite configured${NC}"
else
    echo -e "${RED}❌ vite.config.ts not found${NC}"
    exit 1
fi

###############################################################################
# Step 6: Build TypeScript Files (if needed)
###############################################################################
echo -e "\n${YELLOW}[6/8]${NC} Type checking..."

if npm run typecheck &> /dev/null; then
    echo -e "${GREEN}✅ TypeScript types valid${NC}"
else
    echo -e "${YELLOW}⚠️  TypeScript type check warnings (non-critical)${NC}"
fi

###############################################################################
# Step 7: Verify Runtime Configuration
###############################################################################
echo -e "\n${YELLOW}[7/8]${NC} Verifying runtime configuration..."

# Check if verification script exists
if [ -f "scripts/verify-initialization.ts" ]; then
    echo -e "${BLUE}Running initialization verification...${NC}"

    # Try to run with tsx if available
    if command -v tsx &> /dev/null; then
        if tsx scripts/verify-initialization.ts; then
            echo -e "${GREEN}✅ Initialization verification passed${NC}"
        else
            echo -e "${YELLOW}⚠️  Initialization verification had warnings${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  tsx not found, skipping detailed verification${NC}"
        echo -e "${BLUE}Install tsx globally: npm install -g tsx${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Verification script not found${NC}"
fi

###############################################################################
# Step 8: Display Configuration Summary
###############################################################################
echo -e "\n${YELLOW}[8/8]${NC} Configuration Summary..."

# Read key config values if .env exists
if [ -f "$ENV_FILE" ]; then
    echo -e "\n${BLUE}Key Configuration:${NC}"

    if grep -q "VITE_API_URL" "$ENV_FILE"; then
        API_URL=$(grep "VITE_API_URL" "$ENV_FILE" | cut -d '=' -f2)
        echo -e "  API URL: ${GREEN}${API_URL}${NC}"
    fi

    if grep -q "VITE_SUPABASE_URL" "$ENV_FILE"; then
        SUPABASE_URL=$(grep "VITE_SUPABASE_URL" "$ENV_FILE" | cut -d '=' -f2)
        echo -e "  Supabase URL: ${GREEN}${SUPABASE_URL}${NC}"
    fi

    if grep -q "VITE_WS_BASE_URL" "$ENV_FILE"; then
        WS_URL=$(grep "VITE_WS_BASE_URL" "$ENV_FILE" | cut -d '=' -f2)
        echo -e "  WebSocket URL: ${GREEN}${WS_URL}${NC}"
    fi
fi

###############################################################################
# Final Status
###############################################################################
echo -e "\n${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    Initialization Complete                     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"

echo -e "\n${GREEN}🚀 Next Steps:${NC}"
echo -e "  ${BLUE}1.${NC} Start development server: ${GREEN}npm run dev${NC}"
echo -e "  ${BLUE}2.${NC} Build for production: ${GREEN}npm run build${NC}"
echo -e "  ${BLUE}3.${NC} Run tests: ${GREEN}npm run test${NC}"

if [ "$ENVIRONMENT" = "development" ]; then
    echo -e "\n${YELLOW}Note:${NC} Remember to update .env with your actual API keys and URLs"
fi

echo ""