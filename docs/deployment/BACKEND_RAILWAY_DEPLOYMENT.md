# Backend Railway Deployment Guide

## 🚀 Quick Deploy Checklist

### 1. Railway Project Setup
- [ ] Create new Railway service for backend
- [ ] Connect to GitHub repository
- [ ] Set root directory to `backend-hormonia`
- [ ] Railway will auto-detect Dockerfile

### 2. Environment Variables Configuration

#### 🔐 Security Keys (CRITICAL - Generate New Values)
```bash
# Generate secure keys:
# SECRET_KEY (64 chars)
SECRET_KEY=<generate-new-64-char-key>

# JWT_SECRET_KEY (64 chars)
JWT_SECRET_KEY=<generate-new-64-char-key>

# ENCRYPTION_KEY (32 chars base64)
ENCRYPTION_KEY=<generate-new-32-char-key>

# MONTHLY_QUIZ_TOKEN_SECRET (64 chars)
MONTHLY_QUIZ_TOKEN_SECRET=<generate-new-64-char-key>

# EVOLUTION_WEBHOOK_SECRET (if using WhatsApp)
EVOLUTION_WEBHOOK_SECRET=<generate-new-64-char-key>
```

#### 🗄️ Database Configuration
```bash
# Supabase PostgreSQL
DATABASE_URL=postgresql+psycopg://postgres:PASSWORD@HOST:5432/postgres
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=40
DB_POOL_TIMEOUT=20
DB_STATEMENT_TIMEOUT=30000
DB_POOL_RECYCLE=3600
RLS_POOL_SIZE=30
RLS_POOL_MAX_OVERFLOW=50
```

#### 🔴 Redis Configuration
```bash
# Redis Cloud or Railway Redis
ENABLE_REDIS=true
REDIS_URL=rediss://default:PASSWORD@HOST:PORT
REDIS_PASSWORD=<your-redis-password>
REDIS_HOST=<your-redis-host>
REDIS_PORT=<your-redis-port>
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required
REDIS_MAX_CONNECTIONS=25
REDIS_SOCKET_TIMEOUT=10.0
REDIS_ENABLE_DB_ISOLATION=true
REDIS_CACHE_DB=1
REDIS_BROKER_DB=0

# Celery (uses Redis)
CELERY_BROKER_URL=rediss://default:PASSWORD@HOST:PORT/0
CELERY_RESULT_BACKEND=rediss://default:PASSWORD@HOST:PORT/0
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_MAX_TASKS_PER_CHILD=1000
CELERY_WORKER_TIME_LIMIT=300
CELERY_WORKER_SOFT_TIME_LIMIT=240
```

#### 🔥 Supabase Configuration
```bash
SUPABASE_URL=https://YOUR-PROJECT.supabase.co
SUPABASE_ANON_KEY=<your-anon-key>
SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>
SUPABASE_AVATARS_BUCKET=avatars
SUPABASE_USE_SERVICE_ROLE=true
SUPABASE_BYPASS_RLS=true
```

#### 🔥 Firebase Admin SDK
```bash
FIREBASE_ADMIN_PROJECT_ID=<your-project-id>
FIREBASE_ADMIN_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
FIREBASE_ADMIN_CLIENT_EMAIL=firebase-adminsdk-xxxxx@your-project.iam.gserviceaccount.com
FIREBASE_BLOCK_PUBLIC_DOMAINS=true
FIREBASE_ALLOWED_DOMAINS=["yourdomain.com"]
FIREBASE_WEB_API_KEY=<your-web-api-key>
FIREBASE_WEB_PROJECT_ID=<your-project-id>
FIREBASE_WEB_APP_ID=<your-app-id>
FIREBASE_AUTH_DOMAIN=<your-project>.firebaseapp.com
```

#### 🤖 AI Configuration (Google Gemini)
```bash
GEMINI_API_KEY=<your-gemini-api-key>
GEMINI_MODEL=gemini-2.5-flash-preview-09-2025
GEMINI_TEMPERATURE=0.7
GEMINI_MAX_OUTPUT_TOKENS=4096
```

#### 📱 WhatsApp Integration (Evolution API)
```bash
ENABLE_EVOLUTION=true
EVOLUTION_API_KEY=<your-evolution-api-key>
EVOLUTION_WEBHOOK_SECRET=<your-webhook-secret>
EVOLUTION_INSTANCE_NAME=clinica_oncologica
EVOLUTION_API_URL=https://your-evolution-api.com
EVOLUTION_WEBHOOK_URL=https://your-backend.railway.app/webhooks/whatsapp/evolution/clinica_oncologica
```

#### 🌐 CORS and Security
```bash
# Environment
ENVIRONMENT=production
DEBUG=False
APP_NAME=NeoplasiaLitoral-Backend
APP_VERSION=2.0.0

# CORS - Add your frontend URLs
ALLOWED_ORIGINS=["https://your-frontend.railway.app","https://your-quiz.railway.app"]
ALLOWED_HOSTS=["your-backend.railway.app"]

# Frontend URLs
FRONTEND_API_URL=https://your-backend.railway.app
FRONTEND_URL=https://your-frontend.railway.app
QUIZ_URL=https://your-quiz.railway.app

# Security
SECURE_SSL_REDIRECT=true
SECURE_CONTENT_TYPE_NOSNIFF=true
SECURE_BROWSER_XSS_FILTER=true
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
```

