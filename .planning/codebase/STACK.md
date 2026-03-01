# Technology Stack

**Analysis Date:** 2026-02-22

## Languages

**Primary:**
- Python 3.13 - Backend API, Celery workers, Celery Beat
- TypeScript 5.9 - Frontend (React SPA) and quiz interface (Next.js)

**Secondary:**
- JavaScript (ESM) - Root-level scripts, quiz interface config
- SQL - Alembic migrations in `backend-hormonia/alembic/` and `backend-hormonia/migrations/`
- HTML/CSS - Static templates at `backend-hormonia/app/templates/`, frontend assets

## Runtime

**Backend:**
- Python 3.13 (pinned in `backend-hormonia/.python-version`)
- Uvicorn ASGI server (production: 1 worker on Cloud Run, dev: reload enabled)

**Frontend (Admin SPA):**
- Node.js >=18.0.0 (engines field in `frontend-hormonia/package.json`)
- npm >=9.0.0, npm@10.9.0 declared as packageManager

**Quiz Interface:**
- Node.js >=18 (Next.js 14 SSR application at `quiz-mensal-interface/`)
- npm

## Package Managers

**Backend:**
- pip, lockfile: `backend-hormonia/requirements.txt` (pinned version ranges)
- pyproject.toml at `backend-hormonia/pyproject.toml` (tooling config only, not build system)

**Frontend:**
- npm@10.9.0, lockfile: `frontend-hormonia/package-lock.json`
- npm, lockfile: `quiz-mensal-interface/package-lock.json`

## Frameworks

**Backend Core:**
- FastAPI >=0.128.0 - REST API framework (`backend-hormonia/app/main.py`)
- Uvicorn[standard] >=0.39.0 - ASGI server
- Pydantic v2 >=2.12.5 - Data validation and settings management
- pydantic-settings >=2.12.0 - Configuration management via env vars
- SQLAlchemy >=2.0.45 - ORM (sync Session throughout; async pending migration)
- Alembic >=1.14.1 - Database migrations at `backend-hormonia/alembic/`

**Background Tasks:**
- Celery >=5.6.2 - Task queue (38+ periodic tasks in `backend-hormonia/app/celery_app.py`)
- Celery Beat - Scheduler for periodic tasks
- Flower 2.0.1 - Web-based Celery monitoring UI

**AI / ML:**
- LangChain Core >=1.2.7 - LLM abstraction layer
- langchain-google-genai >=2.1.12 - Google Gemini integration
- LangGraph >=1.0.7 - Stateful AI agent orchestration (`backend-hormonia/app/ai/langgraph/`)
- google-ai-generativelanguage >=0.7.0 - Gemini API dependency

**Frontend (Admin SPA):**
- React 19 - UI library (`frontend-hormonia/src/App.tsx`)
- React Router DOM 6.28 - Client-side routing
- Vite 6 - Build tool (`frontend-hormonia/vite.config.ts`)
- TailwindCSS 4.x - Utility-first CSS
- shadcn/ui (Radix UI primitives) - Component library (full set of @radix-ui/react-* packages)
- TanStack Query v5 - Server state management
- React Hook Form 7 + Zod 3 - Form validation
- Recharts 2 - Data visualization
- Firebase JS SDK v12 - Authentication client

**Quiz Interface:**
- Next.js 14.2 - SSR framework (`quiz-mensal-interface/next.config.mjs`)
- React 18 - UI library
- TailwindCSS 4 - Styling
- shadcn/ui (Radix UI primitives) - Components (same set as frontend)
- React Hook Form 7 + Zod - Form validation
- Recharts - Charts

## Testing

**Backend:**
- pytest >=8.1.0 with pytest-asyncio >=0.23.0 (asyncio_mode=auto)
- pytest-cov >=5.0.0 - Coverage reporting
- pytest-mock >=3.14.0 - Mocking
- fakeredis >=2.20.0 - In-memory Redis for tests
- Playwright >=1.40.0 + pytest-playwright - E2E tests
- Faker >=21.0.0 - Test data generation
- pytest-xdist >=3.5.0 - Parallel test execution

**Frontend (Admin SPA):**
- Vitest 3.x - Test runner (`frontend-hormonia/vite.config.ts` test section)
- @testing-library/react 16 - Component testing
- Playwright 1.49 - E2E tests
- jsdom - Browser environment
- jest-axe - Accessibility testing

