# Railway Networking Architecture

## Overview

This document describes the networking architecture for the Clínica Oncológica Hormonia multi-service deployment on Railway.

## Network Topology

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Internet (HTTPS)                              │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
         ┌───────────────────────────────┐
         │   Railway Load Balancer        │
         │   (Auto SSL/TLS)               │
         └───────────┬───────────────────┘
                     │
         ┌───────────┴────────────┐
         ▼                        ▼
┌─────────────────┐      ┌──────────────────┐
│   Frontend      │      │   Backend API    │
│   (Nginx)       │      │   (FastAPI)      │
│   Port: 3000    │──────│   Port: 8000     │
│                 │      │                  │
│   Public URL:   │      │   Public URL:    │
│   frontend.     │      │   backend-api.   │
│   railway.app   │      │   railway.app    │
└─────────────────┘      └─────┬────────────┘
                                │
                                │ (Internal Network)
                                │
         ┌──────────────────────┼─────────────────────┐
         ▼                      ▼                     ▼
┌─────────────────┐   ┌──────────────┐    ┌──────────────────┐
│ Celery Worker   │   │  PostgreSQL  │    │     Redis        │
│ (Background)    │   │  Database    │    │     Cache        │
│                 │   │              │    │                  │
│ Internal only   │   │ Internal URL:│    │ Internal URL:    │
│ No public URL   │   │ postgres.    │    │ redis.railway.   │
│                 │   │ railway.     │    │ internal:6379    │
│                 │   │ internal     │    │                  │
└─────────────────┘   └──────────────┘    └──────────────────┘
         │
         ▼
┌─────────────────┐
│  Celery Beat    │
│  (Scheduler)    │
│                 │
│  Internal only  │
│  No public URL  │
└─────────────────┘
```

## Network Layers

### 1. Public Internet Layer

**Purpose:** External access to application services

**Characteristics:**
- HTTPS only (Railway auto-provisions SSL/TLS certificates)
- Custom domain support
- DDoS protection
- Rate limiting at edge

**Services with Public Access:**
- Frontend: `https://frontend.railway.app`
- Backend API: `https://backend-api.railway.app`

### 2. Railway Private Network

**Purpose:** Internal service-to-service communication

**Characteristics:**
- Lower latency (same datacenter)
- No egress charges
- Not accessible from internet
- Automatic service discovery

**Services:**
- PostgreSQL: `postgres.railway.internal:5432`
- Redis: `redis.railway.internal:6379`
- Backend API (internal): `backend-api.railway.internal:8000`

### 3. Container Network

**Purpose:** Intra-container communication

**Characteristics:**
- Container-to-container within same service
- Localhost communication
- Not accessible outside container

## Service Communication Patterns

### Frontend → Backend (Public Network)

```javascript
// Frontend makes HTTPS requests to public backend URL
const apiClient = axios.create({
  baseURL: 'https://backend-api.railway.app/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// WebSocket connection
const ws = new WebSocket('wss://backend-api.railway.app/ws');
```

**Why Public Network?**
- Frontend runs in user's browser
- Cannot access Railway's internal network
- Requires public HTTPS endpoint

**Security:**
- CORS configured on backend to allow frontend origin
- JWT authentication for API requests
- Rate limiting on public endpoints

### Backend → Database (Private Network)

```python
# Backend connects to PostgreSQL using internal networking
DATABASE_URL = "postgresql+psycopg://postgres.railway.internal:5432/railway"

# Benefits:
# - No egress costs
# - Lower latency (~1ms vs ~50ms)
# - More secure (not exposed to internet)
```

**Why Private Network?**
- Database should never be publicly accessible
- Faster connection (same datacenter)
- Cost savings (no egress fees)

### Backend → Redis (Private Network)

```python
# Backend connects to Redis using internal networking
REDIS_URL = "redis://redis.railway.internal:6379"

# Celery also uses same Redis URL
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
```

