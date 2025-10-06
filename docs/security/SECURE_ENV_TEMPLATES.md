# 🔐 SECURE .env TEMPLATES
## Safe Environment Variable Examples

**⚠️ CRITICAL:** Never copy actual secret values. Always generate new ones.

---

## 🔧 Secret Generation Commands

```bash
# JWT/Session Secrets (64 bytes)
python -c "import secrets; print(secrets.token_urlsafe(64))"

# Encryption Key (Fernet)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Webhook/Token Secrets (32 bytes)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Random UUID
python -c "import uuid; print(str(uuid.uuid4()))"

# Strong Password (for Redis/DB)
python -c "import secrets; import string; alphabet = string.ascii_letters + string.digits + string.punctuation; print(''.join(secrets.choice(alphabet) for i in range(32)))"
```

---

## 📝 Backend Environment Template

**File:** `backend-hormonia/.env.example`

```bash
# ============================================
# BACKEND PRODUCTION ENVIRONMENT TEMPLATE
# ============================================
# 🚨 SECURITY: Never commit actual values!
# Generate all secrets using the commands in SECURE_ENV_TEMPLATES.md

# ============================================
# APPLICATION CONFIGURATION
# ============================================
ENVIRONMENT=production
DEBUG=false
APP_NAME=NeoplasiaLitoral-Backend
APP_VERSION=2.0.0
HOST=0.0.0.0

# ============================================
# SECURITY SECRETS
# ============================================
# Generate: python -c "import secrets; print(secrets.token_urlsafe(64))"
SECRET_KEY=<GENERATE_64_BYTE_RANDOM_STRING>
JWT_SECRET_KEY=<GENERATE_64_BYTE_RANDOM_STRING>

# JWT Configuration
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
BCRYPT_ROUNDS=12

# Field Encryption
# Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENABLE_FIELD_ENCRYPTION=true
ENCRYPTION_KEY=<GENERATE_FERNET_KEY>

# ============================================
# FIREBASE CONFIGURATION
# ============================================
# Get from: https://console.firebase.google.com/project/YOUR_PROJECT/settings/serviceaccounts
FIREBASE_ADMIN_PROJECT_ID=your-project-id
FIREBASE_ADMIN_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY_HERE\n-----END PRIVATE KEY-----\n"
FIREBASE_ADMIN_CLIENT_EMAIL=firebase-adminsdk-xxxxx@your-project-id.iam.gserviceaccount.com

# Firebase Security
FIREBASE_BLOCK_PUBLIC_DOMAINS=false
FIREBASE_REQUIRE_CUSTOM_CLAIMS=true
FIREBASE_ALLOWED_DOMAINS=["yourdomain.com"]
FIREBASE_ALLOWED_ROLES=["admin","super_admin","doctor","medico"]

# Firebase Web API (Public - safe to expose client-side)
# Get from: https://console.firebase.google.com/project/YOUR_PROJECT/settings/general
FIREBASE_WEB_API_KEY=AIzaSy_YOUR_WEB_API_KEY
FIREBASE_WEB_PROJECT_ID=your-project-id
FIREBASE_WEB_APP_ID=1:123456789:web:abcdef123456
FIREBASE_WEB_STORAGE_BUCKET=your-project-id.appspot.com
FIREBASE_AUTH_DOMAIN=your-project-id.firebaseapp.com

# ============================================
# SUPABASE CONFIGURATION
# ============================================
# Get from: https://supabase.com/dashboard/project/YOUR_PROJECT/settings/api
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=<SUPABASE_ANON_KEY>
SUPABASE_SERVICE_ROLE_KEY=<SUPABASE_SERVICE_ROLE_KEY>
SUPABASE_AVATARS_BUCKET=avatars
SUPABASE_USE_SERVICE_ROLE=true
SUPABASE_BYPASS_RLS=true

# ============================================
# DATABASE CONFIGURATION
# ============================================
# Get from: https://supabase.com/dashboard/project/YOUR_PROJECT/settings/database
# Format: postgresql+psycopg://user:password@host:port/database
DATABASE_URL=postgresql+psycopg://postgres.your-project-ref:YOUR_PASSWORD@aws-0-region.pooler.supabase.com:5432/postgres

# Connection Pool Settings
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=40
DB_POOL_TIMEOUT=20
DB_STATEMENT_TIMEOUT=30000
DB_POOL_RECYCLE=3600
RLS_POOL_SIZE=30
RLS_POOL_MAX_OVERFLOW=50

# ============================================
# REDIS CONFIGURATION
# ============================================
# Get from: https://app.redislabs.com/ (Redis Cloud)
ENABLE_REDIS=true

# Redis Connection
# Format: redis://default:password@host:port
REDIS_URL=redis://default:YOUR_REDIS_PASSWORD@redis-xxxxx.region.ec2.redns.redis-cloud.com:PORT
REDIS_PASSWORD=<REDIS_PASSWORD>
REDIS_HOST=redis-xxxxx.region.ec2.redns.redis-cloud.com
REDIS_PORT=14149

# Redis SSL/TLS (for production)
REDIS_SSL=false
REDIS_SSL_CERT_REQS=none
REDIS_SSL_MIN_VERSION=

# Redis Settings
REDIS_MAX_CONNECTIONS=25
REDIS_SOCKET_TIMEOUT=10.0
REDIS_ENABLE_DB_ISOLATION=true
REDIS_CACHE_DB=1
REDIS_BROKER_DB=0

# ============================================
# CELERY CONFIGURATION
# ============================================
# Format: redis://default:password@host:port/db
CELERY_BROKER_URL=redis://default:YOUR_REDIS_PASSWORD@redis-xxxxx.region.ec2.redns.redis-cloud.com:PORT/0
CELERY_RESULT_BACKEND=redis://default:YOUR_REDIS_PASSWORD@redis-xxxxx.region.ec2.redns.redis-cloud.com:PORT/0

# Celery Worker Settings
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_MAX_TASKS_PER_CHILD=1000
CELERY_WORKER_TIME_LIMIT=300
CELERY_WORKER_SOFT_TIME_LIMIT=240
CELERY_QUEUES=celery,flows,quiz,maintenance,monitoring

# ============================================
# GEMINI AI CONFIGURATION
# ============================================
# Get from: https://console.cloud.google.com/apis/credentials
GEMINI_API_KEY=<GOOGLE_GEMINI_API_KEY>
GEMINI_MODEL=gemini-2.5-flash-preview-09-2025
GEMINI_TEMPERATURE=0.7
GEMINI_MAX_OUTPUT_TOKENS=4096

# ============================================
# WHATSAPP (EVOLUTION API) CONFIGURATION
# ============================================
# Get from: Your Evolution API instance
ENABLE_EVOLUTION=true
EVOLUTION_API_KEY=<EVOLUTION_API_KEY>
EVOLUTION_WEBHOOK_SECRET=<GENERATE_32_BYTE_RANDOM_STRING>
EVOLUTION_INSTANCE_NAME=your-instance-name
EVOLUTION_API_URL=https://your-evolution-api-domain.com
EVOLUTION_WEBHOOK_URL=https://your-backend.railway.app/webhooks/whatsapp/evolution/your-instance-name

# ============================================
# MONTHLY QUIZ CONFIGURATION
# ============================================
MONTHLY_QUIZ_VIA_LINK=true
MONTHLY_QUIZ_BASE_URL=https://your-quiz-frontend.railway.app/quiz/monthly
# Generate: python -c "import secrets; print(secrets.token_urlsafe(32))"
MONTHLY_QUIZ_TOKEN_SECRET=<GENERATE_32_BYTE_RANDOM_STRING>
MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS=72

# ============================================
# CORS & SECURITY CONFIGURATION
# ============================================
# Auto-constructed from FRONTEND_URL + QUIZ_URL in production
ALLOWED_HOSTS=["your-frontend.railway.app","your-backend.railway.app","*.up.railway.app"]
FRONTEND_API_URL=https://your-frontend.railway.app
FRONTEND_URL=https://your-frontend.railway.app
QUIZ_URL=https://your-quiz-frontend.railway.app

# Security Headers
SECURE_SSL_REDIRECT=true
SECURE_CONTENT_TYPE_NOSNIFF=true
SECURE_BROWSER_XSS_FILTER=true
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true

# ============================================
# MONITORING & LOGGING
# ============================================
MONITORING_ENABLED=true
LOG_LEVEL=INFO

# Sentry (Optional)
SENTRY_DSN=
SENTRY_ENVIRONMENT=production

# ============================================
# COMPLIANCE & DATA RETENTION
# ============================================
LGPD_COMPLIANCE_MODE=true
AUDIT_LOG_RETENTION_DAYS=365
DATA_RETENTION_DAYS=730

# ============================================
# FILE UPLOAD CONFIGURATION
# ============================================
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE=10485760

# ============================================
# AUTO PROVISIONING
# ============================================
AUTO_PROVISION_SUPABASE_USERS=true
```

