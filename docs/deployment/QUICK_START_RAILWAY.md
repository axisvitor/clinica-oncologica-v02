# Quick Start: Railway Frontend Deployment

## ⚡ 5-Minute Setup

### 1. Test Build Locally (30 seconds)
```bash
cd frontend-hormonia
npm run build:runtime
```

**✅ Success indicators**:
- Build completes without errors
- Files exist: `dist/api/config`, `dist/api/config.js`

### 2. Set Railway Environment Variables (2 minutes)

Go to Railway Dashboard → Your Service → Variables tab

**Required variables**:
```bash
VITE_API_URL=https://your-backend.railway.app/api/v1
VITE_API_BASE_URL=https://your-backend.railway.app
VITE_WS_BASE_URL=wss://your-backend.railway.app/ws
```

**Optional variables** (if using Supabase):
```bash
VITE_SUPABASE_URL=https://xxxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGc...
```

### 3. Deploy (1 minute)
```bash
git add .
git commit -m "fix: add runtime configuration"
git push
```

Railway will automatically deploy.

### 4. Verify Deployment (1 minute)

**Check Railway logs for**:
```
✅ Runtime configuration generated successfully!
✅ nginx.conf created successfully
```

**Test config endpoint**:
```bash
curl https://your-app.railway.app/api/config
```

Should return JSON with your environment variables.

### 5. Test Frontend (30 seconds)

Open `https://your-app.railway.app` in browser:
- ✅ Page loads (no infinite loading)
- ✅ Console shows: `[Runtime Config] Configuration loaded`
- ✅ Login works
- ✅ API calls succeed

## 🚨 Troubleshooting (Quick Fixes)

### Issue: 404 on `/api/config`
**Fix**: Check Railway logs, redeploy if needed

### Issue: Wrong API URL in config
**Fix**: Update Railway environment variables, redeploy

### Issue: Infinite loading
**Fix**: Check browser console, verify `window.__ENV_CONFIG__` exists

## 📚 Full Documentation

- **Complete Guide**: [RUNTIME_CONFIG_FIX.md](./RUNTIME_CONFIG_FIX.md)
- **Deployment Checklist**: [RAILWAY_DEPLOYMENT_CHECKLIST.md](./RAILWAY_DEPLOYMENT_CHECKLIST.md)
- **Executive Summary**: [RUNTIME_CONFIG_SUMMARY.md](./RUNTIME_CONFIG_SUMMARY.md)

## ✅ Success Checklist

- [ ] Local build succeeds
- [ ] Environment variables set in Railway
- [ ] Code committed and pushed
- [ ] Railway deployment succeeds
- [ ] Config endpoints return correct data
- [ ] Frontend loads without errors
- [ ] API calls work correctly

---

**Total Time**: ~5 minutes
**Difficulty**: Easy
**Status**: ✅ Production Ready
