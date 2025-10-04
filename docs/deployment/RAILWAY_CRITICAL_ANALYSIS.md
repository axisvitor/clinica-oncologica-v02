# 🚨 RAILWAY DEPLOYMENT CRITICAL ANALYSIS - Backend 404 & Missing Frontend Config

**Research Date:** 2025-10-04
**Status:** CRITICAL - Production System Down
**Impact:** Backend unreachable (404), Frontend runtime config missing

---

## 📊 EXECUTIVE SUMMARY

### Problems Identified:
1. **Backend 404 Error** - Backend service returning 404 on all routes
2. **Frontend Runtime Config Missing** - `/api/config` and `/api/config.js` not being served
3. **Build Script Mismatch** - Railway may not be executing the correct build command

### Root Causes:
1. Backend's `railway.json` specifies `DOCKERFILE` builder but healthcheck expects `/health` endpoint
2. Frontend's `dist/api/` directory is not being created during Railway build
3. Railway configuration conflicts between `railway.json` and `railway.toml`

---

## 🔍 DETAILED ANALYSIS

### 1. BACKEND CONFIGURATION ISSUES

#### **Current Configuration:**
- **Railway Config:** `backend-hormonia/railway.json`
  ```json
  {
    "build": { "builder": "DOCKERFILE" },
    "deploy": {
      "healthcheckPath": "/health",
      "healthcheckTimeout": 120
    }
  }
  ```

- **Dockerfile:** Uses Python 3.13, Gunicorn with Uvicorn workers
  ```dockerfile
  CMD gunicorn app.main:app \
      --workers 4 \
      --worker-class uvicorn.workers.UvicornWorker \
      --bind 0.0.0.0:${PORT:-8000}
  ```

- **Main Application:** `backend-hormonia/app/main.py`
  - Uses application factory pattern
  - Has `/test` endpoint but unclear if `/health` exists

#### **Issues Found:**

**❌ Issue #1: Missing `/health` Endpoint**
- Railway healthcheck expects `/health` endpoint
- Main app only shows `/test` endpoint
- Need to verify if `/health` is registered by the application factory

**❌ Issue #2: Package.json Missing Scripts**
- Backend `package.json` only has 3 dependencies
- No build scripts defined
- Railway might be confused about build process

**❌ Issue #3: Railway Root Path Configuration**
- Backend might be mounting at `/` instead of expected path
- Frontend expects backend at specific URLs via environment variables

---

### 2. FRONTEND CONFIGURATION ISSUES

#### **Current Configuration:**

**Frontend Build Process:**
```json
"scripts": {
  "build:railway": "npm ci --prefer-offline && npm run build:runtime",
  "build:runtime": "tsc && vite build --mode production && npm run post-build:runtime",
  "post-build:runtime": "node scripts/post-build-config.js"
}
```

**Railway Configuration Conflict:**
- **railway.json:** Specifies `"builder": "DOCKERFILE"`
- **railway.toml:** Specifies `builder = "nixpacks"` and `buildCommand = "npm run build:runtime"`

#### **Issues Found:**

