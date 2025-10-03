# Security Audit Report - Quiz Mensal Interface

**Date:** 2024-10-01
**Project:** Quiz Mensal Interface - Next.js Application
**Severity:** HIGH
**Status:** ACTION REQUIRED

---

## Executive Summary

A security audit of the Quiz Mensal Interface repository has identified **CRITICAL EXPOSED SECRETS** in the `.env.local` file that is currently tracked in version control. Immediate action is required to rotate these secrets and secure the application.

---

## Critical Findings

### 1. EXPOSED SECRETS IN VERSION CONTROL

**Severity:** CRITICAL
**File:** `quiz-mensal-interface/.env.local`
**Status:** EXPOSED - Likely committed to git history

**Exposed Secrets:**

```env
JWT_SECRET="Qg5gUR2aGyqzaJtZhV4Udyhev0S8exCpjTg0kyn78dE="
NEXTAUTH_SECRET="eLgWCha+fOgkqjL/7xOvkgzKdNVSjtCqLHFK9Jkpd/M="
```

**Impact:**
- Attackers can forge JWT tokens
- Session hijacking possible
- Unauthorized quiz access
- Patient data compromise risk

**Affected Systems:**
- Quiz Mensal Interface (Frontend)
- Backend API (if JWT_SECRET is shared)
- NextAuth authentication system

---

## Immediate Actions Required

### Priority 1: Secret Rotation (URGENT - Within 24 hours)

1. **Generate New Secrets:**

```bash
# Generate new NEXTAUTH_SECRET
NEW_NEXTAUTH=$(openssl rand -base64 32)
echo "NEXTAUTH_SECRET=$NEW_NEXTAUTH"

# Generate new JWT_SECRET
NEW_JWT=$(openssl rand -base64 32)
echo "JWT_SECRET=$NEW_JWT"
```

2. **Update Production Environment:**

```bash
# Railway
railway variables set NEXTAUTH_SECRET="<new-secret>"
railway variables set JWT_SECRET="<new-secret>"

# Or via Railway Dashboard → Settings → Variables
```

3. **Update Local Development:**

```bash
# Edit .env.local with new secrets
# DO NOT commit this file
```

4. **Coordinate with Backend:**
   - If JWT_SECRET is shared with backend, update backend configuration
   - Ensure coordination to avoid breaking active sessions
   - Plan maintenance window if needed

### Priority 2: Git History Cleanup (Within 48 hours)

**⚠️ WARNING:** This will rewrite git history. Coordinate with team first.

```bash
# Install BFG Repo-Cleaner
brew install bfg  # macOS
# or download from: https://rtyley.github.io/bfg-repo-cleaner/

# Clone a fresh copy
git clone --mirror https://github.com/your-org/your-repo.git
cd your-repo.git

# Remove sensitive files from history
bfg --delete-files .env.local

# Clean up and force push
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push --force

# Notify all developers to re-clone the repository
```

**Alternative (if BFG is not feasible):**
- Consider the secrets permanently compromised
- Rotate all secrets immediately
- Monitor for unauthorized access
- Document the incident

### Priority 3: Update .gitignore (Immediate)

```bash
# Ensure .env.local is in .gitignore
echo ".env.local" >> .gitignore
echo ".env*.local" >> .gitignore

# Verify it's not tracked
git rm --cached .env.local
git commit -m "Remove .env.local from tracking"
git push
```

---

## Security Recommendations

### 1. Environment Variable Management

**Current State:** ❌ INSECURE
**Target State:** ✅ SECURE

**Implementation:**

1. **Never commit secrets to git:**
   - Use `.env.local` for local development only
   - Add `.env.local` to `.gitignore`
   - Use `.env.local.example` as template

2. **Use Railway/Vercel environment variables:**
   - Configure all secrets via platform dashboard
   - Enable secret scanning if available
   - Rotate secrets quarterly

3. **Implement secret scanning:**

```bash
# Install git-secrets
brew install git-secrets

# Setup hooks
cd quiz-mensal-interface
git secrets --install
git secrets --register-aws
git secrets --add 'NEXTAUTH_SECRET=.*'
git secrets --add 'JWT_SECRET=.*'
```

### 2. API Security Enhancements

**Implemented:** ✅
- Request timeout (30s)
- Retry logic with exponential backoff
- Error handling with retryable/non-retryable classification

**Recommended Additions:**

1. **Rate Limiting:**

