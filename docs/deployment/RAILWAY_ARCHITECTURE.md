# Railway Deployment Architecture

**Version:** 2.0.0
**Last Updated:** 2025-10-04

---

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          RAILWAY PLATFORM                                │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                     PROJECT: clinica-hormonia                       │ │
│  │                                                                      │ │
│  │  ┌──────────────────┐              ┌──────────────────────────┐    │ │
│  │  │   Frontend       │              │      Backend API         │    │ │
│  │  │   (Nginx)        │              │      (FastAPI)           │    │ │
│  │  │                  │              │                          │    │ │
│  │  │  Port: 3000      │              │  Port: 8000              │    │ │
│  │  │  Workers: 1      │◄─────────────│  Workers: 4 (Gunicorn)   │    │ │
│  │  │                  │   Private    │                          │    │ │
│  │  │  Runtime Config  │   Network    │  Health: /api/v1/health  │    │ │
│  │  │  /api/config     │              │  Docs: /docs, /redoc     │    │ │
│  │  └──────────────────┘              └──────────────────────────┘    │ │
│  │         │                                      │                    │ │
│  │         │                                      │                    │ │
│  │         ▼                                      ▼                    │ │
│  │  ┌──────────────────────────────────────────────────────────────┐  │ │
│  │  │              Railway Redis Plugin (Managed)                   │  │ │
│  │  │                                                               │  │ │
│  │  │  Type: Redis 7.x                                              │  │ │
│  │  │  SSL: Enabled                                                 │  │ │
│  │  │  Port: 6379                                                   │  │ │
│  │  │  Usage: Sessions, Cache, Rate Limiting                        │  │ │
│  │  │  DB 0: Celery Broker | DB 1: Application Cache               │  │ │
│  │  └──────────────────────────────────────────────────────────────┘  │ │
│  │                                                                      │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  Private Network: *.railway.internal                                    │
│  Public URLs: *.up.railway.app                                          │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ HTTPS/PostgreSQL
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       EXTERNAL SERVICES (Cloud)                          │
│                                                                          │
│  ┌────────────────────┐         ┌────────────────────┐                 │
│  │   Supabase         │         │   Firebase         │                 │
│  │   (Database)       │         │   (Auth)           │                 │
│  │                    │         │                    │                 │
│  │  PostgreSQL 15.x   │         │  Auth Provider     │                 │
│  │  Port: 6543 (Pool) │         │  Admin SDK (BE)    │                 │
│  │  Storage: Avatars  │         │  Client SDK (FE)   │                 │
│  │  RLS: Enabled      │         │  Custom Claims     │                 │
│  └────────────────────┘         └────────────────────┘                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Service Communication Flow

### 1. User Request Flow (Frontend → Backend → Database)

```
┌──────┐      HTTPS       ┌──────────┐      /api/*      ┌─────────┐
│      │ ───────────────► │          │ ───────────────► │         │
│ User │                  │ Frontend │   (nginx proxy)  │ Backend │
│      │ ◄─────────────── │ (Nginx)  │ ◄─────────────── │ (API)   │
└──────┘      HTML/JS     └──────────┘      JSON        └─────────┘
                                │                              │
                                │ /api/config                  │
                                │ (runtime vars)               │
                                ▼                              ▼
                          ┌──────────┐                  ┌──────────┐
                          │ Firebase │                  │ Supabase │
                          │  Client  │                  │   DB     │
                          └──────────┘                  └──────────┘
```

### 2. Authentication Flow

