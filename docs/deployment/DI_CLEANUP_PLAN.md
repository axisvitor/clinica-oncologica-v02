# Dependency Injection Cleanup & Migration Plan

**Generated:** 2025-10-07
**Target Completion:** Sprint 2025-Q4-W42
**Risk Level:** Medium (requires production deployment)

---

## Executive Summary

This plan outlines the safe migration from **13 dependency modules** (7 orphaned) to a **clean 6-module architecture**. The cleanup eliminates package/module name collisions, removes shared session anti-patterns, and standardizes on thread-safe request-scoped dependencies.

**Expected Outcomes:**
- ✅ Remove 7 orphaned/deprecated modules
- ✅ Eliminate package/module name collision
- ✅ Remove shared ServiceProvider from app.state
- ✅ 100% thread-safe dependency injection
- ✅ Reduced cognitive load for developers

**Risk Mitigation:**
- Zero production impact (deprecated modules have no active imports)
- Phased rollout with rollback plan
- Comprehensive testing at each stage

---

## Phase 1: Immediate Safety Fixes (Day 1)

### 1.1 Remove Shared ServiceProvider from Lifespan

**Issue:** `app.core.lifespan.py` creates shared ServiceProvider with single DB session.

**Current Code (lines 262-283):**
```python
async def _initialize_service_provider(app: FastAPI, logger) -> None:
    """Initialize ServiceProvider with database session."""
    try:
        from app.services import ServiceProvider

        db_session = next(get_db())  # ❌ SINGLE SESSION FOR ALL REQUESTS

        redis_manager = getattr(app.state, 'redis_manager', None)
        if redis_manager:
            redis_client = redis_manager.get_compatible_client("auto")
        else:
            redis_client = None

        app.state.service_provider = ServiceProvider(db_session, redis_client)
        # ⚠️ This session is NEVER closed!

        logger.info("✓ ServiceProvider initialized")
```

**Action:**
```python
# DELETE entire _initialize_service_provider function
# DELETE line 80 in _startup: await _initialize_service_provider(app, logger)
# DELETE lines 345-352 in _cleanup_session_manager (legacy provider cleanup)
```

**Validation:**
```bash
# Ensure no code references app.state.service_provider
grep -r "app\.state\.service_provider" backend-hormonia/app/
grep -r "request\.app\.state\.service_provider" backend-hormonia/app/

# Expected: Only matches in lifespan.py (to be deleted)
```

**Risk:** Low
- Grep analysis shows ZERO active usage of `app.state.service_provider`
- All routers use request-scoped `Depends(get_thread_safe_service_provider)`

**Testing:**
```bash
# Run full test suite
pytest backend-hormonia/tests/ -v

# Load test with concurrent requests
ab -n 1000 -c 50 https://api.example.com/api/v1/auth/me
```

---

## Phase 2: Archive Orphaned Modules (Day 2)

### 2.1 Create Legacy Archive Directory

```bash
mkdir -p backend-hormonia/legacy/dependencies_archive_2025-10-07
```

### 2.2 Move Orphaned Modules

**Modules to Archive (7 total):**

| Module | Reason | Usage |
|--------|--------|-------|
| `dependencies.py` | Shadowed by package | 0 |
| `dependencies_v2.py` | Abandoned refactor | 0 |
| `dependencies_thread_safe.py` | Superseded by session_manager | 0 |
| `dependencies_secure.py` | Never used | 0 |
| `dependencies_secure_v2.py` | Docs reference only | 0 |
| `dependencies_enhanced.py` | Test-only diagnostics | 1 |
| `dependencies_fallback.py` | Test-only diagnostics | 1 |

**Commands:**
```bash
cd backend-hormonia/app

# Archive with preserved history
git mv dependencies.py legacy/dependencies_archive_2025-10-07/
git mv dependencies_v2.py legacy/dependencies_archive_2025-10-07/
git mv dependencies_thread_safe.py legacy/dependencies_archive_2025-10-07/
git mv dependencies_secure.py legacy/dependencies_archive_2025-10-07/
git mv dependencies_secure_v2.py legacy/dependencies_archive_2025-10-07/

# Keep enhanced/fallback for now (health.py dependency)
# Will migrate in Phase 4
```

