#!/bin/bash
#
# Setup script for Phase 3 encryption keys
#
# Generates encryption keys and hash salt for .env file
#

set -e

echo "=================================================="
echo "Phase 3: Data Encryption - Key Setup"
echo "=================================================="
echo ""

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 not found"
    echo "Please install Python 3 to continue"
    exit 1
fi

# Check if cryptography is installed
if ! python3 -c "import cryptography" 2> /dev/null; then
    echo "❌ Error: cryptography package not installed"
    echo "Installing cryptography..."
    pip3 install cryptography
fi

echo "Generating encryption keys..."
echo ""

# Generate current encryption key
CURRENT_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
echo "✅ Generated ENCRYPTION_KEY_CURRENT"

# Generate hash salt
HASH_SALT=$(python3 -c "import secrets; print(secrets.token_hex(32))")
echo "✅ Generated HASH_SALT"

echo ""
echo "=================================================="
echo "Add these to your .env file:"
echo "=================================================="
echo ""
echo "# Phase 3: Data Encryption"
echo "ENCRYPTION_KEY_CURRENT=$CURRENT_KEY"
echo "ENCRYPTION_KEY_PREVIOUS="
echo "HASH_SALT=$HASH_SALT"
echo ""
echo "=================================================="
echo "⚠️  IMPORTANT SECURITY NOTES:"
echo "=================================================="
echo ""
echo "1. Store keys securely (AWS Secrets Manager in production)"
echo "2. NEVER commit .env file to git"
echo "3. Back up keys in encrypted offline storage"
echo "4. Rotate keys quarterly (90 days)"
echo "5. Keep ENCRYPTION_KEY_PREVIOUS during rotation"
echo ""
echo "=================================================="
echo "Next Steps:"
echo "=================================================="
echo ""
echo "1. Copy the above keys to .env file"
echo "2. Run migration: python3 scripts/encrypt_patient_email_poc.py --dry-run"
echo "3. Run tests: python3 -m pytest tests/encryption/ -v"
echo ""
