# System Initialization Requirements Analysis

**Project:** Clínica Oncológica v02-1 (Full-Stack Healthcare Management System)
**Analysis Date:** 2025-12-21
**Analyst:** RequirementsAnalyst Agent (Claude Flow Swarm)
**Objective:** "init" - Comprehensive initialization requirements documentation

---

## Executive Summary

This full-stack healthcare management application requires multi-layer initialization across backend (FastAPI/Python 3.13), frontend (React 19/TypeScript), and supporting services (PostgreSQL, Redis, Celery, Firebase). The project already has robust initialization infrastructure in place with lifecycle management, health checks, and graceful shutdown procedures.

### Critical Finding
**Existing initialization systems are ALREADY IMPLEMENTED**. The "init" objective likely requires one of:
1. **Development environment setup** - First-time developer onboarding
2. **Production deployment initialization** - New environment provisioning
3. **Service restart/recovery** - Post-failure reinitialization
4. **Migration execution** - Database schema updates

---

## Project Architecture

### Technology Stack

#### Backend (backend-hormonia/)
- **Framework:** FastAPI (async Python web framework)
- **Language:** Python 3.13
- **Database:** PostgreSQL with psycopg3 (async-compatible)
- **ORM:** SQLAlchemy 2.x
- **Migrations:** Alembic
- **Cache/Broker:** Redis 6.x (with SSL/TLS support)
- **Task Queue:** Celery with Redis backend
- **Authentication:** Firebase Admin SDK + JWT
- **AI Integration:** Google Gemini (langchain-google-genai)
- **Monitoring:** Sentry, Prometheus, OpenTelemetry

#### Frontend (frontend-hormonia/)
- **Framework:** React 19
- **Language:** TypeScript 5.9
- **Build Tool:** Vite 6
- **UI Library:** Radix UI + TailwindCSS 4
- **State:** React Query 5 (with persistence)
- **Authentication:** Firebase Client SDK

#### Supporting Services
- **Quiz Interface:** quiz-mensal-interface/ (separate React app)
- **Monitoring:** Flower (Celery task monitor)
- **Reverse Proxy:** Nginx (production)

---

## Existing Initialization Infrastructure

### 1. Backend Initialization System

#### Core Files
- **`/backend-hormonia/app/core/lifespan.py`** - Application lifespan manager
- **`/backend-hormonia/app/core/startup.py`** - Startup sequence orchestration
- **`/backend-hormonia/app/services/system_initialization.py`** - Comprehensive system initialization service
- **`/backend-hormonia/app/api/v2/routers/system/initialization.py`** - Admin initialization endpoints

#### Startup Sequence (lifespan.py)

**Phase 1: Logging Configuration**
```python
setup_logging()
configure_structured_logging(log_level=log_level)
```

**Phase 2: Monitoring System**
```python
await _initialize_monitoring(app, logger)
- Initialize monitoring manager
- Start monitoring services
- Configure health endpoints
```

**Phase 3: Redis & WebSocket Events**
```python
await _initialize_redis_websocket_events(app, logger)
- Get Redis manager instance
- Get async Redis client
- Setup WebSocket events service
- Store in app state for access
```

**Phase 4: Unified WebSocket Manager**
```python
await _initialize_websocket_manager(app, logger)
- Get WebSocket manager instance
- Start background tasks (heartbeat, cleanup)
- Enable Firebase + JWT authentication
```

**Phase 5: Redis Pub/Sub (Horizontal Scaling)**
```python
await _initialize_redis_pubsub(app, logger)
- Create unique instance ID
- Initialize RedisPubSubManager
- Start pub/sub listener
- Enable multi-instance WebSocket coordination
```

**Phase 6: Session Management**
```python
await _initialize_session_manager(app, logger)
- Get Redis client from app state
- Initialize thread-safe session manager
- Configure context-scoped database sessions
- Setup ServiceProvider factory
```

