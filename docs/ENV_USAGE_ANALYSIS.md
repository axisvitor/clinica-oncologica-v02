# Environment Variables Usage Analysis

**Generated:** 2025-10-04
**Scope:** Backend (backend-hormonia/) and Frontend (frontend-hormonia/)

## Executive Summary

This analysis maps ALL environment variables used in code versus those declared in `.env.example` files, identifying:
- ✅ Variables used and documented
- ❌ Variables used but MISSING from .env
- ⚠️ Variables in .env but NEVER used (dead variables)
- 🔄 Variables with naming inconsistencies

---

## Backend Analysis (backend-hormonia/)

### 🔴 CRITICAL: Variables Used in Code but MISSING from .env.example

| Variable | Used In | Purpose | Risk Level |
|----------|---------|---------|------------|
| `WEB_CONCURRENCY` | `config/production.py:48,190,193`<br>`nixpacks.toml:27` | Gunicorn worker count | 🔴 HIGH - Production performance |
| `RAILWAY_ENVIRONMENT` | `config/production.py:10`<br>`app/integrations/evolution.py:124,127`<br>`app/tasks/config.py:159` | Railway detection | 🟡 MEDIUM - Platform detection |
| `RAILWAY_PUBLIC_DOMAIN` | `app/api/v1/config.py:37,72` | Auto-detect backend URL | 🟡 MEDIUM - Config endpoint |
| `RAILWAY_STATIC_URL` | `app/api/v1/config.py:38` | Alternative Railway URL | 🟡 MEDIUM - Config endpoint |
| `SERVICE_NAME` | `app/core/tracing.py:181` | OpenTelemetry service name | 🟢 LOW - Tracing metadata |
| `SERVICE_VERSION` | `app/core/tracing.py:182` | OpenTelemetry service version | 🟢 LOW - Tracing metadata |
| `PORT` | `config/production.py:47`<br>`app/core/application_factory.py:324` | Server bind port | 🔴 HIGH - Runtime required |
| `PYTHONPATH` | `app/core/application_factory.py:328` | Python module path | 🟢 LOW - Debug info only |
| `PWD` | `app/core/application_factory.py:329` | Current working directory | 🟢 LOW - Debug info only |
| `APP_START_TIME` | `app/api/v1/railway_health.py:403` | Uptime calculation | 🟢 LOW - Metrics only |
| `TEST_DATABASE_URL` | `tests/conftest.py:244` | Test database override | 🟢 LOW - Testing only |
| `API_BASE_URL` | `tests/conftest.py:244` | Test API base URL | 🟢 LOW - Testing only |
| `REDIS_ACL_ENABLED` | `app/core/redis_secure.py:128` | Redis ACL authentication | 🟡 MEDIUM - Security feature |
| `REDIS_ACL_USERNAME` | `app/core/redis_secure.py:138` | Redis ACL username | 🟡 MEDIUM - Security feature |
| `REDIS_ENCRYPTION_KEY` | `app/core/redis_secure.py:65` | Redis data encryption | 🟡 MEDIUM - Security feature |
| `REDIS_ENABLE_ENCRYPTION` | `app/core/redis_secure.py:58` | Enable Redis encryption | 🟡 MEDIUM - Security feature |
| `REDIS_RETRY_ON_TIMEOUT` | `app/core/redis_secure.py:54`<br>`app/core/secure_config.py:131` | Redis retry behavior | 🟢 LOW - Resilience config |
| `REDIS_MAX_RETRIES` | `app/core/redis_secure.py:55`<br>`app/core/secure_config.py:132` | Redis max retry attempts | 🟢 LOW - Resilience config |
| `REDIS_ENABLE_DB_ISOLATION` | `app/config.py:151` (Field exists but not in .env.example) | Separate Redis DBs for cache/broker | 🟡 MEDIUM - Production optimization |
| `REDIS_CACHE_DB` | `app/config.py:149` (Field exists but not in .env.example) | Redis DB number for cache | 🟡 MEDIUM - Production optimization |
| `REDIS_BROKER_DB` | `app/config.py:150` (Field exists but not in .env.example) | Redis DB number for Celery broker | 🟡 MEDIUM - Production optimization |
| `RATE_LIMIT_ENABLED` | `app/core/security_config.py:196,197` | Enable/disable rate limiting | 🟡 MEDIUM - Security feature |
| `RATE_LIMIT_PER_MINUTE` | `app/core/security_config.py:198,199` | Rate limit threshold | 🟡 MEDIUM - Security feature |
| `AUTH_LOGIN_RATE_LIMIT` | `app/core/security_config.py:200,201` | Auth-specific rate limit | 🟡 MEDIUM - Security feature |
| `REQUIRE_EMAIL_VERIFICATION` | `app/core/security_config.py:208,209` | Email verification requirement | 🟡 MEDIUM - Auth security |
| `PASSWORD_MIN_LENGTH` | `app/core/security_config.py:210,211` | Minimum password length | 🟡 MEDIUM - Auth security |
| `SESSION_TIMEOUT_MINUTES` | `app/core/security_config.py:212,213` | Session timeout duration | 🟡 MEDIUM - Auth security |
| `MFA_ENABLED` | `app/core/security_config.py:214,215` | Multi-factor authentication | 🟡 MEDIUM - Auth security |
| `TRUSTED_DOMAINS` | `app/core/security_config.py:222,223` | Trusted domain whitelist | 🟡 MEDIUM - Security config |
| `BLOCKED_DOMAINS` | `app/core/security_config.py:224,225` | Blocked domain list | 🟡 MEDIUM - Security config |
| `CORS_ALLOW_ORIGINS` | `app/core/security_config.py:232,233` | Alternative CORS config | 🟡 MEDIUM - Security config |
| `MAX_REQUEST_SIZE_MB` | `app/core/security_config.py:234,235` | Max request body size | 🟡 MEDIUM - Security config |
| `ENABLE_AUTO_PROVISIONING` | `app/core/security_config.py:241,242` | Auto-provision users | 🟡 MEDIUM - Security feature |
| `EVOLUTION_RAILWAY_URL` | `app/integrations/evolution.py:127,128` | Railway-specific Evolution URL | 🟢 LOW - Platform-specific |
| `MINIMAL_ROUTERS` | `app/core/router_registry.py.bak:30` | Minimal router mode (backup file) | 🟢 LOW - Deprecated |
| `REDIS_CONNECT_TIMEOUT` | Referenced in docs | Redis connection timeout | 🟢 LOW - Resilience config |
| `ENABLE_DEBUG_ENDPOINTS` | `app/core/application_factory.py:60` | Enable debug endpoints | 🟢 LOW - Development feature |

