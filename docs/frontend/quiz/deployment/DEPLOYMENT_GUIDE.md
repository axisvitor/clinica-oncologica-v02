# Quiz Mensal Interface - Railway Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying the Quiz Mensal Interface to Railway, a standalone Next.js application that integrates with the Clínica Oncológica backend system.

## Prerequisites

1. **Railway Account**: Sign up at [railway.app](https://railway.app)
2. **GitHub Repository**: Code must be in a GitHub repository
3. **Backend Deployed**: The backend API must be deployed and accessible
4. **Environment Variables**: All required secrets and configuration

## 1. Environment Variables Setup

### Required Variables

Copy `.env.production` and update the following critical variables:

```bash
# ⚠️ CRITICAL API URL CONFIGURATION ⚠️
# The lib/api.ts file AUTO-INJECTS /api/v2/monthly-quiz-public to the base URL!
#
# METHOD 1 (RECOMMENDED): Base URL only
NEXT_PUBLIC_API_URL=https://your-backend-railway-app.up.railway.app
# Result: https://your-backend-railway-app.up.railway.app/api/v2/monthly-quiz-public ✅
#
# METHOD 2: Explicit full path (bypasses auto-injection)
# NEXT_PUBLIC_QUIZ_PUBLIC_API_URL=https://your-backend-railway-app.up.railway.app/api/v2/monthly-quiz-public
#
# ❌ WRONG - DO NOT DO THIS (causes path duplication):
# NEXT_PUBLIC_API_URL=https://your-backend-railway-app.up.railway.app/api/v2
# Result: https://...up.railway.app/api/v2/api/v2/monthly-quiz-public ❌ (404 ERROR)

NEXT_PUBLIC_BASE_URL=https://quiz-mensal-interface.up.railway.app

# SECURITY: Generate new secrets
NEXTAUTH_SECRET=your-generated-nextauth-secret
JWT_SECRET=your-generated-jwt-secret

# PRODUCTION: Set correct environment
NODE_ENV=production
PORT=3001
```

### Generate Secrets

```bash
# NextAuth Secret
openssl rand -base64 32

# JWT Secret
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

## 2. Railway Deployment Steps

### Option A: GitHub Integration (Recommended)

1. **Connect Repository**:
   - Go to Railway Dashboard
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository
   - Select `/quiz-mensal-interface` as root directory

2. **Configure Build Settings**:
   - Railway will auto-detect Next.js
   - Build command: `npm run build`
   - Start command: `npm start`
   - Port: `3001`

3. **Set Environment Variables**:
   - Go to project Settings → Variables
   - Add all variables from `.env.production`
   - Ensure `RAILWAY_PORT` is mapped to `PORT`

### Option B: Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Initialize project
cd quiz-mensal-interface
railway init

# Deploy
railway up
```

## 3. Configuration Files

### railway.json
```json
{
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "npm run build"
  },
  "deploy": {
    "startCommand": "npm start",
    "healthcheckPath": "/api/health",
    "restartPolicyType": "ON_FAILURE"
  }
}
```

### next.config.mjs
- Production optimizations enabled
- Security headers configured
- Image optimization for Railway
- Bundle splitting for performance

### package.json Scripts
```json
{
  "scripts": {
    "build": "next build",
    "start": "next start",
    "railway:build": "npm run build",
    "railway:start": "npm start"
  }
}
```

## 4. Health Checks & Monitoring

### Health Check Endpoint
```
GET /api/health
```

Response example:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00.000-03:00",
  "uptime": 3600,
  "environment": "production",
  "dependencies": {
    "backend_api": {
      "status": "healthy",
      "url": "https://your-backend.up.railway.app"
    }
  }
}
```

### Railway Monitoring
- Built-in metrics dashboard
- Log aggregation
- Performance monitoring
- Automatic restarts on failure

## 5. Domain Configuration

### Custom Domain (Optional)
1. Go to Railway project Settings
2. Click "Domains"
3. Add custom domain
4. Update DNS records as instructed
5. Update `NEXT_PUBLIC_BASE_URL` accordingly

## 6. Environment-Specific Configuration

### Development
```bash
# Base URL only - /api/v2/monthly-quiz-public is auto-injected
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_BASE_URL=http://localhost:3000
NODE_ENV=development

# OR use explicit full path:
# NEXT_PUBLIC_QUIZ_PUBLIC_API_URL=http://localhost:8000/api/v2/monthly-quiz-public
```

### Production
```bash
# Base URL only - /api/v2/monthly-quiz-public is auto-injected
NEXT_PUBLIC_API_URL=https://backend-production.up.railway.app
NEXT_PUBLIC_BASE_URL=https://quiz-mensal.up.railway.app
NODE_ENV=production

