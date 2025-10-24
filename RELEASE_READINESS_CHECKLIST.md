# Release Readiness Checklist
**Generated**: 2025-01-22  
**Target Branch**: `docs-refactor-py313`  
**Status**: ⚠️ **NOT READY FOR PRODUCTION**

---

## Executive Summary

The codebase has **critical security gaps** and **incomplete testing** that must be resolved before production deployment. While significant progress has been made on cookie-only authentication in `firebase-auth.ts`, the legacy `AuthContext.tsx` undermines this security model by maintaining persistent Firebase tokens on the global API client.

**BLOCKERS**: 3 critical, 5 high-priority  
**Estimated Resolution Time**: 2-3 days

---

## 🔴 Critical Blockers

### 1. **SECURITY: Token Leakage in AuthContext** (P0)
**File**: `frontend-hormonia/src/contexts/AuthContext.tsx`  
**Impact**: Authorization header persists across all requests, defeating cookie-only security model

**Issue Details**:
- ✅ `firebase-auth.ts` correctly clears tokens via `finally` blocks (lines 142, 287, 360)
- ❌ `AuthContext.tsx` sets tokens but **never clears** them:
  - Line 114: `transformFirebaseUser()` - no cleanup
  - Line 206: Auth state listener - token stays attached
  - Line 250: Token refresh - no cleanup after validation

**Risk**: 
- Firebase bearer tokens ride along with every API request
- Session hijacking via XSS if token is intercepted
- Violates security model documented in memories

**Required Action**:
```typescript
// Add finally blocks to all setAuthToken() calls in AuthContext.tsx
// Example for transformFirebaseUser:
try {
  apiClient.setAuthToken(token)
  const response = await apiClient.auth.me()
  // ...
} finally {
  apiClient.clearAuthToken()
  logger.log('Cleared token after validation')
}
```

**Files to Update**:
- `frontend-hormonia/src/contexts/AuthContext.tsx` (lines 109-149, 195-237, 240-252)

---

### 2. **BUILD HYGIENE: Coverage Artifacts in Version Control** (P0)
**Files**: 
- `backend-hormonia/coverage.json` (should be ignored)
- `backend-hormonia/coverage.lcov` (should be ignored)
- `backend-hormonia/test_results.txt` (should be ignored)

**Issue**: Coverage reports are build artifacts that change on every test run, causing unnecessary merge conflicts and bloating repository size.

**Required Action**:
```bash
# 1. Update .gitignore
cd backend-hormonia
echo "coverage.json" >> .gitignore
echo "coverage.lcov" >> .gitignore
echo "test_results.txt" >> .gitignore
echo "htmlcov/" >> .gitignore

# 2. Remove from version control
git rm --cached coverage.json coverage.lcov test_results.txt
git commit -m "chore: remove coverage artifacts from version control"
```

---

### 3. **CONFIGURATION: Environment Variable Drift** (P0)
**File**: `backend-hormonia/.env.example`  
**Status**: Modified but production sync unconfirmed

**Required Action**:
1. **Audit**: Compare `.env.example` against actual production `.env`
2. **Document**: List all new variables in deployment checklist
3. **Rotate**: Update production secrets for:
   - `FIREBASE_SERVICE_ACCOUNT_KEY`
   - `GEMINI_API_KEY`
   - `WHATSAPP_API_TOKEN`
   - `REDIS_PASSWORD` (if changed)
4. **Validate**: Test all integrations in staging before production

---

## 🟡 High-Priority Issues

### 4. **TESTING: Incomplete Coverage** (P1)
**Current Status**: Unknown (artifacts outdated)  
**Required**: ≥80% coverage across all modules

**Action Items**:
```bash
# Backend
cd backend-hormonia
make test-cov
# Verify: htmlcov/index.html shows ≥80%

# Frontend
cd frontend-hormonia
npm run test:ci
# Verify: coverage/index.html shows ≥80%

# Quiz App
cd quiz-mensal-interface
pnpm test:coverage
# Verify: coverage thresholds pass
```

**Missing Test Coverage**:
- ❌ `backend-hormonia/app/services/flow/*` (new Flow integration)
- ❌ `backend-hormonia/app/services/messaging/*` (WhatsApp/SMS)
- ❌ `frontend-hormonia/src/lib/api-client-wrapper.ts` (new wrapper)
- ❌ AuthContext token cleanup (after security fix)

---

### 5. **DOCUMENTATION: Incomplete Release Notes** (P1)
**Files to Finalize**:
- [ ] `SECURITY_FIXES_SUMMARY.md` - Document cookie-only auth migration
- [ ] `CRITICAL_FIXES_FINAL.md` - Consolidate all P0/P1 fixes
- [ ] `DEPLOYMENT_CHECKLIST.md` - Add new env vars, migration steps
- [ ] `CHANGELOG.md` - User-facing changes for this release

---

### 6. **OPERATIONAL: Service Health Unvalidated** (P1)
**Services Requiring Validation**:
- [ ] **Celery**: Task queue processing (`docker compose logs celery`)
- [ ] **Redis**: Cache + session store (`docker compose exec redis redis-cli ping`)
- [ ] **Firebase**: Auth token validation (check logs for 401s)
- [ ] **Gemini AI**: Quiz generation (test `/api/v2/quiz/generate`)
- [ ] **WhatsApp**: Message delivery (test Flow integration)

**Action**:
```bash
cd backend-hormonia
make docker-up
docker compose logs --tail=100 celery redis
# Look for connection errors, task failures
```

---

