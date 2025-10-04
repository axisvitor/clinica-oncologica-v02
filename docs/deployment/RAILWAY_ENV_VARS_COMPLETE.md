# Complete Environment Variables Reference - Backend Hormonia

## 🔐 CRITICAL SECURITY KEYS (Must be Unique & Secret)

### 1. Application Security
```bash
# Main application secret key (64+ characters)
SECRET_KEY=<GENERATE_NEW_64_CHAR_RANDOM_STRING>

# JWT signing key (64+ characters, must be different from SECRET_KEY)
JWT_SECRET_KEY=<GENERATE_NEW_64_CHAR_RANDOM_STRING>

# Field encryption key (32 characters, base64 encoded)
ENCRYPTION_KEY=<GENERATE_NEW_32_CHAR_BASE64_STRING>
```

**How to generate**:
```python
# Python
import secrets
SECRET_KEY = secrets.token_urlsafe(64)
JWT_SECRET_KEY = secrets.token_urlsafe(64)

# Encryption key (32 bytes base64)
from cryptography.fernet import Fernet
ENCRYPTION_KEY = Fernet.generate_key().decode()
```

### 2. Authentication Configuration
```bash
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
BCRYPT_ROUNDS=12
ENABLE_FIELD_ENCRYPTION=true
```

---

## 🗄️ DATABASE CONFIGURATION

### PostgreSQL (Supabase)
```bash
# Connection string format: postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres

# Connection pool settings
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=40
DB_POOL_TIMEOUT=20
DB_STATEMENT_TIMEOUT=30000
DB_POOL_RECYCLE=3600

# RLS (Row Level Security) pool settings
RLS_POOL_SIZE=30
RLS_POOL_MAX_OVERFLOW=50
```

**Notes**:
- Use Supabase connection pooler URL for production
- Format must use `postgresql+psycopg` (psycopg3)
- Never commit credentials to git

---

## 🔴 REDIS CONFIGURATION

### Redis Cloud / Railway Redis
```bash
# Enable Redis
ENABLE_REDIS=true

# Connection URL (note: rediss:// with double 's' for SSL)
REDIS_URL=rediss://default:YOUR_PASSWORD@YOUR_HOST:YOUR_PORT

# Individual connection parameters
REDIS_PASSWORD=YOUR_REDIS_PASSWORD
REDIS_HOST=YOUR_REDIS_HOST
REDIS_PORT=YOUR_REDIS_PORT

# SSL Configuration (CRITICAL for production)
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required

# Connection pool settings
REDIS_MAX_CONNECTIONS=25
REDIS_SOCKET_TIMEOUT=10.0
REDIS_DECODE_RESPONSES=true

# Database isolation (recommended for production)
REDIS_ENABLE_DB_ISOLATION=true
REDIS_CACHE_DB=1
REDIS_BROKER_DB=0
```

### Celery Configuration (Uses Redis)
```bash
CELERY_BROKER_URL=rediss://default:YOUR_PASSWORD@YOUR_HOST:YOUR_PORT/0
CELERY_RESULT_BACKEND=rediss://default:YOUR_PASSWORD@YOUR_HOST:YOUR_PORT/0
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_MAX_TASKS_PER_CHILD=1000
CELERY_WORKER_TIME_LIMIT=300
CELERY_WORKER_SOFT_TIME_LIMIT=240
CELERY_QUEUES=celery,flows,quiz,maintenance,monitoring
```

---

## 🔥 SUPABASE CONFIGURATION

```bash
# Supabase project URL
SUPABASE_URL=https://YOUR_PROJECT_ID.supabase.co

# Anonymous key (for client-side operations)
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Service role key (backend operations, bypasses RLS)
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Storage bucket for avatars
SUPABASE_AVATARS_BUCKET=avatars

# RLS Configuration
SUPABASE_USE_SERVICE_ROLE=true
SUPABASE_BYPASS_RLS=true
```

**Where to find**:
- Dashboard → Settings → API
- Project URL: API Settings
- Keys: API Settings → Project API keys

---

## 🔥 FIREBASE ADMIN SDK

### Firebase Credentials
```bash
# Project ID
FIREBASE_ADMIN_PROJECT_ID=your-project-id

# Service account private key (multiline - use quotes)
FIREBASE_ADMIN_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----
YOUR_PRIVATE_KEY_CONTENT_HERE
-----END PRIVATE KEY-----"

# Service account email
FIREBASE_ADMIN_CLIENT_EMAIL=firebase-adminsdk-xxxxx@your-project-id.iam.gserviceaccount.com
```