**Phase 7: AI Services**
```python
await _initialize_ai_services(app, logger)
- Integrate question humanization
- Configure Gemini AI client
```

**Phase 8: Enum Validation**
```python
await _initialize_enum_validation(app, logger)
- Setup enum validation middleware
- Prevent database enum errors
```

**Phase 9: Follow-Up System**
```python
await _initialize_follow_up_system(app, logger)
- Create FollowUpSystemService instance
- Rehydrate state from Redis
- Resume pending follow-up actions
```

#### Shutdown Sequence (lifespan.py)

**Graceful Shutdown Order:**
1. Stop monitoring system
2. Stop WebSocket manager (disconnect all active connections)
3. Stop Redis Pub/Sub manager
4. Cleanup session manager (close DB connections)
5. Close all Redis connections via manager
6. Cleanup additional resources

#### Admin-Controlled Initialization

**API Endpoint:** `POST /api/v2/system/initialize`
- **Authentication:** Admin role required
- **Rate Limit:** 5 requests/hour
- **Components:**
  - Database connectivity validation
  - Redis cache initialization
  - Firebase Admin SDK setup
  - External service configuration checks

**Status Endpoint:** `GET /api/v2/system/initialization-status`
- Returns initialization state (pending/in_progress/completed/failed)
- Component-level status tracking
- Error and warning collection

### 2. Database Initialization

#### Alembic Migrations
- **Config:** `/backend-hormonia/alembic.ini`
- **Migrations Directory:** `/backend-hormonia/alembic/versions/`
- **Environment:** Uses DATABASE_URL from settings

**Migration Commands:**
```bash
# Generate new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Check current version
alembic current

# Rollback
alembic downgrade -1
```

#### Database Connection
- **Pool Size:** 30 connections
- **Max Overflow:** 40 connections
- **Pool Timeout:** 30 seconds
- **Statement Timeout:** 30,000 ms
- **SSL/TLS:** Required in production (sslmode=require)

### 3. Frontend Initialization

#### Build Process
```bash
# Install dependencies
npm install

# Development server
npm run dev

# Production build
npm run build

# Preview production build
npm run preview
```

#### Environment Configuration
- **Development:** `.env` with VITE_ prefixed variables
- **Production:** `.env.production`
- **Example:** `.env.example` with 306 lines of documentation

---

## Initialization Requirements by Scenario

### Scenario 1: First-Time Development Setup

**Developer Onboarding Checklist:**

**Prerequisites:**
- [ ] Python 3.13 installed
- [ ] Node.js >= 18.0.0 installed
- [ ] npm >= 9.0.0 installed
- [ ] PostgreSQL server running
- [ ] Redis server running (optional but recommended)

**Backend Setup:**
```bash
cd backend-hormonia/

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with actual credentials
# REQUIRED:
#   - DATABASE_URL
#   - SECURITY_SECRET_KEY
#   - SECURITY_ENCRYPTION_KEY
#   - SECURITY_CSRF_SECRET_KEY
# OPTIONAL:
#   - REDIS_URL
#   - FIREBASE_* credentials
#   - AI_GEMINI_API_KEY

# Run database migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend Setup:**
```bash
cd frontend-hormonia/

# Install dependencies
npm install

# Copy environment template
cp .env.example .env

# Edit .env with backend URLs
# REQUIRED:
#   - VITE_API_BASE_URL=http://localhost:8000
#   - VITE_API_ENDPOINT_URL=http://localhost:8000/api/v2
#   - VITE_WS_BASE_URL=ws://localhost:8000/ws
#   - VITE_FIREBASE_* credentials

# Start development server
npm run dev
```

**Validation:**
```bash
# Backend health check
curl http://localhost:8000/health

# Frontend access
open http://localhost:5173
```

### Scenario 2: Production Deployment Initialization

**Railway/Cloud Platform Setup:**

**Backend (Railway):**
1. Set environment variables via Railway dashboard
2. Database URL auto-provisioned by Railway PostgreSQL plugin
3. Redis URL auto-provisioned by Railway Redis plugin
4. Deploy triggers automatic:
   - `pip install -r requirements.txt`
   - Alembic migrations (if configured in railway.toml)
   - `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

