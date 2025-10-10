# Pre-Commit Hook - Quick Reference Card

## 🚀 Quick Installation

```bash
./scripts/install-pre-commit-hook.sh
```

## ✅ Verify Installation

```bash
./scripts/test-pre-commit-hook.sh
```

## 🔒 What Gets Blocked

### ❌ ALWAYS BLOCKED
- `.env` files (all variants)
- `.env.local`, `.env.production`, `.env.staging`
- `firebase-adminsdk-*.json`
- `serviceAccountKey.json`

### ✅ ALLOWED
- `.env.example`
- `.env.*.example`
- `.env.sentry.example`

## ⚠️ What Gets Warned

- Hardcoded API keys
- Passwords in code
- Secret keys
- Access tokens
- Private keys
- Database URLs

## 🛠️ Common Workflows

### Normal Commit (Hook Runs Automatically)
```bash
git add .
git commit -m "Your message"

# Hook runs automatically
# ✅ Passes → Commit succeeds
# ❌ Fails → Commit blocked
```

### If Hook Blocks Your Commit

**1. Check what was blocked:**
```bash
git status
git diff --cached --name-only
```

**2. Remove sensitive files:**
```bash
git reset HEAD .env
git reset HEAD firebase-adminsdk-*.json
```

**3. Add to .gitignore:**
```bash
echo ".env" >> .gitignore
echo "firebase-adminsdk-*.json" >> .gitignore
```

**4. Use .env.example instead:**
```bash
# Good: Create template
cp .env .env.example
# Edit .env.example to remove real values
vim .env.example
# Replace secrets with placeholders
git add .env.example
```

### Emergency Bypass (NOT RECOMMENDED)

```bash
# Only use when absolutely necessary
git commit --no-verify -m "Emergency commit"

# ⚠️ WARNING: CI/CD will still validate!
```

## 🔍 Manual Testing

### Test Hook Directly
```bash
./scripts/pre-commit-check.sh
```

### Test With Specific File
```bash
# Stage a test file
echo "SECRET_KEY=test123" > test.py
git add test.py

# Run hook
./scripts/pre-commit-check.sh

# Expected: ⚠️ WARNING detected

# Clean up
git reset HEAD test.py
rm test.py
```

## 🐛 Troubleshooting

### Hook Not Running
```bash
# Check if installed
ls -l .git/hooks/pre-commit

# Reinstall if missing
./scripts/install-pre-commit-hook.sh
```

### Permission Denied
```bash
chmod +x .git/hooks/pre-commit
chmod +x scripts/pre-commit-check.sh
```

### False Positive
```bash
# Review what triggered warning
./scripts/pre-commit-check.sh

# If legitimate:
# 1. Update code to use env vars
# 2. Or bypass (last resort)
git commit --no-verify
```

## 📊 Status Messages

### ✅ Success
```
🔒 Running pre-commit security checks...
  1️⃣ Checking for .env files...
  ✅ No .env files staged
  2️⃣ Scanning for potential secrets...
  ✅ No secrets detected
  3️⃣ Checking CSRF configuration...
  4️⃣ Verifying .gitignore coverage...
  ✅ .gitignore properly configured

✅ All pre-commit security checks passed
```

### ❌ Blocked
```
🔒 Running pre-commit security checks...
  1️⃣ Checking for .env files...

❌ ERROR: .env files cannot be committed

The following .env files are staged for commit:
  - .env

💡 Solution:
  1. Unstage .env files: git reset HEAD .env*
  2. Add secrets to .env.example as placeholders
  3. Ensure .env* is in .gitignore
```

### ⚠️ Warning
```
🔒 Running pre-commit security checks...
  ...
  2️⃣ Scanning for potential secrets...

⚠️  WARNING: Potential secrets detected in commit

The following files contain patterns that might be secrets:
  config.py:
    + SECRET_KEY = "actual-secret-here"

💡 Before committing, verify that:
  1. No actual API keys, passwords, or tokens are present
  2. Use environment variables for secrets
  3. Use placeholders like 'your-secret-here'
```

## 💡 Best Practices

### DO ✅
- Use `.env.example` for documentation
- Store secrets in environment variables
- Use placeholders in example files
- Test hook after installation
- Review warnings carefully

### DON'T ❌
- Commit `.env` files
- Hardcode secrets in code
- Bypass hook without reason
- Share secrets in chat/email
- Reuse secrets across projects

## 🔗 Related Commands

```bash
# View current git status
git status

# See what's staged
git diff --cached

# Unstage file
git reset HEAD <file>

# Check .gitignore
cat .gitignore | grep env

# Test hook manually
./scripts/pre-commit-check.sh

# Full test suite
./scripts/test-pre-commit-hook.sh
```

## 📚 Documentation

- **Full Specification:** `docs/devops/PRE_COMMIT_HOOKS.md`
- **Installation Guide:** `docs/devops/INSTALLATION_GUIDE.md`
- **Implementation Summary:** `docs/devops/PRE_COMMIT_IMPLEMENTATION_SUMMARY.md`
- **Scripts README:** `scripts/README.md`

## 🆘 Getting Help

1. **Check documentation** (links above)
2. **Run test script:** `./scripts/test-pre-commit-hook.sh`
3. **Review CI/CD logs** (GitHub Actions)
4. **Ask in #devops** channel

## ⚡ One-Liners

```bash
# Install + Test
./scripts/install-pre-commit-hook.sh && ./scripts/test-pre-commit-hook.sh

# Check if .env is staged
git diff --cached --name-only | grep .env

# Unstage all .env files
git reset HEAD .env*

# View hook output
./scripts/pre-commit-check.sh

# Force reinstall
rm .git/hooks/pre-commit && ./scripts/install-pre-commit-hook.sh
```

---

**Quick Start:** `./scripts/install-pre-commit-hook.sh`
**Test:** `./scripts/test-pre-commit-hook.sh`
**Help:** `docs/devops/PRE_COMMIT_HOOKS.md`

**Version:** 1.0.0 | **Updated:** 2025-10-09
