# Complete Railway Deployment Guide - Clínica Hormonia

**Version:** 2.0.0
**Last Updated:** 2025-10-04
**Difficulty:** ⭐⭐ Intermediate

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Backend Deployment](#backend-deployment)
4. [Frontend Deployment](#frontend-deployment)
5. [Environment Variables Reference](#environment-variables-reference)
6. [Verification & Testing](#verification-testing)
7. [Troubleshooting](#troubleshooting)
8. [Maintenance & Updates](#maintenance-updates)

---

## Prerequisites

### Required Accounts & Services

#### 1. Railway Account
- Sign up at [railway.app](https://railway.app)
- Add payment method (required for production deployments)
- Install Railway CLI (optional but recommended):
  ```bash
  npm install -g @railway/cli
  railway login
  ```

#### 2. GitHub Repository
- Fork or have access to the codebase repository
- Ensure you have admin/write permissions
- Railway will need read access to your repository

#### 3. Supabase Project
- Create project at [supabase.com](https://supabase.com)
- Navigate to: **Project Settings** → **API**
- Copy these values:
  - Project URL (e.g., `https://xxxxx.supabase.co`)
  - `anon` public key
  - `service_role` secret key
- Navigate to: **Project Settings** → **Database**
  - Copy PostgreSQL connection string
  - Switch to **Connection pooling** tab
  - Copy pooled connection string (uses port 6543)

#### 4. Firebase Project (Optional)
- Create project at [console.firebase.google.com](https://console.firebase.google.com)
- Enable Authentication → Email/Password
- Go to **Project Settings** → **Service Accounts**
- Click **Generate new private key** (for backend)
- Go to **Project Settings** → **General** (for frontend config)
- Copy Firebase config object values

#### 5. Redis Instance
- **Option A:** Railway Redis Plugin (Recommended)
  - Add Redis to your Railway project
  - Connection details auto-configured

- **Option B:** Redis Cloud ([redis.com](https://redis.com))
  - Create free database (30MB)
  - Enable SSL/TLS
  - Copy connection string

### Local Development Setup (Recommended)

Test the deployment configuration locally first:

```bash
# Clone repository
git clone https://github.com/your-org/clinica-oncologica-v02.git
cd clinica-oncologica-v02

# Backend setup
cd backend-hormonia
cp .env.example .env
# Edit .env with your credentials
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend setup
cd ../frontend-hormonia
cp .env.example .env
# Edit .env with your credentials
npm install
npm run dev

# Test with Docker Compose
cd ..
docker-compose up
```

**Verification:**
- Backend health: `http://localhost:8000/api/v1/health`
- Frontend: `http://localhost:3000`

---

## Architecture Overview

### Service Communication

```
┌─────────────────────────────────────────────────────────┐
│                    Railway Platform                      │
│                                                          │
│  ┌──────────────┐                    ┌────────────────┐ │
│  │   Frontend   │                    │    Backend     │ │
│  │   (Nginx)    │                    │  (FastAPI)     │ │
│  │   Port: 3000 │◄───────────────────│   Port: 8000   │ │
│  └──────────────┘  Private Network   └────────────────┘ │
│        │           [service].railway.internal    │       │
│        │                                         │       │
│        ▼                                         ▼       │
│  ┌──────────────────────────────────────────────────┐   │
│  │            Railway Redis Plugin                   │   │
│  │               Port: 6379                          │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
└──────────────────────────────────────────────────────────┘
                           │
                           ▼
         ┌──────────────────────────────────────┐
         │     External Services (Cloud)        │
         │                                      │
         │  • Supabase (PostgreSQL + Storage)   │
         │  • Firebase (Authentication)         │
         └──────────────────────────────────────┘
```

### Technology Stack

**Backend:**
- Python 3.13
- FastAPI + Uvicorn + Gunicorn
- SQLAlchemy + Alembic
- Redis (sessions, cache)
- psycopg 3.0+ (PostgreSQL driver)

**Frontend:**
- React 19 + TypeScript
- Vite 6.0
- Nginx (reverse proxy)
- Runtime configuration support

---

## Backend Deployment

### Step 1: Create Railway Service

1. Go to [railway.app/new](https://railway.app/new)
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your repository
4. Railway will detect the backend automatically
5. Name the service: `backend-hormonia` or `api`

### Step 2: Configure Build Settings

Railway should auto-detect Python, but verify:

**Settings** → **Build**:
- **Root Directory:** `backend-hormonia`
- **Build Command:** (auto-detected)
- **Start Command:** `gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`

**Dockerfile Detection:**
If Railway detects `backend-hormonia/Dockerfile`, use Docker build:
- Enable **"Use Dockerfile"**
- Dockerfile path: `backend-hormonia/Dockerfile`

### Step 3: Set Environment Variables

**Settings** → **Variables** → Add all variables:

```bash
# ============================================
# CRITICAL SECURITY KEYS (GENERATE NEW!)
# ============================================
# Generate using: python -c "import secrets; print(secrets.token_urlsafe(64))"
SECRET_KEY=<64-char-random-string>
JWT_SECRET_KEY=<64-char-random-string>
ENCRYPTION_KEY=<64-char-random-string>

# ============================================
# APPLICATION CONFIG
# ============================================
ENVIRONMENT=production
DEBUG=false
PORT=8000
HOST=0.0.0.0
BCRYPT_ROUNDS=12

# ============================================
# SUPABASE DATABASE
# ============================================
# From: Supabase Dashboard → Settings → Database → Connection Pooling
DATABASE_URL=postgresql+psycopg://postgres:[password]@[host].supabase.co:6543/postgres
SUPABASE_URL=https://[project-id].supabase.co
SUPABASE_ANON_KEY=eyJhbGc...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGc...

# Database Pool Settings
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=40
DB_POOL_TIMEOUT=20
DB_STATEMENT_TIMEOUT=30000
DB_POOL_RECYCLE=3600

# ============================================
# REDIS (Railway Plugin Recommended)
# ============================================
# Option A: Railway Redis Plugin (auto-configured)
ENABLE_REDIS=true
REDIS_URL=${{Redis.REDIS_URL}}
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required
REDIS_MAX_CONNECTIONS=25

# Option B: Redis Cloud (manual)
# REDIS_URL=rediss://default:[password]@[host]:6379/1
# REDIS_PASSWORD=[your-password]
# REDIS_HOST=[your-host]
# REDIS_PORT=6379
# REDIS_SSL=true

# ============================================
# FIREBASE ADMIN (Optional)
# ============================================
# From: Firebase Console → Project Settings → Service Accounts
FIREBASE_ADMIN_PROJECT_ID=your-project-id
FIREBASE_ADMIN_CLIENT_EMAIL=firebase-adminsdk-xxxxx@your-project.iam.gserviceaccount.com
FIREBASE_ADMIN_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\nYour_Key_Here\n-----END PRIVATE KEY-----

# Firebase Security
FIREBASE_ALLOWED_DOMAINS=["oncologia.com","yourdomain.com"]
FIREBASE_BLOCK_PUBLIC_DOMAINS=true
FIREBASE_REQUIRE_CUSTOM_CLAIMS=true

# ============================================
# CORS CONFIGURATION
# ============================================
# Add frontend Railway URL after it's deployed
CORS_ORIGINS=https://your-frontend.up.railway.app,https://yourdomain.com

# ============================================
# OPTIONAL FEATURES
# ============================================
ENABLE_SWAGGER_UI=true
ENABLE_REDOC=true
ENABLE_MONITORING=true
```

### Step 4: Add Redis Plugin (Recommended)

1. In your Railway project, click **"New"** → **"Database"** → **"Add Redis"**
2. Railway creates a Redis service with:
   - Auto-generated password
   - TLS/SSL enabled
   - Private networking configured
3. In backend variables, reference Redis:
   ```bash
   REDIS_URL=${{Redis.REDIS_URL}}
   ```

### Step 5: Deploy Backend

1. Click **"Deploy"** or push to GitHub (auto-deploy)
2. Monitor deployment logs:
   - Look for: `"Uvicorn running on http://0.0.0.0:8000"`
   - Check for errors in red text
3. Deployment time: ~3-5 minutes

### Step 6: Verify Backend Health

1. Copy the Railway public URL (e.g., `https://backend-hormonia-production.up.railway.app`)
2. Test health endpoint:
   ```bash
   curl https://[your-backend-url]/api/v1/health
   ```

   **Expected response:**
   ```json
   {
     "status": "healthy",
     "version": "2.0.0",
     "database": "connected",
     "redis": "connected"
   }
   ```

3. Test API docs (if enabled):
   - Swagger UI: `https://[backend-url]/docs`
   - ReDoc: `https://[backend-url]/redoc`

---

## Frontend Deployment

### Step 1: Create Frontend Service

1. In the same Railway project, click **"New"** → **"GitHub Repo"**
2. Select your repository (same as backend)
3. Railway should detect `frontend-hormonia` folder
4. Name the service: `frontend-hormonia`

### Step 2: Configure Build Settings

**Settings** → **Build**:
- **Root Directory:** `frontend-hormonia`
- **Builder:** Nixpacks (or Dockerfile if detected)
- **Build Command:** `npm run build:runtime`
- **Start Command:** `npm run preview`

**If using Dockerfile:**
- Railway auto-detects `frontend-hormonia/Dockerfile`
- No need to change build commands

### Step 3: Set Environment Variables

**Settings** → **Variables**:

```bash
# ============================================
# RAILWAY CONFIGURATION
# ============================================
NODE_ENV=production
PORT=3000

# ============================================
# BACKEND CONNECTION (CRITICAL!)
# ============================================
# Use Railway Private Networking
# Format: [backend-service-name].railway.internal
BACKEND_HOST=backend-hormonia.railway.internal
BACKEND_PORT=8000

# Alternative: Public URL (not recommended)
# BACKEND_HOST=backend-hormonia-production.up.railway.app
# BACKEND_PORT=443

# ============================================
# SUPABASE (BUILD-TIME)
# ============================================
# From: Supabase Dashboard → Settings → API
VITE_SUPABASE_URL=https://[project-id].supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGc...
VITE_SUPABASE_AUTH_ENABLED=true
VITE_SUPABASE_REALTIME_ENABLED=true

# ============================================
# API ENDPOINTS (BUILD-TIME)
# ============================================
# These use nginx proxy (internal communication)
VITE_API_URL=/api
VITE_API_BASE_PATH=/api/v1
VITE_API_TIMEOUT=30000
VITE_WS_URL=/ws

# ============================================
# FIREBASE CLIENT (RUNTIME - Optional)
# ============================================
# From: Firebase Console → Project Settings → General
# These are loaded at runtime via /api/config
VITE_FIREBASE_API_KEY=AIza...
VITE_FIREBASE_AUTH_DOMAIN=your-app.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-app.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789
VITE_FIREBASE_APP_ID=1:123:web:abc
VITE_FIREBASE_MEASUREMENT_ID=G-XXXXXXXXXX

# ============================================
# APPLICATION SETTINGS
# ============================================
VITE_ENVIRONMENT=production
VITE_DEBUG_MODE=false
VITE_USE_MOCK_AUTH=false
VITE_ENABLE_WHATSAPP_INTEGRATION=true
VITE_ENABLE_AI_CHAT=true

# ============================================
# OPTIONAL FEATURES
# ============================================
VITE_ENABLE_DARK_MODE=true
VITE_ENABLE_PERFORMANCE_MONITORING=true
VITE_ENABLE_ERROR_REPORTING=true
```

### Step 4: Configure Service Reference (Alternative)

Railway can auto-generate backend URLs using Service References:

1. **Variables** → **"+ New Variable"** → **"Service Reference"**
2. Select: `backend-hormonia`
3. Railway creates variables like:
   - `BACKEND_URL` (full URL)
   - `BACKEND_HOST` (hostname only)
   - `BACKEND_PORT` (port number)

Then update `docker-entrypoint.sh` to use these (if needed).

### Step 5: Deploy Frontend

1. Click **"Deploy"** or push to GitHub
2. Monitor logs for:
   ```
   🔗 Backend configuration (with defaults applied):
      BACKEND_HOST=backend-hormonia.railway.internal
      BACKEND_PORT=8000
   ✅ nginx.conf created successfully
   ```
3. Deployment time: ~2-4 minutes

### Step 6: Configure Custom Domain (Optional)

1. **Settings** → **Networking** → **Custom Domain**
2. Add your domain: `app.yourdomain.com`
3. Update DNS records at your registrar:
   ```
   CNAME app.yourdomain.com → [railway-domain].up.railway.app
   ```
4. Wait for SSL certificate provisioning (~5 minutes)

### Step 7: Update Backend CORS

After frontend deployment, update backend CORS:

1. Go to **backend-hormonia** service → **Variables**
2. Update `CORS_ORIGINS`:
   ```bash
   CORS_ORIGINS=https://[frontend-railway-url].up.railway.app,https://app.yourdomain.com
   ```
3. Redeploy backend (Railway auto-redeploys on variable change)

---

## Environment Variables Reference

### Backend Critical Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `SECRET_KEY` | ✅ Yes | JWT signing key | `secrets.token_urlsafe(64)` |
| `DATABASE_URL` | ✅ Yes | PostgreSQL connection | `postgresql+psycopg://...` |
| `REDIS_URL` | ✅ Yes | Redis connection | `rediss://...` or `${{Redis.REDIS_URL}}` |
| `SUPABASE_URL` | ✅ Yes | Supabase project URL | `https://xxx.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ Yes | Supabase admin key | `eyJhbGc...` |
| `FIREBASE_ADMIN_PROJECT_ID` | ❌ Optional | Firebase project ID | `your-app-12345` |
| `CORS_ORIGINS` | ✅ Yes | Allowed origins | `https://app.domain.com` |

### Frontend Critical Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `BACKEND_HOST` | ✅ Yes | Backend hostname | `backend.railway.internal` |
| `BACKEND_PORT` | ✅ Yes | Backend port | `8000` |
| `VITE_SUPABASE_URL` | ✅ Yes | Supabase URL (build) | `https://xxx.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | ✅ Yes | Supabase public key | `eyJhbGc...` |
| `VITE_FIREBASE_API_KEY` | ❌ Optional | Firebase API key (runtime) | `AIza...` |
| `VITE_ENVIRONMENT` | ✅ Yes | Environment name | `production` |

### Security Best Practices

1. **Never commit secrets to Git:**
   - Use Railway's variable management
   - Rotate keys regularly
   - Use different keys per environment

2. **Generate strong keys:**
   ```python
   # Python
   import secrets
   print(secrets.token_urlsafe(64))
   ```
   ```bash
   # Bash
   openssl rand -base64 64 | tr -d '\n'
   ```

3. **Validate placeholders:**
   - Never use `CHANGE_THIS` or `YOUR_KEY_HERE`
   - Backend validates and rejects placeholder values

4. **Use Railway's Secret Variables:**
   - Mark sensitive vars as "Secret" (hidden in logs)
   - Use environment-specific configurations

---

## Verification & Testing

### Health Check Checklist

#### Backend Verification

```bash
# 1. Health endpoint
curl https://[backend-url]/api/v1/health

# Expected: {"status": "healthy", "database": "connected", "redis": "connected"}

# 2. API documentation (if enabled)
curl https://[backend-url]/docs
# Should return HTML (Swagger UI)

# 3. Test authentication endpoint
curl -X POST https://[backend-url]/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'

# 4. Check Redis connection
# In Railway Logs, search for: "Redis connection: ✓ Connected"
```

#### Frontend Verification

```bash
# 1. Root health check
curl https://[frontend-url]/health
# Expected: "healthy"

# 2. Static assets
curl -I https://[frontend-url]/assets/index-[hash].js
# Expected: 200 OK with Cache-Control headers

# 3. Runtime config
curl https://[frontend-url]/api/config
# Expected: JSON with Firebase config (if configured)

# 4. API proxy (internal to backend)
curl https://[frontend-url]/api/v1/health
# Should proxy to backend and return health status
```

### Browser Testing

1. **Open Frontend URL:**
   - Should load without infinite loading screen
   - Check browser console for errors

2. **Test Authentication:**
   - Try logging in
   - Verify token storage (Developer Tools → Application → Local Storage)

3. **Test API Communication:**
   - Network tab should show `/api/*` requests
   - Verify responses are 200 OK (not 502/504)

4. **WebSocket Connection:**
   - Open Network tab → WS filter
   - Should see WebSocket connection to `/ws`

### Automated Verification Script

Create `scripts/verify-deployment.sh`:

```bash
#!/bin/bash

BACKEND_URL="https://your-backend.up.railway.app"
FRONTEND_URL="https://your-frontend.up.railway.app"

echo "🔍 Verifying Railway Deployment..."

# Backend health
echo -n "✓ Backend health: "
curl -sf "$BACKEND_URL/api/v1/health" | jq -r '.status' || echo "❌ FAILED"

# Frontend health
echo -n "✓ Frontend health: "
curl -sf "$FRONTEND_URL/health" || echo "❌ FAILED"

# API proxy
echo -n "✓ Frontend → Backend proxy: "
curl -sf "$FRONTEND_URL/api/v1/health" | jq -r '.status' || echo "❌ FAILED"

# Runtime config
echo -n "✓ Runtime config: "
curl -sf "$FRONTEND_URL/api/config" | jq -r '.apiUrl' || echo "❌ FAILED"

echo "✅ Verification complete!"
```

### Final Deployment Checklist

- [ ] Backend deployed and active (green checkmark in Railway)
- [ ] Frontend deployed and active (green checkmark in Railway)
- [ ] Backend health check returns 200 OK
- [ ] Frontend loads without errors
- [ ] API proxy works (frontend → backend communication)
- [ ] Authentication flow works (login/logout)
- [ ] Database operations work (create/read/update)
- [ ] WebSocket connection established (if applicable)
- [ ] Custom domain configured (if applicable)
- [ ] SSL certificates valid (no browser warnings)
- [ ] CORS configured correctly (no CORS errors)
- [ ] Environment variables validated (no placeholders)
- [ ] Logs show no critical errors
- [ ] Performance acceptable (load time < 3s)

---

## Troubleshooting

### Common Errors & Solutions

#### 1. Backend: 503 Service Unavailable

**Symptoms:**
- Backend doesn't start
- Health check fails
- Logs show startup errors

**Possible Causes:**

**A. Missing Environment Variables**
```bash
# Check logs for:
"Environment variable SECRET_KEY is required"
"Database connection failed"

# Solution:
# Verify all critical variables are set in Railway dashboard
```

**B. Database Connection Error**
```bash
# Logs show:
"Could not connect to PostgreSQL"
"SSL connection error"

# Solution:
# Ensure DATABASE_URL uses correct format:
DATABASE_URL=postgresql+psycopg://postgres:[password]@[host].supabase.co:6543/postgres
# Note: Port 6543 for connection pooling, psycopg (not psycopg2)
```

**C. Redis Connection Failed**
```bash
# Logs show:
"Redis connection failed"
"AuthService requires Redis"

# Solution Option 1: Railway Redis Plugin
# Add Redis plugin to project
REDIS_URL=${{Redis.REDIS_URL}}

# Solution Option 2: Redis Cloud
REDIS_URL=rediss://default:[password]@[host]:6379/1
REDIS_SSL=true
```

#### 2. Frontend: Infinite Loading Screen

**Symptoms:**
- Frontend shows loading spinner forever
- No content appears

**Possible Causes:**

**A. Configuration Not Loading**
```bash
# Check browser console for:
"Supabase configuration validation failed"
"Cannot read property 'VITE_SUPABASE_URL'"

# Solution:
# Ensure Vite variables are set BEFORE build:
VITE_SUPABASE_URL=https://[project].supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGc...

# Redeploy after setting variables
```

**B. Firebase Configuration Error**
```bash
# Console shows:
"Firebase configuration is incomplete"

# Solution Option 1: Configure Firebase fully
VITE_FIREBASE_API_KEY=AIza...
# (all 7 Firebase variables)

# Solution Option 2: Use Mock Auth
VITE_USE_MOCK_AUTH=true
# System falls back to mock authentication
```

#### 3. Frontend: DNS Error - "host not found in upstream"

**Symptoms:**
```bash
nginx: [emerg] host not found in upstream "backend:8000"
```

**Solution:**
```bash
# Ensure BACKEND_HOST uses Railway internal networking:
BACKEND_HOST=backend-hormonia.railway.internal
BACKEND_PORT=8000

# NOT just "backend" or "localhost"
# Format: [service-name].railway.internal
```

**How to find service name:**
1. Railway Dashboard → Backend Service
2. Look at service name (top left)
3. Use exactly: `[service-name].railway.internal`

#### 4. CORS Error

**Symptoms:**
```bash
# Browser console:
Access to fetch at 'https://backend.../api/v1/...' from origin 'https://frontend...'
has been blocked by CORS policy
```

**Solution:**
```bash
# Backend service → Variables:
CORS_ORIGINS=https://frontend-hormonia-production.up.railway.app,https://yourdomain.com

# Important:
# - Include full HTTPS URL
# - No trailing slash
# - Comma-separated for multiple domains
# - Update after domain changes
```

#### 5. Build Fails

**Symptoms:**
- Deployment stuck on "Building..."
- Build logs show errors

**Common Issues:**

**A. Missing Dependencies**
```bash
# Backend logs:
"ModuleNotFoundError: No module named 'fastapi'"

# Solution: Ensure requirements.txt is complete
# Railway should auto-install from requirements.txt
```

**B. Frontend Build Errors**
```bash
# Logs:
"Module not found: Can't resolve '@/components/...'"

# Solution: Check tsconfig.json paths
# Ensure all imports are correct
```

**C. Out of Memory**
```bash
# Logs:
"JavaScript heap out of memory"

# Solution:
# Increase Node memory in build command:
# Settings → Build Command:
NODE_OPTIONS="--max-old-space-size=4096" npm run build:runtime
```

#### 6. High Latency / Slow Response

**Symptoms:**
- API calls take > 5 seconds
- Frontend feels sluggish

**Solutions:**

**A. Enable Connection Pooling**
```bash
# Backend variables:
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=40
DB_POOL_RECYCLE=3600
```

**B. Use Private Networking**
```bash
# Frontend variables:
BACKEND_HOST=backend.railway.internal  # NOT public URL
BACKEND_PORT=8000
```

**C. Enable Redis Caching**
```bash
# Backend variables:
ENABLE_REDIS=true
REDIS_MAX_CONNECTIONS=25
```

**D. Optimize Database Queries**
- Add indexes to frequently queried columns
- Use database connection pooling (port 6543)
- Enable query result caching

### Debug Commands

#### Railway CLI Debugging

```bash
# Install Railway CLI
npm install -g @railway/cli
railway login

# Link to project
railway link

# View logs (real-time)
railway logs

# View specific service logs
railway logs --service backend-hormonia

# SSH into container
railway shell

# Test environment variables
railway run printenv

# Run local command with Railway env vars
railway run python manage.py check
```

#### Container Debugging

```bash
# Access Railway Shell (in dashboard)
# Frontend container:
whoami                    # Should be: nginx
ls -la /etc/nginx/        # Check nginx config
cat /etc/nginx/nginx.conf # View processed config
curl localhost:3000/health # Test local health

# Backend container:
python -c "from app.config import settings; print(settings.DATABASE_URL[:50])"
python -m app.core.database_check  # Test DB connection
redis-cli -u "$REDIS_URL" ping     # Test Redis
```

#### Network Testing

```bash
# From frontend container, test backend connectivity:
nslookup backend-hormonia.railway.internal
curl http://backend-hormonia.railway.internal:8000/api/v1/health

# From backend container, test database:
pg_isready -h [supabase-host] -p 6543

# Test Redis:
redis-cli -u "$REDIS_URL" ping
```

### Log Analysis

**What to look for in logs:**

**Backend Logs:**
```bash
# ✅ Success indicators:
"Uvicorn running on http://0.0.0.0:8000"
"Database connection: ✓ Connected"
"Redis connection: ✓ Connected"
"Application startup complete"

# ❌ Error indicators:
"Environment variable ... is required"
"Could not connect to database"
"Redis connection failed"
"SSL certificate verify failed"
```

**Frontend Logs:**
```bash
# ✅ Success indicators:
"BACKEND_HOST=backend-hormonia.railway.internal"
"✅ nginx.conf created successfully"
"nginx: master process started"

# ❌ Error indicators:
"host not found in upstream"
"Configuration file not found"
"Failed to load environment variables"
```

### Getting Help

1. **Railway Discord:**
   - [discord.gg/railway](https://discord.gg/railway)
   - Active community support
   - Railway team responds quickly

2. **GitHub Issues:**
   - Check existing issues in your repository
   - Create detailed bug reports

3. **Documentation:**
   - [Railway Docs](https://docs.railway.app)
   - [Supabase Docs](https://supabase.com/docs)
   - [FastAPI Docs](https://fastapi.tiangolo.com)

4. **Support Channels:**
   - Railway Support: support@railway.app
   - Include logs, service names, and error messages

---

## Maintenance & Updates

### Updating the Application

#### Via GitHub (Recommended)

Railway auto-deploys when you push to GitHub:

```bash
# Make changes locally
git add .
git commit -m "feat: add new feature"
git push origin main

# Railway automatically:
# 1. Detects push
# 2. Rebuilds services
# 3. Deploys updates
# 4. Runs health checks
```

#### Manual Deployment

1. Railway Dashboard → Service → **Deployments**
2. Click **"Deploy"** on any previous deployment
3. Or click **"Redeploy"** to use latest code

### Rolling Back

1. **Deployments** tab → Find stable deployment
2. Click **"⋯"** menu → **"Redeploy"**
3. Confirm rollback
4. Previous version goes live in ~1-2 minutes

### Monitoring

#### Built-in Metrics

Railway provides:
- **CPU Usage:** Monitor spikes
- **Memory Usage:** Watch for leaks
- **Network Traffic:** Track bandwidth
- **Deployment History:** Audit trail

#### Custom Monitoring (Optional)

Add monitoring service:

```bash
# Backend variables:
VITE_ENABLE_ERROR_REPORTING=true
VITE_SENTRY_DSN=https://[sentry-dsn]
VITE_ANALYTICS_TRACKING_ID=GA-XXXXXXXXX

# Install Sentry (Python)
pip install sentry-sdk[fastapi]

# Install Sentry (JavaScript)
npm install @sentry/react @sentry/vite-plugin
```

### Database Migrations

Railway supports Alembic migrations:

```bash
# Add migration service (optional)
# Settings → Build Command:
alembic upgrade head && gunicorn ...

# Or run manually via Railway CLI:
railway run alembic upgrade head
```

### Backup Strategy

1. **Database Backups:**
   - Supabase auto-backups (Pro plan)
   - Manual exports: Supabase Dashboard → Database → Backups

2. **Environment Variables:**
   - Export from Railway: Settings → Variables → Export
   - Store in secure password manager (not Git!)

3. **Code Versioning:**
   - Use Git tags for releases:
     ```bash
     git tag -a v2.0.0 -m "Production release"
     git push origin v2.0.0
     ```

### Cost Optimization

1. **Use Private Networking:**
   - Saves bandwidth costs
   - Faster than public internet

2. **Optimize Docker Images:**
   - Multi-stage builds (already implemented)
   - Minimize layer count
   - Use Alpine base images

3. **Database Connection Pooling:**
   - Use Supabase pooler (port 6543)
   - Reduces connection overhead

4. **Redis Optimization:**
   - Use Railway Redis plugin (cost-effective)
   - Set appropriate TTL for cache
   - Clean up unused keys

5. **Monitor Usage:**
   - Railway Dashboard → Project → Usage
   - Set up billing alerts
   - Review monthly reports

### Security Updates

1. **Regular Dependency Updates:**
   ```bash
   # Backend
   pip list --outdated
   pip install --upgrade [package]

   # Frontend
   npm outdated
   npm update
   ```

2. **Security Audits:**
   ```bash
   # Backend
   pip-audit

   # Frontend
   npm audit
   npm audit fix
   ```

3. **SSL Certificate Renewal:**
   - Railway auto-renews Let's Encrypt certificates
   - Custom domains: verify DNS records periodically

4. **Rotate Secrets:**
   - Change `SECRET_KEY` and `JWT_SECRET_KEY` every 6 months
   - Update `REDIS_PASSWORD` annually
   - Rotate Firebase service account keys yearly

---

## Quick Reference

### Essential URLs

| Service | URL Pattern | Example |
|---------|-------------|---------|
| Backend API | `https://[service].up.railway.app` | `https://backend-hormonia-production.up.railway.app` |
| Frontend | `https://[service].up.railway.app` | `https://frontend-hormonia-production.up.railway.app` |
| Health Check | `https://[backend]/api/v1/health` | - |
| API Docs | `https://[backend]/docs` | - |
| Custom Domain | `https://app.yourdomain.com` | - |

### Railway CLI Quick Commands

```bash
# Login
railway login

# Link project
railway link

# View logs
railway logs

# Open in browser
railway open

# SSH into container
railway shell

# Run with Railway env vars
railway run [command]

# Deploy
railway up
```

### Useful Snippets

**Test health endpoints:**
```bash
# Backend
curl https://[backend-url]/api/v1/health | jq

# Frontend
curl https://[frontend-url]/health
```

**Check environment variables:**
```bash
# In Railway Shell
printenv | grep VITE_
printenv | grep SUPABASE_
```

**Debug nginx config:**
```bash
# Frontend container
cat /etc/nginx/nginx.conf
nginx -t  # Test config syntax
```

**Test database connection:**
```python
# Backend Python shell
from app.database import engine
with engine.connect() as conn:
    result = conn.execute("SELECT version();")
    print(result.fetchone())
```

---

## Appendix

### A. Dockerfile Reference

**Backend Dockerfile:** `backend-hormonia/Dockerfile`
- Base: `python:3.13-slim`
- Uses gunicorn + uvicorn workers
- Health check on port 8000

**Frontend Dockerfile:** `frontend-hormonia/Dockerfile`
- Multi-stage build (deps → builder → production)
- Base: `node:20-alpine` → `nginx:alpine`
- Runtime config via `docker-entrypoint.sh`

### B. Nginx Configuration

**Template:** `frontend-hormonia/nginx.conf`
- Uses `envsubst` for variable substitution
- Variables: `${BACKEND_HOST}`, `${BACKEND_PORT}`, `${PORT}`
- Proxy: `/api/*` → backend, `/ws` → WebSocket

### C. Health Check Endpoints

**Backend:**
- Path: `/api/v1/health`
- Response: `{"status": "healthy", "database": "connected", "redis": "connected"}`

**Frontend:**
- Path: `/health`
- Response: `healthy` (plain text)

### D. Service Names Convention

Recommended naming:
- Backend: `backend-hormonia`, `api-hormonia`, `server`
- Frontend: `frontend-hormonia`, `web`, `app`
- Redis: `redis` (Railway plugin auto-names)

### E. Railway Region Selection

**Recommended regions:**
- **us-west1:** US West (Oregon) - Default, good latency
- **us-east4:** US East (Virginia) - Close to Supabase US
- **europe-west1:** Europe (Belgium) - EU data residency

**Match with Supabase:**
- If Supabase is in `us-east-1`, use Railway `us-east4`
- Reduces database latency

---

## Conclusion

You've successfully deployed the Clínica Hormonia application to Railway!

**Next Steps:**
1. Set up monitoring and alerts
2. Configure custom domain
3. Run end-to-end tests
4. Train your team on the platform
5. Document any custom configurations

**Support:**
- Railway Discord: [discord.gg/railway](https://discord.gg/railway)
- Documentation: [docs.railway.app](https://docs.railway.app)
- GitHub Issues: Create detailed bug reports

**Feedback:**
If you encounter issues not covered in this guide, please:
1. Document the problem and solution
2. Update this guide for future reference
3. Share with the team

---

**Document Version:** 2.0.0
**Last Updated:** 2025-10-04
**Maintained By:** DevOps Team
**Review Schedule:** Monthly
