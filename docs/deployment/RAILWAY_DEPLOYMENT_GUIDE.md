# Railway Multi-Service Deployment Guide

## Overview

This guide covers deploying the Clínica Oncológica Hormonia application as a multi-service monorepo on Railway.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Railway Project                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐    │
│  │  Frontend   │  │  Backend API │  │ Celery Worker   │    │
│  │  (Nginx)    │→→│  (FastAPI)   │←←│ (Background)    │    │
│  │  Port: 3000 │  │  Port: 8000  │  │                 │    │
│  └─────────────┘  └──────────────┘  └─────────────────┘    │
│         ↓                ↓                    ↓              │
│         ↓                ↓                    ↓              │
│  ┌──────────────────────────────────────────────────┐       │
│  │           PostgreSQL (Railway DB)                │       │
│  │           Redis (Railway Plugin)                 │       │
│  └──────────────────────────────────────────────────┘       │
│                                                               │
│  ┌─────────────────┐                                        │
│  │  Celery Beat    │                                        │
│  │  (Scheduler)    │                                        │
│  └─────────────────┘                                        │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Deployment Strategy

### Option A: Monorepo Multi-Service (Recommended)

**Advantages:**
- Single Railway project
- Shared environment variables
- Internal networking
- Cost-effective

**Implementation:**
1. Create one Railway project
2. Use root `railway.toml` to define services
3. Each service points to a different directory
4. Shared database and Redis resources

### Option B: Separate Projects

**Advantages:**
- Independent scaling
- Isolated deployments
- Clear separation of concerns

**Disadvantages:**
- More complex networking setup
- Duplicate environment variables
- Higher costs

## Step-by-Step Deployment

### Prerequisites

1. Railway account
2. Railway CLI installed: `npm i -g @railway/cli`
3. Git repository connected to Railway
4. All Dockerfiles present in each service directory

### 1. Initial Setup

```bash
# Login to Railway
railway login

# Link to existing project or create new
railway link

# Or create new project
railway init
```

### 2. Create Required Resources

**PostgreSQL Database:**
```bash
railway add --database postgres
```

**Redis Cache:**
```bash
railway add --plugin redis
```

### 3. Configure Environment Variables

**Backend API Variables:**
```bash
# Database
railway variables set DATABASE_URL="postgresql+psycopg://..."

# Redis
railway variables set REDIS_URL="redis://..."

# Supabase
railway variables set VITE_SUPABASE_URL="https://..."
railway variables set VITE_SUPABASE_ANON_KEY="eyJ..."

# Security
railway variables set SECRET_KEY="your-super-secret-key-min-32-chars"
railway variables set JWT_SECRET_KEY="your-jwt-secret-key"
railway variables set ENCRYPTION_KEY="base64-encoded-fernet-key"

# Firebase (optional)
railway variables set FIREBASE_CREDENTIALS='{"type":"service_account",...}'

# AI
railway variables set GEMINI_API_KEY="your-gemini-key"

# WhatsApp
railway variables set WHATSAPP_API_URL="https://..."
railway variables set WHATSAPP_API_KEY="your-key"
railway variables set WHATSAPP_INSTANCE_NAME="hormonia-instance"

# Python
railway variables set PYTHONUNBUFFERED="1"
railway variables set PYTHONDONTWRITEBYTECODE="1"
railway variables set PASSLIB_BUILTIN_BCRYPT="enabled"

# Environment
railway variables set ENVIRONMENT="production"
railway variables set LOG_LEVEL="info"
```

**Frontend Variables:**
```bash
# API Configuration (use Railway's internal URLs)
railway variables set VITE_API_URL="https://backend-api.railway.app/api/v1"
railway variables set VITE_API_BASE_URL="https://backend-api.railway.app"
railway variables set VITE_WS_BASE_URL="wss://backend-api.railway.app/ws"

# Supabase (same as backend)
railway variables set VITE_SUPABASE_URL="https://..."
railway variables set VITE_SUPABASE_ANON_KEY="eyJ..."

# Build Configuration
railway variables set NODE_ENV="production"
railway variables set VITE_ENVIRONMENT="production"
railway variables set VITE_DEBUG_MODE="false"
```

### 4. Service-to-Service Communication

Railway provides automatic service discovery:

**Backend accessing other services:**
```python
# Use Railway's internal networking
redis_url = os.getenv("REDIS_URL")  # Automatically provided
db_url = os.getenv("DATABASE_URL")  # Automatically provided
```

**Frontend accessing Backend:**
```javascript
// Use public domain with HTTPS
const apiUrl = import.meta.env.VITE_API_URL || 'https://backend-api.railway.app/api/v1';
```

**Internal URLs Pattern:**
```
Backend API: https://${{backend-api.RAILWAY_PUBLIC_DOMAIN}}
Frontend:    https://${{frontend.RAILWAY_PUBLIC_DOMAIN}}

# Or use Railway's private networking (faster, no egress costs)
Backend API: backend-api.railway.internal:8000
```

### 5. Deploy Services

**Using railway.toml (Automatic):**
```bash
# Push to Git - Railway auto-detects services from railway.toml
git add railway.toml
git commit -m "feat: add Railway multi-service configuration"
git push origin main

# Railway will automatically deploy all 4 services:
# 1. backend-api
# 2. celery-worker
# 3. celery-beat
# 4. frontend
```

**Manual Service Creation:**
```bash
# Create each service manually in Railway dashboard
# 1. New Service → GitHub Repo → Select directory
# 2. Configure build settings
# 3. Set environment variables
# 4. Deploy
```

### 6. Configure Custom Domains (Optional)

```bash
# Backend
railway domain add api.yourdomain.com --service backend-api

# Frontend
railway domain add app.yourdomain.com --service frontend
```

