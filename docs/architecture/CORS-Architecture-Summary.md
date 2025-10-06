# CORS Architecture Summary

**Quick Reference Guide**
**Last Updated**: 2025-10-06

---

## Current Architecture

### Middleware Stack

```
Request Flow (Top to Bottom):
1. Monitoring Middleware
2. Query Performance Middleware
3. Request Logging (Debug only)
4. Security Middleware
5. Rate Limiting Middleware
6. Compression Middleware
7. CORSMiddleware ← Standard FastAPI/Starlette
8. Route Handler

Response Flow (Bottom to Top):
8. Route Handler
7. CORSMiddleware (adds CORS headers)
6. Compression Middleware
5. Rate Limiting Middleware
4. Security Middleware
3. Request Logging
2. Query Performance Middleware
1. Monitoring Middleware
```

### Configuration

**File**: `backend-hormonia/app/core/middleware_setup.py`

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,  # Explicit list, NO wildcards
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[...],  # Explicit headers
    expose_headers=[...],
    max_age=86400  # 24-hour preflight cache
)
```

**Environment**: `backend-hormonia/.env`

```env
ALLOWED_ORIGINS=[
  "http://localhost:3000",
  "http://localhost:5173",
  "http://127.0.0.1:3000",
  "https://frontend-production-18bb.up.railway.app",
  "https://interface-quiz-production.up.railway.app"
]
```

---

## Key Decisions

| Decision | Rationale | Status |
|----------|-----------|--------|
| Use standard `CORSMiddleware` | Proven reliability, community support | ✅ Implemented |
| Explicit origins only (no wildcards) | Security: prevent unauthorized access | ✅ Implemented |
| 24-hour preflight cache | Performance: reduce OPTIONS requests | ✅ Implemented |
| HTTPS-only in production | Encryption in transit (compliance) | ✅ Implemented |

---

## Security Principles

1. **No Wildcards in Production**: `allow_origins=["*"]` is forbidden
2. **Explicit Methods**: Only allow methods actually used by app
3. **Explicit Headers**: Minimal `allow_headers` and `expose_headers`
4. **HTTPS Only**: All production origins must use `https://`
5. **Audit Logging**: All CORS blocks logged for security review

---

## Performance Optimizations

1. **Preflight Cache**: `max_age=86400` (24 hours)
   - **Impact**: ~50% reduction in OPTIONS requests
2. **Vary Header**: `Vary: Origin` for CDN compatibility
3. **Minimal Processing**: Standard middleware has low overhead (~5ms)

---

## Monitoring

### Key Metrics

- **CORS Block Rate**: Target < 0.1%
- **Preflight Cache Hit Rate**: Target > 50%
- **CORS Processing Time**: Target < 5ms

### Alerts

- **Critical**: CORS block spike (> 100 in 5 min)
- **Warning**: New blocked origin detected
- **Info**: CORS configuration changed

---

## Common Operations

### Add New Origin (Manual)

1. Update `.env`:
   ```env
   ALLOWED_ORIGINS=[..., "https://new-app.railway.app"]
   ```
2. Commit and push:
   ```bash
   git commit -m "Add new CORS origin"
   git push
   ```
3. Railway auto-deploys (~3 min)

### Test CORS Configuration

```bash
# Test preflight
curl -X OPTIONS \
  -H "Origin: https://frontend.railway.app" \
  -H "Access-Control-Request-Method: GET" \
  https://backend.railway.app/api/v1/auth/me \
  -v

# Test actual request
curl -X GET \
  -H "Origin: https://frontend.railway.app" \
  https://backend.railway.app/api/v1/health/cors-test
```

### Debug CORS Errors

1. Check backend logs: `railway logs | grep "CORS"`
2. Verify origin in `ALLOWED_ORIGINS`: `GET /api/v1/health/detailed`
3. Test with health endpoint: `GET /api/v1/health/cors-test`
4. Check browser DevTools → Network → Response Headers

---

## Migration History

| Date | Change | Reason |
|------|--------|--------|
| 2025-10-06 | Replaced `PatternCORSMiddleware` with `CORSMiddleware` | Production CORS failure |
| 2025-10-06 | Removed wildcard patterns | Security hardening |
| 2025-10-06 | Added explicit Railway production URLs | Production deployment support |

---

## Future Roadmap

### Phase 1: Automation (Q2 2025)
- Dynamic origin management API
- CORS metrics dashboard
- CI/CD integration for origin detection

### Phase 2: Performance (Q3 2025)
- Edge CORS handling (CloudFlare Workers)
- Smart preflight caching

### Phase 3: Zero-Trust (Q4 2025)
- Token-based origin validation
- AI anomaly detection

---

## Documentation Index

| Document | Purpose |
|----------|---------|
| `ADR-001-CORS-Architecture.md` | Architecture Decision Record |
| `CORS-Request-Flow-Diagram.md` | Visual diagrams and flows |
| `CORS-Migration-Guide.md` | Step-by-step migration instructions |
| `CORS-Production-Hardening.md` | Security best practices |
| `CORS-Future-Improvements.md` | Innovation roadmap |
| `CORS-Architecture-Summary.md` | This quick reference |

---

## Support

- **Team**: Backend Engineering
- **Escalation**: System Architect
- **Slack**: `#backend-infrastructure`
- **Docs**: `docs/architecture/`

---

## Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| CORS error in production | Add origin to `ALLOWED_ORIGINS` in `.env` |
| CORS error in development | Verify localhost/127.0.0.1 ports in allowed list |
| Preflight takes too long | Check `max_age=86400` is set |
| WebSocket 502 error | Verify Railway WebSocket support enabled |
| New Railway deployment blocked | Add explicit URL to `ALLOWED_ORIGINS` |

---

**Last Review**: 2025-10-06
**Next Review**: 2025-11-06 (30 days)
