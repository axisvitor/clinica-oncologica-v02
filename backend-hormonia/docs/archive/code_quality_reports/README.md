# Code Quality Documentation

This directory contains documentation and tools for maintaining code quality in the Hormonia backend.

## 📋 Quick Start

### Run All Quality Checks

```bash
cd backend-hormonia

# Install tools
pip install ruff vulture eradicate interrogate autoflake radon

# Run all checks
python scripts/generate_code_quality_report.py
```

### Individual Checks

```bash
# Check unused imports
python scripts/remove_unused_imports.py --dry-run

# Check dead code
python scripts/detect_dead_code.py --output dead_code_report.txt

# Check commented code
python scripts/detect_commented_code.py --output commented_code_report.txt

# Check docstring coverage
python scripts/analyze_docstring_coverage.py --fail-under 95

# Check hardcoded regex
python scripts/audit_regex_patterns.py --json
```

## 📊 Quality Metrics

### Current Targets

| Metric | Target | Tool |
|--------|--------|------|
| Unused Imports | 0 | ruff |
| Dead Code | 0 | vulture |
| Commented Code | 0 lines | eradicate |
| Docstring Coverage | ≥95% | interrogate |
| Hardcoded Regex | 0 | custom |
| Code Complexity | ≤10 (Grade B) | radon |
| Maintainability | ≥20 (Grade A) | radon |

## 🛠️ Tools

### Automated Tools

1. **ruff**: Fast Python linter
   - Unused imports (F401)
   - Unused variables (F841)
   - Style violations (E)

2. **vulture**: Dead code detection
   - Min confidence: 80%
   - Finds unused functions, classes, variables

3. **eradicate**: Commented code detection
   - Removes commented-out code
   - Preserves TODO/FIXME comments

4. **interrogate**: Docstring coverage
   - Target: 95% coverage
   - Google-style docstrings

5. **autoflake**: Unused imports removal
   - Auto-removes unused imports
   - Removes unused variables

6. **radon**: Code metrics
   - Cyclomatic complexity
   - Maintainability index

### Custom Tools

7. **audit_regex_patterns.py**: Find hardcoded regex
8. **generate_code_quality_report.py**: Comprehensive report

## 📁 File Structure

```
docs/code-quality/
├── README.md                    # This file
├── DOCSTRING_GUIDE.md          # Docstring style guide
├── FINAL_REPORT.md             # Latest quality report
└── FINAL_REPORT.json           # Machine-readable report

scripts/
├── audit_regex_patterns.py     # Find hardcoded regex
├── remove_unused_imports.py    # Remove unused imports
├── detect_dead_code.py         # Find dead code
├── detect_commented_code.py    # Find commented code
├── analyze_docstring_coverage.py  # Check docstrings
├── generate_docstrings.py      # Generate templates
└── generate_code_quality_report.py  # Full report
```

## 🚀 Automation

### Pre-commit Hooks

Install pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
```

Hooks will run automatically on `git commit`:

- Autoflake (remove unused imports)
- Ruff (linting)
- Black (formatting)
- isort (import sorting)
- Vulture (dead code)
- Interrogate (docstrings)

### CI/CD Integration

GitHub Actions workflow runs on every push/PR:

```yaml
# .github/workflows/code-quality.yml
- Lint checks
- Format checks
- Security scans
- Quality report generation
```

## 📖 Documentation

### Docstring Guide

See [DOCSTRING_GUIDE.md](./DOCSTRING_GUIDE.md) for:
- Google-style docstring format
- Examples for functions, classes, methods
- Coverage requirements
- Tools and automation

### Example Usage

#### Remove Unused Imports

```bash
# Dry run (see what would change)
python scripts/remove_unused_imports.py --dry-run

# Actually remove
python scripts/remove_unused_imports.py

# Generate report only
python scripts/remove_unused_imports.py --report
```

#### Detect Dead Code

```bash
# Default (80% confidence)
python scripts/detect_dead_code.py

# Higher confidence
python scripts/detect_dead_code.py --min-confidence 90

# Generate removal script
python scripts/detect_dead_code.py --generate-script

# JSON output
python scripts/detect_dead_code.py --json
```

#### Check Docstrings

```bash
# Check coverage
python scripts/analyze_docstring_coverage.py --fail-under 95

# Generate HTML report
python scripts/analyze_docstring_coverage.py --html

# Find missing docstrings
python scripts/generate_docstrings.py
```

#### Generate Comprehensive Report

```bash
# Markdown report
python scripts/generate_code_quality_report.py

# Include JSON
python scripts/generate_code_quality_report.py --json

# Custom output
python scripts/generate_code_quality_report.py \
    --output my_report.md
```

## 🎯 Workflow

### Daily Development

1. Write code with proper docstrings
2. Pre-commit hooks run automatically
3. Fix any issues before commit
4. CI/CD validates on push

### Weekly Review

1. Run comprehensive quality report
2. Review and address issues
3. Update documentation
4. Track improvements over time

### Before Release

1. Ensure all quality gates pass
2. Review security scan results
3. Update CHANGELOG
4. Tag release

## 📈 Tracking Progress

### Quality Score

Overall score (0-100) calculated from:

- Unused imports (max -10 points)
- Dead code (max -15 points)
- Commented code (max -10 points)
- Docstring coverage (max -20 points)
- Hardcoded regex (max -5 points)

Target: ≥90/100 (Excellent)

### Reports

Generated reports are stored in:

- `docs/code-quality/FINAL_REPORT.md`
- `docs/code-quality/FINAL_REPORT.json`

Reports include:

- Overall score and status
- Metrics vs targets
- Recommendations
- Next steps

## 🔧 Configuration

### ruff.toml

```toml
[lint]
select = ["E", "F", "I"]
ignore = ["E501"]
```

### .eradicaterc

```
--whitelist=TODO
--whitelist=FIXME
--whitelist=NOTE
```

### pyproject.toml

```toml
[tool.interrogate]
fail-under = 95
exclude = ["tests", "migrations"]
```

## 🤝 Contributing

### Adding New Checks

1. Create script in `scripts/`
2. Add to `generate_code_quality_report.py`
3. Update CI/CD workflow
4. Document in this README

### Improving Tools

1. Fork and create feature branch
2. Add tests for new functionality
3. Update documentation
4. Submit pull request

## 📞 Support

For issues or questions:

1. Check existing documentation
2. Review tool help: `python script.py --help`
3. Check CI/CD logs
4. Open GitHub issue

## 📚 References

- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Vulture Documentation](https://github.com/jendrikseipp/vulture)
- [Interrogate Documentation](https://interrogate.readthedocs.io/)
- [Radon Documentation](https://radon.readthedocs.io/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