### ⚠️ Variables in .env.example but NEVER Used (Dead Variables)

| Variable | Declared In | Status |
|----------|-------------|--------|
| `SUPABASE_AVATARS_BUCKET` | Line 59 | NOT FOUND in codebase - Storage bucket name |
| `DB_POOL_TIMEOUT` | Line 71 | NOT FOUND in direct usage - Only in config.py Field |
| `DB_STATEMENT_TIMEOUT` | Line 72 | NOT FOUND in codebase |
| `DB_POOL_RECYCLE` | Line 73 | NOT FOUND in direct usage - Only in config.py Field |

**Note:** These variables may be used indirectly through `settings.*` in Pydantic Settings.

### ✅ Variables Correctly Documented and Used

Variables that exist in `.env.example` AND are actively used in code:

#### Core Application
- `ENVIRONMENT` - Used in 10+ files for environment detection
- `DEBUG` - Used extensively for debug mode checks
- `SECRET_KEY` - JWT signing and encryption
- `ALGORITHM` - JWT algorithm configuration
- `ACCESS_TOKEN_EXPIRE_MINUTES` - Token expiration
- `REFRESH_TOKEN_EXPIRE_DAYS` - Refresh token expiration
- `BCRYPT_ROUNDS` - Password hashing rounds

#### Firebase Admin SDK
- `FIREBASE_ADMIN_PROJECT_ID` - Firebase project identifier
- `FIREBASE_ADMIN_PRIVATE_KEY` - Service account private key
- `FIREBASE_ADMIN_CLIENT_EMAIL` - Service account email
- `FIREBASE_ALLOWED_DOMAINS` - Allowed email domains (JSON array)
- `FIREBASE_BLOCK_PUBLIC_DOMAINS` - Block public emails (gmail, etc.)

#### Firebase Frontend Config (served via /config endpoint)
- `FIREBASE_WEB_API_KEY` - Public web API key
- `FIREBASE_WEB_PROJECT_ID` - Public project ID
- `FIREBASE_WEB_APP_ID` - Public app ID
- `FIREBASE_AUTH_DOMAIN` - Auth domain

#### Database
- `DATABASE_URL` - PostgreSQL connection string
- `DB_POOL_SIZE` - Connection pool size
- `DB_MAX_OVERFLOW` - Max overflow connections

#### Redis
- `REDIS_URL` - Main Redis connection URL
- `REDIS_PASSWORD` - Redis authentication
- `REDIS_HOST` - Redis server host
- `REDIS_PORT` - Redis server port
- `REDIS_SSL` - Enable SSL/TLS
- `REDIS_SSL_CERT_REQS` - SSL certificate requirements
- `REDIS_MAX_CONNECTIONS` - Connection pool size
- `REDIS_SOCKET_TIMEOUT` - Socket timeout

