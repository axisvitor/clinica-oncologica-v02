#!/bin/bash
# Start Backend Server for Login Testing
# This script starts the FastAPI backend server with proper configuration

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🚀 Starting Backend Server${NC}"
echo -e "${BLUE}========================================${NC}"

# Navigate to backend directory
cd "$(dirname "$0")/../backend-hormonia"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    echo -e "${YELLOW}Please copy .env.example to .env and configure it${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Found .env file${NC}"

# Check if virtual environment exists
if [ ! -d "venv_linux" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Creating...${NC}"
    python3 -m venv venv_linux
    echo -e "${GREEN}✅ Virtual environment created${NC}"
fi

# Activate virtual environment
echo -e "${BLUE}📦 Activating virtual environment...${NC}"
source venv_linux/bin/activate

# Check if requirements are installed
if [ ! -f "venv_linux/.requirements_installed" ]; then
    echo -e "${YELLOW}⚠️  Installing dependencies...${NC}"
    pip install -r requirements.txt
    touch venv_linux/.requirements_installed
    echo -e "${GREEN}✅ Dependencies installed${NC}"
else
    echo -e "${GREEN}✅ Dependencies already installed${NC}"
fi

# Check if port 8000 is already in use
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo -e "${YELLOW}⚠️  Port 8000 is already in use${NC}"
    echo -e "${YELLOW}Attempting to stop existing process...${NC}"
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    sleep 2
    echo -e "${GREEN}✅ Port 8000 cleared${NC}"
fi

# Display configuration
echo -e "\n${BLUE}Configuration:${NC}"
source .env
echo -e "  Host:     ${APP_HOST:-0.0.0.0}"
echo -e "  Port:     ${APP_PORT:-8000}"
echo -e "  API:      /api/${APP_API_VERSION:-v2}"
echo -e "  Debug:    ${APP_ENABLE_DEBUG:-false}"
echo -e "  Database: ${DATABASE_URL:0:30}..."
echo -e "  Redis:    ${REDIS_ENABLE_SERVICE:-false}"

# Start server
echo -e "\n${GREEN}🚀 Starting Uvicorn server...${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}\n"

# Start with auto-reload for development
uvicorn app.main:app \
    --reload \
    --host "${APP_HOST:-0.0.0.0}" \
    --port "${APP_PORT:-8000}" \
    --log-level info

# This line is reached when server is stopped
echo -e "\n${YELLOW}🛑 Server stopped${NC}"
