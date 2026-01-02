# Pre-Deployment Checklist - P0 Implementations

**Version:** 1.0
**Last Updated:** 2025-11-15
**Applies To:** P0 Database Optimization, Security Fixes, HIPAA Compliance

---

## Overview

This checklist MUST be completed before deploying P0 implementations to staging or production environments. All items marked as **REQUIRED** must be checked off before proceeding with deployment.

**Deployment Scope:**
- Migration 010: Database Performance Indexes (28 indexes)
- Migration 011: HIPAA Audit Trail Enhancement
- Migration 012: Quiz Response JSONB Migration
- Security fixes: CSRF, SQL Injection, Rate Limiting
- Service refactoring: Patient service modularization

---

## 1. Code Review ✅

### 1.1 Peer Review **REQUIRED**
- [ ] **At least 2 engineers** have reviewed all P0 changes
- [ ] **Security team** has approved security-related changes
- [ ] **Database team** has approved migration scripts
- [ ] All review comments resolved and documented
- [ ] Code follows project style guide and conventions

### 1.2 Pull Request Status **REQUIRED**
- [ ] All P0 PRs merged to main branch
- [ ] PR descriptions include migration impact assessment
- [ ] PR includes rollback plan documentation
- [ ] Breaking changes clearly documented (if any)
- [ ] Git tags created for release version

### 1.3 Code Quality Checks **REQUIRED**
```bash
# Run these commands and verify all pass:
cd /mnt/c/Meu\ Projetos/clinica-oncologica-v02-1/backend-hormonia

# Linting
make lint
# Expected: No errors, max 10 warnings

# Type checking
make typecheck
# Expected: 0 errors

# Security scanning
bandit -r app/ -ll
# Expected: 0 high/medium severity issues
```

**Validation:**
- [ ] Linting: 0 errors, <10 warnings
- [ ] Type checking: 0 errors
- [ ] Security scan: 0 high/medium issues
- [ ] No hardcoded secrets in code
- [ ] No debug code or print statements

---

## 2. Test Suite Validation ✅

### 2.1 Unit Tests **REQUIRED**
```bash
# Run full unit test suite
pytest tests/unit/ -v --cov=app --cov-report=term-missing

# Target metrics:
# - Coverage: >80%
# - All tests passing
# - No skipped tests
```

**Validation:**
- [ ] All unit tests passing (100%)
- [ ] Test coverage >80% overall
- [ ] New P0 code coverage >90%
- [ ] No flaky tests (run 3x to verify)
- [ ] No tests skipped or marked as xfail

### 2.2 Integration Tests **REQUIRED**
```bash
# Run integration tests
pytest tests/integration/ -v --tb=short

# Focus areas:
# - Patient onboarding flow
# - Quiz session management
# - Message delivery
# - Alert system
# - Audit trail logging
```

**Validation:**
- [ ] All integration tests passing
- [ ] Database transactions work correctly
- [ ] External API mocks work as expected
- [ ] Message delivery tested end-to-end
- [ ] HIPAA audit events captured correctly

### 2.3 Performance Tests **REQUIRED**
```bash
# Run performance benchmarks
pytest tests/performance/ -v -s

# Key metrics to validate:
# - Query latency <10ms (with new indexes)
# - API endpoint P95 <200ms
# - ThreadPool no blocking detected
```

**Validation:**
- [ ] Query performance <10ms for indexed queries
- [ ] API endpoints P95 latency <200ms
- [ ] No event loop blocking warnings
- [ ] Database connection pool healthy
- [ ] Redis cache hit ratio >70%

### 2.4 Security Tests **REQUIRED**
```bash
# Run security test suite
pytest tests/security/ -v

# Covered areas:
# - CSRF protection
# - SQL injection prevention
# - Rate limiting
# - XSS prevention
# - Authentication bypass attempts
```

**Validation:**
- [ ] All security tests passing
- [ ] CSRF protection validated (CVE-2025-CLINIC-001)
- [ ] SQL injection fixes verified (CVE-2025-CLINIC-004)
- [ ] Rate limiting working (429 responses)
- [ ] No authentication bypass possible
- [ ] Webhook signature validation working

