# CORS Documentation

**Hormonia Healthcare Platform**
**Last Updated**: October 6, 2025

---

## Overview

This directory contains comprehensive CORS (Cross-Origin Resource Sharing) documentation for the Hormonia Healthcare Platform. The documentation covers security audits, configuration guides, and testing procedures to ensure proper cross-origin communication between frontend and backend services.

---

## 📚 Documentation Index

### 1. [CORS Audit Report](./cors-audit-report.md)
**Purpose**: Security audit findings and risk assessment

**Contents**:
- Executive summary of CORS vulnerabilities
- Critical security findings (CVE analysis)
- Risk assessment before/after corrections
- Compliance considerations (HIPAA, LGPD)
- Verification results

**When to Read**:
- Before production deployment
- During security audits
- When reviewing compliance requirements
- After CORS-related incidents

**Key Findings**:
- ✅ PatternCORSMiddleware replaced with standard CORSMiddleware
- ✅ Expanded allowed origins (23 explicit origins)
- ✅ Added diagnostic health endpoints
- ✅ Risk level reduced from CRITICAL to LOW

---

### 2. [CORS Configuration Guide](./cors-configuration-guide.md)
**Purpose**: Step-by-step configuration instructions

**Contents**:
- Production setup (Railway environment)
- Development setup (local .env)
- Environment variables reference
- Middleware configuration details
- Security best practices

**When to Read**:
- Setting up new development environment
- Deploying to production
- Adding new frontend origins
- Troubleshooting CORS errors

**Quick Start**:
```env
# Production
ALLOWED_ORIGINS=["https://frontend.railway.app","https://api.railway.app"]

# Development
ALLOWED_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
```

---

### 3. [CORS Testing Guide](./cors-testing-guide.md)
**Purpose**: Comprehensive testing procedures

**Contents**:
- CORS smoke tests
- Manual testing with curl
- Browser-based testing
- Automated testing scripts
- WebSocket CORS testing
- CI/CD integration

**When to Read**:
- After configuration changes
- Before production deployment
- During troubleshooting
- Setting up automated testing

**Quick Test**:
```bash
# Test CORS preflight
curl -X OPTIONS \
  -H "Origin: https://frontend.railway.app" \
  https://backend.railway.app/api/v1/auth/me -v
```

---

## 🚀 Quick Start

### For Developers

1. **Setup Development Environment**:
   ```bash
   # Add to backend-hormonia/.env
   ALLOWED_ORIGINS=[
     "http://localhost:5173",
     "http://127.0.0.1:5173"
   ]
   ```

2. **Start Services**:
   ```bash
   # Backend
   cd backend-hormonia
   uvicorn app.main:app --reload

   # Frontend
   cd frontend-hormonia
   npm run dev
   ```

3. **Test CORS**:
   ```bash
   # Run quick test
   ./scripts/quick-cors-check.sh http://localhost:8000 http://localhost:5173
   ```

### For DevOps

1. **Configure Production**:
   ```bash
   # Railway Dashboard → Backend → Variables
   ALLOWED_ORIGINS=["https://frontend-production.railway.app","https://api-production.railway.app"]
   ```

2. **Deploy Backend**:
   ```bash
   git push origin main
   # Railway auto-deploys
   ```

3. **Verify CORS**:
   ```bash
   curl https://backend.railway.app/api/v1/health/detailed | jq '.cors'
   ```

### For QA

1. **Run Test Suite**:
   ```bash
   ./scripts/test-cors-comprehensive.sh
   ```

2. **Check Results**:
   - ✅ All tests pass: CORS configured correctly
   - ❌ Tests fail: Review [Testing Guide](./cors-testing-guide.md)

---

## 🔧 Common Issues

### Issue 1: CORS Blocked in Production