### 7. **MERGE STRATEGY: Branch Divergence** (P1)
**Current State**: `docs-refactor-py313` is +16 commits ahead of `origin`  
**Risk**: Merge conflicts on deployment day

**Required**:
1. **Review**: Audit all 16 commits for breaking changes
2. **Squash**: Consolidate WIP commits before merge
3. **Rebase**: Sync with latest `main`/`production` branch
4. **Test**: Re-run full test suite after rebase

---

### 8. **E2E TESTING: Smoke Tests Missing** (P1)
**Required Before Go-Live**:
```bash
cd frontend-hormonia
npm run test:e2e:smoke

# Must pass all critical paths:
# ✓ User login with cookie-only auth
# ✓ Token refresh without Authorization header leak
# ✓ Quiz creation and submission
# ✓ Patient CRUD operations
# ✓ Session validation after 55min token refresh
```

---

## 📋 Pre-Production Validation Checklist

### Security Review
- [ ] All `setAuthToken()` calls have corresponding `clearAuthToken()` cleanup
- [ ] CSRF token fetched before every login attempt
- [ ] Rate limiting active on all write endpoints (patients, quiz, analytics)
- [ ] RBAC enforced: write operations require ADMIN/DOCTOR role
- [ ] Secrets rotation completed in production environment
- [ ] SQL injection protection via ORM confirmed (no raw queries)

### Testing & Quality
- [ ] Backend: `make test-cov` ≥80% coverage
- [ ] Frontend: `npm run quality` passes (lint + typecheck + test)
- [ ] Quiz: `pnpm test:coverage` meets thresholds
- [ ] E2E: `npm run test:e2e:smoke` all green
- [ ] Performance: No N+1 queries (check analytics endpoints)
- [ ] Load test: Simulate 100 concurrent users on staging

### Configuration & Environment
- [ ] `.env.example` matches production `.env` structure
- [ ] All new env vars documented in deployment guide
- [ ] Firebase service account key rotated and validated
- [ ] Redis connection string tested (TLS if required)
- [ ] Database migration dry-run completed (`make migrate`)

### Documentation
- [ ] API changes documented in OpenAPI/Swagger
- [ ] Frontend breaking changes communicated to team
- [ ] Deployment runbook updated with rollback steps
- [ ] Incident response plan reviewed
- [ ] Monitoring/alerting configured (Sentry, DataDog, etc.)

### Operational Readiness
- [ ] Health checks returning 200 OK (`/health/ready`)
- [ ] Metrics endpoint accessible (`/metrics`)
- [ ] Log aggregation configured (centralized logging)
- [ ] Backup strategy validated (database + Redis snapshots)
- [ ] Rollback plan tested (restore from backup)

---

## 🚀 Deployment Steps (After All Checks Pass)

### Phase 1: Pre-Deployment (1 hour)
1. **Freeze Code**: Merge `docs-refactor-py313` → `main`
2. **Tag Release**: `git tag -a v2.0.0 -m "Cookie-only auth + Flow integration"`
3. **Build Artifacts**: Run CI/CD pipeline
4. **Database Backup**: Full PostgreSQL dump
5. **Redis Snapshot**: Save current session state

### Phase 2: Deployment (30 minutes)
1. **Database Migration**: `make migrate` on production
2. **Deploy Backend**: Rolling update (zero-downtime)
3. **Deploy Frontend**: CDN cache invalidation
4. **Deploy Quiz App**: Railway deployment
5. **Verify Health**: All `/health/*` endpoints green

### Phase 3: Post-Deployment (1 hour)
1. **Smoke Tests**: Run critical user flows manually
2. **Monitor Logs**: Watch for errors (15 min window)
3. **Performance Check**: Response times < 200ms p95
4. **Alert Validation**: Trigger test alert, verify delivery
5. **Rollback Ready**: Keep previous version on standby

---

## 📊 Test Results (To Be Filled)

### Backend Coverage
```
Date: ___________
Command: make test-cov
Coverage: ____%
Report: backend-hormonia/htmlcov/index.html
```

### Frontend Coverage
```
Date: ___________
Command: npm run test:ci
Coverage: ____%
Report: frontend-hormonia/coverage/index.html
```

### E2E Tests
```
Date: ___________
Command: npm run test:e2e:smoke
Passed: ___/___
Report: frontend-hormonia/playwright-report/index.html
```

---

## 🔧 Quick Fix Commands

### Clean Coverage Artifacts
```bash
cd backend-hormonia
git rm --cached coverage.json coverage.lcov test_results.txt
echo -e "\n# Test coverage\ncoverage.json\ncoverage.lcov\ntest_results.txt\nhtmlcov/" >> .gitignore
git commit -m "chore: ignore coverage artifacts"
```

### Run Full Test Suite
```bash
# Backend
cd backend-hormonia && make test-cov

# Frontend
cd frontend-hormonia && npm run quality && npm run test:e2e:smoke

# Quiz
cd quiz-mensal-interface && pnpm test:coverage
```

### Verify Service Health
```bash
cd backend-hormonia
make docker-up
sleep 10
docker compose logs --tail=50 celery redis
curl http://localhost:8000/health/ready
```

---

## 📞 Contact & Escalation

**Release Manager**: [Name]  
**Security Lead**: [Name]  
**On-Call Engineer**: [Name]  

**Rollback Decision Authority**: Product Owner + Tech Lead consensus

---

**Document Status**: 🔴 DRAFT - Awaiting validation results  
**Last Updated**: 2025-01-22 06:00 UTC-3  
**Next Review**: After critical blockers resolved