**Frontend (Railway/Vercel):**
1. Set VITE_* environment variables
2. Deploy triggers:
   - `npm install`
   - `npm run build`
   - Static file serving via `npm run preview`

**Post-Deployment:**
```bash
# Trigger system initialization (Admin API)
curl -X POST https://api.yourdomain.com/api/v2/system/initialize \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json"

# Verify initialization status
curl https://api.yourdomain.com/api/v2/system/initialization-status \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Scenario 3: Database Migration Initialization

**When schema changes occur:**

```bash
cd backend-hormonia/

# Activate virtual environment
source venv/bin/activate

# Generate migration (after model changes)
alembic revision --autogenerate -m "Add new patient fields"

# Review generated migration in alembic/versions/
# Make manual adjustments if needed

# Apply migration
alembic upgrade head

# Verify database schema
psql $DATABASE_URL -c "\d patients"
```

**Rollback Procedure (if migration fails):**
```bash
# Rollback one version
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision_id>

# Check current version
alembic current

# View migration history
alembic history
```

### Scenario 4: Service Recovery/Restart

**After system crash or maintenance:**

**Backend Automatic Recovery:**
- Lifespan manager automatically runs startup sequence
- Session manager rehydrates from Redis
- Follow-up system resumes from Redis state
- WebSocket manager restarts heartbeat monitoring

**Manual Recovery (if needed):**
```bash
# Check service status
systemctl status backend-hormonia  # systemd
pm2 status backend-api             # PM2

# Restart service
systemctl restart backend-hormonia
# OR
pm2 restart backend-api

# Verify initialization via logs
journalctl -u backend-hormonia -f
# OR
pm2 logs backend-api
```

**Redis State Recovery:**
```bash
# Check Redis connectivity
redis-cli ping

# Verify session data
redis-cli KEYS "session:*"

# Check follow-up system state
redis-cli HGETALL "follow_up:pending_actions"
```

---

## Environment Variable Requirements

### Backend Critical Variables

**Security (REQUIRED):**
```env
SECURITY_SECRET_KEY=<64-char-random-string>
SECURITY_ENCRYPTION_KEY=<64-char-random-string>
SECURITY_CSRF_SECRET_KEY=<64-char-random-string>
```

**Database (REQUIRED):**
```env
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname?sslmode=require
DATABASE_POOL_SIZE=30
DATABASE_POOL_MAX_OVERFLOW=40
```

**Redis (RECOMMENDED):**
```env
REDIS_URL=rediss://user:pass@host:6379  # Production (SSL)
REDIS_URL=redis://localhost:6379        # Development
REDIS_POOL_MAX_CONNECTIONS=50
REDIS_ENABLE_SSL=true                    # Production
```

**Firebase (OPTIONAL - for authentication):**
```env
FIREBASE_ADMIN_PROJECT_ID=your-project-id
FIREBASE_ADMIN_CLIENT_EMAIL=service-account@project.iam.gserviceaccount.com
FIREBASE_ADMIN_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n
```

**AI Services (OPTIONAL):**
```env
AI_GEMINI_API_KEY=your-gemini-api-key
AI_GEMINI_MODEL=gemini-2.0-flash-exp
```

### Frontend Critical Variables

**API Endpoints (REQUIRED):**
```env
VITE_API_BASE_URL=https://api.yourdomain.com
VITE_API_ENDPOINT_URL=https://api.yourdomain.com/api/v2
VITE_WS_BASE_URL=wss://api.yourdomain.com/ws
```

**Firebase (REQUIRED - for client auth):**
```env
VITE_FIREBASE_API_KEY=your-web-api-key
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
```

---

## Initialization Validation

### Health Check Endpoints

**Backend Health:**
```bash
GET /health
GET /api/v2/system/health
GET /api/v2/system/initialization-status  # Admin only
```

**Expected Response (Healthy):**
```json
{
  "status": "healthy",
  "timestamp": "2025-12-21T20:00:00Z",
  "components": {
    "database": {"status": "healthy", "latency_ms": "< 10"},
    "redis": {"status": "healthy", "latency_ms": "< 5"},
    "firebase": {"status": "healthy"}
  },
  "overall_score": 100
}
```

### Component-Level Checks

**Database:**
```sql
-- Test query
SELECT 1;

