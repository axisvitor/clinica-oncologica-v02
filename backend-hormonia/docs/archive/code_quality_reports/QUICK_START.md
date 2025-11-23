# Code Quality - Quick Start Guide

Get started with code quality tools in 5 minutes!

## 🚀 Installation (1 minute)

```bash
cd backend-hormonia

# Install all quality tools
make install-quality

# Or manually:
pip install ruff black isort vulture eradicate interrogate autoflake radon bandit safety
```

## ⚡ Quick Commands

### Daily Use

```bash
# Format code before committing
make format

# Check for issues (dry run)
make lint

# Fix issues automatically
make fix-all

# Run all quality checks
make quality
```

### Pre-commit Setup (One-time)

```bash
# Install pre-commit hooks
make pre-commit

# Now hooks run automatically on every commit!
git add .
git commit -m "Your message"  # Hooks run here
```

## 📊 Generate Report

```bash
# Get comprehensive quality report
make quality-report

# View results
cat docs/code-quality/FINAL_REPORT.md
```

## 🎯 Common Tasks

### 1. Remove Unused Imports

```bash
# See what would be removed (safe)
make unused-imports-dry

# Actually remove them
make unused-imports
```

### 2. Check Docstrings

```bash
# Check coverage (target: 95%)
make docstrings

# Find missing docstrings
python scripts/generate_docstrings.py
```

### 3. Find Dead Code

```bash
# Find unused code
make dead-code

# Review report
cat dead_code_report.txt
```

### 4. Check Hardcoded Regex

```bash
# Audit regex patterns
make regex-audit

# Review and extract to app/utils/regex_patterns.py
cat regex_audit_report.txt
```

## 🔧 Individual Tools

### Linting

```bash
# Check only
ruff check app/ tests/

# Auto-fix
ruff check app/ tests/ --fix

# Via Makefile
make lint
make lint-fix
```

### Formatting

```bash
# Format with black + isort
make format

# Check formatting (no changes)
make format-check
```

### Dead Code Detection

```bash
# Min confidence 80%
python scripts/detect_dead_code.py

# Higher confidence (90%)
python scripts/detect_dead_code.py --min-confidence 90

# JSON output
python scripts/detect_dead_code.py --json
```

### Docstring Coverage

```bash
# Check coverage
python scripts/analyze_docstring_coverage.py --fail-under 95

# Generate HTML report
python scripts/analyze_docstring_coverage.py --html

# Find missing docstrings with templates
python scripts/generate_docstrings.py
```

### Code Metrics

```bash
# Code complexity
make complexity

# Maintainability index
make maintainability

# Or directly:
radon cc app/ -a -s
radon mi app/ -s
```

## 📈 Understanding Reports

### Quality Score

- **90-100**: Excellent ✅
- **75-89**: Good 🟡
- **60-74**: Needs Improvement 🟠
- **< 60**: Poor ❌

### Metrics

| Metric | What It Means | Target |
|--------|---------------|--------|
| Unused Imports | Import statements not used | 0 |
| Dead Code | Code that's never executed | 0 |
| Docstring Coverage | % of functions with docs | ≥95% |
| Code Complexity | How complex functions are | ≤10 |
| Maintainability | How easy to maintain | ≥20 |

## 🔄 Workflow Examples

### Before Committing

```bash
# 1. Format code
make format

# 2. Fix linting issues
make lint-fix

# 3. Remove unused imports
make unused-imports

# 4. Commit (pre-commit hooks run automatically)
git add .
git commit -m "feat: add new feature"
```

### Weekly Review

```bash
# Generate comprehensive report
make quality-report

# Review specific issues
make dead-code
make docstrings
make regex-audit

# Read reports
cat docs/code-quality/FINAL_REPORT.md
cat dead_code_report.txt
cat missing_docstrings_report.txt
```

### Before Pull Request

```bash
# Run all checks
make check-all

# If issues found, fix them
make fix-all

# Verify everything passes
make quality-report
```

## 🛠️ Troubleshooting

### Pre-commit Hooks Failing

```bash
# Run manually to see errors
pre-commit run --all-files

# Update hooks
pre-commit autoupdate

# Skip hooks if needed (not recommended)
git commit --no-verify
```

### Tools Not Found

```bash
# Reinstall quality tools
make install-quality

# Or install individually
pip install ruff vulture eradicate interrogate
```

### High Complexity Warnings

If radon reports high complexity:

1. Break large functions into smaller ones
2. Extract nested loops/conditions
3. Use early returns to reduce nesting
4. Consider refactoring with design patterns

### Low Docstring Coverage

```bash
# Find missing docstrings
python scripts/generate_docstrings.py

# Generate template for specific function
python scripts/generate_docstrings.py \
    --add-to-file app/services/patient.py \
    --function create_patient \
    --line 45
```

## 📚 Learn More

- [Complete Guide](./README.md) - Comprehensive documentation
- [Docstring Guide](./DOCSTRING_GUIDE.md) - How to write good docstrings
- [Implementation Summary](./IMPLEMENTATION_SUMMARY_LOW_CLEANUP.md) - What was implemented

## 🆘 Getting Help

### Check Tool Help

```bash
python scripts/remove_unused_imports.py --help
python scripts/detect_dead_code.py --help
python scripts/analyze_docstring_coverage.py --help
```

### View Makefile Commands

```bash
make help
```

### CI/CD Logs

Check GitHub Actions for detailed CI/CD logs and reports.

---

## 🎯 Quick Reference Card

```bash
# SETUP (one-time)
make install-quality
make pre-commit

# DAILY USE
make format              # Format code
make lint-fix            # Fix lint issues
make unused-imports      # Remove unused imports

# BEFORE COMMIT
make fix-all             # Auto-fix everything

# WEEKLY REVIEW
make quality-report      # Full report
make dead-code           # Find dead code
make docstrings          # Check docs

# BEFORE RELEASE
make check-all           # All checks + tests
```

---

**Remember:** Quality tools are here to help, not hinder. Run them often and keep code clean!
