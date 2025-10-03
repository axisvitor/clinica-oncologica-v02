# Environment Variables Reference - Backend

## Complete Environment Variables Documentation

This document lists all environment variables used by the Hormonia Backend system.

## Application Configuration

### Core Settings

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `ENVIRONMENT` | string | Yes | `development` | Environment name (`development`, `production`, `staging`) |
| `DEBUG` | boolean | Yes | `true` | Debug mode (set to `false` in production) |
| `SECRET_KEY` | string | **Required** | - | Secret key for JWT signing (generate random secure key) |
| `ALGORITHM` | string | No | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | integer | No | `30` | JWT access token expiration (minutes) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | integer | No | `7` | JWT refresh token expiration (days) |
| `BCRYPT_ROUNDS` | integer | No | `12` | Bcrypt hashing rounds (12-15 for production) |

### API Configuration

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `FRONTEND_API_URL` | string | No | Auto-detected | API URL for frontend (Railway: auto-detect) |
| `RAILWAY_PUBLIC_DOMAIN` | string | No | - | Railway public domain (e.g., `backend.railway.app`) |
| `PORT` | integer | No | `8000` | API server port (Railway auto-assigns) |
| `HOST` | string | No | `0.0.0.0` | API server host |

## Database Configuration

### Supabase PostgreSQL

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `DATABASE_URL` | string | **Required** | - | PostgreSQL connection string (Supabase pooler) |
| `SUPABASE_URL` | string | **Required** | - | Supabase project URL |
| `SUPABASE_ANON_KEY` | string | **Required** | - | Supabase anonymous key |
| `SUPABASE_SERVICE_ROLE_KEY` | string | **Required** | - | Supabase service role key |
| `DB_POOL_SIZE` | integer | No | `30` | Database connection pool size |
| `DB_MAX_OVERFLOW` | integer | No | `40` | Max overflow connections |
| `DB_POOL_TIMEOUT` | integer | No | `20` | Pool timeout (seconds) |
| `DB_POOL_RECYCLE` | integer | No | `3600` | Connection recycle time (seconds) |

### Row Level Security (RLS)

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `SUPABASE_USE_SERVICE_ROLE` | boolean | No | `false` | Use service role (bypasses RLS) |
| `SUPABASE_BYPASS_RLS` | boolean | No | `false` | Bypass RLS policies |
| `RLS_POOL_SIZE` | integer | No | `30` | RLS connection pool size |
| `RLS_POOL_MAX_OVERFLOW` | integer | No | `50` | RLS max overflow connections |

## Redis Configuration

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `REDIS_URL` | string | **Required** | - | Redis connection URL |
| `REDIS_PASSWORD` | string | No | - | Redis password |
| `REDIS_HOST` | string | No | `localhost` | Redis host |
| `REDIS_PORT` | integer | No | `6379` | Redis port |
| `REDIS_SSL` | boolean | No | `true` | Enable SSL/TLS |
| `REDIS_SSL_CERT_REQS` | string | No | `required` | SSL certificate requirements |
| `REDIS_MAX_CONNECTIONS` | integer | No | `10` | Max Redis connections |

## CORS Configuration

### Critical for Railway Deployment

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `ALLOWED_ORIGINS` | JSON array or string | **Required** | See below | Allowed CORS origins |

**Format Options:**
```bash
# Option 1: JSON array
ALLOWED_ORIGINS=["https://frontend.railway.app","https://quiz.railway.app"]

# Option 2: Comma-separated string
ALLOWED_ORIGINS=https://frontend.railway.app,https://quiz.railway.app
```

**Default Development Origins:**
```json
[
  "http://localhost:3000",
  "http://localhost:5173",
  "http://localhost:5179",
  "http://127.0.0.1:3000",
  "http://127.0.0.1:5173",
  "http://127.0.0.1:5179"
]
```

**Production Railway Pattern:**
```json
[
  "https://frontend-production.up.railway.app",
  "https://quiz-interface.up.railway.app",
  "https://*.railway.app"
]
```

## AI Services

### Google Gemini

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `GEMINI_API_KEY` | string | No | - | Google Gemini API key |
| `GEMINI_MODEL` | string | No | `gemini-2.0-flash-exp` | Gemini model version |
| `GEMINI_TEMPERATURE` | float | No | `0.7` | Generation temperature |
| `GEMINI_MAX_OUTPUT_TOKENS` | integer | No | `500` | Max output tokens |
| `AI_HUMANIZATION_ENABLED` | boolean | No | `true` | Enable AI message humanization |

### LangChain (Optional)

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `LANGCHAIN_TRACING_V2` | boolean | No | `false` | Enable LangChain tracing |
| `LANGCHAIN_API_KEY` | string | No | - | LangChain API key |

