# Scripts Documentation

This directory contains utility scripts for the Clínica Oncológica project.

## Pre-commit Security Hooks

### Overview

The pre-commit hooks provide automated security validation to prevent sensitive data from being committed to the repository.

### Security Checks Performed

1. **`.env` File Detection**
   - Prevents any `.env` or `.env.*` files from being committed
   - Ensures environment variables remain local

2. **Hardcoded Secrets**
   - Detects API keys, tokens, passwords, and secrets
   - Scans for patterns like `api_key="xxx"`, `secret="xxx"`, etc.

3. **Insecure Token Storage**
   - Identifies `localStorage` usage for tokens/authentication
   - Enforces httpOnly cookie usage instead

4. **Cloud Provider Credentials**
   - Detects AWS access keys (AKIA...)
   - Detects Firebase/Google API keys (AIza...)
   - Detects OpenAI/Stripe secret keys (sk-...)
   - Detects GitHub/GitLab tokens

5. **Private Keys**
   - Identifies RSA, DSA, EC, or OpenSSH private keys
   - Prevents accidental key commits

6. **Database Connection Strings**
   - Detects PostgreSQL, MySQL, MongoDB, Redis connection strings
   - Warns about embedded credentials

## Installation

### Quick Installation

```bash
# Run the installation script
./scripts/install-pre-commit-hook.sh
```

The script will:
- Verify you're in a git repository
- Backup any existing pre-commit hook
- Install the new security validation hook
- Make the hook executable
- Optionally test the installation

### Manual Installation

```bash
# Copy the hook to .git/hooks/
cp scripts/pre-commit-check.sh .git/hooks/pre-commit

# Make it executable
chmod +x .git/hooks/pre-commit
```

## Usage

### Automatic Validation

Once installed, the hook runs automatically before every commit:

```bash
git add .
git commit -m "Your commit message"

# Hook runs automatically and validates changes
```

### Manual Testing

Test the hook without committing:

```bash
# Run validation on currently staged files
./scripts/pre-commit-check.sh
```

### Comprehensive Testing

Run the full test suite:

```bash
# Test all hook scenarios
./scripts/test-pre-commit-hook.sh
```

This will test:
- ✅ .env file blocking
- ✅ Hardcoded secret detection
- ✅ localStorage token usage
- ✅ AWS credential detection
- ✅ Private key detection
- ✅ Database connection string detection
- ✅ Safe commits (should pass)

### Bypassing the Hook (Not Recommended)

In rare cases where you need to bypass the hook:

```bash
git commit --no-verify -m "Emergency commit"
```

⚠️ **Warning**: Only use `--no-verify` when absolutely necessary and you're certain no sensitive data is being committed.

## CI/CD Integration

### GitHub Actions

The pre-commit validation is also enforced in CI/CD via GitHub Actions:

**Workflow**: `.github/workflows/pre-commit-validation.yml`

**Triggers**:
- Pull requests to `main`, `develop`, `docs-refactor-py313`
- Pushes to `main`, `develop`, `docs-refactor-py313`

**Jobs**:
1. **security-checks**: Validates PR changes for security issues
2. **pre-commit-hook-validation**: Tests hook functionality

### CI Checks

The CI workflow performs:
- Security validation on changed files
- Pre-commit hook functionality tests
- `.gitignore` validation
- Repository-wide secret scanning
- Environment variable usage validation

## Troubleshooting

### Hook Not Running

**Problem**: Commits go through without validation

**Solutions**:
```bash
# Verify hook is installed
ls -la .git/hooks/pre-commit

# Reinstall if missing
./scripts/install-pre-commit-hook.sh

# Verify it's executable
chmod +x .git/hooks/pre-commit
```

### False Positives

**Problem**: Hook blocks legitimate code

**Solutions**:
1. Review the flagged pattern
2. Ensure secrets are in environment variables
3. Update code to use `process.env` or `os.getenv()`
4. If absolutely necessary, use `--no-verify` with caution

### Hook Fails on Windows

**Problem**: Script doesn't run on Windows Git Bash

**Solutions**:
```bash
# Ensure Git Bash is being used
git config core.hooksPath .git/hooks

# Verify line endings
dos2unix scripts/pre-commit-check.sh

# Or set in git
git config core.autocrlf false
```

## File Organization

```
scripts/
├── README.md                      # This file
├── pre-commit-check.sh           # Main validation script
├── install-pre-commit-hook.sh    # Installation script
└── test-pre-commit-hook.sh       # Comprehensive test suite
```

## Best Practices

### For Developers

1. **Install hooks immediately** after cloning:
   ```bash
   ./scripts/install-pre-commit-hook.sh
   ```

2. **Use environment variables** for all secrets:
   ```javascript
   // ❌ Bad
   const apiKey = "sk_test_1234567890";

   // ✅ Good
   const apiKey = process.env.API_KEY;
   ```

3. **Use `.env.example`** for templates:
   ```bash
   # Create template
   cp .env .env.example

   # Remove actual values
   sed -i 's/=.*/=/' .env.example
   ```

4. **Test before committing**:
   ```bash
   # Stage your changes
   git add .

   # Test validation
   ./scripts/pre-commit-check.sh

   # Commit if validation passes
   git commit -m "Your message"
   ```

### For Teams

1. **Document in onboarding**:
   - Include hook installation in setup docs
   - Explain security rationale
   - Provide examples of proper secret management

2. **Regular updates**:
   - Review and update security patterns
   - Add new checks as threats evolve
   - Test hooks with each major change

3. **Security training**:
   - Educate on why these checks matter
   - Show examples of security incidents
   - Demonstrate proper secret management

## Security Incident Response

### If Secrets Are Committed

1. **Immediately rotate** the exposed credential
2. **Remove from git history**:
   ```bash
   # Use BFG Repo-Cleaner
   bfg --delete-files .env
   git reflog expire --expire=now --all
   git gc --prune=now --aggressive
   ```

3. **Force push** (coordinate with team):
   ```bash
   git push --force
   ```

4. **Notify security team** and affected services

### If Private Keys Are Committed

1. **Revoke the key immediately**
2. **Generate new keypair**
3. **Clean git history** (as above)
4. **Update deployment configurations**

## Related Documentation

- **Security Headers**: `backend-hormonia/docs/SECURITY_HEADERS.md`
- **localStorage Cleanup**: `docs/security/LOCALSTORAGE_CLEANUP_SUMMARY.md`
- **Rate Limiting**: `backend-hormonia/docs/RATE_LIMITING.md`
- **CSRF Protection**: `docs/security/csrf-protection-implementation.md`

## Support

### Questions or Issues?

1. Check this documentation
2. Review test output: `./scripts/test-pre-commit-hook.sh`
3. Check CI logs in GitHub Actions
4. Contact the security team

### Contributing

To improve the hooks:

1. Add new patterns to `pre-commit-check.sh`
2. Add corresponding tests to `test-pre-commit-hook.sh`
3. Update this documentation
4. Test thoroughly before committing

---

**Last Updated**: 2025-10-09
**Maintainer**: DevOps Team
**Version**: 1.0.0