#### Celery
- `CELERY_BROKER_URL` - Message broker URL
- `CELERY_RESULT_BACKEND` - Result backend URL
- `CELERY_WORKER_CONCURRENCY` - Worker concurrency
- `CELERY_WORKER_MAX_TASKS_PER_CHILD` - Task limit per worker
- `CELERY_WORKER_TIME_LIMIT` - Hard task timeout
- `CELERY_WORKER_SOFT_TIME_LIMIT` - Soft task timeout
- `CELERY_QUEUES` - Queue names

#### AI Services
- `GEMINI_API_KEY` - Google Gemini API key
- `GEMINI_MODEL` - Model name
- `GEMINI_TEMPERATURE` - Generation temperature
- `GEMINI_MAX_OUTPUT_TOKENS` - Max output tokens

#### Evolution API (WhatsApp)
- `ENABLE_EVOLUTION` - Enable WhatsApp integration
- `EVOLUTION_API_URL` - Evolution API base URL
- `EVOLUTION_INSTANCE_NAME` - Instance identifier
- `EVOLUTION_API_KEY` - API authentication key
- `EVOLUTION_WEBHOOK_SECRET` - Webhook signature validation
- `EVOLUTION_WEBHOOK_URL` - Webhook callback URL

#### Monthly Quiz
- `MONTHLY_QUIZ_VIA_LINK` - Enable link-based quiz
- `MONTHLY_QUIZ_BASE_URL` - Quiz interface URL
- `MONTHLY_QUIZ_TOKEN_SECRET` - Token signing secret
- `MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS` - Link expiration

#### CORS
- `ALLOWED_ORIGINS` - Allowed CORS origins (JSON array)
- `ALLOWED_HOSTS` - Allowed HTTP hosts

#### Monitoring
- `MONITORING_ENABLED` - Enable monitoring system
- `LOG_LEVEL` - Logging level
- `SENTRY_DSN` - Sentry error tracking

#### Security
- `ENABLE_FIELD_ENCRYPTION` - Enable field-level encryption
- `ENCRYPTION_KEY` - Encryption key for sensitive data
- `LGPD_COMPLIANCE_MODE` - LGPD compliance enforcement
- `AUDIT_LOG_RETENTION_DAYS` - Audit log retention
- `DATA_RETENTION_DAYS` - Data retention policy

---

## Frontend Analysis (frontend-hormonia/)

### 🔴 CRITICAL: Variables Used in Code but MISSING from .env.example

| Variable | Used In | Purpose | Risk Level |
|----------|---------|---------|------------|
| `VITE_API_BASE_URL` | `src/lib/runtime-config.ts:133`<br>`public/api/config.js:55` | Alternative API URL variable | 🟡 MEDIUM - Fallback config |
| `VITE_OPENAI_API_KEY` | `src/lib/runtime-config.ts:139` | OpenAI API key (frontend) | 🔴 HIGH - Security risk if used |
| `VITE_LANGCHAIN_API_KEY` | `src/lib/runtime-config.ts:140` | LangChain API key (frontend) | 🔴 HIGH - Security risk if used |
| `VITE_GEMINI_API_KEY` | `src/lib/runtime-config.ts:141` | Gemini API key (frontend) | 🔴 HIGH - Security risk if used |

**⚠️ SECURITY WARNING:** API keys for OpenAI, LangChain, and Gemini should NEVER be in frontend environment variables. These are server-side secrets. Frontend code references them but they should not be configured.

### ⚠️ Variables in .env.example but NEVER Used (Potential Dead Variables)

