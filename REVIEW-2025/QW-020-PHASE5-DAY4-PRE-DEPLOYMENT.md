# QW-020 Phase 5 Migration - Day 4 Pre-Deployment Checklist

**Project**: Quick Win QW-020 - Alert Services Consolidation (3 → 1)  
**Phase**: 5 - Production Migration  
**Day**: 4 - Staging Deployment  
**Date**: 2025-01-22  
**Status**: 🔄 **PRE-DEPLOYMENT VALIDATION**

---

## 📋 Executive Summary

Day 4 focuses on validating all work from Days 1-3 and deploying the consolidated alert system to the staging environment. This document provides a comprehensive checklist and validation guide to ensure a safe, controlled deployment.

### Pre-Deployment Objectives

✅ Execute and validate all 148+ tests  
✅ Measure and confirm 95%+ code coverage  
✅ Verify zero regressions  
✅ Validate performance benchmarks  
✅ Prepare staging environment  
✅ Execute deployment with feature flag  
✅ Run smoke tests  
✅ Monitor and validate behavior  
✅ Make Go/No-Go decision

---

## 🎯 Day 4 Timeline

| Phase | Duration | Status | Tasks |
|-------|----------|--------|-------|
| **Morning: Pre-Deployment** | 2-3h | ⏳ Pending | Test execution, coverage validation |
| **Afternoon: Deployment** | 2-3h | ⏳ Pending | Deploy to staging, smoke tests |
| **Evening: Validation** | 2-3h | ⏳ Pending | Monitoring, validation, Go/No-Go |
| **Total** | 8-10h | ⏳ Pending | Complete Day 4 |

---

## ✅ PRE-DEPLOYMENT CHECKLIST

### Phase 1: Code Validation (1-2 hours)

#### 1.1 Test Execution ✅
```bash
# Navigate to backend
cd backend-hormonia

# Run all tests with coverage
pytest tests/services/alerts/ -v --cov=app.services.alerts --cov-report=html --cov-report=term

# Expected results:
# ✓ 148+ tests should pass
# ✓ 0 failures
# ✓ 0 errors
# ✓ Coverage >= 95%
```

**Checklist**:
- [ ] All unit tests passing (63/63)
- [ ] All integration tests passing (60+/60+)
- [ ] All performance tests passing (25+/25+)
- [ ] Zero test failures
- [ ] Zero test errors
- [ ] Test execution time < 5 minutes

#### 1.2 Coverage Validation ✅
```bash
# Generate detailed coverage report
pytest tests/services/alerts/ --cov=app.services.alerts --cov-report=html --cov-report=term-missing

# Open coverage report
open htmlcov/index.html  # macOS
start htmlcov/index.html  # Windows
```

**Coverage Targets**:
- [ ] Overall coverage >= 95%
- [ ] adapter.py coverage >= 95%
- [ ] All public methods covered
- [ ] All error paths covered
- [ ] No critical uncovered lines

**Coverage Report Review**:
```
Expected Coverage Report:
========================
Name                                    Stmts   Miss  Cover   Missing
---------------------------------------------------------------------
app/services/alerts/adapter.py           458      X    XX%    (lines)
app/services/alerts/alert_manager.py     XXX      X    XX%    
app/services/alerts/...                  ...     ...   ...    
---------------------------------------------------------------------
TOTAL                                   XXXX     XX    XX%
```

#### 1.3 Code Quality Validation ✅
```bash
# Run linting
black app/services/alerts/ --check
flake8 app/services/alerts/
mypy app/services/alerts/

# Expected: No errors, no warnings
```

**Checklist**:
- [ ] Black formatting passes
- [ ] Flake8 linting passes
- [ ] MyPy type checking passes
- [ ] No pylint errors
- [ ] No security warnings

#### 1.4 Performance Benchmark Validation ✅
```bash
# Run performance tests
pytest tests/services/alerts/integration/test_adapter_performance.py -v -s

# Review benchmark output
```