# OR use explicit full path:
# NEXT_PUBLIC_QUIZ_PUBLIC_API_URL=https://backend-production.up.railway.app/api/v2/monthly-quiz-public
```

### Understanding API URL Resolution (lib/api.ts behavior)

The `lib/api.ts` file has smart URL resolution logic:

1. **Priority 1**: `NEXT_PUBLIC_QUIZ_PUBLIC_API_URL` (if set) - uses exact URL
2. **Priority 2**: `NEXT_PUBLIC_API_URL` - auto-appends `/api/v2/monthly-quiz-public`

**Code Reference (lib/api.ts:16-35):**
```typescript
function resolveApiBaseUrl(): string {
  const explicit = process.env.NEXT_PUBLIC_QUIZ_PUBLIC_API_URL
  if (explicit) {
    return explicit.replace(/\/$/, '')  // Uses exact URL
  }

  const legacy = process.env.NEXT_PUBLIC_API_URL
  if (legacy) {
    let trimmed = legacy.replace(/\/$/, '')

    // Auto-injects /api/v2 if missing
    if (!trimmed.includes('/api/v2')) {
      trimmed = `${trimmed}/api/v2`
    }

    // Auto-appends /monthly-quiz-public
    return trimmed.endsWith('/monthly-quiz-public') ? trimmed : `${trimmed}/monthly-quiz-public`
  }

  return DEFAULT_API_BASE_URL
}
```

**Therefore:**
- `NEXT_PUBLIC_API_URL=http://localhost:8000` → `http://localhost:8000/api/v2/monthly-quiz-public` ✅
- `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v2` → `http://localhost:8000/api/v2/api/v2/monthly-quiz-public` ❌

## 7. Security Checklist

- [ ] All secrets are generated and unique
- [ ] HTTPS is enforced in production
- [ ] Security headers are configured
- [ ] CORS is properly configured
- [ ] No sensitive data in client-side code
- [ ] CSP headers are enabled
- [ ] Rate limiting is configured

## 8. Performance Optimizations

### Enabled Features
- Bundle splitting and optimization
- Image optimization with WebP/AVIF
- CSS optimization
- Tree shaking for unused code
- Compression enabled
- Static asset caching

### Monitoring Performance
- Railway provides built-in performance metrics
- Monitor bundle size and loading times
- Use Lighthouse for performance audits

## 9. Integration with Backend

### API Communication
- All API calls use `NEXT_PUBLIC_API_URL`
- JWT tokens for authentication
- Proper error handling and retries
- CORS configuration in backend

### Quiz Flow Integration
1. User accesses quiz via generated link
2. Frontend validates token with backend
3. Quiz questions fetched from backend API
4. Responses submitted to backend
5. Results processed and stored

## 10. Troubleshooting

### Common Issues

**Build Failures**:
```bash
# Check build logs in Railway dashboard
# Ensure all dependencies are in package.json
# Verify TypeScript types are correct
```

**API Connection Issues (404 Errors)**:
```bash
# ⚠️ MOST COMMON ISSUE: Incorrect API URL causing path duplication
# Verify NEXT_PUBLIC_API_URL does NOT include /api/v2
# WRONG: NEXT_PUBLIC_API_URL=http://localhost:8000/api/v2 ❌
# RIGHT: NEXT_PUBLIC_API_URL=http://localhost:8000 ✅

# Check browser DevTools Network tab to see actual URL being called
# Should be: http://localhost:8000/api/v2/monthly-quiz-public
# NOT: http://localhost:8000/api/v2/api/v2/monthly-quiz-public (duplicated)

# Check backend CORS configuration
# Ensure backend is deployed and healthy
```

**Environment Variable Issues**:
```bash
# Verify all NEXT_PUBLIC_ vars are set
# Check Railway environment variables
# Restart deployment after changes
```

### Debugging Steps
1. Check Railway deployment logs
2. Use health check endpoint
3. Verify environment variables
4. Test API connectivity
5. Review browser console errors

## 11. Backup and Recovery

### Database Backup
- Quiz responses are stored in backend database
- Backend handles all data persistence
- Frontend is stateless

### Deployment Recovery
- Railway maintains deployment history
- Can rollback to previous versions
- Environment variables are preserved

## 12. Scaling Considerations

### Auto-scaling
- Railway handles automatic scaling
- Monitor resource usage in dashboard
- Consider upgrading plan for high traffic

### Performance Monitoring
- Monitor response times
- Track error rates
- Use Railway metrics dashboard

## Support and Documentation

- **Railway Docs**: [docs.railway.app](https://docs.railway.app)
- **Next.js Deploy**: [nextjs.org/docs/deployment](https://nextjs.org/docs/deployment)
- **Project Repository**: [GitHub Repository Link]

## Quick Deployment Checklist

- [ ] Repository connected to Railway
- [ ] Environment variables configured
- [ ] Backend API URL updated
- [ ] Secrets generated and set
- [ ] Health check endpoint working
- [ ] Custom domain configured (if needed)
- [ ] HTTPS enforced
- [ ] Performance optimizations verified