#### 🔧 Authentication & Encryption
```bash
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
BCRYPT_ROUNDS=12
ENABLE_FIELD_ENCRYPTION=true
```

#### 📊 Monitoring
```bash
MONITORING_ENABLED=true
LOG_LEVEL=INFO
SENTRY_DSN=<your-sentry-dsn>
SENTRY_ENVIRONMENT=production
```

#### 🎯 Monthly Quiz
```bash
MONTHLY_QUIZ_VIA_LINK=true
MONTHLY_QUIZ_BASE_URL=https://your-quiz.railway.app
MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS=72
```

#### 📈 Rate Limiting
```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REDIS_URL=<same-as-REDIS_URL>
```

#### 🇧🇷 LGPD Compliance
```bash
LGPD_COMPLIANCE_MODE=true
AUDIT_LOG_RETENTION_DAYS=365
DATA_RETENTION_DAYS=730
```

### 3. Docker Configuration

The backend uses the existing `Dockerfile` with:
- **Base Image**: Python 3.13-slim
- **Server**: Gunicorn with 4 Uvicorn workers
- **Port**: Automatically set by Railway (`$PORT`)
- **Health Check**: `/health` endpoint
- **Security**: Runs as non-root user

### 4. Health Endpoints

Railway will use these endpoints:
- **Health Check**: `GET /health` (basic check)
- **Liveness**: `GET /health/liveness` (service alive)
- **Readiness**: `GET /health/readiness` (ready for traffic)
- **Detailed**: `GET /health/detailed` (comprehensive metrics)

### 5. Deployment Steps

#### Option 1: Railway Dashboard
1. Go to Railway dashboard
2. Create new service → Deploy from GitHub
3. Select repository and branch
4. Set root directory: `backend-hormonia`
5. Add all environment variables from above
6. Deploy automatically triggers

#### Option 2: Railway CLI
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to project
railway link

# Set environment variables (one by one or from file)
railway variables set SECRET_KEY="your-secret-key"

# Deploy
railway up
```

### 6. Post-Deployment Verification

```bash
# Check health
curl https://your-backend.railway.app/health

# Expected response:
{
  "status": "healthy",
  "service": "hormonia-backend",
  "message": "Service is operational"
}

# Check detailed health
curl https://your-backend.railway.app/health/detailed

# Check API documentation (if DEBUG=True in dev)
https://your-backend.railway.app/docs
```

### 7. Common Issues & Solutions

#### Issue: 404 Application not found
**Solution**: Verify:
- Root directory is set to `backend-hormonia`
- Dockerfile exists in root directory
- Railway has detected the Dockerfile builder

#### Issue: Database connection fails
**Solution**:
- Verify DATABASE_URL format: `postgresql+psycopg://...`
- Check Supabase connection pooler settings
- Ensure database allows connections from Railway IPs

#### Issue: Redis connection fails
**Solution**:
- Verify Redis SSL settings (`REDIS_SSL=true`)
- Check Redis Cloud allows external connections
- Verify REDIS_URL format: `rediss://` (with double 's')

#### Issue: Health check timeout
**Solution**:
- Increase `healthcheckTimeout` in `railway.toml`
- Check database and Redis connectivity
- Review application logs for startup errors

### 8. Monitoring

After deployment, monitor:
- **Logs**: Railway dashboard → Deployments → Logs
- **Metrics**: Railway dashboard → Metrics (CPU, Memory, Network)
- **Health**: Regular checks to `/health` endpoint
- **Errors**: Sentry integration (if configured)

### 9. Scaling

To scale the backend:
```bash
# Increase replicas in railway.toml or dashboard
numReplicas = 2  # or more

# Increase workers in Dockerfile
--workers 8  # adjust based on needs
```

### 10. Security Checklist

- [ ] All secrets are environment variables (not hardcoded)
- [ ] DEBUG=False in production
- [ ] SECURE_SSL_REDIRECT=true
- [ ] SESSION_COOKIE_SECURE=true
- [ ] Strong SECRET_KEY, JWT_SECRET_KEY (64+ chars)
- [ ] CORS configured with specific origins
- [ ] Rate limiting enabled
- [ ] Redis SSL enabled
- [ ] Database uses SSL connection

## 📝 Environment Variables Quick Reference

**Total Required Variables**: ~50+

**Categories**:
1. **Security Keys**: 5 variables
2. **Database**: 10 variables
3. **Redis**: 12 variables
4. **Supabase**: 6 variables
5. **Firebase**: 9 variables
6. **AI/Gemini**: 4 variables
7. **WhatsApp**: 5 variables
8. **CORS**: 5 variables
9. **Application**: 6 variables
10. **Monitoring**: 3 variables

**Critical Variables** (service won't start without these):
- `SECRET_KEY`
- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `REDIS_URL` (if ENABLE_REDIS=true)

## 🔗 Related Documentation

- [Railway DNS Configuration](./RAILWAY_DNS_INDEX.md)
- [Railway Networking Guide](./RAILWAY_NETWORKING_GUIDE.md)
- [Environment Variables Reference](./RAILWAY_ENV_VARS.md)

## 📞 Support

If deployment issues persist:
1. Check Railway logs
2. Verify all environment variables
3. Test health endpoints
4. Review Dockerfile configuration
5. Check database and Redis connectivity
