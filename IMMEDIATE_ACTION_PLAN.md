# Immediate Action Plan - Production Release
**Status**: 🔴 **BLOCKERS IDENTIFIED**  
**Generated**: 2025-01-22 06:00 UTC-3  
**Priority**: P0 - Critical Path Items

---

## 🎯 Executive Summary

**Current State**: Branch `docs-refactor-py313` is **NOT production-ready**  
**Blockers**: 3 critical security/quality issues  
**Timeline**: 2-3 days to resolution + validation  
**Risk Level**: 🔴 **HIGH** (security vulnerability active in AuthContext)

---

## 🚨 CRITICAL - Do This First (30 minutes)

### 1. Fix AuthContext Token Leakage (P0 - Security)
**Why**: Firebase tokens persist on API client, defeating cookie-only auth security model  
**Impact**: XSS vulnerability, session hijacking risk

```powershell
# Review the fix specification
code SECURITY_AUTHCONTEXT_FIX.md

# Key changes needed in frontend-hormonia/src/contexts/AuthContext.tsx:
# - Add finally block to transformFirebaseUser() (lines 109-149)
# - Remove setAuthToken from auth state listener (line 206)  
# - Add finally cleanup to token refresh listener (lines 240-252)
```

**Files to Edit**:
- `frontend-hormonia/src/contexts/AuthContext.tsx`

**Validation**:
```powershell
cd frontend-hormonia
npm run typecheck
npm run lint
# Manually test: DevTools Network tab should show NO Authorization header
```

---

### 2. Clean Coverage Artifacts (P0 - Build Hygiene)
**Why**: Coverage reports are build artifacts causing merge conflicts  
**Impact**: Repository bloat, noisy commits

```powershell
# Run automated cleanup
.\scripts\cleanup-coverage-artifacts.ps1

# Review changes
git status

# Commit
git add backend-hormonia/.gitignore
git commit -m "chore: remove coverage artifacts from version control"
```

**Expected Changes**:
- `backend-hormonia/coverage.json` removed from git
- `backend-hormonia/coverage.lcov` removed from git
- `backend-hormonia/test_results.txt` removed from git
- `.gitignore` updated with coverage patterns

---

### 3. Run Full Validation Suite (P0 - Quality Gate)
**Why**: Current coverage/test status is unknown  
**Impact**: Cannot certify production readiness

```powershell
# Comprehensive validation (all modules)
.\scripts\validate-release.ps1

# This will test:
# ✓ Backend: pytest + coverage (≥80%)
# ✓ Frontend: lint + typecheck + vitest + coverage (≥80%)
# ✓ Quiz: jest + coverage
# ✓ E2E: Playwright smoke tests

# Results saved to: validation-reports/YYYY-MM-DD_HH-mm-ss/
```

**Expected Duration**: 10-15 minutes  
**Success Criteria**: All tests pass, coverage ≥80%

---

## 📋 PHASE 1: Immediate Fixes (Today)

### ✅ Completed
1. ✅ Security review of firebase-auth.ts (token cleanup implemented)
2. ✅ `.gitignore` updated for coverage artifacts
3. ✅ Cleanup scripts created (PowerShell + Bash)
4. ✅ Validation automation script created
5. ✅ Release readiness checklist documented

### 🔴 Critical Remaining Tasks

#### A. Security Fix Implementation (1-2 hours)
- [ ] Apply AuthContext token cleanup (see `SECURITY_AUTHCONTEXT_FIX.md`)
- [ ] Run `npm run typecheck` (must pass)
- [ ] Run `npm run lint:fix` (zero warnings)
- [ ] Manual smoke test: Login → verify no Authorization header in DevTools
- [ ] Git commit: `fix(auth): clear Firebase tokens after validation in AuthContext`

#### B. Coverage Artifact Cleanup (15 minutes)
- [ ] Run `.\scripts\cleanup-coverage-artifacts.ps1`
- [ ] Verify `.gitignore` changes
- [ ] Git commit: `chore: remove coverage artifacts from version control`
- [ ] Push to remote branch

#### C. Test Suite Execution (30 minutes)
- [ ] Run `.\scripts\validate-release.ps1`
- [ ] Review reports in `validation-reports/` directory
- [ ] Fix any failing tests
- [ ] Ensure coverage ≥80% across all modules
- [ ] Document results in `RELEASE_READINESS_CHECKLIST.md`

---

## 📋 PHASE 2: Validation & Documentation (Tomorrow)