**Performance Criteria**:
- [ ] Acknowledge alert: <10ms average, <20ms P95
- [ ] Resolve alert: <10ms average, <20ms P95
- [ ] Get statistics: <50ms average, <100ms P95
- [ ] Process escalation: <10ms average, <20ms P95
- [ ] Adapter overhead: <5% vs direct calls
- [ ] Memory usage: <10MB creation overhead
- [ ] No memory leaks detected
- [ ] Throughput: >100 ops/sec

### Phase 2: Environment Preparation (30 minutes)

#### 2.1 Staging Environment Check ✅

**Infrastructure Checklist**:
- [ ] Staging server accessible
- [ ] Database connection verified
- [ ] Redis connection verified
- [ ] Celery workers running
- [ ] Monitoring stack operational (Grafana, Prometheus)
- [ ] Log aggregation working (ELK/CloudWatch)
- [ ] Alerting configured

**Environment Variables**:
```bash
# Verify staging environment variables
# .env.staging

# Feature flag (initially disabled)
USE_CONSOLIDATED_ALERTS=false
ALERTS_LEGACY_DEPRECATION_WARNING=true

# Database
DATABASE_URL=postgresql://...

# Redis
REDIS_URL=redis://...

# Monitoring
SENTRY_DSN=...
LOG_LEVEL=INFO
```

**Checklist**:
- [ ] All environment variables set
- [ ] Database migrations applied
- [ ] Redis available and responsive
- [ ] Celery broker accessible
- [ ] Monitoring endpoints responding

#### 2.2 Backup and Rollback Preparation ✅

**Pre-Deployment Backup**:
```bash
# Backup current staging deployment
kubectl get deployment alert-service -n staging -o yaml > backup/alert-service-deployment.yaml

# Backup database (if needed)
pg_dump -h staging-db -U user clinica_oncologica > backup/staging-db-$(date +%Y%m%d).sql

# Tag current commit
git tag pre-qw020-phase5-deployment
git push origin pre-qw020-phase5-deployment
```

**Checklist**:
- [ ] Current deployment backed up
- [ ] Database backup created (if needed)
- [ ] Git tag created and pushed
- [ ] Rollback procedure documented
- [ ] Emergency contacts notified

**Rollback Procedure**:
```bash
# Emergency rollback steps:
# 1. Set feature flag to false
export USE_CONSOLIDATED_ALERTS=false

# 2. Restart application
kubectl rollout restart deployment/alert-service -n staging

# 3. Verify legacy system active
curl https://staging-api.clinica.com/health

# 4. Monitor for 5 minutes
# 5. Confirm all services healthy
```

### Phase 3: Deployment Validation (1 hour)

#### 3.1 Code Deployment ✅

**Deployment Steps**:
```bash
# 1. Merge to staging branch
git checkout staging
git merge feature/qw-020-phase5-migration
git push origin staging

# 2. Build and push Docker image
docker build -t clinica-backend:qw020-phase5 .
docker tag clinica-backend:qw020-phase5 registry.clinica.com/backend:qw020-phase5
docker push registry.clinica.com/backend:qw020-phase5

# 3. Update Kubernetes deployment
kubectl set image deployment/alert-service backend=registry.clinica.com/backend:qw020-phase5 -n staging

# 4. Wait for rollout
kubectl rollout status deployment/alert-service -n staging

# 5. Verify pods running
kubectl get pods -n staging | grep alert-service
```

**Checklist**:
- [ ] Code merged to staging branch
- [ ] Docker image built successfully
- [ ] Image pushed to registry
- [ ] Deployment updated
- [ ] Rollout completed successfully
- [ ] All pods running (X/X ready)
- [ ] No pod crashes or restarts

#### 3.2 Health Check Validation ✅

