#!/bin/bash
# ==============================================================================
# Git Cache Removal Script
# ==============================================================================
# Removes Python cache files and virtual environments from Git tracking
# WITHOUT deleting them from the filesystem
# ==============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "🔍 Removing Python cache files from Git tracking..."
echo "📂 Working directory: $PROJECT_ROOT"
echo ""
echo "⚠️  WARNING: This will unstage files but NOT delete them from disk"
echo ""

# Remove __pycache__ directories from git
echo "🗑️  Removing __pycache__ from Git index..."
git rm -r --cached --ignore-unmatch "**/__pycache__" 2>/dev/null || true
git rm -r --cached --ignore-unmatch "*/__pycache__" 2>/dev/null || true
find . -type d -name "__pycache__" -exec git rm -r --cached --ignore-unmatch {} + 2>/dev/null || true

# Remove .pyc files from git
echo "🗑️  Removing .pyc files from Git index..."
git rm --cached --ignore-unmatch "**/*.pyc" 2>/dev/null || true
git rm --cached --ignore-unmatch "*.pyc" 2>/dev/null || true
find . -type f -name "*.pyc" -exec git rm --cached --ignore-unmatch {} + 2>/dev/null || true

# Remove .pyo files from git
echo "🗑️  Removing .pyo files from Git index..."
git rm --cached --ignore-unmatch "**/*.pyo" 2>/dev/null || true
find . -type f -name "*.pyo" -exec git rm --cached --ignore-unmatch {} + 2>/dev/null || true

# Remove virtual environments from git
echo "🗑️  Removing virtual environments from Git index..."
git rm -r --cached --ignore-unmatch venv/ 2>/dev/null || true
git rm -r --cached --ignore-unmatch venv_linux/ 2>/dev/null || true
git rm -r --cached --ignore-unmatch ENV/ 2>/dev/null || true
git rm -r --cached --ignore-unmatch env/ 2>/dev/null || true
git rm -r --cached --ignore-unmatch .venv/ 2>/dev/null || true
git rm -r --cached --ignore-unmatch "**/venv/" 2>/dev/null || true
git rm -r --cached --ignore-unmatch "**/venv_linux/" 2>/dev/null || true

# Remove pytest cache from git
echo "🗑️  Removing .pytest_cache from Git index..."
git rm -r --cached --ignore-unmatch "**/.pytest_cache" 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec git rm -r --cached --ignore-unmatch {} + 2>/dev/null || true

# Remove other Python artifacts
echo "🗑️  Removing additional Python artifacts from Git index..."
git rm -r --cached --ignore-unmatch "**/*.egg-info" 2>/dev/null || true
git rm --cached --ignore-unmatch "**/.coverage" 2>/dev/null || true
git rm -r --cached --ignore-unmatch "**/htmlcov" 2>/dev/null || true
git rm -r --cached --ignore-unmatch "**/.tox" 2>/dev/null || true
git rm -r --cached --ignore-unmatch "**/.mypy_cache" 2>/dev/null || true
git rm -r --cached --ignore-unmatch "**/.ruff_cache" 2>/dev/null || true

echo ""
echo "✅ Files removed from Git tracking!"
echo ""
echo "📋 Next steps:"
echo "   1. Review changes: git status"
echo "   2. Commit removal: git commit -m 'chore: remove Python cache files from git'"
echo "   3. Ensure .gitignore is updated to prevent re-adding these files"
echo ""
echo "💡 Files are removed from Git but still exist on your filesystem"