**Why Private Network?**
- Cache/session data should be internal
- High-frequency access (performance critical)
- No need for external access

### Celery Worker → Backend/Database (Private Network)

```python
# Celery worker shares same database and Redis URLs as backend
DATABASE_URL = "postgresql+psycopg://postgres.railway.internal:5432/railway"
REDIS_URL = "redis://redis.railway.internal:6379"

# Workers can communicate with backend via internal HTTP if needed
BACKEND_INTERNAL_URL = "http://backend-api.railway.internal:8000"
```

**Why Private Network?**
- Background tasks don't need public access
- Shares database with backend API
- Uses Redis for task queue

## Port Allocation

### Public Ports (Railway-Assigned)

| Service | Internal Port | Public Port | URL |
|---------|--------------|-------------|-----|
| Frontend | 3000 | Dynamic (HTTPS) | `https://frontend.railway.app` |
| Backend API | 8000 | Dynamic (HTTPS) | `https://backend-api.railway.app` |

**Note:** Railway dynamically assigns public ports and maps them to service ports.

### Internal Ports (Fixed)

| Service | Port | Protocol | Access |
|---------|------|----------|--------|
| PostgreSQL | 5432 | TCP | Internal only |
| Redis | 6379 | TCP | Internal only |
| Celery Worker | N/A | N/A | No network service |
| Celery Beat | N/A | N/A | No network service |

## CORS Configuration

### Backend CORS Settings

```python
# app/main.py
from fastapi.middleware.cors import CORSMiddleware

# Production frontend URL (Railway or custom domain)
frontend_url = os.getenv("FRONTEND_URL", "https://frontend.railway.app")

# Configure CORS to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        frontend_url,
        "https://app.yourdomain.com",  # Custom domain
        "http://localhost:5173",        # Local development
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)
```

**Why Specific Origins?**
- Security: Prevents unauthorized domains from accessing API
- Credentials: Allows cookies/auth headers
- Compliance: Meets security best practices

## DNS Configuration

### Railway Subdomains (Default)

**Format:** `<service-name>.up.railway.app`

```
Frontend:  frontend.up.railway.app
Backend:   backend-api.up.railway.app
```

**Characteristics:**
- Auto-generated SSL/TLS certificates
- Automatic DNS management
- No configuration required

### Custom Domains

**Frontend:** `app.yourdomain.com`
```
CNAME: app.yourdomain.com → frontend.up.railway.app
```

**Backend:** `api.yourdomain.com`
```
CNAME: api.yourdomain.com → backend-api.up.railway.app
```

**Configuration Steps:**
1. Add custom domain in Railway dashboard
2. Update DNS records with CNAME
3. Wait for SSL certificate provisioning (~5-10 minutes)
4. Update environment variables with new URLs

## Security Architecture

### Network Security Layers

1. **Edge Layer (Railway)**
   - DDoS protection
   - Rate limiting
   - SSL/TLS termination
   - WAF (Web Application Firewall)

2. **Application Layer (Backend)**
   - CORS validation
   - JWT authentication
   - Rate limiting (per-user, per-IP)
   - Input validation

3. **Data Layer (Database)**
   - Private network only
   - Connection pooling
   - Encrypted at rest
   - Automated backups

### Authentication Flow

