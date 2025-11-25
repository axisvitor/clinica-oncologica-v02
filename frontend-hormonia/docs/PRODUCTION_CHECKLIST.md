# Production Deployment Checklist

## Pre-Deployment Configuration

### Environment Variables
- [ ] All required environment variables configured in deployment platform
- [ ] API URL points to production backend (`VITE_API_URL`)
- [ ] WebSocket URL configured for production (`VITE_WS_URL`)
- [ ] Firebase production credentials set:
  - [ ] `VITE_FIREBASE_API_KEY`
  - [ ] `VITE_FIREBASE_AUTH_DOMAIN`
  - [ ] `VITE_FIREBASE_PROJECT_ID`
  - [ ] `VITE_FIREBASE_STORAGE_BUCKET`
  - [ ] `VITE_FIREBASE_MESSAGING_SENDER_ID`
  - [ ] `VITE_FIREBASE_APP_ID`
- [ ] Sentry DSN configured (`VITE_SENTRY_DSN`) - Optional
- [ ] Environment set to production (`VITE_ENVIRONMENT=production`)
- [ ] Debug mode disabled (`VITE_DEBUG_MODE=false`)

### Security Configuration
- [ ] HTTPS enforced (`VITE_FORCE_HTTPS=true`)
- [ ] CSP enabled (`VITE_ENABLE_CSP=true`)
- [ ] Security headers enabled (`VITE_SECURITY_HEADERS_ENABLED=true`)
- [ ] No hardcoded secrets in code
- [ ] All sensitive data removed from environment files
- [ ] CORS properly configured on backend

## Build Verification

### Build Process
- [ ] `npm run build` completes without errors
- [ ] `npm run typecheck` passes with zero errors
- [ ] `npm run lint` passes with zero warnings
- [ ] No TypeScript compilation errors
- [ ] All dependencies installed successfully

### Bundle Optimization
- [ ] Bundle size within limits:
  - [ ] Main chunk < 500KB
  - [ ] Vendor chunk < 300KB
  - [ ] UI chunk < 200KB
  - [ ] Total initial load < 1MB
- [ ] Code splitting verified (multiple chunks created)
- [ ] Tree-shaking working (unused code removed)
- [ ] CSS minification enabled
- [ ] Asset optimization complete

### Production Build Settings (vite.config.ts)
- [x] `minify: "esbuild"` enabled
- [x] `sourcemap: false` for production
- [x] `drop: ["console", "debugger"]` configured
- [x] Tree-shaking enabled (`treeshake: { preset: "recommended" }`)
- [x] CSS minification enabled (`cssMinify: "lightningcss"`)
- [x] Code splitting configured with manual chunks
- [x] Chunk size warning limit set to 500KB

## Security Checklist

### Code Security
- [ ] No `console.log` statements in production code
- [ ] No `debugger` statements in production code
- [ ] No hardcoded API keys or secrets
- [ ] No development URLs or endpoints
- [ ] Input validation implemented
- [ ] XSS protection enabled
- [ ] CSRF protection enabled

### Network Security
- [ ] HTTPS enforced for all requests
- [ ] Secure WebSocket connections (WSS)
- [ ] API authentication tokens secured
- [ ] Session management properly configured
- [ ] Token refresh mechanism working
- [ ] Proper CORS configuration

### Content Security Policy
- [ ] CSP headers configured in vite.config.ts
- [ ] `script-src` properly restricted
- [ ] `style-src` allows required fonts
- [ ] `connect-src` lists all API endpoints
- [ ] `frame-ancestors` set to 'none'
- [ ] `upgrade-insecure-requests` enabled

## Performance Optimization

### Code Optimization
- [x] Lazy loading enabled for routes
- [x] Code splitting for large components
- [x] Dynamic imports used where appropriate
- [ ] Images optimized (compressed, proper formats)
- [ ] Fonts optimized and preloaded
- [ ] Dead code eliminated

### Caching Strategy
- [ ] Cache headers properly configured
- [ ] Service worker configured (if PWA enabled)
- [ ] Static assets have long cache times
- [ ] API responses cached appropriately
- [ ] Browser caching optimized

### Loading Performance
- [ ] Initial bundle size < 1MB
- [ ] First Contentful Paint < 2s
- [ ] Time to Interactive < 3.5s
- [ ] Critical CSS inlined
- [ ] Non-critical resources deferred
- [ ] Preload/prefetch configured

