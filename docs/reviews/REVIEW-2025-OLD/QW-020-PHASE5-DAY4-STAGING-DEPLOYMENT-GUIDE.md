# QW-020 Phase 5 Migration - Day 4 Staging Deployment Guide

**Project**: Quick Win QW-020 - Alert Services Consolidation (3 → 1)  
**Phase**: 5 - Production Migration  
**Day**: 4 - Staging Deployment  
**Date**: 2025-01-22  
**Status**: 📘 **DEPLOYMENT GUIDE**

---

## 📋 Overview

This guide provides step-by-step instructions for deploying the consolidated alert system to the staging environment. Follow each step carefully and document results in the validation report.

### Deployment Strategy

- **Approach**: Blue-Green deployment with feature flag
- **Risk Level**: 🟢 LOW (feature flag enables instant rollback)
- **Duration**: 4-6 hours (including monitoring)
- **Team Required**: 1 engineer + 1 DevOps (optional)
- **Rollback Time**: <1 minute via feature flag

---

## 🎯 Deployment Phases

```
Phase 1: Pre-Deployment Validation    [2h]  ⏳
Phase 2: Staging Deployment            [1h]  ⏳
Phase 3: Smoke Testing                 [1h]  ⏳
Phase 4: Monitoring & Validation       [2h]  ⏳
Phase 5: Go/No-Go Decision            [30m] ⏳
```

---

## ⚙️ PHASE 1: PRE-DEPLOYMENT VALIDATION

**Duration**: 2 hours  
**Status**: ⏳ Pending

### Step 1.1: Execute Test Suite

```bash
# Navigate to backend directory
cd backend-hormonia

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install test dependencies (if needed)
pip install pytest pytest-asyncio pytest-cov pytest-mock

# Run all alert tests with coverage
pytest tests/services/alerts/ \
  -v \
  --cov=app.services.alerts \
  --cov-report=html \
  --cov-report=term-missing \
  --tb=short \
  -m "not integration or not performance"

# Expected output:
# ======================== test session starts =========================
# collected 148 items
# 
# tests/services/alerts/test_alert_manager_adapter.py ......... [100%]
# tests/services/alerts/integration/test_adapter_integration.py ... [100%]
# tests/services/alerts/integration/test_adapter_performance.py ... [100%]
# 
# ======================== 148 passed in X.XXs =========================
# 
# ----------- coverage: platform X, python X.X.X -----------
# Name                                    Stmts   Miss  Cover   Missing
# ---------------------------------------------------------------------
# app/services/alerts/adapter.py           458      X    XX%    
# ---------------------------------------------------------------------
# TOTAL                                   XXXX     XX    XX%
```

**Validation Checklist**:
- [ ] All 148+ tests passed (0 failures)
- [ ] Test execution time < 10 minutes
- [ ] No unexpected warnings
- [ ] Coverage report generated

**If tests fail**:
1. Review failure logs carefully
2. Fix failing tests
3. Re-run test suite
4. DO NOT proceed until 100% passing

### Step 1.2: Verify Code Coverage

```bash
# Check coverage report
cat htmlcov/index.html  # or open in browser

# Verify coverage meets target
python << EOF
import json
with open('.coverage', 'r') as f:
    # Parse coverage data
    pass
# Check if coverage >= 95%
EOF
```

**Coverage Requirements**:
- [ ] Overall coverage >= 95%
- [ ] adapter.py coverage >= 95%
- [ ] No critical uncovered lines
- [ ] All public methods covered 100%

**Coverage Report**:
```
Expected Coverage Breakdown:
============================
adapter.py:                95-100%
  __init__:                100%
  evaluate_patient_alerts: 100%
  acknowledge_alert:       100%
  resolve_alert:           100%
  get_alert_statistics:    100%
  get_alert_dashboard_data:100%
  process_escalation:      100%
  Helper methods:          100%
```

### Step 1.3: Run Performance Benchmarks

