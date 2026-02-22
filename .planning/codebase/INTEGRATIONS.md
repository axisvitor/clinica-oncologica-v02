# External Integrations

**Analysis Date:** 2026-02-22

## APIs & External Services

**Messaging:**
- Evolution API (WhatsApp) - Sending and receiving WhatsApp messages to patients
  - SDK/Client: custom `httpx`-based client at `backend-hormonia/app/integrations/evolution/client.py`
  - Auth: `WHATSAPP_EVOLUTION_API_KEY` env var, passed as API key header
  - Webhook: receives events at `/webhooks/whatsapp/evolution/{INSTANCE_NAME}` (HMAC-SHA256 validated)
  - Config: `WHATSAPP_EVOLUTION_API_URL`, `WHATSAPP_EVOLUTION_INSTANCE_NAME`
  - Mock mode: `WHATSAPP_EVOLUTION_USE_MOCK=true` for development/testing

**AI / LLM:**
- Google Gemini - Patient message humanization, quiz question generation, clinical insights
  - SDK/Client: `langchain-google-genai` and `google-ai-generativelanguage`
  - Auth: `AI_GEMINI_API_KEY` env var
  - LangGraph orchestration at `backend-hormonia/app/ai/langgraph/` (graphs, nodes, state machine)
  - PII redaction before Gemini calls: `backend-hormonia/app/ai/pii_redaction.py`
  - LangChain tracing: `AI_LANGCHAIN_API_KEY` (optional, `AI_LANGCHAIN_ENABLE_TRACING_V2=false` by default)
  - Models: `AI_GEMINI_MODEL` (default `gemini-3-flash-preview`)

**PDF Generation:**
- ReportLab 4.4 - On-demand clinical PDF reports
  - Integration point: `backend-hormonia/app/integrations/pdf_generator.py`
  - No external API; pure local library

**Notifications (Alerting):**
- Slack - Operational alerts via webhooks
  - Auth: `SLACK_WEBHOOK_URL` env var
  - Channel: `SLACK_DEFAULT_CHANNEL` (default `#alerts`)
  - Client: `httpx` in `backend-hormonia/app/services/notification_service.py`
- PagerDuty - On-call incident escalation
  - Auth: `PAGERDUTY_API_KEY`, `PAGERDUTY_SERVICE_KEY` env vars
  - Client: `httpx` in `backend-hormonia/app/services/notification_service.py`
- Email (SMTP) - Notification channel
  - Server: `SMTP_HOST` (default `smtp.gmail.com`), `SMTP_PORT=587`
  - Auth: `SMTP_USERNAME`, `SMTP_PASSWORD` env vars
  - TLS: `SMTP_ENABLE_TLS=true`
  - Client: Python `smtplib` in `backend-hormonia/app/services/notification_service.py`

**Security Scanning:**
- ClamAV - Virus scanning for file uploads (optional, `CLAMAV_ENABLED=false` by default)
  - Connection: `CLAMAV_HOST:CLAMAV_PORT` (default `localhost:3310`)

## Data Storage

**Primary Database:**
- PostgreSQL (AWS RDS)
  - Connection: `DATABASE_URL` env var (`postgresql+psycopg://...?sslmode=require`)
  - Driver: psycopg3 (`psycopg[binary]` for sync, `asyncpg` for async background tasks)
  - ORM: SQLAlchemy 2.0 with session-based pattern
  - Pool: `DATABASE_POOL_SIZE=30`, `DATABASE_POOL_MAX_OVERFLOW=40`
  - Migrations: Alembic at `backend-hormonia/alembic/`
  - SSL: required (`sslmode=require` in connection URL)

**Cache / Message Broker:**
- Dragonfly (Redis-compatible drop-in replacement)
  - Connection: `REDIS_URL` env var (e.g., `redis://10.109.61.19:6379/0`)
  - Client: `redis-py` >=6.4.0 via `RedisManager` singleton at `backend-hormonia/app/core/redis_manager/manager.py`
  - DB isolation: 4 logical databases
    - DB 0: Celery broker (`CELERY_BROKER_URL`, `REDIS_BROKER_DB_NUMBER=0`)
    - DB 1: Celery result backend + cache (`CELERY_RESULT_BACKEND`, `REDIS_CACHE_DB_NUMBER=1`)
    - DB 2: Session storage (`REDIS_SESSION_DB_NUMBER=2`)
    - DB 3: Rate limiting (`RATE_LIMIT_REDIS_URL`, `REDIS_RATE_LIMIT_DB_NUMBER=3`)
  - SSL: optional (`REDIS_ENABLE_SSL=false` in production Memorystore; `rediss://` for TLS)
  - Local dev: via Docker container defined in `backend-hormonia/docker-compose.yml`

