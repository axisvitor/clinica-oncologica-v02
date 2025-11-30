# Security Key Validation Scripts

Scripts para validar e gerar chaves de segurança com entropia adequada.

**Security Issue:** AUTH-001 (Severity 9.5/10)

## Quick Start

### 1. Generate Secure Keys
```bash
python scripts/validate_security_keys.py --generate-keys
```

**Output:**
```
SECURITY_SECRET_KEY=YSeNsnGDMp8uTa1gMrHQt5c5gOOEUYT-qmcsKrZYFeE
  # Entropy: 208.6 bits, Strength: very_strong

AUTH_JWT_SECRET_KEY=htg_tbjrPZpYHZzo_NWku-wkYC5Rmoe1USWsRM7bZLk
  # Entropy: 209.8 bits, Strength: very_strong
```

Copy these to your `.env` file.

### 2. Validate Existing Keys
```bash
python scripts/validate_security_keys.py
```

**Output (Success):**
```
✅ SECURITY_SECRET_KEY
   Entropy: 208.6 bits
   Strength: very_strong

✅ ALL KEYS VALID - Production Ready!
```

**Output (Failure):**
```
❌ SECURITY_SECRET_KEY
   Masked: CHAN********************TION
   Entropy: 36.1 bits (minimum: 128)
   Strength: weak
   Issues:
      - Contains placeholder text that must be replaced
      - Insufficient entropy: 36.1 bits (minimum: 128)

❌ SOME KEYS INVALID - Fix Before Production!
```

### 3. Quick Check Single Key
```bash
python scripts/validate_security_keys.py --check-key "your_key_here"
```

## Usage Examples

### Validate Production Environment
```bash
python scripts/validate_security_keys.py --env-file .env.production --environment production
```

### Validate Development Environment (Lenient)
```bash
python scripts/validate_security_keys.py --env-file .env --environment development
```

### Generate Keys and Save to File
```bash
python scripts/validate_security_keys.py --generate-keys > generated_keys.txt
```

⚠️ **Remember to delete `generated_keys.txt` after copying to secure storage!**

## Command-Line Options

```
--env-file FILE         Environment file to validate (default: .env)
--environment ENV       Environment type: production or development (default: production)
--generate-keys         Generate new secure keys
--check-key KEY         Quick check a single key
```

## Validation Criteria

### Production Environment
- ✅ Minimum entropy: **128 bits**
- ✅ Minimum length: **32 characters**
- ✅ No placeholder patterns (CHANGE_THIS, your_secret, etc.)
- ✅ High character diversity (uppercase, lowercase, digits, special)
- ✅ No repeated patterns
- ✅ No sequential patterns (abc, 123, etc.)

### Development Environment
- ✅ Minimum entropy: **64 bits**
- ⚠️ Warnings for placeholders (doesn't block)
- ⚠️ Warnings for low entropy (doesn't block)

## Integration with CI/CD

### GitHub Actions Example
```yaml
- name: Validate Security Keys
  run: |
    python scripts/validate_security_keys.py --env-file .env.production
  env:
    SECURITY_SECRET_KEY: ${{ secrets.SECURITY_SECRET_KEY }}
    # ... other secrets
```

### Pre-commit Hook
```bash
#!/bin/sh
python scripts/validate_security_keys.py --environment production
if [ $? -ne 0 ]; then
    echo "❌ Security key validation failed!"
    exit 1
fi
```

## Programmatic Usage

### Python Example
```python
from app.utils.security_validation import (
    validate_key_strength,
    is_production_ready,
    mask_secret_for_logging,
)

# Validate key
key = "your_key_here"
result = validate_key_strength(key)

if result.is_valid:
    print("✅ Key is valid!")
else:
    print(f"❌ Issues: {result.issues}")

# Quick check
if is_production_ready(key):
    print("✅ Production ready!")

# Safe logging
print(f"Key: {mask_secret_for_logging(key)}")
```

## Troubleshooting

### Error: "No environment variables found"
**Solution:** Ensure `.env` file exists and has `KEY=value` format.

### Error: "Key has insufficient entropy"
**Solution:** Generate new key with:
```bash
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

### Error: "Contains placeholder text"
**Solution:** Replace placeholder with generated key from `--generate-keys`.

## Security Best Practices

1. **Never commit secrets to version control**
   - Use `.gitignore` for `.env` files
   - Only commit `.env.example` with placeholders

2. **Use different keys per environment**
   - Development: Can use weaker keys for convenience
   - Staging: Should use production-strength keys
   - Production: Must use 128+ bit entropy keys

3. **Rotate keys regularly**
   - Recommended: Every 90 days
   - After security incident: Immediately
   - After team member departure: As soon as possible

4. **Store production keys securely**
   - Use secret management (AWS Secrets Manager, HashiCorp Vault)
   - Environment variables in CI/CD
   - Never in plaintext files

5. **Validate keys on every deployment**
   - Add to CI/CD pipeline
   - Fail deployment if validation fails
   - Log masked versions only

## Related Documentation

- [Entropy Validation Implementation](../docs/ENTROPY_VALIDATION_IMPLEMENTATION.md)
- [Security Configuration](../app/config/settings/security.py)
- [Validation Module](../app/utils/security_validation.py)
- [Test Suite](../tests/utils/test_security_validation.py)