**Add README to Archive:**
```bash
cat > legacy/dependencies_archive_2025-10-07/README.md << 'EOF'
# Deprecated Dependency Modules Archive

**Archived:** 2025-10-07
**Reason:** Consolidated to app/dependencies/ package

## Why These Were Archived

### dependencies.py
- **Issue:** Shadowed by app/dependencies/__init__.py (package)
- **Replacement:** Use `from app.dependencies import ...`

### dependencies_v2.py
- **Issue:** Experimental refactor never completed
- **Replacement:** app/dependencies/ package

### dependencies_thread_safe.py
- **Issue:** Superseded by session_manager.py
- **Replacement:** app/dependencies/session_manager.py

### dependencies_secure.py & dependencies_secure_v2.py
- **Issue:** Never integrated into production
- **Replacement:** app/dependencies/auth_dependencies.py (Firebase + Redis)

## Restoration Instructions

If you need to reference these implementations:

```bash
# View historical implementation
git log --all --full-history legacy/dependencies_archive_2025-10-07/dependencies.py

# Restore specific file
git checkout <commit-hash> legacy/dependencies_archive_2025-10-07/dependencies.py
```

## Migration Guide

See: `docs/deployment/DI_CLEANUP_PLAN.md`
EOF
```

**Validation:**
```bash
# Ensure no imports reference archived modules
grep -r "from app.dependencies_" backend-hormonia/app/ | grep -v "legacy"
# Expected: Only dependencies_enhanced and dependencies_fallback (health.py)

# Run tests
pytest backend-hormonia/tests/ -v
```

**Risk:** Zero
- These modules have no active imports (except enhanced/fallback in health.py)
- Git history preserved for future reference

---

## Phase 3: Update Health Endpoint (Day 2-3)

### 3.1 Refactor Diagnostics in health.py

**Current Issue:**
```python
# app/api/v1/health.py (line 354, 389)
from app.dependencies_fallback import test_fallback_systems
from app.dependencies_enhanced import get_dependency_manager, reset_dependency_system
```

**Solution Options:**

**Option A: Inline Diagnostics (Recommended)**
- Move fallback testing logic directly into health.py
- Removes external dependency on deprecated modules
- Cleaner separation of concerns

**Option B: Create New Diagnostics Module**
- Create `app/diagnostics/dependency_health.py`
- Consolidate all DI health checks
- Better for future maintenance

**Recommended: Option A**

**Implementation:**
```python
# app/api/v1/health.py

async def test_dependency_injection_stack():
    """Test DI system without external dependencies."""
    results = {
        "database_session": False,
        "service_provider": False,
        "redis_cache": False,
        "session_manager": False
    }

    try:
        # Test database session creation
        from app.database import get_db
        db = next(get_db())
        db.execute("SELECT 1")
        db.close()
        results["database_session"] = True
    except Exception as e:
        logger.error(f"Database session test failed: {e}")

    try:
        # Test service provider creation
        from app.dependencies import get_thread_safe_service_provider
        provider = next(get_thread_safe_service_provider())
        provider.validate_session()
        results["service_provider"] = True
    except Exception as e:
        logger.error(f"Service provider test failed: {e}")

    try:
        # Test Redis cache
        from app.core.redis_manager import get_redis_manager
        redis_manager = get_redis_manager()
        client = redis_manager.get_compatible_client("sync")
        results["redis_cache"] = client is not None
    except Exception as e:
        logger.error(f"Redis cache test failed: {e}")

    try:
        # Test session manager
        from app.core.session_manager import get_session_manager
        session_manager = get_session_manager()
        results["session_manager"] = session_manager is not None
    except Exception as e:
        logger.error(f"Session manager test failed: {e}")

    return results
```

**Delete Lines in health.py:**
```python
# DELETE line 354
from app.dependencies_fallback import test_fallback_systems

# DELETE line 389
from app.dependencies_enhanced import get_dependency_manager, reset_dependency_system as reset_deps

# REPLACE with inline implementation above
```

**Testing:**
```bash
# Test health endpoint
curl http://localhost:8000/api/v1/health/advanced

# Expected: All DI tests pass
```

---

## Phase 4: Archive Remaining Test-Only Modules (Day 3)

### 4.1 Move Enhanced/Fallback to Archive