## Testing Requirements

### Unit Tests
- [ ] All unit tests passing (`npm run test:run`)
- [ ] Test coverage > 80%
- [ ] Critical paths tested
- [ ] Edge cases covered

### Integration Tests
- [ ] API integration tests passing
- [ ] Authentication flow tested
- [ ] Data persistence verified
- [ ] Error handling tested

### E2E Tests
- [ ] Critical user journeys tested (`npm run test:e2e`)
- [ ] Login/logout flow works
- [ ] Patient management flow tested
- [ ] WhatsApp integration tested
- [ ] Mobile responsiveness verified

### Browser Compatibility
- [ ] Chrome (latest 2 versions)
- [ ] Firefox (latest 2 versions)
- [ ] Safari (latest 2 versions)
- [ ] Edge (latest 2 versions)
- [ ] Mobile browsers tested

## Deployment Configuration

### Railway Configuration
- [ ] Railway project created
- [ ] Environment variables configured in Railway
- [ ] Build command: `npm run build:prod`
- [ ] Start command: `npm run preview`
- [ ] Port configuration correct
- [ ] Health check endpoint working
- [ ] Auto-deploy from Git configured

### Domain & DNS
- [ ] Custom domain configured (if applicable)
- [ ] DNS records properly set
- [ ] SSL certificate active
- [ ] Domain redirects working
- [ ] www/non-www redirects configured

### Monitoring & Logging
- [ ] Error tracking configured (Sentry)
- [ ] Performance monitoring enabled
- [ ] Analytics tracking set up
- [ ] Health check endpoint available
- [ ] Logging properly configured

## Post-Deployment Verification

### Functionality Testing
- [ ] Application loads successfully
- [ ] Login/authentication working
- [ ] Main features functional
- [ ] API connectivity verified
- [ ] WebSocket connections working
- [ ] Firebase authentication working

### Performance Testing
- [ ] Page load times acceptable
- [ ] API response times normal
- [ ] No JavaScript errors in console
- [ ] No network errors
- [ ] Assets loading correctly

### Security Verification
- [ ] HTTPS working on all pages
- [ ] Security headers present
- [ ] No mixed content warnings
- [ ] Authentication tokens secure
- [ ] Session management working

### Mobile Testing
- [ ] Responsive design working
- [ ] Touch interactions functional
- [ ] Mobile performance acceptable
- [ ] PWA features working (if enabled)

## Rollback Plan

### Backup Strategy
- [ ] Previous version backed up
- [ ] Database backup created
- [ ] Environment variables documented
- [ ] Rollback procedure documented

### Rollback Triggers
- [ ] Critical bugs identified
- [ ] Performance degradation
- [ ] Security vulnerabilities
- [ ] Data integrity issues

### Rollback Steps
1. [ ] Identify issue severity
2. [ ] Notify stakeholders
3. [ ] Revert to previous deployment
4. [ ] Verify rollback successful
5. [ ] Document incident
6. [ ] Plan fix deployment

## Documentation

### Technical Documentation
- [ ] API endpoints documented
- [ ] Environment variables documented
- [ ] Deployment process documented
- [ ] Architecture diagrams updated
- [ ] Change log updated

### User Documentation
- [ ] User guides updated
- [ ] Release notes prepared
- [ ] Known issues documented
- [ ] Support contacts listed

## Sign-off Checklist

### Team Approvals
- [ ] Development team approval
- [ ] QA team approval
- [ ] Security team approval
- [ ] Product owner approval

### Final Checks
- [ ] All checklist items completed
- [ ] Stakeholders notified
- [ ] Support team briefed
- [ ] Monitoring alerts configured
- [ ] Deployment window scheduled

---

## Deployment Commands

```bash
# Local validation before deployment
npm run typecheck
npm run lint
npm run test:run
npm run test:e2e

# Production build locally (test)
npm run build:prod

# Preview production build
npm run preview:local

# Railway deployment (automatic on git push)
git push origin main
```

## Emergency Contacts

- **DevOps Lead**: [Contact]
- **Backend Team**: [Contact]
- **Frontend Team**: [Contact]
- **Security Team**: [Contact]
- **Product Owner**: [Contact]

## Notes

- This checklist should be reviewed before every production deployment
- All items must be checked before proceeding with deployment
- Any unchecked items must be documented with justification
- Keep this document updated with lessons learned from each deployment
