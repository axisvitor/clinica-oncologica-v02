#!/bin/bash
#
# Stop All Services - Clinica Oncologica v02
#
# This script stops all services by killing the tmux session.
#
# Usage: ./scripts/stop-all.sh
#

SESSION_NAME="clinica-oncologica"

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    tmux kill-session -t "$SESSION_NAME"
    echo "✅ All services stopped (tmux session '$SESSION_NAME' killed)"
else
    echo "⚠️  No active session '$SESSION_NAME' found"
fi