```bash
# Execute performance tests
pytest tests/services/alerts/integration/test_adapter_performance.py \
  -v \
  -s \
  --tb=short

# Review benchmark output
# All benchmarks should meet targets:
# - Response times < thresholds
# - Adapter overhead < 5%
# - Memory usage acceptable
# - No memory leaks
```

**Performance Validation**:
- [ ] Acknowledge alert: <10ms avg, <20ms P95
- [ ] Resolve alert: <10ms avg, <20ms P95
- [ ] Get statistics: <50ms avg, <100ms P95
- [ ] Adapter overhead: <5%
- [ ] Memory overhead: <10MB
- [ ] Throughput: >100 ops/sec

### Step 1.4: Code Quality Checks

```bash
# Run code formatters and linters
black app/services/alerts/ --check --diff
flake8 app/services/alerts/ --max-line-length=88
mypy app/services/alerts/ --strict

# Check for security issues
bandit -r app/services/alerts/ -ll

# Expected: All checks pass with 0 errors
```

**Quality Checklist**:
- [ ] Black formatting: PASS
- [ ] Flake8 linting: PASS
- [ ] MyPy type checking: PASS
- [ ] Bandit security: PASS
- [ ] No TODO or FIXME in production code

---

## 🚀 PHASE 2: STAGING DEPLOYMENT

**Duration**: 1 hour  
**Status**: ⏳ Pending

### Step 2.1: Prepare Deployment Branch

```bash
# Create deployment branch
git checkout main
git pull origin main
git checkout -b deploy/qw020-phase5-staging

# Verify all changes included
git log --oneline -10

# Tag the deployment
git tag qw020-phase5-staging-$(date +%Y%m%d-%H%M)
git push origin qw020-phase5-staging-$(date +%Y%m%d-%H%M)
```

**Checklist**:
- [ ] All Day 1-3 changes included
- [ ] No unexpected commits
- [ ] Tag created and pushed
- [ ] Branch ready for merge

### Step 2.2: Update Staging Configuration

```bash
# Update .env.staging file
cat > .env.staging << 'EOF'
# Feature Flags (START WITH CONSOLIDATED DISABLED)
USE_CONSOLIDATED_ALERTS=false
ALERTS_LEGACY_DEPRECATION_WARNING=true

# Database
DATABASE_URL=postgresql://user:pass@staging-db:5432/clinica_staging
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Redis
REDIS_URL=redis://staging-redis:6379/0
REDIS_MAX_CONNECTIONS=50

# Celery
CELERY_BROKER_URL=redis://staging-redis:6379/1
CELERY_RESULT_BACKEND=redis://staging-redis:6379/2

# Monitoring
SENTRY_DSN=https://xxx@sentry.io/xxx
SENTRY_ENVIRONMENT=staging
LOG_LEVEL=INFO
ENABLE_METRICS=true

# API Settings
API_RATE_LIMIT=100/minute
CORS_ORIGINS=https://staging.clinica.com

# Security
SECRET_KEY=${STAGING_SECRET_KEY}
JWT_SECRET=${STAGING_JWT_SECRET}
EOF
```

**Configuration Checklist**:
- [ ] Feature flag set to false (start safe)
- [ ] Database URL correct
- [ ] Redis URL correct
- [ ] Sentry configured
- [ ] Log level appropriate
- [ ] All secrets set

### Step 2.3: Build Docker Image

```bash
# Build production image
docker build \
  -t clinica-backend:qw020-phase5-staging \
  -f Dockerfile.prod \
  --build-arg ENV=staging \
  .

# Verify image built successfully
docker images | grep qw020-phase5-staging

# Tag for registry
docker tag clinica-backend:qw020-phase5-staging \
  registry.clinica.com/backend:qw020-phase5-staging

# Push to registry
docker push registry.clinica.com/backend:qw020-phase5-staging

# Verify push successful
docker pull registry.clinica.com/backend:qw020-phase5-staging
```

