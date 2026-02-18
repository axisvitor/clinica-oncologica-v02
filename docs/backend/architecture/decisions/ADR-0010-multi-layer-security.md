# ADR-0010: Multi-Layer Security Scanning (7 Layers)

## Status

Accepted

Date: 2024-01-24

## Context

The Clínica Hormonia system handles sensitive medical data (HIPAA/LGPD compliant) and requires comprehensive security measures:
- **Patient health information (PHI)**: Highly sensitive medical data
- **Compliance**: HIPAA (US), LGPD (Brazil), GDPR (EU) requirements
- **Attack surface**: API, database, external integrations, frontend
- **Threat actors**: External attackers, insider threats, accidental exposure
- **Security incidents**: Data breaches can result in fines, legal action, reputation damage

Current security gaps:
- No automated security scanning in CI/CD
- Dependencies not regularly audited
- Secrets potentially committed to git
- No runtime security monitoring
- Limited security testing beyond manual reviews

We need a comprehensive, multi-layer security approach that:
- Prevents security issues before production
- Detects vulnerabilities in dependencies
- Scans for secrets and credentials
- Validates infrastructure security
- Monitors runtime threats
- Provides audit trails
- Integrates with development workflow

## Decision

We will implement **7-layer security scanning** integrated into CI/CD pipeline and runtime monitoring:

### Layer 1: Secret Scanning
- Detect secrets in code, config, and git history
- Tools: TruffleHog, GitGuardian, detect-secrets

### Layer 2: Dependency Vulnerability Scanning
- Scan Python and JavaScript dependencies for known CVEs
- Tools: Safety, pip-audit, Snyk, npm audit

### Layer 3: Static Code Analysis (SAST)
- Analyze source code for security vulnerabilities
- Tools: Bandit (Python), ESLint security plugins, Semgrep

### Layer 4: Container Security Scanning
- Scan Docker images for vulnerabilities
- Tools: Trivy, Clair, Anchore

### Layer 5: Infrastructure as Code Scanning
- Validate Terraform/CloudFormation security
- Tools: tfsec, Checkov, CloudSploit

### Layer 6: Dynamic Application Security Testing (DAST)
- Test running application for vulnerabilities
- Tools: OWASP ZAP, Burp Suite, Nuclei

### Layer 7: Runtime Security Monitoring
- Detect threats in production
- Tools: Falco, OSSEC, Sentry Security

## Consequences

### Positive Consequences

- **Early detection**: Find vulnerabilities before production
- **Compliance**: Meet HIPAA/LGPD security requirements
- **Automation**: Security checks in every build
- **Visibility**: Security metrics and dashboards
- **Prevention**: Block insecure code from merging
- **Audit trail**: Track all security findings
- **Developer awareness**: Educate team on security
- **Cost savings**: Fix issues early (cheaper than post-breach)

### Negative Consequences

- **Build time**: Security scans add 5-10 minutes to CI/CD
- **False positives**: Some tools generate noise
- **Maintenance**: Need to keep tools updated
- **Learning curve**: Team needs security training
- **Tool fatigue**: Many tools to manage

### Risks

- **Scan fatigue**: Developers might ignore warnings
- **Tool bypass**: Developers might skip security checks
- **Zero-day vulnerabilities**: Scanners can't detect unknown exploits
- **Configuration errors**: Misconfigured tools may miss issues
- **Performance impact**: Runtime monitoring could slow production

## Alternatives Considered

### Alternative 1: Manual Security Reviews Only

**Description**: Rely on manual code reviews and penetration testing

**Pros**:
- Human expertise and context
- No tool overhead
- Flexible approach

**Cons**:
- Slow and expensive
- Inconsistent coverage
- Not scalable
- Misses known vulnerabilities
- No continuous monitoring

**Why rejected**: Can't scale with development velocity

### Alternative 2: Single Comprehensive Tool (Snyk Premium)

**Description**: Use one paid tool for all security scanning

**Pros**:
- Single vendor
- Integrated dashboard
- Good coverage
- Professional support

**Cons**:
- Expensive ($500-2000/month)
- Vendor lock-in
- May miss edge cases
- Not specialized per layer

