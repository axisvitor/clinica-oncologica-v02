# CORS Production Hardening Guide

**Audience**: Security Engineers, DevOps, Backend Developers
**Classification**: Security Best Practices
**Last Updated**: 2025-10-06

---

## Overview

This document outlines **production hardening strategies** for CORS (Cross-Origin Resource Sharing) to ensure security, reliability, and compliance with web security standards.

---

## 1. Security Hardening

### 1.1 Explicit Origin Allowlisting

**Principle**: **NEVER use wildcards in production ALLOWED_ORIGINS**

#### ❌ INSECURE: Wildcard Patterns

```python
# NEVER DO THIS IN PRODUCTION
ALLOWED_ORIGINS = [
    "https://*.railway.app",  # ❌ Matches ANY Railway subdomain
    "https://*",               # ❌ Matches ANY HTTPS site
    "*"                        # ❌ Allows ALL origins (critical vulnerability)
]
```

**Vulnerability**: Attacker can create `https://evil.railway.app` and access your API

#### ✅ SECURE: Explicit Enumeration

```python
# PRODUCTION BEST PRACTICE
ALLOWED_ORIGINS = [
    "https://frontend-production-18bb.up.railway.app",
    "https://interface-quiz-production.up.railway.app",
    "https://clinica-oncologica-v02-production.up.railway.app"
]
```

**Security Benefit**: Only authorized, verified domains can access API

---

### 1.2 Environment-Specific Configuration

**Principle**: Different CORS policies for development vs production

```python
import os

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

if ENVIRONMENT == "production":
    ALLOWED_ORIGINS = [
        "https://frontend-production-18bb.up.railway.app",
        "https://interface-quiz-production.up.railway.app"
        # NO localhost, NO wildcards
    ]
    ALLOW_CREDENTIALS = True  # Secure cookies over HTTPS only

elif ENVIRONMENT == "development":
    ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
        # OK to include multiple dev ports
    ]
    ALLOW_CREDENTIALS = True  # Allow for local testing

else:
    # Staging/testing environment
    ALLOWED_ORIGINS = [
        "https://staging-frontend.railway.app"
    ]
    ALLOW_CREDENTIALS = True
```

**Security Benefit**: Prevents accidental exposure of dev/staging origins in production

---

### 1.3 Minimal Allow Methods and Headers

**Principle**: Only allow HTTP methods and headers that are actually used

#### ❌ INSECURE: Allow All

```python
app.add_middleware(
    CORSMiddleware,
    allow_methods=["*"],  # ❌ Includes TRACE, CONNECT, etc.
    allow_headers=["*"]   # ❌ Accepts ANY custom header
)
```

**Vulnerability**: Enables potentially dangerous methods and headers

#### ✅ SECURE: Explicit Whitelist

```python
app.add_middleware(
    CORSMiddleware,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS"  # Always include OPTIONS for preflight
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "X-Request-ID",
        "X-Correlation-ID",
        # Only headers your app actually uses
    ]
)
```

**Security Benefit**: Reduces attack surface by blocking unused methods/headers

---

### 1.4 Credentials Handling

**Principle**: Only enable `allow_credentials=True` when necessary

```python
# If using cookies or Authorization headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # MUST be explicit (no "*")
    allow_credentials=True
)

# If ONLY using public APIs (no auth)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # OK for truly public APIs
    allow_credentials=False  # MUST be False with wildcard
)
```

**CRITICAL**: `allow_credentials=True` with `allow_origins=["*"]` is **FORBIDDEN** by CORS spec and browsers will block it.

---

### 1.5 Origin Validation

**Principle**: Always log and monitor blocked origins

```python
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)

class CORSLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")

        if origin and origin not in settings.ALLOWED_ORIGINS:
            logger.warning(
                f"CORS: Blocked origin: {origin} | "
                f"Path: {request.url.path} | "
                f"Method: {request.method} | "
                f"User-Agent: {request.headers.get('user-agent', 'Unknown')}"
            )

        response = await call_next(request)
        return response

# Add BEFORE CORSMiddleware
app.add_middleware(CORSLoggingMiddleware)
```

**Security Benefit**: Detect unauthorized access attempts and potential new legitimate origins

---

## 2. Performance Hardening

### 2.1 Preflight Cache Optimization