**Symptom**: Frontend shows CORS error
**Solution**: Check [Configuration Guide](./cors-configuration-guide.md#troubleshooting) → Issue 1

**Quick Fix**:
```bash
# Verify origin is in ALLOWED_ORIGINS
curl https://backend.railway.app/api/v1/health/detailed | jq '.cors.allowed_origins'
```

### Issue 2: CORS Works Locally, Fails in Production

**Symptom**: Local dev works, production fails
**Solution**: Check [Configuration Guide](./cors-configuration-guide.md#troubleshooting) → Issue 3

**Quick Fix**:
```env
# Ensure production uses HTTPS
ALLOWED_ORIGINS=["https://frontend.railway.app"]  # NOT http://
```

### Issue 3: WebSocket CORS Errors

**Symptom**: WebSocket connection fails with 502
**Solution**: Check [Testing Guide](./cors-testing-guide.md#websocket-cors-testing)

**Quick Fix**:
```bash
# Test WebSocket connection
wscat -c wss://backend.railway.app/ws/connect --origin https://frontend.railway.app
```

---

## 📊 CORS Status

### Current Configuration

| Environment | Status | Origins | Last Verified |
|-------------|--------|---------|---------------|
| **Production** | ✅ Working | 3 explicit origins | 2025-10-06 |
| **Development** | ✅ Working | 22 localhost origins | 2025-10-06 |
| **Staging** | ✅ Working | 2 Railway URLs | 2025-10-06 |

### Security Posture

| Category | Status | Details |
|----------|--------|---------|
| **CORS Implementation** | ✅ Secure | Standard CORSMiddleware |
| **Origin Whitelist** | ✅ Explicit | No wildcards in production |
| **Credentials Support** | ✅ Enabled | Proper authentication flow |
| **WebSocket CORS** | ✅ Working | Real-time features enabled |
| **HIPAA Compliance** | ✅ Compliant | No PHI exposure via CORS |

### Recent Changes

**October 6, 2025**:
- ✅ Replaced PatternCORSMiddleware with CORSMiddleware
- ✅ Expanded ALLOWED_ORIGINS to 23 origins
- ✅ Added `/api/v1/health/cors-test` endpoint
- ✅ Implemented comprehensive logging

---

## 🛠️ Maintenance

### Regular Tasks

**Weekly**:
- [ ] Monitor CORS error logs
- [ ] Review unauthorized origin attempts
- [ ] Check CORS endpoint health

**Monthly**:
- [ ] Run comprehensive test suite
- [ ] Review and update allowed origins
- [ ] Verify production CORS headers

**Quarterly**:
- [ ] Security audit (review [Audit Report](./cors-audit-report.md))
- [ ] Update documentation
- [ ] Review compliance requirements

### Monitoring Commands

```bash
# Check CORS configuration
curl https://backend.railway.app/api/v1/health/detailed | jq '.cors'

# Monitor CORS logs
railway logs --service backend-hormonia | grep "CORS"

# Run automated tests
./scripts/test-cors-comprehensive.sh
```

---

## 🔗 Related Documentation

### Internal Documentation
- [Security Audit Report](../backend-hormonia/docs/security-audit-report.md)
- [Railway Deployment Guide](../deployment/RAILWAY_DEPLOYMENT.md)
- [Environment Variables Guide](../deployment/ENVIRONMENT_VARIABLES.md)
- [API Documentation](../backend-hormonia/README.md)

### External Resources
- [MDN CORS Guide](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
- [FastAPI CORS Middleware](https://fastapi.tiangolo.com/tutorial/cors/)
- [OWASP CORS Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/CORS_Cheat_Sheet.html)

---

## 📝 Document History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 2.0 | 2025-10-06 | Complete CORS documentation suite created | Backend Team |
| 1.5 | 2025-10-06 | CORS fix implementation and testing | DevOps Team |
| 1.0 | 2025-10-05 | Initial CORS debugging report | Security Team |

---

## 📞 Support

### Getting Help

**CORS Configuration Issues**:
1. Check [Configuration Guide](./cors-configuration-guide.md)
2. Review [Troubleshooting Section](./cors-configuration-guide.md#troubleshooting)
3. Run diagnostic tests: `./scripts/quick-cors-check.sh`

**CORS Testing Issues**:
1. Check [Testing Guide](./cors-testing-guide.md)
2. Run comprehensive tests: `./scripts/test-cors-comprehensive.sh`
3. Review [Common Issues](./cors-testing-guide.md#common-issues-and-solutions)

**Security Concerns**:
1. Review [Audit Report](./cors-audit-report.md)
2. Check compliance section
3. Contact security team

### Contact Information

- **Backend Team**: backend-team@neoplasiaslitoral.com.br
- **DevOps Team**: devops-team@neoplasiaslitoral.com.br
- **Security Team**: security-team@neoplasiaslitoral.com.br

---

## 🎯 Next Steps

### For New Team Members
1. ✅ Read [Configuration Guide](./cors-configuration-guide.md)
2. ✅ Setup local development environment
3. ✅ Run CORS tests locally
4. ✅ Review [Audit Report](./cors-audit-report.md) for security context

### For Production Deployment
1. ✅ Review [Audit Report](./cors-audit-report.md) findings
2. ✅ Configure production origins in Railway
3. ✅ Run [comprehensive tests](./cors-testing-guide.md#automated-testing-scripts)
4. ✅ Monitor CORS logs post-deployment

### For Ongoing Maintenance
1. ✅ Schedule quarterly security audits
2. ✅ Monitor CORS error rates
3. ✅ Keep documentation updated
4. ✅ Review and remove deprecated origins

---

**Last Updated**: October 6, 2025
**Maintained By**: Backend Team
**Review Frequency**: Quarterly
**Next Review**: January 2026