---

## 📝 Frontend Environment Template

**File:** `frontend-hormonia/.env.example`

```bash
# ============================================
# FRONTEND PRODUCTION ENVIRONMENT TEMPLATE
# ============================================
# 🚨 SECURITY: All VITE_* variables are PUBLIC
# Never put secrets in frontend environment variables!

# ============================================
# API CONFIGURATION
# ============================================
VITE_API_BASE_URL=https://your-backend.railway.app
VITE_API_URL=https://your-backend.railway.app/api/v1
VITE_API_BASE_PATH=/api/v1
VITE_API_TIMEOUT=30000

# ============================================
# WEBSOCKET CONFIGURATION
# ============================================
VITE_WS_BASE_URL=wss://your-backend.railway.app/ws/connect
VITE_WS_URL=wss://your-backend.railway.app/ws/connect

# ============================================
# FIREBASE CONFIGURATION (Public)
# ============================================
# Get from: https://console.firebase.google.com/project/YOUR_PROJECT/settings/general
VITE_FIREBASE_API_KEY=AIzaSy_YOUR_WEB_API_KEY
VITE_FIREBASE_AUTH_DOMAIN=your-project-id.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-project-id.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789
VITE_FIREBASE_APP_ID=1:123456789:web:abcdef123456
VITE_FIREBASE_MEASUREMENT_ID=G-XXXXXXXXXX

# ============================================
# SUPABASE CONFIGURATION (Public)
# ============================================
# Get from: https://supabase.com/dashboard/project/YOUR_PROJECT/settings/api
VITE_SUPABASE_URL=https://your-project-ref.supabase.co
VITE_SUPABASE_ANON_KEY=<SUPABASE_ANON_KEY>
VITE_SUPABASE_AUTH_ENABLED=true
VITE_SUPABASE_REALTIME_ENABLED=true
VITE_SUPABASE_PUBLISHABLE_DEFAULT_KEY=sb_publishable_XXXXX

# ============================================
# APPLICATION CONFIGURATION
# ============================================
VITE_ENVIRONMENT=production
VITE_DEBUG_MODE=false
VITE_APP_NAME=Hormonia - Sistema de Gestão Oncológica
VITE_APP_VERSION=2.0.0

# ============================================
# FEATURE FLAGS
# ============================================
VITE_ENABLE_WHATSAPP_INTEGRATION=true
VITE_ENABLE_AI_CHAT=true
VITE_ENABLE_APPOINTMENT_BOOKING=true
VITE_ENABLE_PATIENT_PORTAL=true
VITE_ENABLE_TELEMEDICINE=true
VITE_ENABLE_DARK_MODE=true
VITE_ENABLE_EVOLUTION=true
VITE_ENABLE_DEBUG_TOOLS=false
VITE_ENABLE_MOCK_DATA=false
VITE_USE_MOCK_API=false
VITE_USE_MOCK_AUTH=false

# ============================================
# AI FEATURES
# ============================================
VITE_AI_CHAT_ENABLED=true
VITE_AI_ANALYTICS_ENABLED=true
VITE_AI_INSIGHTS_ENABLED=true
VITE_AI_RECOMMENDATIONS_ENABLED=true

# ============================================
# SESSION & SECURITY
# ============================================
VITE_SESSION_TIMEOUT=3600000
VITE_TOKEN_REFRESH_THRESHOLD=300000
VITE_JWT_STORAGE_KEY=hormonia_access_token
VITE_JWT_REFRESH_KEY=hormonia_refresh_token
VITE_ENABLE_CSP=true
VITE_FORCE_HTTPS=true
VITE_SECURITY_HEADERS_ENABLED=true

# ============================================
# UI CONFIGURATION
# ============================================
VITE_PRIMARY_COLOR=
VITE_SECONDARY_COLOR=
VITE_SUCCESS_COLOR=
VITE_ERROR_COLOR=
VITE_WARNING_COLOR=
VITE_SIDEBAR_WIDTH=280
VITE_HEADER_HEIGHT=64
VITE_FOOTER_HEIGHT=60

# ============================================
# PAGINATION & API
# ============================================
VITE_DEFAULT_PAGE_SIZE=20
VITE_MAX_PAGE_SIZE=100
VITE_REQUEST_TIMEOUT=30000
VITE_REQUEST_RETRY_ATTEMPTS=3
VITE_REQUEST_RETRY_DELAY=1000
VITE_CACHE_DURATION=300000
VITE_IMAGE_CACHE_DURATION=3600000

# ============================================
# FILE UPLOAD
# ============================================
VITE_MAX_FILE_SIZE=10485760
VITE_ALLOWED_FILE_TYPES=pdf,doc,docx,jpg,jpeg,png,gif,txt
VITE_UPLOAD_CHUNK_SIZE=1048576
VITE_SUPPORTED_FILE_TYPES=image/jpeg,image/png,image/gif,application/pdf

# ============================================
# LOCALIZATION
# ============================================
VITE_DEFAULT_LANGUAGE=pt-BR
VITE_SUPPORTED_LANGUAGES=pt-BR,en-US
VITE_TIMEZONE=America/Sao_Paulo
VITE_DATE_FORMAT=DD/MM/YYYY
VITE_TIME_FORMAT=HH:mm
VITE_DATETIME_FORMAT=DD/MM/YYYY HH:mm

# ============================================
# WHATSAPP INTEGRATION
# ============================================
VITE_WHATSAPP_INSTANCE_NAME=hormonia-instance
VITE_WHATSAPP_MAX_FILE_SIZE=16777216

# ============================================
# MONITORING (Optional)
# ============================================
VITE_ENABLE_ERROR_REPORTING=true
VITE_ENABLE_PERFORMANCE_MONITORING=true
VITE_SENTRY_DSN=

# ============================================
# PWA CONFIGURATION
# ============================================
VITE_PWA_ENABLED=true
VITE_PWA_SHORT_NAME=Hormonia
VITE_PWA_DESCRIPTION=Sistema de Gestão para Clínica Oncológica
VITE_PWA_THEME_COLOR=
VITE_PWA_BACKGROUND_COLOR=

# ============================================
# HEALTH CHECK
# ============================================
VITE_HEALTH_CHECK_INTERVAL=60000
VITE_API_STATUS_CHECK=true
VITE_SHOW_VERSION=false

# ============================================
# CLINIC INFORMATION
# ============================================
VITE_CLINIC_NAME=Clínica Hormonia
VITE_CLINIC_ADDRESS=Rua das Flores, 123, São Paulo, SP
VITE_CLINIC_PHONE=+55 11 99999-9999
VITE_CLINIC_EMAIL=contato@clinicahormonia.com.br

# ============================================
# MAPS (Optional)
# ============================================
VITE_GOOGLE_MAPS_API_KEY=
VITE_MAPBOX_TOKEN=

# ============================================
# BUILD CONFIGURATION
# ============================================
VITE_BUILD_SOURCEMAP=false
VITE_BUILD_MINIFY=true
VITE_BUILD_TARGET=es2015
VITE_BASE_URL=/
VITE_ASSET_INLINE_LIMIT=4096
VITE_CSS_CODE_SPLIT=true
```