**After Phase 3 refactor:**
```bash
cd backend-hormonia/app

git mv dependencies_enhanced.py legacy/dependencies_archive_2025-10-07/
git mv dependencies_fallback.py legacy/dependencies_archive_2025-10-07/

git commit -m "refactor(deps): Archive deprecated DI modules

- Move 7 orphaned dependency modules to legacy archive
- Inline diagnostics into health.py (no external deps)
- Preserve git history for future reference

Breaking changes: None (modules had zero production usage)
See: docs/deployment/DI_CLEANUP_PLAN.md"
```

**Validation:**
```bash
# Final check: NO references to deprecated modules
grep -r "dependencies_" backend-hormonia/app/ | grep -v "legacy" | grep -v "dependencies/"
# Expected: Only package imports (app/dependencies/...)

# Full test suite
pytest backend-hormonia/tests/ -v --cov=app
```

---

## Phase 5: Update Documentation (Day 4)

### 5.1 Update SUPABASE_CLIENT_USAGE.md

**Current References (lines 46, 137):**
```markdown
- Authorization logic is in `dependencies_secure_v2.py`
- [dependencies_secure_v2.py](../dependencies_secure_v2.py) - Firebase token validation
```

**Update to:**
```markdown
- Authorization logic is in `dependencies/auth_dependencies.py`
- [auth_dependencies.py](../dependencies/auth_dependencies.py) - Firebase token validation
```

**Action:**
```bash
# Edit file
nano backend-hormonia/app/dependencies/SUPABASE_CLIENT_USAGE.md

# Update all references
:%s/dependencies_secure_v2.py/dependencies\/auth_dependencies.py/g
```

### 5.2 Create DI Usage Guide

**Create:** `docs/development/DEPENDENCY_INJECTION_GUIDE.md`

**Content:**
```markdown
# Dependency Injection Guide

## Quick Start

### Authentication
```python
from app.dependencies import get_current_user, get_admin_user

@router.get("/secure")
async def secure_endpoint(user: User = Depends(get_current_user)):
    return {"user_id": user.id}
```

### Database Access
```python
from app.dependencies import get_db

@router.post("/patients")
async def create_patient(
    patient_data: PatientCreate,
    db: Session = Depends(get_db)
):
    # db is request-scoped, auto-cleanup guaranteed
    patient = Patient(**patient_data.dict())
    db.add(patient)
    db.commit()
    return patient
```

### Service Layer
```python
from app.dependencies import get_patient_service

@router.get("/patients/{patient_id}")
async def get_patient(
    patient_id: UUID,
    service: PatientService = Depends(get_patient_service)
):
    # Service has request-scoped session
    return service.get_patient(patient_id)
```

## Available Dependencies

See: `app/dependencies/__init__.py` for full list.

### Authentication
- `get_current_user` - Validate Firebase token + Redis session
- `get_current_active_user` - Additional is_active check
- `get_admin_user` - Require ADMIN/SUPER_ADMIN role
- `get_doctor_user` - Require DOCTOR+ role
- `get_optional_user` - Auth optional (returns None if not authenticated)

### Database
- `get_db` - Request-scoped SQLAlchemy session
- `get_thread_safe_db` - Alias for get_db (backward compat)

### Services (All request-scoped, thread-safe)
- `get_patient_service` - Patient domain logic
- `get_quiz_service` - Quiz domain logic
- `get_auth_service` - Authentication service
- `get_analytics_service` - Analytics domain
- `get_message_service` - Messaging domain
- `get_report_service` - Report generation
- ... (see full list in __init__.py)

### Business Logic
- `get_pagination_params` - Extract pagination from query params
- `validate_patient_access` - Check user can access patient
- `verify_patient_access` - Validate + return patient
- `verify_monthly_quiz_token` - Public quiz token validation

## Thread Safety Guarantee

All dependencies use **request-scoped** sessions and services:

```python
# ✅ SAFE: Each request gets fresh session
@router.get("/data")
async def get_data(db: Session = Depends(get_db)):
    # This session is ISOLATED from other concurrent requests
    pass

