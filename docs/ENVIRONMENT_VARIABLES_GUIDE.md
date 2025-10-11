# Environment Variables - Complete Guide

**Date**: 2025-10-10
**Status**: Updated & Cleaned

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Frontend Variables](#frontend-variables)
3. [Backend Variables](#backend-variables)
4. [Quiz Interface Variables](#quiz-interface-variables)
5. [Configuration Best Practices](#configuration-best-practices)
6. [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

### Environment Structure

```
clinica-oncologica-v02/
├── frontend-hormonia/
│   ├── .env                 # Frontend actual config (gitignored)
│   └── .env.example         # Frontend template
├── backend-hormonia/
│   ├── .env                 # Backend actual config (gitignored)
│   └── .env.example         # Backend template
└── quiz-mensal-interface/
    ├── .env                 # Quiz actual config (gitignored)
    └── .env.example         # Quiz template
```

### Variable Naming Conventions

| Component | Prefix | Example | Visibility |
|-----------|--------|---------|------------|
| Frontend (Vite) | `VITE_` | `VITE_API_URL` | Public (browser) |
| Backend (Python) | None | `DATABASE_URL` | Private (server) |
| Quiz (Next.js) | `NEXT_PUBLIC_` | `NEXT_PUBLIC_API_URL` | Public (browser) |

---

## 🎨 Frontend Variables

### Core API Configuration

```bash
# Backend API endpoint
VITE_API_URL=https://clinica-oncologica-v02-production.up.railway.app/api/v1

# WebSocket endpoint
VITE_WS_URL=wss://clinica-oncologica-v02-production.up.railway.app/ws/connect

# API configuration
VITE_API_BASE_PATH=/api/v1
VITE_API_TIMEOUT=30000
```

### Firebase Authentication (Client)

```bash
# Firebase client configuration (safe for browser)
VITE_FIREBASE_API_KEY=your-api-key
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-project.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789
VITE_FIREBASE_APP_ID=1:123456789:web:abc123
VITE_FIREBASE_MEASUREMENT_ID=G-ABC123

# Enable/disable Firebase
VITE_FIREBASE_ENABLED=true
```

### Supabase Configuration (Optional)

```bash
# Supabase configuration (if using Supabase features)
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key

# Feature flags
VITE_SUPABASE_AUTH_ENABLED=false
VITE_SUPABASE_REALTIME_ENABLED=false
```

⚠️ **Note**: If Supabase auth is disabled, consider removing Supabase keys entirely or moving to backend.

### Feature Flags

```bash
# Core features
VITE_ENABLE_WHATSAPP_INTEGRATION=true
VITE_ENABLE_AI_CHAT=true
VITE_ENABLE_APPOINTMENT_BOOKING=true
VITE_ENABLE_PATIENT_PORTAL=true
VITE_ENABLE_TELEMEDICINE=true
VITE_ENABLE_DARK_MODE=true
VITE_ENABLE_EVOLUTION=true

# Development features
VITE_ENABLE_DEBUG_TOOLS=false
VITE_ENABLE_MOCK_DATA=false
VITE_USE_MOCK_API=false
VITE_USE_MOCK_AUTH=false

# AI features
VITE_AI_ANALYTICS_ENABLED=true
VITE_AI_INSIGHTS_ENABLED=true
VITE_AI_RECOMMENDATIONS_ENABLED=true
```

### Application Configuration

```bash
# Environment
VITE_ENVIRONMENT=production  # development | staging | production
VITE_DEBUG_MODE=false

# Application metadata
VITE_APP_NAME=Hormonia - Sistema de Gestão Oncológica
VITE_APP_VERSION=2.0.0
```

### Security & Session

```bash
# Session management (milliseconds)
VITE_SESSION_TIMEOUT=3600000  # 1 hour
VITE_TOKEN_REFRESH_THRESHOLD=300000  # 5 minutes

# JWT storage keys (if using JWT)
VITE_JWT_STORAGE_KEY=hormonia_access_token
VITE_JWT_REFRESH_KEY=hormonia_refresh_token

# Security features
VITE_ENABLE_CSP=true
VITE_FORCE_HTTPS=true
VITE_SECURITY_HEADERS_ENABLED=true
```

---

## 🔧 Backend Variables

### Database Configuration

```bash
# PostgreSQL connection (CRITICAL: Use sslmode=require in production)
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require

# Connection pool
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=40
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600
DB_STATEMENT_TIMEOUT=30
```

### Redis Configuration

```bash
# Redis connection (CRITICAL: Use rediss:// with SSL in production)
ENABLE_REDIS=true
REDIS_URL=rediss://default:PASSWORD@HOST:PORT
REDIS_PASSWORD=your-password
REDIS_HOST=your-host
REDIS_PORT=6379

# SSL configuration
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required  # none | optional | required

# Connection pool
REDIS_MAX_CONNECTIONS=50
REDIS_SOCKET_TIMEOUT=10.0
REDIS_SOCKET_CONNECT_TIMEOUT=5.0
REDIS_RETRY_ON_TIMEOUT=true
REDIS_HEALTH_CHECK_INTERVAL=30

# Database isolation
REDIS_ENABLE_DB_ISOLATION=true
REDIS_CACHE_DB=1
REDIS_BROKER_DB=0
REDIS_SESSION_DB=2
REDIS_RATE_LIMIT_DB=3
```

### Celery Configuration

```bash
# Celery broker and backend
CELERY_BROKER_URL=rediss://default:PASSWORD@HOST:PORT/0
CELERY_RESULT_BACKEND=rediss://default:PASSWORD@HOST:PORT/0

# Worker configuration
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_MAX_TASKS_PER_CHILD=1000
CELERY_WORKER_TIME_LIMIT=300
CELERY_WORKER_SOFT_TIME_LIMIT=240
CELERY_QUEUES=celery,flows,quiz,maintenance,monitoring
```

### Firebase Admin SDK

```bash
# Firebase Admin (server-side)
FIREBASE_ADMIN_PROJECT_ID=your-project-id
FIREBASE_ADMIN_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n
FIREBASE_ADMIN_CLIENT_EMAIL=firebase-adminsdk@your-project.iam.gserviceaccount.com

# Firebase configuration
FIREBASE_ALLOWED_DOMAINS=yourdomain.com,localhost
FIREBASE_ALLOWED_ROLES=admin,physician,staff
FIREBASE_BLOCK_PUBLIC_DOMAINS=true
FIREBASE_REQUIRE_CUSTOM_CLAIMS=true
```

### Security

```bash
# Secret keys (CRITICAL: Generate unique secure keys)
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here
CSRF_SECRET_KEY=your-csrf-secret-key-here
ENCRYPTION_KEY=your-encryption-key-here

# Algorithm
ALGORITHM=HS256

# Token expiration
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### CORS Configuration

```bash
# Environment
ENVIRONMENT=production  # development | production

# Frontend URLs
FRONTEND_URL=https://frontend-production.up.railway.app
QUIZ_URL=https://quiz-production.up.railway.app

# Allowed origins (CSV format)
ALLOWED_ORIGINS=https://frontend-production.up.railway.app,https://quiz-production.up.railway.app

# Allowed hosts
ALLOWED_HOSTS=backend-production.up.railway.app,localhost
```

### WhatsApp Evolution API

```bash
# Evolution API configuration
ENABLE_EVOLUTION=true
EVOLUTION_API_URL=https://evolution-api.yourdomain.com
EVOLUTION_API_KEY=your-evolution-api-key
EVOLUTION_INSTANCE_NAME=hormonia-instance
EVOLUTION_WEBHOOK_URL=https://your-backend.railway.app/api/v1/whatsapp/webhook
EVOLUTION_WEBHOOK_SECRET=your-webhook-secret
```

### AI Configuration (Gemini)

```bash
# Google Gemini API
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-1.5-pro
GEMINI_TEMPERATURE=0.7
GEMINI_MAX_OUTPUT_TOKENS=8192
```

### Application Settings

```bash
# Application info
APP_NAME=Hormonia Backend
APP_VERSION=2.0.0

# Environment
DEBUG=false
LOG_LEVEL=INFO  # DEBUG | INFO | WARNING | ERROR | CRITICAL

# Features
MONITORING_ENABLED=true
ENABLE_FIELD_ENCRYPTION=true
LGPD_COMPLIANCE_MODE=strict

# Data retention
DATA_RETENTION_DAYS=2555  # ~7 years
AUDIT_LOG_RETENTION_DAYS=2555
```

---

## 🎮 Quiz Interface Variables

### API Configuration

```bash
# Backend API base URL (no path)
NEXT_PUBLIC_API_URL=https://clinica-oncologica-v02-production.up.railway.app

# API timeout
NEXT_PUBLIC_API_TIMEOUT=30000

# Retry configuration
NEXT_PUBLIC_API_RETRY_ATTEMPTS=3
NEXT_PUBLIC_API_RETRY_DELAY=1000
```

### Runtime Configuration

```bash
# Environment
NODE_ENV=production
NEXT_TELEMETRY_DISABLED=1
```

### Feature Flags

```bash
# Features
NEXT_PUBLIC_ENABLE_ANALYTICS=false
NEXT_PUBLIC_ENABLE_ERROR_REPORTING=true
NEXT_PUBLIC_DEBUG_MODE=false
```

### Analytics (Optional)

```bash
# Error tracking
NEXT_PUBLIC_SENTRY_DSN=your-sentry-dsn

# Analytics
NEXT_PUBLIC_GOOGLE_ANALYTICS_ID=your-ga-id
```

### Application Info

```bash
# Branding
NEXT_PUBLIC_APP_NAME=Quiz Mensal - Hormonia
NEXT_PUBLIC_APP_VERSION=1.0.0
```

---

## ✅ Configuration Best Practices

### 1. Security

```bash
# ✅ DO:
- Use environment-specific .env files
- Never commit .env files to git
- Use strong, unique secret keys
- Enable SSL/TLS in production (rediss://, https://, wss://)
- Set sslmode=require for PostgreSQL

# ❌ DON'T:
- Hardcode secrets in code
- Reuse secret keys across environments
- Use same keys for different purposes
- Expose backend secrets in frontend
- Use http:// or redis:// in production
```

### 2. Variable Organization

```bash
# ✅ DO:
- Group related variables together
- Use consistent naming conventions
- Document each variable's purpose
- Provide examples in .env.example

# ❌ DON'T:
- Mix development and production values
- Use unclear variable names
- Leave undocumented variables
- Create duplicate variables
```

### 3. Environment-Specific Configuration

#### Development
```bash
VITE_ENVIRONMENT=development
VITE_DEBUG_MODE=true
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws/connect
DATABASE_URL=postgresql+psycopg://localhost:5432/hormonia_dev
REDIS_URL=redis://localhost:6379
```

#### Production
```bash
VITE_ENVIRONMENT=production
VITE_DEBUG_MODE=false
VITE_API_URL=https://api.yourdomain.com/api/v1
VITE_WS_URL=wss://api.yourdomain.com/ws/connect
DATABASE_URL=postgresql+psycopg://USER:PASS@HOST:PORT/DB?sslmode=require
REDIS_URL=rediss://default:PASS@HOST:PORT
```

---

## 🔍 Troubleshooting

### Common Issues

#### 1. CORS Errors
```bash
# Solution: Update ALLOWED_ORIGINS in backend
ALLOWED_ORIGINS=https://frontend.com,https://quiz.com
# No trailing slashes, use https:// in production
```

#### 2. WebSocket Connection Failed
```bash
# Solution: Check WS URL format
# Development: ws://localhost:8000/ws/connect
# Production: wss://your-domain.com/ws/connect
VITE_WS_URL=wss://your-domain.com/ws/connect
```

#### 3. Database SSL Error
```bash
# Solution: Add sslmode parameter
DATABASE_URL=postgresql+psycopg://user:pass@host:port/db?sslmode=require
```

#### 4. Redis Connection Timeout
```bash
# Solution: Use rediss:// with SSL
REDIS_URL=rediss://default:password@host:port
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required
```

#### 5. Firebase Auth Errors
```bash
# Solution: Verify all Firebase variables are set
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=...
VITE_FIREBASE_PROJECT_ID=...
# And backend Firebase Admin variables
```

---

## 📋 Variable Checklist

### Frontend Deployment
- [ ] `VITE_API_URL` points to production backend
- [ ] `VITE_WS_URL` uses wss:// protocol
- [ ] `VITE_FIREBASE_*` credentials configured
- [ ] `VITE_ENVIRONMENT=production`
- [ ] `VITE_DEBUG_MODE=false`
- [ ] `VITE_FORCE_HTTPS=true`
- [ ] All feature flags set correctly

### Backend Deployment
- [ ] `DATABASE_URL` includes `?sslmode=require`
- [ ] `REDIS_URL` uses `rediss://` protocol
- [ ] `ALLOWED_ORIGINS` includes all frontend URLs
- [ ] Secret keys are unique and secure
- [ ] Firebase Admin credentials configured
- [ ] `ENVIRONMENT=production`
- [ ] `DEBUG=false`
- [ ] SSL certificates valid

### Quiz Interface Deployment
- [ ] `NEXT_PUBLIC_API_URL` points to backend (no /api/v1 path)
- [ ] `NODE_ENV=production`
- [ ] Analytics configured (if needed)
- [ ] Error reporting enabled

---

## 📚 Additional Resources

- [Railway Environment Variables Guide](https://docs.railway.app/develop/variables)
- [Vite Environment Variables](https://vitejs.dev/guide/env-and-mode.html)
- [Next.js Environment Variables](https://nextjs.org/docs/basic-features/environment-variables)
- [Firebase Admin SDK Setup](https://firebase.google.com/docs/admin/setup)
- [PostgreSQL SSL Modes](https://www.postgresql.org/docs/current/libpq-ssl.html)

---

**Last Updated**: 2025-10-10
**Maintained By**: Development Team