---

## 📝 Quiz Interface Environment Template

**File:** `quiz-mensal-interface/.env.example`

```bash
# ============================================
# QUIZ INTERFACE - PRODUCTION ENVIRONMENT
# ============================================
# 🚨 SECURITY: All NEXT_PUBLIC_* variables are PUBLIC
# Never put secrets in Next.js public environment variables!

# ============================================
# BACKEND API CONFIGURATION
# ============================================
# Set after backend-web service is deployed
NEXT_PUBLIC_API_URL=https://your-backend.railway.app/api/v1
NEXT_PUBLIC_QUIZ_PUBLIC_API_URL=https://your-backend.railway.app/api/v1/monthly-quiz-public

# ============================================
# RUNTIME CONFIGURATION
# ============================================
NODE_ENV=production
NEXT_TELEMETRY_DISABLED=1

# ============================================
# MONITORING & ANALYTICS (Optional)
# ============================================
NEXT_PUBLIC_SENTRY_DSN=
NEXT_PUBLIC_GOOGLE_ANALYTICS_ID=
```

---

## 📝 Root Environment Template

**File:** `.env.example` (Root directory)

```bash
# ============================================
# ROOT ENVIRONMENT TEMPLATE
# ============================================
# This file should typically be empty or only contain
# project-wide development configuration

# ⚠️ DO NOT store Flow Nexus or other service sessions here
# These should be managed by the respective CLI tools

# Example: Project-wide development settings
NODE_ENV=development
```