### 2.5 Critical Path Tests **REQUIRED**
```bash
# Run critical API endpoint tests
pytest tests/api/critical/ -v

# Must pass 100%:
# - User authentication (login/refresh)
# - Patient CRUD operations
# - Quiz session lifecycle
# - Message sending
# - Alert creation
```

**Validation:**
- [ ] Authentication endpoints: 100% passing
- [ ] Patient CRUD endpoints: 100% passing
- [ ] Quiz endpoints: 100% passing
- [ ] Message endpoints: 100% passing
- [ ] Alert endpoints: 100% passing

---

## 3. Backward Compatibility ✅

### 3.1 API Contract Validation **REQUIRED**
- [ ] All API endpoints maintain same request/response schema
- [ ] No breaking changes to public APIs
- [ ] New optional fields only (no required field changes)
- [ ] API versioning strategy documented if needed
- [ ] Client SDK compatibility verified (if applicable)

### 3.2 Database Schema Compatibility **REQUIRED**
```bash
# Verify migrations are backward compatible
alembic history --verbose

# Check for:
# - No column drops without deprecation period
# - No data type changes that lose precision
# - All migrations reversible (downgrade works)
```

**Validation:**
- [ ] No columns dropped (use deprecation strategy)
- [ ] No breaking data type changes
- [ ] All migrations have downgrade() implemented
- [ ] Foreign key constraints preserve data integrity
- [ ] Indexes created with CONCURRENTLY (non-blocking)

### 3.3 Service Interface Compatibility **REQUIRED**
- [ ] Service method signatures unchanged
- [ ] New parameters are optional with defaults
- [ ] Return types remain consistent
- [ ] Exception handling maintains same contracts
- [ ] Dependency injection interfaces unchanged

---

## 4. Database Migrations ✅

### 4.1 Migration Scripts Validated **REQUIRED**
```bash
# Check migration files exist and are valid
ls -la alembic/versions/010*.py
ls -la alembic/versions/011*.py
ls -la alembic/versions/012*.py

# Verify syntax
alembic check

# Test on local database
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

**Validation:**
- [ ] Migration 010 (indexes): Syntax valid, upgrade/downgrade works
- [ ] Migration 011 (HIPAA audit): Syntax valid, upgrade/downgrade works
- [ ] Migration 012 (JSONB): Syntax valid, upgrade/downgrade works
- [ ] No duplicate revision IDs
- [ ] Revision chain is linear (no conflicts)

### 4.2 Migration Safety Checks **REQUIRED**
- [ ] **All index creations use CONCURRENTLY** (non-blocking)
- [ ] **No table locks during migration** (verified in test environment)
- [ ] **Estimated migration time <5 minutes** (tested on production-sized data)
- [ ] **Rollback tested and takes <2 minutes**
- [ ] **No data loss during upgrade/downgrade**

### 4.3 Migration Impact Assessment **REQUIRED**
```sql
-- Estimate table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    n_tup_ins - n_tup_del AS live_tuples
FROM pg_stat_user_tables
WHERE tablename IN (
    'patients', 'messages', 'quiz_sessions', 'quiz_responses',
    'alerts', 'medical_reports', 'flow_analytics', 'audit_trail'
)
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

**Expected Results (Document Actual Values):**
- [ ] Largest table size: _______ MB
- [ ] Total affected rows: _______
- [ ] Estimated index build time: _______ minutes
- [ ] Disk space required: _______ MB (indexes ~10-15% of table size)
- [ ] Production downtime: **0 minutes** (CONCURRENTLY operations)

### 4.4 Test Database Validation **REQUIRED**
```bash
# Apply migrations to test database with production-sized data
export DATABASE_URL=<test_db_url>

# Backup test database
pg_dump $DATABASE_URL > test_backup_$(date +%Y%m%d_%H%M%S).sql

# Time the migration
time alembic upgrade head

# Verify indexes created
psql $DATABASE_URL -f scripts/verify_p0_indexes.sql

# Test query performance
psql $DATABASE_URL -f scripts/test_query_performance.sql
```