-- Check connection count
SELECT count(*) FROM pg_stat_activity WHERE datname = 'hormonia';

-- Verify migrations
SELECT * FROM alembic_version;
```

**Redis:**
```bash
redis-cli ping
redis-cli INFO server
redis-cli INFO stats
```

**WebSocket:**
```javascript
// Test connection
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onopen = () => console.log('WebSocket connected');
```

---

## Common Initialization Issues & Solutions

### Issue 1: Database Connection Failed

**Symptoms:**
```
psycopg.OperationalError: connection failed: FATAL: database "hormonia" does not exist
```

**Solutions:**
1. Create database: `createdb hormonia`
2. Verify DATABASE_URL format: `postgresql+psycopg://user:pass@host:port/dbname`
3. Check PostgreSQL is running: `pg_isready`
4. Verify credentials: `psql $DATABASE_URL -c "SELECT 1"`

### Issue 2: Redis Connection Timeout

**Symptoms:**
```
redis.exceptions.TimeoutError: Timeout connecting to Redis
```

**Solutions:**
1. Start Redis: `redis-server` or `systemctl start redis`
2. Check Redis connectivity: `redis-cli ping`
3. Verify REDIS_URL: should be `redis://localhost:6379` for dev
4. Check firewall: Redis port 6379 must be accessible
5. For production SSL issues: verify REDIS_ENABLE_SSL=true and correct certificate path

### Issue 3: Alembic Migration Conflicts

**Symptoms:**
```
alembic.util.exc.CommandError: Can't locate revision identified by 'abc123'
```

**Solutions:**
```bash
# Check current version
alembic current

# View migration history
alembic history

# Stamp database to specific version (if out of sync)
alembic stamp head

# Re-run migrations
alembic upgrade head
```

### Issue 4: Frontend Build Errors

**Symptoms:**
```
RollupError: Could not resolve './config' from src/main.tsx
```

**Solutions:**
```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install

# Clear Vite cache
rm -rf node_modules/.vite

# Verify Node version
node --version  # Should be >= 18.0.0

# Check TypeScript compilation
npm run typecheck
```

### Issue 5: Firebase Initialization Failed

**Symptoms:**
```
Firebase Admin SDK initialization failed: invalid private key
```

**Solutions:**
1. Verify private key format: Must include `\n` for newlines
2. Check environment variable escaping: Use quotes in .env
3. Validate JSON structure: Test with `firebase-admin` directly
4. Ensure all three variables set: PROJECT_ID, CLIENT_EMAIL, PRIVATE_KEY

---

## Initialization Scripts (Recommended Additions)

### Development Init Script
**Location:** `/scripts/init-dev.sh`

```bash
#!/bin/bash
set -e

echo "🚀 Initializing Clínica Oncológica Development Environment"

# Check prerequisites
command -v python3 >/dev/null 2>&1 || { echo "Python 3 required"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js required"; exit 1; }
command -v psql >/dev/null 2>&1 || { echo "PostgreSQL required"; exit 1; }

# Backend setup
cd backend-hormonia
echo "📦 Installing Python dependencies..."
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

if [ ! -f .env ]; then
    echo "📝 Creating .env from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your credentials"
fi

echo "🗄️  Running database migrations..."
alembic upgrade head

# Frontend setup
cd ../frontend-hormonia
echo "📦 Installing NPM dependencies..."
npm install

if [ ! -f .env ]; then
    echo "📝 Creating frontend .env..."
    cp .env.example .env
fi

echo "✅ Development environment initialized!"
echo "Run 'npm run dev' in frontend-hormonia/"
echo "Run 'uvicorn app.main:app --reload' in backend-hormonia/"
```