**Build Checklist**:
- [ ] Docker build successful
- [ ] Image size reasonable (<1GB)
- [ ] Image tagged correctly
- [ ] Push to registry successful
- [ ] Image pullable from registry

### Step 2.4: Deploy to Kubernetes Staging

```bash
# Update Kubernetes deployment
kubectl set image deployment/alert-service \
  backend=registry.clinica.com/backend:qw020-phase5-staging \
  -n staging

# Monitor rollout
kubectl rollout status deployment/alert-service -n staging

# Expected output:
# Waiting for deployment "alert-service" rollout to finish: 1 out of 3 new replicas have been updated...
# Waiting for deployment "alert-service" rollout to finish: 2 out of 3 new replicas have been updated...
# Waiting for deployment "alert-service" rollout to finish: 3 old replicas are pending termination...
# deployment "alert-service" successfully rolled out

# Verify pods running
kubectl get pods -n staging | grep alert-service

# Expected: All pods Running with X/X ready
# alert-service-xxxx-yyyy   2/2     Running   0          2m
# alert-service-xxxx-zzzz   2/2     Running   0          2m
# alert-service-xxxx-wwww   2/2     Running   0          2m
```

**Deployment Checklist**:
- [ ] Deployment updated successfully
- [ ] Rollout completed (no errors)
- [ ] All pods running (3/3 or configured count)
- [ ] No pod crashes or restarts
- [ ] Pods ready (2/2 containers per pod)

### Step 2.5: Verify Health Checks

```bash
# Wait 30 seconds for startup
sleep 30

# Check basic health
curl -f https://staging-api.clinica.com/health
# Expected: {"status":"healthy","timestamp":"..."}

# Check alerts endpoint
curl -f https://staging-api.clinica.com/api/v1/alerts/health
# Expected: {"status":"healthy","system":"legacy"}

# Check database connection
curl -f https://staging-api.clinica.com/api/v1/health/database
# Expected: {"status":"connected","latency_ms":XX}

# Check Redis connection
curl -f https://staging-api.clinica.com/api/v1/health/redis
# Expected: {"status":"connected","latency_ms":XX}
```

**Health Check Validation**:
- [ ] API responding (200 OK)
- [ ] Health endpoint healthy
- [ ] Alert service responding
- [ ] Database connected
- [ ] Redis connected
- [ ] All checks <100ms latency

---

## 🧪 PHASE 3: SMOKE TESTING

**Duration**: 1 hour  
**Status**: ⏳ Pending

### Smoke Test 1: Legacy System Baseline

```bash
# Set authentication token
export TOKEN="your-staging-jwt-token"

# Test 1A: List alerts (legacy)
curl -X GET "https://staging-api.clinica.com/api/v1/alerts?page=1&size=10" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/json" \
  | jq .

# Verify response:
# - Status: 200 OK
# - Returns: {"items": [...], "total": X, "page": 1, "size": 10}
# - Response time: < 200ms
```

**Result**: [ ] PASS [ ] FAIL  
**Notes**: _______________________________________________

```bash
# Test 1B: Get specific alert
ALERT_ID="<existing-alert-id>"
curl -X GET "https://staging-api.clinica.com/api/v1/alerts/$ALERT_ID" \
  -H "Authorization: Bearer $TOKEN" \
  | jq .

# Verify:
# - Status: 200 OK
# - Returns complete alert object
```

**Result**: [ ] PASS [ ] FAIL  
**Notes**: _______________________________________________

### Smoke Test 2: Enable Consolidated System

```bash
# Enable consolidated alerts
kubectl set env deployment/alert-service \
  USE_CONSOLIDATED_ALERTS=true \
  -n staging

# Monitor rollout (should be fast - just env var change)
kubectl rollout status deployment/alert-service -n staging

# Verify pods restarted
kubectl get pods -n staging | grep alert-service

# Check logs for confirmation
kubectl logs -f deployment/alert-service -n staging | grep "consolidated"

# Expected log:
# "Using consolidated alert system with adapter (QW-020)"
```

