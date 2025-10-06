# ADR-001: CORS Architecture and Implementation Strategy

**Status**: Accepted
**Date**: 2025-10-06
**Decision Makers**: System Architecture Team
**Stakeholders**: Backend Engineers, DevOps, Security Team

---

## Context and Problem Statement

The application experienced critical CORS (Cross-Origin Resource Sharing) failures in production, blocking all API requests from the frontend. The root cause was traced to a custom `PatternCORSMiddleware` that failed to properly set CORS headers on preflight OPTIONS requests, despite having correct origin configurations.

### Key Issues Identified

1. **Custom Middleware Failure**: `PatternCORSMiddleware` did not return proper `Access-Control-Allow-Origin` headers
2. **Production Blocking**: All API endpoints returned `ERR_FAILED` with CORS errors
3. **WebSocket Failures**: WebSocket connections received 502 errors due to CORS + connection issues
4. **Dashboard Inaccessibility**: System was 100% inaccessible to end users

### Environment Context

- **Platform**: FastAPI/Starlette (Python 3.11+)
- **Deployment**: Railway (production), localhost (development)
- **Clients**: React SPA, Quiz Interface, Mobile Apps
- **Architecture**: Microservices with cross-origin communication

---

## Decision Drivers

1. **Reliability**: CORS must work 100% of the time in production
2. **Security**: No wildcards in production; explicit origin allowlisting
3. **Maintainability**: Use battle-tested libraries over custom implementations
4. **Developer Experience**: Support multiple development ports and environments
5. **Performance**: Minimal overhead on request processing
6. **Compliance**: Adhere to CORS specification (RFC 6454)

---

## Considered Options

### Option 1: Custom PatternCORSMiddleware (Original Implementation)

**Description**: Custom middleware extending Starlette's `CORSMiddleware` with regex pattern matching for Railway dynamic subdomains.

**Pros**:
- Supports wildcard patterns (`https://*.railway.app`)
- Single configuration for multiple dynamic origins
- Theoretically elegant for cloud deployments

**Cons**:
- ❌ **Failed in production** - did not return CORS headers on OPTIONS requests
- ❌ Custom code has bugs and edge cases
- ❌ Requires maintenance and testing
- ❌ Security risk: wildcards can match unintended origins
- ❌ Not battle-tested by community

**Verdict**: ❌ **Rejected** - Production failure demonstrates unreliability

---

### Option 2: Standard CORSMiddleware with Explicit Origins (Selected)

**Description**: Use FastAPI/Starlette's built-in `CORSMiddleware` with explicit origin enumeration.

**Pros**:
- ✅ **Proven reliability** - used by thousands of production apps
- ✅ **Guaranteed CORS headers** on all OPTIONS requests
- ✅ **Zero custom code** - reduces maintenance burden
- ✅ **Explicit security** - no wildcards in production
- ✅ **Community support** - well-documented and tested
- ✅ **Simple debugging** - logs and behavior are predictable

**Cons**:
- Requires updating allowed origins when adding new Railway deployments
- More verbose configuration (explicit URLs)

**Verdict**: ✅ **ACCEPTED** - Reliability and security outweigh convenience

---

### Option 3: Dual Middleware Approach (Development + Production)

**Description**: Use `PatternCORSMiddleware` in development, `CORSMiddleware` in production.

**Pros**:
- Flexibility for dynamic development origins
- Production reliability with standard middleware

**Cons**:
- ❌ Complexity: different behavior in dev vs prod
- ❌ Higher risk of environment-specific bugs
- ❌ Not DRY (Don't Repeat Yourself)

**Verdict**: ❌ **Rejected** - Unnecessary complexity

---

### Option 4: API Gateway/Proxy with CORS Handling

**Description**: Offload CORS to a reverse proxy (Nginx, CloudFlare, Railway proxy).

**Pros**:
- Centralized CORS handling
- Backend doesn't need CORS middleware

**Cons**:
- ❌ Railway doesn't support custom proxy configuration
- ❌ Adds architectural complexity
- ❌ Harder to debug (CORS logic outside application)
- ❌ Not portable across cloud providers

**Verdict**: ❌ **Rejected** - Not feasible with current infrastructure

---

## Decision Outcome

### **Chosen Option: Standard CORSMiddleware with Explicit Origins (Option 2)**

We replace `PatternCORSMiddleware` with FastAPI's standard `CORSMiddleware`, using explicit origin enumeration for both development and production environments.

### Implementation Details

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,  # Explicit list, no wildcards
    allow_credentials=True,
    allow_methods=["*"],  # All HTTP methods (GET, POST, PUT, DELETE, OPTIONS)
    allow_headers=["*"],  # All headers for compatibility
    expose_headers=[
        "X-Request-ID", "X-Correlation-ID", "X-Process-Time",
        "X-Quiz-Session-ID", "X-RateLimit-Limit",
        "X-RateLimit-Remaining", "X-RateLimit-Reset"
    ],
    max_age=86400  # Preflight cache: 24 hours
)
```

### ALLOWED_ORIGINS Configuration

**Development**:
```python
# Localhost (Vite auto-assigns random ports)
"http://localhost:3000", "http://localhost:5173", "http://localhost:5174",
"http://localhost:5175", "http://localhost:5176", "http://localhost:5177",
"http://localhost:5178", "http://localhost:5179",