**File Storage:**
- Local filesystem - File uploads stored at `backend-hormonia/uploads/`
  - Max size: `UPLOAD_MAX_SIZE_BYTES=10485760` (10 MB)
  - No external cloud storage (S3, GCS) configured

**In-Memory (Test):**
- fakeredis >=2.20.0 - In-memory Redis replacement for tests

## Authentication & Identity

**Firebase Authentication:**
- Provider: Firebase Auth (Google Cloud)
- Backend: `firebase-admin >=6.9.0` SDK for token verification
  - Service account configured via: `FIREBASE_ADMIN_PROJECT_ID`, `FIREBASE_ADMIN_CLIENT_EMAIL`, `FIREBASE_ADMIN_PRIVATE_KEY` env vars
  - Service account key file also present: `clinica-oncologica-hosting-firebase-adminsdk-fbsvc-0c279a6456.json` (root directory)
  - Token cache TTL: `FIREBASE_TOKEN_CACHE_TTL_SECONDS=3600`
  - User cache: cached in Redis (`backend-hormonia/app/core/redis_manager/firebase_cache.py`)
  - Circuit breaker: `backend-hormonia/app/services/firebase_auth_circuit_breaker.py`
  - Services: `backend-hormonia/app/services/firebase_auth_service.py`, `firebase_auth_shared.py`
- Frontend: Firebase JS SDK v12 (`firebase ^12.3.0`)
  - Initialized at: `frontend-hormonia/src/lib/firebase-client.ts`
  - Lazy loading: `frontend-hormonia/src/lib/firebase-lazy.ts`
  - Auth service: `frontend-hormonia/src/services/firebase-auth.ts`
  - Config env vars: `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_STORAGE_BUCKET`, `VITE_FIREBASE_MESSAGING_SENDER_ID`, `VITE_FIREBASE_APP_ID`, `VITE_FIREBASE_MEASUREMENT_ID`
- Custom Claims: `FIREBASE_ENABLE_REQUIRE_CUSTOM_CLAIMS=true`, roles: `["admin","doctor","medico"]`
- Role enforcement: `FIREBASE_ALLOWED_ROLES` and `FIREBASE_ENABLE_BLOCK_PUBLIC_DOMAINS=true`

**JWT (Internal):**
- Library: `pyjwt >=2.8.0` (replaced python-jose for CVE-2024-23342 fix)
- Algorithm: `SECURITY_ALGORITHM=HS256`
- Access token expiry: `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES=30`
- Refresh token expiry: `AUTH_REFRESH_TOKEN_EXPIRE_DAYS=7`
- Token blacklist: Redis-backed, `AUTH_ENABLE_TOKEN_BLACKLIST=true`
- Token rotation: `AUTH_ENABLE_TOKEN_ROTATION=false`

**CSRF Protection:**
- Library: `fastapi-csrf-protect >=0.3.4`
- Token endpoint: `GET /csrf-token` and `GET /api/v2/auth/csrf-token`
- Implementation: `backend-hormonia/app/middleware/csrf.py` (553-line split: `csrf_tokens.py` for token gen/validation)

## Monitoring & Observability

**Error Tracking:**
- Sentry - Backend and frontend error tracking
  - Backend: `sentry-sdk[fastapi] >=1.38.0`, initialized at `backend-hormonia/app/core/setup/sentry.py`
  - Backend config: `MONITORING_SENTRY_DSN` / `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE=0.1`
  - Integrations: FastAPI, SQLAlchemy, Redis
  - PII: `send_default_pii=False` (HIPAA compliance)
  - Frontend: `@sentry/react ^10.25.0`
  - Quiz Interface: `next.config.sentry.js` at `quiz-mensal-interface/next.config.sentry.js`
  - Config env vars: `SENTRY_DSN` (backend), `VITE_SENTRY_DSN` (frontend)

**Distributed Tracing:**
- OpenTelemetry - Distributed tracing across services
  - Backend: `opentelemetry-api/sdk >=1.28.0`, initialized at `backend-hormonia/app/core/tracing.py`
  - Exporter: OTLP HTTP-only (`opentelemetry-exporter-otlp-proto-http`) — Jaeger removed (no Python 3.13 support)
  - Instrumentation: FastAPI, SQLAlchemy, Redis, httpx
  - OTLP endpoint: configurable via standard `OTEL_EXPORTER_OTLP_ENDPOINT` env var
  - Graceful degradation: mock tracer used when OpenTelemetry not installed

