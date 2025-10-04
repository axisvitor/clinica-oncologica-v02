# Railway Deployment Checklist - Frontend Runtime Config

## Pre-Deployment Verification

### ✅ Local Build Test
```bash
cd frontend-hormonia
npm run build:runtime
```

**Expected Output**:
```
✓ built in ~15s
[PostBuild] ✓ Copied runtime config to dist/api/config.js
[PostBuild] ✓ Created Railway-compatible config endpoint
[PostBuild] ✓ Created static config JSON endpoint
[PostBuild] ✓ Created static config.js endpoint
[PostBuild] ✅ Post-build configuration completed successfully!
```

### ✅ Verify Build Artifacts
```bash
# Check all required files exist
ls -la dist/config.js
ls -la dist/api/config
ls -la dist/api/config.js
ls -la dist/api/config-railway.js

# Verify config.js content
head -5 dist/api/config.js
# Should show: window.__ENV_CONFIG__ = { ... }

# Verify JSON config
head -5 dist/api/config
# Should show: valid JSON object
```

## Railway Environment Variables Setup

### Required Variables (Backend Connection)
```bash
VITE_API_URL=https://your-backend.railway.app/api/v1
VITE_API_BASE_URL=https://your-backend.railway.app
VITE_WS_BASE_URL=wss://your-backend.railway.app/ws
```

### Optional Variables (Supabase)
```bash
VITE_SUPABASE_URL=https://xxxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGc...
```

### Optional Variables (Configuration)
```bash
VITE_ENVIRONMENT=production
VITE_DEBUG_MODE=false
VITE_WHATSAPP_INSTANCE_NAME=hormonia-instance
VITE_SESSION_TIMEOUT=3600000
VITE_TOKEN_REFRESH_THRESHOLD=300000
VITE_MAX_FILE_SIZE=10485760
```

## Deployment Steps

### 1. Commit Changes
```bash
git add frontend-hormonia/scripts/post-build-config.js
git add frontend-hormonia/docker-entrypoint.sh
git add frontend-hormonia/nginx.conf
git commit -m "fix: add runtime configuration generation for Railway deployment"
git push origin main
```

### 2. Deploy to Railway
- Railway will automatically detect changes and start build
- Monitor deployment logs in Railway dashboard

### 3. Monitor Deployment Logs

**Look for these key messages**:
```
✅ Build Stage:
[PostBuild] ✅ Post-build configuration completed successfully!

✅ Startup Stage:
🔧 Generating runtime configuration from Railway environment variables...
✅ Runtime configuration generated successfully!
   - API URL: https://...
   - API Base: https://...
   - WS URL: wss://...
✅ nginx.conf created successfully
```

## Post-Deployment Verification

### 1. Test Config Endpoints
```bash
# Test JSON endpoint
curl https://your-app.railway.app/api/config

# Expected: JSON object with your env vars
{
  "VITE_API_URL": "https://your-backend.railway.app/api/v1",
  "VITE_API_BASE_URL": "https://your-backend.railway.app",
  ...
}

# Test JavaScript endpoint
curl https://your-app.railway.app/api/config.js

# Expected: JavaScript code setting window.__ENV_CONFIG__
window.__ENV_CONFIG__ = {
  "VITE_API_URL": "https://your-backend.railway.app/api/v1",
  ...
};
```

### 2. Test Frontend Loading
1. Open `https://your-app.railway.app` in browser
2. Open browser DevTools Console
3. Check for these messages:
   ```
   [Runtime Config] Configuration loaded from Railway environment
   ```
4. Verify config in console:
   ```javascript
   console.log(window.__ENV_CONFIG__)
   ```

### 3. Test Backend Connectivity
1. Try logging in to the application
2. Check Network tab for API calls
3. Verify API calls go to correct backend URL
4. Check for successful API responses

### 4. Check Application Functionality
- [ ] Login works
- [ ] Dashboard loads
- [ ] API requests succeed
- [ ] WebSocket connections work
- [ ] No infinite loading issues
- [ ] No console errors

## Troubleshooting

### Issue: Config endpoint returns 404
**Diagnosis**: Config files not generated at startup

**Fix**:
1. Check Railway logs for entrypoint errors
2. Verify docker-entrypoint.sh has execute permissions
3. Check if `/usr/share/nginx/html/api` directory exists

### Issue: Config has wrong values
**Diagnosis**: Environment variables not set in Railway

**Fix**:
1. Go to Railway dashboard → Service → Variables
2. Verify all `VITE_*` variables are set
3. Redeploy service to pick up new variables

### Issue: Frontend still shows infinite loading
**Diagnosis**: Frontend not reading runtime config

**Fix**:
1. Check browser console for errors
2. Verify `/config.js` is loaded in Network tab
3. Check if `window.__ENV_CONFIG__` exists
4. Verify API URL is correct in config

### Issue: CORS errors
**Diagnosis**: Backend not configured for frontend domain

**Fix**:
1. Update backend CORS settings
2. Add Railway frontend domain to allowed origins
3. Ensure WebSocket URLs use `wss://` not `ws://`

## Success Metrics

✅ **Build Success**:
- Build completes without errors
- All config files created in dist/api/

✅ **Deployment Success**:
- Container starts without errors
- Runtime config generated successfully
- Nginx serves config endpoints

✅ **Runtime Success**:
- Frontend loads completely
- No infinite loading
- API connections work
- No console errors

✅ **User Experience**:
- Login succeeds
- All pages load
- Real-time features work
- No error messages

## Rollback Procedure

If deployment fails:

1. **Check Railway logs** for specific errors
2. **Revert to previous deployment** via Railway dashboard
3. **Fix issues locally** and test with `npm run build:runtime`
4. **Re-deploy** after local verification

## Monitoring After Deployment

### First 24 Hours
- Monitor Railway logs for errors
- Check application performance metrics
- Watch for user-reported issues
- Verify all features work as expected

### Ongoing
- Set up uptime monitoring
- Configure error tracking (Sentry)
- Monitor API response times
- Track user sessions

## Additional Resources

- [Runtime Config Fix Documentation](./RUNTIME_CONFIG_FIX.md)
- [Railway DNS Configuration](./RAILWAY_DNS_INDEX.md)
- [Railway Environment Variables](../RAILWAY_ENV_VARS.md)
- [Railway Backend Connection](../RAILWAY_BACKEND_CONNECTION.md)
