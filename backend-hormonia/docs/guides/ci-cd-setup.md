# CI/CD Pipeline Documentation

## Overview

This project uses GitHub Actions for Continuous Integration and Continuous Deployment (CI/CD). The pipeline is designed with production-grade practices including security scanning, automated testing, and deployment strategies.

## 🚀 Workflows

### 1. Continuous Integration (`ci.yml`)

**Triggers:**
- Push to `main`, `develop`, `docs-refactor-py313`
- Pull requests to these branches
- Manual dispatch

**Jobs:**
1. **Backend Linting** - Ruff, MyPy, import sorting
2. **Frontend Linting** - ESLint, TypeScript compiler
3. **Backend Tests** - pytest with PostgreSQL and Redis
4. **Frontend Tests** - Vitest with coverage
5. **Security Scan** - Bandit, Safety, npm audit
6. **Build Backend** - Docker image verification
7. **Build Frontend** - Production bundle build

**Status Checks:** All jobs must pass for PR merge

### 2. Staging Deployment (`cd-staging.yml`)

**Triggers:**
- Push to `develop` branch
- Manual dispatch

**Deployment Flow:**
```
Build Docker Images → Push to Registry → Deploy Backend (Railway) 
→ Deploy Frontend (Vercel) → E2E Tests → Smoke Tests → Notify
```

**Environments:**
- `staging-backend` - Railway environment
- `staging-frontend` - Vercel preview

**Automatic Rollback:** Not enabled (use manual intervention)

### 3. Production Deployment (`cd-production.yml`)

**Triggers:**
- Release tag (e.g., `v1.0.0`)
- Manual dispatch with approval

**Deployment Flow:**
```
Approval Required → Pre-deployment Checks → Build Production Images 
→ Deploy Backend → Deploy Frontend → Smoke Tests → Monitoring → Notifications
```

**Safety Features:**
- Manual approval required (unless skipped)
- Pre-deployment validation
- Health check verification
- 15-minute post-deployment monitoring
- Auto-rollback on failure
- Backup metadata saved

### 4. Security Scanning (`security.yml`)

**Triggers:**
- Push/PR to main branches
- Weekly schedule (Mondays at 9 AM Sao Paulo)
- Manual dispatch

**Scans:**
1. **Python Dependencies** - Safety, pip-audit
2. **JavaScript Dependencies** - npm audit
3. **Snyk** - Vulnerability scanning
4. **Bandit** - Python SAST
5. **CodeQL** - Multi-language analysis
6. **Semgrep** - Pattern-based security
7. **TruffleHog** - Secret detection
8. **Gitleaks** - Git secret scanning
9. **Trivy** - Container scanning
10. **OWASP Dependency Check**

**Reports:** Uploaded as artifacts and SARIF to GitHub Security

### 5. Pull Request Checks (`pr-checks.yml`)

**Automated Checks:**
- PR title validation (semantic format)
- Size labeling
- Breaking changes detection
- Database migration detection
- Test coverage reporting
- Secret scanning
- Changed files linting
- Auto-reviewer assignment

### 6. Release Management (`release.yml`)

**Triggers:**
- Tag push (`v*.*.*`)
- Manual dispatch

**Process:**
1. Validate release tag
2. Generate changelog
3. Build release artifacts
4. Create GitHub release
5. Publish Docker images
6. Update documentation
7. Create deployment issue
8. Send notifications

## 📋 Required Secrets

Configure these secrets in GitHub repository settings:

### General
- `GITHUB_TOKEN` - Automatically provided by GitHub
- `CODECOV_TOKEN` - For code coverage reporting

### Deployment
- `RAILWAY_TOKEN_STAGING` - Railway staging environment
- `RAILWAY_TOKEN_PRODUCTION` - Railway production environment
- `VERCEL_TOKEN` - Vercel deployment token
- `VERCEL_ORG_ID` - Vercel organization ID
- `VERCEL_PROJECT_ID` - Vercel project ID

