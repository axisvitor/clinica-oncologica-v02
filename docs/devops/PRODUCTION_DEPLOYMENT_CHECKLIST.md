# Production Deployment Checklist
**Project:** Clínica Oncológica v02
**Platform:** Railway Cloud
**Last Updated:** October 9, 2025

## Pre-Deployment Phase

### 1. Environment Configuration ✅
- [ ] **Railway Project Setup**
  - [ ] Project created and linked to GitHub repository
  - [ ] Services configured (backend, frontend, database)
  - [ ] Custom domains configured (if applicable)
  - [ ] SSL certificates provisioned and validated

- [ ] **Environment Variables (Backend)**
  ```bash
  # Required Variables
  ENVIRONMENT=production
  DEBUG=false
  SECRET_KEY=<secure-generated-key>
  DATABASE_URL=<railway-postgres-url>
  REDIS_URL=<railway-redis-url>

  # Security
  SESSION_COOKIE_SECURE=true
  SECURE_SSL_REDIRECT=true
  CSRF_SECRET_KEY=<secure-csrf-key>

  # CORS Configuration
  ALLOWED_ORIGINS=["https://frontend.railway.app"]
  FRONTEND_URL=https://frontend.railway.app

  # Firebase (if used)
  FIREBASE_ADMIN_PROJECT_ID=<project-id>
  FIREBASE_ADMIN_PRIVATE_KEY=<private-key>
  FIREBASE_ADMIN_CLIENT_EMAIL=<service-email>

  # Optional Services
  GEMINI_API_KEY=<gemini-key>
  SENTRY_DSN=<sentry-dsn>
  ```

- [ ] **Environment Variables (Frontend)**
  ```bash
  NODE_ENV=production
  VITE_API_BASE_URL=https://backend.railway.app
  VITE_API_URL=https://backend.railway.app/api/v1
  VITE_WS_URL=wss://backend.railway.app/ws
  VITE_ENVIRONMENT=production
  VITE_DEBUG_MODE=false

  # Firebase Configuration
  VITE_FIREBASE_API_KEY=<api-key>
  VITE_FIREBASE_AUTH_DOMAIN=<auth-domain>
  VITE_FIREBASE_PROJECT_ID=<project-id>
  ```

### 2. Security Validation ✅
- [ ] **Secret Management**
  - [ ] No hardcoded secrets in codebase
  - [ ] All sensitive data in Railway environment variables
  - [ ] Secret rotation capability configured
  - [ ] `.env` files properly gitignored

- [ ] **Authentication Security**
  - [ ] JWT secret keys generated securely (minimum 256-bit)
  - [ ] CSRF protection enabled and configured
  - [ ] Session security settings enabled
  - [ ] Firebase security rules validated

- [ ] **Network Security**
  - [ ] HTTPS enforced on all endpoints
  - [ ] CORS configured for production domains only
  - [ ] Security headers implemented
  - [ ] SSL/TLS configuration validated

### 3. Database & Infrastructure ✅
- [ ] **Database Setup**
  - [ ] Railway PostgreSQL service provisioned
  - [ ] Database migrations applied and verified
  - [ ] Connection pooling configured
  - [ ] Backup strategy implemented
  - [ ] Database performance optimized

- [ ] **Redis Configuration**
  - [ ] Railway Redis service provisioned
  - [ ] SSL/TLS connection configured
  - [ ] Connection pool settings optimized
  - [ ] Cache strategy validated

- [ ] **Resource Allocation**
  - [ ] Backend service: 1GB RAM, 0.5 CPU (recommended)
  - [ ] Frontend service: 512MB RAM, 0.25 CPU (recommended)
  - [ ] Database: Appropriate plan selected
  - [ ] Auto-scaling rules configured

## Pre-Launch Testing

### 4. Health Check Validation ✅
- [ ] **Backend Health Endpoints**
  ```bash
  # Primary health check (Railway uses this)
  curl https://backend.railway.app/health
  # Expected: 200 OK with "healthy" status

  # Detailed health check
  curl https://backend.railway.app/api/v1/health
  # Expected: 200 OK with service details

  # Database connectivity
  curl https://backend.railway.app/api/v1/database/health
  # Expected: 200 OK with connection status

  # Redis connectivity
  curl https://backend.railway.app/api/v1/redis/health
  # Expected: 200 OK or warning (non-blocking)
  ```

- [ ] **Frontend Health Validation**
  ```bash
  # Frontend availability
  curl https://frontend.railway.app/
  # Expected: 200 OK with React app

  # Configuration endpoint
  curl https://frontend.railway.app/config
  # Expected: Environment configuration (no secrets)
  ```

### 5. Functional Testing ✅
- [ ] **Authentication Flow**
  ```bash
  # Test login endpoint
  curl -X POST https://backend.railway.app/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"password"}'
  # Expected: JWT token response or proper error
  ```

- [ ] **API Connectivity**
  ```bash
  # Test protected endpoint
  curl -H "Authorization: Bearer <token>" \
    https://backend.railway.app/api/v1/patients
  # Expected: Proper authentication response
  ```

- [ ] **WebSocket Connection**
  ```bash
  # Test WebSocket endpoint
  wscat -c wss://backend.railway.app/ws
  # Expected: Successful WebSocket connection
  ```

### 6. Performance Validation ✅
- [ ] **Response Time Testing**
  ```bash
  # Health endpoint performance
  time curl https://backend.railway.app/health
  # Target: < 100ms

  # API endpoint performance
  time curl https://backend.railway.app/api/v1/health
  # Target: < 500ms

  # Database query performance
  time curl https://backend.railway.app/api/v1/database/health
  # Target: < 1000ms
  ```

