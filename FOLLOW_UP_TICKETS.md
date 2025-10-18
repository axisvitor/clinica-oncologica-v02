# Follow-Up Tickets - Post-Hotfix Work

## Priority 1: Critical Regression Tests

### Ticket #1: Implement RBAC Regression Tests
**Labels:** `testing`, `security`, `p0-critical`

**Description:**
Create comprehensive tests for RBAC patient scoping to prevent privacy regression.

**Acceptance Criteria:**
- [ ] `test_list_patients_rbac` - Verify doctors only see their own patients
- [ ] `test_list_patients_admin_sees_all` - Verify admins see all patients
- [ ] `test_get_patient_rbac` - Verify single patient access follows RBAC
- [ ] `test_create_patient_sets_doctor_id` - Verify doctor_id is set correctly
- [ ] All tests pass with 100% coverage

**Files:**
- `backend-hormonia/tests/api/v2/test_patients.py`

**Estimated Effort:** 4 hours

---

### Ticket #2: Implement Cursor Pagination Regression Tests
**Labels:** `testing`, `pagination`, `p1-high`

**Description:**
Create tests for cursor-based pagination to prevent SQL type errors and pagination bugs.

**Acceptance Criteria:**
- [ ] `test_quiz_pagination_with_cursor` - Test cursor with datetime comparison
- [ ] `test_quiz_pagination_empty_cursor` - Test first page (no cursor)
- [ ] `test_quiz_pagination_invalid_cursor` - Test malformed cursor handling
- [ ] `test_quiz_pagination_tie_breaking` - Test records with same created_at
- [ ] Test both quiz and patient pagination endpoints

**Files:**
- `backend-hormonia/tests/api/v2/test_quiz.py`
- `backend-hormonia/tests/api/v2/test_patients.py`

**Estimated Effort:** 6 hours

---

### Ticket #3: Implement Session Authentication Tests
**Labels:** `testing`, `auth`, `p1-high`

**Description:**
Create tests for session validation and error handling to prevent TypeError on invalid sessions.

**Acceptance Criteria:**
- [ ] `test_invalid_session_handling` - Test clean 401 on invalid session_id
- [ ] `test_missing_session_id` - Test behavior when session_id is None
- [ ] `test_session_creation` - Test POST /session flow
- [ ] `test_session_validation` - Test GET /session/validate
- [ ] `test_session_logout` - Test DELETE /session/logout

**Files:**
- `backend-hormonia/tests/auth/test_session.py`

**Estimated Effort:** 5 hours

---

### Ticket #4: Frontend Empty Response Tests
**Labels:** `testing`, `frontend`, `p1-high`

**Description:**
Create Vitest tests for empty response handling (204/205 status codes).

**Acceptance Criteria:**
- [ ] Test DELETE patient returns 204 without error
- [ ] Test 204 response doesn't call response.json()
- [ ] Test 205 response doesn't call response.json()
- [ ] Test Content-Length: 0 handling
- [ ] Mock fetch responses for all test cases

**Files:**
- `frontend-hormonia/tests/lib/api-client/core.test.ts`

**Estimated Effort:** 3 hours

---

## Priority 2: API v2 Migration

### Ticket #5: Migrate Auth Endpoints to /api/v2
**Labels:** `enhancement`, `api-v2`, `auth`, `p2-medium`

**Description:**
Create /api/v2/session endpoints to consolidate all API traffic under v2 namespace.

**Acceptance Criteria:**
- [ ] Create `/api/v2/session` (POST) - Session creation
- [ ] Create `/api/v2/session/validate` (GET) - Session validation  
- [ ] Create `/api/v2/session/logout` (DELETE) - Logout
- [ ] Keep root `/session` endpoints for backward compatibility
- [ ] Update frontend to use v2 endpoints
- [ ] Add deprecation warning to root endpoints
- [ ] Update API documentation

**Files:**
- `backend-hormonia/app/api/v2/router.py`
- `backend-hormonia/app/api/v2/session.py` (new)
- `frontend-hormonia/src/lib/api-client/auth.ts`