**Validation:**
- [ ] Migration completed successfully
- [ ] All 28 indexes verified present
- [ ] Query performance improved (document metrics)
- [ ] No errors in PostgreSQL logs
- [ ] Downgrade works successfully

---

## 5. Configuration & Environment Variables ✅

### 5.1 Environment Variables Documented **REQUIRED**

Review and update `.env.example` with any new variables:

```bash
# Verify all required variables documented
cat .env.example | grep -E "^[A-Z_]+=" | wc -l
# Should match production environment variable count
```

**Validation:**
- [ ] All P0-related env vars documented in `.env.example`
- [ ] Default values provided for non-sensitive vars
- [ ] Sensitive vars marked with placeholder (e.g., `SECRET_KEY=your-secret-here`)
- [ ] Railway-specific variables documented
- [ ] Database SSL mode documented (`?sslmode=require`)

### 5.2 Required Environment Variables **REQUIRED**

**Database:**
- [ ] `DATABASE_URL` - PostgreSQL connection string with SSL
- [ ] `DB_POOL_SIZE=30`
- [ ] `DB_MAX_OVERFLOW=40`
- [ ] `DB_POOL_TIMEOUT=30`

**Redis:**
- [ ] `REDIS_URL` - Redis connection string with SSL
- [ ] `REDIS_MAX_CONNECTIONS=50`
- [ ] `REDIS_TIMEOUT=5`

**Security:**
- [ ] `SECRET_KEY` - 32+ character random string
- [ ] `CSRF_SECRET_KEY` - 32+ character random string (NEW)
- [ ] `WEBHOOK_SECRET_KEY` - For webhook signature validation (NEW)
- [ ] `CORS_ORIGINS` - Allowed frontend origins

**HIPAA Audit:**
- [ ] `HIPAA_AUDIT_ENABLED=true` (NEW)
- [ ] `AUDIT_RETENTION_DAYS=2555` (7 years, NEW)

**Rate Limiting:**
- [ ] `RATE_LIMIT_ENABLED=true` (NEW)
- [ ] `RATE_LIMIT_WEBHOOK_REQUESTS_PER_MINUTE=60` (NEW)

### 5.3 Configuration Validation Script **REQUIRED**

```bash
# Run configuration validation
python scripts/verify_configuration.py --env=staging

# Or manually check:
python -c "
from app.core.secure_config import validate_environment
validate_environment()
print('✅ Configuration valid')
"
```

**Validation:**
- [ ] All required variables present
- [ ] No placeholder values in staging/production
- [ ] Secret keys are strong (32+ chars, high entropy)
- [ ] Database URLs use SSL (`sslmode=require`)
- [ ] CORS origins match actual frontend URLs

### 5.4 Secrets Management **REQUIRED**

**Railway Secrets:**
```bash
# Verify secrets are set in Railway dashboard
# DO NOT commit secrets to git
railway variables

# Expected variables set:
# - DATABASE_URL (from Railway PostgreSQL plugin)
# - REDIS_URL (from Railway Redis plugin)
# - SECRET_KEY
# - CSRF_SECRET_KEY
# - WEBHOOK_SECRET_KEY
```

**Validation:**
- [ ] All secrets stored in Railway environment variables
- [ ] No secrets in git repository (verified with git grep)
- [ ] Secret rotation schedule documented
- [ ] Access to secrets restricted (team permissions)
- [ ] Secrets backup strategy in place

---

## 6. Rollback Plan Validated ✅

### 6.1 Rollback Documentation **REQUIRED**
- [ ] `ROLLBACK_PROCEDURE.md` created and reviewed
- [ ] Rollback criteria clearly defined
- [ ] Step-by-step rollback instructions tested
- [ ] Rollback time estimate documented (<10 minutes)
- [ ] Data loss assessment documented (none expected)

### 6.2 Rollback Testing **REQUIRED**
```bash
# Test rollback procedure on staging
# 1. Deploy P0 changes
alembic upgrade head

# 2. Verify deployment
psql $DATABASE_URL -f scripts/verify_p0_indexes.sql

# 3. Execute rollback
alembic downgrade -3  # Rollback 3 migrations (012, 011, 010)

# 4. Verify rollback successful
psql $DATABASE_URL -c "\d+ patients"  # Check indexes removed

# 5. Re-deploy
alembic upgrade head
```