---

## 🔍 Secret Validation Checklist

Before deploying, verify each secret:

### ✅ Backend Secrets
- [ ] `SECRET_KEY` is 64+ bytes and cryptographically random
- [ ] `JWT_SECRET_KEY` is 64+ bytes and cryptographically random
- [ ] `ENCRYPTION_KEY` is valid Fernet key
- [ ] Firebase private key is valid RSA key
- [ ] Database URL contains correct password
- [ ] Redis password is strong (32+ characters)
- [ ] Gemini API key is valid and restricted
- [ ] Evolution API credentials are current
- [ ] Quiz token secret is 32+ bytes

### ✅ Frontend Secrets
- [ ] All secrets use `VITE_` prefix (for Vite exposure)
- [ ] No private keys or passwords in frontend `.env`
- [ ] Firebase Web API key is public (safe to expose)
- [ ] Supabase Anon key is public (RLS-protected)

### ✅ Security
- [ ] No `.env` files committed to git
- [ ] All `.env` files in `.gitignore`
- [ ] Pre-commit hooks enabled
- [ ] Secret scanning enabled

---

## 🚨 Common Mistakes to Avoid

### ❌ DON'T DO THIS:
```bash
# Weak secrets
SECRET_KEY=mysecret123
JWT_SECRET_KEY=password

# Committing secrets
git add .env
git commit -m "Add configuration"

# Using production secrets in development
DATABASE_URL=<production_database_url>

# Storing secrets in code
const API_KEY = "AIzaSy_REAL_KEY_HERE";
```

### ✅ DO THIS INSTEAD:
```bash
# Strong, generated secrets
SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(64))")

# Never commit secrets
echo ".env" >> .gitignore
git add .env.example

# Use separate environments
DATABASE_URL=<local_development_database_url>

# Load from environment
const API_KEY = process.env.VITE_FIREBASE_API_KEY;
```

---

## 📚 Additional Resources

- [OWASP Secret Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [Railway Environment Variables](https://docs.railway.app/develop/variables)
- [Supabase Security Best Practices](https://supabase.com/docs/guides/platform/going-into-prod#security)
- [Firebase Security Rules](https://firebase.google.com/docs/rules)

---

**Document Version:** 1.0
**Last Updated:** 2025-10-06
**Review Schedule:** Quarterly (every 90 days)