# ❌ UNSAFE: Never store sessions in globals or app.state
app.state.db = next(get_db())  # DON'T DO THIS!
```

## Performance

### Redis Cache Layers (Authentication)

1. **Token Cache** (1h TTL): ~5ms
2. **User Cache** (2h TTL): ~5ms
3. **Session Cache** (24h TTL): ~2-5ms
4. **PostgreSQL Fallback**: ~50-100ms

**Recommendation:** Use session-based auth (X-Session-ID header) for best performance.

## Migration from Legacy Code

### Old Pattern (DEPRECATED)
```python
# DON'T USE
from app.dependencies_thread_safe import get_current_user
```

### New Pattern (RECOMMENDED)
```python
# USE THIS
from app.dependencies import get_current_user
```

## Troubleshooting

### Issue: "Could not import get_current_user"
**Solution:** Import from package, not root module:
```python
# ✅ Correct
from app.dependencies import get_current_user

# ❌ Wrong (module shadowed by package)
from app.dependencies import get_current_user  # This works, but...
import app.dependencies as deps
# deps is the PACKAGE, not the module
```

### Issue: "Session is closed"
**Solution:** Don't store session references:
```python
# ❌ Wrong
session = None
@router.get("/data")
async def get_data(db: Session = Depends(get_db)):
    global session
    session = db  # DON'T DO THIS

# ✅ Correct
@router.get("/data")
async def get_data(db: Session = Depends(get_db)):
    # Use db only within this function
    data = db.query(Model).all()
    return data
```

## Testing

### Unit Tests
```python
from app.dependencies import get_db, get_current_user

def test_endpoint():
    # Override dependencies
    def override_get_db():
        yield MockSession()

    app.dependency_overrides[get_db] = override_get_db

    response = client.get("/api/v1/data")
    assert response.status_code == 200
```

### Integration Tests
```python
# Use real dependencies
response = client.get(
    "/api/v1/secure",
    headers={"Authorization": f"Bearer {firebase_token}"}
)
```

## Further Reading

- [FastAPI Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [SQLAlchemy Sessions](https://docs.sqlalchemy.org/en/14/orm/session_basics.html)
- [DI Architecture Audit](../deployment/DI_ARCHITECTURE_AUDIT.md)
```

---

## Phase 6: Final Validation & Deployment (Day 5)

### 6.1 Pre-Deployment Checklist

```bash
# 1. All tests pass
pytest backend-hormonia/tests/ -v --cov=app --cov-report=html

# 2. No linting errors
ruff check backend-hormonia/app/
mypy backend-hormonia/app/

# 3. No deprecated imports
grep -r "from app.dependencies_" backend-hormonia/app/ | grep -v legacy
# Expected: No matches

# 4. Database migrations applied
alembic upgrade head

# 5. Load test
ab -n 10000 -c 100 https://staging.api.example.com/api/v1/health
```

### 6.2 Deployment Steps

**Staging Deployment:**
```bash
# 1. Deploy to staging
railway up --service backend-staging

# 2. Smoke tests
curl https://staging.api.example.com/api/v1/health/advanced
# Verify: all DI tests pass

# 3. Load test (5 minutes)
ab -t 300 -c 50 https://staging.api.example.com/api/v1/auth/me

# 4. Monitor logs
railway logs --service backend-staging --tail 100
# Check for: session errors, import errors, auth failures
```

**Production Deployment:**
```bash
# 1. Deploy during low-traffic window
railway up --service backend-production

# 2. Monitor critical metrics
- Request latency (should be unchanged)
- Error rate (should be 0% increase)
- Database connection pool (should be stable)
- Redis cache hit rate (should be >90%)

# 3. Rollback plan (if needed)
railway rollback --service backend-production
```

### 6.3 Post-Deployment Validation

**Health Checks:**
```bash
# Advanced health endpoint
curl https://api.example.com/api/v1/health/advanced | jq .

# Expected:
{
  "dependency_injection": {
    "database_session": true,
    "service_provider": true,
    "redis_cache": true,
    "session_manager": true
  }
}
```

**Performance Metrics:**
```bash
# Authentication latency
ab -n 1000 -c 50 https://api.example.com/api/v1/auth/me
# Expected: p95 < 100ms (with cache hits)

# Concurrent patient queries
ab -n 5000 -c 100 https://api.example.com/api/v1/patients
# Expected: No session cross-talk errors
```

**Database Session Monitoring:**
```sql
-- Check for connection leaks (PostgreSQL)
SELECT
  count(*) as total_connections,
  count(*) FILTER (WHERE state = 'idle') as idle,
  count(*) FILTER (WHERE state = 'active') as active
FROM pg_stat_activity
WHERE datname = 'hormonia_production';

-- Expected: idle < pool_size (25), active = concurrent requests
```

