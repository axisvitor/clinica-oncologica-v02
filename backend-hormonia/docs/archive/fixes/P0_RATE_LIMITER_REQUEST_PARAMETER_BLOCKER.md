# P0 CRITICAL: Rate Limiter Missing Request Parameter - Test Execution Blocker

**Status**: 🚨 BLOCKING - Tests Cannot Run
**Priority**: P0 - Critical Blocker
**Discovery Date**: 2025-11-15
**Impact**: Application won't start - conftest.py fails to import

## Executive Summary

**CRITICAL BLOCKER**: 29 rate-limited API endpoints are missing the required `request: Request` parameter. This causes the application to crash during startup, preventing any tests from running.

### Error Message
```
Exception: No "request" or "websocket" argument on function "<function search_patients at 0x7c5763441b20>"
```

## Root Cause

The `slowapi` rate limiter requires all decorated endpoints to have either a `request: Request` or `websocket: WebSocket` parameter in their function signature. 29 endpoints across the codebase are missing this parameter.

## Impact Assessment

### Severity: CRITICAL P0
- ✅ **Blocking**: Application cannot start
- ✅ **Blocking**: Tests cannot run (conftest.py import fails)
- ✅ **Blocking**: No development or deployment possible
- ⚠️ **Pre-existing**: This is NOT a P0 implementation issue - it's a pre-existing bug

### Affected Areas

1. **A/B Testing** (5 endpoints) - `app/api/v2/ab_testing.py`
2. **Admin** (1 endpoint) - `app/api/v2/admin.py`
3. **Flows** (16 endpoints) - `app/api/v2/flows.py`
4. **Patient Flow** (4 endpoints) - `app/api/v2/patients_flow.py`
5. **Patient CRUD** (2 endpoints) - `app/api/v2/patients_crud.py` ✅ FIXED
6. **Reports** (3 endpoints) - `app/api/v2/reports.py`

## Affected Endpoints (27 remaining to fix)

### A/B Testing (5 endpoints)
```python
# Line 410
@limiter.limit(RATE_LIMIT_READ)
async def list_experiments(
    # MISSING: request: Request,
    cursor: Optional[str] = Query(None),
    ...
)

# Line 506
@limiter.limit(RATE_LIMIT_READ)
async def get_experiment(
    # MISSING: request: Request,
    experiment_id: UUID,
    ...
)

# Line 985
@limiter.limit(RATE_LIMIT_ANALYSIS)
async def get_experiment_results(
    # MISSING: request: Request,
    experiment_id: UUID,
    ...
)

# Line 1246
@limiter.limit(RATE_LIMIT_WRITE)
async def delete_experiment(
    # MISSING: request: Request,
    experiment_id: UUID,
    ...
)

# Line 1325
@limiter.limit(RATE_LIMIT_READ)
async def get_dashboard(
    # MISSING: request: Request,
    db: Session = Depends(get_db),
    ...
)
```

### Admin (1 endpoint)
```python
# Line 133
@limiter.limit("60/minute")
async def get_system_stats(
    # MISSING: request: Request,
    db: Session = Depends(get_db),
    ...
)
```

### Flows (16 endpoints)
```python
# Lines: 396, 428, 465, 497, 534, 602, 714, 760, 788, 941, 1032, 1060, 1091, 1202, 1229, 1524
# All missing: request: Request as first parameter
```

### Patient Flow (4 endpoints)
```python
# Lines: 63, 122, 279, 346
# All missing: request: Request as first parameter
```

### Reports (3 endpoints)
```python
# Lines: 278, 394, 579
# All missing: request: Request as first parameter
```

## Fix Strategy

### Pattern to Apply
```python
# BEFORE (INCORRECT)
@limiter.limit("120/minute")
async def my_endpoint(
    db: Session = Depends(get_db),
    ...
):
    pass

# AFTER (CORRECT)
@limiter.limit("120/minute")
async def my_endpoint(
    request: Request,  # ← ADD THIS
    db: Session = Depends(get_db),
    ...
):
    pass
```

### Required Import
```python
from fastapi import Request
```

## Implementation Plan

### Phase 1: Automated Fix (Recommended)
1. Create script to automatically add `request: Request` parameter
2. Run script on all affected files
3. Verify imports are present
4. Run tests to validate fix

### Phase 2: Manual Fix (Alternative)
1. Fix each file individually:
   - `app/api/v2/ab_testing.py` (5 endpoints)
   - `app/api/v2/admin.py` (1 endpoint)
   - `app/api/v2/flows.py` (16 endpoints)
   - `app/api/v2/patients_flow.py` (4 endpoints)
   - `app/api/v2/reports.py` (3 endpoints)

## Validation Steps

1. **Import Check**: Application must start without errors
2. **Test Suite**: conftest.py must import successfully
3. **Rate Limiting**: Verify rate limiting still works
4. **Integration Tests**: Run full test suite

## Timeline

- **Discovery**: 2025-11-15 17:00 UTC
- **Triage**: 2025-11-15 17:15 UTC
- **Fix Required**: IMMEDIATE - Blocking all testing
- **Target Resolution**: Within 1 hour

## Files Fixed

- ✅ `app/api/v2/patients_crud.py` (2/2 endpoints fixed)
  - Line 258: `search_patients` ✅
  - Line 299: `get_patient` ✅

## Files Remaining (27 endpoints)

- ❌ `app/api/v2/ab_testing.py` (5 endpoints)
- ❌ `app/api/v2/admin.py` (1 endpoint)
- ❌ `app/api/v2/flows.py` (16 endpoints)
- ❌ `app/api/v2/patients_flow.py` (4 endpoints)
- ❌ `app/api/v2/reports.py` (3 endpoints)

## Related Issues

- Original discovery during test execution attempt
- Pre-existing bug (not related to P0 implementations)
- Affects backward compatibility testing

## References

- slowapi documentation: https://github.com/laurentS/slowapi
- FastAPI Request: https://fastapi.tiangolo.com/tutorial/first-steps/
- Rate Limiting Best Practices: https://fastapi.tiangolo.com/advanced/middleware/#advanced-middleware

## Next Steps

1. ✅ Document the issue (this file)
2. ⏳ Create automated fix script
3. ⏳ Apply fix to all 27 remaining endpoints
4. ⏳ Validate application starts
5. ⏳ Run full test suite
6. ⏳ Update test execution report

---

**Note**: This is a PRE-EXISTING BUG, not a regression from P0 implementations. It must be fixed before any testing can proceed.
