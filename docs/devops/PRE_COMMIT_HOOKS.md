# Pre-Commit Hooks - Security Implementation

## Overview

Pre-commit hooks implemented to prevent accidental commits of sensitive files and secrets, addressing security concerns identified in the comprehensive review (docs/COMPREHENSIVE_REVIEW_2025-10-09.md).

## Implementation Date
2025-10-09

## Components

### 1. Main Pre-Commit Script
**Location:** `scripts/pre-commit-check.sh`

**Checks performed:**
- ❌ Prevents `.env` file commits
- ❌ Blocks environment-specific `.env.*` files (except `.example`)
- ⚠️ Detects potential secrets in staged files
- ❌ Prevents Firebase service account key commits
- ⚠️ Warns about hardcoded credentials

**Detected Secret Patterns:**
- `FIREBASE_ADMIN_PRIVATE_KEY`
- `SECRET_KEY`
- `DATABASE_URL`
- `API_KEY`
- `PRIVATE_KEY`
- `ACCESS_TOKEN`
- `REFRESH_TOKEN`
- `JWT_SECRET`
- `ENCRYPTION_KEY`
- `AWS_SECRET`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `STRIPE_SECRET`
- `TWILIO_AUTH_TOKEN`
- `SENDGRID_API_KEY`

**Credential Patterns:**
- `password = "..."`
- `api_key = "..."`
- `secret = "..."`
- `token = "..."`

### 2. Git Hook Wrapper
**Location:** `.git/hooks/pre-commit`

Automatically calls the main script from `scripts/pre-commit-check.sh` during `git commit`.

## Installation

The hooks are automatically installed in the repository. To verify:

```bash
# Check if hook exists
ls -l .git/hooks/pre-commit

# Check if script exists
ls -l scripts/pre-commit-check.sh

# Verify execution permissions
test -x .git/hooks/pre-commit && echo "Hook is executable" || echo "Hook needs chmod +x"
```

## Usage

### Normal Commit Flow

```bash
# Make changes
git add .

# Commit (hook runs automatically)
git commit -m "Your commit message"

# If checks pass:
# ✅ ALL PRE-COMMIT CHECKS PASSED
# Commit proceeds normally

# If checks fail:
# ❌ PRE-COMMIT CHECKS FAILED
# Commit is blocked
```

### Bypassing Checks (NOT RECOMMENDED)

```bash
# Only use when absolutely necessary
git commit --no-verify -m "Emergency commit"
```

**⚠️ WARNING:** Bypassing checks can lead to:
- Exposed secrets in repository history
- Security vulnerabilities
- Compliance violations
- Difficult secret rotation

## Testing

### Test 1: Block .env File Commit

```bash
# Create test .env file
echo "SECRET_KEY=test123" > .env

# Try to commit
git add .env
git commit -m "Test .env blocking"

# Expected result:
# ❌ ERROR: .env file cannot be committed
# Commit blocked
```

### Test 2: Detect Secrets in Code

```bash
# Create file with hardcoded secret
echo 'API_KEY = "sk_live_1234567890"' > test_secrets.py

# Try to commit
git add test_secrets.py
git commit -m "Test secret detection"

# Expected result:
# ⚠️ WARNING: Potential secret detected
# User prompted to review
```

### Test 3: Block Firebase Keys

```bash
# Create fake service account file
touch firebase-adminsdk-test.json

# Try to commit
git add firebase-adminsdk-test.json
git commit -m "Test Firebase key blocking"

# Expected result:
# ❌ ERROR: Firebase service account key files detected
# Commit blocked
```

## .gitignore Verification

The following entries in `.gitignore` prevent `.env` files from being staged:

```gitignore
# Environment variables
.env
.env.local
.env.*.local
.env.production
.env.staging
*.env
!.env.example
!.env.*.example
!.env.sentry.example
```

**Allowed Files:**
- ✅ `.env.example` - Template files
- ✅ `.env.sentry.example` - Service-specific templates

**Blocked Files:**
- ❌ `.env` - Main environment file
- ❌ `.env.local` - Local overrides
- ❌ `.env.production` - Production config
- ❌ `.env.staging` - Staging config
- ❌ Any `.env.*` not ending in `.example`

## Security Best Practices

### DO:
✅ Use `.env.example` for documentation
✅ Store secrets in environment variables
✅ Use secret management services (Railway, Vault, AWS Secrets Manager)
✅ Rotate secrets regularly
✅ Use different secrets per environment
✅ Review pre-commit warnings carefully

### DON'T:
❌ Commit `.env` files
❌ Bypass pre-commit checks without review
❌ Hardcode secrets in source code
❌ Share secrets in chat/email
❌ Reuse secrets across projects
❌ Store secrets in documentation

## Incident Response

If a secret is accidentally committed:

1. **Immediate Actions:**
   ```bash
   # Remove from latest commit
   git reset HEAD~1
   git rm --cached .env
   git commit -m "Remove accidentally committed .env"

   # If already pushed
   git push --force
   ```

2. **Rotate Compromised Secrets:**
   - Generate new Firebase service account key
   - Update database passwords
   - Regenerate API keys
   - Update JWT secrets
   - Rotate encryption keys

3. **Verify History:**
   ```bash
   # Check if secret exists in history
   git log --all --full-history --source -- .env

   # Remove from all history (DESTRUCTIVE)
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch .env" \
     --prune-empty --tag-name-filter cat -- --all
   ```

4. **Audit Access:**
   - Check deployment logs for unauthorized access
   - Review database audit logs
   - Monitor API usage for anomalies
   - Update security documentation

## Continuous Improvement

### Planned Enhancements:
- [ ] Add support for Husky (npm-based hooks)
- [ ] Implement pre-push hooks
- [ ] Add commit message validation
- [ ] Integrate with Gitleaks for secret scanning
- [ ] Add custom secret patterns per project
- [ ] Implement hooks for conventional commits
- [ ] Add TypeScript/Python linting in hooks

### Monitoring:
- Track number of blocked commits
- Analyze common secret patterns
- Review bypass usage
- Update detection patterns quarterly

## Related Documentation

- [Security Improvements 2025-10-08](../SECURITY_IMPROVEMENTS_2025-10-08.md)
- [Comprehensive Review 2025-10-09](../COMPREHENSIVE_REVIEW_2025-10-09.md)
- [Environment Configuration](../../backend-hormonia/docs/ENVIRONMENT_CONFIGURATION.md)

## Support

For issues with pre-commit hooks:

1. **Check hook installation:**
   ```bash
   ls -l .git/hooks/pre-commit
   ```

2. **Verify script permissions:**
   ```bash
   chmod +x .git/hooks/pre-commit
   chmod +x scripts/pre-commit-check.sh
   ```

3. **Test manually:**
   ```bash
   ./scripts/pre-commit-check.sh
   ```

4. **Review git config:**
   ```bash
   git config --list | grep hooks
   ```

## Conclusion

Pre-commit hooks provide an essential security layer by:
- Preventing accidental secret commits
- Enforcing security best practices
- Educating developers about secure coding
- Reducing incident response overhead
- Maintaining compliance requirements

**Remember:** Hooks are a safety net, not a replacement for security awareness.