# 127.0.0.1 (Windows compatibility)
"http://127.0.0.1:3000", "http://127.0.0.1:5173", "http://127.0.0.1:5174",
"http://127.0.0.1:5175", "http://127.0.0.1:5176", "http://127.0.0.1:5177",
"http://127.0.0.1:5178", "http://127.0.0.1:5179",
```

**Production** (Railway - Explicit URLs Only):
```python
"https://clinica-oncologica-v02-production.up.railway.app",
"https://frontend-production-18bb.up.railway.app",
"https://interface-quiz-production.up.railway.app",
"https://quiz-mensal-interface.railway.app",
"https://hormonia-frontend.railway.app",
```

**Security Principle**: **NO WILDCARDS IN PRODUCTION**

---

## Consequences

### Positive

1. ✅ **Immediate Production Fix**: CORS errors resolved within one deployment
2. ✅ **Zero Downtime Risk**: Standard middleware has no known bugs
3. ✅ **Security Hardening**: Explicit origin allowlist prevents unauthorized access
4. ✅ **Reduced Technical Debt**: No custom middleware to maintain
5. ✅ **Compliance**: Full adherence to CORS RFC 6454 specification
6. ✅ **Developer Confidence**: Predictable behavior across environments

### Negative

1. ⚠️ **Manual Origin Updates**: Must add new Railway URLs manually to `.env`
2. ⚠️ **Verbose Configuration**: Longer `ALLOWED_ORIGINS` list

### Mitigation Strategies

**For Manual Updates**:
- **Automation**: CI/CD pipeline checks for new deployments and prompts for origin updates
- **Documentation**: Railway deployment guide includes CORS update checklist
- **Monitoring**: Alert if frontend origin is not in allowed list (from logs)

**For Verbosity**:
- **Environment Variables**: Use JSON arrays in `.env` for cleaner management
- **Validation**: Config validation ensures no duplicate or invalid origins

---

## Validation and Testing

### Acceptance Criteria

- [x] All preflight OPTIONS requests return proper CORS headers
- [x] Frontend can successfully call backend APIs
- [x] WebSocket connections establish without CORS errors
- [x] No `ERR_FAILED` or CORS blocking in browser console
- [x] Production deployment verified on Railway

### Test Cases

1. **Preflight OPTIONS Test**
   ```bash
   curl -X OPTIONS \
     -H "Origin: https://frontend-production-18bb.up.railway.app" \
     -H "Access-Control-Request-Method: GET" \
     https://clinica-oncologica-v02-production.up.railway.app/api/v1/auth/me \
     -v
   ```
   **Expected**: Headers `Access-Control-Allow-Origin`, `Access-Control-Allow-Methods`, `Access-Control-Allow-Headers`

2. **GET Request with CORS**
   ```bash
   curl -X GET \
     -H "Origin: https://frontend-production-18bb.up.railway.app" \
     https://clinica-oncologica-v02-production.up.railway.app/api/v1/health/cors-test
   ```
   **Expected**: `200 OK` with CORS headers

3. **Unauthorized Origin Rejection**
   ```bash
   curl -X OPTIONS \
     -H "Origin: https://evil.com" \
     https://clinica-oncologica-v02-production.up.railway.app/api/v1/auth/me \
     -v
   ```
   **Expected**: No `Access-Control-Allow-Origin` header (browser blocks request)

---

## Migration Path

### Phase 1: Immediate Fix (Completed)
1. ✅ Replace `PatternCORSMiddleware` with `CORSMiddleware` in `middleware_setup.py`
2. ✅ Update `ALLOWED_ORIGINS` with all explicit production URLs
3. ✅ Add health endpoints for CORS testing (`/api/v1/health/cors-test`)
4. ✅ Deploy to Railway and verify

### Phase 2: Monitoring (In Progress)
1. Add CORS logging middleware to track blocked origins
2. Set up alerts for CORS errors in production
3. Dashboard widget for CORS metrics (blocked vs allowed requests)

### Phase 3: Automation (Future)
1. CI/CD integration to detect new Railway deployments
2. Automated origin validation in deployment pipeline
3. Dynamic origin management API (admin-only, with audit logging)

---

## Rollback Plan

If production issues occur after deployment:

### Immediate Rollback (Railway Dashboard)
1. Go to Railway → Deployments → Find previous working deployment
2. Click "Redeploy" (instant rollback)

### Git Rollback
```bash
git revert HEAD
git push origin docs-refactor-py313
# Railway auto-redeploys previous version
```

### Emergency Bypass (Temporary)
```python
# In middleware_setup.py - ONLY FOR EMERGENCY
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # WARNING: Allows ALL origins
    allow_credentials=False  # Must disable credentials with wildcard
)
```
**⚠️ WARNING**: This is a security risk. Use only for minutes to restore service, then fix properly.

---

## Related Decisions

- **ADR-002**: Production Deployment Strategy (Railway-specific configurations)
- **ADR-003**: WebSocket Connection Handling (separate from CORS but related)
- **ADR-004**: Security Headers and Middleware Order

---

## References

- [CORS RFC 6454](https://www.rfc-editor.org/rfc/rfc6454)
- [FastAPI CORS Middleware Docs](https://fastapi.tiangolo.com/tutorial/cors/)
- [Starlette CORS Middleware Source](https://github.com/encode/starlette/blob/master/starlette/middleware/cors.py)
- [OWASP CORS Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Origin_Resource_Sharing_Cheat_Sheet.html)
- Railway CORS Debugging Report: `docs/CORS_DEBUGGING_REPORT.md`
- Railway CORS Fix Implementation: `docs/CORS_FIX_IMPLEMENTATION.md`

---

## Approval

**Approved by**: System Architect
**Date**: 2025-10-06
**Review Date**: 2025-11-06 (30-day review)
