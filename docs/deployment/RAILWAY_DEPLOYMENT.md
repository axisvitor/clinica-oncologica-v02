# Railway Deployment Guide

## Overview

This repository is configured for multi-service deployment on Railway using **per-service configuration** (each service has its own `railway.json` in its directory). The setup includes:

- **backend-web**: FastAPI application (gunicorn + uvicorn workers) - `backend-hormonia/railway.json` → `Dockerfile`
- **backend-worker**: Celery worker for async tasks - Create service pointing to `backend-hormonia/` → `Dockerfile.worker`
- **backend-beat**: Celery beat scheduler - Create service pointing to `backend-hormonia/` → `Dockerfile.beat`
- **frontend**: React/Vite SPA with Nginx - `frontend-hormonia/railway.json` → `Dockerfile`
- **quiz**: Next.js application - `quiz-mensal-interface/railway.json` (Nixpacks)

## Prerequisites

1. Railway account and CLI installed
2. PostgreSQL and Redis plugins added to your Railway project
3. Repository connected to Railway

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Railway Project                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ backend-web  │  │backend-worker│  │ backend-beat │      │
│  │ (FastAPI)    │  │   (Celery)   │  │ (Celery Beat)│      │
│  │ Port: 8000   │  └──────────────┘  └──────────────┘      │
│  │ Health: /health                                           │
│  └──────────────┘                                            │
│         ▲                                                     │
│         │                                                     │
│  ┌──────────────┐                    ┌──────────────┐       │
│  │  frontend    │                    │     quiz     │       │
│  │   (Nginx)    │                    │  (Next.js)   │       │
│  │ Port: 3000   │                    │ Port: 3000   │       │
│  │ Health: /health                   Health: /api/health     │
│  └──────────────┘                    └──────────────┘       │
│                                                               │
│  ┌──────────────┐                    ┌──────────────┐       │
│  │  PostgreSQL  │                    │    Redis     │       │
│  │   (Plugin)   │                    │   (Plugin)   │       │
│  └──────────────┘                    └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## Environment Variables Matrix

### 🔧 backend-web (FastAPI)

**Required:**
- `DATABASE_URL`: PostgreSQL connection string with `postgresql+psycopg://` driver
  - Example: `postgresql+psycopg://user:pass@host:5432/dbname`
  - ⚠️ Railway generates `postgresql://` by default - you must change it to `postgresql+psycopg://`
- `REDIS_URL`: Redis connection string
  - Example: `redis://:password@host:6379/0`
- `JWT_SECRET_KEY`: Secret key for JWT token signing

**Recommended:**
- `LOG_LEVEL`: `info` (default), `debug`, `warning`, `error`
- `ALLOWED_ORIGINS`: JSON array or CSV of allowed CORS origins
  - Example: `["https://frontend.up.railway.app","https://quiz.up.railway.app"]`
- `SENTRY_DSN`: Sentry error tracking DSN (if using)
- `GEMINI_API_KEY`: Google Gemini API key (if using)
- `WHATSAPP_API_URL`: WhatsApp API endpoint (if using)
- `WHATSAPP_API_KEY`: WhatsApp API key (if using)

**Pre-configured (in railway.json):**
- `PORT`: `8000`
- `PYTHONUNBUFFERED`: `1`
- `PYTHONDONTWRITEBYTECODE`: `1`
- `PASSLIB_BUILTIN_BCRYPT`: `enabled`

### 🔧 backend-worker (Celery Worker)

**Required:**
- `DATABASE_URL`: Same as backend-web
- `REDIS_URL`: Same as backend-web
- `JWT_SECRET_KEY`: Same as backend-web
- `CELERY_BROKER_URL`: Set to same value as `REDIS_URL`
- `CELERY_RESULT_BACKEND`: Set to same value as `REDIS_URL`

**Recommended:**
- `CELERY_WORKER_CONCURRENCY`: `4` (default)
- `CELERY_WORKER_MAX_TASKS_PER_CHILD`: `1000` (default)

**Pre-configured:**
- `PYTHONUNBUFFERED`: `1`
- `PYTHONDONTWRITEBYTECODE`: `1`
- `PASSLIB_BUILTIN_BCRYPT`: `enabled`
- `LOG_LEVEL`: `info`