**Principle**: Maximize `max_age` to reduce OPTIONS requests

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    max_age=86400  # 24 hours (maximum recommended)
)
```

**Performance Impact**:
- **Before**: Every request requires preflight OPTIONS (2 requests per API call)
- **After**: Preflight cached for 24 hours (~50% reduction in requests)

**Calculation**:
```
Dashboard with 10 API endpoints:
- Without cache: 10 endpoints × 2 requests = 20 requests per page load
- With 24h cache: 10 endpoints × 1 request = 10 requests per page load
- Savings: 50% fewer requests
```

---

### 2.2 Conditional CORS Middleware

**Principle**: Skip CORS processing for same-origin requests

```python
from starlette.middleware.base import BaseHTTPMiddleware

class ConditionalCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        host = request.headers.get("host")

        # Skip CORS if same-origin request
        if origin and origin.endswith(host):
            return await call_next(request)

        # Apply CORS middleware
        response = await call_next(request)

        if origin in settings.ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"

        return response
```

**Performance Benefit**: Reduces processing overhead for same-origin requests

---

### 2.3 CDN and Proxy Optimization

**Principle**: Leverage CDN for CORS header caching

#### CloudFlare Workers Example

```javascript
// CloudFlare Worker for CORS preflight caching
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  if (request.method === "OPTIONS") {
    // Serve preflight from edge cache
    return new Response(null, {
      headers: {
        "Access-Control-Allow-Origin": "https://frontend.railway.app",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
        "Access-Control-Max-Age": "86400",
        "Cache-Control": "public, max-age=86400"
      }
    })
  }

  // Forward actual requests to backend
  return fetch(request)
}
```

**Performance Benefit**: Preflight responses served from edge cache (< 50ms latency)

---

### 2.4 Vary Header Configuration

**Principle**: Always include `Vary: Origin` for proper caching

```python
from starlette.middleware.base import BaseHTTPMiddleware

class VaryHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Add Vary header for CORS responses
        if "Access-Control-Allow-Origin" in response.headers:
            existing_vary = response.headers.get("Vary", "")
            if "Origin" not in existing_vary:
                response.headers["Vary"] = f"{existing_vary}, Origin".strip(", ")

        return response
```

**Why `Vary: Origin`?**
- Ensures CDN/proxies cache responses separately per origin
- Prevents CORS header leakage between origins
- Required by HTTP caching spec (RFC 7234)

**Example**:
```
Origin: https://frontend.railway.app
Response: Access-Control-Allow-Origin: https://frontend.railway.app
Vary: Origin

Origin: https://quiz.railway.app
Response: Access-Control-Allow-Origin: https://quiz.railway.app
Vary: Origin
```

Without `Vary`, second request might get first origin's cached CORS headers (CORS error).

---

## 3. Monitoring and Alerting

### 3.1 CORS Metrics Collection

**Key Metrics to Track**:

| Metric | Description | Target |
|--------|-------------|--------|
| CORS Block Rate | Blocked origins / Total requests | < 0.1% |
| Preflight Cache Hit Rate | Cached OPTIONS / Total OPTIONS | > 50% |
| CORS Processing Time | Time in CORS middleware | < 5ms |
| Unauthorized Origin Attempts | Unique blocked origins | 0 per day |

**Implementation** (Prometheus metrics):

```python
from prometheus_client import Counter, Histogram

cors_blocks = Counter(
    'cors_blocked_origins_total',
    'Total number of blocked CORS requests',
    ['origin', 'path']
)

cors_processing_time = Histogram(
    'cors_processing_seconds',
    'Time spent processing CORS',
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1]
)

class CORSMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")

        start_time = time.time()
        response = await call_next(request)

        if origin and origin not in settings.ALLOWED_ORIGINS:
            cors_blocks.labels(origin=origin, path=request.url.path).inc()

        cors_processing_time.observe(time.time() - start_time)

        return response
```

---

### 3.2 Security Alerts

**Critical Alerts** (page on-call engineer):

```yaml
alerts:
  - name: CORS Block Spike
    severity: critical
    condition: cors_blocks > 100 in 5 minutes
    action: Page on-call + security team
    message: "Potential CORS attack or misconfigured frontend"

  - name: Wildcard CORS Detected
    severity: critical
    condition: allow_origins contains "*"
    action: Immediate alert + auto-rollback
    message: "WILDCARD CORS IN PRODUCTION - SECURITY RISK"