| Variable | Declared In | Status | Notes |
|----------|-------------|--------|-------|
| `VITE_SUPABASE_URL` | Line 54 | CONDITIONALLY USED | Used in `config-runtime.ts` but Supabase auth is replaced by Firebase |
| `VITE_SUPABASE_ANON_KEY` | Line 55 | CONDITIONALLY USED | Used in `config-runtime.ts` but Supabase auth is replaced by Firebase |
| `VITE_SUPABASE_AUTH_ENABLED` | Line 56 | NOT FOUND | Feature flag for Supabase auth (deprecated) |
| `VITE_SUPABASE_REALTIME_ENABLED` | Line 57 | NOT FOUND | Feature flag for Supabase realtime (deprecated) |
| `VITE_APP_NAME` | Line 68 | NOT FOUND | Application name metadata |
| `VITE_APP_VERSION` | Line 69 | NOT FOUND | Application version |
| `VITE_ENABLE_WHATSAPP_INTEGRATION` | Line 77 | NOT FOUND | WhatsApp UI toggle |
| `VITE_ENABLE_AI_CHAT` | Line 78 | NOT FOUND | AI chat UI toggle |
| `VITE_ENABLE_APPOINTMENT_BOOKING` | Line 79 | NOT FOUND | Appointment booking toggle |
| `VITE_ENABLE_PATIENT_PORTAL` | Line 80 | NOT FOUND | Patient portal toggle |
| `VITE_ENABLE_TELEMEDICINE` | Line 81 | NOT FOUND | Telemedicine toggle |
| `VITE_ENABLE_DARK_MODE` | Line 82 | NOT FOUND | Dark mode toggle |
| `VITE_ENABLE_EVOLUTION` | Line 83 | NOT FOUND | Evolution integration toggle |
| `VITE_ENABLE_DEBUG_TOOLS` | Line 86 | NOT FOUND | Debug tools toggle |
| `VITE_ENABLE_MOCK_DATA` | Line 87 | NOT FOUND | Mock data toggle |
| `VITE_USE_MOCK_API` | Line 88 | NOT FOUND | Mock API toggle |
| `VITE_USE_MOCK_AUTH` | Line 89 | NOT FOUND | Mock auth toggle |
| `VITE_JWT_STORAGE_KEY` | Line 106 | NOT FOUND | Local storage key name |
| `VITE_JWT_REFRESH_KEY` | Line 107 | NOT FOUND | Refresh token storage key |
| `VITE_ENABLE_CSP` | Line 110 | NOT FOUND | Content Security Policy toggle |
| `VITE_FORCE_HTTPS` | Line 111 | NOT FOUND | Force HTTPS toggle |
| `VITE_SECURITY_HEADERS_ENABLED` | Line 112 | NOT FOUND | Security headers toggle |
| `VITE_PRIMARY_COLOR` | Line 119 | NOT FOUND | Theme primary color |
| `VITE_SECONDARY_COLOR` | Line 120 | NOT FOUND | Theme secondary color |
| `VITE_SUCCESS_COLOR` | Line 121 | NOT FOUND | Theme success color |
| `VITE_ERROR_COLOR` | Line 122 | NOT FOUND | Theme error color |
| `VITE_WARNING_COLOR` | Line 123 | NOT FOUND | Theme warning color |
| `VITE_SIDEBAR_WIDTH` | Line 126 | NOT FOUND | Layout sidebar width |
| `VITE_HEADER_HEIGHT` | Line 127 | NOT FOUND | Layout header height |
| `VITE_FOOTER_HEIGHT` | Line 128 | NOT FOUND | Layout footer height |
| `VITE_DEFAULT_PAGE_SIZE` | Line 131 | NOT FOUND | Pagination default |
| `VITE_MAX_PAGE_SIZE` | Line 132 | NOT FOUND | Pagination max |
| `VITE_REQUEST_TIMEOUT` | Line 139 | NOT FOUND | HTTP request timeout |
| `VITE_REQUEST_RETRY_ATTEMPTS` | Line 140 | NOT FOUND | Request retry count |
| `VITE_REQUEST_RETRY_DELAY` | Line 141 | NOT FOUND | Retry delay |
| `VITE_CACHE_DURATION` | Line 144 | NOT FOUND | Cache TTL |
| `VITE_IMAGE_CACHE_DURATION` | Line 145 | NOT FOUND | Image cache TTL |
| `VITE_ALLOWED_FILE_TYPES` | Line 153 | NOT FOUND | File upload types |
| `VITE_UPLOAD_CHUNK_SIZE` | Line 154 | NOT FOUND | Upload chunk size |
| `VITE_DEFAULT_LANGUAGE` | Line 162 | NOT FOUND | Default locale |
| `VITE_SUPPORTED_LANGUAGES` | Line 163 | NOT FOUND | Supported locales |
| `VITE_TIMEZONE` | Line 164 | NOT FOUND | Default timezone |
| `VITE_DATE_FORMAT` | Line 167 | NOT FOUND | Date format pattern |
| `VITE_TIME_FORMAT` | Line 168 | NOT FOUND | Time format pattern |
| `VITE_DATETIME_FORMAT` | Line 169 | NOT FOUND | DateTime format pattern |
| `VITE_WHATSAPP_MAX_FILE_SIZE` | Line 177 | NOT FOUND | WhatsApp file size limit |
| `VITE_ENABLE_ERROR_REPORTING` | Line 184 | NOT FOUND | Error reporting toggle |
| `VITE_ENABLE_PERFORMANCE_MONITORING` | Line 185 | NOT FOUND | Performance monitoring toggle |
| `VITE_ANALYTICS_TRACKING_ID` | Line 192 | NOT FOUND | Analytics tracking ID (used in runtime-config but not consumed) |
| `VITE_PWA_ENABLED` | Line 199 | NOT FOUND | PWA toggle |
| `VITE_PWA_SHORT_NAME` | Line 200 | NOT FOUND | PWA short name |
| `VITE_PWA_DESCRIPTION` | Line 201 | NOT FOUND | PWA description |
| `VITE_PWA_THEME_COLOR` | Line 202 | NOT FOUND | PWA theme color |
| `VITE_PWA_BACKGROUND_COLOR` | Line 203 | NOT FOUND | PWA background color |
| `VITE_HEALTH_CHECK_INTERVAL` | Line 210 | NOT FOUND | Health check interval |
| `VITE_API_STATUS_CHECK` | Line 211 | NOT FOUND | API status check toggle |
| `VITE_SHOW_VERSION` | Line 214 | NOT FOUND | Show version toggle |
| `VITE_CLINIC_NAME` | Line 221 | NOT FOUND | Clinic branding name |
| `VITE_CLINIC_ADDRESS` | Line 222 | NOT FOUND | Clinic address |
| `VITE_CLINIC_PHONE` | Line 223 | NOT FOUND | Clinic phone |
| `VITE_CLINIC_EMAIL` | Line 224 | NOT FOUND | Clinic email |
| `VITE_GOOGLE_ANALYTICS_ID` | Line 235 | NOT FOUND | Google Analytics ID |
| `VITE_HOTJAR_ID` | Line 236 | NOT FOUND | Hotjar tracking ID |
| `VITE_MIXPANEL_TOKEN` | Line 237 | NOT FOUND | Mixpanel token |
| `VITE_GOOGLE_MAPS_API_KEY` | Line 240 | NOT FOUND | Google Maps API key |
| `VITE_MAPBOX_TOKEN` | Line 241 | NOT FOUND | Mapbox token |
| `VITE_BUILD_SOURCEMAP` | Line 248 | NOT FOUND | Build sourcemap toggle |
| `VITE_BUILD_MINIFY` | Line 249 | NOT FOUND | Build minify toggle |
| `VITE_BUILD_TARGET` | Line 250 | NOT FOUND | Build target |
| `VITE_BASE_URL` | Line 253 | NOT FOUND | Base URL for deployment |
| `VITE_ASSET_INLINE_LIMIT` | Line 256 | NOT FOUND | Asset inline limit |
| `VITE_CSS_CODE_SPLIT` | Line 257 | NOT FOUND | CSS code split toggle |