### 🔧 backend-beat (Celery Beat)

**Required:**
- `DATABASE_URL`: Same as backend-web
- `REDIS_URL`: Same as backend-web
- `JWT_SECRET_KEY`: Same as backend-web
- `CELERY_BROKER_URL`: Set to same value as `REDIS_URL`
- `CELERY_RESULT_BACKEND`: Set to same value as `REDIS_URL`

**Pre-configured:**
- `PYTHONUNBUFFERED`: `1`
- `PYTHONDONTWRITEBYTECODE`: `1`
- `PASSLIB_BUILTIN_BCRYPT`: `enabled`
- `LOG_LEVEL`: `info`

### 🎨 frontend (React + Nginx)

**Required:**
- `BACKEND_URL`: Public domain of backend-web service
  - Example: `https://backend-web.up.railway.app`
  - This is injected into nginx.conf at runtime for proxying `/api` and `/ws` requests

**Pre-configured:**
- `PORT`: `3000`
- `NODE_ENV`: `production`

**Note:** Build-time variables (`VITE_*`) should be set in Railway if needed:
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_API_URL`
- `VITE_API_BASE_URL`
- `VITE_WS_BASE_URL`

### 📝 quiz (Next.js)

**Required:**
- `NEXT_PUBLIC_API_URL`: Public domain of backend-web service
  - Example: `https://backend-web.up.railway.app`

**Pre-configured:**
- `NODE_ENV`: `production`
- `PORT`: Set automatically by Railway

## Step-by-Step Deployment

### 1. Add Plugins

In your Railway project dashboard:

1. Click "+ New" → "Database" → "Add PostgreSQL"
   - Note the `DATABASE_URL` generated
   - **IMPORTANT**: Change the driver from `postgresql://` to `postgresql+psycopg://`

2. Click "+ New" → "Database" → "Add Redis"
   - Note the `REDIS_URL` generated

### 2. Configure Environment Variables

For each service, add the required environment variables in Railway's UI:

#### backend-web
```bash
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname
REDIS_URL=redis://:password@host:6379/0
JWT_SECRET_KEY=your-secret-key-here
ALLOWED_ORIGINS=["https://your-frontend.up.railway.app"]
```

#### backend-worker & backend-beat
```bash
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname
REDIS_URL=redis://:password@host:6379/0
JWT_SECRET_KEY=your-secret-key-here
CELERY_BROKER_URL=${{REDIS_URL}}
CELERY_RESULT_BACKEND=${{REDIS_URL}}
```

#### frontend
```bash
# Wait until backend-web is deployed to get its URL
BACKEND_URL=https://backend-web-production-xxxx.up.railway.app
```

#### quiz
```bash
# Wait until backend-web is deployed to get its URL
NEXT_PUBLIC_API_URL=https://backend-web-production-xxxx.up.railway.app
```

### 3. Create Services in Railway

You need to create **5 separate services** in Railway, each pointing to the correct directory:

#### Service 1: backend-web
1. Click "+ New" → "GitHub Repo"
2. Select your repository
3. **Root Directory**: `backend-hormonia`
4. Railway will auto-detect `railway.json` and use `Dockerfile`
5. Add environment variables (see above)

#### Service 2: backend-worker
1. Click "+ New" → "GitHub Repo"
2. Select your repository
3. **Root Directory**: `backend-hormonia`
4. **Settings** → **Build**:
   - Builder: `DOCKERFILE`
   - Dockerfile Path: `Dockerfile.worker`
5. Add environment variables (same as backend-web + Celery configs)

#### Service 3: backend-beat
1. Click "+ New" → "GitHub Repo"
2. Select your repository
3. **Root Directory**: `backend-hormonia`
4. **Settings** → **Build**:
   - Builder: `DOCKERFILE`
   - Dockerfile Path: `Dockerfile.beat`
5. Add environment variables (same as backend-web + Celery configs)

#### Service 4: frontend
1. Click "+ New" → "GitHub Repo"
2. Select your repository
3. **Root Directory**: `frontend-hormonia`
4. Railway will auto-detect `railway.json` and use `Dockerfile`
5. Add `BACKEND_URL` (wait for backend-web URL first)

