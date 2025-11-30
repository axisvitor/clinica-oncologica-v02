#!/bin/bash
# ==============================================================================
# Python Cache Cleanup Script
# ==============================================================================
# Removes all Python bytecode cache files and directories from the project
# Safe to run multiple times - idempotent operation
# ==============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "🧹 Starting Python cache cleanup..."
echo "📂 Working directory: $PROJECT_ROOT"
echo ""

# Counter for statistics
pycache_dirs=0
pyc_files=0
pyo_files=0
pytest_cache=0

# Remove __pycache__ directories
echo "🗑️  Removing __pycache__ directories..."
while IFS= read -r -d '' dir; do
    rm -rf "$dir"
    ((pycache_dirs++))
done < <(find . -type d -name "__pycache__" -print0 2>/dev/null)

# Remove .pyc files
echo "🗑️  Removing .pyc files..."
while IFS= read -r -d '' file; do
    rm -f "$file"
    ((pyc_files++))
done < <(find . -type f -name "*.pyc" -print0 2>/dev/null)

# Remove .pyo files
echo "🗑️  Removing .pyo files..."
while IFS= read -r -d '' file; do
    rm -f "$file"
    ((pyo_files++))
done < <(find . -type f -name "*.pyo" -print0 2>/dev/null)

# Remove pytest cache
echo "🗑️  Removing .pytest_cache directories..."
while IFS= read -r -d '' dir; do
    rm -rf "$dir"
    ((pytest_cache++))
done < <(find . -type d -name ".pytest_cache" -print0 2>/dev/null)

# Remove additional Python cache patterns
echo "🗑️  Removing additional cache patterns..."
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".tox" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name ".coverage" -delete 2>/dev/null || true
find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true

echo ""
echo "✅ Python cache cleanup completed!"
echo ""
echo "📊 Statistics:"
echo "   - __pycache__ directories removed: $pycache_dirs"
echo "   - .pyc files removed: $pyc_files"
echo "   - .pyo files removed: $pyo_files"
echo "   - .pytest_cache directories removed: $pytest_cache"
echo ""
echo "💡 To prevent cache files from being committed, ensure .gitignore is up to date."
echo "   Run: git rm -r --cached **/__pycache__ **/*.pyc"