```

**Warning Alerts** (notify DevOps):

```yaml
alerts:
  - name: New Origin Detected
    severity: warning
    condition: new_blocked_origin
    action: Notify DevOps Slack channel
    message: "New origin blocked: {origin}. Verify if legitimate."

  - name: Preflight Cache Miss Rate High
    severity: warning
    condition: preflight_cache_hit_rate < 30% for 1 hour
    action: Notify backend team
    message: "Preflight cache inefficient. Check max_age configuration."
```

---

### 3.3 Audit Logging

**Log All CORS Configuration Changes**:

```python
import logging
from datetime import datetime

audit_logger = logging.getLogger("audit.cors")

def update_allowed_origins(new_origins: List[str], admin_user: str):
    old_origins = settings.ALLOWED_ORIGINS

    # Audit log
    audit_logger.info(
        f"CORS Configuration Changed | "
        f"User: {admin_user} | "
        f"Timestamp: {datetime.utcnow().isoformat()} | "
        f"Old Origins: {old_origins} | "
        f"New Origins: {new_origins} | "
        f"Added: {set(new_origins) - set(old_origins)} | "
        f"Removed: {set(old_origins) - set(new_origins)}"
    )

    # Apply change
    settings.ALLOWED_ORIGINS = new_origins
```

**Audit Log Retention**: 1 year minimum (compliance requirement)

---

## 4. Compliance and Regulatory Requirements

### 4.1 GDPR Compliance

**Principle**: CORS headers don't expose personal data

```python
# GDPR-compliant CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Only authorized EU/global frontends
    expose_headers=[
        "X-Request-ID",  # OK: Not PII
        "X-RateLimit-Remaining",  # OK: Not PII
        # ❌ NEVER expose: "X-User-Email", "X-User-ID"
    ]
)
```

**GDPR Article 32**: Technical measures for data security
- ✅ Explicit origin allowlisting = Access Control
- ✅ Audit logging = Security incident detection

---

### 4.2 HIPAA Compliance (Healthcare Data)

**Principle**: CORS must prevent unauthorized PHI access

```python
# HIPAA-compliant CORS configuration
if settings.ENVIRONMENT == "production":
    ALLOWED_ORIGINS = [
        "https://verified-frontend.hospital.com",
        # Must be HTTPS (encryption in transit)
        # Must be audited and approved domains
    ]

    # HIPAA requires audit trail
    audit_logger.info(
        f"CORS request from {origin} | "
        f"User: {request.state.user.email} | "
        f"PHI Access: {request.url.path}"
    )
```

**HIPAA Requirements**:
- ✅ Encryption in transit (HTTPS only in ALLOWED_ORIGINS)
- ✅ Access controls (explicit origin allowlisting)
- ✅ Audit logging (all CORS blocked attempts logged)

---

### 4.3 PCI-DSS Compliance (Payment Data)

**Principle**: CORS must protect cardholder data

```python
# PCI-DSS compliant CORS configuration
ALLOWED_ORIGINS = [
    "https://payment-frontend.pci-compliant-host.com"
    # Must be PCI-DSS Level 1 certified domain
]

# PCI-DSS Requirement 10.2: Audit all access to cardholder data
def cors_audit_log(request, origin, allowed):
    if "/api/v1/payment" in request.url.path:
        audit_logger.info(
            f"PCI Audit | CORS request | "
            f"Origin: {origin} | "
            f"Allowed: {allowed} | "
            f"IP: {request.client.host} | "
            f"Timestamp: {datetime.utcnow().isoformat()}"
        )
