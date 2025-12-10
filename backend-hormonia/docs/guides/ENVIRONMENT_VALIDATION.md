# Environment Variable Validation

## Overview

The application now includes **startup validation** for required environment variables. This ensures the application fails fast with clear error messages if critical configuration is missing, preventing confusing runtime errors later.

## Validation Strategy

### Production Environment

In production (`APP_ENVIRONMENT=production`), the following variables are **required**:

#### Security Keys

1. **SECURITY_CSRF_SECRET_KEY**
   - Purpose: CSRF token generation and validation
   - Generate: `python -c 'import secrets; print(secrets.token_urlsafe(32))'`
   - Example: `xYz123...` (Base64-encoded, 32+ bytes)

2. **ENCRYPTION_KEY_CURRENT**
   - Purpose: Field-level encryption for PHI/PII data (AES-256)
   - Generate: `python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`
   - Example: `fZgOQvXq...` (Fernet key, 44 characters)

3. **HASH_SALT**
   - Purpose: Searchable hash generation for encrypted fields
   - Generate: `python -c 'import secrets; print(secrets.token_hex(32))'`
   - Example: `abc123...` (Hex-encoded, 64 characters minimum)

#### Firebase Admin SDK (if using Firebase)

If **any** Firebase variable is set, **all three** must be set:

1. **FIREBASE_ADMIN_PROJECT_ID**
   - Purpose: Firebase project identifier
   - Source: Firebase Console > Project Settings > General

2. **FIREBASE_ADMIN_PRIVATE_KEY**
   - Purpose: Service account private key for Firebase Admin SDK
   - Source: Firebase Console > Project Settings > Service Accounts > Generate New Private Key
   - Format: JSON string with newlines (`\n`)

3. **FIREBASE_ADMIN_CLIENT_EMAIL**
   - Purpose: Service account email for Firebase Admin SDK
   - Source: Firebase Console > Project Settings > Service Accounts
   - Format: `firebase-adminsdk-xxxxx@project-id.iam.gserviceaccount.com`

### Development Environment

In development (`APP_ENVIRONMENT=development`):

- Security keys (CSRF, encryption, hash) are **optional**
- Firebase variables are **required only if Firebase is in use** (partial configuration is rejected)
- This allows local development without full production setup

## Error Messages

When validation fails, you'll see a clear error message:

```
================================================================================
❌ STARTUP VALIDATION FAILED: Missing Required Environment Variables
================================================================================

The following environment variables are missing:

1. SECURITY_CSRF_SECRET_KEY - Required for CSRF token generation
  Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'

2. ENCRYPTION_KEY_CURRENT - Required for field-level encryption (PHI/PII)
  Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'

3. HASH_SALT - Required for searchable hash generation
  Generate with: python -c 'import secrets; print(secrets.token_hex(32))'

================================================================================
Environment: production
Please set these variables in your .env file or environment configuration.
================================================================================
```

## Implementation Details

### Where Validation Happens

1. **SecuritySettings class** (`app/config/settings/security.py`)
   - `@model_validator(mode="after")` runs after Pydantic model initialization
   - Validates all required variables before the application starts
   - Raises `ValueError` with detailed messages if validation fails

2. **Settings initialization** (`app/config/settings/__init__.py`)
   - `Settings.__init__()` calls validation methods during startup
   - Application cannot start if validation fails

### Validation Flow

```
Application Startup
  ↓
Settings.__init__()
  ↓
SecuritySettings.validate_required_environment_variables()
  ↓
Check APP_ENVIRONMENT
  ↓
┌─────────────────────────────────────────┐
│ Production:                             │
│  - Validate SECURITY_CSRF_SECRET_KEY    │
│  - Validate ENCRYPTION_KEY_CURRENT      │
│  - Validate HASH_SALT                   │
│  - Validate Firebase (if in use)        │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│ Development:                            │
│  - Validate Firebase (if in use)        │
│  - Skip encryption keys                 │
└─────────────────────────────────────────┘
  ↓
Missing variables?
  ↓ YES              ↓ NO
Raise ValueError   Continue startup
with detailed      ✓ Success
error message
```

## Testing

### Manual Testing

Test validation locally:

```bash
# Test missing variables in production
APP_ENVIRONMENT=production python -m app.main

# Test with all variables set
APP_ENVIRONMENT=production \
  SECURITY_CSRF_SECRET_KEY="test_key" \
  ENCRYPTION_KEY_CURRENT="fZgOQvXq..." \
  HASH_SALT="test_salt_32_bytes_minimum_length" \
  python -m app.main
```

