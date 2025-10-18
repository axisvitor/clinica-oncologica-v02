---
title: "Implement Session Authentication Validation Tests"
labels: ["testing", "auth", "p1-high", "backend"]
assignees: []
milestone: "Post-Hotfix Stabilization"
---

## 🎯 Objective

Create tests for session validation and error handling to prevent TypeError on invalid sessions and ensure clean 401 responses.

## 📋 Context

**Related PR:** Hotfix - Auth Dependency Logging Fix  
**Fixed in:** `backend-hormonia/app/dependencies/auth_dependencies.py:217,226`

The logging fix prevents `TypeError: 'NoneType' object is not subscriptable` when session_id is None. Without tests, refactoring could reintroduce 500 errors instead of clean 401s.

## ✅ Acceptance Criteria

### Session Validation Tests
- [ ] `test_invalid_session_handling` - Test clean 401 on invalid session (no TypeError)
- [ ] `test_missing_session_id_both_headers` - Test behavior when session_id is None
- [ ] `test_session_missing_firebase_uid` - Test corrupted session data handling
- [ ] `test_session_inactive_user` - Test 403 when user account is inactive
- [ ] `test_session_priority_cookie_over_header` - Test cookie takes precedence

### Session Endpoint Tests
- [ ] `test_session_creation_flow` - Test POST /session creates session correctly
- [ ] `test_session_validation_endpoint` - Test GET /session/validate returns user data
- [ ] `test_session_logout` - Test DELETE /session/logout invalidates session
- [ ] `test_session_logout_clears_cookie` - Verify httpOnly cookie is cleared

### Error Handling
- [ ] All invalid session scenarios return 401 (not 500)
- [ ] Error messages are clear and actionable
- [ ] No sensitive data leaked in error responses

## 📁 Files to Modify

**Test File:**
```
backend-hormonia/tests/auth/test_session_validation.py
```

**Fixtures Needed:**
- `redis_cache_mock` - Mock FirebaseRedisCache
- `firebase_token_mock` - Mock Firebase token verification
- `valid_session_id` - Returns test session ID
- `client` - FastAPI TestClient

## 🧪 Test Skeleton

Already created at `backend-hormonia/tests/auth/test_session_validation.py` with TODO markers.

## 🔧 Implementation Checklist

- [ ] Set up Redis mock (patch FirebaseRedisCache)
- [ ] Set up Firebase mock (patch _firebase_service)
- [ ] Remove `@pytest.mark.skip` from all 9 test methods
- [ ] Test cookie vs header priority
- [ ] Test session creation with httpOnly cookie
- [ ] Test session validation caching layers
- [ ] Test logout flow and cookie clearing
- [ ] Verify no TypeError in any scenario
- [ ] Add integration with authentication middleware
- [ ] Document session lifecycle

## 📊 Success Metrics

- 9/9 tests passing
- Zero 500 errors in any auth scenario
- All invalid sessions return 401 with clear messages
- Cookie security flags verified (httpOnly, secure, samesite)
- Test execution time < 8 seconds

## 🚨 Critical Bug to Prevent

**TypeError Scenario (Before Fix):**
```python
# session_id from header is None
session_id = request.headers.get("X-Session-ID")  # None

# Logging tries to slice None
logger.warning(f"Invalid session: {session_id[:8]}")  # TypeError!
# Returns 500 instead of 401
```

**Test Should Catch:**
```python
response = client.get(
    "/api/v2/patients",
    headers={"X-Session-ID": "invalid"}
)
assert response.status_code == 401  # NOT 500!
assert "Invalid or expired session" in response.json()["detail"]
```

## 🔗 Related Issues

- Depends on: Hotfix - Session Validation Fix
- Blocks: Production deployment
- Related: #001 (RBAC Tests), #002 (Pagination Tests)
- Related: #005 (Auth v2 Migration)

## ⏱️ Estimated Effort

**5 hours**
- Mock setup: 1.5 hours
- Session creation tests: 1 hour
- Validation tests: 1.5 hours
- Error handling tests: 1 hour

## 📝 Notes

### Session Flow
1. Frontend calls POST /session with Firebase token
2. Backend validates token, creates Redis session
3. Backend sets httpOnly cookie with session_id
4. Subsequent requests send cookie automatically
5. Backend validates session from cookie/header

### Security Considerations
- httpOnly prevents XSS attacks
- secure flag requires HTTPS
- samesite=strict prevents CSRF
- Session ID must be cryptographically random (32 bytes)

### Testing Strategy
- Mock Redis to simulate cache hits/misses
- Mock Firebase to control token validation
- Test both cookie and header authentication
- Verify cookie security flags
- Test session expiration scenarios

## 🔍 Debugging Tips

If tests fail:
1. Check Redis mock is properly patched
2. Verify session_id generation (32 bytes, URL-safe)
3. Check cookie attributes in test client
4. Verify error messages match exactly
5. Test with real Redis in integration tests