**Validation:**
- [ ] Rollback tested successfully on staging
- [ ] Rollback time <10 minutes
- [ ] No data loss during rollback
- [ ] Application remains functional after rollback
- [ ] Re-deployment works after rollback

### 6.3 Rollback Triggers Defined **REQUIRED**

**Automatic Rollback Triggers:**
- [ ] Error rate >5% (critical endpoints)
- [ ] P95 latency >1000ms (critical endpoints)
- [ ] Database CPU >90% for >5 minutes
- [ ] Migration failure with data corruption
- [ ] HIPAA audit trail failures

**Manual Rollback Criteria:**
- [ ] Critical business functionality broken
- [ ] Data integrity issues detected
- [ ] Security vulnerability introduced
- [ ] User-reported critical bugs >10/hour

---

## 7. Monitoring & Alerting Setup ✅

### 7.1 Monitoring Dashboards **REQUIRED**

**Grafana Dashboards to Update:**
- [ ] Database Performance Dashboard (add P0 index metrics)
- [ ] API Performance Dashboard (verify P95 latency)
- [ ] Security Dashboard (add CSRF, rate limiting metrics)
- [ ] HIPAA Audit Dashboard (NEW - create if not exists)
- [ ] Saga Orchestration Dashboard (verify metrics)

### 7.2 Alerts Configured **REQUIRED**

**Critical Alerts (PagerDuty/Slack):**
```yaml
# Example alert rules to configure
alerts:
  - name: P95LatencyHigh
    condition: p95_latency > 500ms for 5m
    severity: critical

  - name: ErrorRateHigh
    condition: error_rate > 5% for 3m
    severity: critical

  - name: DatabaseCPUHigh
    condition: db_cpu > 80% for 10m
    severity: warning

  - name: RateLimitExceeded
    condition: rate_limit_429_rate > 10% for 5m
    severity: warning

  - name: HIPAAAuditFailure
    condition: audit_log_failures > 0 for 1m
    severity: critical
```

**Validation:**
- [ ] Critical alerts configured and tested
- [ ] Alert routing to correct channels (PagerDuty/Slack)
- [ ] On-call rotation updated for P0 deployment
- [ ] Alert runbooks updated with P0 context
- [ ] False positive alerts tuned

### 7.3 Logging Configuration **REQUIRED**

```python
# Verify structured logging enabled
import logging
logger = logging.getLogger("app")
logger.info("P0_DEPLOYMENT_TEST", extra={
    "event": "pre_deployment_check",
    "migration": "010_indexes",
    "status": "ready"
})
```

**Validation:**
- [ ] Structured logging enabled (JSON format)
- [ ] Log aggregation working (CloudWatch/Datadog)
- [ ] Log retention set to 90+ days (HIPAA requirement)
- [ ] Sensitive data redacted in logs (PII/PHI)
- [ ] Log levels appropriate (INFO for production)

---

## 8. Documentation ✅

### 8.1 Technical Documentation **REQUIRED**
- [ ] `P0_DATABASE_OPTIMIZATION_COMPLETE.md` - Complete
- [ ] `docs/P0_DATABASE_INDEXES_REPORT.md` - Complete (500+ lines)
- [ ] `docs/P0_DEPLOYMENT_GUIDE.md` - Complete
- [ ] `docs/deployment/PRE_DEPLOYMENT_CHECKLIST.md` - This document
- [ ] `docs/deployment/POST_DEPLOYMENT_CHECKLIST.md` - Created
- [ ] `docs/deployment/ROLLBACK_PROCEDURE.md` - Created
- [ ] Migration impact assessment documented

### 8.2 Runbook Updates **REQUIRED**
- [ ] Deployment runbook updated with P0 procedures
- [ ] Incident response runbook includes P0 rollback
- [ ] Database maintenance runbook updated
- [ ] Security incident runbook updated (CSRF, SQL injection)
- [ ] On-call playbook updated

### 8.3 Architecture Decision Records **REQUIRED**
- [ ] ADR created for ThreadPoolExecutor pattern
- [ ] ADR created for HIPAA audit implementation
- [ ] ADR created for JSONB migration strategy
- [ ] ADR created for security fixes approach
- [ ] ADRs reviewed and approved by tech lead