- [ ] **Load Testing (Optional)**
  ```bash
  # Basic load test
  ab -n 100 -c 10 https://backend.railway.app/health
  # Target: 95% requests < 1s
  ```

## Security Verification

### 7. Security Testing ✅
- [ ] **HTTPS Enforcement**
  ```bash
  # Test HTTP redirect
  curl -I http://backend.railway.app/health
  # Expected: 301/302 redirect to HTTPS
  ```

- [ ] **CORS Validation**
  ```bash
  # Test CORS headers
  curl -H "Origin: https://frontend.railway.app" \
       -H "Access-Control-Request-Method: GET" \
       -X OPTIONS https://backend.railway.app/api/v1/patients
  # Expected: Proper CORS headers
  ```

- [ ] **Security Headers**
  ```bash
  # Check security headers
  curl -I https://backend.railway.app/
  # Expected: X-Content-Type-Options, X-Frame-Options, etc.
  ```

- [ ] **Secret Exposure Check**
  ```bash
  # Verify no secrets in config endpoint
  curl https://backend.railway.app/config | grep -i "secret\|key\|password"
  # Expected: No sensitive data exposed
  ```

## Monitoring & Observability

### 8. Monitoring Setup ✅
- [ ] **Application Monitoring**
  - [ ] Sentry error tracking configured
  - [ ] Performance monitoring enabled
  - [ ] Custom metrics collection verified
  - [ ] Log aggregation configured

- [ ] **Infrastructure Monitoring**
  - [ ] Railway metrics dashboard configured
  - [ ] Resource usage alerts set up
  - [ ] Database performance monitoring enabled
  - [ ] Redis performance monitoring enabled

- [ ] **Alerting Configuration**
  ```yaml
  Alert Rules:
  - CPU usage > 80% for 5 minutes
  - Memory usage > 85% for 5 minutes
  - Response time > 2s for 1 minute
  - Error rate > 5% for 2 minutes
  - Database connection failures
  - Health check failures
  ```

### 9. Backup & Recovery ✅
- [ ] **Backup Strategy**
  - [ ] Automated daily database backups enabled
  - [ ] Backup retention policy configured (30 days minimum)
  - [ ] Backup restoration procedure tested
  - [ ] Code repository backup verified

- [ ] **Recovery Procedures**
  - [ ] Database recovery procedure documented
  - [ ] Service rollback procedure documented
  - [ ] Emergency contact list updated
  - [ ] Incident response plan reviewed

## Go-Live Checklist

### 10. Final Pre-Launch ✅
- [ ] **Documentation Complete**
  - [ ] API documentation updated
  - [ ] Deployment procedures documented
  - [ ] Troubleshooting guide available
  - [ ] Emergency procedures documented

- [ ] **Team Preparation**
  - [ ] Development team notified of go-live
  - [ ] Support team trained on new deployment
  - [ ] Monitoring alerts configured to appropriate channels
  - [ ] Escalation procedures established

- [ ] **Rollback Plan**
  - [ ] Previous version tagged and ready
  - [ ] Rollback procedure tested
  - [ ] Database rollback strategy defined
  - [ ] DNS/routing rollback procedure ready

### 11. Launch Execution ✅
- [ ] **Go-Live Steps**
  1. [ ] Final code review and approval
  2. [ ] Deploy to production environment
  3. [ ] Execute post-deployment health checks
  4. [ ] Verify all services are operational
  5. [ ] Monitor for first 30 minutes actively
  6. [ ] Send go-live confirmation to stakeholders

- [ ] **Post-Launch Monitoring (First 24 hours)**
  - [ ] Monitor error rates and response times
  - [ ] Check resource utilization
  - [ ] Verify user authentication flows
  - [ ] Monitor database performance
  - [ ] Watch for any security alerts

## Post-Deployment

### 12. Post-Launch Activities ✅
- [ ] **Performance Validation**
  - [ ] Response time metrics within targets
  - [ ] Resource utilization optimal
  - [ ] Error rates below 1%
  - [ ] User feedback collected and analyzed

- [ ] **Documentation Updates**
  - [ ] Production environment documentation updated
  - [ ] Monitoring runbooks updated
  - [ ] User guides updated with production URLs
  - [ ] API documentation reflects production endpoints

- [ ] **Optimization Planning**
  - [ ] Performance metrics baseline established
  - [ ] Cost optimization opportunities identified
  - [ ] Scaling requirements assessed
  - [ ] Next release planning initiated

### 13. Success Criteria ✅
All items must be verified before considering deployment successful:

- [ ] **Availability**: 99.9% uptime in first week
- [ ] **Performance**: All endpoints respond within SLA
- [ ] **Security**: No security incidents in first month
- [ ] **Functionality**: All user flows working correctly
- [ ] **Monitoring**: All monitoring and alerting operational

## Emergency Procedures

### Rollback Triggers
Execute immediate rollback if any of these occur:
- Critical security vulnerability discovered
- More than 5% error rate sustained for 10+ minutes
- Complete service unavailability for 5+ minutes
- Data corruption or loss detected
- Authentication system failure

### Emergency Contacts
```
Primary: DevOps Team Lead
Secondary: Project Manager
Escalation: Technical Director
Railway Support: support@railway.app
```

### Quick Rollback Procedure
```bash
# 1. Immediate rollback via Railway dashboard
# 2. Via Railway CLI (if available)
railway rollback

# 3. Verify rollback success
curl https://backend.railway.app/health
```

---

**Deployment Checklist Version**: 1.0
**Last Updated**: October 9, 2025
**Next Review**: January 9, 2026

**Sign-off Required**:
- [ ] DevOps Engineer: ________________________
- [ ] Project Manager: ________________________
- [ ] Technical Lead: ________________________