**Result**: [ ] PASS [ ] FAIL  
**Notes**: _______________________________________________

### Smoke Test 3: Consolidated System Validation

```bash
# Wait 30 seconds for system to stabilize
sleep 30

# Test 3A: List alerts (consolidated)
curl -X GET "https://staging-api.clinica.com/api/v1/alerts?page=1&size=10" \
  -H "Authorization: Bearer $TOKEN" \
  | jq .

# Verify:
# - Status: 200 OK
# - Response format IDENTICAL to legacy
# - Response time similar to legacy (<200ms)
# - Data consistency maintained
```

**Result**: [ ] PASS [ ] FAIL  
**Response Time**: _____ms (vs legacy: _____ms)  
**Notes**: _______________________________________________

```bash
# Test 3B: Get alert statistics
curl -X GET "https://staging-api.clinica.com/api/v1/alerts/statistics" \
  -H "Authorization: Bearer $TOKEN" \
  | jq .

# Verify:
# - Status: 200 OK
# - Contains: total_alerts, by_severity, by_status
# - Numbers make sense
```

**Result**: [ ] PASS [ ] FAIL  
**Notes**: _______________________________________________

### Smoke Test 4: Write Operations

```bash
# Test 4A: Acknowledge alert
ALERT_ID="<pending-alert-id>"
curl -X POST "https://staging-api.clinica.com/api/v1/alerts/$ALERT_ID/acknowledge" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user-id",
    "notes": "Smoke test - consolidated system"
  }' \
  | jq .

# Verify:
# - Status: 200 OK
# - Alert status changed to ACKNOWLEDGED
# - acknowledged_by set correctly
# - acknowledged_at timestamp present
```

**Result**: [ ] PASS [ ] FAIL  
**Notes**: _______________________________________________

```bash
# Test 4B: Resolve alert
curl -X POST "https://staging-api.clinica.com/api/v1/alerts/$ALERT_ID/resolve" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "resolution_notes": "Smoke test resolution"
  }' \
  | jq .

# Verify:
# - Status: 200 OK
# - Alert status changed to RESOLVED
# - resolved_at timestamp present
```

**Result**: [ ] PASS [ ] FAIL  
**Notes**: _______________________________________________

### Smoke Test 5: Feature Flag Toggle

```bash
# Toggle back to legacy
kubectl set env deployment/alert-service \
  USE_CONSOLIDATED_ALERTS=false \
  -n staging

kubectl rollout status deployment/alert-service -n staging
sleep 30

# Test with legacy
curl "https://staging-api.clinica.com/api/v1/alerts" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.items | length'

# Toggle back to consolidated
kubectl set env deployment/alert-service \
  USE_CONSOLIDATED_ALERTS=true \
  -n staging

kubectl rollout status deployment/alert-service -n staging
sleep 30

# Test with consolidated
curl "https://staging-api.clinica.com/api/v1/alerts" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.items | length'

# Verify:
# - Both return same data
# - Toggle works smoothly
# - No errors during switch
```

**Result**: [ ] PASS [ ] FAIL  
**Notes**: _______________________________________________

### Smoke Test 6: Background Tasks

```bash
# Trigger background task
curl -X POST "https://staging-api.clinica.com/api/v1/alerts/tasks/check-patient-alerts" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_ids": ["test-patient-id"]
  }' \
  | jq .

# Check Celery logs
kubectl logs -f deployment/celery-worker -n staging | grep "check_patient_alerts"

# Verify:
# - Task accepted
# - Task executes successfully
# - Uses consolidated system
# - No errors in logs
```

**Result**: [ ] PASS [ ] FAIL  
**Notes**: _______________________________________________

---

## 📊 PHASE 4: MONITORING & VALIDATION

**Duration**: 2 hours  
**Status**: ⏳ Pending