```
┌──────────┐                                           ┌──────────┐
│ Frontend │                                           │ Backend  │
└────┬─────┘                                           └────┬─────┘
     │                                                      │
     │ 1. User Login Request                               │
     │ ──────────────────────────────────────────────────► │
     │                                                      │
     │                                                      │ 2. Validate
     │                                                      │ Firebase Token
     │                                                      │ (Admin SDK)
     │                                                      │
     │                                                      ▼
     │                                                 ┌─────────┐
     │                                                 │Firebase │
     │                                                 │  Auth   │
     │                                                 └─────────┘
     │                                                      │
     │ 3. JWT Token + User Data                            │
     │ ◄──────────────────────────────────────────────────┤
     │                                                      │
     │ 4. Store in LocalStorage                            │
     │    - access_token                                   │
     │    - refresh_token                                  │
     │                                                      │
     │ 5. Subsequent API Requests                          │
     │    Header: Authorization: Bearer <token>            │
     │ ──────────────────────────────────────────────────► │
     │                                                      │
     │                                                      │ 6. Verify JWT
     │                                                      │ Check Redis
     │                                                      │ Session
     │                                                      ▼
     │                                                 ┌─────────┐
     │                                                 │  Redis  │
     │                                                 │ Session │
     │                                                 └─────────┘
     │                                                      │
     │ 7. Authorized Response                              │
     │ ◄──────────────────────────────────────────────────┤
```

### 3. WebSocket Connection Flow

```
┌──────────┐                                           ┌──────────┐
│ Frontend │                                           │ Backend  │
└────┬─────┘                                           └────┬─────┘
     │                                                      │
     │ 1. Upgrade: websocket                               │
     │    Connection: Upgrade                              │
     │    Sec-WebSocket-Key: xxx                           │
     │ ──────────────────────────────────────────────────► │
     │                                                      │
     │ 2. 101 Switching Protocols                          │
     │ ◄──────────────────────────────────────────────────┤
     │                                                      │
     │ 3. Persistent Bi-directional Channel                │
     │ ◄─────────────────────────────────────────────────► │
     │                                                      │
     │ Real-time Events:                                   │
     │ - Patient updates                                   │
     │ - Notifications                                     │
     │ - Metrics streams                                   │
     │                                                      │
```

---

## Network Architecture

### Private Networking (Railway Internal)

```
┌───────────────────────────────────────────────────────────┐
│           Railway Private Network (Internal DNS)          │
│                                                           │
│  Service Discovery via: [service-name].railway.internal   │
│                                                           │
│  Example Hostnames:                                       │
│  • backend-hormonia.railway.internal:8000                 │
│  • frontend-hormonia.railway.internal:3000                │
│  • redis.railway.internal:6379                            │
│                                                           │
│  Benefits:                                                │
│  ✓ Low latency (~1-5ms internal)                         │
│  ✓ No bandwidth charges                                   │
│  ✓ Automatic service discovery                            │
│  ✓ Encrypted TLS by default                               │
│  ✓ No public internet exposure                            │
└───────────────────────────────────────────────────────────┘
```

### Public Access (External)

```
┌───────────────────────────────────────────────────────────┐
│              Railway Public URLs (HTTPS)                  │
│                                                           │
│  Auto-generated Domains:                                  │
│  • https://backend-[hash].up.railway.app                  │
│  • https://frontend-[hash].up.railway.app                 │
│                                                           │
│  Custom Domains (Optional):                               │
│  • https://api.yourdomain.com → backend                   │
│  • https://app.yourdomain.com → frontend                  │
│                                                           │
│  SSL/TLS:                                                 │
│  ✓ Automatic Let's Encrypt certificates                   │
│  ✓ Auto-renewal                                           │
│  ✓ HTTP → HTTPS redirect                                  │
└───────────────────────────────────────────────────────────┘
```

---

## Data Flow Architecture

### Request Processing Pipeline

```
1. HTTP Request
   ↓
2. Railway Load Balancer
   ↓
3. Nginx (Frontend Container)
   ├── Static Assets (HTML, CSS, JS) → Served Directly
   ├── /api/* → Proxied to Backend (Private Network)
   ├── /ws → WebSocket Upgrade → Backend
   └── /api/config → Runtime Config (Local File)
   ↓
4. FastAPI Backend
   ├── Authentication Middleware
   ├── CORS Middleware
   ├── Rate Limiting (Redis)
   ├── Route Handler
   └── Business Logic
   ↓
5. Data Layer
   ├── PostgreSQL (Supabase) → CRUD Operations
   ├── Redis → Cache, Sessions
   └── Firebase Admin → User Verification
   ↓
6. Response
   ├── JSON API Response
   ├── WebSocket Events
   └── Static Files
```