### Firebase Web Configuration
```bash
FIREBASE_WEB_API_KEY=AIzaSy...
FIREBASE_WEB_PROJECT_ID=your-project-id
FIREBASE_WEB_APP_ID=1:123456789:web:abcdef123456
FIREBASE_AUTH_DOMAIN=your-project-id.firebaseapp.com
```

### Firebase Security Settings
```bash
# Block public email domains (gmail, yahoo, etc.)
FIREBASE_BLOCK_PUBLIC_DOMAINS=true

# Allowed domains for user registration (JSON array)
FIREBASE_ALLOWED_DOMAINS=["yourdomain.com","anotherdomain.com"]
```

**Where to find**:
- Firebase Console → Project Settings
- Service Account: Project Settings → Service Accounts → Generate New Private Key
- Web Config: Project Settings → General → Your apps

---

## 🤖 AI CONFIGURATION (Google Gemini)

```bash
# Gemini API key
GEMINI_API_KEY=AIzaSy...

# Model selection
GEMINI_MODEL=gemini-2.5-flash-preview-09-2025

# Generation parameters
GEMINI_TEMPERATURE=0.7
GEMINI_MAX_OUTPUT_TOKENS=4096
GEMINI_TOP_P=0.8
GEMINI_TOP_K=40
GEMINI_TIMEOUT=30
GEMINI_MAX_RETRIES=3
```

### AI Humanization Settings
```bash
AI_HUMANIZATION_ENABLED=true
AI_HUMANIZATION_SAFETY_MODE=true
AI_HUMANIZATION_MAX_RETRIES=2
AI_HUMANIZATION_TIMEOUT=10.0
AI_HUMANIZATION_FALLBACK_ENABLED=true
```

**Where to find**:
- Google AI Studio: https://makersuite.google.com/app/apikey

---

## 📱 WHATSAPP INTEGRATION (Evolution API)

```bash
# Enable WhatsApp integration
ENABLE_EVOLUTION=true

# Evolution API credentials
EVOLUTION_API_KEY=YOUR_EVOLUTION_API_KEY
EVOLUTION_WEBHOOK_SECRET=YOUR_WEBHOOK_SECRET

# Instance configuration
EVOLUTION_INSTANCE_NAME=clinica_oncologica
EVOLUTION_API_URL=https://your-evolution-api.com

# Webhook URL (your backend URL)
EVOLUTION_WEBHOOK_URL=https://your-backend.railway.app/webhooks/whatsapp/evolution/clinica_oncologica
```

---

## 🌐 CORS & SECURITY

### Environment Configuration
```bash
ENVIRONMENT=production
DEBUG=False
APP_NAME=NeoplasiaLitoral-Backend
APP_VERSION=2.0.0
```

### CORS Configuration
```bash
# Allowed origins (JSON array format)
ALLOWED_ORIGINS=["https://your-frontend.railway.app","https://your-quiz.railway.app"]

# Allowed hosts
ALLOWED_HOSTS=["your-backend.railway.app"]
```

### Frontend URLs
```bash
FRONTEND_API_URL=https://your-backend.railway.app
FRONTEND_URL=https://your-frontend.railway.app
QUIZ_URL=https://your-quiz.railway.app
```

### Security Headers
```bash
SECURE_SSL_REDIRECT=true
SECURE_CONTENT_TYPE_NOSNIFF=true
SECURE_BROWSER_XSS_FILTER=true
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
```

---

## 📊 MONITORING & LOGGING

```bash
# Monitoring
MONITORING_ENABLED=true
LOG_LEVEL=INFO

# Sentry error tracking (optional)
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=production
```

### Enhanced Monitoring
```bash
MONITORING_DEBUG=false
MONITORING_REDIS_HOST=localhost
MONITORING_REDIS_PORT=6379
MONITORING_REDIS_DB=1
APM_APDEX_THRESHOLD=0.5
APM_SLOW_REQUEST_THRESHOLD=1.0
DB_SLOW_QUERY_THRESHOLD=1.0
RESOURCE_SAMPLE_INTERVAL=10.0
RESOURCE_CPU_THRESHOLD=80.0
RESOURCE_MEMORY_THRESHOLD=85.0
```

---

## 🎯 MONTHLY QUIZ