### Security
- `SNYK_TOKEN` - Snyk security scanning
- `GITLEAKS_LICENSE` - Gitleaks license key (optional)

### Notifications
- `SLACK_WEBHOOK_URL` - General notifications
- `SLACK_WEBHOOK_SECURITY` - Security alerts
- `SLACK_WEBHOOK_CRITICAL` - Critical issues

## 🔧 Configuration Files

### Dependabot (`dependabot.yml`)
- Automated dependency updates
- Weekly schedule for Python and npm
- Monthly GitHub Actions updates
- Auto-labeling and assignment

### Code Owners (`CODEOWNERS`)
- Defines code ownership and review requirements
- Protects critical paths (workflows, migrations, security)
- Team-based review assignments

### Changelog Config (`changelog-config.json`)
- Automatic changelog generation
- Categorized by change type
- Semantic versioning support

## 🎯 Branch Protection Rules

Recommended settings for `main` branch:

```yaml
Require pull request reviews: 1 approver
Require status checks: 
  - ci-status
  - lint-backend
  - lint-frontend
  - test-backend
  - test-frontend
  - security-scan
Require branches to be up to date: true
Include administrators: false
Restrict pushes: true
Allow force pushes: false
Allow deletions: false
```

## 🚦 Deployment Strategy

### Staging
- **Trigger:** Every push to `develop`
- **Environment:** Isolated staging environment
- **Testing:** Full E2E and smoke tests
- **Rollback:** Manual intervention

### Production
- **Trigger:** Release tags only
- **Approval:** Required (configurable)
- **Monitoring:** 15 minutes post-deployment
- **Rollback:** Automatic on failure
- **Strategy:** Blue-green deployment

## 📊 Monitoring and Observability

### Health Checks
- Backend: `/api/health`, `/api/v2/health`
- Frontend: Root endpoint availability
- Database: Connection verification

### Metrics
- Build duration
- Test coverage
- Deployment success rate
- Mean time to recovery (MTTR)

### Alerts
- Slack notifications for:
  - Failed deployments
  - Security vulnerabilities
  - Critical errors
  - Release announcements

## 🔒 Security Best Practices

1. **Secret Management**
   - Never commit secrets to repository
   - Use GitHub Secrets for sensitive data
   - Rotate secrets regularly

2. **Dependency Management**
   - Automated updates via Dependabot
   - Weekly vulnerability scans
   - Security patches prioritized

3. **Code Scanning**
   - Multiple SAST tools (Bandit, Semgrep, CodeQL)
   - Container scanning with Trivy
   - Secret detection (TruffleHog, Gitleaks)

4. **Access Control**
   - Code owners for critical paths
   - Environment protection rules
   - Required approvals for production

## 🛠️ Maintenance

### Weekly Tasks
- Review security scan results
- Check dependency updates
- Monitor failed workflows

### Monthly Tasks
- Rotate deployment tokens
- Review and update branch protection
- Audit team access permissions

### Quarterly Tasks
- Review and optimize workflow performance
- Update CI/CD documentation
- Security audit of pipeline

## 📚 Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Railway Deployment Guide](https://docs.railway.app/)
- [Vercel Deployment Guide](https://vercel.com/docs)
- [Security Best Practices](https://docs.github.com/en/code-security)

## 🆘 Troubleshooting

### Common Issues

**Workflow fails on dependency installation:**
```bash
# Clear cache and retry
gh workflow run ci.yml --ref your-branch
```

**Docker build fails:**
```bash
# Check Docker build locally
cd backend-hormonia
docker build --no-cache -t test .
```

**E2E tests timeout:**
- Check Playwright configuration
- Verify staging environment accessibility
- Review network connectivity

**Deployment stuck in approval:**
- Check GitHub environment settings
- Verify required reviewers availability
- Use manual dispatch to skip approval (emergency only)

## 📞 Support

For CI/CD related issues:
1. Check workflow logs in GitHub Actions tab
2. Review this documentation
3. Contact DevOps team via Slack
4. Create issue with `ci/cd` label