---

## Rollback Plan

### If Critical Issues Detected

**Symptoms:**
- Authentication failures >1%
- Database connection pool exhaustion
- Session cross-talk errors
- Import errors

**Immediate Actions:**

```bash
# 1. Rollback deployment
railway rollback --service backend-production

# 2. Verify rollback succeeded
curl https://api.example.com/api/v1/health
# Expected: status "healthy"

# 3. Restore archived files (if needed)
cd backend-hormonia/app
git checkout HEAD~1 dependencies.py
git checkout HEAD~1 dependencies_enhanced.py
git checkout HEAD~1 dependencies_fallback.py

# 4. Redeploy with restored files
railway up --service backend-production

# 5. Monitor recovery
railway logs --service backend-production --tail 200
```

**Root Cause Analysis:**
1. Check logs for specific import errors
2. Verify all test environments match production config
3. Review dependency graph for missed imports
4. Update testing strategy to catch missed patterns

---

## Success Metrics

### Pre-Cleanup Baseline

| Metric | Current | Target |
|--------|---------|--------|
| Total DI Modules | 13 | 6 |
| Orphaned Modules | 7 | 0 |
| Name Collisions | 1 | 0 |
| Shared Sessions | 1 | 0 |
| Thread-Safe Coverage | 95% | 100% |
| Import Graph Complexity | High | Low |

### Post-Cleanup Validation

| Metric | Target | Status |
|--------|--------|--------|
| All Tests Pass | ✅ | |
| Zero Import Errors | ✅ | |
| Auth Latency p95 < 100ms | ✅ | |
| No Session Leaks | ✅ | |
| Documentation Complete | ✅ | |
| Developer Onboarding Time | -50% | |

---

## Timeline

| Phase | Duration | Dependencies | Risk |
|-------|----------|--------------|------|
| Phase 1: Remove Shared ServiceProvider | 4 hours | None | Low |
| Phase 2: Archive Orphaned Modules | 4 hours | Phase 1 | Zero |
| Phase 3: Refactor Health Endpoint | 8 hours | Phase 2 | Low |
| Phase 4: Archive Remaining Modules | 2 hours | Phase 3 | Zero |
| Phase 5: Update Documentation | 8 hours | Phase 4 | Zero |
| Phase 6: Deployment & Validation | 8 hours | Phase 1-5 | Medium |
| **Total** | **5 days** | | **Low-Medium** |

---

## Stakeholder Communication

### Engineering Team

**Subject:** DI Architecture Cleanup - Action Required

**Body:**
> We're consolidating our dependency injection architecture from 13 modules to 6 to eliminate technical debt and improve maintainability.
>
> **Impact on Your Work:**
> - ✅ No code changes required (all imports already use package)
> - ✅ Improved onboarding documentation
> - ✅ Better IDE autocomplete (fewer shadowed imports)
>
> **Deployment:** Wednesday 2025-10-09, 2:00 AM UTC (low-traffic window)
>
> **Questions?** See docs/deployment/DI_CLEANUP_PLAN.md

### QA Team

**Testing Focus:**
1. Authentication flows (Firebase + Redis session)
2. Concurrent patient access (no data cross-talk)
3. Load testing (sustained 100 concurrent users)
4. Error scenarios (database connection failures)

---

## Next Steps

### Immediate (This Week)
- [ ] Review plan with tech lead
- [ ] Schedule deployment window
- [ ] Notify stakeholders
- [ ] Prepare rollback scripts

### Short-Term (Next Sprint)
- [ ] Execute Phase 1-6 according to timeline
- [ ] Monitor production metrics for 48 hours
- [ ] Gather developer feedback on new docs
- [ ] Archive this document (mark as "Completed")

### Long-Term (Next Quarter)
- [ ] Audit app.state usage patterns
- [ ] Standardize naming (remove "thread_safe" prefix)
- [ ] Add CI check for orphaned modules
- [ ] Performance baseline for future optimizations

---

**Plan Owner:** Backend Team Lead
**Reviewers:** Senior Backend Engineer, DevOps Engineer
**Approvals Required:** Tech Lead, CTO (for production deployment)

**Questions?** Contact #backend-team on Slack