### A. Environment Configuration Audit (1 hour)
```powershell
# Compare .env.example with production .env
cd backend-hormonia
code .env.example

# Document any new variables needed:
# - FIREBASE_SERVICE_ACCOUNT_KEY (rotate if changed)
# - GEMINI_API_KEY (verify quota)
# - WHATSAPP_API_TOKEN (test connectivity)
# - REDIS_PASSWORD (rotate if exposed)
```

**Checklist**:
- [ ] All new env vars documented in `.env.example`
- [ ] Production secrets rotated (especially Firebase)
- [ ] Staging environment updated with new vars
- [ ] Integration tests passed (Firebase, Gemini, WhatsApp)

### B. Flow/Messaging Integration Tests (2 hours)
```powershell
cd backend-hormonia

# New code needs test coverage:
# - app/services/flow/*
# - app/services/messaging/*

# Create tests in:
# - tests/services/test_flow_*.py
# - tests/services/test_messaging_*.py

# Target: ≥80% coverage on new modules
```

**Checklist**:
- [ ] Flow service unit tests created
- [ ] Messaging service unit tests created
- [ ] Integration tests for WhatsApp connectivity
- [ ] Error handling tests (API failures, timeouts)
- [ ] Coverage reports show ≥80% on new code

### C. Operational Readiness (1 hour)
```powershell
cd backend-hormonia

# Start services
make docker-up

# Wait 30 seconds for initialization
Start-Sleep -Seconds 30

# Check service health
docker compose logs --tail=100 celery redis
docker compose ps

# Test health endpoints
curl http://localhost:8000/health/ready
curl http://localhost:8000/health/startup
curl http://localhost:8000/metrics
```

**Checklist**:
- [ ] Celery worker processing tasks (check logs)
- [ ] Redis responding to PING (`redis-cli ping`)
- [ ] PostgreSQL migrations up to date (`make migrate`)
- [ ] Firebase auth working (test login flow)
- [ ] Gemini API responding (test quiz generation)
- [ ] WhatsApp API connected (test message send)

---

## 📋 PHASE 3: Pre-Production (Day 3)

### A. Documentation Finalization (2 hours)
- [ ] Update `SECURITY_FIXES_SUMMARY.md` with cookie-only auth migration
- [ ] Update `CRITICAL_FIXES_FINAL.md` with all P0/P1 fixes
- [ ] Update `DEPLOYMENT_CHECKLIST.md` with new env vars
- [ ] Create `CHANGELOG.md` with user-facing changes
- [ ] Update API documentation (OpenAPI/Swagger)

### B. Merge Strategy & Branch Cleanup (1 hour)
```powershell
# Review divergence
git log origin/main..HEAD --oneline
# Should show 16+ commits

# Squash WIP commits (interactive rebase)
git rebase -i origin/main

# Example squash:
# pick abc1234 feat(auth): implement cookie-only authentication
# squash def5678 fix: typo in auth service
# squash ghi9012 fix: linting errors
# pick jkl3456 feat(flow): add patient flow integration
```

**Checklist**:
- [ ] Commits squashed into logical units
- [ ] Commit messages follow Conventional Commits
- [ ] No "WIP" or "temp" commits remain
- [ ] Branch rebased on latest `main`
- [ ] Force push to remote: `git push --force-with-lease`

### C. E2E Smoke Tests in Staging (2 hours)
```powershell
cd frontend-hormonia

# Set staging environment
$env:VITE_API_BASE_URL = "https://staging-api.example.com"

# Run full E2E suite
npm run test:e2e

# Critical paths to verify:
# ✓ Login with cookie-only auth
# ✓ Token refresh at 55min (no Authorization header)
# ✓ Quiz creation and submission
# ✓ Patient CRUD operations
# ✓ WebSocket real-time updates
# ✓ Logout and session cleanup
```

**Checklist**:
- [ ] All critical user flows pass
- [ ] No Authorization headers in Network tab (only Cookie)
- [ ] Session persists across page refreshes
- [ ] Token refresh works silently (background)
- [ ] Logout clears session and redirects to login
- [ ] Screenshots saved for failed tests

---

## 🚀 PHASE 4: Production Deployment (Day 4)

### Pre-Deployment Checklist
- [ ] All Phase 1-3 tasks completed
- [ ] All tests passing (backend, frontend, quiz, E2E)
- [ ] Coverage ≥80% across all modules
- [ ] Security vulnerabilities resolved (AuthContext fixed)
- [ ] Documentation up to date
- [ ] Staging environment validated (24h uptime)
- [ ] Rollback plan tested
- [ ] Stakeholder approval obtained