### Database Connection Pool

```
┌──────────────────────────────────────────────────────────┐
│              Backend API Instances (4 Workers)            │
│                                                           │
│  Worker 1 ─┐                                             │
│  Worker 2 ─┤                                             │
│  Worker 3 ─┼──► Connection Pool Manager                  │
│  Worker 4 ─┘     (SQLAlchemy)                            │
│                                                           │
│                  Pool Size: 30                            │
│                  Max Overflow: 40                         │
│                  Total Max: 70 connections                │
│                                                           │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  Supabase Connection  │
         │  Pooler (PgBouncer)   │
         │                       │
         │  Port: 6543           │
         │  Mode: Transaction    │
         │  Max: 200 connections │
         └───────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  PostgreSQL Database  │
         │  (Supabase Cloud)     │
         └───────────────────────┘
```

---

## Security Architecture

### Layer Security Model

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: Network Security                              │
│  • Railway Private Network (isolated)                   │
│  • TLS/SSL encryption (all traffic)                     │
│  • DDoS protection (Railway managed)                    │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 2: Application Security                          │
│  • CORS policy enforcement                              │
│  • JWT token validation                                 │
│  • Session management (Redis)                           │
│  • Rate limiting (per IP, per user)                     │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 3: Authentication & Authorization                │
│  • Firebase Admin SDK (backend)                         │
│  • Custom claims validation                             │
│  • Role-based access control (RBAC)                     │
│  • Domain allowlist (email validation)                  │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 4: Data Security                                 │
│  • Row Level Security (RLS) - Supabase                  │
│  • Encrypted connections (PostgreSQL SSL)               │
│  • Redis TLS/SSL                                        │
│  • Sensitive data encryption at rest                    │
└─────────────────────────────────────────────────────────┘
```

### Environment Variables Security

```
┌────────────────────────────────────────────────────────┐
│          Railway Environment Variables                  │
│                                                         │
│  Encrypted at Rest: ✓                                  │
│  Encrypted in Transit: ✓                               │
│  Access Control: Project members only                   │
│  Secret Variables: Hidden in logs                       │
│                                                         │
│  Critical Secrets:                                      │
│  • SECRET_KEY (JWT signing)                            │
│  • SUPABASE_SERVICE_ROLE_KEY                           │
│  • FIREBASE_ADMIN_PRIVATE_KEY                          │
│  • REDIS_URL (includes password)                       │
│                                                         │
│  Build-time Variables:                                  │
│  • Injected during build                               │
│  • Embedded in compiled code                           │
│  • Example: VITE_SUPABASE_URL                          │
│                                                         │
│  Runtime Variables:                                     │
│  • Loaded at container startup                         │
│  • Never exposed to client                             │
│  • Example: DATABASE_URL, SECRET_KEY                   │
└────────────────────────────────────────────────────────┘
```

---

## Scalability Architecture

### Horizontal Scaling (Future)

```
┌──────────────────────────────────────────────────────────┐
│             Railway Auto-Scaling (Pro Plan)              │
│                                                           │
│  Current: 1 instance per service                          │
│  Future: Auto-scale based on:                             │
│  • CPU usage > 80%                                        │
│  • Memory usage > 85%                                     │
│  • Request rate > threshold                               │
│                                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │ Backend  │  │ Backend  │  │ Backend  │               │
│  │ Instance │  │ Instance │  │ Instance │               │
│  │    1     │  │    2     │  │    N     │               │
│  └──────────┘  └──────────┘  └──────────┘               │
│       │              │              │                     │
│       └──────────────┴──────────────┘                     │
│                      │                                     │
│              Railway Load Balancer                        │
│                                                           │
│  Shared State:                                            │
│  • Redis (sessions, cache)                                │
│  • PostgreSQL (persistent data)                           │
│  • Supabase Storage (files)                               │
└──────────────────────────────────────────────────────────┘
```

### Caching Strategy

```
┌──────────────────────────────────────────────────────────┐
│                  Multi-Level Caching                      │
│                                                           │
│  Level 1: Browser Cache                                   │
│  • Static assets (1 year)                                │
│  • Service Worker (optional)                              │
│                                                           │
│  Level 2: CDN Cache (if using custom domain)              │
│  • Railway Edge Network                                   │
│  • CloudFlare (optional)                                  │
│                                                           │
│  Level 3: Nginx Cache                                     │
│  • API response cache (5 min)                            │
│  • Static file cache                                      │
│                                                           │
│  Level 4: Redis Cache (Application)                       │
│  • User sessions (30 min)                                │
│  • Database query results (5 min)                        │
│  • Rate limit counters (1 min)                           │
│                                                           │
│  Level 5: Database Query Cache                            │
│  • PostgreSQL query cache                                 │
│  • Materialized views                                     │
└──────────────────────────────────────────────────────────┘
```

---

## Monitoring & Observability

### Metrics Collection

```
┌──────────────────────────────────────────────────────────┐
│              Railway Built-in Metrics                     │
│                                                           │
│  Infrastructure Metrics:                                  │
│  • CPU Usage (%)                                         │
│  • Memory Usage (MB)                                     │
│  • Network I/O (MB/s)                                    │
│  • Disk I/O (MB/s)                                       │
│                                                           │
│  Application Metrics:                                     │
│  • Request Rate (req/s)                                  │
│  • Response Time (ms)                                    │
│  • Error Rate (%)                                        │
│  • Active Connections                                     │
│                                                           │
│  Database Metrics (Supabase):                             │
│  • Connection Pool Usage                                  │
│  • Query Performance                                      │
│  • Table Size Growth                                      │
│                                                           │
│  Redis Metrics:                                           │
│  • Memory Usage                                          │
│  • Hit/Miss Ratio                                        │
│  • Commands/sec                                          │
└──────────────────────────────────────────────────────────┘
```

### Logging Architecture

```
┌─────────────────────────────────────────────────────────┐
│                Application Logging                       │
│                                                          │
│  Frontend (Browser Console):                             │
│  • Client-side errors                                    │
│  • Performance metrics                                   │
│  • User interactions                                     │
│                                                          │
│  Frontend (Nginx):                                       │
│  • Access logs (requests)                                │
│  • Error logs (4xx, 5xx)                                │
│  • Proxy logs (backend calls)                           │
│                                                          │
│  Backend (FastAPI):                                      │
│  • Structured JSON logs                                  │
│  • Request/Response logs                                 │
│  • Error stack traces                                    │
│  • Audit logs (auth, data changes)                      │
│                                                          │
│  Aggregation:                                            │
│  • Railway Logs (centralized)                            │
│  • Optional: Sentry, LogRocket, DataDog                 │
└─────────────────────────────────────────────────────────┘
```

---

## Deployment Pipeline

### CI/CD Flow

```
┌──────────┐
│   Git    │
│  Commit  │
└────┬─────┘
     │
     ▼
