#!/bin/bash
#
# Start All Services - Clinica Oncologica v02
# 
# This script starts all services for local development/production testing.
# Run this script from the project root directory in WSL.
#
# Usage: ./scripts/start-all.sh
#
# Requirements:
#   - tmux installed (sudo apt install tmux)
#   - Redis running (redis-server or via Docker)
#   - PostgreSQL running and configured
#   - Virtual environment created in backend-hormonia/venv_linux
#   - npm dependencies installed in frontend-hormonia and quiz-mensal-interface
#

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION_NAME="clinica-oncologica"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       🏥 Clínica Oncológica - Starting All Services          ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo -e "${RED}❌ tmux is not installed. Please install it:${NC}"
    echo -e "   ${YELLOW}sudo apt install tmux${NC}"
    exit 1
fi

# Check if session already exists
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Session '$SESSION_NAME' already exists.${NC}"
    echo -e "   To attach: ${GREEN}tmux attach -t $SESSION_NAME${NC}"
    echo -e "   To kill it first: ${RED}tmux kill-session -t $SESSION_NAME${NC}"
    read -p "Kill existing session and start fresh? (y/N): " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        tmux kill-session -t "$SESSION_NAME"
        echo -e "${GREEN}✓ Killed existing session${NC}"
    else
        echo "Attaching to existing session..."
        tmux attach -t "$SESSION_NAME"
        exit 0
    fi
fi

echo -e "${GREEN}✓ Creating tmux session: $SESSION_NAME${NC}"

# Create new tmux session with first window (Backend API)
tmux new-session -d -s "$SESSION_NAME" -n "backend-api" -c "$PROJECT_ROOT/backend-hormonia"
tmux send-keys -t "$SESSION_NAME:backend-api" "source venv_linux/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload" C-m

# Create window for Celery Worker
tmux new-window -t "$SESSION_NAME" -n "celery-worker" -c "$PROJECT_ROOT/backend-hormonia"
tmux send-keys -t "$SESSION_NAME:celery-worker" "source venv_linux/bin/activate && celery -A app.celery_app worker --loglevel=info" C-m

# Create window for Celery Beat
tmux new-window -t "$SESSION_NAME" -n "celery-beat" -c "$PROJECT_ROOT/backend-hormonia"
tmux send-keys -t "$SESSION_NAME:celery-beat" "source venv_linux/bin/activate && celery -A app.celery_app beat --loglevel=info" C-m

# Create window for Frontend
tmux new-window -t "$SESSION_NAME" -n "frontend" -c "$PROJECT_ROOT/frontend-hormonia"
tmux send-keys -t "$SESSION_NAME:frontend" "npm run dev" C-m

# Create window for Quiz Interface
tmux new-window -t "$SESSION_NAME" -n "quiz" -c "$PROJECT_ROOT/quiz-mensal-interface"
tmux send-keys -t "$SESSION_NAME:quiz" "npm run dev" C-m

# Select first window
tmux select-window -t "$SESSION_NAME:backend-api"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    ✅ All Services Started!                  ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BLUE}📡 Backend API:${NC}      http://localhost:8000"
echo -e "  ${BLUE}📊 API Docs:${NC}         http://localhost:8000/docs"
echo -e "  ${BLUE}🖥️  Frontend:${NC}        http://localhost:5173"
echo -e "  ${BLUE}📝 Quiz Interface:${NC}   http://localhost:3001"
echo ""
echo -e "  ${YELLOW}tmux commands:${NC}"
echo -e "    Attach:         ${GREEN}tmux attach -t $SESSION_NAME${NC}"
echo -e "    Switch windows: ${GREEN}Ctrl+B then window number (0-4)${NC}"
echo -e "    Detach:         ${GREEN}Ctrl+B then D${NC}"
echo -e "    Kill session:   ${RED}tmux kill-session -t $SESSION_NAME${NC}"
echo ""

# Ask to attach
read -p "Attach to tmux session now? (Y/n): " attach
if [[ ! "$attach" =~ ^[Nn]$ ]]; then
    tmux attach -t "$SESSION_NAME"
fi
