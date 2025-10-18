# Deployment Guide - Clínica Oncológica V02

**Version:** 2.0.0  
**Last Updated:** 2025-10-17  
**Environment:** Production, Staging, Development

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Variables](#environment-variables)
3. [Database Setup](#database-setup)
4. [Deployment Steps](#deployment-steps)
5. [Health Checks](#health-checks)
6. [Rollback Procedures](#rollback-procedures)
7. [Monitoring](#monitoring)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Services
- **PostgreSQL 14+** (AWS RDS recommended for production)
- **Redis 6+** (with SSL/TLS support)
- **Python 3.11+**
- **Node.js 18+** (for frontend)
- **Evolution API** (WhatsApp integration)

### Required Accounts
- **Sentry** account for error tracking (https://sentry.io)
- **Railway** or **AWS** account for hosting
- **Evolution API** instance with webhook support

### Tools
```bash
# Backend
pip install -r backend-hormonia/requirements.txt
alembic --version  # Should be 1.12+

# Frontend
cd frontend-hormonia
npm install
```

---

## Environment Variables

### Critical Variables (MUST be set)

```bash
# Database (PostgreSQL with SSL)
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require

# Redis (with SSL)
REDIS_URL=rediss://default:PASSWORD@HOST:PORT

# Security
SECRET_KEY=<generate-with-secrets.token_urlsafe(32)>
CSRF_SECRET_KEY=<generate-with-secrets.token_urlsafe(32)>
EVOLUTION_WEBHOOK_SECRET=<generate-with-secrets.token_urlsafe(32)>

# Monitoring
SENTRY_DSN=https://PUBLIC_KEY@ORGANIZATION.ingest.sentry.io/PROJECT_ID

# Environment
ENVIRONMENT=production  # or staging, development
```

### Generate Secure Secrets

```bash
# Generate all required secrets
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('CSRF_SECRET_KEY=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('EVOLUTION_WEBHOOK_SECRET=' + secrets.token_urlsafe(32))"
```

### Complete Environment Configuration

See `backend-hormonia/.env.example` for all available variables.

**Key configurations:**
- **Database Pool:** `DB_POOL_SIZE=10`, `DB_MAX_OVERFLOW=10` (production)
- **Redis:** `ENABLE_REDIS=true`
- **Evolution API:** `ENABLE_EVOLUTION=true`, `EVOLUTION_API_URL`, `EVOLUTION_API_KEY`
- **CORS:** `FRONTEND_URL`, `QUIZ_URL`
- **Logging:** `LOG_LEVEL=INFO` (production), `LOG_LEVEL=DEBUG` (development)

---

## Database Setup

### 1. Create Database

```bash
# PostgreSQL (local)
createdb clinica_oncologica

# AWS RDS
# Create database via AWS Console or CLI
aws rds create-db-instance \
  --db-instance-identifier clinica-oncologica-prod \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username admin \
  --master-user-password <PASSWORD> \
  --allocated-storage 20
```

### 2. Run Migrations

```bash
cd backend-hormonia

# Check current migration status
alembic current

# Run all pending migrations
alembic upgrade head

# Verify migration
alembic current
# Should show: <latest_revision> (head)
```

### 3. Verify Database Schema

```bash
# Connect to database
psql $DATABASE_URL

# Check tables
\dt

# Expected tables:
# - alembic_version
# - patients
# - messages
# - appointments
# - quiz_responses
# - saga_state
# - webhook_events
# (and others)
```

---

## Deployment Steps

### Production Deployment (Railway/AWS)

#### Step 1: Pre-Deployment Checklist

- [ ] All tests passing (`make test` in backend, `npm run test` in frontend)
- [ ] Code coverage ≥80% (`make test-cov`)
- [ ] Linting passed (`make lint`, `npm run lint`)
- [ ] Environment variables configured in Railway/AWS
- [ ] Database migrations tested in staging
- [ ] Sentry DSN configured
- [ ] Evolution API webhook secret configured

#### Step 2: Deploy Backend

```bash
# Railway (automatic deployment from main branch)
git push origin main

# Manual deployment
cd backend-hormonia
railway up

# AWS (using Docker)
docker build -t clinica-oncologica-backend .
docker tag clinica-oncologica-backend:latest <ECR_REPO>:latest
docker push <ECR_REPO>:latest
```

#### Step 3: Run Database Migrations

```bash
# Railway
railway run alembic upgrade head

# AWS ECS
aws ecs run-task \
  --cluster clinica-oncologica \
  --task-definition migration-task \
  --launch-type FARGATE
```

#### Step 4: Deploy Frontend

```bash
cd frontend-hormonia

# Build production bundle
npm run build

# Deploy to Railway
railway up

# Or deploy to Vercel/Netlify
vercel --prod
# or
netlify deploy --prod
```

#### Step 5: Verify Deployment

```bash
# Check health endpoint
curl https://your-domain.com/health

# Expected response (200 OK):
{
  "status": "healthy",
  "timestamp": "2025-10-17T12:00:00Z",
  "version": "2.0.0",
  "environment": "production",
  "checks": {
    "database": {"status": "healthy", "response_time_ms": 15.2},
    "database_pool": {"status": "healthy", "utilization_percent": 25.5},
    "migrations": {"status": "healthy", "current_version": "abc123"},
    "redis": {"status": "healthy", "response_time_ms": 8.1},
    "evolution_api": {"status": "healthy", "response_time_ms": 120.5}
  }
}
```

#### Step 6: Configure Evolution API Webhook

```bash
# Set webhook URL in Evolution API
curl -X POST https://evolution-api.com/webhook/set \
  -H "apikey: YOUR_EVOLUTION_API_KEY" \
  -d '{
    "url": "https://your-domain.com/api/v1/webhooks/evolution/message",
    "webhook_by_events": true,
    "events": ["messages.upsert", "messages.update", "connection.update"]
  }'
```

#### Step 7: Test Webhook Integration

```bash
# Send test webhook
python scripts/test_webhook.py --url https://your-domain.com/api/v1/webhooks/evolution/message

# Check logs in Sentry
# Check webhook events in database
psql $DATABASE_URL -c "SELECT * FROM webhook_events ORDER BY created_at DESC LIMIT 10;"
```

---

## Health Checks

### Endpoints

| Endpoint | Purpose | Expected Status |
|----------|---------|-----------------|
| `/health` | Comprehensive health check | 200 (healthy/degraded), 503 (unhealthy) |
| `/api/v1/health` | Legacy health check | 200 |
| `/metrics` | Prometheus metrics | 200 |

### Health Check Response

```json
{
  "status": "healthy",  // or "degraded", "unhealthy"
  "timestamp": "2025-10-17T12:00:00Z",
  "version": "2.0.0",
  "environment": "production",
  "checks": {
    "database": {
      "status": "healthy",
      "response_time_ms": 15.2,
      "message": "Database connection successful"
    },
    "database_pool": {
      "status": "healthy",
      "pool_size": 10,
      "checked_out": 3,
      "overflow": 0,
      "utilization_percent": 30.0,
      "message": "Pool utilization normal"
    },
    "migrations": {
      "status": "healthy",
      "current_version": "abc123def456",
      "message": "Migrations up to date"
    },
    "redis": {
      "status": "healthy",
      "response_time_ms": 8.1,
      "message": "Redis connection successful"
    },
    "evolution_api": {
      "status": "healthy",
      "response_time_ms": 120.5,
      "instance_status": "open",
      "message": "Evolution API connected"
    },
    "celery": {
      "status": "healthy",
      "worker_count": 2,
      "workers": ["worker1@hostname", "worker2@hostname"],
      "message": "2 worker(s) active"
    }
  },
  "response_time_ms": 185.3
}
```

### Configure Load Balancer Health Checks

```yaml
# Railway
healthcheck:
  path: /health
  interval: 30s
  timeout: 10s
  retries: 3

# AWS ALB
HealthCheckPath: /health
HealthCheckIntervalSeconds: 30
HealthCheckTimeoutSeconds: 10
HealthyThresholdCount: 2
UnhealthyThresholdCount: 3
```

---

## Rollback Procedures

### Immediate Rollback (Critical Issues)

```bash
# Railway - Rollback to previous deployment
railway rollback

# AWS ECS - Update service to previous task definition
aws ecs update-service \
  --cluster clinica-oncologica \
  --service backend-service \
  --task-definition backend-task:PREVIOUS_REVISION

# Verify rollback
curl https://your-domain.com/health
```

### Database Rollback

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>

# Verify
alembic current
```

### Frontend Rollback

```bash
# Vercel
vercel rollback

# Netlify
netlify rollback

# Railway
railway rollback
```

---

## Monitoring

### Sentry Error Tracking

1. **Access Sentry Dashboard:** https://sentry.io/organizations/YOUR_ORG/projects/
2. **Check Error Rate:** Should be <1% of requests
3. **Review Critical Errors:** Filter by `level:error` or `level:fatal`
4. **Set Up Alerts:** Configure alerts for error rate >5%

### Prometheus Metrics

```bash
# Access metrics endpoint
curl https://your-domain.com/metrics

# Key metrics:
# - http_requests_total
# - http_request_duration_seconds
# - db_pool_size
# - db_pool_checked_out
# - redis_operations_total
```

### Logs

```bash
# Railway
railway logs

# AWS CloudWatch
aws logs tail /aws/ecs/clinica-oncologica --follow
```

---

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors

**Symptom:** `FATAL: no pg_hba.conf entry for host`

**Solution:**
```bash
# Verify SSL mode in DATABASE_URL
echo $DATABASE_URL | grep sslmode=require

# If missing, add ?sslmode=require
export DATABASE_URL="${DATABASE_URL}?sslmode=require"
```

#### 2. Connection Pool Exhaustion

**Symptom:** `QueuePool limit of size X overflow Y reached`

**Solution:**
```bash
# Increase pool size
export DB_POOL_SIZE=20
export DB_MAX_OVERFLOW=20

# Restart application
railway restart
```

#### 3. Webhook Signature Validation Failures

**Symptom:** `401 Unauthorized - Invalid webhook signature`

**Solution:**
```bash
# Verify webhook secret matches Evolution API
echo $EVOLUTION_WEBHOOK_SECRET

# Test webhook signature generation
python scripts/test_webhook_signature.py
```

#### 4. Redis Connection Errors

**Symptom:** `Error connecting to Redis`

**Solution:**
```bash
# Verify Redis URL uses rediss:// (with SSL)
echo $REDIS_URL | grep rediss://

# Test Redis connection
redis-cli -u $REDIS_URL ping
```

---

## Support

- **Documentation:** `docs/` directory
- **Runbook:** `docs/RUNBOOK.md`
- **Architecture:** `docs/ARCHITECTURE.md`
- **API Docs:** `docs/API.md`

For urgent issues, see `docs/RUNBOOK.md` for incident response procedures.