**Why rejected**: Cost prohibitive, prefer best-of-breed approach

### Alternative 3: HIPAA Compliance Service

**Description**: Use managed HIPAA compliance service (Aptible, etc.)

**Pros**:
- Compliance handled
- Infrastructure managed
- Audit trails included

**Cons**:
- Very expensive ($1000-5000/month)
- Platform lock-in
- Less flexibility
- Not addressing code-level security

**Why rejected**: Doesn't address application security, only infrastructure

### Alternative 4: Security as Manual Gate

**Description**: Require security team approval before deployment

**Pros**:
- Expert review
- Thorough analysis
- Compliance focused

**Cons**:
- Slow deployment
- Security team bottleneck
- Not sustainable at scale
- Misses automated checks

**Why rejected**: Too slow for continuous deployment

## Implementation Notes

### Layer 1: Secret Scanning

```yaml
# .github/workflows/security-secrets.yml
name: Secret Scanning

on: [push, pull_request]

jobs:
  trufflehog:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0  # Full history for TruffleHog

      - name: TruffleHog OSS
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./
          base: ${{ github.event.repository.default_branch }}
          head: HEAD
          extra_args: --debug --only-verified

  detect-secrets:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Detect Secrets
        uses: reviewdog/action-detect-secrets@master
        with:
          reporter: github-pr-review
          fail_on_error: true
```

### Layer 2: Dependency Scanning

```yaml
# .github/workflows/security-dependencies.yml
name: Dependency Security

on: [push, pull_request]

jobs:
  python-deps:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: pip install safety pip-audit

      - name: Safety check
        run: safety check --json --output safety-report.json
        continue-on-error: true

      - name: pip-audit
        run: pip-audit -r requirements.txt

  npm-deps:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: npm audit
        run: npm audit --audit-level=moderate
        working-directory: frontend-hormonia
```

### Layer 3: Static Code Analysis

```yaml
# .github/workflows/security-sast.yml
name: Static Analysis Security Testing

on: [push, pull_request]

jobs:
  bandit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Bandit Security Linter
        uses: jpetrucciani/bandit-report@main
        with:
          path: backend-hormonia
          level: medium
          confidence: medium
          exit-zero: false

  semgrep:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Semgrep
        uses: returntocorp/semgrep-action@v1
        with:
          config: >-
            p/security-audit
            p/owasp-top-ten
            p/python
```

### Layer 4: Container Scanning

```yaml
# .github/workflows/security-containers.yml
name: Container Security

on: [push, pull_request]

jobs:
  trivy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Build image
        run: docker build -t hormonia-backend:latest -f backend-hormonia/Dockerfile .

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'hormonia-backend:latest'
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'

      - name: Upload Trivy results to GitHub Security
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: 'trivy-results.sarif'
```

### Layer 5: Infrastructure Scanning

```yaml
# .github/workflows/security-infrastructure.yml
name: Infrastructure Security

on: [push, pull_request]

jobs:
  checkov:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run Checkov
        uses: bridgecrewio/checkov-action@master
        with:
          directory: infrastructure/
          framework: terraform,dockerfile,kubernetes
          output_format: sarif
          output_file_path: checkov-results.sarif
```

### Layer 6: DAST Scanning

```bash
# scripts/security/dast-scan.sh
#!/bin/bash

# Run OWASP ZAP scan against staging environment
docker run --rm \
  -v $(pwd)/zap-reports:/zap/wrk/:rw \
  owasp/zap2docker-stable \
  zap-baseline.py \
  -t https://staging.hormonia.com \
  -g gen.conf \
  -r zap-report.html \
  -J zap-report.json

# Check for high severity issues
HIGH_ALERTS=$(jq '.site[0].alerts | map(select(.riskcode == "3")) | length' zap-report.json)

if [ "$HIGH_ALERTS" -gt 0 ]; then
  echo "❌ Found $HIGH_ALERTS high severity issues"
  exit 1
fi
```

### Layer 7: Runtime Security