**Health Checks**:
```bash
# Basic health check
curl https://staging-api.clinica.com/health
# Expected: {"status": "healthy"}

# Alert service health
curl https://staging-api.clinica.com/api/v1/alerts/health
# Expected: {"status": "healthy", "system": "legacy"}

# Database health
curl https://staging-api.clinica.com/api/v1/health/database
# Expected: {"status": "connected"}

# Redis health
curl https://staging-api.clinica.com/api/v1/health/redis
# Expected: {"status": "connected"}
```

**Checklist**:
- [ ] API responding (200 OK)
- [ ] Health endpoint returns healthy
- [ ] Alert service responding
- [ ] Database connection healthy
- [ ] Redis connection healthy
- [ ] Celery workers processing

---

## 🔥 SMOKE TESTS

### Smoke Test Suite (30 minutes)

#### Test 1: List Alerts (Legacy System)
```bash
# With USE_CONSOLIDATED_ALERTS=false
curl -X GET "https://staging-api.clinica.com/api/v1/alerts?page=1&size=10" \
  -H "Authorization: Bearer $TOKEN"

# Expected:
# - 200 OK
# - Returns alert list
# - Pagination data present
```
**Result**: [ ] PASS / [ ] FAIL

#### Test 2: Acknowledge Alert (Legacy System)
```bash
# Create test alert first, then acknowledge
ALERT_ID="test-alert-id"
curl -X POST "https://staging-api.clinica.com/api/v1/alerts/$ALERT_ID/acknowledge" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test-user-id", "notes": "Smoke test"}'

# Expected:
# - 200 OK
# - Alert status = ACKNOWLEDGED
```
**Result**: [ ] PASS / [ ] FAIL

#### Test 3: Enable Consolidated System
```bash
# Update environment variable
kubectl set env deployment/alert-service USE_CONSOLIDATED_ALERTS=true -n staging

# Wait for rollout
kubectl rollout status deployment/alert-service -n staging

# Verify feature flag active
curl https://staging-api.clinica.com/api/v1/alerts/health
# Expected: {"status": "healthy", "system": "consolidated"}
```
**Result**: [ ] PASS / [ ] FAIL

#### Test 4: List Alerts (Consolidated System)
```bash
# With USE_CONSOLIDATED_ALERTS=true
curl -X GET "https://staging-api.clinica.com/api/v1/alerts?page=1&size=10" \
  -H "Authorization: Bearer $TOKEN"

# Expected:
# - 200 OK
# - Returns alert list (same format as legacy)
# - Pagination data present
# - Response time similar to legacy
```
**Result**: [ ] PASS / [ ] FAIL

#### Test 5: Acknowledge Alert (Consolidated System)
```bash
ALERT_ID="test-alert-id-2"
curl -X POST "https://staging-api.clinica.com/api/v1/alerts/$ALERT_ID/acknowledge" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test-user-id", "notes": "Smoke test consolidated"}'

# Expected:
# - 200 OK
# - Alert status = ACKNOWLEDGED
# - Response time similar to legacy
```
**Result**: [ ] PASS / [ ] FAIL

#### Test 6: Get Alert Statistics (Consolidated)
```bash
curl -X GET "https://staging-api.clinica.com/api/v1/alerts/statistics" \
  -H "Authorization: Bearer $TOKEN"

# Expected:
# - 200 OK
# - Statistics object returned
# - Contains: total_alerts, by_severity, by_status
```
**Result**: [ ] PASS / [ ] FAIL

#### Test 7: Feature Flag Toggle Test
```bash
# 1. Set to legacy
kubectl set env deployment/alert-service USE_CONSOLIDATED_ALERTS=false -n staging
kubectl rollout status deployment/alert-service -n staging

# Test legacy endpoint
curl https://staging-api.clinica.com/api/v1/alerts

# 2. Set to consolidated
kubectl set env deployment/alert-service USE_CONSOLIDATED_ALERTS=true -n staging
kubectl rollout status deployment/alert-service -n staging

# Test consolidated endpoint
curl https://staging-api.clinica.com/api/v1/alerts

# Expected: Both work identically
```
**Result**: [ ] PASS / [ ] FAIL

