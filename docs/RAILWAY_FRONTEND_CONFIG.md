# Railway Frontend Configuration Guide

## Critical Issue Identified

**Problem**: Frontend is connecting to `http://127.0.0.1:8000` instead of production backend
**Cause**: Missing environment variables in Railway dashboard
**Impact**: Authentication fails, page stuck in loading state

## Required Environment Variables for Railway Frontend Service

Add **ALL** of these variables to your Railway frontend service dashboard:

### 1. API Configuration (CRITICAL - Currently Missing)

```env
VITE_API_BASE_URL=https://clinica-oncologica-v02-production.up.railway.app
VITE_API_URL=https://clinica-oncologica-v02-production.up.railway.app/api/v1
VITE_WS_URL=wss://clinica-oncologica-v02-production.up.railway.app/ws
```

### 2. Firebase Configuration (Already Added)

```env
VITE_FIREBASE_API_KEY=AIzaSyDbZHMNV2eZQty03TgA4yNo_3L6UDSpHdI
VITE_FIREBASE_AUTH_DOMAIN=sistema-oncologico-auth.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=sistema-oncologico-auth
VITE_FIREBASE_STORAGE_BUCKET=sistema-oncologico-auth.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=608742835827
VITE_FIREBASE_APP_ID=1:608742835827:web:fa12840b0bd4949b7c8c06
VITE_FIREBASE_MEASUREMENT_ID=G-2QZQFKJMH2
```

### 3. Feature Flags (Optional but Recommended)

```env
VITE_ENABLE_ANALYTICS=false
VITE_ENABLE_SENTRY=false
VITE_DEV_MODE=false
```

## Step-by-Step Railway Configuration

### Option 1: Railway Dashboard (Recommended)

1. Go to Railway dashboard: https://railway.app
2. Select your frontend service: `frontend-hormonia`
3. Click on **Variables** tab
4. Click **+ New Variable**
5. Add each variable one by one:
   - Variable name: `VITE_API_BASE_URL`
   - Value: `https://clinica-oncologica-v02-production.up.railway.app`
6. Repeat for ALL variables listed above
7. Click **Deploy** to trigger redeploy

### Option 2: Railway CLI (Faster for Multiple Variables)

```bash
# Install Railway CLI if not already installed
npm i -g @railway/cli

# Login to Railway
railway login

# Link to your project
railway link

# Set variables (run each command)
railway variables set VITE_API_BASE_URL=https://clinica-oncologica-v02-production.up.railway.app
railway variables set VITE_API_URL=https://clinica-oncologica-v02-production.up.railway.app/api/v1
railway variables set VITE_WS_URL=wss://clinica-oncologica-v02-production.up.railway.app/ws

# Railway will automatically redeploy
```

## Verification After Deployment

### 1. Check Build Logs

Look for these lines in Railway build logs:

```
Building configuration:
  hasApiKey: true
  apiKeyPreview: AIzaSyDbZH...
  authDomain: sistema-oncologico-auth.firebaseapp.com
  projectId: sistema-oncologico-auth
```

### 2. Check Browser Console

After redeployment, open browser console and look for:

```
[Firebase Config] Environment check: {
  hasRuntime: true,
  importMetaEnv: {
    VITE_FIREBASE_API_KEY: true,
    VITE_FIREBASE_AUTH_DOMAIN: true,
    VITE_FIREBASE_PROJECT_ID: true
  }
}
```

### 3. Verify API Calls

Console should show:

```
[ApiClient] Calling /api/v1/auth/me with token: {
  hasToken: true,
  baseURL: "https://clinica-oncologica-v02-production.up.railway.app/api/v1"
}
```

**NOT**:
```
baseURL: "http://127.0.0.1:8000/api/v1"  ❌ WRONG
```

## Current Errors (Before Fix)

```
Failed to load resource: net::ERR_CONNECTION_REFUSED
@ http://127.0.0.1:8000/api/v1/auth/me

Failed to load resource: net::ERR_CONNECTION_REFUSED
@ http://127.0.0.1:8000/api/v1/auth/notifications

WebSocket connection failed
```

## Expected Behavior (After Fix)

```
[ApiClient] Calling /api/v1/auth/me with token: {
  hasToken: true,
  baseURL: "https://clinica-oncologica-v02-production.up.railway.app/api/v1"
}

[ApiClient] Received user from /api/v1/auth/me: {
  id: "...",
  email: "...",
  role: "admin",
  is_active: true
}
```

## Why This Happened

### Docker Build Process

1. **Railway** provides environment variables
2. **Dockerfile** declares them as ARGs:
   ```dockerfile
   ARG VITE_FIREBASE_API_KEY
   ARG VITE_API_URL
   ```
3. **Dockerfile** converts ARGs to ENVs:
   ```dockerfile
   ENV VITE_FIREBASE_API_KEY=$VITE_FIREBASE_API_KEY
   ENV VITE_API_URL=$VITE_API_URL
   ```
4. **Vite** injects ENVs into JavaScript bundle during `npm run build`

### What Was Missing

Only Firebase variables were added to Railway. The API URL variables were never configured, so:
- `VITE_API_URL` = undefined
- Frontend falls back to default: `http://127.0.0.1:8000`
- All API calls fail with `ERR_CONNECTION_REFUSED`

## Next Steps After Configuration

1. Wait for Railway redeploy (3-5 minutes)
2. Open browser console
3. Navigate to login page
4. Verify API calls go to production backend
5. Test authentication flow
6. Run Playwright performance analysis

## Troubleshooting

### If Still Seeing Localhost Errors

1. **Check Railway Variables Tab**: Verify all variables are present
2. **Check Build Logs**: Look for environment variable values during build
3. **Hard Refresh Browser**: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)
4. **Clear Browser Cache**: Ensure you're not loading old bundle

### If Firebase Still Not Initializing

1. Check that Firebase variables match EXACTLY (no typos)
2. Verify `apiKey` starts with `AIzaSy`
3. Check Railway build logs for "Building configuration" output

## Complete Variable Checklist

Copy this to Railway Variables tab:

```
✅ VITE_API_BASE_URL
✅ VITE_API_URL
✅ VITE_WS_URL
✅ VITE_FIREBASE_API_KEY
✅ VITE_FIREBASE_AUTH_DOMAIN
✅ VITE_FIREBASE_PROJECT_ID
✅ VITE_FIREBASE_STORAGE_BUCKET
✅ VITE_FIREBASE_MESSAGING_SENDER_ID
✅ VITE_FIREBASE_APP_ID
✅ VITE_FIREBASE_MEASUREMENT_ID
```

Total: **10 required variables**

---

**Status**: Configuration guide created
**Action Required**: Add missing API variables to Railway dashboard
**ETA**: 3-5 minutes for redeploy after configuration
