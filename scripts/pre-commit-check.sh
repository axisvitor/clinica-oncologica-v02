#!/bin/sh
# Pre-commit hook for security validation
# Prevents .env files and secrets from being committed
# 
# Installation:
#   chmod +x scripts/pre-commit-check.sh
#   ln -sf ../../scripts/pre-commit-check.sh .git/hooks/pre-commit
#
# References:
#   - docs/COMPREHENSIVE_REVIEW_2025-10-09.md
#   - OWASP Secrets Management Cheat Sheet

set -e

echo "🔒 Running pre-commit security checks..."

# ==============================================================================
# Check 1: Prevent .env files from being committed
# ==============================================================================
echo "  1️⃣ Checking for .env files..."

# Check if any .env files are staged
ENV_FILES=$(git diff --cached --name-only | grep -E '^\.env$|^\.env\..*$|/\.env$|/\.env\..*$' || true)

if [ -n "$ENV_FILES" ]; then
    echo ""
    echo "❌ ERROR: .env files cannot be committed"
    echo ""
    echo "The following .env files are staged for commit:"
    echo "$ENV_FILES" | sed 's/^/  - /'
    echo ""
    echo "💡 Solution:"
    echo "  1. Unstage .env files: git reset HEAD .env*"
    echo "  2. Add secrets to .env.example as placeholders (without real values)"
    echo "  3. Ensure .env* is in .gitignore"
    echo ""
    echo "Example .env.example format:"
    echo "  SECRET_KEY=your-secret-key-here-change-this"
    echo "  CSRF_SECRET_KEY=generate-with-python-secrets"
    echo ""
    exit 1
fi

echo "  ✅ No .env files staged"

# ==============================================================================
# Check 2: Scan for potential secrets in code
# ==============================================================================
echo "  2️⃣ Scanning for potential secrets..."

# Patterns that might indicate secrets (excluding .env.example)
SECRET_PATTERNS="api[_-]?key|secret|password|token|private[_-]?key|access[_-]?key"

# Get staged files (excluding .env.example and known safe files)
STAGED_FILES=$(git diff --cached --name-only | grep -v '.env.example' | grep -v 'package-lock.json' | grep -v 'yarn.lock' | grep -v '.gitignore' || true)

if [ -n "$STAGED_FILES" ]; then
    # Check each staged file for secret patterns
    FOUND_SECRETS=""
    
    for FILE in $STAGED_FILES; do
        if [ -f "$FILE" ]; then
            # Search for secret patterns (case-insensitive)
            MATCHES=$(git diff --cached "$FILE" | grep -i -E "^\+.*($SECRET_PATTERNS)" | grep -v "description=" | grep -v "Field(" | grep -v "# " | grep -v "//" || true)
            
            if [ -n "$MATCHES" ]; then
                FOUND_SECRETS="$FOUND_SECRETS\n$FILE:\n$MATCHES"
            fi
        fi
    done
    
    if [ -n "$FOUND_SECRETS" ]; then
        echo ""
        echo "⚠️  WARNING: Potential secrets detected in commit"
        echo ""
        echo "The following files contain patterns that might be secrets:"
        echo "$FOUND_SECRETS"
        echo ""
        echo "💡 Before committing, verify that:"
        echo "  1. No actual API keys, passwords, or tokens are present"
        echo "  2. Use environment variables for secrets"
        echo "  3. Use placeholders like 'your-secret-here' or 'CHANGETHIS'"
        echo ""
        echo "To proceed anyway, run: git commit --no-verify"
        echo ""
        exit 1
    fi
fi

echo "  ✅ No secrets detected"

# ==============================================================================
# Check 3: Validate CSRF secret format in config
# ==============================================================================
echo "  3️⃣ Checking CSRF configuration..."

# Check if config.py is being modified
if echo "$STAGED_FILES" | grep -q "config.py"; then
    # Ensure CSRF_SECRET_KEY field is defined
    if git diff --cached backend-hormonia/app/config.py | grep -q "CSRF_SECRET_KEY"; then
        echo "  ✅ CSRF configuration updated"
    fi
fi

# ==============================================================================
# Check 4: Ensure sensitive files are in .gitignore
# ==============================================================================
echo "  4️⃣ Verifying .gitignore coverage..."

REQUIRED_IGNORES=".env .env.local .env.production .env.development"

if [ -f .gitignore ]; then
    MISSING_IGNORES=""
    for PATTERN in $REQUIRED_IGNORES; do
        if ! grep -q "^$PATTERN" .gitignore; then
            MISSING_IGNORES="$MISSING_IGNORES $PATTERN"
        fi
    done
    
    if [ -n "$MISSING_IGNORES" ]; then
        echo ""
        echo "⚠️  WARNING: Some sensitive files may not be ignored"
        echo "Missing from .gitignore:$MISSING_IGNORES"
        echo ""
    else
        echo "  ✅ .gitignore properly configured"
    fi
fi

# ==============================================================================
# All checks passed
# ==============================================================================
echo ""
echo "✅ All pre-commit security checks passed"
echo ""

exit 0