#### Test 8: Celery Task Test (Consolidated)
```bash
# Trigger background task
curl -X POST "https://staging-api.clinica.com/api/v1/alerts/tasks/check-patient-alerts" \
  -H "Authorization: Bearer $TOKEN"

# Check task status in Celery
# Expected: Task executes successfully with consolidated system
```
**Result**: [ ] PASS / [ ] FAIL

---

## 📊 MONITORING & VALIDATION

### Monitoring Checklist (2 hours)

#### 1. Application Metrics

**Prometheus Metrics to Monitor**:
```
# Request rate
http_requests_total{endpoint="/api/v1/alerts"}

# Response time (should be similar to legacy)
http_request_duration_seconds{endpoint="/api/v1/alerts",quantile="0.95"}

# Error rate (should be 0)
http_requests_errors_total{endpoint="/api/v1/alerts"}

# Alert processing rate
alerts_processed_total

# Alert system status
alert_system_active{system="consolidated"}
```

**Checklist**:
- [ ] Request rate normal (baseline comparison)
- [ ] Response time P95 < 200ms
- [ ] Response time P99 < 500ms
- [ ] Error rate < 0.1%
- [ ] No 5xx errors
- [ ] Alert processing working

#### 2. Application Logs

**Log Patterns to Monitor**:
```bash
# Check for consolidated system activation
kubectl logs -f deployment/alert-service -n staging | grep "consolidated"

# Check for errors
kubectl logs -f deployment/alert-service -n staging | grep "ERROR"

# Check for warnings
kubectl logs -f deployment/alert-service -n staging | grep "WARN"

# Check deprecation warnings (should see when legacy used)
kubectl logs -f deployment/alert-service -n staging | grep "deprecated"
```

**Checklist**:
- [ ] "Using consolidated alert system" log present
- [ ] No ERROR logs related to alerts
- [ ] Deprecation warnings appear when legacy used
- [ ] No unexpected WARNING logs
- [ ] Database queries executing properly

#### 3. Database Performance

**Database Queries to Monitor**:
```sql
-- Check alert table query performance
SELECT COUNT(*) FROM alerts;

-- Check for slow queries
SELECT query, mean_exec_time, calls 
FROM pg_stat_statements 
WHERE query LIKE '%alerts%' 
ORDER BY mean_exec_time DESC 
LIMIT 10;

-- Check connection pool usage
SELECT count(*) FROM pg_stat_activity 
WHERE application_name LIKE '%clinica%';
```

**Checklist**:
- [ ] No slow queries (>100ms)
- [ ] Connection pool usage normal
- [ ] No connection errors
- [ ] Query patterns similar to legacy

#### 4. Resource Usage

**Resource Metrics**:
```bash
# CPU usage
kubectl top pods -n staging | grep alert-service

# Memory usage
kubectl describe pod alert-service-xxx -n staging | grep Memory

# Expected:
# - CPU: < 500m (50% of 1 core)
# - Memory: < 512Mi
```

**Checklist**:
- [ ] CPU usage < 50%
- [ ] Memory usage < 512Mi
- [ ] No memory leaks (stable over time)
- [ ] No OOM kills
- [ ] Disk I/O normal

---

## 🎯 GO/NO-GO DECISION CRITERIA

### Go Criteria (All Must Be Met)

#### Technical Criteria ✅
- [ ] **All 148+ tests passing** (100%)
- [ ] **Code coverage >= 95%**
- [ ] **Zero regressions detected**
- [ ] **Performance within 5% of legacy**
- [ ] **All smoke tests passing** (8/8)
- [ ] **Zero errors in logs**
- [ ] **Monitoring shows healthy metrics**
- [ ] **Feature flag toggle works correctly**

