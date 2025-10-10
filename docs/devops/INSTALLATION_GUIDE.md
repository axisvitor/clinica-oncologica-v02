# Pre-Commit Hook Installation Guide

## Quick Installation

### Option 1: Automated Installation (Recommended)

```bash
# Navigate to project root
cd /path/to/clinica-oncologica-v02

# Run installation script
./scripts/install-pre-commit-hook.sh

# Expected output:
# ✅ Made pre-commit script executable
# ✅ Created pre-commit hook at: .git/hooks/pre-commit
# ╔════════════════════════════════════════════════════════╗
# ║  ✅ PRE-COMMIT HOOK INSTALLED SUCCESSFULLY             ║
# ╚════════════════════════════════════════════════════════╝
```

### Option 2: Manual Installation

```bash
# 1. Make pre-commit script executable
chmod +x scripts/pre-commit-check.sh

# 2. Create hook wrapper
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/sh
REPO_ROOT=$(git rev-parse --show-toplevel)
PRE_COMMIT_SCRIPT="$REPO_ROOT/scripts/pre-commit-check.sh"

if [ ! -f "$PRE_COMMIT_SCRIPT" ]; then
    echo "ERROR: Pre-commit script not found"
    exit 1
fi

if [ ! -x "$PRE_COMMIT_SCRIPT" ]; then
    chmod +x "$PRE_COMMIT_SCRIPT"
fi

exec "$PRE_COMMIT_SCRIPT"
EOF

# 3. Make hook executable
chmod +x .git/hooks/pre-commit
```

### Option 3: Windows Installation

```powershell
# PowerShell
# 1. Navigate to project root
cd C:\path\to\clinica-oncologica-v02

# 2. Run installation via Git Bash (recommended)
& "C:\Program Files\Git\bin\bash.exe" -c "./scripts/install-pre-commit-hook.sh"

# Or install manually
Copy-Item scripts\pre-commit-check.sh .git\hooks\pre-commit
```

## Verification

### Test Installation

```bash
# Run test script
./scripts/test-pre-commit-hook.sh

# Expected output:
# 🧪 Testing Pre-Commit Hook
# ================================
# Test 1: Checking hook installation...
# ✅ Pre-commit hook is installed and executable
# Test 2: Running hook with no staged changes...
# ✅ Hook passes with no staged changes
# ...
```

### Manual Verification

```bash
# 1. Check if hook exists
ls -l .git/hooks/pre-commit

# Expected: -rwxr-xr-x (executable permissions)

# 2. Check if script exists
ls -l scripts/pre-commit-check.sh

# Expected: -rwxr-xr-x (executable permissions)

# 3. Test hook manually
./scripts/pre-commit-check.sh

# Expected:
# ✅ ALL PRE-COMMIT CHECKS PASSED
```

## Team Setup

### For New Team Members

Add to onboarding documentation:

```bash
# After cloning repository
git clone <repository-url>
cd clinica-oncologica-v02

# Install pre-commit hook
./scripts/install-pre-commit-hook.sh

# Verify installation
./scripts/test-pre-commit-hook.sh
```

### Automated Setup in README.md

Add to project README:

```markdown
## Setup

1. Clone repository
2. Install dependencies
3. **Install pre-commit hooks**: `./scripts/install-pre-commit-hook.sh`
4. Configure environment variables
```

## CI/CD Integration

The pre-commit hook validation is integrated into GitHub Actions:

**Workflow:** `.github/workflows/pre-commit-validation.yml`

**Checks on every PR:**
- ✅ .env file detection
- ✅ Firebase key detection
- ✅ Secret scanning with Gitleaks
- ✅ Hardcoded credential detection
- ✅ Hook script validation
- ✅ Documentation verification

## Troubleshooting

### Hook Not Running

**Problem:** Commits go through without hook execution

**Solution:**
```bash
# Check if hook exists
ls -l .git/hooks/pre-commit

# If not found, reinstall
./scripts/install-pre-commit-hook.sh

# Verify permissions
chmod +x .git/hooks/pre-commit
chmod +x scripts/pre-commit-check.sh
```

### Permission Denied

**Problem:** `permission denied: .git/hooks/pre-commit`

**Solution:**
```bash
chmod +x .git/hooks/pre-commit
```

### Script Not Found

**Problem:** `ERROR: Pre-commit script not found`

**Solution:**
```bash
# Verify script exists
ls -l scripts/pre-commit-check.sh

# Reinstall
./scripts/install-pre-commit-hook.sh
```

### Windows Line Endings

**Problem:** `bad interpreter: No such file or directory`

**Solution:**
```bash
# Convert line endings to Unix format
dos2unix scripts/pre-commit-check.sh
dos2unix .git/hooks/pre-commit

# Or use git
git config core.autocrlf false
git rm --cached scripts/pre-commit-check.sh
git reset --hard
```

### Hook Fails Unexpectedly

**Problem:** Hook fails on valid commits

**Solution:**
```bash
# Run hook manually to see detailed output
./scripts/pre-commit-check.sh

# Check git status
git status

# Review staged files
git diff --cached --name-only

# If necessary, bypass temporarily
git commit --no-verify -m "message"
# (Only use when absolutely necessary!)
```

## Updating Hooks

### Update Hook Script

```bash
# 1. Edit the script
vim scripts/pre-commit-check.sh

# 2. Test changes
./scripts/pre-commit-check.sh

# 3. Reinstall hook
./scripts/install-pre-commit-hook.sh

# 4. Verify
./scripts/test-pre-commit-hook.sh
```

### Add Custom Checks

Edit `scripts/pre-commit-check.sh`:

```bash
# Add custom pattern detection
if git diff --cached | grep -E "YOUR_PATTERN"; then
    echo "⚠️  WARNING: Custom pattern detected"
    ISSUES_FOUND=1
fi
```

## Uninstallation

### Remove Hook

```bash
# Remove hook file
rm .git/hooks/pre-commit

# Verify removal
ls -l .git/hooks/pre-commit
# Expected: No such file or directory
```

### Disable Temporarily

```bash
# Rename to disable
mv .git/hooks/pre-commit .git/hooks/pre-commit.disabled

# Re-enable later
mv .git/hooks/pre-commit.disabled .git/hooks/pre-commit
```

## Best Practices

1. **Always run installation script** after cloning repository
2. **Test hook** before first commit
3. **Never bypass** without valid reason
4. **Update documentation** when modifying hooks
5. **Run test script** after hook updates
6. **Check CI/CD** for additional validation

## Related Documentation

- [Pre-Commit Hooks Overview](PRE_COMMIT_HOOKS.md)
- [Security Best Practices](../SECURITY_IMPROVEMENTS_2025-10-08.md)
- [CI/CD Workflows](../../.github/workflows/README.md)

## Support

For issues:
1. Check troubleshooting section above
2. Run test script: `./scripts/test-pre-commit-hook.sh`
3. Review hook output carefully
4. Check GitHub Actions logs
5. Contact DevOps team

---

**Last Updated:** 2025-10-09
**Version:** 1.0.0
