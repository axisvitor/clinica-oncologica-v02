# Dependency Management Policy

This document outlines the dependency management strategy for Backend Hormonia.

## Overview

Proper dependency management is critical for:
- **Security:** Patching vulnerabilities quickly
- **Stability:** Avoiding breaking changes
- **Performance:** Leveraging improvements in libraries
- **Compliance:** Meeting audit requirements

---

## Automated Dependency Updates

### Dependabot Configuration

Dependabot automatically creates pull requests for dependency updates.

**Configuration:** `/.github/dependabot.yml`

**Schedule:**
- **Python dependencies:** Weekly on Mondays
- **GitHub Actions:** Weekly on Mondays
- **Docker images:** Weekly on Tuesdays

**Update Strategy:**
- **Security updates:** Immediate
- **Patch updates:** Grouped weekly
- **Minor updates:** Grouped weekly
- **Major updates:** Individual PRs with manual review

---

## Dependency Update Workflow

### 1. Automated PR Creation

Dependabot creates PRs automatically:

```
Title: chore(deps): bump fastapi from 0.104.1 to 0.105.0
Labels: dependencies, python, automated
```

### 2. Automated Testing

CI/CD runs automatically:
- Unit tests
- Integration tests
- Security scan
- Performance benchmarks

### 3. Manual Review

For major version updates, review:
- **Changelog:** What changed?
- **Breaking changes:** Any incompatibilities?
- **Migration guide:** What needs updating?
- **Test coverage:** Are tests still passing?

### 4. Approval and Merge

- **Patch/Minor + Tests Pass:** Auto-merge eligible
- **Major updates:** Require manual approval
- **Security updates:** Priority merge

---

## Security Vulnerability Management

### Severity Levels

| Severity | Response Time | Action |
|----------|---------------|--------|
| **CRITICAL** | Immediate (24h) | Emergency patch + deploy |
| **HIGH** | 7 days | Priority update |
| **MEDIUM** | 30 days | Regular update cycle |
| **LOW** | Next release | Include in routine updates |

### Security Scanning

#### pip-audit (Primary)

```bash
# Weekly automated scan
pip-audit -r requirements.txt

# Check specific package
pip-audit -r requirements.txt --vulnerable-package fastapi
```

#### Safety (Secondary)

```bash
# Safety database scan
safety check -r requirements.txt

# Generate JSON report
safety check --json -r requirements.txt > safety-report.json
```

#### Snyk (Optional)

```bash
# Install Snyk
npm install -g snyk

# Test for vulnerabilities
snyk test --file=requirements.txt

# Monitor project
snyk monitor --file=requirements.txt
```

---

## Dependency Update Types

### Patch Updates (0.0.X)

**Example:** `fastapi 0.104.1` → `fastapi 0.104.2`

**Characteristics:**
- Bug fixes only
- No breaking changes
- Low risk

**Process:**
1. Automated PR created
2. Tests run automatically
3. Auto-merge if tests pass

### Minor Updates (0.X.0)

**Example:** `fastapi 0.104.1` → `fastapi 0.105.0`

**Characteristics:**
- New features (backward compatible)
- Deprecation warnings possible
- Medium risk

**Process:**
1. Automated PR created
2. Tests + compatibility check
3. Manual review recommended
4. Merge after approval

### Major Updates (X.0.0)

**Example:** `fastapi 0.104.1` → `fastapi 1.0.0`

**Characteristics:**
- Breaking changes likely
- Migration required
- High risk

**Process:**
1. Individual PR created
2. Comprehensive testing required
3. Review changelog thoroughly
4. Update code for compatibility
5. Staged rollout

---

## Manual Dependency Updates

### Check for Outdated Packages

```bash
# List outdated packages
pip list --outdated

# JSON format for scripting
pip list --outdated --format=json
```

### Update Specific Package

```bash
# Update single package
pip install --upgrade fastapi

# Update with version constraint
pip install 'fastapi>=0.105.0,<0.106.0'

# Freeze new version
pip freeze | grep fastapi >> requirements.txt
```

### Update All Dependencies

```bash
# ⚠️ Use with caution - can break things
pip install --upgrade -r requirements.txt

# Better: Use pip-tools for controlled updates
pip-compile --upgrade requirements.in
```

---

## Dependency Health Monitoring

### Weekly Health Report

Automated report generation:

```bash
# Generate health report
python scripts/dependency_report.py

# Output: docs/dependencies/DEPENDENCY_HEALTH_REPORT.md
```

**Report includes:**
- Outdated packages count
- Security vulnerabilities
- Dependency tree complexity
- Health score (0-100)
- Actionable recommendations

### Metrics Tracked

1. **Outdated packages:** Target < 10%
2. **Vulnerabilities:** Target = 0 critical/high
3. **Dependency count:** Monitor growth
4. **Dependency age:** Flag packages > 2 years old

---

## Best Practices

### 1. Pin Exact Versions

**❌ Bad:**
```txt
fastapi>=0.104.0
sqlalchemy~=2.0
```

**✅ Good:**
```txt
fastapi==0.104.1
sqlalchemy==2.0.23
```

**Rationale:**
- Reproducible builds
- Prevent unexpected breakage
- Easier debugging

### 2. Use requirements.in + pip-tools

**Structure:**
```
requirements.in     # High-level dependencies
requirements.txt    # Pinned dependencies (generated)
```

**Workflow:**
```bash
# Edit requirements.in
vim requirements.in

# Generate pinned requirements.txt
pip-compile requirements.in

# Install dependencies
pip install -r requirements.txt
```

### 3. Separate Dev Dependencies

```
requirements.txt          # Production dependencies
requirements-dev.txt      # Development dependencies
requirements-test.txt     # Test dependencies
```