### 7. CORS Configuration

**Backend (app/main.py):**
```python
from fastapi.middleware.cors import CORSMiddleware

# Get frontend URL from environment
frontend_url = os.getenv("FRONTEND_URL", "https://frontend.railway.app")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        frontend_url,
        "https://app.yourdomain.com",  # Custom domain
        "http://localhost:5173",        # Local development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 8. Database Migrations

**Run migrations after deployment:**
```bash
# Connect to backend service
railway run --service backend-api

# Run Alembic migrations
alembic upgrade head

# Or use Railway's one-off command
railway run --service backend-api "alembic upgrade head"
```

### 9. Health Checks

All services include health check endpoints:

**Backend API:**
```
GET https://backend-api.railway.app/health
Response: {"status": "healthy"}
```

**Frontend:**
```
GET https://frontend.railway.app/health
Response: 200 OK
```

### 10. Monitoring

**View Logs:**
```bash
# All services
railway logs

# Specific service
railway logs --service backend-api
railway logs --service frontend
railway logs --service celery-worker
```

**Metrics:**
- Access Railway dashboard for CPU, Memory, Network metrics
- Configure alerts for service failures

## Networking Best Practices

### Internal Communication (Recommended)

**Benefits:**
- No egress costs
- Lower latency
- More secure

**Configuration:**
```bash
# Backend → Redis (automatically internal)
REDIS_URL=redis://redis.railway.internal:6379

# Backend → PostgreSQL (automatically internal)
DATABASE_URL=postgresql+psycopg://postgres.railway.internal:5432/db

# Celery Worker → Redis (same REDIS_URL)
```

### External Communication

**Frontend → Backend:**
```javascript
// Always use HTTPS public domain
const API_URL = 'https://backend-api.railway.app/api/v1';
```

**Backend → Frontend (for CORS):**
```python
# Set FRONTEND_URL in Railway dashboard
FRONTEND_URL=https://frontend.railway.app
```

## Environment Variables Strategy

### 1. Sensitive Variables (Set in Railway Dashboard)

**Never commit to Git:**
- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `DATABASE_URL`
- `REDIS_URL`
- `SUPABASE_ANON_KEY`
- `FIREBASE_CREDENTIALS`
- `GEMINI_API_KEY`
- `WHATSAPP_API_KEY`

### 2. Build-time Variables (Can be in railway.toml)

**Non-sensitive configuration:**
- `NODE_ENV=production`
- `PYTHONUNBUFFERED=1`
- `LOG_LEVEL=info`
- `ENVIRONMENT=production`

### 3. Runtime Variables (Injected by code)

**Generated at runtime:**
- API URLs using Railway's service discovery
- Port numbers (Railway sets `PORT` automatically)

## Security Checklist

- [ ] All secrets set in Railway dashboard (not in code)
- [ ] CORS configured with specific origins (not `*`)
- [ ] HTTPS enabled for all public endpoints
- [ ] Database credentials rotated regularly
- [ ] API rate limiting enabled
- [ ] Health checks configured
- [ ] Non-root Docker users configured
- [ ] Environment variables validated at startup

## Scaling

### Horizontal Scaling
```bash
# Increase replicas for high traffic
railway service scale --replicas 3 backend-api
railway service scale --replicas 2 frontend

# Note: Celery Beat should only have 1 replica (scheduler)
# Celery Worker can have multiple replicas
railway service scale --replicas 4 celery-worker
```

### Vertical Scaling
```bash
# Increase resources per instance
railway service scale --memory 2048 backend-api
railway service scale --cpu 2 backend-api
```

## Cost Optimization

1. **Use internal networking** (no egress costs)
2. **Optimize Docker images** (smaller = faster deployments)
3. **Configure auto-sleep** for non-production environments
4. **Monitor resource usage** and right-size instances
5. **Use caching** (Redis) to reduce database queries

## Troubleshooting

### Service Won't Start

**Check logs:**
```bash
railway logs --service backend-api --tail 100
```

**Common issues:**
- Missing environment variables
- Database connection failed
- Port binding issues (ensure using `$PORT`)

### DNS/Networking Issues

**Verify internal connectivity:**
```bash
railway run --service backend-api "curl http://redis.railway.internal:6379"
```

**Verify public connectivity:**
```bash
curl https://backend-api.railway.app/health
```

### Build Failures

**Clear build cache:**
```bash
railway build --clear-cache
```

**Verify Dockerfile:**
```bash
# Test locally
docker build -t test-backend -f backend-hormonia/Dockerfile backend-hormonia
docker run -p 8000:8000 test-backend
```

## Deployment Checklist

### Pre-Deployment
- [ ] All Dockerfiles tested locally
- [ ] Environment variables documented
- [ ] Database migrations ready
- [ ] Health checks configured
- [ ] CORS settings reviewed

### Deployment
- [ ] Railway project created
- [ ] PostgreSQL database added
- [ ] Redis plugin added
- [ ] Environment variables set
- [ ] Services deployed
- [ ] Database migrations run

### Post-Deployment
- [ ] All health checks passing
- [ ] Frontend can reach backend
- [ ] Celery tasks running
- [ ] Logs reviewed for errors
- [ ] Custom domains configured (if applicable)
- [ ] Monitoring alerts set up

## Support Resources

- **Railway Documentation:** https://docs.railway.app
- **Railway Discord:** https://discord.gg/railway
- **Project Issues:** GitHub Issues
- **Status Page:** https://status.railway.app

## Next Steps

1. **Set up CI/CD** (see `.github/workflows/railway-deploy.yml`)
2. **Configure monitoring** (Sentry, DataDog, etc.)
3. **Set up staging environment**
4. **Implement feature flags**
5. **Configure backups**