### Step 4.1: Application Metrics (First 30 Minutes)

```bash
# Monitor Prometheus metrics
# Open Grafana dashboard: https://grafana.staging.clinica.com

# Key metrics to watch:
# 1. Request rate
# 2. Response time (P50, P95, P99)
# 3. Error rate
# 4. CPU/Memory usage
# 5. Database connections
```

**Metrics Snapshot (t=30min)**:
- Request rate: _____ req/s (baseline: _____ req/s)
- P95 latency: _____ms (baseline: _____ms)
- P99 latency: _____ms (baseline: _____ms)
- Error rate: _____% (target: <0.1%)
- CPU usage: _____% (target: <50%)
- Memory: _____MB (target: <512MB)

**Status**: [ ] Normal [ ] Degraded [ ] Critical

### Step 4.2: Error Monitoring

```bash
# Check application logs
kubectl logs -f deployment/alert-service -n staging

# Look for:
# - ERROR level logs
# - Exception traces
# - Warning patterns
# - Deprecation warnings (expected when legacy used)

# Check Sentry for errors
# Open: https://sentry.io/organizations/clinica/issues/?project=XXX

# Expected: 0 new errors related to consolidated alerts
```

**Error Summary**:
- Total errors (2h): _____
- Critical errors: _____
- Warnings: _____
- Related to QW-020: _____

**Status**: [ ] Clean [ ] Minor issues [ ] Major issues

### Step 4.3: Database Performance

```bash
# Connect to staging database
psql $DATABASE_URL

-- Check slow queries
SELECT 
  query,
  mean_exec_time,
  calls,
  total_exec_time
FROM pg_stat_statements
WHERE query LIKE '%alert%'
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Check connection pool
SELECT count(*) as connections, state
FROM pg_stat_activity
WHERE application_name LIKE '%clinica%'
GROUP BY state;

-- Check table size
SELECT 
  pg_size_pretty(pg_total_relation_size('alerts')) as total_size,
  COUNT(*) as row_count
FROM alerts;
```

**Database Metrics**:
- Slowest query: _____ms
- Active connections: _____
- Idle connections: _____
- Alert table size: _____MB
- Query patterns: [ ] Normal [ ] Unusual

**Status**: [ ] Healthy [ ] Needs attention

### Step 4.4: Comparative Analysis

**Legacy vs Consolidated Comparison** (measure with feature flag):

```bash
# Test with legacy (USE_CONSOLIDATED_ALERTS=false)
# Run 100 requests and measure
for i in {1..100}; do
  curl -w "@curl-format.txt" -s \
    "https://staging-api.clinica.com/api/v1/alerts?page=1&size=10" \
    -H "Authorization: Bearer $TOKEN" \
    -o /dev/null
done | awk '{sum+=$1; count++} END {print "Avg: " sum/count " ms"}'

# Test with consolidated (USE_CONSOLIDATED_ALERTS=true)
# Run 100 requests and measure
# (repeat above after switching flag)
```

**Comparison Results**:
| Metric | Legacy | Consolidated | Difference | Status |
|--------|--------|--------------|------------|--------|
| Avg Response Time | ___ms | ___ms | ___% | [ ] OK |
| P95 Response Time | ___ms | ___ms | ___% | [ ] OK |
| P99 Response Time | ___ms | ___ms | ___% | [ ] OK |
| Error Rate | ___% | ___% | ___% | [ ] OK |
| CPU Usage | ___% | ___% | ___% | [ ] OK |
| Memory Usage | ___MB | ___MB | ___% | [ ] OK |

**Acceptance Criteria**: Consolidated system within 5% of legacy

---

## 🎯 PHASE 5: GO/NO-GO DECISION

**Duration**: 30 minutes  
**Status**: ⏳ Pending

### Decision Matrix

#### Technical Validation ✅

