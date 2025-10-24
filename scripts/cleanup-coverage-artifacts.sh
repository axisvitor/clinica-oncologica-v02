#!/bin/bash
# Coverage Artifacts Cleanup Script
# Removes coverage files from git version control (they should be build artifacts only)

set -e

echo "[INFO] Cleaning up coverage artifacts from version control..."

cd "$(dirname "$0")/.."

# Ensure we are inside a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "[ERROR] Not in a git repository"
    exit 1
fi

echo
echo "[SECTION] Backend: removing coverage artifacts tracked by git..."
cd backend-hormonia

if [ -f coverage.json ]; then
    git rm --cached coverage.json 2>/dev/null || echo "  [SKIP] coverage.json not tracked (ok)"
else
    echo "  [MISSING] coverage.json not found (ok)"
fi

if [ -f coverage.lcov ]; then
    git rm --cached coverage.lcov 2>/dev/null || echo "  [SKIP] coverage.lcov not tracked (ok)"
else
    echo "  [MISSING] coverage.lcov not found (ok)"
fi

if [ -f test_results.txt ]; then
    git rm --cached test_results.txt 2>/dev/null || echo "  [SKIP] test_results.txt not tracked (ok)"
else
    echo "  [MISSING] test_results.txt not found (ok)"
fi

if [ -d htmlcov ]; then
    git rm --cached -r htmlcov 2>/dev/null || echo "  [SKIP] htmlcov/ not tracked (ok)"
else
    echo "  [MISSING] htmlcov/ not found (ok)"
fi

cd ..

echo
echo "[SECTION] Frontend: checking coverage artifacts..."
cd frontend-hormonia

if [ -d coverage ]; then
    git rm --cached -r coverage 2>/dev/null || echo "  [SKIP] coverage/ already ignored (ok)"
else
    echo "  [MISSING] coverage/ not found (ok)"
fi

if [ -d test-results ]; then
    git rm --cached -r test-results 2>/dev/null || echo "  [SKIP] test-results/ already ignored (ok)"
else
    echo "  [MISSING] test-results/ not found (ok)"
fi

cd ..

echo
echo "[SECTION] Quiz app: checking coverage artifacts..."
cd quiz-mensal-interface

if [ -d coverage ]; then
    git rm --cached -r coverage 2>/dev/null || echo "  [SKIP] coverage/ already ignored (ok)"
else
    echo "  [MISSING] coverage/ not found (ok)"
fi

cd ..

echo
echo "[DONE] Coverage artifact cleanup completed."
echo "[NEXT] Review changes with 'git status', then commit if they look correct."
echo "[NOTE] Files remain on disk; only git tracking was removed."