### Automated Testing

Run the validation test suite:

```bash
cd backend-hormonia
python scripts/test_env_validation.py
```

Test scenarios:
1. ✅ Production with missing variables (should fail)
2. ✅ Production with all variables (should succeed)
3. ✅ Firebase partial configuration (should fail)
4. ✅ Development without encryption keys (should succeed)

## Best Practices

### Security

1. **Never commit secrets to version control**
   - Use `.env` files locally (listed in `.gitignore`)
   - Use environment variables in production (Railway, Docker, etc.)

2. **Generate strong keys**
   - Use provided commands to generate cryptographically secure keys
   - Minimum key lengths:
     - CSRF: 32 bytes (256 bits)
     - Encryption: 32 bytes (256 bits) - Fernet format
     - Hash Salt: 32 bytes (256 bits)

3. **Key rotation**
   - Support for `ENCRYPTION_KEY_PREVIOUS` for zero-downtime key rotation
   - See `docs/guides/KEY_ROTATION_GUIDE.md` for details

### Deployment

1. **Railway/Cloud Platforms**
   ```bash
   # Set variables via Railway CLI
   railway variables set SECURITY_CSRF_SECRET_KEY="..."
   railway variables set ENCRYPTION_KEY_CURRENT="..."
   railway variables set HASH_SALT="..."
   ```

2. **Docker/Compose**
   ```yaml
   # docker-compose.yml
   environment:
     - SECURITY_CSRF_SECRET_KEY=${SECURITY_CSRF_SECRET_KEY}
     - ENCRYPTION_KEY_CURRENT=${ENCRYPTION_KEY_CURRENT}
     - HASH_SALT=${HASH_SALT}
   ```

3. **Kubernetes**
   ```yaml
   # Use Kubernetes Secrets
   apiVersion: v1
   kind: Secret
   metadata:
     name: app-secrets
   data:
     csrf-key: <base64-encoded>
     encryption-key: <base64-encoded>
     hash-salt: <base64-encoded>
   ```

## Troubleshooting

### Common Issues

1. **Application won't start with generic error**
   - Check the error message for missing variables
   - Verify `.env` file exists and contains required variables
   - Ensure variables are exported in your shell environment

2. **Firebase partial configuration error**
   - Either set all three Firebase variables or none
   - Check for typos in variable names
   - Verify private key format (JSON with escaped newlines)

3. **Production validation too strict**
   - If you're testing production mode locally, ensure all variables are set
   - Consider using `APP_ENVIRONMENT=development` for local testing
   - Use `.env.example` as a template

### Debug Commands

```bash
# Check if variables are set
env | grep -E "(SECURITY_|ENCRYPTION_|HASH_|FIREBASE_)"

# Validate .env file syntax
python -c "from dotenv import dotenv_values; print(dotenv_values('.env'))"

# Test settings import
python -c "from app.config.settings import settings; print('✓ Settings loaded successfully')"
```

## Related Documentation

- [Security Configuration](../backend-hormonia/docs/guides/SECURITY_CONFIG.md)
- [Key Rotation Guide](../backend-hormonia/docs/guides/KEY_ROTATION_GUIDE.md)
- [LGPD Compliance](../backend-hormonia/docs/database/LGPD_COMPLIANCE.md)
- [Railway Deployment](../backend-hormonia/docs/deployment/RAILWAY.md)

## Migration Guide

### Existing Deployments

If you have an existing deployment without these variables:

1. **Generate required keys:**
   ```bash
   # Generate all keys at once
   echo "SECURITY_CSRF_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
   echo "ENCRYPTION_KEY_CURRENT=$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
   echo "HASH_SALT=$(python -c 'import secrets; print(secrets.token_hex(32))')"
   ```

2. **Set variables in your deployment platform**
   - Railway: `railway variables set ...`
   - Docker: Update `docker-compose.yml` or `.env`
   - Kubernetes: Update secrets

3. **Restart the application**
   - Validation will run on startup
   - Check logs for any remaining issues

### New Deployments

Use the `.env.railway.template` as a starting point:

```bash
cp .env.railway.template .env
# Edit .env and fill in all required variables
# Use the generate commands provided in the template
```

## Future Enhancements

Planned improvements:

1. **Health check endpoint** - Include validation status in `/health` response
2. **Startup diagnostics** - Log masked variable status (e.g., "CSRF_KEY: set (32 bytes)")
3. **Configuration audit** - Weekly automated check for key rotation needs
4. **Secret management integration** - Support for AWS Secrets Manager, HashiCorp Vault