#### Service 5: quiz
1. Click "+ New" → "GitHub Repo"
2. Select your repository
3. **Root Directory**: `quiz-mensal-interface`
4. Railway will auto-detect `railway.json` and use Nixpacks
5. Add `NEXT_PUBLIC_API_URL` (wait for backend-web URL first)

**Deployment order:**
1. Deploy backend services first (web, worker, beat)
2. Once backend-web is deployed, copy its public URL
3. Add `BACKEND_URL` to frontend service → Redeploy
4. Add `NEXT_PUBLIC_API_URL` to quiz service → Redeploy

### 4. Verify Health Checks

After deployment, verify each service is healthy:

- **backend-web**: `https://your-backend.up.railway.app/health` → should return 200
- **backend-worker**: Check logs for "celery@worker ready" message
- **backend-beat**: Check logs for "Scheduler: Sending due task" messages
- **frontend**: `https://your-frontend.up.railway.app/health` → should return 200
- **quiz**: `https://your-quiz.up.railway.app/api/health` → should return 200

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors
```
Error: could not connect to server
```
**Solution:** Ensure `DATABASE_URL` uses `postgresql+psycopg://` driver, not `postgresql://`

#### 2. Build Failures (Node.js services)
```
Error: Cannot find module
```
**Solution:** Check that `.dockerignore` doesn't exclude necessary files

#### 3. Frontend Proxy Errors
```
502 Bad Gateway on /api requests
```
**Solution:**
- Verify `BACKEND_URL` is set correctly
- Ensure backend-web is deployed and healthy
- Check nginx logs in Railway dashboard

#### 4. Celery Worker Not Processing Tasks
```
Tasks stuck in pending state
```
**Solution:**
- Verify `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` are set
- Check worker logs for connection errors
- Ensure Redis is accessible from worker service

#### 5. Permission Denied on Entrypoint
```
Error: permission denied: /docker-entrypoint.sh
```
**Solution:** This is fixed in the current Dockerfile with `chmod +x`

## Monitoring

### Logs
Access logs for each service in Railway dashboard:
```
Services → [service-name] → Deployments → [latest] → Logs
```

### Metrics
Railway provides built-in metrics:
- CPU usage
- Memory usage
- Network traffic
- Deployment history

## Scaling

To scale services:
1. Navigate to service in Railway dashboard
2. Click "Settings"
3. Adjust "Replicas" under "Deploy"
4. Redeploy

**Recommendations:**
- **backend-web**: Scale horizontally (2-4 replicas)
- **backend-worker**: Scale based on queue depth (2-4 replicas)
- **backend-beat**: Keep at 1 replica (scheduler should not be duplicated)
- **frontend**: Scale horizontally (1-2 replicas)
- **quiz**: Scale horizontally (1-2 replicas)

## Cost Optimization

- Use Railway's "Sleep Application" feature for non-production environments
- Monitor resource usage and adjust replica counts
- Set appropriate `healthcheckTimeout` to avoid unnecessary restarts
- Use build caching by maintaining `.dockerignore` files

## Security Best Practices

1. **Never commit secrets** to repository
2. Use Railway's **environment variable groups** for shared configs
3. Enable **private networking** between services when available
4. Rotate `JWT_SECRET_KEY` periodically
5. Use **Railway's secret management** for API keys
6. Enable **CORS** with specific origins, not `*`

## Updates and Maintenance

### Update Dependencies
```bash
# Backend
cd backend-hormonia
pip install --upgrade -r requirements.txt

# Frontend
cd frontend-hormonia
npm update

# Quiz
cd quiz-mensal-interface
pnpm update
```

### Database Migrations
```bash
# Railway CLI
railway run --service backend-web alembic upgrade head
```

### Rolling Updates
Railway automatically performs zero-downtime deployments when health checks pass.

## Support

- Railway Documentation: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- Repository Issues: https://github.com/your-repo/issues

---

**Last Updated:** 2025-10-03
**Railway JSON Version:** 1.0.0
**Deployment Type:** Multi-service monorepo