**Metrics:**
- Prometheus - Application and Celery metrics
  - Library: `prometheus-client >=0.24.1`
  - Exposed at: `backend-hormonia/app/api/v2/routers/system/metrics.py`
  - Flower: Celery task monitoring UI (port 5555 by default)

**Logging:**
- Libraries: `python-json-logger >=2.0.7`, `structlog >=24.1.0`
- Level: `LOGGING_LEVEL=INFO`
- Rate limiting: `LOGGING_MAX_LOGS_PER_SECOND=100` (Railway limit: 500/sec)
- Log deduplication window: `LOGGING_DEDUPLICATION_WINDOW_SECONDS=300`

## CI/CD & Deployment

**Hosting:**
- Backend API: Railway (`RAILWAY_TOKEN` secret, `railway up --detach`)
- Celery Worker + Beat: Railway (separate services)
- Frontend SPA: Railway (Nginx container) or Firebase Hosting (`frontend-hormonia/firebase.json`)
- Quiz Interface: Firebase Hosting with Next.js Frameworks Backend (Firebase project `clinica-quiz`, region `us-central1`) or Railway
- Database: AWS RDS PostgreSQL (external, accessed via `DATABASE_URL`)
- Cache: Dragonfly via Google Cloud Memorystore (Redis-compatible)

**CI Pipeline:**
- GitHub Actions (`.github/workflows/` - 22 workflow files)
- Key workflows:
  - `railway-deploy.yml` - Deploy to Railway on push to `main`/`production`
  - `ci-pipeline.yml`, `ci.yml` - Build and test pipeline
  - `security-scan.yml`, `security.yml` - Security scans
  - `e2e-tests.yml` - Playwright E2E tests
  - `frontend-monthly-quiz-tests.yml` - Quiz interface tests
  - `code-quality.yml` - Linting and type checking
  - `dependency-updates.yml` - Automated dependency updates
  - `load-test.yml` - Load tests (locust at `backend-hormonia/locust/`)

## Webhooks & Callbacks

**Incoming Webhooks:**
- WhatsApp (Evolution API): `POST /webhooks/whatsapp/evolution/{instance_name}`
  - Handler: `backend-hormonia/app/integrations/whatsapp/webhook_handler.py`
  - Security: HMAC-SHA256 (`WHATSAPP_WEBHOOK_HMAC_ENABLED=true`), optional IP whitelist, optional timestamp validation
  - Registered in router at `backend-hormonia/app/api/v2/routers/webhooks.py` and whatsapp integration routes

**Outgoing Webhooks / Callbacks:**
- Evolution API webhook registration: `WHATSAPP_EVOLUTION_WEBHOOK_URL` - registers backend URL with Evolution API on startup
- Slack webhook: `SLACK_WEBHOOK_URL` for alert notifications
- LangChain tracing: optional `AI_LANGCHAIN_API_KEY` for LangSmith tracing callbacks

## Environment Configuration

**Required env vars (production):**
- `DATABASE_URL` - PostgreSQL connection string (`postgresql+psycopg://...?sslmode=require`)
- `REDIS_URL` - Dragonfly/Redis URL
- `CELERY_BROKER_URL` - Redis broker URL
- `CELERY_RESULT_BACKEND` - Redis result URL
- `SECURITY_SECRET_KEY` - JWT signing key (64-char random)
- `FIREBASE_ADMIN_PROJECT_ID`, `FIREBASE_ADMIN_CLIENT_EMAIL`, `FIREBASE_ADMIN_PRIVATE_KEY` - Firebase Admin
- `WHATSAPP_EVOLUTION_API_KEY`, `WHATSAPP_EVOLUTION_API_URL` - WhatsApp integration
- `WHATSAPP_EVOLUTION_WEBHOOK_SECRET` - Webhook HMAC secret
- `AI_GEMINI_API_KEY` - Google Gemini API key
- `MONITORING_SENTRY_DSN` - Sentry DSN
- `CORS_FRONTEND_URL` - Admin frontend URL (default: `https://clinica-oncologica-hosting.web.app`)
- `CORS_QUIZ_URL` - Quiz URL (default: `https://clinica-quiz.web.app`)

**Frontend required:**
- `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`
- `VITE_API_BASE_URL` or `VITE_API_URL`
- `VITE_WS_BASE_URL` (optional, for real-time features)

**Secrets location:**
- Local: `.env` files per service (`backend-hormonia/.env`, root `.env`)
- CI: GitHub repository secrets (e.g., `RAILWAY_TOKEN`, `VITE_SUPABASE_URL`)
- Firebase Admin: service account key at `clinica-oncologica-hosting-firebase-adminsdk-fbsvc-0c279a6456.json` (root) — should be moved to env vars

---

*Integration audit: 2026-02-22*