```bash
MONTHLY_QUIZ_VIA_LINK=true
MONTHLY_QUIZ_BASE_URL=https://your-quiz.railway.app
MONTHLY_QUIZ_TOKEN_SECRET=<GENERATE_NEW_64_CHAR_RANDOM_STRING>
MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS=72
```

---

## 📈 RATE LIMITING

```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REDIS_URL=rediss://default:PASSWORD@HOST:PORT
```

---

## 🇧🇷 LGPD COMPLIANCE

```bash
LGPD_COMPLIANCE_MODE=true
AUDIT_LOG_RETENTION_DAYS=365
DATA_RETENTION_DAYS=730
```

---

## 🐍 PYTHON CONFIGURATION

```bash
# Python runtime (automatically set by Railway)
PYTHONUNBUFFERED=1
PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=/app

# Fix for passlib bcrypt compatibility
PASSLIB_BUILTIN_BCRYPT=enabled
```

---

## 📋 COMPLETE CHECKLIST

### Minimum Required Variables (20)
- [ ] SECRET_KEY
- [ ] JWT_SECRET_KEY
- [ ] ENCRYPTION_KEY
- [ ] DATABASE_URL
- [ ] REDIS_URL
- [ ] REDIS_PASSWORD
- [ ] REDIS_HOST
- [ ] REDIS_PORT
- [ ] SUPABASE_URL
- [ ] SUPABASE_ANON_KEY
- [ ] SUPABASE_SERVICE_ROLE_KEY
- [ ] FIREBASE_ADMIN_PROJECT_ID
- [ ] FIREBASE_ADMIN_PRIVATE_KEY
- [ ] FIREBASE_ADMIN_CLIENT_EMAIL
- [ ] GEMINI_API_KEY
- [ ] ENVIRONMENT
- [ ] ALLOWED_ORIGINS
- [ ] FRONTEND_URL
- [ ] MONTHLY_QUIZ_TOKEN_SECRET
- [ ] EVOLUTION_API_KEY (if WhatsApp enabled)

### Recommended Additional Variables (15+)
- [ ] DB_POOL_SIZE
- [ ] REDIS_SSL
- [ ] CELERY_BROKER_URL
- [ ] FIREBASE_ALLOWED_DOMAINS
- [ ] ALLOWED_HOSTS
- [ ] SECURE_SSL_REDIRECT
- [ ] SESSION_COOKIE_SECURE
- [ ] MONITORING_ENABLED
- [ ] SENTRY_DSN
- [ ] RATE_LIMIT_ENABLED
- [ ] LGPD_COMPLIANCE_MODE
- [ ] All security headers
- [ ] All Gemini parameters
- [ ] All monitoring parameters

---

## 🔒 SECURITY BEST PRACTICES

1. **Never commit secrets to git**
   - Use Railway environment variables
   - Use `.env.example` for documentation only

2. **Generate unique keys**
   - Each key should be different
   - Use cryptographically secure random generation
   - Minimum 64 characters for signing keys

3. **Production configuration**
   - `DEBUG=False`
   - `ENVIRONMENT=production`
   - `SECURE_SSL_REDIRECT=true`
   - `SESSION_COOKIE_SECURE=true`
   - `REDIS_SSL=true`

4. **Database security**
   - Use connection pooling
   - Enable SSL for database connections
   - Use Supabase connection pooler

5. **Redis security**
   - Always use SSL (`rediss://`)
   - Set `REDIS_SSL_CERT_REQS=required`
   - Use password authentication
   - Isolate databases (cache vs broker)

---

## 📝 NOTES

### Format Requirements
- **JSON Arrays**: Use double quotes, e.g., `["item1","item2"]`
- **Multiline Strings**: Use quotes with `\n`, e.g., `"line1\nline2"`
- **Boolean Values**: Use `true`/`false` or `True`/`False`
- **Numbers**: No quotes needed

### Railway-Specific
- `PORT` is automatically set by Railway (don't override)
- Use Railway's private networking for internal services
- Set root directory to `backend-hormonia` in Railway settings

### Testing
```bash
# Test locally with .env file
cd backend-hormonia
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Verify health
curl http://localhost:8000/health
```

---

## 🔗 Related Documentation

- [Backend Deployment Guide](./BACKEND_RAILWAY_DEPLOYMENT.md)
- [Railway DNS Configuration](./RAILWAY_DNS_INDEX.md)
- [Production Checklist](../../backend-hormonia/PRODUCTION_READY_CHECKLIST.md)