#### Operational Criteria ✅
- [ ] **Rollback procedure validated**
- [ ] **Team available for monitoring**
- [ ] **Stakeholders informed**
- [ ] **Documentation complete**
- [ ] **On-call engineer available**

#### Business Criteria ✅
- [ ] **No production incidents in last 24h**
- [ ] **Low traffic period selected**
- [ ] **Stakeholder approval obtained**
- [ ] **Communication plan ready**

### No-Go Criteria (Any Triggers Delay)

#### Critical Issues ❌
- [ ] **Test failures** (any critical tests failing)
- [ ] **Coverage below 95%**
- [ ] **Performance degradation >5%**
- [ ] **Smoke test failures**
- [ ] **Errors in staging logs**
- [ ] **Resource usage spikes**

#### Operational Issues ❌
- [ ] **Monitoring not working**
- [ ] **Team not available**
- [ ] **Recent production incidents**
- [ ] **Rollback procedure not tested**

---

## 📝 VALIDATION REPORT TEMPLATE

### Staging Deployment Validation Report

**Deployment Date**: _________________  
**Deployment Time**: _________________  
**Engineer**: _________________  
**Reviewer**: _________________  

#### Test Execution Results
- Total Tests: 148+
- Tests Passed: _____ / _____
- Tests Failed: _____ 
- Code Coverage: _____% 
- Performance: Within ____% of legacy

#### Smoke Tests Results
- Test 1 (List Alerts - Legacy): [ ] PASS [ ] FAIL
- Test 2 (Acknowledge - Legacy): [ ] PASS [ ] FAIL
- Test 3 (Enable Consolidated): [ ] PASS [ ] FAIL
- Test 4 (List Alerts - Consolidated): [ ] PASS [ ] FAIL
- Test 5 (Acknowledge - Consolidated): [ ] PASS [ ] FAIL
- Test 6 (Statistics): [ ] PASS [ ] FAIL
- Test 7 (Feature Toggle): [ ] PASS [ ] FAIL
- Test 8 (Celery Task): [ ] PASS [ ] FAIL

#### Monitoring Results (First 2 Hours)
- Error Rate: _____%
- P95 Latency: _____ms
- P99 Latency: _____ms
- CPU Usage: _____%
- Memory Usage: _____MB
- Alerts Processed: _____

#### Issues Identified
1. _________________
2. _________________
3. _________________

#### Go/No-Go Decision
- [ ] **GO** - Proceed to production (Day 5)
- [ ] **NO-GO** - Address issues, revalidate

**Decision Rationale**:
_________________________________________________
_________________________________________________

**Signatures**:
- Engineering Lead: _________________
- QA Lead: _________________
- Tech Lead: _________________

---

## 🚀 SUCCESS CRITERIA SUMMARY

### Day 4 Complete When:
1. ✅ All 148+ tests passing
2. ✅ Coverage >= 95% achieved
3. ✅ Performance validated (<5% overhead)
4. ✅ Code deployed to staging
5. ✅ Smoke tests completed (8/8 passing)
6. ✅ 2 hours monitoring completed
7. ✅ Zero critical issues found
8. ✅ Go/No-Go decision made
9. ✅ Documentation updated
10. ✅ Team ready for Day 5

---

## 📞 Emergency Contacts

**On-Call Engineer**: [Name] - [Phone]  
**Tech Lead**: [Name] - [Phone]  
**DevOps**: [Name] - [Phone]  
**Manager**: [Name] - [Phone]

**Escalation Path**:
1. On-Call Engineer (immediate)
2. Tech Lead (5 minutes)
3. Engineering Manager (15 minutes)
4. CTO (30 minutes)

---

**Document Version**: 1.0  
**Last Updated**: 2025-01-22  
**Status**: ✅ READY FOR USE  
**Next**: Execute Day 4 validation and deployment