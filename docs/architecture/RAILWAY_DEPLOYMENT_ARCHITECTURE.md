# Railway Deployment Architecture - Sistema Hormonia

**Data**: 2025-10-04
**Versão**: 1.0.0
**Sistema**: Clínica Oncológica Hormonia
**Plataforma**: Railway.app
**Metodologia**: System Architecture Design

---

## Executive Summary

Este documento especifica a arquitetura de deployment do sistema Hormonia na plataforma Railway, incluindo topologia de serviços, estratégias de configuração, ordem de deployment, health checks, e recomendações de produção.

### Componentes Principais
1. **Backend Service** - FastAPI Python 3.13 + Gunicorn
2. **Frontend Service** - Vite React SPA + Nginx
3. **PostgreSQL Database** - Supabase Cloud (managed)
4. **Redis Cache** - Redis Cloud (managed, SSL/TLS)

### Características da Arquitetura
- **Escalabilidade**: Horizontal scaling via Railway replicas
- **Resiliência**: Health checks, restart policies, connection pooling
- **Segurança**: HTTPS por padrão, secrets via environment variables
- **Observabilidade**: Structured logging, health endpoints, metrics

---

## 1. Deployment Topology

### 1.1 Diagrama de Arquitetura

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Railway Platform                                 │
│                        (us-east-1 region)                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │ Frontend Service (frontend-production-18bb)                  │       │
│  │ ─────────────────────────────────────────────────────────────│       │
│  │ • Build: Node 20 → Vite → Nginx Alpine                      │       │
│  │ • URL: https://frontend-production-18bb.up.railway.app       │       │
│  │ • Health: /health (every 30s)                                │       │
│  │ • Port: ${PORT} (Railway managed)                            │       │
│  │ • Replicas: 1 (autoscale to 3 under load)                   │       │
│  └────────────────────┬─────────────────────────────────────────┘       │
│                       │                                                  │
│                       │ /api/* → proxy_pass                              │
│                       │ /ws → WebSocket upgrade                          │
│                       ▼                                                  │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │ Backend Service (backend-production-e0bd)                    │       │
│  │ ─────────────────────────────────────────────────────────────│       │
│  │ • Build: Python 3.13 + Node.js 20 hybrid                    │       │
│  │ • URL: https://backend-production-e0bd.up.railway.app        │       │
│  │ • Workers: 4x Gunicorn + Uvicorn                            │       │
│  │ • Health: /health (every 30s)                                │       │
│  │ • Port: ${PORT} (Railway managed)                            │       │
│  │ • Replicas: 1 (autoscale to 3 under load)                   │       │
│  └────────────────────┬─────────────────────────────────────────┘       │
│                       │                                                  │
│                       ├───────────────┐                                  │
│                       │               │                                  │
│                       ▼               ▼                                  │
│  ┌─────────────────────────┐  ┌─────────────────────────────────┐      │
│  │ Supabase PostgreSQL     │  │ Redis Cloud (SSL)               │      │
│  │ ─────────────────────── │  │ ─────────────────────────────── │      │
│  │ • Managed Service       │  │ • Managed Service               │      │
│  │ • Connection Pooling    │  │ • DB 0: Celery Broker           │      │
│  │ • Row-Level Security    │  │ • DB 1: Application Cache       │      │
│  │ • Auto Backups          │  │ • SSL/TLS Required              │      │
│  └─────────────────────────┘  └─────────────────────────────────┘      │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘

External Services (not on Railway):
  ┌─────────────────────┐  ┌─────────────────────┐  ┌──────────────────┐
  │ Firebase Auth       │  │ Evolution API       │  │ Gemini AI API    │
  │ (Google Cloud)      │  │ (WhatsApp Gateway)  │  │ (Google Cloud)   │
  └─────────────────────┘  └─────────────────────┘  └──────────────────┘
```

### 1.2 Service Dependencies

```
┌─────────────────────────────────────────────────────────────────┐
│                    Dependency Graph                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  External Services (must be configured first)                   │
│  ───────────────────────────────────────────                    │
│  1. Supabase PostgreSQL                                         │
│  2. Redis Cloud                                                 │
│  3. Firebase Auth (Admin SDK)                                   │
│                                                                  │
│         ↓ (provide connection strings)                          │
│                                                                  │
│  Backend Service                                                │
│  ────────────────                                               │
│  • Requires: DATABASE_URL, REDIS_URL, FIREBASE_*                │
│  • Exposes: /health, /api/v1/*, /api/config                     │
│                                                                  │
│         ↓ (provides BACKEND_URL)                                │
│                                                                  │
│  Frontend Service                                               │
│  ─────────────────                                              │
│  • Requires: BACKEND_URL (runtime), VITE_* (build-time)         │
│  • Proxies: /api/* → Backend, /ws → Backend                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Service Specifications

### 2.1 Backend Service

#### Build Configuration

**Root Directory**: `backend-hormonia`

**Dockerfile**: `backend-hormonia/Dockerfile`

```dockerfile
# Key characteristics:
FROM python:3.13-slim
# Hybrid Python + Node.js for bcrypt/supabase-js dependencies

# Multi-worker production server
CMD gunicorn app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:${PORT:-8000} \
    --timeout 120
```

**Railway Configuration** (`backend-hormonia/railway.json`):

```json
{
  "build": {
    "builder": "DOCKERFILE"
  },
  "deploy": {
    "numReplicas": 1,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10,
    "healthcheckPath": "/health",
    "healthcheckTimeout": 120
  }
}
```

#### Environment Variables (Backend)

**Critical Variables** (must be set):

```bash
# Application Configuration
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=info
PORT=8000  # Railway auto-injects, but included for local dev

# Security Keys (CHANGE THESE!)
SECRET_KEY=<generate-64-char-random-string>
JWT_SECRET_KEY=<generate-64-char-random-string>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Database (Supabase PostgreSQL)
DATABASE_URL=postgresql+psycopg://postgres:password@db.supabase.co:6543/postgres
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=40
DB_POOL_TIMEOUT=20
DB_STATEMENT_TIMEOUT=30000

# Redis Cache (REQUIRED for authentication)
REDIS_URL=rediss://default:password@host.redis-cloud.com:port/1
REDIS_PASSWORD=<redis-password>
REDIS_HOST=<redis-host>
REDIS_PORT=<redis-port>
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required
REDIS_MAX_CONNECTIONS=25
REDIS_SOCKET_TIMEOUT=10.0
REDIS_ENABLE_DB_ISOLATION=true
REDIS_CACHE_DB=1
REDIS_BROKER_DB=0

# Celery (uses Redis DB 0)
CELERY_BROKER_URL=rediss://default:password@host.redis-cloud.com:port/0
CELERY_RESULT_BACKEND=rediss://default:password@host.redis-cloud.com:port/0

# Firebase Admin SDK (CRITICAL)
FIREBASE_ADMIN_PROJECT_ID=<firebase-project-id>
FIREBASE_ADMIN_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n<key>\n-----END PRIVATE KEY-----
FIREBASE_ADMIN_CLIENT_EMAIL=firebase-adminsdk-xxxxx@project.iam.gserviceaccount.com

# Firebase Security
FIREBASE_ALLOWED_DOMAINS=["oncologia.com","hospital.local"]
FIREBASE_BLOCK_PUBLIC_DOMAINS=true

# Supabase (Database + Storage)
SUPABASE_URL=https://project.supabase.co
SUPABASE_ANON_KEY=<anon-key>
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
SUPABASE_AVATARS_BUCKET=avatars

# CORS Configuration
ALLOWED_ORIGINS=["https://frontend-production-18bb.up.railway.app","http://localhost:3000","http://localhost:5173"]

# Frontend URLs (for /api/config endpoint)
FRONTEND_URL=https://frontend-production-18bb.up.railway.app
FRONTEND_API_URL=https://backend-production-e0bd.up.railway.app

# AI Services (optional)
GEMINI_API_KEY=<gemini-api-key>
GEMINI_MODEL=gemini-2.5-flash-preview-09-2025
```

**Optional Variables**:

```bash
# Evolution API (WhatsApp Integration)
ENABLE_EVOLUTION=true
EVOLUTION_API_URL=https://evolution-api.example.com
EVOLUTION_API_KEY=<api-key>
EVOLUTION_INSTANCE_NAME=hormonia-instance
EVOLUTION_WEBHOOK_SECRET=<webhook-secret>
EVOLUTION_WEBHOOK_URL=https://backend-production-e0bd.up.railway.app/webhooks/whatsapp/evolution/hormonia-instance

# Monitoring
MONITORING_ENABLED=true
SENTRY_DSN=<sentry-dsn>
SENTRY_ENVIRONMENT=production

# Compliance
LGPD_COMPLIANCE_MODE=true
AUDIT_LOG_RETENTION_DAYS=365

# bcrypt workaround for Python 3.13
PASSLIB_BUILTIN_BCRYPT=enabled
```

#### Health Check

**Endpoint**: `GET /health`

**Expected Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-04T12:00:00Z",
  "services": {
    "database": "connected",
    "redis": "connected",
    "firebase": "initialized"
  }
}
```

**Railway Health Check Settings**:
- Path: `/health`
- Interval: 30 seconds
- Timeout: 120 seconds
- Start Period: 40 seconds
- Retries: 3

---

### 2.2 Frontend Service

#### Build Configuration

**Root Directory**: `frontend-hormonia`

**Dockerfile**: `frontend-hormonia/Dockerfile` (multi-stage)

```dockerfile
# Stage 1: Build dependencies
FROM node:20-alpine AS deps
# npm ci --prefer-offline

# Stage 2: Build application with Vite
FROM node:20-alpine AS builder
# npm run build:runtime
# Outputs to /app/dist

# Stage 3: Production nginx server
FROM nginx:alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Startup script with BACKEND_URL substitution
ENTRYPOINT ["/docker-entrypoint.sh"]
```

**Railway Configuration** (`frontend-hormonia/railway.json`):

```json
{
  "build": {
    "builder": "DOCKERFILE"
  },
  "deploy": {
    "numReplicas": 1,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10,
    "healthcheckPath": "/health",
    "healthcheckTimeout": 120
  }
}
```

#### Environment Variables (Frontend)

**Critical Variables** (runtime):

```bash
# REQUIRED: Backend URL for nginx proxy_pass
BACKEND_URL=https://backend-production-e0bd.up.railway.app

# Railway auto-injected
PORT=${PORT}  # Defaults to 3000 if not set
```

**Build-time Variables** (optional, fallback if `/api/config` fails):

```bash
# Firebase Client SDK (PUBLIC - safe to expose)
VITE_FIREBASE_API_KEY=<public-api-key>
VITE_FIREBASE_AUTH_DOMAIN=project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=<project-id>
VITE_FIREBASE_STORAGE_BUCKET=<project-id>.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=<sender-id>
VITE_FIREBASE_APP_ID=<app-id>

# Supabase Client (PUBLIC - anon key only)
VITE_SUPABASE_URL=https://project.supabase.co
VITE_SUPABASE_ANON_KEY=<anon-key>

# Backend API URLs (fallback - prefer runtime config)
VITE_API_URL=https://backend-production-e0bd.up.railway.app
VITE_API_BASE_URL=https://backend-production-e0bd.up.railway.app
VITE_WS_BASE_URL=wss://backend-production-e0bd.up.railway.app/ws
```

#### Nginx Configuration

**Key Features**:

```nginx
# Proxy to backend API
location /api/ {
    proxy_pass ${BACKEND_URL};  # Substituted at runtime
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

# WebSocket support
location /ws {
    proxy_pass ${BACKEND_URL};
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_buffering off;
    proxy_request_buffering off;
}

# SPA routing (fallback to index.html)
location / {
    root /usr/share/nginx/html;
    try_files $uri $uri/ /index.html;
}
```

#### Runtime Configuration Loading

**Flow**:

1. Frontend loads → Fetches `GET /api/config` from backend
2. Backend returns runtime config (VITE_* formatted)
3. Frontend caches config for 5 minutes
4. Frontend uses config for API_URL, WS_URL, Firebase keys

**Fallback Chain**:
```
1. /api/config (runtime, preferred)
   ↓ (if fails)
2. window.__ENV_CONFIG__ (server-injected, not used in Railway)
   ↓ (if fails)
3. import.meta.env (build-time VITE_*)
   ↓ (if fails)
4. Production defaults (hardcoded)
```

#### Health Check

**Endpoint**: `GET /health`

**Expected Response**:
```
healthy
```

**Railway Health Check Settings**:
- Path: `/health`
- Interval: 30 seconds
- Timeout: 3 seconds
- Start Period: 5 seconds
- Retries: 3

---

### 2.3 External Dependencies

#### PostgreSQL Database (Supabase)

**Service Type**: Managed Supabase Cloud

**Configuration Checklist**:
- [ ] Create Supabase project
- [ ] Enable Row-Level Security (RLS) policies
- [ ] Create `avatars` storage bucket (public read, authenticated write)
- [ ] Apply schema migrations (`backend-hormonia/sql/SCHEMA_MASTER_COMPLETO.sql`)
- [ ] Copy `DATABASE_URL` from Supabase dashboard → Railway env vars
- [ ] Copy `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`

**Connection String Format**:
```
postgresql+psycopg://postgres:password@db.supabase.co:6543/postgres
```

**Connection Pool Settings** (backend):
```python
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=40
DB_POOL_TIMEOUT=20  # seconds
DB_STATEMENT_TIMEOUT=30000  # milliseconds
DB_POOL_RECYCLE=3600  # seconds
```

**Migrations Strategy**:
- **Development**: Manual migration via `alembic upgrade head` (run locally)
- **Production**: Migrations run automatically in Dockerfile `CMD` before server starts
- **Rollback**: `alembic downgrade -1` (manual, via Railway shell)

---

#### Redis Cache (Redis Cloud)

**Service Type**: Managed Redis Cloud (SSL/TLS required)

**Configuration Checklist**:
- [ ] Create Redis Cloud instance (AWS us-east-1 for low latency)
- [ ] Enable SSL/TLS
- [ ] Configure DB isolation: DB 0 for Celery, DB 1 for cache
- [ ] Copy connection string → Railway env vars

**Connection String Format**:
```
rediss://default:password@host.redis-cloud.com:port/1
```

**Critical Settings**:
```bash
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required  # Enforce SSL certificate validation
REDIS_MAX_CONNECTIONS=25
REDIS_SOCKET_TIMEOUT=10.0
```

**Database Isolation**:
- **DB 0**: Celery broker + result backend (task queue)
- **DB 1**: Application cache (sessions, rate limiting, query cache)

**Fallback Strategy**:
- **Dev/Staging**: Redis optional, fallback to in-memory cache
- **Production**: Redis REQUIRED (AuthService raises RuntimeError if unavailable)

---

#### Firebase Authentication

**Service Type**: Firebase Admin SDK (Google Cloud)

**Configuration Checklist**:
- [ ] Create Firebase project (https://console.firebase.google.com)
- [ ] Enable Authentication → Email/Password provider
- [ ] Create service account → Download JSON
- [ ] Extract credentials: `project_id`, `private_key`, `client_email`
- [ ] Set custom claims for users: `{"role": "medico"}` or `{"role": "admin"}`
- [ ] Add backend domain to Firebase authorized domains

**Environment Variables**:
```bash
FIREBASE_ADMIN_PROJECT_ID=<from service account JSON>
FIREBASE_ADMIN_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n<key>\n-----END PRIVATE KEY-----
FIREBASE_ADMIN_CLIENT_EMAIL=firebase-adminsdk-xxxxx@project.iam.gserviceaccount.com
```

**Security Policies**:
```bash
# Domain allowlist for auto-provisioning
FIREBASE_ALLOWED_DOMAINS=["oncologia.com","hospital.local"]

# Block public email providers
FIREBASE_BLOCK_PUBLIC_DOMAINS=true
FIREBASE_PUBLIC_DOMAINS_BLOCKLIST=["gmail.com","yahoo.com","hotmail.com"]

# Require custom claims (role)
FIREBASE_REQUIRE_CUSTOM_CLAIMS=true
FIREBASE_ALLOWED_ROLES=["admin","super_admin","doctor","medico"]
```

**Token Validation Flow**:
```
1. Frontend: User logs in → Firebase Auth SDK → ID Token (JWT)
2. Frontend: API request → Authorization: Bearer <token>
3. Backend: Validate token → Firebase Admin SDK verify_id_token()
4. Backend: Extract uid, email, role from token claims
5. Backend: Check if user exists in local DB → Auto-provision if needed
6. Backend: Return current_user dependency for route handlers
```

---

## 3. Deployment Order & Dependencies

### 3.1 Pre-Deployment Checklist

**Phase 1: External Services Setup**

```
┌────────────────────────────────────────────────────────────────┐
│ 1. Supabase PostgreSQL                                         │
│    ─────────────────────────────────────────────────────────   │
│    [ ] Create Supabase project                                 │
│    [ ] Apply database schema (SCHEMA_MASTER_COMPLETO.sql)      │
│    [ ] Enable RLS policies                                     │
│    [ ] Create storage bucket: avatars                          │
│    [ ] Copy DATABASE_URL → .env                                │
│                                                                 │
│ 2. Redis Cloud                                                 │
│    ───────────                                                 │
│    [ ] Create Redis instance (AWS us-east-1)                   │
│    [ ] Enable SSL/TLS                                          │
│    [ ] Copy REDIS_URL → .env                                   │
│                                                                 │
│ 3. Firebase Authentication                                     │
│    ────────────────────────                                    │
│    [ ] Create Firebase project                                 │
│    [ ] Enable Email/Password authentication                    │
│    [ ] Download service account JSON                           │
│    [ ] Copy FIREBASE_ADMIN_* credentials → .env                │
│    [ ] Create test user with custom claims: {"role": "admin"}  │
│                                                                 │
│ 4. Generate Security Keys                                      │
│    ─────────────────────                                       │
│    [ ] Generate SECRET_KEY (64+ chars)                         │
│    [ ] Generate JWT_SECRET_KEY (64+ chars)                     │
│    [ ] Generate MONTHLY_QUIZ_TOKEN_SECRET                      │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### 3.2 Railway Deployment Order

**Phase 2: Railway Services Deployment**

```
┌────────────────────────────────────────────────────────────────┐
│ Step 1: Deploy Backend Service                                 │
│ ────────────────────────────────────────────────────────────   │
│ 1. Create Railway project: "hormonia-production"               │
│ 2. Add service: "backend" → Connect GitHub repo                │
│ 3. Configure:                                                  │
│    • Root Directory: backend-hormonia                          │
│    • Builder: DOCKERFILE                                       │
│    • Branch: main (or docs-refactor-py313)                     │
│ 4. Set ALL environment variables (see section 2.1)             │
│ 5. Deploy → Wait for health check (/health) → 200 OK          │
│ 6. Copy backend URL: https://backend-xxxxx.up.railway.app      │
│                                                                 │
│ ✅ Validation:                                                 │
│    curl https://backend-xxxxx.up.railway.app/health            │
│    → {"status": "healthy", ...}                                │
│                                                                 │
│    curl https://backend-xxxxx.up.railway.app/api/config        │
│    → {"VITE_API_URL": "...", ...}                              │
│                                                                 │
└────────────────────────────────────────────────────────────────┘

↓ (wait for backend to be healthy)

┌────────────────────────────────────────────────────────────────┐
│ Step 2: Deploy Frontend Service                                │
│ ────────────────────────────────────────────────────────────   │
│ 1. Add service: "frontend" → Connect GitHub repo               │
│ 2. Configure:                                                  │
│    • Root Directory: frontend-hormonia                         │
│    • Builder: DOCKERFILE                                       │
│    • Branch: main (or docs-refactor-py313)                     │
│ 3. Set environment variables:                                  │
│    • BACKEND_URL=https://backend-xxxxx.up.railway.app (REQUIRED)│
│    • VITE_* (optional build-time vars, see section 2.2)        │
│ 4. Deploy → Wait for health check (/health) → 200 OK          │
│ 5. Copy frontend URL: https://frontend-xxxxx.up.railway.app    │
│                                                                 │
│ ✅ Validation:                                                 │
│    curl https://frontend-xxxxx.up.railway.app/health           │
│    → healthy                                                   │
│                                                                 │
│    # Test backend proxy                                        │
│    curl https://frontend-xxxxx.up.railway.app/api/v1/health    │
│    → proxied to backend, 200 OK                                │
│                                                                 │
└────────────────────────────────────────────────────────────────┘

↓ (update CORS settings)

┌────────────────────────────────────────────────────────────────┐
│ Step 3: Update Backend CORS Configuration                      │
│ ────────────────────────────────────────────────────────────   │
│ 1. Edit backend service environment variables:                 │
│    ALLOWED_ORIGINS=["https://frontend-xxxxx.up.railway.app"]   │
│    FRONTEND_URL=https://frontend-xxxxx.up.railway.app          │
│                                                                 │
│ 2. Redeploy backend (or wait for auto-deploy)                  │
│                                                                 │
│ ✅ Validation:                                                 │
│    # From browser console on frontend domain:                  │
│    fetch('https://backend-xxxxx.up.railway.app/api/config')    │
│    → Response should include CORS headers                      │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### 3.3 Post-Deployment Verification

**End-to-End Test Flow**:

```bash
# 1. Frontend loads successfully
curl -I https://frontend-xxxxx.up.railway.app/
# → 200 OK, Content-Type: text/html

# 2. Frontend fetches runtime config from backend
curl https://frontend-xxxxx.up.railway.app/api/config
# → Proxied to backend /api/config
# → Returns JSON with VITE_API_URL, VITE_FIREBASE_*, etc.

# 3. Frontend proxies API requests to backend
curl https://frontend-xxxxx.up.railway.app/api/v1/health
# → Proxied to backend /api/v1/health
# → 200 OK

# 4. WebSocket connection works
# (Use browser DevTools → Network → WS filter)
ws://frontend-xxxxx.up.railway.app/ws
# → Upgraded to WebSocket
# → Connected to backend WebSocket handler

# 5. Test authentication flow (manual browser test)
# Navigate to: https://frontend-xxxxx.up.railway.app/login
# Login with Firebase credentials
# → Should redirect to dashboard
# → Should see API requests with Authorization: Bearer <token>
```

---

## 4. Health Check Strategy

### 4.1 Health Check Endpoints

| Service | Endpoint | Protocol | Timeout | Interval | Expected Response |
|---------|----------|----------|---------|----------|-------------------|
| **Backend** | `/health` | HTTP GET | 10s | 30s | `{"status": "healthy"}` 200 OK |
| **Frontend** | `/health` | HTTP GET | 3s | 30s | `healthy` 200 OK |

### 4.2 Health Check Implementation

#### Backend Health Check

**Endpoint**: `GET /health`

**File**: `backend-hormonia/app/main.py` (inferred)

```python
@app.get("/health", include_in_schema=False)
async def health_check():
    """
    Comprehensive health check for Railway

    Checks:
    - Database connectivity (Supabase PostgreSQL)
    - Redis connectivity (cache + Celery broker)
    - Firebase Admin SDK initialization
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }

    # Database check
    try:
        async with db_session() as session:
            await session.execute(text("SELECT 1"))
        health_status["services"]["database"] = "connected"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["services"]["database"] = f"error: {str(e)}"

    # Redis check
    try:
        await redis_client.ping()
        health_status["services"]["redis"] = "connected"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["services"]["redis"] = f"error: {str(e)}"

    # Firebase check
    try:
        if firebase_admin.auth.verify_id_token:
            health_status["services"]["firebase"] = "initialized"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["services"]["firebase"] = f"error: {str(e)}"

    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)
```

**Docker Healthcheck** (`backend-hormonia/Dockerfile`):

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1
```

#### Frontend Health Check

**Endpoint**: `GET /health`

**File**: `frontend-hormonia/nginx.conf`

```nginx
location /health {
    access_log off;  # Don't log health checks
    return 200 "healthy\n";
    add_header Content-Type text/plain;
}
```

**Docker Healthcheck** (`frontend-hormonia/Dockerfile`):

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT:-3000}/health || exit 1
```

### 4.3 Railway Health Check Configuration

**Backend Service Settings**:
```json
{
  "deploy": {
    "healthcheckPath": "/health",
    "healthcheckTimeout": 120,  // seconds
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

**Frontend Service Settings**:
```json
{
  "deploy": {
    "healthcheckPath": "/health",
    "healthcheckTimeout": 120,  // seconds
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### 4.4 Health Check Failure Scenarios

| Scenario | Detection | Railway Action | Recovery |
|----------|-----------|----------------|----------|
| **Backend DB connection fails** | `/health` returns 503 | Restart container (up to 10 times) | Auto-reconnect via connection pool |
| **Backend Redis fails** | `/health` returns 503 | Restart container | Auto-reconnect via redis-py |
| **Frontend nginx crashes** | `/health` timeout | Restart container | Immediate restart |
| **Backend Python crash** | Process exit code != 0 | Restart container | Gunicorn master restarts workers |

---

## 5. Monitoring & Observability

### 5.1 Application Metrics

**Backend Exposed Headers** (every API response):

```http
X-Request-ID: <uuid>
X-Correlation-ID: <uuid>
X-Process-Time: <milliseconds>
X-Query-Count: <number>
X-DB-Time-Ms: <milliseconds>
X-RateLimit-Limit: <requests-per-window>
X-RateLimit-Remaining: <remaining-requests>
```

**Metrics Collected by Middleware**:

| Metric | Middleware | Storage | Purpose |
|--------|------------|---------|---------|
| Request latency (p50, p95, p99) | `MonitoringMiddleware` | In-memory + logs | APM |
| DB query count per request | `QueryPerformanceMiddleware` | Response header | N+1 detection |
| DB query duration | `QueryPerformanceMiddleware` | Response header | Slow query identification |
| Rate limit violations | `EnhancedRateLimitMiddleware` | Redis | Abuse detection |
| 4xx/5xx error rates | `MonitoringMiddleware` | Logs + Sentry | Error tracking |
| WebSocket connections | Custom middleware | Prometheus (future) | Capacity planning |

### 5.2 Logging Strategy

**Backend Logging** (`app/config.py`):

```python
LOG_LEVEL=info  # production
LOG_FORMAT=json  # structured logging for Railway

# Example log output:
{
  "timestamp": "2025-10-04T12:00:00Z",
  "level": "INFO",
  "logger": "app.api.v1.auth",
  "message": "User authenticated",
  "request_id": "uuid",
  "user_id": "uuid",
  "duration_ms": 45
}
```

**Frontend Logging**:
- Nginx access logs (Railway captures automatically)
- Client-side errors → Sentry (if `VITE_SENTRY_DSN` configured)

### 5.3 External Monitoring (Recommended)

**Sentry Integration**:

```bash
# Backend
SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1  # 10% of requests

# Frontend
VITE_SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx
```

**Features**:
- Error tracking (exceptions, API errors)
- Performance monitoring (transaction traces)
- Release tracking (deploy notifications)
- User feedback (error reports with user context)

---

## 6. Production Optimization Recommendations

### 6.1 Performance Optimizations

#### Backend

**1. Connection Pooling Tuning**

```python
# Current settings (conservative)
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=40

# Recommended for production (monitor and adjust)
# Formula: pool_size = (num_replicas * workers_per_replica * 2) + 10
# Example: 3 replicas * 4 workers * 2 + 10 = 34
DB_POOL_SIZE=35
DB_MAX_OVERFLOW=50
DB_POOL_TIMEOUT=20
DB_POOL_PRE_PING=true  # Verify connections before use
```

**2. Gunicorn Worker Tuning**

```bash
# Current: 4 workers (fixed)
# Recommended: (2 * num_cores) + 1

# For Railway shared CPU (2 vCPU):
--workers 5

# For Railway Pro plan (4 vCPU):
--workers 9

# Worker class: uvicorn (async)
--worker-class uvicorn.workers.UvicornWorker

# Timeouts
--timeout 120  # Request timeout (2 minutes)
--graceful-timeout 30  # Graceful shutdown
--keep-alive 5  # Keep-alive connections
```

**3. Redis Connection Pooling**

```python
# Current
REDIS_MAX_CONNECTIONS=25

# Recommended for production
REDIS_MAX_CONNECTIONS=50
REDIS_SOCKET_CONNECT_TIMEOUT=5.0
REDIS_SOCKET_TIMEOUT=10.0
REDIS_SOCKET_KEEPALIVE=true
REDIS_SOCKET_KEEPALIVE_OPTIONS={
    "TCP_KEEPIDLE": 60,
    "TCP_KEEPINTVL": 10,
    "TCP_KEEPCNT": 3
}
```

#### Frontend

**1. Nginx Caching**

```nginx
# Cache static assets (already implemented)
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}

# Recommended: Add ETag support
etag on;

# Recommended: Enable gzip compression
gzip on;
gzip_vary on;
gzip_proxied any;
gzip_comp_level 6;
gzip_types text/plain text/css text/xml text/javascript
           application/json application/javascript application/xml+rss
           application/rss+xml font/truetype font/opentype
           application/vnd.ms-fontobject image/svg+xml;
```

**2. Vite Build Optimization**

```typescript
// vite.config.ts
export default defineConfig({
  build: {
    // Code splitting
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'ui-vendor': ['@shadcn/ui', 'lucide-react'],
          'firebase-vendor': ['firebase/app', 'firebase/auth'],
          'supabase-vendor': ['@supabase/supabase-js']
        }
      }
    },
    // Minification
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,  // Remove console.log in production
        drop_debugger: true
      }
    },
    // Chunk size warnings
    chunkSizeWarningLimit: 1000  // 1MB chunks
  }
})
```

### 6.2 Security Hardening

#### 1. Content Security Policy (CSP)

**Recommendation**: Add CSP header to prevent XSS attacks

**Frontend** (`nginx.conf`):

```nginx
add_header Content-Security-Policy "
    default-src 'self';
    script-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.googletagmanager.com;
    style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
    img-src 'self' data: https: blob:;
    font-src 'self' data: https://fonts.gstatic.com;
    connect-src 'self'
        https://*.railway.app
        https://*.supabase.co
        https://identitytoolkit.googleapis.com
        https://securetoken.googleapis.com
        wss://*.railway.app;
    frame-ancestors 'none';
    base-uri 'self';
    form-action 'self';
" always;
```

#### 2. Security Headers

**Backend** (`app/middleware/security.py`):

```python
# Add missing headers
response.headers["X-Frame-Options"] = "DENY"
response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
```

**Frontend** (already has X-Frame-Options, X-Content-Type-Options, X-XSS-Protection)

#### 3. Rate Limiting Adjustment

```python
# Current rate limits (dev-friendly)
# Recommendation: Tighten for production

# Authentication endpoints
@limiter.limit("10/minute")  # Current: 10/minute
@limiter.limit("5/minute")   # Recommended: 5/minute

# Public endpoints
@limiter.limit("100/minute")  # /api/config
@limiter.limit("60/minute")   # Recommended: 60/minute

# Authenticated endpoints
@limiter.limit("1000/hour")   # General API
@limiter.limit("500/hour")    # Recommended: 500/hour
```

### 6.3 Reliability Improvements

#### 1. Circuit Breaker Pattern

**Recommendation**: Implement circuit breaker for external services (Evolution API, Gemini AI)

```python
# Using circuitbreaker library
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=60)
async def send_whatsapp_message(phone: str, message: str):
    """
    Circuit breaker for Evolution API

    - Opens circuit after 5 consecutive failures
    - Stays open for 60 seconds before half-open state
    - Falls back to queuing message for retry
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{EVOLUTION_API_URL}/sendText",
            json={"phone": phone, "message": message},
            timeout=10.0
        )
        response.raise_for_status()
        return response.json()
```

#### 2. Database Query Timeout

**Recommendation**: Add query timeout to prevent long-running queries

```python
# Current: DB_STATEMENT_TIMEOUT=30000 (30 seconds)
# Recommendation: 10 seconds for most queries, 30 for reports

# In SQLAlchemy session:
session.execute(
    query,
    execution_options={"timeout": 10}  # 10 seconds
)
```

#### 3. Graceful Degradation

**Recommendation**: Implement fallback strategies

```python
# Redis fallback to in-memory cache
try:
    cached_value = await redis.get(key)
except RedisConnectionError:
    logger.warning("Redis unavailable, using in-memory cache")
    cached_value = in_memory_cache.get(key)

# Gemini AI fallback to original message
try:
    ai_response = await gemini_client.generate(prompt)
except Exception as e:
    logger.error(f"Gemini AI failed: {e}")
    ai_response = original_message  # Pass-through
```

### 6.4 Scalability Recommendations

#### Horizontal Scaling

**Backend**:
```json
{
  "deploy": {
    "numReplicas": 3,  // Start with 3 replicas
    "autoscaling": {
      "enabled": true,
      "minReplicas": 2,
      "maxReplicas": 10,
      "targetCPUUtilization": 70,
      "targetMemoryUtilization": 80
    }
  }
}
```

**Frontend**:
```json
{
  "deploy": {
    "numReplicas": 2,  // Frontend is stateless, easy to scale
    "autoscaling": {
      "enabled": true,
      "minReplicas": 1,
      "maxReplicas": 5,
      "targetCPUUtilization": 60
    }
  }
}
```

#### Database Scaling

**Supabase**:
- Upgrade to Pro plan for read replicas
- Enable connection pooling (PgBouncer) - already included in Supabase
- Consider sharding for very large datasets (>1M patients)

**Redis**:
- Upgrade to high-availability cluster (Redis Cloud)
- Enable persistence (RDB + AOF)
- Configure eviction policy: `allkeys-lru` for cache DB

---

## 7. Cost Optimization

### 7.1 Railway Pricing Estimates

**Starter Plan** (Hobby):
- $5/month per service
- Shared CPU, 512MB RAM
- Suitable for: Development, staging

**Pro Plan**:
- $20/month per service (base)
- Dedicated CPU, 8GB RAM max
- Pay-as-you-go for usage
- Suitable for: Production

**Estimated Monthly Cost** (Production):

| Service | Plan | Cost |
|---------|------|------|
| Backend (1 replica) | Pro | $20 + usage |
| Frontend (1 replica) | Pro | $20 + usage |
| **Total Railway** | | **~$50-100/month** |
| Supabase Pro | | $25/month |
| Redis Cloud (250MB) | | $7/month |
| Firebase Auth (free tier) | | $0 |
| **Total Infrastructure** | | **~$82-132/month** |

### 7.2 Cost Optimization Strategies

1. **Use Starter Plan for Staging**
   - Production: Pro plan
   - Staging: Starter plan ($5/month per service)

2. **Optimize Database Queries**
   - Add indexes for frequently queried columns
   - Use query result caching (Redis)
   - Implement pagination for large datasets

3. **CDN for Static Assets** (optional)
   - Cloudflare (free tier) for frontend static assets
   - Reduces Railway bandwidth costs

4. **Aggressive Caching**
   - API response caching (Redis)
   - Browser caching (nginx `Cache-Control` headers)
   - Reduce database query load

---

## 8. Disaster Recovery & Backup

### 8.1 Backup Strategy

**Database Backups** (Supabase):
- Automated daily backups (last 7 days on free tier, 30 days on Pro)
- Point-in-time recovery (Pro plan only)
- Manual backups before major migrations

**Backup Verification**:
```bash
# Test restore from backup (monthly)
1. Create test Supabase project
2. Restore latest backup
3. Verify data integrity (row counts, sample queries)
4. Delete test project
```

**Code Backups**:
- Git repository (GitHub) - primary backup
- Railway auto-deploys from Git - no separate code backup needed

**Configuration Backups**:
- Environment variables → Stored in password manager (1Password, Bitwarden)
- Railway settings → Export as JSON (manual, quarterly)

### 8.2 Disaster Recovery Plan

**RTO (Recovery Time Objective)**: 30 minutes

**RPO (Recovery Point Objective)**: 24 hours (database daily backups)

**Disaster Scenarios**:

| Scenario | Detection | Recovery Steps | RTO |
|----------|-----------|----------------|-----|
| **Railway outage** | Health check fails, Railway status page | Wait for Railway recovery, or migrate to Vercel/Fly.io | 2-4 hours |
| **Database corruption** | Query errors, data inconsistencies | Restore from Supabase backup | 30 minutes |
| **Redis outage** | Auth failures, cache misses | Restart Redis instance, or provision new instance | 15 minutes |
| **Firebase outage** | Auth failures | Wait for Firebase recovery (Google SLA: 99.95%) | 1-2 hours |
| **Accidental deployment of bad code** | 5xx errors, health check fails | Rollback to previous Railway deployment | 5 minutes |

**Recovery Procedure** (Database Restore):

```bash
# 1. Identify backup to restore
# Navigate to: Supabase Dashboard → Database → Backups
# Select: backup-2025-10-04-12-00 (example)

# 2. Initiate restore (Supabase UI)
# Click "Restore" → Confirm

# 3. Wait for restore to complete (~5-10 minutes for small DB)

# 4. Verify data integrity
psql $DATABASE_URL
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM patients;
# ... (verify expected counts)

# 5. Restart backend service (Railway)
# Railway Dashboard → Backend Service → Restart

# 6. Verify health check
curl https://backend-xxxxx.up.railway.app/health
# → 200 OK
```

---

## 9. Architecture Decision Records (ADRs)

### ADR-001: Railway as Deployment Platform

**Context**: Need managed platform-as-a-service for deploying FastAPI + React application with PostgreSQL and Redis dependencies.

**Decision**: Use Railway.app for deployment.

**Alternatives Considered**:
- Vercel (frontend-only, no backend support for FastAPI)
- Heroku (expensive, $25/month per dyno)
- Fly.io (complex networking, steep learning curve)
- AWS ECS (requires significant DevOps expertise)

**Consequences**:
- ✅ Pros:
  - Simple deployment (Git push to deploy)
  - Managed SSL/TLS certificates
  - Automatic health checks and restarts
  - Environment variable management
  - Built-in logging and metrics
  - Generous free tier for development
- ❌ Cons:
  - Vendor lock-in (Railway-specific configuration)
  - Limited customization (no Kubernetes control)
  - Regional availability (US-centric, ~100ms latency to Brazil)

**Status**: Accepted

---

### ADR-002: Supabase for PostgreSQL Database

**Context**: Need managed PostgreSQL database with Row-Level Security (RLS) support for multi-tenant data isolation.

**Decision**: Use Supabase managed PostgreSQL.

**Alternatives Considered**:
- Railway PostgreSQL plugin (limited features, no RLS)
- AWS RDS (expensive, complex setup)
- Self-hosted PostgreSQL (requires maintenance)

**Consequences**:
- ✅ Pros:
  - Built-in Row-Level Security (RLS)
  - Auto-backups and point-in-time recovery
  - Connection pooling (PgBouncer)
  - Storage buckets (avatars, documents)
  - Realtime subscriptions (future feature)
- ❌ Cons:
  - Additional service to manage (not on Railway)
  - Requires Supabase account and billing
  - Network latency (Supabase → Railway cross-cloud)

**Status**: Accepted

---

### ADR-003: Redis Cloud for Caching & Sessions

**Context**: Need distributed cache and session storage for multi-replica deployment. Local in-memory cache not suitable for horizontal scaling.

**Decision**: Use Redis Cloud managed service with SSL/TLS.

**Alternatives Considered**:
- Railway Redis plugin (no SSL/TLS support)
- AWS ElastiCache (expensive, complex VPC setup)
- In-memory cache (not distributed, lost on restart)

**Consequences**:
- ✅ Pros:
  - Distributed cache (shared across replicas)
  - SSL/TLS encryption in transit
  - High availability (automatic failover)
  - Database isolation (DB 0 for Celery, DB 1 for cache)
- ❌ Cons:
  - Additional service to manage
  - Network dependency (Redis Cloud → Railway)
  - Cost ($7/month for 250MB)

**Status**: Accepted

---

### ADR-004: Nginx Reverse Proxy for Frontend

**Context**: Frontend needs to proxy API requests to backend and handle SPA routing.

**Decision**: Use Nginx in frontend Docker container to proxy `/api/*` and `/ws` to backend.

**Alternatives Considered**:
- Client-side CORS (requires CORS headers on every backend response)
- Separate API domain (requires DNS management, SSL certificates)
- Next.js API routes (adds complexity, requires Node.js runtime)

**Consequences**:
- ✅ Pros:
  - No CORS issues (same origin for frontend and API)
  - WebSocket support (proxy upgrade headers)
  - SPA routing (fallback to index.html)
  - Static asset caching
- ❌ Cons:
  - Adds Nginx as dependency (more complexity)
  - Requires BACKEND_URL environment variable at runtime

**Status**: Accepted

---

### ADR-005: Runtime Configuration via /api/config

**Context**: Railway build arguments not reliably passed to Vite build. Frontend needs backend URL at runtime.

**Decision**: Backend serves `/api/config` endpoint with runtime environment variables in `VITE_*` format.

**Alternatives Considered**:
- Build-time injection (unreliable on Railway)
- Server-side rendering (SSR) with Next.js (too complex)
- Hardcode production URLs (not flexible)

**Consequences**:
- ✅ Pros:
  - Environment changes don't require rebuild
  - Single source of truth (backend)
  - Works across all deployment platforms
- ❌ Cons:
  - Extra HTTP request on app load
  - Network dependency for configuration
  - Config cached for 5 minutes (delays updates)

**Status**: Accepted

---

## 10. Troubleshooting Guide

### 10.1 Common Deployment Issues

#### Issue 1: Backend Health Check Fails

**Symptoms**:
- Railway shows service as "unhealthy"
- Logs show `ModuleNotFoundError` or import errors

**Diagnosis**:
```bash
# Check Railway logs
railway logs --service backend

# Look for:
# - "ModuleNotFoundError: No module named 'app'"
# - "ImportError: cannot import name 'X' from 'Y'"
```

**Solutions**:

1. **Wrong Root Directory**
   ```
   Railway Settings → Root Directory: backend-hormonia
   (NOT: . or backend-hormonia/app)
   ```

2. **Missing Dependencies**
   ```bash
   # Verify requirements.txt includes all dependencies
   pip freeze > requirements.txt
   git commit -am "Update requirements.txt"
   git push  # Triggers redeploy
   ```

3. **Database Connection Failure**
   ```bash
   # Verify DATABASE_URL is correct
   railway variables --service backend | grep DATABASE_URL

   # Test connection locally
   psql $DATABASE_URL -c "SELECT 1"
   ```

---

#### Issue 2: Frontend Shows "502 Bad Gateway"

**Symptoms**:
- Frontend loads, but `/api/*` requests fail with 502
- Nginx logs: `upstream prematurely closed connection`

**Diagnosis**:
```bash
# Check frontend logs
railway logs --service frontend

# Look for:
# - "nginx: [emerg] host not found in upstream"
# - "connect() failed (111: Connection refused)"
```

**Solutions**:

1. **BACKEND_URL Not Set**
   ```bash
   # Add environment variable
   railway variables --service frontend
   BACKEND_URL=https://backend-xxxxx.up.railway.app

   # Redeploy
   railway up --service frontend
   ```

2. **Backend Service Not Running**
   ```bash
   # Check backend health
   curl https://backend-xxxxx.up.railway.app/health

   # If fails, check backend logs
   railway logs --service backend
   ```

3. **Incorrect nginx.conf**
   ```nginx
   # Verify proxy_pass uses variable substitution
   location /api/ {
       proxy_pass ${BACKEND_URL};  # Correct
       # NOT: proxy_pass http://backend:8000;  # Wrong
   }
   ```

---

#### Issue 3: CORS Errors in Browser

**Symptoms**:
- Browser console: `Access to fetch at '...' has been blocked by CORS policy`
- API requests fail with status 0 or `opaque` response

**Diagnosis**:
```javascript
// In browser console
fetch('https://backend-xxxxx.up.railway.app/api/config')
  .then(r => r.text())
  .then(console.log)

// Look for Access-Control-Allow-Origin header
```

**Solutions**:

1. **Frontend Domain Not in ALLOWED_ORIGINS**
   ```bash
   # Backend environment variables
   ALLOWED_ORIGINS=["https://frontend-xxxxx.up.railway.app"]

   # Redeploy backend
   railway up --service backend
   ```

2. **Credentials Mismatch**
   ```python
   # Backend CORS middleware
   allow_credentials=True  # Must be True

   # Frontend fetch
   fetch(url, { credentials: 'include' })  # Must include
   ```

---

#### Issue 4: Firebase Auth Fails

**Symptoms**:
- Login fails with "Firebase initialization failed"
- Backend logs: `FirebaseError: Invalid service account`

**Diagnosis**:
```bash
# Check Firebase environment variables
railway variables --service backend | grep FIREBASE

# Verify format
FIREBASE_ADMIN_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----
```

**Solutions**:

1. **Private Key Formatting**
   ```bash
   # Ensure newlines are literal \n, not actual newlines
   FIREBASE_ADMIN_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nMIIE...\n-----END PRIVATE KEY-----"
   ```

2. **Missing Credentials**
   ```bash
   # All three required:
   FIREBASE_ADMIN_PROJECT_ID=your-project-id
   FIREBASE_ADMIN_PRIVATE_KEY=-----BEGIN...
   FIREBASE_ADMIN_CLIENT_EMAIL=firebase-adminsdk-...@project.iam.gserviceaccount.com
   ```

---

#### Issue 5: Redis Connection Timeout

**Symptoms**:
- Backend health check fails with `RedisConnectionError`
- Auth endpoints return 500 errors

**Diagnosis**:
```bash
# Test Redis connection
redis-cli -u $REDIS_URL ping
# → PONG (success) or timeout (failure)
```

**Solutions**:

1. **SSL/TLS Mismatch**
   ```bash
   # Verify SSL settings match Redis Cloud
   REDIS_URL=rediss://...  # Note: rediss:// (with 's')
   REDIS_SSL=true
   REDIS_SSL_CERT_REQS=required
   ```

2. **Firewall Rules**
   ```bash
   # Redis Cloud: Add Railway IP ranges to allowlist
   # Railway IPs: https://docs.railway.app/reference/public-api#ip-ranges
   ```

---

## 11. Appendix

### A. Environment Variables Reference

**Backend Critical Variables**:

| Variable | Type | Required | Example | Description |
|----------|------|----------|---------|-------------|
| `SECRET_KEY` | String | ✅ | `abc123...` (64+ chars) | JWT signing key |
| `DATABASE_URL` | URL | ✅ | `postgresql+psycopg://...` | PostgreSQL connection |
| `REDIS_URL` | URL | ✅ | `rediss://...` | Redis cache connection |
| `FIREBASE_ADMIN_PROJECT_ID` | String | ✅ | `hormonia-prod` | Firebase project ID |
| `FIREBASE_ADMIN_PRIVATE_KEY` | String | ✅ | `-----BEGIN...` | Firebase service account key |
| `ALLOWED_ORIGINS` | JSON | ✅ | `["https://..."]` | CORS allowed origins |

**Frontend Critical Variables**:

| Variable | Type | Required | Example | Description |
|----------|------|----------|---------|-------------|
| `BACKEND_URL` | URL | ✅ | `https://backend-xxxxx.up.railway.app` | Backend URL for nginx proxy |
| `VITE_FIREBASE_API_KEY` | String | ⚠️ | `AIza...` | Firebase client API key (public) |
| `VITE_SUPABASE_URL` | URL | ⚠️ | `https://xxx.supabase.co` | Supabase project URL (public) |

⚠️ = Optional if `/api/config` endpoint works

### B. Railway CLI Commands

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to project
railway link

# View logs
railway logs --service backend
railway logs --service frontend --tail

# Set environment variable
railway variables set BACKEND_URL=https://backend-xxxxx.up.railway.app --service frontend

# Deploy
railway up --service backend
railway up --service frontend

# SSH into service
railway shell --service backend

# View service status
railway status
```

### C. Monitoring Checklist

**Daily**:
- [ ] Check Railway dashboard for service health (green status)
- [ ] Review error logs for 5xx errors (`railway logs --service backend --tail`)
- [ ] Verify health check endpoints return 200 OK

**Weekly**:
- [ ] Review Sentry error reports (if configured)
- [ ] Check database connection pool usage (Supabase dashboard)
- [ ] Verify Redis memory usage (Redis Cloud dashboard)
- [ ] Review API response times (`X-Process-Time` headers)

**Monthly**:
- [ ] Test database backup restore
- [ ] Review Railway usage and costs
- [ ] Update dependencies (`pip list --outdated`, `npm outdated`)
- [ ] Rotate secret keys (if policy requires)

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-04
**Author**: System Architecture Designer (Claude)
**Next Review**: 2025-11-04
**Approved By**: _Pending_

---

## Document Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-10-04 | System Architect | Initial architecture design |
