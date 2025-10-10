#!/bin/bash
# Installation script for pre-commit hooks
# Created: 2025-10-09
# Purpose: Install security validation hooks in git repository

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 Installing pre-commit hooks...${NC}"
echo ""

# ============================================================================
# Validate we're in a git repository
# ============================================================================
if [ ! -d ".git" ]; then
    echo -e "${RED}❌ ERROR: Not a git repository${NC}"
    echo "Please run this script from the root of your git repository."
    exit 1
fi

# ============================================================================
# Create hooks directory if it doesn't exist
# ============================================================================
HOOKS_DIR=".git/hooks"
if [ ! -d "$HOOKS_DIR" ]; then
    echo -e "${YELLOW}Creating hooks directory...${NC}"
    mkdir -p "$HOOKS_DIR"
fi

# ============================================================================
# Install pre-commit hook
# ============================================================================
HOOK_PATH="$HOOKS_DIR/pre-commit"
SOURCE_SCRIPT="scripts/pre-commit-check.sh"

if [ ! -f "$SOURCE_SCRIPT" ]; then
    echo -e "${RED}❌ ERROR: Source script not found: $SOURCE_SCRIPT${NC}"
    echo "Please ensure the script exists in the scripts directory."
    exit 1
fi

# Backup existing hook if present
if [ -f "$HOOK_PATH" ]; then
    BACKUP_PATH="$HOOK_PATH.backup.$(date +%Y%m%d_%H%M%S)"
    echo -e "${YELLOW}⚠️  Existing pre-commit hook found${NC}"
    echo "Backing up to: $BACKUP_PATH"
    mv "$HOOK_PATH" "$BACKUP_PATH"
fi

# Copy and make executable
echo "Installing pre-commit hook..."
cp "$SOURCE_SCRIPT" "$HOOK_PATH"
chmod +x "$HOOK_PATH"

# ============================================================================
# Verify installation
# ============================================================================
if [ -x "$HOOK_PATH" ]; then
    echo ""
    echo -e "${GREEN}✅ Pre-commit hook installed successfully!${NC}"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "The hook will automatically run before each commit to check for:"
    echo "  • .env files"
    echo "  • Hardcoded secrets"
    echo "  • Insecure token storage (localStorage)"
    echo "  • Cloud provider credentials"
    echo "  • Private keys"
    echo "  • Database connection strings"
    echo ""
    echo "Usage:"
    echo "  • Hooks run automatically on 'git commit'"
    echo "  • Test manually: ./scripts/pre-commit-check.sh"
    echo "  • Bypass (not recommended): git commit --no-verify"
    echo ""
    echo "To uninstall:"
    echo "  rm .git/hooks/pre-commit"
    echo ""
else
    echo -e "${RED}❌ ERROR: Installation failed${NC}"
    echo "Hook file is not executable."
    exit 1
fi

# ============================================================================
# Optional: Test the hook
# ============================================================================
echo -e "${BLUE}Would you like to test the hook now? (y/n)${NC}"
read -r response

if [[ "$response" =~ ^[Yy]$ ]]; then
    echo ""
    echo "Running test..."
    echo ""

    # Run the hook (will fail if there are issues in staged files)
    if "$HOOK_PATH"; then
        echo ""
        echo -e "${GREEN}✅ Hook test passed!${NC}"
    else
        echo ""
        echo -e "${YELLOW}⚠️  Hook test detected issues in staged files.${NC}"
        echo "This is expected if you have staged changes that violate security rules."
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}Installation complete!${NC}"
echo ""
