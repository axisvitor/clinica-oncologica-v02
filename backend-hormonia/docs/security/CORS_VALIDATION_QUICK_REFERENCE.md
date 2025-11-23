# CORS Validation Quick Reference

**Quick access guide for CORS validation tools and commands**

---

## Quick Commands

### Local Development

```bash
# Validate CORS (Shell script - recommended for quick checks)
cd backend-hormonia
./scripts/validate-cors.sh

# Validate CORS (Node.js - recommended for detailed reports)
node scripts/validate-cors.js

# With custom URLs
./scripts/validate-cors.sh http://localhost:8000 http://localhost:5173
```

### CI/CD

```bash
# Trigger staging validation
gh workflow run cors-validation.yml -f environment=staging

# Trigger production validation (requires approval)
gh workflow run cors-validation.yml -f environment=production
```

### Manual Testing

```bash
# Test preflight request
curl -v -X OPTIONS http://localhost:8000/api/v2/patients \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: X-CSRF-Token"

# Test actual request
curl -v -X GET http://localhost:8000/api/v2/health \
  -H "Origin: http://localhost:5173"
```

---

## Expected Headers Cheat Sheet

### Preflight (OPTIONS) Response

```
✓ Access-Control-Allow-Origin: http://localhost:5173 (exact origin)
✓ Access-Control-Allow-Credentials: true
✓ Access-Control-Allow-Methods: GET, POST, PUT, DELETE, PATCH, OPTIONS
✓ Access-Control-Allow-Headers: Content-Type, X-CSRF-Token, ...
✓ Access-Control-Max-Age: 3600
✓ Vary: Origin
```

### Actual Request Response

```
✓ Access-Control-Allow-Origin: http://localhost:5173 (exact origin)
✓ Access-Control-Allow-Credentials: true
✓ Vary: Origin
```

---

## Common Issues - Quick Fixes

### Issue: "CORS header missing"

**Fix:**
```python
# app/middleware/cors.py
from app.middleware.cors import setup_cors
setup_cors(app)  # Ensure this is called in app/main.py
```

### Issue: "Credentials flag is false"

**Fix:**
```python
# app/middleware/cors.py
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,  # Must be True
    # ...
)
```

### Issue: "Origin not allowed"

**Fix:**
```python
# app/config/settings/security.py
CORS_ALLOWED_ORIGINS = [
    "https://app.example.com",  # Add your origin here
]
```

---

## File Locations

| Component | Location |
|-----------|----------|
| Shell validator | `backend-hormonia/scripts/validate-cors.sh` |
| Node.js validator | `backend-hormonia/scripts/validate-cors.js` |
| CORS middleware | `backend-hormonia/app/middleware/cors.py` |
| Security config | `backend-hormonia/app/config/settings/security.py` |
| CI/CD workflow | `.github/workflows/cors-validation.yml` |
| Full guide | `backend-hormonia/docs/operations/CORS_VALIDATION_GUIDE.md` |
| Monitoring | `backend-hormonia/monitoring/cors_checks.yaml` |

---

## Test Checklist

- [ ] Preflight OPTIONS request
- [ ] Simple GET request
- [ ] POST with credentials
- [ ] Custom headers (X-CSRF-Token)
- [ ] Blocked origin (security)
- [ ] All HTTP methods
- [ ] Credentials flag
- [ ] Vary header

---

## Emergency Rollback

If CORS validation fails in production:

1. Check current configuration:
```bash
curl -v -X OPTIONS https://api.example.com/api/v2/health \
  -H "Origin: https://app.example.com"
```

2. Review recent changes:
```bash
git log --oneline --since="24 hours ago" -- backend-hormonia/app/middleware/cors.py
```

3. Rollback if needed:
```bash
git revert <commit-hash>
```

---

## Support

- Full Guide: `docs/operations/CORS_VALIDATION_GUIDE.md`
- Implementation Summary: `docs/operations/P0_CORS_VALIDATION_IMPLEMENTATION_SUMMARY.md`
- GitHub Issues: Tag with `cors`, `security`, `P0`