**Note:** Many of these are feature flags or UI configuration that may have been planned but not implemented yet.

### ✅ Variables Correctly Documented and Used

Variables that exist in `.env.example` AND are actively used in code:

#### Backend Connection
- `VITE_API_URL` - Backend API base URL (primary variable)
- `VITE_WS_URL` - WebSocket connection URL
- `VITE_API_BASE_PATH` - API base path prefix
- `VITE_API_TIMEOUT` - Request timeout

#### Firebase Authentication (Client SDK)
- `VITE_FIREBASE_API_KEY` - Public Firebase API key
- `VITE_FIREBASE_AUTH_DOMAIN` - Auth domain
- `VITE_FIREBASE_PROJECT_ID` - Project identifier
- `VITE_FIREBASE_STORAGE_BUCKET` - Storage bucket
- `VITE_FIREBASE_MESSAGING_SENDER_ID` - Messaging sender ID
- `VITE_FIREBASE_APP_ID` - App identifier
- `VITE_FIREBASE_MEASUREMENT_ID` - Analytics measurement ID

#### Application Configuration
- `VITE_ENVIRONMENT` - Environment name (development/production)
- `VITE_DEBUG_MODE` - Debug mode toggle

#### Feature Flags (Used in runtime-config.ts)
- `VITE_AI_CHAT_ENABLED` - AI chat feature toggle
- `VITE_AI_ANALYTICS_ENABLED` - AI analytics toggle
- `VITE_AI_INSIGHTS_ENABLED` - AI insights toggle
- `VITE_AI_RECOMMENDATIONS_ENABLED` - AI recommendations toggle

#### Session Management
- `VITE_SESSION_TIMEOUT` - Session timeout duration
- `VITE_TOKEN_REFRESH_THRESHOLD` - Token refresh threshold

#### File Upload
- `VITE_MAX_FILE_SIZE` - Max file size limit
- `VITE_SUPPORTED_FILE_TYPES` - Allowed MIME types

