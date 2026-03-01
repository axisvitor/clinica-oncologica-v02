# Required Environment Variables - Quick Reference

## 🚨 Production Requirements

These variables **MUST** be set in production or the application will not start:

### Security Keys

```bash
# CSRF Protection
export SECURITY_CSRF_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

# Core App Secret
export SECURITY_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')"

# PHI Encryption (AES-256-GCM)
export PHI_ENCRYPTION_KEY="$(python3 -c 'import os, base64; print(base64.b64encode(os.urandom(32)).decode())')"

# Field-level Encryption (PHI/PII)
export ENCRYPTION_KEY_CURRENT="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"

# Searchable Hash Salt
export HASH_SALT="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
```

### Firebase (if using Firebase Authentication)

**All three required if using Firebase:**

```bash
export FIREBASE_ADMIN_PROJECT_ID="your-project-id"
export FIREBASE_ADMIN_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
export FIREBASE_ADMIN_CLIENT_EMAIL="firebase-adminsdk-xxxxx@project-id.iam.gserviceaccount.com"
```

Get from: Firebase Console → Project Settings → Service Accounts → Generate New Private Key

## 📝 Development Environment

Only Firebase variables are required (if Firebase is in use). Encryption keys are optional for local development.

## ⚡ Quick Setup Commands

### Generate All Keys at Once

```bash
#!/bin/bash
# Save this as generate_env_keys.sh and run: bash generate_env_keys.sh

echo "# Generated on $(date)"
echo ""
echo "# Security Keys"
echo "SECURITY_CSRF_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
echo "SECURITY_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')"
echo "PHI_ENCRYPTION_KEY=$(python3 -c 'import os, base64; print(base64.b64encode(os.urandom(32)).decode())')"
echo "ENCRYPTION_KEY_CURRENT=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
echo "HASH_SALT=$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
```

### Set in Railway

```bash
# From generated values above
railway variables set SECURITY_CSRF_SECRET_KEY="..."
railway variables set SECURITY_SECRET_KEY="..."
railway variables set PHI_ENCRYPTION_KEY="..."
railway variables set ENCRYPTION_KEY_CURRENT="..."
railway variables set HASH_SALT="..."
```

### Set in Docker Compose

```yaml
environment:
  SECURITY_CSRF_SECRET_KEY: ${SECURITY_CSRF_SECRET_KEY}
  SECURITY_SECRET_KEY: ${SECURITY_SECRET_KEY}
  PHI_ENCRYPTION_KEY: ${PHI_ENCRYPTION_KEY}
  ENCRYPTION_KEY_CURRENT: ${ENCRYPTION_KEY_CURRENT}
  HASH_SALT: ${HASH_SALT}
```

## 🔍 Verify Configuration

```bash
# Check if variables are set
env | grep -E "(SECURITY_SECRET_KEY|SECURITY_CSRF_SECRET_KEY|PHI_ENCRYPTION_KEY|ENCRYPTION_KEY_CURRENT|HASH_SALT|FIREBASE_ADMIN)"

# Test application startup
python3 -m app.main

# Run validation tests
python3 scripts/test_env_validation.py
```

## ❌ Error: Missing Variables

If you see this error:

```
❌ STARTUP VALIDATION FAILED: Missing Required Environment Variables
```

1. Check which variables are missing (listed in error message)
2. Generate the missing keys using commands above
3. Set them in your environment or `.env` file
4. Restart the application

## 📚 Full Documentation

For complete details, see:
- [Environment Validation Guide](./guides/ENVIRONMENT_VALIDATION.md)
- [Implementation Summary](./IMPLEMENTATION_SUMMARY_ENV_VALIDATION.md)
- [Security Configuration](./guides/SECURITY_CONFIG.md)

## 🔒 Security Notes

- **NEVER commit these values to version control**
- **Use different keys for each environment** (dev, staging, prod)
- **Rotate keys regularly** (see `docs/guides/KEY_ROTATION_GUIDE.md`)
- **Use secure secret management** in production (AWS Secrets Manager, HashiCorp Vault, etc.)
