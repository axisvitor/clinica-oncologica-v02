---
title: "Migrate Auth Endpoints to /api/v2/session"
labels: ["enhancement", "api-v2", "auth", "p2-medium", "backend", "frontend"]
assignees: []
milestone: "API v2 Consolidation"
---

## 🎯 Objective

Create `/api/v2/session` endpoints to consolidate all API traffic under v2 namespace while maintaining backward compatibility.

## 📋 Context

Currently, session endpoints live at root level:
- POST `/session` - Session creation
- GET `/session/validate` - Session validation
- DELETE `/session/logout` - Logout

These should be available under `/api/v2/session` for consistency with other v2 endpoints (patients, quiz, analytics).

## ✅ Acceptance Criteria

### Backend
- [ ] Create `/api/v2/session` POST endpoint (session creation)
- [ ] Create `/api/v2/session/validate` GET endpoint
- [ ] Create `/api/v2/session/logout` DELETE endpoint
- [ ] Keep root `/session` endpoints for backward compatibility (6 months)
- [ ] Add deprecation warning headers to root endpoints
- [ ] Maintain identical functionality between v2 and root
- [ ] Add OpenAPI docs for v2 session endpoints

### Frontend
- [ ] Update `createSession` to use `/api/v2/session`
- [ ] Update session validation calls
- [ ] Update logout calls
- [ ] Maintain fallback to root endpoints (graceful degradation)
- [ ] Update API client documentation

### Testing
- [ ] Add tests for all v2 session endpoints
- [ ] Test backward compatibility
- [ ] Test deprecation warnings
- [ ] Integration tests with frontend

## 📁 Files to Create/Modify

### Backend
```
backend-hormonia/app/api/v2/session.py (NEW)
backend-hormonia/app/api/v2/router.py (MODIFY - include session router)
backend-hormonia/app/routers/auth_session.py (MODIFY - add deprecation)
backend-hormonia/tests/api/v2/test_session.py (NEW)
```

### Frontend
```
frontend-hormonia/src/lib/api-client/auth.ts (MODIFY - update URLs)
frontend-hormonia/src/config/api.ts (ADD - v2 feature flag)
```

## 🔧 Implementation Plan

### Phase 1: Backend v2 Endpoints (4 hours)
1. Copy `app/routers/auth_session.py` logic to `app/api/v2/session.py`
2. Include in v2 router: `api_v2_router.include_router(session_router)`
3. Ensure identical behavior to root endpoints
4. Add comprehensive tests

### Phase 2: Deprecation Warnings (1 hour)
1. Add response header to root endpoints:
   ```python
   response.headers["Deprecated"] = "true"
   response.headers["Sunset"] = "2025-04-18"  # 6 months
   response.headers["Link"] = '</api/v2/session>; rel="alternate"'
   ```
2. Log deprecation warnings
3. Update documentation

### Phase 3: Frontend Migration (2 hours)
1. Add feature flag `USE_V2_SESSION_ENDPOINTS`
2. Update API client to use v2 when flag enabled
3. Test with feature flag on/off
4. Enable flag in production after validation

### Phase 4: Monitoring & Validation (1 hour)
1. Monitor v2 endpoint usage
2. Monitor root endpoint usage (should decrease)
3. Track deprecation warnings
4. Plan removal after 6 months

## 📊 Success Metrics

- v2 session endpoints have same functionality as root
- Zero breaking changes for existing clients
- Frontend successfully uses v2 endpoints
- Deprecation warnings visible in logs/headers
- 100% test coverage on v2 endpoints

## 🔗 API Endpoint Mapping

| Root Endpoint | v2 Endpoint | Method | Description |
|---------------|-------------|--------|-------------|
| POST `/session` | POST `/api/v2/session` | POST | Create session |
| GET `/session/validate` | GET `/api/v2/session/validate` | GET | Validate session |
| DELETE `/session/logout` | DELETE `/api/v2/session/logout` | DELETE | Single logout |
| DELETE `/session/logout-all` | DELETE `/api/v2/session/logout-all` | DELETE | Global logout |
| GET `/session/active` | GET `/api/v2/session/active` | GET | List sessions |
| GET `/session/stats` | GET `/api/v2/session/stats` | GET | Cache stats |

## 🚨 Breaking Change Prevention

**Backward Compatibility Strategy:**
1. Keep root endpoints active (6 months minimum)
2. Frontend uses feature flag for gradual rollout
3. Monitor API usage before deprecation
4. Communicate timeline to API consumers
5. Provide migration guide

## 🔗 Related Issues

- Related: #001, #002, #003 (Test tickets)
- Blocks: #009 (v1 Deprecation)
- Depends on: Session validation working correctly

## ⏱️ Estimated Effort

**8 hours**
- Backend v2 endpoints: 4 hours
- Deprecation setup: 1 hour
- Frontend migration: 2 hours
- Testing & validation: 1 hour

## 📝 Notes

### Migration Timeline
- **Week 1:** Deploy v2 endpoints (root still active)
- **Week 2:** Enable feature flag for internal testing
- **Week 3:** Enable for 10% of users
- **Week 4:** Enable for 50% of users
- **Week 5:** Enable for 100% of users
- **Month 6:** Remove root endpoints (with notice)

### Deprecation Response Headers
```http
HTTP/1.1 200 OK
Deprecated: true
Sunset: Wed, 18 Apr 2025 00:00:00 GMT
Link: </api/v2/session>; rel="alternate"
Warning: 299 - "This endpoint is deprecated. Use /api/v2/session"
```

### Feature Flag Implementation
```typescript
// config/api.ts
export const USE_V2_SESSION_ENDPOINTS = 
  import.meta.env.VITE_USE_V2_SESSION === 'true'

// api-client/auth.ts
const sessionUrl = USE_V2_SESSION_ENDPOINTS 
  ? '/api/v2/session' 
  : '/session'
```

## 📚 Documentation Updates

- [ ] Update API documentation (OpenAPI/Swagger)
- [ ] Update frontend API client docs
- [ ] Create migration guide for API consumers
- [ ] Update deployment documentation
- [ ] Announce deprecation in changelog