**Quiz Interface:**
- Jest 29 + ts-jest - Test runner (`quiz-mensal-interface/package.json` jest config)
- @testing-library/react 14 - Component testing
- jest-environment-jsdom - Browser environment
- msw 1 - API mocking

## Build / Dev Tools

**Backend:**
- Black (line-length=120, py313 target) - Formatter
- isort (black profile) - Import sorting
- ruff (F rules only) - Linter
- bandit - Security scanning
- radon - Complexity metrics
- mypy - Type checking (used in CI but non-blocking with `|| true`)

**Frontend:**
- ESLint 9 with typescript-eslint 8 - Linting
- Prettier (implied by husky + lint-staged setup)
- TypeScript 5.9 - Type checking
- LightningCSS - CSS minification in Vite build
- husky 9 + lint-staged 16 - Pre-commit hooks

## Key Dependencies

**Critical (Backend):**
- psycopg[binary] >=3.2.13 - PostgreSQL driver (psycopg3 for Python 3.13)
- asyncpg >=0.30.0 - Async PostgreSQL driver for background tasks
- redis >=6.4.0 - Redis client (supports Dragonfly, uses ssl_context)
- firebase-admin >=6.9.0 - Firebase Admin SDK for auth token verification
- pyjwt >=2.8.0 - JWT (replaces python-jose, CVE-2024-23342 fix)
- passlib[bcrypt] + argon2-cffi - Password hashing
- cryptography >=43.0.0 - Fernet field encryption, AES-GCM for PHI
- sentry-sdk[fastapi] >=1.38.0 - Error tracking
- tenacity >=8.2.3 - Retry with exponential backoff
- aiobreaker >=1.2.0 - Async circuit breaker

**Critical (Frontend):**
- firebase ^12.3.0 - Auth client (email/password + custom token)
- axios ^1.7.9 - HTTP client
- @sentry/react ^10.25.0 - Error tracking
- @tanstack/react-query ^5.62.0 - Server state management

**Infrastructure (Backend):**
- OpenTelemetry stack (>=1.28.0) - Distributed tracing with OTLP HTTP exporter
- prometheus-client >=0.24.1 - Metrics for Celery
- python-json-logger, structlog - Structured logging
- reportlab >=4.4.7 - PDF report generation
- Jinja2 >=3.1.2 - Template rendering for notifications
- httpx >=0.28.1 - Async HTTP client (Evolution API calls)

## Configuration

**Environment:**
- Backend: `.env` file loaded via `python-dotenv` only in non-production/non-pytest mode
- Config class: `app/config/settings/` (modular pydantic-settings) with base/database/security/integrations/features/monitoring modules
- Env var naming: `{CATEGORY}_{SUBCATEGORY}_{ATTRIBUTE}_{UNIT}` pattern
- List fields preprocessed before pydantic validation (see `_preprocess_list_env_vars` in `app/config/settings/__init__.py`)

**Build:**
- Backend: Dockerfile at `backend-hormonia/Dockerfile` (python:3.13-slim)
- Celery Worker: `backend-hormonia/Dockerfile.worker`
- Celery Beat: `backend-hormonia/Dockerfile.beat`
- Frontend SPA: `frontend-hormonia/Dockerfile`, served via Nginx
- Quiz Interface: `quiz-mensal-interface/Dockerfile`, Next.js standalone output
- Local dev: `backend-hormonia/docker-compose.yml` (API + Worker + Beat + Dragonfly)

## Platform Requirements

**Development:**
- Python 3.13 (`.python-version`)
- Node.js >=18
- Docker (for Dragonfly locally via `docker-compose.yml`)
- PostgreSQL (AWS RDS in production, local connection via `DATABASE_URL`)

**Production:**
- Backend API: Railway (Cloud Run-compatible uvicorn, port 8080)
- Celery Worker + Beat: Railway
- Frontend SPA: Railway or Firebase Hosting (`frontend-hormonia/firebase.json`)
- Quiz Interface: Firebase Hosting with Next.js Frameworks Backend (`quiz-mensal-interface/firebase.json`, region: us-central1), also Railway-compatible
- Database: AWS RDS PostgreSQL with SSL (`sslmode=require`)
- Cache/Broker: Dragonfly (Redis-compatible, Cloud Memorystore or self-hosted)

---

*Stack analysis: 2026-02-22*