### Deployment Steps
1. **Code Freeze** (1 hour before deployment)
   - Merge `docs-refactor-py313` → `main`
   - Tag release: `git tag -a v2.0.0 -m "Cookie-only auth + Flow integration"`
   - Trigger CI/CD pipeline

2. **Database Backup** (30 minutes)
   ```bash
   # Full PostgreSQL dump
   pg_dump -h <host> -U <user> -d hormonia_prod > backup_$(date +%Y%m%d_%H%M%S).sql
   
   # Redis snapshot
   redis-cli BGSAVE
   ```

3. **Deployment** (30 minutes)
   - Deploy backend (rolling update, zero downtime)
   - Run migrations: `make migrate` on production
   - Deploy frontend (CDN cache invalidation)
   - Deploy quiz app (Railway)
   - Verify health checks: `/health/ready` → 200 OK

4. **Post-Deployment Validation** (1 hour)
   - Monitor logs for errors (first 15 minutes)
   - Run smoke tests against production
   - Check metrics: response times, error rates
   - Verify integrations: Firebase, Gemini, WhatsApp
   - Alert validation: trigger test alert

### Rollback Criteria
**Immediate rollback if**:
- Health checks failing (>5% error rate)
- Authentication broken (users cannot login)
- Database errors (migration issues)
- Third-party integrations down (Firebase, Gemini, WhatsApp)
- Response times >2s p95

**Rollback Command**:
```bash
git revert <merge-commit-sha>
git push origin main
# Redeploy previous version via CI/CD
```

---

## 📊 Success Metrics

### Pre-Production
- ✅ Test coverage ≥80% (backend + frontend + quiz)
- ✅ Zero linting warnings
- ✅ Zero TypeScript errors
- ✅ All E2E smoke tests green
- ✅ Security vulnerabilities resolved (AuthContext)
- ✅ Coverage artifacts cleaned from git

### Production (First 24 Hours)
- ✅ Authentication success rate ≥99.5%
- ✅ API response time p95 <300ms
- ✅ Error rate <0.5%
- ✅ Zero security incidents
- ✅ Session persistence working (cookie-only)
- ✅ Token refresh working (no Authorization header leakage)

---

## 🆘 Emergency Contacts

**Release Manager**: [Name] - [Contact]  
**Security Lead**: [Name] - [Contact]  
**On-Call Engineer**: [Name] - [Contact]  
**Database Admin**: [Name] - [Contact]

**Escalation Path**: Engineer → Tech Lead → CTO

---

## 📁 Quick Reference

### Key Documents
- `RELEASE_READINESS_CHECKLIST.md` - Comprehensive checklist
- `SECURITY_AUTHCONTEXT_FIX.md` - Security fix specification
- `DEPLOYMENT_CHECKLIST.md` - Deployment runbook
- `validation-reports/` - Test execution reports

### Key Scripts
- `.\scripts\validate-release.ps1` - Run all tests
- `.\scripts\cleanup-coverage-artifacts.ps1` - Clean git artifacts
- `make test-cov` - Backend tests (from backend-hormonia/)
- `npm run quality` - Frontend quality gate (from frontend-hormonia/)

### Key Commands
```powershell
# Start all services
cd backend-hormonia && make docker-up

# Run full validation
.\scripts\validate-release.ps1

# Check service health
docker compose logs --tail=50 celery redis
curl http://localhost:8000/health/ready

# Frontend dev server
cd frontend-hormonia && npm run dev
```

---

**Status**: 🔴 **BLOCKERS ACTIVE**  
**Next Review**: After Phase 1 completion  
**Target Go-Live**: Day 4 (pending validation)

---

## 🎬 Start Here - Copy/Paste Commands

```powershell
# STEP 1: Review security fix
code c:\Meu` Projetos\clinica-oncologica-v02\SECURITY_AUTHCONTEXT_FIX.md

# STEP 2: Clean coverage artifacts
cd "c:\Meu Projetos\clinica-oncologica-v02"
.\scripts\cleanup-coverage-artifacts.ps1

# STEP 3: Run full validation
.\scripts\validate-release.ps1

# STEP 4: Review results
code validation-reports\<timestamp>\validation-summary.json

# After validation passes:
# STEP 5: Update release checklist with results
code RELEASE_READINESS_CHECKLIST.md
```

**Time to Complete Phase 1**: ~2 hours  
**Time to Production Ready**: 2-3 days