```

**PCI-DSS Requirements**:
- ✅ Secure transmission (HTTPS)
- ✅ Access control (ALLOWED_ORIGINS)
- ✅ Audit trail (logged for 1 year)

---

## 5. Incident Response

### 5.1 CORS Attack Detection

**Common CORS Attacks**:

1. **Origin Spoofing**:
   ```
   Attacker sends: Origin: https://frontend-production.railway.app
   But actual source: https://evil.com (spoofed in malicious browser extension)
   ```
   **Mitigation**: CORS is a browser security feature; server-side validation prevents this.

2. **Subdomain Takeover**:
   ```
   Attacker registers: old-abandoned.railway.app (previously in ALLOWED_ORIGINS)
   Uses to access API with legitimate origin
   ```
   **Mitigation**: Regularly audit ALLOWED_ORIGINS; remove unused domains.

3. **Wildcard Exploitation**:
   ```
   ALLOWED_ORIGINS = ["https://*.railway.app"]
   Attacker creates: https://evil-app.railway.app
   ```
   **Mitigation**: **NEVER use wildcards in production.**

---

### 5.2 Incident Response Playbook

**Scenario**: Unauthorized CORS access detected

**Response Steps**:

1. **Immediate (< 5 minutes)**:
   - Review blocked origin logs
   - Verify if origin is legitimate (new deployment?) or malicious
   - If malicious: No action needed (already blocked by CORS)
   - If legitimate: Emergency origin addition (see below)

2. **Emergency Origin Addition** (< 15 minutes):
   ```bash
   # Add to ALLOWED_ORIGINS in .env
   ALLOWED_ORIGINS=[..., "https://new-frontend.railway.app"]

   # Commit and deploy
   git add backend-hormonia/.env
   git commit -m "hotfix: Add emergency origin to ALLOWED_ORIGINS"
   git push origin main

   # Railway auto-deploys in ~3 minutes
   ```

3. **Post-Incident Review** (< 24 hours):
   - Document why origin was initially missing
   - Update deployment checklist
   - Improve automation (auto-detect new Railway deploys)

---

### 5.3 Rollback Procedures

**Scenario**: CORS change breaks production

**Rollback Steps**:

1. **Railway Dashboard Rollback** (fastest):
   - Railway → Deployments → Previous working deployment → Redeploy
   - Time: ~2 minutes

2. **Git Revert** (if Railway unavailable):
   ```bash
   git revert HEAD
   git push origin main
   # Railway auto-deploys reverted version
   ```
   - Time: ~5 minutes

3. **Emergency Wildcard** (last resort):
   ```python
   # TEMPORARY ONLY - REVERT ASAP
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["*"],
       allow_credentials=False
   )
   ```
   - Time: Immediate
   - **⚠️ CRITICAL**: Revert within 30 minutes; security risk

---

## 6. Future Hardening Roadmap

### Short-term (Next Sprint)

- [ ] **CORS Dashboard**: Real-time metrics and blocked origins
- [ ] **Automated Alerts**: Slack notifications for CORS blocks
- [ ] **Health Endpoint**: `/api/v1/health/cors` for diagnostics

### Medium-term (Next Quarter)

- [ ] **Dynamic Origin Management**: Admin API to add/remove origins
- [ ] **Preflight Edge Caching**: CloudFlare Workers for OPTIONS requests
- [ ] **CORS Testing Suite**: Automated tests for all scenarios

### Long-term (Next Year)

- [ ] **Zero-Trust CORS**: Replace origin-based with token-based validation
- [ ] **AI Anomaly Detection**: ML model to detect suspicious CORS patterns
- [ ] **Decentralized Allow List**: Blockchain-based origin registry (experimental)

---

## 7. Checklist: Production Deployment

Before deploying CORS changes to production:

- [ ] **No wildcards** in ALLOWED_ORIGINS
- [ ] **HTTPS only** for production origins
- [ ] **Explicit methods** in allow_methods (no "*")
- [ ] **Explicit headers** in allow_headers (no "*")
- [ ] **Vary: Origin** header configured
- [ ] **max_age** set to 86400 (24 hours)
- [ ] **Audit logging** enabled for CORS blocks
- [ ] **Monitoring alerts** configured
- [ ] **Rollback plan** documented and tested
- [ ] **Compliance requirements** met (GDPR, HIPAA, PCI-DSS)

---

## 8. References

- [RFC 6454 - CORS Specification](https://www.rfc-editor.org/rfc/rfc6454)
- [OWASP CORS Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Origin_Resource_Sharing_Cheat_Sheet.html)
- [FastAPI CORS Documentation](https://fastapi.tiangolo.com/tutorial/cors/)
- [MDN CORS Guide](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
- [GDPR Article 32 - Security of Processing](https://gdpr-info.eu/art-32-gdpr/)
- [HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/index.html)
- [PCI-DSS Requirement 10](https://www.pcisecuritystandards.org/document_library)

---

## Support

**Contact**: Security Team
**Escalation**: Chief Security Officer
**Slack**: `#security-alerts`
**Email**: security@example.com