---

## 9. Stakeholder Communication ✅

### 9.1 Deployment Announcement **REQUIRED**

**Email to Stakeholders:**
```
Subject: P0 Deployment - Database Performance & Security Improvements

Team,

We are deploying critical P0 improvements on [DATE] at [TIME]:

**What's Changing:**
- Database performance: 50-99% faster queries (28 new indexes)
- Security enhancements: CSRF protection, SQL injection fixes
- HIPAA compliance: Enhanced audit trail
- Quiz system: JSONB migration for better performance

**Expected Impact:**
- Downtime: 0 minutes (non-blocking migrations)
- User Experience: Faster page loads, improved responsiveness
- Risk Level: LOW (comprehensive testing completed)

**Rollback Plan:**
- Automated rollback if error rate >5%
- Manual rollback available within 10 minutes
- Full rollback procedure documented

**Monitoring:**
- Real-time metrics dashboard: [URL]
- On-call team: [NAMES]
- Incident channel: #p0-deployment

Questions? Reply to this email or ping #engineering-team.

Thanks,
[YOUR NAME]
```

**Validation:**
- [ ] Deployment announcement sent 48 hours before deployment
- [ ] Stakeholders acknowledged and approved
- [ ] Deployment window scheduled and confirmed
- [ ] On-call team briefed and prepared
- [ ] Emergency contacts documented

### 9.2 Change Request (if required) **REQUIRED**
- [ ] Change request ticket created (e.g., JIRA)
- [ ] Change approved by change management board
- [ ] Risk assessment documented
- [ ] Rollback plan included in change request
- [ ] Testing evidence attached

---

## 10. Compliance & Security ✅

### 10.1 HIPAA Compliance **REQUIRED**
- [ ] Audit trail captures all PHI access (migration 011)
- [ ] Audit logs retained for 7 years (2555 days)
- [ ] Encryption at rest enabled (database, Redis)
- [ ] Encryption in transit enabled (SSL/TLS)
- [ ] Access controls verified (RBAC working)
- [ ] PHI data minimization reviewed

### 10.2 Security Scan Results **REQUIRED**
```bash
# Run OWASP dependency check
safety check

# Run security linting
bandit -r app/ -ll -f json -o security_report.json

# Check for secrets in code
git secrets --scan

# Verify SSL certificates valid
openssl s_client -connect <your-db-host>:5432 -showcerts
```

**Validation:**
- [ ] No critical vulnerabilities in dependencies
- [ ] No secrets committed to repository
- [ ] SSL certificates valid for >30 days
- [ ] Security headers configured (CSRF, XSS, etc.)
- [ ] Rate limiting working (webhook endpoints)

### 10.3 Data Privacy **REQUIRED**
- [ ] PII/PHI handling reviewed
- [ ] Data retention policies enforced
- [ ] GDPR compliance maintained (if applicable)
- [ ] Data export functionality working
- [ ] Data deletion functionality working

---

## 11. Performance Baselines ✅

### 11.1 Pre-Deployment Metrics **REQUIRED**

**Capture Current Production Metrics:**
```bash
# Database query performance
SELECT
    query,
    mean_exec_time,
    calls,
    total_exec_time
FROM pg_stat_statements
WHERE query LIKE '%patients%' OR query LIKE '%messages%'
ORDER BY mean_exec_time DESC
LIMIT 20;

# API endpoint latency (from monitoring)
# Document P50, P95, P99 for critical endpoints
```

**Document Baseline Metrics:**
- [ ] Doctor dashboard load time: _______ ms (current)
- [ ] Patient message list: _______ ms (current)
- [ ] Quiz analytics query: _______ ms (current)
- [ ] Alert dashboard load: _______ ms (current)
- [ ] API error rate: _______ % (current)
- [ ] Database CPU utilization: _______ % (current)

### 11.2 Performance Targets **REQUIRED**

