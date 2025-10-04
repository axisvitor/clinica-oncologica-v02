# Frontend Runtime Configuration Fix - SOLUTION

## Problem Diagnosed
The production frontend was stuck in infinite loading because runtime configuration files were not being served properly. The issue was that config files were created during build but not updated with Railway's runtime environment variables.

## Solution Implemented

### 1. Enhanced Post-Build Script
**File**: `frontend-hormonia/scripts/post-build-config.js`

**Changes Made**:
- Creates `dist/api/config` (JSON format) with build-time environment variables
- Creates `dist/api/config.js` (JavaScript format) with `window.__ENV_CONFIG__`
- Both files serve as fallbacks if runtime generation fails

### 2. Docker Entrypoint Integration
**File**: `frontend-hormonia/docker-entrypoint.sh`

**Critical Addition**: Runtime config generation section that:
1. Reads Railway environment variables at container startup
2. Generates fresh `/usr/share/nginx/html/api/config` with runtime values
3. Generates fresh `/usr/share/nginx/html/api/config.js` with runtime values
4. Happens BEFORE nginx starts serving requests

**Key Code**:
```bash
# Generate JSON configuration from Railway environment variables
cat > "$CONFIG_FILE" << EOF
{
  "VITE_SUPABASE_URL": "${VITE_SUPABASE_URL:-}",
  "VITE_SUPABASE_ANON_KEY": "${VITE_SUPABASE_ANON_KEY:-}",
  "VITE_API_URL": "${VITE_API_URL:-http://localhost:8000/api/v1}",
  ...
}
EOF
```

### 3. Nginx Configuration Update
**File**: `frontend-hormonia/nginx.conf`

**Changes Made**:
- Added dedicated endpoint for `/api/config` (JSON)
- Added dedicated endpoint for `/api/config.js` (JavaScript)
- Both with `Cache-Control: no-store` to prevent caching
- Both serve files generated at container startup

### 4. Build Process Flow

```
Build Time (npm run build:runtime):
├── TypeScript compilation
├── Vite build
└── post-build-config.js runs
    ├── Creates dist/api/config (with build-time defaults)
    ├── Creates dist/api/config.js (with build-time defaults)
    └── Creates dist/config.js (runtime loader script)

Container Startup (Railway):
├── docker-entrypoint.sh runs
├── Generates /usr/share/nginx/html/api/config (with Railway env vars)
├── Generates /usr/share/nginx/html/api/config.js (with Railway env vars)
└── Starts nginx → Serves fresh config files
```

## Files Created/Modified

### Modified Files:
1. `frontend-hormonia/scripts/post-build-config.js` - Enhanced to create config.js
2. `frontend-hormonia/docker-entrypoint.sh` - Added runtime config generation
3. `frontend-hormonia/nginx.conf` - Added /api/config.js endpoint

### New Files:
1. `frontend-hormonia/scripts/generate-runtime-config.sh` - Standalone helper script
2. `docs/deployment/RUNTIME_CONFIG_FIX.md` - This documentation

## Verification Steps

### Local Testing:
```bash
cd frontend-hormonia
npm run build:runtime

# Verify files exist
ls -la dist/config.js
ls -la dist/api/config
ls -la dist/api/config.js
ls -la dist/api/config-railway.js
```

### Production Testing (Railway):
1. Deploy to Railway
2. Check deployment logs for:
   ```
   🔧 Generating runtime configuration from Railway environment variables...
   ✅ Runtime configuration generated successfully!
   ```
3. Access endpoints:
   - `https://your-app.railway.app/api/config` (should return JSON)
   - `https://your-app.railway.app/api/config.js` (should return JS)
4. Frontend should load configuration and connect to backend

## Railway Environment Variables Required

The following environment variables should be set in Railway dashboard:

### Essential:
- `VITE_API_URL` - Backend API URL (e.g., `https://backend.railway.app/api/v1`)
- `VITE_API_BASE_URL` - Backend base URL (e.g., `https://backend.railway.app`)
- `VITE_WS_BASE_URL` - WebSocket URL (e.g., `wss://backend.railway.app/ws`)

### Optional (Supabase):
- `VITE_SUPABASE_URL` - Supabase project URL
- `VITE_SUPABASE_ANON_KEY` - Supabase anonymous key

### Optional (Configuration):
- `VITE_ENVIRONMENT` - Environment name (default: `production`)
- `VITE_DEBUG_MODE` - Debug mode (default: `false`)
- `VITE_WHATSAPP_INSTANCE_NAME` - WhatsApp instance (default: `hormonia-instance`)

## How It Works

### 1. Build Time:
- Vite builds static assets with placeholder configs
- Post-build script creates initial config files with build defaults

### 2. Container Startup:
- Docker entrypoint reads Railway environment variables
- Overwrites config files with actual runtime values
- Nginx serves the updated files

### 3. Frontend Load:
- Browser loads `index.html`
- Loads `/config.js` which attempts to fetch `/api/config`
- Runtime config is merged into `window.__ENV_CONFIG__`
- Application uses runtime configuration

## Debugging

### Check if config files exist in container:
```bash
railway run bash
ls -la /usr/share/nginx/html/api/
cat /usr/share/nginx/html/api/config
```

### Check nginx is serving config:
```bash
curl http://localhost:3000/api/config
curl http://localhost:3000/api/config.js
```

### Check browser console:
```javascript
console.log(window.__ENV_CONFIG__)
```

## Success Criteria

✅ Build completes without errors
✅ Config files created in dist/api/
✅ Container logs show "Runtime configuration generated successfully"
✅ `/api/config` endpoint returns JSON with Railway env vars
✅ `/api/config.js` endpoint returns JavaScript with config
✅ Frontend loads without infinite loading
✅ Frontend can connect to backend API

## Rollback Plan

If issues occur:
1. Check Railway deployment logs
2. Verify environment variables are set correctly
3. Test config endpoints manually
4. Check browser console for errors
5. Review nginx logs: `railway logs --service frontend`

## Next Steps

1. Deploy to Railway and monitor logs
2. Verify config endpoints are accessible
3. Test frontend loading
4. Validate backend connectivity
5. Monitor for any runtime errors

## Related Documentation
- [Railway DNS Configuration](./RAILWAY_DNS_INDEX.md)
- [Railway Backend Connection](../RAILWAY_BACKEND_CONNECTION.md)
- [Railway Environment Variables](../RAILWAY_ENV_VARS.md)