### Production Deployment Checklist
**Location:** `/scripts/production-deploy-checklist.md`

```markdown
# Production Deployment Checklist

## Pre-Deployment
- [ ] All environment variables set in deployment platform
- [ ] DATABASE_URL points to production PostgreSQL
- [ ] REDIS_URL points to production Redis with SSL
- [ ] All SECURITY_*_KEY variables use strong random values
- [ ] APP_ENVIRONMENT=production
- [ ] APP_ENABLE_DEBUG=false
- [ ] SECURITY_ENABLE_SSL_REDIRECT=true
- [ ] SESSION_ENABLE_COOKIE_SECURE=true

## Deployment
- [ ] Backend deployed and healthy
- [ ] Database migrations executed
- [ ] Frontend built and deployed
- [ ] CORS origins configured correctly
- [ ] Health endpoints responding

## Post-Deployment
- [ ] Admin initialization endpoint called
- [ ] All components showing "healthy" status
- [ ] WebSocket connections working
- [ ] Authentication flow tested
- [ ] Monitoring/logging configured
```

---

## Recommendations for "init" Implementation

Based on this analysis, here are recommended actions for the "init" objective:

### Option 1: Development Environment Setup Script
**Create:** `/scripts/init-dev.sh` (full automation)
- Install dependencies (pip + npm)
- Copy and validate .env templates
- Run database migrations
- Start development servers
- Open browser to localhost:5173

### Option 2: Production Deployment Automation
**Create:** `/scripts/deploy-production.sh`
- Validate environment variables
- Run pre-deployment health checks
- Execute database migrations
- Build frontend assets
- Deploy to Railway/Vercel
- Run post-deployment validation
- Trigger admin initialization endpoint

### Option 3: Database Migration Runner
**Create:** `/scripts/migrate-database.sh`
- Backup current database state
- Run Alembic migrations
- Validate schema changes
- Rollback on failure
- Generate migration report

### Option 4: Health Check & Validation Suite
**Create:** `/scripts/validate-system.sh`
- Check all service dependencies
- Validate environment variables
- Test database connectivity
- Test Redis connectivity
- Test API endpoints
- Generate system health report

---

## Conclusion

The Clínica Oncológica v02-1 project has **robust initialization infrastructure already implemented**. The existing system handles:

✅ Application lifecycle management (startup/shutdown)
✅ Database connection pooling and health checks
✅ Redis connection management with SSL/TLS
✅ WebSocket service initialization
✅ Session management with Redis persistence
✅ Monitoring and logging configuration
✅ Security middleware setup
✅ Graceful degradation on component failures

**The "init" objective likely requires:**
1. **Development onboarding automation** - Scripts to help new developers set up quickly
2. **Production deployment validation** - Automated health checks post-deployment
3. **Documentation** - Clear initialization guides (this document fulfills that)
4. **Recovery procedures** - Scripts for service restart and state recovery

All core initialization logic exists. The gap is in **automation, documentation, and developer experience**.

---

## Next Steps for SwarmLead Coordinator

1. **Clarify Objective:** Confirm which initialization scenario is needed:
   - First-time developer setup?
   - Production deployment?
   - Database migration?
   - Service recovery?

2. **Implement Solution:** Based on clarification, create:
   - Shell scripts for automation
   - Docker Compose for consistent environments
   - CI/CD pipeline integration
   - Initialization documentation

3. **Validate Implementation:** Test initialization in:
   - Clean development environment
   - Staging environment
   - Production environment

4. **Document Results:** Update README.md with initialization instructions

---

**Analysis Complete. Awaiting SwarmLead coordination for next steps.**