```typescript
// lib/rate-limiter.ts
export class RateLimiter {
  private requests: Map<string, number[]> = new Map()

  canMakeRequest(identifier: string, maxRequests = 10, windowMs = 60000): boolean {
    const now = Date.now()
    const timestamps = this.requests.get(identifier) || []
    const recentRequests = timestamps.filter(t => now - t < windowMs)

    if (recentRequests.length >= maxRequests) {
      return false
    }

    recentRequests.push(now)
    this.requests.set(identifier, recentRequests)
    return true
  }
}
```

2. **Request Signing:**

```typescript
// Add HMAC signatures to requests
function signRequest(data: any, secret: string): string {
  const crypto = require('crypto')
  return crypto
    .createHmac('sha256', secret)
    .update(JSON.stringify(data))
    .digest('hex')
}
```

3. **Content Security Policy (CSP):**

Already implemented in `next.config.mjs`. Verify headers:

```javascript
// Verify CSP headers in production
// Should include:
// - default-src 'self'
// - script-src 'self'
// - connect-src 'self' https://backend.railway.app
```

### 3. Authentication Security

**Current Implementation:** ⚠️ BASIC

**Recommendations:**

1. **Token Validation Enhancement:**

```typescript
// lib/token-validator.ts
export function validateToken(token: string): boolean {
  // 1. Check format (JWT structure)
  if (!/^[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+$/.test(token)) {
    return false
  }

  // 2. Check expiration (decode without verification first)
  try {
    const [, payload] = token.split('.')
    const decoded = JSON.parse(atob(payload))

    if (decoded.exp && decoded.exp * 1000 < Date.now()) {
      return false
    }
  } catch {
    return false
  }

  return true
}
```

2. **Session Security:**

```typescript
// next-auth configuration
export const authOptions = {
  session: {
    strategy: "jwt",
    maxAge: 72 * 60 * 60, // 72 hours
  },
  cookies: {
    sessionToken: {
      name: `__Secure-next-auth.session-token`,
      options: {
        httpOnly: true,
        sameSite: 'lax',
        path: '/',
        secure: process.env.NODE_ENV === 'production'
      }
    }
  }
}
```

### 4. Data Protection

**Current State:** ⚠️ BASIC
**Improvements Needed:**

1. **Sanitize Input:**

```typescript
// lib/sanitizer.ts
export function sanitizeInput(input: string): string {
  // Remove potential XSS vectors
  return input
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
    .replace(/\//g, '&#x2F;')
}
```

2. **Validate Quiz Responses:**

```typescript
// lib/validators.ts
export function validateQuizResponse(
  value: string | string[],
  questionType: string,
  options?: string[]
): boolean {
  switch (questionType) {
    case 'single_choice':
      return typeof value === 'string' &&
             options?.includes(value)

    case 'multiple_choice':
      return Array.isArray(value) &&
             value.every(v => options?.includes(v))

    case 'scale':
      const num = parseInt(value as string)
      return !isNaN(num) && num >= 0 && num <= 10

    default:
      return true
  }
}
```

### 5. Monitoring & Logging

**Recommended Implementation:**

1. **Error Tracking:**

```bash
# Install Sentry
pnpm add @sentry/nextjs

# Configure in sentry.client.config.js
Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NEXT_PUBLIC_ENVIRONMENT,
  tracesSampleRate: 0.1,
})
```

2. **Security Event Logging:**

```typescript
// lib/security-logger.ts
export function logSecurityEvent(event: {
  type: 'token_invalid' | 'token_expired' | 'rate_limit' | 'suspicious_request'
  token?: string
  ip?: string
  details?: any
}) {
  // Send to monitoring service
  if (process.env.NODE_ENV === 'production') {
    console.error('[SECURITY]', {
      timestamp: new Date().toISOString(),
      ...event
    })
  }
}
```

---

## Compliance Checklist

### LGPD (Lei Geral de Proteção de Dados)

- [ ] Data encryption in transit (HTTPS)
- [ ] Data encryption at rest (database level)
- [ ] User consent logging
- [ ] Data retention policy implemented
- [ ] Right to deletion mechanism
- [ ] Data breach notification procedure
- [ ] Privacy policy displayed
- [ ] Terms of service acceptance

### Security Best Practices

- [x] HTTPS enforced in production
- [x] CSP headers configured
- [x] XSS protection headers
- [x] CSRF protection (via NextAuth)
- [ ] Rate limiting implemented
- [ ] Security headers verified
- [ ] Dependency scanning enabled
- [ ] Regular security audits scheduled

---

## Incident Response Plan

### If Breach Detected:

1. **Immediate Actions (0-1 hour):**
   - Rotate all secrets immediately
   - Revoke all active sessions
   - Enable maintenance mode if necessary
   - Notify security team

2. **Investigation (1-24 hours):**
   - Review access logs
   - Identify scope of breach
   - Document timeline
   - Assess data exposure

3. **Remediation (24-72 hours):**
   - Fix identified vulnerabilities
   - Deploy security patches
   - Re-enable services gradually
   - Monitor for anomalies

4. **Post-Incident (72+ hours):**
   - Conduct post-mortem
   - Update security procedures
   - Notify affected users (if required by LGPD)
   - File incident report

---

## Testing & Verification

### Security Testing Checklist:

```bash
# 1. Test secret rotation
railway variables set NEXTAUTH_SECRET="test-secret"
# Verify app still works

# 2. Test HTTPS enforcement
curl http://your-app.railway.app
# Should redirect to https://

# 3. Test CSP headers
curl -I https://your-app.railway.app
# Should include Content-Security-Policy header

# 4. Test token validation
curl -X POST https://your-app.railway.app/api/v1/monthly-quiz-public/access \
  -H "Content-Type: application/json" \
  -d '{"token":"invalid-token"}'
# Should return 401/403

# 5. Test rate limiting (if implemented)
# Make 100 requests rapidly
# Should block after threshold
```

---

## Maintenance Schedule

### Regular Security Tasks:

**Weekly:**
- Review error logs for suspicious activity
- Check Railway deployment logs
- Verify no new secrets committed to git

**Monthly:**
- Update dependencies (`pnpm update`)
- Review and update `.gitignore`
- Test backup/recovery procedures
- Review Railway access logs

**Quarterly:**
- Rotate NEXTAUTH_SECRET and JWT_SECRET
- Security audit
- Penetration testing (if budget allows)
- Review and update security policies

**Annually:**
- Full security assessment
- Update security documentation
- Review compliance requirements
- Train team on security practices

---

## Contact Information

**Security Team:**
- Email: security@clinicahormonia.com.br
- On-call: [Define on-call rotation]

**Escalation:**
1. Team Lead
2. CTO
3. CEO (for major incidents)

---

## Appendix

### A. Secret Generation Scripts

```bash
#!/bin/bash
# generate-secrets.sh

echo "=== Generating New Secrets ==="
echo ""

echo "NEXTAUTH_SECRET:"
openssl rand -base64 32
echo ""

echo "JWT_SECRET:"
openssl rand -base64 32
echo ""

echo "Copy these values to Railway variables"
echo "NEVER commit them to git"
```

### B. Git History Cleanup Script

```bash
#!/bin/bash
# cleanup-git-history.sh

echo "⚠️  WARNING: This will rewrite git history!"
echo "Make sure all team members are notified."
read -p "Continue? (yes/no) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
  # Backup current repo
  cd ..
  cp -r quiz-mensal-interface quiz-mensal-interface-backup

  # Clean history
  cd quiz-mensal-interface
  git filter-branch --force --index-filter \
    "git rm --cached --ignore-unmatch .env.local" \
    --prune-empty --tag-name-filter cat -- --all

  echo "History cleaned. Review changes before force pushing."
  echo "To force push: git push --force --all"
fi
```

### C. Railway Environment Setup Script

```bash
#!/bin/bash
# setup-railway-env.sh

echo "=== Railway Environment Setup ==="
echo ""

read -p "Backend URL (e.g., https://backend.railway.app): " BACKEND_URL
read -p "Quiz App URL (e.g., https://quiz.railway.app): " APP_URL

echo ""
echo "Generating secrets..."
NEXTAUTH_SECRET=$(openssl rand -base64 32)
JWT_SECRET=$(openssl rand -base64 32)

echo ""
echo "Setting Railway variables..."
railway variables set NEXT_PUBLIC_QUIZ_PUBLIC_API_URL="$BACKEND_URL/api/v1/monthly-quiz-public"
railway variables set NEXTAUTH_URL="$APP_URL"
railway variables set NEXTAUTH_SECRET="$NEXTAUTH_SECRET"
railway variables set JWT_SECRET="$JWT_SECRET"
railway variables set NODE_ENV="production"
railway variables set NEXT_PUBLIC_FORCE_HTTPS="true"
railway variables set NEXT_PUBLIC_DEBUG_MODE="false"

echo ""
echo "✅ Railway environment configured"
echo "Secrets have been set. Do not share them."
```

---

**Document Version:** 1.0
**Last Updated:** 2024-10-01
**Next Review:** 2024-11-01
