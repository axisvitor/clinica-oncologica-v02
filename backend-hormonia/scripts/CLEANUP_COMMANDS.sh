#!/bin/bash
# ==============================================================================
# Quick Cleanup Commands - Python Cache Removal
# ==============================================================================
# Execute this file to clean Python cache and remove from Git in one go
# ==============================================================================

set -e

echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║                   Python Cache Cleanup - Full Process                   ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""

# Change to project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "📂 Project root: $PROJECT_ROOT"
echo ""

# Step 1: Physical cleanup
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1/4: Cleaning Python cache files from filesystem..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
./backend-hormonia/scripts/clean_python_cache.sh
echo ""

# Step 2: Remove from Git
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2/4: Removing cache files from Git tracking..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
./backend-hormonia/scripts/git_remove_cache.sh
echo ""

# Step 3: Verify
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3/4: Verification..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

pycache_count=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l)
pyc_count=$(find . -type f -name "*.pyc" 2>/dev/null | wc -l)

echo "📊 Remaining cache files:"
echo "   - __pycache__ directories: $pycache_count"
echo "   - .pyc files: $pyc_count"
echo ""

if [ "$pycache_count" -eq 0 ] && [ "$pyc_count" -eq 0 ]; then
    echo "✅ All cache files successfully removed!"
else
    echo "⚠️  Some cache files still exist (this is OK if they were just generated)"
fi
echo ""

# Step 4: Git status
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 4/4: Git Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
git status --short | head -20
echo ""

# Summary
echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║                            Cleanup Complete!                             ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "📋 Next Steps:"
echo ""
echo "1️⃣  Review the changes:"
echo "   git status"
echo ""
echo "2️⃣  Commit the cleanup:"
echo "   git commit -m \"chore: remove Python cache files and venv from repository\""
echo ""
echo "3️⃣  Push to remote (if needed):"
echo "   git push"
echo ""
echo "💡 Future Prevention:"
echo "   - The .gitignore has been updated"
echo "   - Cache files will be automatically ignored"
echo "   - Run './backend-hormonia/scripts/clean_python_cache.sh' periodically"
echo ""