```python
# app/monitoring/security_monitoring.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

# Initialize Sentry with security monitoring
sentry_sdk.init(
    dsn="https://...",
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,
    profiles_sample_rate=0.1,

    # Security-specific configuration
    send_default_pii=False,  # Don't send PHI to Sentry
    before_send=scrub_sensitive_data,
)

def scrub_sensitive_data(event, hint):
    """Remove PHI from error reports"""
    # Scrub request data
    if 'request' in event:
        if 'data' in event['request']:
            event['request']['data'] = '[REDACTED]'

    # Scrub user data
    if 'user' in event:
        event['user'] = {
            'id': event['user'].get('id'),
            # Remove email, name, etc.
        }

    return event

# Runtime anomaly detection
async def detect_anomalies(request: Request):
    """Detect suspicious patterns"""
    # Rate limiting violations
    # Unusual data access patterns
    # SQL injection attempts
    # XSS attempts
    pass
```

### Security Dashboard

```python
# scripts/security/generate-report.py
import json
from datetime import datetime

def generate_security_report():
    """Aggregate all security scan results"""

    report = {
        "timestamp": now_sao_paulo().isoformat(),
        "scans": {
            "secrets": load_scan_results("secrets"),
            "dependencies": load_scan_results("dependencies"),
            "sast": load_scan_results("sast"),
            "containers": load_scan_results("containers"),
            "infrastructure": load_scan_results("infrastructure"),
            "dast": load_scan_results("dast"),
            "runtime": load_scan_results("runtime")
        },
        "summary": {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0
        }
    }

    # Aggregate severity counts
    for scan_type, results in report["scans"].items():
        for severity in ["critical", "high", "medium", "low"]:
            report["summary"][severity] += results.get(severity, 0)

    # Save report
    with open("security-report.json", "w") as f:
        json.dump(report, f, indent=2)

    return report
```

### Security Quality Gates

```yaml
# .github/workflows/security-gate.yml
name: Security Quality Gate

on: [pull_request]

jobs:
  security-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run all security scans
        run: make security-scan-all

      - name: Check security thresholds
        run: python scripts/security/check-thresholds.py
        # Fails if:
        # - Any critical vulnerabilities
        # - More than 5 high vulnerabilities
        # - Secrets detected
        # - Container image has critical CVEs

      - name: Comment PR with results
        uses: actions/github-script@v6
        with:
          script: |
            const report = require('./security-report.json');
            const comment = `
            ## 🔒 Security Scan Results

            | Layer | Critical | High | Medium | Low |
            |-------|----------|------|--------|-----|
            | Secrets | ${report.scans.secrets.critical} | ${report.scans.secrets.high} | ${report.scans.secrets.medium} | ${report.scans.secrets.low} |
            | Dependencies | ${report.scans.dependencies.critical} | ${report.scans.dependencies.high} | ${report.scans.dependencies.medium} | ${report.scans.dependencies.low} |
            | SAST | ${report.scans.sast.critical} | ${report.scans.sast.high} | ${report.scans.sast.medium} | ${report.scans.sast.low} |
            | Containers | ${report.scans.containers.critical} | ${report.scans.containers.high} | ${report.scans.containers.medium} | ${report.scans.containers.low} |

            **Total**: ${report.summary.critical} critical, ${report.summary.high} high
            `;

            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: comment
            });
```

### Migration Path

1. ✅ Security scanning tools selected
2. ✅ CI/CD pipeline configured
3. ✅ Quality gates defined
4. 🔄 Team training on security best practices
5. 🔄 Security dashboard deployed
6. 🔄 Runtime monitoring configured
7. 🔄 Incident response procedures documented
8. 🔄 Regular security audits scheduled

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/index.html)
- [LGPD (Brazil Data Protection Law)](https://www.gov.br/cidadania/pt-br/acesso-a-informacao/lgpd)
- [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

## Metadata

- **Author**: Security Team
- **Reviewers**: DevOps Team, Compliance Officer, CTO
- **Last Updated**: 2024-01-24
- **Related ADRs**: ADR-0006 (Firebase Auth), ADR-0002 (PostgreSQL RLS), ADR-0001 (FastAPI)
- **Tags**: security, compliance, scanning, hipaa, lgpd, devops