**❌ Issue #1: Configuration File Conflict**
- Railway.app prioritizes `railway.json` over `railway.toml`
- `railway.json` uses DOCKERFILE (doesn't run `npm run build:runtime`)
- `railway.toml` uses nixpacks (would run `npm run build:runtime`)
- **CONFLICT:** Railway is using Dockerfile, skipping post-build script!

**❌ Issue #2: Post-Build Script Not Executed**
- `post-build-config.js` creates `dist/api/config.js` and `dist/api/config`
- When using Dockerfile builder, npm scripts are bypassed
- Dockerfile stage runs `npm run build:runtime` but in builder stage
- Runtime config files are created but NOT copied to final nginx stage

**❌ Issue #3: Dockerfile Doesn't Copy Config Files**
```dockerfile
# Stage 2: Builder runs build:runtime
RUN npm run build:runtime

# Stage 3: Production - ONLY copies dist folder
COPY --from=builder /app/dist /usr/share/nginx/html
```
- The `dist/api/` directory IS created by post-build script
- But verification shows it's not present locally
- This means the script either failed or wasn't run

**❌ Issue #4: Runtime Config Generation Location**
- `docker-entrypoint.sh` generates `/usr/share/nginx/html/api/config` at runtime
- But build process should have already created these files
- Double configuration generation could cause conflicts

---

### 3. CONFIGURATION FILES ANALYSIS

#### **Files That Should Exist After Build:**

**Expected in `dist/` directory:**
```
dist/
├── index.html (with injected <script src="/config.js">)
├── api/
│   ├── config          # JSON endpoint (static build-time values)
│   ├── config.js       # JavaScript version (for <script> loading)
│   └── config-railway.js  # Railway-specific config
└── assets/
    └── (compiled JS/CSS)
```

**Current Status:**
```bash
# Check shows: "dist/api directory not found"
```

#### **Public Directory Files:**
```
frontend-hormonia/public/api/config.js  ✅ EXISTS
  - Contains BACKEND_URL_PLACEHOLDER
  - Should be copied to dist/api/ during build
```

---

## 🎯 ROOT CAUSE IDENTIFICATION

### **PRIMARY ROOT CAUSE: Railway.json vs Railway.toml Conflict**

Railway.app's priority order:
1. ✅ `railway.json` (if exists) - **CURRENTLY USED**
2. `railway.toml` (if no railway.json)
3. Nixpacks auto-detection

**Current State:**
- `frontend-hormonia/railway.json` specifies `"builder": "DOCKERFILE"`
- `frontend-hormonia/railway.toml` specifies `builder = "nixpacks"` with `buildCommand = "npm run build:runtime"`
- **Railway uses railway.json**, so Dockerfile is used
- **Dockerfile runs build:runtime** in builder stage
- **But post-build files not verified** to be in final image

### **SECONDARY ROOT CAUSE: Backend Health Endpoint**

**Backend Main App Analysis:**
- Uses `create_application()` factory
- Has `/test` endpoint
- Healthcheck expects `/health`
- Need to verify if application factory registers `/health`

---

## ✅ SOLUTIONS

### **Solution 1: Fix Frontend Config Generation (IMMEDIATE)**

**Option A: Remove railway.json (Use railway.toml with Nixpacks)**
```bash
# Remove conflicting railway.json
rm frontend-hormonia/railway.json

# Railway will use railway.toml:
# - builder = "nixpacks"
# - buildCommand = "npm run build:runtime"
# - This WILL run post-build-config.js
```

**Option B: Update Dockerfile to Verify Config Files**
```dockerfile
# In builder stage, after build:runtime
RUN npm run build:runtime && \
    echo "🔍 Verifying config files..." && \
    ls -la dist/api/ && \
    cat dist/api/config.js && \
    test -f dist/api/config || (echo "❌ Config file missing!" && exit 1)

# In production stage, verify files were copied
RUN ls -la /usr/share/nginx/html/api/ && \
    test -f /usr/share/nginx/html/api/config || \
    echo "⚠️ Config file not found in final image!"
```

**Option C: Simplify Entrypoint Config Generation**
- Keep docker-entrypoint.sh's runtime config generation
- Remove build-time config generation from post-build-config.js
- This is actually the current intended approach!

### **Solution 2: Fix Backend 404 Error**

**Step 1: Verify /health Endpoint Exists**
```bash
# Check application factory router registration
grep -r "health" backend-hormonia/app/core/
grep -r "@app.get.*health" backend-hormonia/app/
```

**Step 2: Add Health Endpoint if Missing**
```python
# In backend-hormonia/app/main.py
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "mode": deployment_mode,
        "timestamp": datetime.utcnow().isoformat()
    }
```

**Step 3: Verify Backend Environment Variables**
- Check Railway dashboard for correct env vars
- Ensure PORT is set (Railway provides this)
- Verify SUPABASE_URL and other required vars

### **Solution 3: Fix Frontend-Backend Communication**

**Environment Variables Required in Railway:**

**Frontend Service:**
```bash
VITE_API_URL=https://backend-service.railway.app/api/v1
VITE_API_BASE_URL=https://backend-service.railway.app
VITE_WS_BASE_URL=wss://backend-service.railway.app/ws
```

**Backend Service:**
```bash
PORT=8000  # Railway sets this automatically
SUPABASE_URL=<your-supabase-url>
SUPABASE_KEY=<your-supabase-key>
# ... other required env vars
```

---

## 🔧 IMMEDIATE ACTION PLAN

### **Step 1: Fix Frontend Runtime Config (Choose One)**

**Recommended: Remove railway.json, use Nixpacks**
```bash
# This ensures post-build-config.js runs
rm frontend-hormonia/railway.json
git add frontend-hormonia/railway.json
git commit -m "fix: remove railway.json to use nixpacks builder"
git push
```

### **Step 2: Verify Backend Health Endpoint**
```bash
# Search for health endpoint
grep -r "\/health" backend-hormonia/app/

# If not found, add to main.py or router
```

### **Step 3: Update Railway Environment Variables**
1. Go to Railway dashboard
2. Frontend service → Variables → Add:
   - `VITE_API_URL` = https://[backend-service-name].railway.app/api/v1
   - `VITE_API_BASE_URL` = https://[backend-service-name].railway.app
3. Backend service → Verify all required vars are set

### **Step 4: Redeploy Both Services**
```bash
# Trigger redeployment
git push

# Or in Railway dashboard:
# - Backend service → Deployments → Redeploy
# - Frontend service → Deployments → Redeploy
```

---

## 📋 VERIFICATION CHECKLIST

### **Frontend Checks:**
- [ ] `railway.json` removed OR Dockerfile verifies config files
- [ ] Build logs show "✓ Created static config.js endpoint"
- [ ] `/api/config` returns valid JSON
- [ ] `/api/config.js` returns valid JavaScript
- [ ] `index.html` includes `<script src="/config.js">`

### **Backend Checks:**
- [ ] `/health` endpoint returns 200 OK
- [ ] `/test` endpoint returns 200 OK
- [ ] `/api/v1/docs` (Swagger) loads correctly
- [ ] Logs show "Application startup complete"
- [ ] No errors in Railway logs

### **Integration Checks:**
- [ ] Frontend can reach backend `/health`
- [ ] Frontend config shows correct backend URL
- [ ] Browser console shows no CORS errors
- [ ] API calls from frontend succeed

---

## 📁 CRITICAL FILES REFERENCE

### **Frontend:**
- `c:\Meu Projetos\clinica-oncologica-v02\frontend-hormonia\railway.json` - **REMOVE THIS**
- `c:\Meu Projetos\clinica-oncologica-v02\frontend-hormonia\railway.toml` - Keep
- `c:\Meu Projetos\clinica-oncologica-v02\frontend-hormonia\Dockerfile` - Verify config files
- `c:\Meu Projetos\clinica-oncologica-v02\frontend-hormonia\docker-entrypoint.sh` - Runtime config
- `c:\Meu Projetos\clinica-oncologica-v02\frontend-hormonia\scripts\post-build-config.js` - Build config
- `c:\Meu Projetos\clinica-oncologica-v02\frontend-hormonia\package.json` - Build scripts

### **Backend:**
- `c:\Meu Projetos\clinica-oncologica-v02\backend-hormonia\railway.json` - Config
- `c:\Meu Projetos\clinica-oncologica-v02\backend-hormonia\Dockerfile` - Build process
- `c:\Meu Projetos\clinica-oncologica-v02\backend-hormonia\app\main.py` - Entry point
- `c:\Meu Projetos\clinica-oncologica-v02\backend-hormonia\app\core\application_factory.py` - Router setup

---

## 🎓 LESSONS LEARNED

1. **Railway configuration priority:** `railway.json` > `railway.toml` > auto-detection
2. **Multi-stage Dockerfile:** Files created in builder stage must be explicitly copied to final stage
3. **Runtime vs Build-time config:** Decide which approach and stick to one
4. **Health endpoints:** Always verify healthcheck endpoints exist before deployment

---

## 📞 NEXT STEPS

1. **Immediate:** Remove `frontend-hormonia/railway.json` to fix config generation
2. **High Priority:** Verify backend `/health` endpoint exists
3. **High Priority:** Check Railway env vars are correctly set
4. **Medium Priority:** Add verification steps to Dockerfile
5. **Low Priority:** Consider consolidating config generation strategy

---

**Report Generated by:** Research Agent (Claude-Flow SPARC)
**Coordination Hooks:** Used for real-time team synchronization
**Memory Storage:** Findings stored in `.swarm/memory.db`