**Post-Deployment Targets:**
- [ ] Doctor dashboard: <10ms (target: 99% improvement)
- [ ] Patient messages: <5ms (target: 99% improvement)
- [ ] Quiz analytics: <8ms (target: 98% improvement)
- [ ] Alert dashboard: <10ms (target: 99% improvement)
- [ ] API error rate: No increase (target: 0% regression)
- [ ] Database CPU: -40% reduction (target)

---

## 12. Final Pre-Deployment Sign-off ✅

### 12.1 Deployment Readiness **REQUIRED**

**Sign-off Required From:**
- [ ] **Tech Lead:** Code review approved, architecture sound
- [ ] **Database Admin:** Migrations validated, backup strategy confirmed
- [ ] **Security Lead:** Security fixes verified, no vulnerabilities
- [ ] **QA Lead:** All tests passing, manual testing complete
- [ ] **Product Owner:** Business impact understood and approved
- [ ] **DevOps Lead:** Infrastructure ready, monitoring configured

### 12.2 Pre-Deployment Checklist Summary **REQUIRED**

**Total Checklist Items:**
- [ ] Code Review: ___/10 items complete
- [ ] Testing: ___/25 items complete
- [ ] Backward Compatibility: ___/8 items complete
- [ ] Database Migrations: ___/15 items complete
- [ ] Configuration: ___/12 items complete
- [ ] Rollback Plan: ___/8 items complete
- [ ] Monitoring: ___/10 items complete
- [ ] Documentation: ___/8 items complete
- [ ] Communication: ___/5 items complete
- [ ] Compliance: ___/10 items complete
- [ ] Performance: ___/6 items complete
- [ ] Final Sign-off: ___/6 items complete

**Minimum Requirements for Deployment:**
- All **REQUIRED** items must be checked ✅
- Test coverage >80%
- All critical tests passing (100%)
- At least 2 approvals on PRs
- Rollback procedure tested
- On-call team briefed

### 12.3 Go/No-Go Decision **REQUIRED**

**Deployment Decision:** [ ] GO / [ ] NO-GO

**If NO-GO, document blockers:**
1. _______________________________________
2. _______________________________________
3. _______________________________________

**Next Steps:**
- [ ] Proceed to deployment (see `DEPLOYMENT_PROCEDURE.md`)
- [ ] Re-schedule deployment (document new date)
- [ ] Cancel deployment (document reason)

---

## Appendix A: Quick Reference Commands

### Database Backup
```bash
# Production backup (before deployment)
pg_dump $DATABASE_URL > backup_p0_$(date +%Y%m%d_%H%M%S).sql

# Verify backup size
ls -lh backup_p0_*.sql
```

### Migration Application
```bash
# Check current migration version
alembic current

# Apply P0 migrations
alembic upgrade head

# Verify migrations applied
alembic current -v
```

### Index Verification
```bash
# Verify all 28 indexes created
psql $DATABASE_URL -f scripts/verify_p0_indexes.sql

# Expected output: 28 indexes found
```

### Performance Testing
```bash
# Test query performance with new indexes
psql $DATABASE_URL -f scripts/test_query_performance.sql

# Expected: All queries <10ms
```

### Health Check
```bash
# Verify application health
curl https://your-app.railway.app/health

# Expected response: {"status":"healthy","database":"connected","redis":"connected"}
```

---

## Appendix B: Emergency Contacts

**On-Call Team:**
- Primary: _______________________
- Secondary: _____________________
- Escalation: ____________________

**Stakeholders:**
- Tech Lead: _____________________
- Product Owner: _________________
- Database Admin: ________________
- Security Lead: _________________

**Communication Channels:**
- Slack: #p0-deployment
- PagerDuty: [Service Name]
- Email: engineering-team@company.com

---

**Document Version:** 1.0
**Last Updated:** 2025-11-15
**Next Review:** Before each P0 deployment

**Status:** ✅ Ready for use

---

**Related Documents:**
- `DEPLOYMENT_PROCEDURE.md` - Step-by-step deployment guide
- `POST_DEPLOYMENT_CHECKLIST.md` - Post-deployment validation
- `ROLLBACK_PROCEDURE.md` - Emergency rollback procedures
- `P0_DATABASE_OPTIMIZATION_COMPLETE.md` - Implementation summary