┌─────────────────┐
│  GitHub Push    │
│  (main branch)  │
└────┬────────────┘
     │
     ▼
┌──────────────────────────────────────┐
│  Railway Webhook Trigger             │
│  • Detects changes                   │
│  • Reads railway.toml                │
│  • Identifies affected services      │
└────┬─────────────────────────────────┘
     │
     ├─────────────────┬────────────────┐
     ▼                 ▼                ▼
┌─────────┐    ┌──────────────┐   ┌─────────┐
│ Backend │    │   Frontend   │   │  Other  │
│  Build  │    │    Build     │   │ Services│
└────┬────┘    └──────┬───────┘   └────┬────┘
     │                │                 │
     │                │                 │
     ▼                ▼                 ▼
┌──────────────────────────────────────────┐
│  Build Process                           │
│  • Install dependencies                  │
│  • Run tests (if configured)            │
│  • Build Docker image                    │
│  • Push to Railway registry              │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│  Deployment                              │
│  • Pull new image                        │
│  • Health check old instance             │
│  • Start new instance                    │
│  • Health check new instance             │
│  • Switch traffic (zero downtime)        │
│  • Terminate old instance                │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│  Post-Deployment                         │
│  • Run migrations (if configured)        │
│  • Warm up caches                        │
│  • Send notifications                    │
└──────────────────────────────────────────┘
```

---

## Disaster Recovery

### Backup Strategy

```
┌────────────────────────────────────────────────────────┐
│               Backup & Recovery Strategy                │
│                                                         │
│  Database (Supabase):                                   │
│  • Automatic daily backups (7 days retention)          │
│  • Point-in-time recovery (Pro plan)                   │
│  • Manual exports (pg_dump)                            │
│                                                         │
│  Redis (Railway):                                       │
│  • Snapshots (if enabled)                              │
│  • Session data is ephemeral (acceptable loss)         │
│  • Cache can be rebuilt                                │
│                                                         │
│  Code & Configuration:                                  │
│  • Git repository (source of truth)                    │
│  • Environment variables (exported JSON)               │
│  • Railway project config (railway.toml)               │
│                                                         │
│  Files/Assets:                                          │
│  • Supabase Storage (built-in replication)             │
│  • CDN cache (automatic)                               │
│                                                         │
│  Recovery Time Objective (RTO): < 30 minutes            │
│  Recovery Point Objective (RPO): < 1 hour               │
└────────────────────────────────────────────────────────┘
```

---

## Performance Targets

### Service Level Objectives (SLOs)

```
┌────────────────────────────────────────────────────────┐
│                Performance Targets                      │
│                                                         │
│  Availability:                                          │
│  • Target: 99.9% uptime (8.76 hours/year downtime)     │
│  • Actual: Monitored via Railway metrics               │
│                                                         │
│  Response Time:                                         │
│  • API endpoints: p95 < 200ms                          │
│  • Database queries: p95 < 100ms                       │
│  • Page load: LCP < 2.5s                               │
│                                                         │
│  Throughput:                                            │
│  • API: > 1000 req/s (per instance)                    │
│  • WebSocket: > 500 concurrent connections             │
│                                                         │
│  Error Rate:                                            │
│  • 4xx errors: < 5%                                    │
│  • 5xx errors: < 0.1%                                  │
│                                                         │
│  Resource Utilization:                                  │
│  • CPU: < 70% average                                  │
│  • Memory: < 80% average                               │
│  • Database connections: < 80% pool size               │
└────────────────────────────────────────────────────────┘
```

---

## Cost Optimization

### Resource Allocation

```
┌────────────────────────────────────────────────────────┐
│              Railway Resource Costs                     │
│                                                         │
│  Frontend Service:                                      │
│  • CPU: 1 vCPU (shared)                                │
│  • Memory: 512 MB                                      │
│  • Estimated: $5-10/month                              │
│                                                         │
│  Backend Service:                                       │
│  • CPU: 2 vCPU (shared)                                │
│  • Memory: 2 GB                                        │
│  • Estimated: $20-30/month                             │
│                                                         │
│  Redis Plugin:                                          │
│  • Memory: 256 MB                                      │
│  • Estimated: $5/month                                 │
│                                                         │
│  External Services:                                     │
│  • Supabase: $0-25/month (Pro plan optional)           │
│  • Firebase: $0 (free tier)                            │
│                                                         │
│  Total Estimated: $30-70/month                         │
│                                                         │
│  Optimization Tips:                                     │
│  • Use private networking (saves bandwidth)            │
│  • Enable Redis caching (reduces DB queries)           │
│  • Optimize Docker images (faster builds)              │
│  • Use connection pooling (fewer DB connections)       │
└────────────────────────────────────────────────────────┘
```

---

## References

- **Railway Documentation:** [docs.railway.app](https://docs.railway.app)
- **Supabase Documentation:** [supabase.com/docs](https://supabase.com/docs)
- **Firebase Documentation:** [firebase.google.com/docs](https://firebase.google.com/docs)
- **FastAPI Documentation:** [fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- **Nginx Documentation:** [nginx.org/en/docs](https://nginx.org/en/docs)

---

**Document Version:** 2.0.0
**Last Updated:** 2025-10-04
**Review Schedule:** Quarterly