### 4. Regular Dependency Audits

**Monthly checklist:**
- [ ] Review all outdated packages
- [ ] Check for security vulnerabilities
- [ ] Remove unused dependencies
- [ ] Update documentation
- [ ] Test compatibility

### 5. Document Breaking Changes

When updating major versions:

```markdown
## Migration: FastAPI 0.x → 1.x

### Breaking Changes
1. `JSONResponse` import changed
   - Before: `from fastapi.responses import JSONResponse`
   - After: `from starlette.responses import JSONResponse`

2. Dependency injection updated
   - See: https://fastapi.tiangolo.com/migration/

### Testing Checklist
- [ ] All API endpoints tested
- [ ] Authentication still works
- [ ] Websockets functional
```

---

## Dependency Approval Process

### Low-Risk Updates (Auto-Approve)

- Patch version updates
- No test failures
- No security warnings
- Dependency count < 5 new packages

### Medium-Risk Updates (Review Required)

- Minor version updates
- New features added
- Deprecation warnings
- Dependency count 5-10 new packages

### High-Risk Updates (Approval + Testing)

- Major version updates
- Breaking changes documented
- Migration guide available
- Dependency count > 10 new packages
- Security-sensitive packages (auth, crypto)

---

## Rollback Procedures

### If Update Breaks Production

1. **Immediate rollback:**
   ```bash
   # Revert PR
   git revert <commit-hash>

   # Or rollback to previous version
   pip install fastapi==0.104.1
   ```

2. **Investigate issue:**
   - Check error logs
   - Review changelog
   - Test in staging

3. **Fix or defer:**
   - Fix compatibility issue
   - Or defer update until fix available

4. **Document incident:**
   - Update dependency notes
   - Add test case for regression
   - Share learnings with team

---

## Dependency Licensing

### Allowed Licenses

✅ Permissive licenses:
- MIT
- Apache 2.0
- BSD (2/3-clause)
- Python Software Foundation
- ISC

⚠️ Copyleft licenses (review required):
- GPL (v2/v3)
- LGPL
- MPL

❌ Prohibited:
- Proprietary
- Custom restrictive licenses

### License Audit

```bash
# Install license checker
pip install pip-licenses

# Check all licenses
pip-licenses

# Export to CSV
pip-licenses --format=csv > licenses.csv

# Check for prohibited licenses
pip-licenses | grep -E 'GPL|AGPL'
```

---

## Dependency Tree Management

### Keep Dependencies Flat

**❌ Bad:**
```
fastapi → pydantic → typing-extensions
         ↘ starlette → anyio
```
Deep dependency trees increase risk.

**✅ Good:**
```
fastapi
sqlalchemy
redis
```
Direct dependencies only.

### Minimize Transitive Dependencies

```bash
# Show dependency tree
pip install pipdeptree
pipdeptree

# Find circular dependencies
pipdeptree --warn fail
```

---

## Troubleshooting

### Issue: Dependency Conflict

**Error:**
```
ERROR: Cannot install fastapi 0.105.0 because these package versions have conflicting dependencies:
  pydantic 2.0.0 (required by fastapi 0.105.0)
  pydantic 1.10.0 (required by other-package)
```

**Solution:**
```bash
# Find conflicting packages
pip install pip-check
pip-check

# Resolve manually or use pip-tools
pip-compile --upgrade --resolver=backtracking
```

### Issue: Broken After Update

**Solution:**
```bash
# Rollback to known good state
git checkout requirements.txt HEAD~1
pip install -r requirements.txt

# Test
pytest

# If working, identify problematic package
git diff HEAD~1 requirements.txt
```

---

## CI/CD Integration

### GitHub Actions Checks

Every PR must pass:

1. **Dependency audit** - Zero critical vulnerabilities
2. **License check** - All licenses approved
3. **Test suite** - All tests passing
4. **Security scan** - Bandit + Safety clean

### Automated Weekly Jobs

- **Monday 00:00 UTC:** Generate dependency health report
- **Monday 09:00 UTC:** Create update PRs (Dependabot)
- **Sunday 02:00 UTC:** Security vulnerability scan

---

## Emergency Security Patch Process

### When Critical Vulnerability Announced

1. **Assess impact** (15 min)
   - Check if we use affected package
   - Determine if vulnerability applies
   - Review patch availability

2. **Create emergency PR** (30 min)
   ```bash
   git checkout -b security/CVE-2024-XXXX
   pip install --upgrade vulnerable-package
   pytest
   git commit -m "security: patch CVE-2024-XXXX"
   ```

3. **Fast-track review** (30 min)
   - Security team review
   - Abbreviated testing (critical paths only)
   - Deploy to staging

4. **Production deploy** (1 hour)
   - Deploy during business hours if possible
   - Monitor for 2 hours post-deployment
   - Document in incident log

**Total time:** 2-3 hours from disclosure to production

---

## Resources

### Tools

- **Dependabot:** Automated updates
- **pip-audit:** Vulnerability scanning
- **Safety:** Security checks
- **pip-tools:** Dependency compilation
- **pipdeptree:** Dependency visualization

### External Links

- [Python Packaging Guide](https://packaging.python.org/)
- [PEP 440 - Version Specification](https://peps.python.org/pep-0440/)
- [OWASP Dependency Check](https://owasp.org/www-project-dependency-check/)
- [Snyk Vulnerability Database](https://snyk.io/vuln/)

---

## Support

**Questions:** backend-team@hormonia.com.br
**Security incidents:** security@hormonia.com.br
**Dependency issues:** File a ticket in Jira

**Last Updated:** 2025-01-16
**Version:** 1.0.0
**Next Review:** 2025-02-16