#### WhatsApp Integration
- `VITE_WHATSAPP_INSTANCE_NAME` - WhatsApp instance identifier

#### Monitoring
- `VITE_SENTRY_DSN` - Sentry error tracking DSN

---

## Naming Inconsistencies

### Backend

1. **Redis Configuration:**
   - `.env.example` uses: `REDIS_URL`, `REDIS_PASSWORD`, `REDIS_HOST`, `REDIS_PORT`
   - Code also checks: `REDIS_ACL_ENABLED`, `REDIS_ACL_USERNAME` (not in .env)

2. **Rate Limiting:**
   - `app/config.py` has: `RATE_LIMIT_ENABLED`, `RATE_LIMIT_REDIS_URL`
   - `app/core/security_config.py` looks for: `RATE_LIMIT_PER_MINUTE`, `AUTH_LOGIN_RATE_LIMIT`
   - Not consistent across modules

3. **Database Pool:**
   - `.env.example`: `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `DB_STATEMENT_TIMEOUT`, `DB_POOL_RECYCLE`
   - `app/config.py` uses Fields for all of these
   - `app/core/secure_config.py` uses: `os.getenv()` for pool settings
   - Some used via Pydantic, some via direct os.getenv()

### Frontend

1. **API URL Variables:**
   - Primary: `VITE_API_URL`
   - Alternative: `VITE_API_BASE_URL` (used in code, not in .env)
   - Inconsistent naming between runtime-config.ts and other files

2. **WebSocket URL:**
   - `.env.example`: `VITE_WS_URL`
   - Code also uses: `VITE_WS_BASE_URL` (in runtime-config.ts)

---

## Recommendations

### Backend: Add to .env.example

**HIGH PRIORITY (Production Critical):**
```bash
# ===================================
# SERVER CONFIGURATION
# ===================================
PORT=8000
WEB_CONCURRENCY=4

# ===================================
# RAILWAY PLATFORM VARIABLES (Auto-populated)
# ===================================
# RAILWAY_ENVIRONMENT=production
# RAILWAY_PUBLIC_DOMAIN=your-app.railway.app
# RAILWAY_STATIC_URL=your-app-production.up.railway.app

# ===================================
# REDIS ADVANCED CONFIGURATION
# ===================================
# Redis Database Isolation (separate DBs for cache vs Celery broker)
REDIS_ENABLE_DB_ISOLATION=true
REDIS_CACHE_DB=1
REDIS_BROKER_DB=0

# Redis Security (optional advanced features)
REDIS_ACL_ENABLED=false
REDIS_ACL_USERNAME=default
REDIS_ENABLE_ENCRYPTION=false
# REDIS_ENCRYPTION_KEY=  # Required if REDIS_ENABLE_ENCRYPTION=true

# Redis Resilience
REDIS_RETRY_ON_TIMEOUT=true
REDIS_MAX_RETRIES=3

# ===================================
# RATE LIMITING CONFIGURATION
# ===================================
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
AUTH_LOGIN_RATE_LIMIT=5

# ===================================
# AUTHENTICATION SECURITY
# ===================================
REQUIRE_EMAIL_VERIFICATION=false
PASSWORD_MIN_LENGTH=8
SESSION_TIMEOUT_MINUTES=60
MFA_ENABLED=false

# ===================================
# DOMAIN SECURITY
# ===================================
TRUSTED_DOMAINS=[]
BLOCKED_DOMAINS=[]

# ===================================
# API SECURITY
# ===================================
MAX_REQUEST_SIZE_MB=10

# ===================================
# TRACING (OPTIONAL)
# ===================================
SERVICE_NAME=clinica-oncologica
SERVICE_VERSION=2.0.0
```

**MEDIUM PRIORITY (Feature Toggles):**
```bash
# ===================================
# FEATURE FLAGS
# ===================================
ENABLE_AUTO_PROVISIONING=true
ENABLE_DEBUG_ENDPOINTS=false
```

### Backend: Remove from .env.example (Dead Variables)

Consider removing these if truly unused:
- `SUPABASE_AVATARS_BUCKET` (storage bucket not implemented)
- `DB_STATEMENT_TIMEOUT` (not used anywhere)

Or add usage documentation if they are used via Pydantic Fields.

### Frontend: Add to .env.example

**CRITICAL - Fix API Key Security:**
```bash
# ===================================
# ⚠️ WARNING: DO NOT USE THESE VARIABLES IN PRODUCTION
# ===================================
# AI API keys should NEVER be in frontend environment variables
# These are server-side secrets and should only be in backend .env
#
# If you need AI features in frontend:
# 1. Call backend API endpoints that use AI services
# 2. Backend handles API keys securely
# 3. Frontend only receives processed results
#
# VITE_OPENAI_API_KEY=  # ❌ DO NOT USE
# VITE_LANGCHAIN_API_KEY=  # ❌ DO NOT USE
# VITE_GEMINI_API_KEY=  # ❌ DO NOT USE
```

**Add Alternative Variable:**
```bash
# Alternative API URL variable (used as fallback)
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