**Estimated Effort:** 8 hours

---

### Ticket #6: Migrate Remaining Analytics to v2
**Labels:** `enhancement`, `api-v2`, `analytics`, `p2-medium`

**Description:**
Migrate secondary analytics endpoints still on v1 to v2 API.

**Endpoints to Migrate:**
- `/api/v1/analytics/timeseries` → `/api/v2/analytics/timeseries`
- `/api/v1/analytics/reports` → `/api/v2/analytics/reports`
- `/api/v1/analytics/engagement` → `/api/v2/analytics/engagement`
- `/api/v1/analytics/outcomes` → `/api/v2/analytics/outcomes`
- `/api/v1/analytics/appointments` → `/api/v2/analytics/appointments`
- `/api/v1/analytics/messages` → `/api/v2/analytics/messages`
- `/api/v1/analytics/revenue` → `/api/v2/analytics/revenue`
- `/api/v1/analytics/system-usage` → `/api/v2/analytics/system-usage`

**Acceptance Criteria:**
- [ ] Implement v2 endpoints with same functionality
- [ ] Add cursor pagination where applicable
- [ ] Add field selection support
- [ ] Update frontend API client
- [ ] Add deprecation warnings to v1 endpoints
- [ ] Integration tests for all endpoints

**Estimated Effort:** 16 hours

---

### Ticket #7: Create Quiz v2 Endpoints (if not exist)
**Labels:** `enhancement`, `api-v2`, `quiz`, `p3-low`

**Description:**
Verify monthly quiz has v2 equivalent endpoints or create them.

**Investigation:**
- Check if `/api/v2/quiz` covers all monthly quiz functionality
- Identify gaps between v1 and v2 quiz APIs
- Plan migration strategy

**Estimated Effort:** 4 hours (investigation) + TBD (implementation)

---

## Priority 3: Code Quality

### Ticket #8: Fix TypeScript Lint Errors in core.ts
**Labels:** `code-quality`, `frontend`, `typescript`, `p3-low`

**Description:**
Clean up duplicate exports and type incompatibilities in API client core.

**Lint Errors to Fix:**
- Duplicate `ApiError` export declarations
- Duplicate `ApiResponse`, `PaginatedResponse`, `RequestOptions` exports
- `exactOptionalPropertyTypes` violations in request methods

**Acceptance Criteria:**
- [ ] Remove duplicate export declarations
- [ ] Fix RequestOptions type to allow undefined params
- [ ] All TypeScript files compile without errors
- [ ] No lint warnings in api-client directory

**Files:**
- `frontend-hormonia/src/lib/api-client/core.ts`
- `frontend-hormonia/src/lib/api-client/index.ts`

**Estimated Effort:** 2 hours

---

### Ticket #9: Archive or Remove v1 Endpoints
**Labels:** `cleanup`, `deprecation`, `p4-backlog`

**Description:**
After v2 migration is complete and tested in production, remove v1 endpoints.

**Acceptance Criteria:**
- [ ] Confirm all frontend uses v2 APIs
- [ ] Monitor production for v1 API usage (logs/metrics)
- [ ] Add 410 Gone responses to v1 endpoints
- [ ] Remove v1 router code after grace period
- [ ] Update all documentation

**Estimated Effort:** 8 hours (after 30-day grace period)

---

## Summary

**Total Estimated Effort:**
- **Priority 1 (Critical Tests):** 18 hours
- **Priority 2 (v2 Migration):** 28+ hours  
- **Priority 3 (Code Quality):** 10 hours
- **TOTAL:** ~56 hours (~7 days)

**Recommended Sprint Planning:**
1. **Sprint 1:** Complete all P1 tests (critical for deployment confidence)
2. **Sprint 2:** Auth v2 migration + Analytics v2 migration
3. **Sprint 3:** Quiz v2 investigation + TypeScript cleanup
4. **Future:** v1 deprecation after monitoring

**Immediate Action (Pre-Deployment):**
✅ Run smoke tests manually (no automation yet)
✅ Deploy with monitoring on RBAC, pagination, session handling
✅ Create P1 test tickets immediately
