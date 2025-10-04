# System Integration Architecture - Clínica Oncológica v02

**Data**: 2025-10-04
**Status**: Análise Completa
**Versão**: 2.0.0

---

## Executive Summary

Este documento mapeia a arquitetura completa de integração entre Frontend, Backend e Quiz Interface, identificando pontos de integração, configurações de segurança, estratégias de cache, e possíveis vulnerabilidades arquiteturais.

---

## 1. Fluxo de Dados Completo

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           User Browser (HTTPS)                          │
└────────────────────────┬────────────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Frontend   │  │   Backend   │  │Quiz Interface│
│  (Railway)  │  │  (Railway)  │  │  (Railway)   │
│  Port 3000  │  │  Port 8000  │  │  Port 3000   │
│             │  │             │  │              │
│ nginx:alpine│  │python:3.13  │  │ node:20      │
└──────┬──────┘  └──────┬──────┘  └──────┬───────┘
       │                │                │
       │  REST API      │  WebSocket     │  Secure Link
       │  /api/v1/*     │  /ws           │  /quiz/monthly/:token
       │                │                │
       └────────────────┼────────────────┘
                        │
                        ▼
           ┌────────────────────────┐
           │   Supabase Cloud       │
           │   PostgreSQL + Storage │
           │                        │
           │   ┌──────────────────┐ │
           │   │ Tables:          │ │
           │   │ - users          │ │
           │   │ - patients       │ │
           │   │ - monthly_quiz   │ │
           │   │ - flow_sessions  │ │
           │   └──────────────────┘ │
           └────────────┬───────────┘
                        │
                        ▼
           ┌────────────────────────┐
           │   Firebase Auth        │
           │   Admin SDK            │
           │                        │
           │   - User Management    │
           │   - Token Validation   │
           │   - Custom Claims      │
           └────────────────────────┘
                        │
                        ▼
           ┌────────────────────────┐
           │   Redis Cloud          │
           │   (SSL/TLS Required)   │
           │                        │
           │   DB 0: Celery Broker  │
           │   DB 1: App Cache      │
           └────────────────────────┘
                        │
                        ▼
           ┌────────────────────────┐
           │   Evolution API        │
           │   WhatsApp Integration │
           │                        │
           │   - Message Sending    │
           │   - Webhook Events     │
           └────────────────────────┘
```

---

## 2. Pontos de Integração Detalhados

### 2.1 Frontend ↔️ Backend

#### Protocol & Transport
- **Protocol**: REST API over HTTPS
- **Base Paths**:
  - `/api/v1/*` - Authenticated endpoints
  - `/api/config` - Public runtime configuration
  - `/health` - Health check
- **WebSocket**: `/ws` - Real-time communication
- **Authentication**: Firebase JWT tokens via `Authorization: Bearer <token>`

#### CORS Configuration
**Backend** (`app/config.py` lines 202-257):
```python
ALLOWED_ORIGINS = [
    # Local Development
    "http://localhost:3000", "http://localhost:5173",
    "http://127.0.0.1:3000", "http://127.0.0.1:5173",

    # Production Railway URLs (Explicit - No Wildcards)
    "https://clinica-oncologica-v02-production.up.railway.app",
    "https://interface-quiz-production.up.railway.app",
    "https://hormonia-frontend.railway.app",
    "https://frontend-v2.railway.app"
]
```

**Custom CORS Middleware** (`app/middleware/custom_cors.py`):
- **Pattern Matching**: Wildcard support (`*.railway.app`) ONLY in dev/staging
- **Production**: Explicit URLs only for security
- **WebSocket Headers**: Full support for `Sec-WebSocket-*` headers

#### Security Headers
**CORS Headers** (lines 104-141):
```python
allow_credentials=True
allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
allow_headers=[
    "Authorization", "Content-Type",
    "X-Quiz-Token", "X-Patient-ID",  # Quiz-specific
    "Sec-WebSocket-Protocol", "Upgrade", "Connection"  # WebSocket
]
expose_headers=[
    "X-Request-ID", "X-Quiz-Session-ID",
    "X-RateLimit-Limit", "X-Query-Count"
]
```

**Frontend nginx** (`nginx.conf` lines 14-18):
```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

#### Configuration Loading Strategy
**Runtime Config Endpoint** (`/api/config`):
- **Purpose**: Solves Railway build-time environment variable injection issues
- **Security**: PUBLIC endpoint with NO sensitive data
- **Flow**:
  1. Frontend loads → Fetches `/api/config`
  2. Backend returns runtime environment variables in `VITE_*` format
  3. Frontend caches config for 5 minutes (`Cache-Control: max-age=300`)

**Frontend Config Loading** (`src/config.ts` + `src/lib/runtime-config.ts`):
```typescript
// Priority chain:
1. /api/config endpoint (runtime)
2. window.__ENV_CONFIG__ (server-injected)
3. import.meta.env (build-time)
4. Production fallback defaults
```

#### Request Flow
```
User Action → Frontend Component
    ↓ (fetch/axios)
    API Client (src/lib/api-client.ts)
    ↓ (HTTPS, Authorization header)
    Nginx Reverse Proxy (frontend/nginx.conf)
    ↓ (proxy_pass $BACKEND_URL)
    Backend FastAPI (app/main.py)
    ↓ (Middleware chain)
    1. PatternCORSMiddleware
    2. EnhancedCompressionMiddleware
    3. EnhancedRateLimitMiddleware
    4. EnhancedSecurityMiddleware
    5. QueryPerformanceMiddleware
    6. MonitoringMiddleware
    ↓ (Route handling)
    Router (app/api/v1/*)
    ↓ (Business logic)
    Service Layer
    ↓ (Database queries)
    Supabase PostgreSQL
```

---

### 2.2 Frontend ↔️ Quiz Interface

#### Integration Type
- **Method**: Secure redirect with JWT token
- **URL Pattern**: `{QUIZ_BASE_URL}/quiz/monthly/:token`
- **Token Generation**: Backend endpoint `/api/v1/monthly-quiz/generate-link`

#### Security Model
**Token Configuration** (`app/config.py` lines 278-293):
```python
MONTHLY_QUIZ_VIA_LINK = True  # Link-based (not WhatsApp conversational)
MONTHLY_QUIZ_BASE_URL = "http://localhost:3001"  # Dev default
MONTHLY_QUIZ_TOKEN_SECRET = "your-secret"  # CHANGE IN PRODUCTION
MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS = 72  # 3 days
```

**Token Validation Flow**:
1. Backend generates JWT token with patient ID + quiz metadata
2. Frontend redirects user to Quiz Interface with token in URL
3. Quiz Interface validates token against backend `/api/v1/monthly-quiz/validate-token`
4. Quiz Interface fetches questions via backend API
5. Quiz submissions POST to backend `/api/v1/monthly-quiz/submit`

#### Cross-Origin Considerations
- Quiz Interface is on different Railway domain
- CORS must allow Quiz domain in `ALLOWED_ORIGINS`
- Token-based authentication bypasses session cookies

---

### 2.3 Backend ↔️ Supabase Database

#### Connection Configuration
**Database URL** (`app/config.py` line 135):
```python
DATABASE_URL = "postgresql+psycopg://postgres:password@host.supabase.co:6543/postgres"
# IMPORTANT: psycopg v3 for Python 3.13 compatibility
```

**Connection Pool Settings** (lines 69-131):
```python
# Standard Pool
DB_POOL_SIZE = 30
DB_MAX_OVERFLOW = 40

# RLS Pool (Row-Level Security)
RLS_POOL_SIZE = 30
RLS_POOL_MAX_OVERFLOW = 50
```

#### Authentication Strategy
**Supabase Auth vs Firebase Auth**:
- **Supabase**: Used for PostgreSQL database + Storage (avatars)
- **Firebase**: Primary authentication provider
- **Backend**: Validates Firebase JWT, then queries Supabase DB

**RLS (Row-Level Security)** Configuration (lines 89-123):
```python
SUPABASE_USE_SERVICE_ROLE = False  # Use user JWT for RLS
SUPABASE_BYPASS_RLS = False  # Enforce RLS policies
RLS_ENABLE_AUDIT_LOGGING = True
RLS_DEFAULT_ROLE = "authenticated"
```

#### Database Access Pattern
```
Backend Service
    ↓ (Firebase JWT validation)
    Auth Dependency
    ↓ (Extract user_id)
    RLS Context Manager
    ↓ (Set PostgreSQL role + user_id)
    Supabase Client (with RLS)
    ↓ (Execute queries with RLS enforcement)
    PostgreSQL Tables
```

---

### 2.4 Backend ↔️ Firebase Auth

#### Firebase Admin SDK Configuration
**Environment Variables** (`.env.example` lines 33-37):
```bash
FIREBASE_ADMIN_PROJECT_ID=your-project-id
FIREBASE_ADMIN_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
FIREBASE_ADMIN_CLIENT_EMAIL=firebase-adminsdk-xxxxx@your-project.iam.gserviceaccount.com
```

**Security Policies** (`app/config.py` lines 49-86):
```python
# Domain Allowlist for Auto-Provisioning
FIREBASE_ALLOWED_DOMAINS = []  # JSON array: ["oncologia.com", "hospital.local"]

# Public Domain Blocking
FIREBASE_BLOCK_PUBLIC_DOMAINS = True
FIREBASE_PUBLIC_DOMAINS_BLOCKLIST = [
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com"
]

# Role Enforcement
FIREBASE_REQUIRE_CUSTOM_CLAIMS = True
FIREBASE_ALLOWED_ROLES = ["admin", "super_admin", "doctor", "medico"]
```

#### Token Validation Flow
```
Frontend Login → Firebase Auth SDK
    ↓ (ID Token)
    Backend API Request
    ↓ (Authorization: Bearer <token>)
    Firebase Admin SDK verify_id_token()
    ↓ (Validate signature, expiry, custom claims)
    Extract uid, email, role
    ↓ (Check if user exists in local DB)
    Auto-Provision User (if enabled)
    ↓ (Return user object)
    Request Context (current_user dependency)
```

---

### 2.5 Backend ↔️ Redis

#### Connection Configuration
**Redis URLs** (`.env.example` lines 84-101):
```bash
# Main Cache (DB 1)
REDIS_URL=rediss://default:password@host:6379/1
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required

# Celery Broker (DB 0)
CELERY_BROKER_URL=rediss://default:password@host:6379/0
CELERY_RESULT_BACKEND=rediss://default:password@host:6379/0
```

**Database Isolation** (`app/config.py` lines 149-151):
```python
REDIS_ENABLE_DB_ISOLATION = True
REDIS_CACHE_DB = 1  # Application cache
REDIS_BROKER_DB = 0  # Celery task queue
```

#### Usage Patterns
- **Session Storage**: User sessions, JWT refresh tokens
- **Rate Limiting**: Request throttling per IP/user
- **Caching**: API responses, database query results
- **Celery**: Task queue for async jobs (quiz notifications, reports)

**Critical Dependency**:
- Redis is **REQUIRED** for authentication (session storage)
- `AuthService` raises `RuntimeError` if Redis unavailable

---

### 2.6 Backend ↔️ Evolution API (WhatsApp)

#### Configuration
**Environment Variables** (`.env.example` lines 125-134):
```bash
ENABLE_EVOLUTION=true
EVOLUTION_API_URL=https://evolution-api.example.com
EVOLUTION_INSTANCE_NAME=clinica_oncologica
EVOLUTION_API_KEY=your-api-key
EVOLUTION_WEBHOOK_SECRET=your-webhook-secret
EVOLUTION_WEBHOOK_URL=https://backend.railway.app/webhooks/whatsapp/evolution/clinica_oncologica
```

#### Integration Points
1. **Outbound Messages**: Backend → Evolution API
   - Send quiz notifications
   - Send appointment reminders
   - Send flow responses

2. **Inbound Webhooks**: Evolution API → Backend
   - Receive user messages
   - Receive message status updates
   - Trigger conversational flows

---

## 3. Security Analysis

### 3.1 Security Headers Compliance

| Header | Frontend (nginx) | Backend (FastAPI) | Status |
|--------|------------------|-------------------|--------|
| `X-Frame-Options` | ✅ SAMEORIGIN | ❌ Not set | ⚠️ Partial |
| `X-Content-Type-Options` | ✅ nosniff | ✅ Via middleware | ✅ Complete |
| `X-XSS-Protection` | ✅ 1; mode=block | ✅ Via middleware | ✅ Complete |
| `Referrer-Policy` | ✅ strict-origin-when-cross-origin | ❌ Not set | ⚠️ Partial |
| `Content-Security-Policy` | ❌ Not set | ❌ Not set | ❌ Missing |
| `Strict-Transport-Security` | ❌ Not set | ❌ Not set | ⚠️ Railway handles |

**Recommendations**:
1. Add CSP header to prevent XSS attacks
2. Add HSTS header (or verify Railway provides it)
3. Set `X-Frame-Options` on backend responses

---

### 3.2 CORS Security Assessment

#### Current Configuration
✅ **Strengths**:
- Explicit origin whitelisting in production
- No wildcard origins in production mode
- WebSocket header support
- Credentials allowed (required for auth)

⚠️ **Weaknesses**:
- `/api/config` endpoint allows `Access-Control-Allow-Origin: *` (PUBLIC)
  - Mitigation: No sensitive data in response
- Development mode allows wildcard patterns
  - Mitigation: Only enabled via `ENVIRONMENT=development`

#### CORS Preflight Caching
```python
max_age=86400  # 24 hours for standard endpoints
max_age=3600   # 1 hour for quiz endpoints
```

**Security Note**: Long `max_age` reduces preflight requests but may delay CORS policy updates.

---

### 3.3 Authentication & Authorization

#### Token Flow Security
```
1. User Login → Firebase Auth → ID Token (JWT)
2. Frontend stores token → localStorage/sessionStorage
3. API Request → Authorization: Bearer <token>
4. Backend verifies token → Firebase Admin SDK
5. Extract claims → user_id, role, email
6. Database query → Supabase (with RLS)
```

**Security Measures**:
- ✅ Token expiry: 30 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`)
- ✅ Refresh token: 7 days (`REFRESH_TOKEN_EXPIRE_DAYS`)
- ✅ Custom claims validation (role enforcement)
- ✅ Domain allowlist for user provisioning
- ⚠️ Token storage in localStorage (XSS risk)

**Recommendations**:
1. Consider httpOnly cookies for token storage
2. Implement token rotation on refresh
3. Add device fingerprinting for token binding

---

### 3.4 Quiz Token Security

#### Token Generation
**Algorithm**: HS256 JWT
**Secret**: `MONTHLY_QUIZ_TOKEN_SECRET` (separate from main `SECRET_KEY`)
**Expiry**: 72 hours (configurable)

**Payload**:
```json
{
  "patient_id": "uuid",
  "quiz_id": "uuid",
  "generated_at": "timestamp",
  "exp": "expiry_timestamp"
}
```

**Security Concerns**:
- ✅ Separate secret from main application
- ✅ Short expiry window (3 days)
- ⚠️ Token in URL (visible in browser history, logs)
- ❌ No single-use enforcement (token can be reused)

**Recommendations**:
1. Implement single-use token validation
2. Track token usage in database
3. Consider POST-based token exchange instead of URL parameter

---

## 4. Cache Strategy

### 4.1 Frontend Caching

#### Nginx Static Assets (`nginx.conf` lines 21-30)
```nginx
# Cache static assets for 1 year (immutable)
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}

# Don't cache HTML (SPA routing)
location ~* \.(html)$ {
    expires -1;
    add_header Cache-Control "no-cache, no-store, must-revalidate";
}
```

#### Runtime Config Caching (`/api/config`)
```
Cache-Control: public, max-age=300  # 5 minutes
```

**Rationale**: Balance between fast config loading and environment updates.

---

### 4.2 Backend Caching

#### Redis Cache Strategy
- **Query Results**: Cache expensive database queries
- **Session Data**: User sessions with TTL
- **Rate Limiting**: Request counters per IP/user
- **API Responses**: Cacheable GET endpoints

**Cache Invalidation**:
- Time-based expiry (TTL)
- Event-based invalidation (on data mutation)
- Manual cache flush (admin endpoint)

---

### 4.3 Database Query Performance

#### Query Monitoring Middleware
**File**: `app/middleware/query_logger.py`

**Headers Exposed**:
```python
X-Query-Count: <number>      # Total queries in request
X-DB-Time-Ms: <milliseconds> # Total DB time
X-Request-Duration: <ms>     # Total request time
```

**Slow Query Threshold**: 1 second (configurable)

---

## 5. Error Boundaries & Resilience

### 5.1 Frontend Error Handling

#### Error Boundary Strategy
**File**: `src/components/ErrorBoundary.tsx` (inferred)

**Levels**:
1. **Component-Level**: Catch errors in individual components
2. **Route-Level**: Catch errors in route loading
3. **Global**: Fallback UI for uncaught errors

**Integration with Monitoring**:
- Errors reported to Sentry (if `VITE_SENTRY_DSN` configured)
- User-friendly error messages displayed
- Technical details logged to console (dev mode only)

---

### 5.2 Backend Resilience

#### Middleware Chain (Execution Order)
```python
# app/core/middleware_setup.py (lines 38-143)
1. MonitoringMiddleware       # APM, metrics collection
2. QueryPerformanceMiddleware # Database monitoring
3. RequestLoggingMiddleware   # Debug logging (dev only)
4. EnhancedSecurityMiddleware # Input sanitization, headers
5. EnhancedRateLimitMiddleware # Request throttling
6. EnhancedCompressionMiddleware # Response compression
7. PatternCORSMiddleware      # CORS validation (executes first)
```

#### Circuit Breakers
**Services with Resilience Patterns**:
- Evolution API calls: Retry with exponential backoff
- Redis connections: Failover to in-memory cache
- Gemini AI calls: Fallback to original message
- Database queries: Connection pool with overflow

---

### 5.3 Health Checks

#### Frontend Health Check
**Endpoint**: `/health`
**Implementation**: `nginx.conf` line 33-37
```nginx
location /health {
    access_log off;
    return 200 "healthy\n";
    add_header Content-Type text/plain;
}
```

**Docker Health Check** (`Dockerfile` lines 113-114):
```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT:-3000}/health || exit 1
```

#### Backend Health Check
**Endpoint**: `/health`
**Implementation**: `app/main.py` (inferred from standard pattern)

**Docker Health Check** (`Dockerfile` lines 49-50):
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1
```

#### Quiz Interface Health Check
**Endpoint**: `/api/health`
**Docker Health Check** (`Dockerfile` lines 35-36):
```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:${PORT:-3000}/api/health || exit 1
```

---

## 6. Identified Architectural Issues

### 6.1 Critical Issues

#### 1. **Missing Content Security Policy (CSP)**
**Severity**: HIGH
**Impact**: XSS vulnerability, code injection risk
**Recommendation**: Implement CSP header on both frontend and backend

**Proposed CSP**:
```nginx
# Frontend nginx.conf
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https://*.railway.app https://*.supabase.co https://*.googleapis.com wss://*.railway.app; frame-ancestors 'none';" always;
```

#### 2. **Quiz Token in URL Parameter**
**Severity**: MEDIUM
**Impact**: Token exposure in browser history, server logs, referrer headers
**Recommendation**: Implement POST-based token exchange

**Proposed Flow**:
```
1. Backend generates token → Store in Redis with 5-minute TTL
2. Frontend redirects to Quiz Interface with token_id (not token)
3. Quiz Interface exchanges token_id for actual token via POST
4. Backend validates token_id, returns token, deletes from Redis
```

#### 3. **No Rate Limiting on /api/config**
**Severity**: LOW
**Impact**: Potential DoS target (public endpoint)
**Recommendation**: Add lightweight rate limiting

```python
# 100 requests per minute per IP for /api/config
@router.get("/config")
@limiter.limit("100/minute")
async def get_public_config(request: Request):
    ...
```

---

### 6.2 Performance Bottlenecks

#### 1. **Nginx Proxy Buffering for WebSocket**
**File**: `nginx.conf` lines 73-74
```nginx
proxy_buffering off;
proxy_request_buffering off;
```

**Issue**: Disabled buffering for all `/api/*` routes, not just WebSocket.
**Impact**: Reduced performance for regular HTTP requests.
**Recommendation**: Create separate location block for WebSocket only.

**Proposed Fix**:
```nginx
# Regular API requests (with buffering)
location /api/ {
    proxy_pass ${BACKEND_URL};
    proxy_buffering on;  # Enable for better performance
    ...
}

# WebSocket requests (no buffering)
location /ws {
    proxy_pass ${BACKEND_URL};
    proxy_buffering off;
    proxy_request_buffering off;
    ...
}
```

#### 2. **Database Connection Pool Sizing**
**Current Settings**:
```python
DB_POOL_SIZE = 30
DB_MAX_OVERFLOW = 40
```

**Issue**: High pool size may exhaust Supabase connection limits.
**Recommendation**: Monitor connection usage and adjust based on load.

#### 3. **CORS Preflight Cache Too Long**
**Current**: `max_age=86400` (24 hours)
**Issue**: Policy changes take 24 hours to propagate
**Recommendation**: Reduce to 1 hour in production

```python
max_age=3600  # 1 hour
```

---

### 6.3 Single Points of Failure

#### 1. **Redis Dependency**
**Issue**: Authentication requires Redis (session storage)
**Impact**: Redis outage = complete authentication failure
**Mitigation**: Implement fallback to in-memory cache or database-backed sessions

#### 2. **Firebase Auth Dependency**
**Issue**: Firebase outage = no user authentication
**Impact**: Complete system unavailability
**Mitigation**:
- Implement fallback authentication mechanism
- Cache Firebase tokens for short-term validation

#### 3. **Supabase Database**
**Issue**: Single database instance (no replica)
**Impact**: Database outage = system down
**Mitigation**: Supabase handles replication internally, but consider:
- Read replicas for heavy read workloads
- Connection pooling (PgBouncer)

---

## 7. Deployment Architecture (Railway)

### 7.1 Service Topology

```
Railway Project: clinica-oncologica-v02
│
├── Backend Service (backend-production-e0bd)
│   ├── URL: https://backend-production-e0bd.up.railway.app
│   ├── Build: Python 3.13 Docker image
│   ├── Start Command: gunicorn (4 workers, uvicorn)
│   ├── Health Check: /health
│   └── Environment Variables: 50+ (database, firebase, redis, etc.)
│
├── Frontend Service (frontend-production-18bb)
│   ├── URL: https://frontend-production-18bb.up.railway.app
│   ├── Build: Node.js 20 → Vite build → nginx:alpine
│   ├── Start Command: nginx (with BACKEND_URL substitution)
│   ├── Health Check: /health
│   └── Environment Variables: VITE_* (build-time + runtime)
│
└── Quiz Interface Service (interface-quiz-production)
    ├── URL: https://interface-quiz-production.up.railway.app
    ├── Build: Node.js 20 → Next.js build
    ├── Start Command: pnpm exec next start
    ├── Health Check: /api/health
    └── Environment Variables: NEXT_PUBLIC_*
```

### 7.2 Environment Variable Propagation

#### Backend → Frontend Runtime Config
**Flow**:
```
1. Railway sets environment variables on Backend service
2. Backend exposes /api/config endpoint
3. Frontend fetches /api/config at runtime
4. Frontend uses config for API_URL, WS_URL, etc.
```

**Benefits**:
- No build-time dependency on environment variables
- Environment changes don't require rebuild
- Single source of truth (Backend)

**Drawbacks**:
- Extra HTTP request on app load (mitigated by 5-minute cache)
- Network dependency for configuration

---

### 7.3 Docker Build Optimization

#### Multi-Stage Build (Frontend)
**File**: `frontend-hormonia/Dockerfile`

**Stages**:
1. **deps**: Install Node.js dependencies
2. **builder**: Build Vite application with ARG environment variables
3. **production**: nginx:alpine with built assets

**Build Arguments**:
```dockerfile
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ARG VITE_API_URL
ARG VITE_FIREBASE_API_KEY
# ... (11 total build args)
```

**Issue**: Railway doesn't always pass build args correctly.
**Solution**: Runtime config endpoint (`/api/config`) as fallback.

---

## 8. Monitoring & Observability

### 8.1 Application Performance Monitoring (APM)

**Backend Middleware**: `app/monitoring/manager.py` (inferred)

**Metrics Collected**:
- Request latency (p50, p95, p99)
- Database query count per request
- Database query duration
- Error rates (4xx, 5xx)
- WebSocket connection count

**Exposed Headers**:
```
X-Request-ID: <uuid>
X-Correlation-ID: <uuid>
X-Process-Time: <milliseconds>
X-Query-Count: <number>
X-DB-Time-Ms: <milliseconds>
```

---

### 8.2 Business Metrics

**Monitoring Configuration** (`app/config.py` lines 295-316):
```python
MONITORING_ENABLED = True
APM_APDEX_THRESHOLD = 0.5  # 500ms for satisfactory response
APM_SLOW_REQUEST_THRESHOLD = 1.0  # 1 second
DB_SLOW_QUERY_THRESHOLD = 1.0  # 1 second
```

**Dashboard**: `/api/v1/monitoring/dashboard` (authenticated)

---

### 8.3 External Monitoring

#### Sentry Integration
**Frontend**: `VITE_SENTRY_DSN`
**Backend**: `SENTRY_DSN`

**Error Tracking**:
- JavaScript errors (frontend)
- Python exceptions (backend)
- Performance monitoring
- Release tracking

---

## 9. Recommendations Summary

### 9.1 Security Enhancements

| Priority | Recommendation | Impact | Effort |
|----------|----------------|--------|--------|
| **HIGH** | Implement Content Security Policy | Prevent XSS attacks | Medium |
| **HIGH** | Add HSTS header (if not Railway-provided) | Force HTTPS | Low |
| **MEDIUM** | Quiz token POST exchange | Prevent token leakage | Medium |
| **MEDIUM** | Implement token rotation | Improve auth security | High |
| **LOW** | Rate limit /api/config | Prevent DoS | Low |

---

### 9.2 Performance Optimizations

| Priority | Recommendation | Impact | Effort |
|----------|----------------|--------|--------|
| **HIGH** | Separate nginx proxy buffering for WS | Improve HTTP perf | Low |
| **MEDIUM** | Reduce CORS preflight cache | Faster policy updates | Low |
| **MEDIUM** | Optimize database pool sizing | Better resource usage | Medium |
| **LOW** | Implement CDN for static assets | Faster page loads | High |

---

### 9.3 Reliability Improvements

| Priority | Recommendation | Impact | Effort |
|----------|----------------|--------|--------|
| **HIGH** | Redis failover mechanism | Prevent auth outage | High |
| **HIGH** | Database connection retry logic | Handle transient errors | Medium |
| **MEDIUM** | Circuit breaker for Evolution API | Prevent cascading failures | Medium |
| **MEDIUM** | Implement request timeout strategy | Prevent hanging requests | Low |

---

## 10. Architecture Decision Records (ADRs)

### ADR-001: Runtime Configuration via /api/config

**Context**: Railway build arguments not reliably passed to Vite build.
**Decision**: Backend serves runtime config via `/api/config` endpoint.
**Consequences**:
- ✅ Environment changes don't require rebuild
- ✅ Single source of truth
- ❌ Extra HTTP request on app load
- ❌ Network dependency for configuration

---

### ADR-002: Firebase Auth + Supabase Database

**Context**: Need authentication + PostgreSQL database.
**Decision**: Firebase for auth, Supabase for database + storage.
**Consequences**:
- ✅ Separate concerns (auth vs data)
- ✅ Firebase's mature auth features
- ✅ Supabase's powerful PostgreSQL + RLS
- ❌ Complexity of managing two services
- ❌ Firebase outage = no authentication

---

### ADR-003: Custom CORS Middleware with Pattern Matching

**Context**: Railway generates dynamic domains (`*.railway.app`).
**Decision**: Implement custom CORS middleware with wildcard support.
**Consequences**:
- ✅ Support for dynamic Railway domains
- ✅ Explicit origins in production (security)
- ✅ Wildcard only in dev/staging
- ❌ More complex CORS configuration

---

### ADR-004: Redis DB Isolation (Celery vs Cache)

**Context**: Prevent Celery task queue interference with application cache.
**Decision**: Use separate Redis databases (DB 0 for Celery, DB 1 for cache).
**Consequences**:
- ✅ Isolated workloads
- ✅ Easier debugging
- ✅ Better performance monitoring
- ❌ Requires Redis configuration support

---

## 11. Glossary

| Term | Definition |
|------|------------|
| **RLS** | Row-Level Security - PostgreSQL feature for data isolation |
| **APM** | Application Performance Monitoring |
| **CORS** | Cross-Origin Resource Sharing |
| **CSP** | Content Security Policy |
| **JWT** | JSON Web Token |
| **HSTS** | HTTP Strict Transport Security |
| **TTL** | Time To Live (cache expiration) |
| **Apdex** | Application Performance Index (user satisfaction metric) |

---

## 12. Appendix

### A. Configuration Files Reference

| File | Purpose | Lines of Interest |
|------|---------|-------------------|
| `backend-hormonia/app/config.py` | Backend settings | 202-257 (CORS), 278-293 (Quiz) |
| `backend-hormonia/app/middleware/custom_cors.py` | CORS logic | 16-159 (PatternCORS) |
| `backend-hormonia/app/core/middleware_setup.py` | Middleware chain | 25-143 (setup) |
| `frontend-hormonia/src/config.ts` | Frontend config | 22-98 (loadConfig) |
| `frontend-hormonia/src/lib/runtime-config.ts` | Runtime config loader | 112-198 (loadRuntimeConfig) |
| `frontend-hormonia/nginx.conf` | Nginx proxy config | 40-77 (API proxy), 79-96 (WebSocket) |

---

### B. API Endpoint Inventory

#### Backend Public Endpoints (No Auth)
- `GET /health` - Health check
- `GET /api/config` - Runtime configuration
- `GET /api/v1/monthly-quiz/validate-token` - Quiz token validation (requires token)

#### Backend Authenticated Endpoints
- `POST /api/v1/monthly-quiz/generate-link` - Generate quiz link (requires auth)
- `POST /api/v1/monthly-quiz/submit` - Submit quiz answers (requires auth or quiz token)
- `GET /api/v1/monitoring/dashboard` - Monitoring dashboard (requires admin role)

#### Frontend Routes
- `/` - Home/Dashboard
- `/patients` - Patient management
- `/login` - Login page
- `/quiz/monthly/:token` - Redirect to Quiz Interface

#### Quiz Interface Routes
- `/quiz/monthly/:token` - Quiz page
- `/api/health` - Health check

---

### C. Environment Variables Checklist

#### Backend Critical Variables
- [ ] `SECRET_KEY` - JWT signing (64+ chars)
- [ ] `DATABASE_URL` - PostgreSQL connection
- [ ] `FIREBASE_ADMIN_PROJECT_ID` - Firebase project
- [ ] `FIREBASE_ADMIN_PRIVATE_KEY` - Firebase service account key
- [ ] `FIREBASE_ADMIN_CLIENT_EMAIL` - Firebase service account email
- [ ] `REDIS_URL` - Redis connection (SSL required)
- [ ] `SUPABASE_URL` - Supabase project URL
- [ ] `SUPABASE_SERVICE_ROLE_KEY` - Supabase admin key
- [ ] `MONTHLY_QUIZ_TOKEN_SECRET` - Quiz token signing

#### Frontend Critical Variables
- [ ] `VITE_API_BASE_URL` - Backend API URL
- [ ] `VITE_WS_BASE_URL` - WebSocket URL
- [ ] `VITE_FIREBASE_API_KEY` - Firebase client key
- [ ] `VITE_FIREBASE_PROJECT_ID` - Firebase project ID

#### Quiz Interface Critical Variables
- [ ] `NEXT_PUBLIC_API_URL` - Backend API URL

---

**Document Version**: 1.0
**Last Updated**: 2025-10-04
**Reviewed By**: System Architecture Designer (Claude)
**Next Review**: 2025-11-04