```
┌─────────┐                  ┌──────────┐                ┌──────────┐
│ Browser │                  │ Frontend │                │ Backend  │
└────┬────┘                  └────┬─────┘                └────┬─────┘
     │                            │                           │
     │  1. Visit app              │                           │
     ├────────────────────────────▶                           │
     │                            │                           │
     │  2. Request login          │                           │
     │  (username/password)       │                           │
     ├────────────────────────────▶  3. POST /api/v1/login   │
     │                            ├───────────────────────────▶
     │                            │                           │
     │                            │  4. Validate credentials  │
     │                            │     (PostgreSQL)          │
     │                            │                           │
     │                            │  5. Generate JWT token    │
     │                            │◀───────────────────────────
     │                            │                           │
     │  6. Store JWT in memory    │                           │
     │◀────────────────────────────                           │
     │                            │                           │
     │  7. Subsequent requests    │                           │
     │  (with JWT in header)      │                           │
     ├────────────────────────────▶  8. API calls with JWT    │
     │                            ├───────────────────────────▶
     │                            │                           │
     │                            │  9. Verify JWT signature  │
     │                            │                           │
     │                            │  10. Return protected data│
     │                            │◀───────────────────────────
     │  11. Display data          │                           │
     │◀────────────────────────────                           │
```

## Load Balancing & Scaling

### Horizontal Scaling

**Backend API:**
```bash
# Scale to 3 replicas
railway service scale --replicas 3 backend-api
```

**Railway Auto-Balancing:**
- Round-robin load balancing
- Automatic health check integration
- Graceful shutdown handling

**Frontend:**
```bash
# Scale to 2 replicas
railway service scale --replicas 2 frontend
```

**Celery Worker:**
```bash
# Scale to 4 workers for background tasks
railway service scale --replicas 4 celery-worker
```

**Celery Beat:**
- **MUST have only 1 replica** (scheduler should not duplicate)
- Railway ensures single instance

### Session Persistence

**Strategy:** Redis-based sessions (shared across all replicas)

```python
# app/core/session.py
from redis import Redis

# All backend replicas connect to same Redis instance
redis_client = Redis.from_url(os.getenv("REDIS_URL"))

# Session stored in Redis, accessible by any backend replica
def store_session(session_id: str, data: dict):
    redis_client.setex(f"session:{session_id}", 3600, json.dumps(data))
```

## Monitoring & Observability

### Health Check Endpoints

**Backend API:**
```bash
GET https://backend-api.railway.app/health

Response:
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "timestamp": "2025-10-04T22:00:00Z"
}
```

**Frontend:**
```bash
GET https://frontend.railway.app/health

Response: 200 OK
```

### Network Metrics

**Track:**
- Request latency (p50, p95, p99)
- Error rates (4xx, 5xx)
- Throughput (requests/sec)
- Connection pool utilization

**Tools:**
- Railway built-in metrics
- Custom logging (structlog)
- APM (Sentry, Datadog)

## Troubleshooting

### Issue: Frontend can't reach Backend

**Check:**
1. CORS configuration in backend
2. Frontend `VITE_API_URL` environment variable
3. Backend health endpoint: `curl https://backend-api.railway.app/health`
4. Browser console for CORS errors

### Issue: Backend can't connect to Database

**Check:**
1. `DATABASE_URL` environment variable
2. Database plugin enabled in Railway
3. Private networking enabled
4. Connection string format: `postgresql+psycopg://...`

### Issue: Celery tasks not processing

**Check:**
1. `REDIS_URL` matches between backend and worker
2. Celery worker logs: `railway logs --service celery-worker`
3. Redis connection: `redis-cli -u $REDIS_URL ping`

## Best Practices

1. **Always use private network for internal services**
   - Database, Redis, background workers
   - Lower cost, better security

2. **Use public network only when necessary**
   - Frontend access
   - External webhooks
   - Public APIs

3. **Configure CORS restrictively**
   - Specify exact origins (no wildcards)
   - Enable credentials only when needed

4. **Implement health checks**
   - Railway uses them for routing
   - Improves reliability

5. **Monitor network metrics**
   - Track latency and errors
   - Set up alerts for anomalies

6. **Use environment variables for URLs**
   - Never hardcode URLs
   - Easy to update for different environments

## Reference Links

- Railway Networking: https://docs.railway.app/reference/private-networking
- Railway Custom Domains: https://docs.railway.app/reference/domains
- Railway Health Checks: https://docs.railway.app/reference/healthchecks