### Frontend: Clean Up Dead Variables

**Option 1:** Remove all unused feature flags and UI config from `.env.example` (70+ variables)

**Option 2:** Document them as "planned features" and mark as optional:
```bash
# ===================================
# PLANNED FEATURES (NOT YET IMPLEMENTED)
# ===================================
# The following variables are defined for future features
# They currently have no effect on the application

# Feature Toggles (Planned)
# VITE_ENABLE_DARK_MODE=true
# VITE_ENABLE_AI_CHAT=true
# ... etc
```

### Code Cleanup

**Backend:**
1. Standardize variable access: Use `settings.*` everywhere (Pydantic) instead of mixing with `os.getenv()`
2. Remove `MINIMAL_ROUTERS` usage from backup file `router_registry.py.bak`
3. Document which variables are Railway auto-injected vs user-configured

**Frontend:**
1. Remove API key references from `src/lib/runtime-config.ts` (lines 139-141)
2. Standardize on `VITE_API_URL` OR `VITE_API_BASE_URL` (not both)
3. Standardize on `VITE_WS_URL` OR `VITE_WS_BASE_URL` (not both)
4. Remove or implement all unused feature flags

---

## Complete Variable Mapping

### Backend: Settings Class Fields (app/config.py)

All these are loaded via Pydantic Settings from `.env`:

| Field Name | Type | Default | Env Variable |
|------------|------|---------|--------------|
| DEBUG | bool | True | DEBUG |
| ENVIRONMENT | str | "development" | ENVIRONMENT |
| SECRET_KEY | str | REQUIRED | SECRET_KEY |
| ALGORITHM | str | "HS256" | ALGORITHM |
| ACCESS_TOKEN_EXPIRE_MINUTES | int | 30 | ACCESS_TOKEN_EXPIRE_MINUTES |
| REFRESH_TOKEN_EXPIRE_DAYS | int | 7 | REFRESH_TOKEN_EXPIRE_DAYS |
| BCRYPT_ROUNDS | int | 12 | BCRYPT_ROUNDS |
| SUPABASE_URL | str | REQUIRED | SUPABASE_URL |
| SUPABASE_ANON_KEY | str | REQUIRED | SUPABASE_ANON_KEY |
| SUPABASE_SERVICE_ROLE_KEY | str | REQUIRED | SUPABASE_SERVICE_ROLE_KEY |
| AUTO_PROVISION_SUPABASE_USERS | bool | False | AUTO_PROVISION_SUPABASE_USERS |
| FIREBASE_ADMIN_PROJECT_ID | Optional[str] | None | FIREBASE_ADMIN_PROJECT_ID |
| FIREBASE_ADMIN_PRIVATE_KEY | Optional[str] | None | FIREBASE_ADMIN_PRIVATE_KEY |
| FIREBASE_ADMIN_CLIENT_EMAIL | Optional[str] | None | FIREBASE_ADMIN_CLIENT_EMAIL |
| FIREBASE_ALLOWED_DOMAINS | List[str] | [] | FIREBASE_ALLOWED_DOMAINS |
| FIREBASE_REQUIRE_CUSTOM_CLAIMS | bool | True | FIREBASE_REQUIRE_CUSTOM_CLAIMS |
| FIREBASE_ALLOWED_ROLES | List[str] | ['admin', 'super_admin', 'doctor', 'medico'] | FIREBASE_ALLOWED_ROLES |
| FIREBASE_ENABLE_AUDIT_LOGGING | bool | True | FIREBASE_ENABLE_AUDIT_LOGGING |
| FIREBASE_BLOCK_PUBLIC_DOMAINS | bool | True | FIREBASE_BLOCK_PUBLIC_DOMAINS |
| FIREBASE_PUBLIC_DOMAINS_BLOCKLIST | List[str] | ['gmail.com', ...] | FIREBASE_PUBLIC_DOMAINS_BLOCKLIST |
| DATABASE_URL | str | REQUIRED | DATABASE_URL |
| REDIS_URL | str | "rediss://localhost:6379" | REDIS_URL |
| REDIS_PASSWORD | Optional[str] | None | REDIS_PASSWORD |
| REDIS_HOST | str | "localhost" | REDIS_HOST |
| REDIS_PORT | int | 6379 | REDIS_PORT |
| REDIS_SSL | bool | True | REDIS_SSL |
| REDIS_SSL_CERT_REQS | str | "required" | REDIS_SSL_CERT_REQS |
| REDIS_MAX_CONNECTIONS | int | 10 | REDIS_MAX_CONNECTIONS |
| REDIS_SOCKET_TIMEOUT | float | 30.0 | REDIS_SOCKET_TIMEOUT |
| REDIS_CACHE_DB | int | 1 | REDIS_CACHE_DB |
| REDIS_BROKER_DB | int | 0 | REDIS_BROKER_DB |
| REDIS_ENABLE_DB_ISOLATION | bool | True | REDIS_ENABLE_DB_ISOLATION |
| RATE_LIMIT_ENABLED | bool | True | RATE_LIMIT_ENABLED |
| RATE_LIMIT_REDIS_URL | Optional[str] | None | RATE_LIMIT_REDIS_URL |
| ENABLE_EVOLUTION | bool | True | ENABLE_EVOLUTION |
| EVOLUTION_API_URL | str | "http://localhost:8080" | EVOLUTION_API_URL |
| EVOLUTION_INSTANCE_NAME | str | "clinica_oncologica" | EVOLUTION_INSTANCE_NAME |
| EVOLUTION_API_KEY | str | "your-evolution-api-key-here" | EVOLUTION_API_KEY |
| EVOLUTION_WEBHOOK_SECRET | Optional[str] | None | EVOLUTION_WEBHOOK_SECRET |
| EVOLUTION_WEBHOOK_URL | Optional[str] | None | EVOLUTION_WEBHOOK_URL |
| GEMINI_API_KEY | Optional[str] | None | GEMINI_API_KEY |
| GEMINI_MODEL | str | "gemini-2.0-flash-exp" | GEMINI_MODEL |
| GEMINI_TEMPERATURE | float | 0.7 | GEMINI_TEMPERATURE |
| GEMINI_MAX_OUTPUT_TOKENS | int | 500 | GEMINI_MAX_OUTPUT_TOKENS |
| CELERY_BROKER_URL | str | "rediss://localhost:6379/0" | CELERY_BROKER_URL |
| CELERY_RESULT_BACKEND | str | "rediss://localhost:6379/1" | CELERY_RESULT_BACKEND |
| ALLOWED_ORIGINS | List[str] | [localhost URLs, Railway URLs] | ALLOWED_ORIGINS |
| MONTHLY_QUIZ_VIA_LINK | bool | True | MONTHLY_QUIZ_VIA_LINK |
| MONTHLY_QUIZ_BASE_URL | str | "http://localhost:3001" | MONTHLY_QUIZ_BASE_URL |
| MONTHLY_QUIZ_TOKEN_SECRET | str | "change-this" | MONTHLY_QUIZ_TOKEN_SECRET |
| MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS | int | 72 | MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS |
| MONITORING_ENABLED | bool | True | MONITORING_ENABLED |
| LOG_LEVEL | str | "INFO" | LOG_LEVEL |

**Total Fields in Settings Class:** 100+

---

## Security Risks Identified

### 🔴 CRITICAL

1. **Frontend API Keys** - `VITE_OPENAI_API_KEY`, `VITE_LANGCHAIN_API_KEY`, `VITE_GEMINI_API_KEY` referenced in code
   - **Risk:** Exposing API keys in frontend bundle
   - **Fix:** Remove from frontend, use backend proxies

2. **Missing WEB_CONCURRENCY** - Production performance affected
   - **Risk:** Suboptimal worker count in production
   - **Fix:** Add to .env.example with recommended value (4)

### 🟡 MEDIUM

1. **Inconsistent Variable Access** - Mix of `os.getenv()` and `settings.*`
   - **Risk:** Configuration drift, harder to validate
   - **Fix:** Standardize on Pydantic Settings

2. **Undocumented Security Variables** - Rate limiting, MFA, session timeout
   - **Risk:** Security features disabled by default
   - **Fix:** Document in .env.example with secure defaults

---

## Conclusion

**Backend:** 30+ variables used but missing from `.env.example`
**Frontend:** 4 critical variables used but missing, 70+ declared but unused

**Recommended Actions:**
1. Update backend `.env.example` with missing production variables
2. Remove frontend API key references (security risk)
3. Clean up 70+ unused frontend feature flags
4. Standardize variable access patterns (Pydantic only)
5. Document Railway auto-injected variables separately

**Next Steps:**
1. Create PR with updated `.env.example` files
2. Audit code for direct `os.getenv()` usage → migrate to `settings.*`
3. Remove dead variables from frontend
4. Add runtime validation for critical missing variables
