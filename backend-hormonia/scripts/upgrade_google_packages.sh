#!/bin/bash
# Script to upgrade Google packages and fix pkg_resources deprecation warning
# Run this from the backend-hormonia directory

set -e  # Exit on error

echo "============================================================"
echo "Upgrading Google packages to fix pkg_resources deprecation"
echo "============================================================"
echo ""

echo "Step 1: Checking current Python version..."
python3 --version
echo ""

echo "Step 2: Backing up current package list..."
python3 -m pip freeze > requirements.backup.txt
echo "Backup saved to requirements.backup.txt"
echo ""

echo "Step 3: Upgrading specific Google packages..."
python3 -m pip install --upgrade "googleapis-common-protos>=1.70.0,<2.0.0"
python3 -m pip install --upgrade "google-api-core>=2.25.0,<3.0.0"
python3 -m pip install --upgrade "google-auth>=2.40.0,<3.0.0"
python3 -m pip install --upgrade "grpcio>=1.75.0,<2.0.0"
python3 -m pip install --upgrade "grpcio-status>=1.75.0,<2.0.0"
python3 -m pip install --upgrade "proto-plus>=1.26.0,<2.0.0"
python3 -m pip install --upgrade "firebase-admin>=6.9.0,<7.0.0"
echo ""

echo "Step 4: Installing all requirements (to catch any new dependencies)..."
python3 -m pip install --upgrade -r requirements.txt
echo ""

echo "Step 5: Checking for package conflicts..."
python3 -m pip check
echo ""

echo "Step 6: Running verification script..."
python3 scripts/verify_pkg_resources_fix.py
echo ""

echo "============================================================"
echo "Upgrade complete!"
echo "============================================================"
echo ""
echo "Next steps:"
echo "1. Review the verification output above"
echo "2. Test your application: python3 -m uvicorn app.main:app --reload"
echo "3. Run tests: python3 -m pytest tests/ -v"
echo ""
echo "If you encounter issues, restore from backup:"
echo "   python3 -m pip install -r requirements.backup.txt"
echo ""