| Criterion | Required | Actual | Status |
|-----------|----------|--------|--------|
| Tests passing | 148/148 | ___/___ | [ ] PASS |
| Code coverage | ≥95% | ___% | [ ] PASS |
| Smoke tests | 6/6 | ___/___ | [ ] PASS |
| Performance | Within 5% | ___% | [ ] PASS |
| Error rate | <0.1% | ___% | [ ] PASS |
| Monitoring | All green | [ ] | [ ] PASS |

#### Operational Readiness ✅

| Criterion | Status |
|-----------|--------|
| Team available for production | [ ] YES |
| Rollback tested and verified | [ ] YES |
| Documentation complete | [ ] YES |
| Stakeholders informed | [ ] YES |
| On-call engineer assigned | [ ] YES |

### Decision

**GO Decision** (proceed to production):
- [ ] All technical criteria met
- [ ] All operational criteria met
- [ ] No critical issues found
- [ ] Team consensus: GO

**NO-GO Decision** (delay deployment):
- [ ] Technical criteria not met
- [ ] Critical issues found
- [ ] Team not ready
- [ ] Stakeholder concerns

### Signatures

**Engineering Lead**: _________________ Date: _____  
**QA Lead**: _________________ Date: _____  
**DevOps Lead**: _________________ Date: _____  
**Tech Lead**: _________________ Date: _____

---

## 🔄 ROLLBACK PROCEDURE

### Emergency Rollback (If Needed)

```bash
# Step 1: Disable consolidated alerts immediately
kubectl set env deployment/alert-service \
  USE_CONSOLIDATED_ALERTS=false \
  -n staging

# Step 2: Monitor rollout
kubectl rollout status deployment/alert-service -n staging

# Step 3: Verify legacy system active
sleep 30
curl https://staging-api.clinica.com/api/v1/alerts/health
# Expected: {"status":"healthy","system":"legacy"}

# Step 4: Monitor for 5 minutes
# Check metrics, logs, errors

# Step 5: If stable, document issue and schedule fix
```

**Rollback Time**: ~1 minute  
**Impact**: Minimal (instant switch to legacy)

---

## 📝 POST-DEPLOYMENT CHECKLIST

### Immediate (Within 1 Hour)
- [ ] All smoke tests passing
- [ ] Monitoring dashboards green
- [ ] Error rate acceptable
- [ ] Performance acceptable
- [ ] Team notified of completion

### Short-Term (Within 4 Hours)
- [ ] 2-hour monitoring period completed
- [ ] No regressions detected
- [ ] Stakeholders updated
- [ ] Documentation updated
- [ ] Go/No-Go decision made

### Next Steps
- [ ] If GO: Schedule Day 5 (Production)
- [ ] If NO-GO: Document issues, create action plan
- [ ] Update project tracking
- [ ] Team retrospective scheduled

---

## 📞 Support & Escalation

### Immediate Support
- **On-Call Engineer**: [Name] - [Phone]
- **DevOps On-Call**: [Name] - [Phone]

### Escalation Path
1. **Level 1**: On-Call Engineer (0-5 min)
2. **Level 2**: Tech Lead (5-15 min)
3. **Level 3**: Engineering Manager (15-30 min)
4. **Level 4**: CTO (30-60 min)

### Communication Channels
- **Slack**: #qw020-deployment
- **Incident Channel**: #incidents
- **Email**: engineering@clinica.com

---

## ✅ SUCCESS CRITERIA

### Deployment Successful When:
1. ✅ All 148+ tests passing
2. ✅ Code coverage ≥95%
3. ✅ All 6 smoke tests passing
4. ✅ Performance within 5% of legacy
5. ✅ Error rate <0.1%
6. ✅ 2 hours monitoring completed
7. ✅ Zero critical issues
8. ✅ Feature flag toggle verified
9. ✅ Team consensus: GO
10. ✅ Ready for Day 5 (Production)

---

**Document Version**: 1.0  
**Created**: 2025-01-22  
**Status**: ✅ READY FOR USE  
**Next**: Execute staging deployment following this guide