## WhatsApp Integration (Evolution API)

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `ENABLE_EVOLUTION` | boolean | No | `true` | Enable WhatsApp integration |
| `EVOLUTION_API_URL` | string | No | - | Evolution API base URL |
| `EVOLUTION_API_KEY` | string | No | - | Evolution API key |
| `EVOLUTION_INSTANCE_NAME` | string | No | `clinica_oncologica` | Evolution instance name |
| `EVOLUTION_WEBHOOK_SECRET` | string | No | - | Webhook signature secret |

## Celery Configuration

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `CELERY_BROKER_URL` | string | No | Same as REDIS_URL | Celery broker URL |
| `CELERY_RESULT_BACKEND` | string | No | Same as REDIS_URL | Celery result backend |
| `CELERY_WORKER_CONCURRENCY` | integer | No | `2` | Worker concurrency |
| `CELERY_TASK_TIME_LIMIT` | integer | No | `300` | Task time limit (seconds) |

## Monitoring & Logging

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `MONITORING_ENABLED` | boolean | No | `true` | Enable monitoring system |
| `LOG_LEVEL` | string | No | `INFO` | Logging level |
| `SENTRY_DSN` | string | No | - | Sentry error tracking DSN |
| `SENTRY_ENVIRONMENT` | string | No | `development` | Sentry environment |

## Security

### Firebase Configuration

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `FIREBASE_ADMIN_PROJECT_ID` | string | No | - | Firebase project ID |
| `FIREBASE_WEB_API_KEY` | string | No | - | Firebase web API key |
| `FIREBASE_ADMIN_PRIVATE_KEY` | string | No | - | Firebase private key (base64) |
| `FIREBASE_ADMIN_CLIENT_EMAIL` | string | No | - | Firebase service account email |

### Security Headers

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `ENABLE_ENHANCED_SECURITY` | boolean | No | `true` | Enable security headers |
| `ENABLE_AUDIT_LOGGING` | boolean | No | `true` | Enable audit logging |
| `SESSION_TIMEOUT_MINUTES` | integer | No | `30` | Session timeout |

## Quiz Configuration

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `MONTHLY_QUIZ_VIA_LINK` | boolean | No | `true` | Enable quiz via link |
| `MONTHLY_QUIZ_BASE_URL` | string | No | `http://localhost:3001` | Quiz base URL |
| `MONTHLY_QUIZ_TOKEN_SECRET` | string | No | - | Quiz token secret |
| `MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS` | integer | No | `72` | Quiz token expiry (hours) |

## Localization

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `DEFAULT_LOCALE` | string | No | `pt-BR` | Default language |
| `SUPPORTED_LOCALES` | JSON array | No | `["en","pt-BR","es"]` | Supported languages |
| `TIMEZONE` | string | No | `America/Sao_Paulo` | Timezone |

## Railway-Specific Variables

**Automatically set by Railway:**

| Variable | Description |
|----------|-------------|
| `RAILWAY_ENVIRONMENT` | Railway environment (production/staging) |
| `RAILWAY_PUBLIC_DOMAIN` | Public domain assigned by Railway |
| `PORT` | Port assigned by Railway (use in start command) |

## Critical Production Settings

**Minimum required for Railway deployment:**

```bash
# Core
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<generate-secure-random-key>

# Database
DATABASE_URL=<supabase-connection-string>
SUPABASE_URL=<supabase-project-url>
SUPABASE_ANON_KEY=<supabase-anon-key>
SUPABASE_SERVICE_ROLE_KEY=<supabase-service-role-key>

# Redis
REDIS_URL=<redis-connection-string>
REDIS_SSL=true

# CORS
ALLOWED_ORIGINS=["https://frontend.railway.app"]
```

## Security Notes

### 🔒 Never Expose These Variables:

1. `SECRET_KEY` - JWT signing key
2. `SUPABASE_SERVICE_ROLE_KEY` - Bypasses RLS
3. `SUPABASE_ANON_KEY` - **REMOVED from /config endpoint**
4. `REDIS_PASSWORD` - Redis authentication
5. `GEMINI_API_KEY` - AI service key
6. Database passwords

### ✅ Safe to Expose (via /config endpoint):

1. `VITE_API_BASE_URL` - Frontend API URL
2. `VITE_WS_BASE_URL` - WebSocket URL
3. `ENVIRONMENT` - Environment name
4. `DEFAULT_LOCALE` - Default language
5. Feature flags (non-sensitive)

## Validation

**Test configuration endpoint:**
```bash
curl https://<domain>.railway.app/config | jq
```

**Expected output (should NOT contain sensitive keys):**
```json
{
  "VITE_API_BASE_URL": "https://backend.railway.app/api/v1",
  "VITE_WS_BASE_URL": "wss://backend.railway.app/ws",
  "ENVIRONMENT": "production",
  "DEFAULT_LOCALE": "pt-BR",
  "SUPPORTED_LOCALES": ["en", "pt-BR", "es"]
}
```

---

**Last Updated:** 2025-10-01
**Version:** 2.0.0
