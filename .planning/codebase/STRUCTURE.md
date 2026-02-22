# Codebase Structure

**Analysis Date:** 2026-02-22

## Directory Layout

```
clinica-oncologica-v02-1/        # Monorepo root
├── backend-hormonia/            # Python/FastAPI backend
├── frontend-hormonia/           # React/TypeScript SPA (clinic staff)
├── quiz-mensal-interface/       # Next.js app (patient-facing monthly quiz)
├── docs/                        # Project documentation, stories, PRDs
├── scripts/                     # Utility scripts
├── .claude/                     # AIOS agent system configuration
├── .planning/                   # GSD planning documents
├── .env                         # Environment variables (never commit)
├── .env.example                 # Template for env vars
└── package.json                 # Root workspace (minimal)
```

## Backend Structure (`backend-hormonia/`)

```
backend-hormonia/
├── main.py                      # ASGI entry point (uvicorn targets 'app')
├── app/
│   ├── api/                     # HTTP layer
│   │   └── v2/                  # Current API version
│   │       ├── __init__.py      # Exports api_v2_router
│   │       └── routers/         # Domain-grouped endpoint modules
│   │           ├── auth.py
│   │           ├── patients/
│   │           ├── physicians/
│   │           ├── flows.py
│   │           ├── analytics/
│   │           ├── admin/
│   │           ├── ai/
│   │           ├── tasks/
│   │           ├── health/
│   │           ├── monthly_quiz_operations/
│   │           └── ...
│   ├── core/                    # Application infrastructure
│   │   ├── application_factory.py
│   │   ├── lifespan.py
│   │   ├── middleware_setup.py
│   │   ├── router_registry.py
│   │   ├── redis_manager/       # Canonical Redis singleton
│   │   ├── setup/               # Sentry, OpenAPI configuration
│   │   └── ...
│   ├── domain/                  # Business logic
│   │   ├── quizzes/             # Quiz session, delivery, evaluation, security
│   │   ├── messaging/           # Message service, scheduling, WhatsApp
│   │   ├── patient/             # Patient onboarding domain
│   │   ├── analytics/           # Analytics domain logic
│   │   └── agents/              # Agent-based quiz logic (LangGraph)
│   ├── services/                # Cross-cutting services
│   │   ├── flow/                # Patient flow engine (QW-021 system)
│   │   ├── alerts/              # Alert evaluation, monitoring, notification
│   │   ├── audit/               # HIPAA audit logging
│   │   ├── encryption/          # PII field encryption
│   │   ├── lgpd/                # LGPD consent management
│   │   ├── follow_up_system/    # Scheduled follow-up orchestration
│   │   ├── websocket/           # WebSocket connection manager
│   │   ├── webhook/             # Incoming webhook handling and DLQ
│   │   ├── dlq/                 # Dead letter queue
│   │   ├── unified_whatsapp_service.py  # Canonical WhatsApp facade
│   │   ├── template_loader_pkg/ # Flow/quiz template loading
│   │   ├── automated_recovery_pkg/
│   │   ├── critical_error_escalation_pkg/
│   │   └── ...
│   ├── orchestration/           # Long-running transactions
│   │   └── saga_orchestrator/   # Patient onboarding saga
│   │       ├── orchestrator.py
│   │       ├── steps.py
│   │       ├── compensation.py
│   │       ├── persistence.py
│   │       └── types.py
│   ├── ai/                      # AI/ML pipelines
│   │   ├── langgraph/           # LangGraph graph definitions
│   │   │   ├── graphs.py
│   │   │   ├── nodes.py
│   │   │   ├── nodes_ai.py
│   │   │   ├── state.py
│   │   │   └── runtime.py
│   │   └── pii_redaction.py     # PII/PHI removal before AI calls
│   ├── integrations/            # External service clients
│   │   ├── evolution/           # Evolution API (WhatsApp)
│   │   ├── whatsapp/            # WhatsApp integration models, queue
│   │   ├── gemini_orchestrator.py  # Google Gemini AI
│   │   └── pdf_generator.py
│   ├── agents/                  # AI agent implementations
│   │   ├── patient/             # Patient flow coordinator agent
│   │   ├── analytics/
│   │   └── communication/       # Message composer agent
│   ├── models/                  # SQLAlchemy ORM models
│   ├── schemas/                 # Pydantic request/response schemas
│   │   ├── v2/                  # V2 API schemas
│   │   └── validators/          # Field validators (phone.py canonical)
│   ├── repositories/            # Data access layer
│   ├── dependencies/            # FastAPI dependency injection
│   ├── middleware/              # ASGI middleware implementations
│   ├── resilience/              # Circuit breaker, retry, health, rate limit
│   ├── tasks/                   # Celery task definitions
│   │   ├── quiz_flow/           # Quiz-specific tasks
│   │   └── flows/               # Flow automation tasks
│   ├── jobs/                    # Scheduler stub (no-op, kept for compat)
│   ├── config/                  # Settings modules
│   │   └── settings/            # Split settings: base, database, security, features, etc.
│   ├── infrastructure/          # Infrastructure abstractions
│   │   └── cache/               # Canonical cache layer
│   ├── memory/                  # Agent memory management
│   ├── monitoring/              # Prometheus exporters, monitoring manager
│   ├── metrics/                 # Metrics collection
│   ├── templates/               # Jinja/static templates
│   │   ├── flows/               # Flow message templates
│   │   ├── quiz/
│   │   └── whatsapp/
│   ├── locales/                 # i18n strings (en, es, pt-BR)
│   ├── utils/                   # Shared utilities
│   └── workers/                 # Celery worker bootstrap
├── alembic/                     # Database migrations
│   └── versions/                # Migration scripts (000-009+)
├── tests/                       # Pytest test suite
├── migrations/                  # Alembic config
├── beat/                        # Celery beat launcher
├── worker/                      # Celery worker launcher
├── scripts/                     # DB seeds, maintenance scripts
├── monitoring/                  # Monitoring config (Prometheus, Grafana)
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── requirements.txt
```

## Frontend Structure (`frontend-hormonia/`)

```
frontend-hormonia/
├── src/
│   ├── app/
│   │   ├── routes/              # React Router route definitions
│   │   │   ├── routeDefinitions.tsx
│   │   │   ├── AdminRoutes.tsx
│   │   │   └── MedicoRoutes.tsx
│   │   ├── providers/           # Context providers
│   │   │   ├── AuthContext.tsx
│   │   │   ├── MedicoAuthContext.tsx
│   │   │   └── OptimizedQueryProvider.tsx
│   │   └── styles/
│   ├── features/                # Domain feature modules
│   │   ├── patients/            # Patient management
│   │   ├── dashboard/           # Physician dashboard
│   │   ├── flows/               # Flow management
│   │   ├── flow-designer/       # Visual flow designer
│   │   ├── auth/                # Authentication UI
│   │   ├── admin/               # Admin panel
│   │   ├── analytics/           # Analytics views
│   │   ├── alerts/              # Alert management
│   │   ├── messages/            # Message history
│   │   ├── monthly-quiz/        # Monthly quiz admin
│   │   ├── metrics/             # Metrics visualizations
│   │   ├── templates/           # Flow and quiz templates
│   │   ├── whatsapp/            # WhatsApp integration UI
│   │   ├── ai/                  # AI feature components
│   │   └── monitoring/          # System monitoring views
│   ├── components/              # Shared UI components
│   │   ├── ui/                  # Base UI primitives
│   │   ├── layout/              # Navigation, layout shells
│   │   ├── charts/              # Chart components
│   │   ├── auth/                # Auth-specific components
│   │   └── common/              # Shared generic components
│   ├── hooks/                   # Shared React hooks
│   │   ├── api/                 # API data-fetching hooks
│   │   ├── admin/               # Admin-specific hooks
│   │   ├── usePatients.ts
│   │   ├── useFlows.ts
│   │   ├── useWebSocket.ts
│   │   └── ...
│   ├── contexts/                # Additional React contexts
│   └── config/                  # Frontend configuration
├── lib/                         # Shared library code (used by quiz too)
│   ├── api-client.ts            # Quiz API client (direct to backend)
│   ├── api.ts
│   ├── flow-engine/
│   └── types/
├── shared-types/                # TypeScript types shared across apps
│   └── src/
├── public/                      # Static assets
└── dist/                        # Build output (Firebase Hosting)
```

## Quiz Interface Structure (`quiz-mensal-interface/`)

```
quiz-mensal-interface/
├── app/                         # Next.js 14 App Router
│   ├── layout.tsx               # Root layout
│   ├── page.tsx                 # Home/entry
│   ├── api/                     # Next.js API routes (proxy layer)
│   └── quiz/                    # Quiz pages
│       └── monthly/
│           └── page.tsx
├── components/                  # Quiz UI components
│   ├── quiz/                    # Quiz question, answer components
│   │   └── quiz-interface.tsx
│   ├── ui/                      # Base primitives
│   └── error/
├── hooks/                       # Quiz-specific hooks
├── lib/                         # Utilities
├── styles/                      # Global CSS
├── types/                       # TypeScript types
└── tests/                       # Jest/RTL tests
```

## Key File Locations

**Entry Points:**
- `backend-hormonia/main.py`: ASGI application (uvicorn entry)
- `backend-hormonia/app/core/application_factory.py`: App factory with all wiring
- `backend-hormonia/app/core/lifespan.py`: Startup/shutdown lifecycle
- `frontend-hormonia/src/app/routes/routeDefinitions.tsx`: All frontend routes
- `quiz-mensal-interface/app/layout.tsx`: Quiz app root

**Configuration:**
- `backend-hormonia/app/config/__init__.py`: Settings singleton export
- `backend-hormonia/app/config/settings/`: Split settings by concern (base, database, security, features, integrations, monitoring, tasks, webhooks, performance, cache)
- `backend-hormonia/app/celery_app.py`: Celery + beat_schedule (38 jobs)
- `backend-hormonia/app/task_queue.py`: Simplified Celery-only queue

**Canonical Modules (Always Use These):**
- `backend-hormonia/app/core/redis_manager/manager.py`: ALL Redis clients
- `backend-hormonia/app/services/unified_whatsapp_service.py`: All WhatsApp messaging
- `backend-hormonia/app/infrastructure/cache/`: Cache layer
- `backend-hormonia/app/schemas/validators/phone.py`: Phone normalization
- `backend-hormonia/app/services/audit/audit_service.py`: HIPAA audit logging
- `backend-hormonia/app/services/dlq/`: Dead letter queue (shared config in `base.py`)
- `backend-hormonia/app/services/flow/types.py`: `FlowType` enum
- `backend-hormonia/app/services/alerts/utils.py`: `apply_alert_filters()`
- `backend-hormonia/app/services/websocket/connection_manager.py`: WebSocket manager

**Database:**
- `backend-hormonia/alembic/versions/`: Migration scripts (numbered 000-009+)
- `backend-hormonia/alembic/env.py`: Migration environment
- `backend-hormonia/app/models/`: SQLAlchemy ORM models
- `backend-hormonia/app/core/database_config.py`: Pool sizing and DB config

**Testing:**
- `backend-hormonia/tests/`: Pytest test suite
- `quiz-mensal-interface/tests/`: Jest test suite

## Naming Conventions

**Backend Files:**
- Modules: `snake_case.py` (e.g., `flow_service.py`, `patient_repository.py`)
- Packages with split responsibilities: `_pkg` suffix (e.g., `template_loader_pkg/`, `automated_recovery_pkg/`)
- Dead code (tombstoned): file kept with docstring + `raise ImportError`
- Shim files: thin re-exports with `from canonical import X  # noqa: F401`

**Backend Symbols:**
- Classes: `PascalCase` (e.g., `SagaOrchestrator`, `RedisManager`)
- Functions: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Pydantic models: `PascalCase` with `Request`/`Response`/`Create`/`Update` suffixes

**Frontend Files:**
- Components: `PascalCase.tsx` (e.g., `PatientCard.tsx`)
- Hooks: `camelCase.ts` prefixed with `use` (e.g., `usePatients.ts`)
- Feature barrel exports: `index.ts`
- Lazy-loaded routes: `.lazy.tsx` suffix (e.g., `AdminRoutes.lazy.tsx`)

**Frontend Directories:**
- Feature modules: `kebab-case` (e.g., `flow-designer/`, `monthly-quiz/`)
- Shared hooks: `hooks/` inside feature or at `src/hooks/`

## Where to Add New Code

**New API Endpoint:**
- Primary code: `backend-hormonia/app/api/v2/routers/{domain}/`
- Router registration: `backend-hormonia/app/core/router_registry.py` (add to `api_v2_router`)
- Schemas: `backend-hormonia/app/schemas/v2/`
- Tests: `backend-hormonia/tests/api/`

**New Domain Service:**
- Implementation: `backend-hormonia/app/services/{domain_name}/`
- If complex (>1 class or 500+ lines expected): use package `{name}_pkg/` pattern
- Domain logic: `backend-hormonia/app/domain/{domain}/`

**New Celery Task:**
- Task file: `backend-hormonia/app/tasks/{task_group}.py`
- Register in `celery_app.py` `include` list
- Schedule (if periodic): add to `beat_schedule` in `celery_app.py`

**New SQLAlchemy Model:**
- Model file: `backend-hormonia/app/models/{entity}.py`
- Alembic migration: `backend-hormonia/alembic/versions/{NNN}_{description}.py`
- Repository: `backend-hormonia/app/repositories/{entity}.py`

**New Frontend Feature:**
- Feature directory: `frontend-hormonia/src/features/{feature-name}/`
- Inside: `index.ts` barrel, `components/`, `hooks/`, `types/` as needed
- Register route in `frontend-hormonia/src/app/routes/routeDefinitions.tsx`

**New Shared UI Component:**
- Place in: `frontend-hormonia/src/components/ui/` (primitives) or `src/components/common/` (complex)

**Shared Utilities:**
- Backend: `backend-hormonia/app/utils/`
- Frontend: `frontend-hormonia/src/` (no dedicated utils dir; place in relevant feature or `lib/`)

## Special Directories

**`backend-hormonia/app/orchestration/.archive/`:**
- Purpose: Archived/tombstoned orchestration files
- Generated: No
- Committed: Yes (tombstones must remain for import error clarity)

**`backend-hormonia/.venv/`:**
- Purpose: Python virtual environment
- Generated: Yes (via `python -m venv .venv`)
- Committed: No

**`frontend-hormonia/dist/`:**
- Purpose: Vite production build output (deployed to Firebase Hosting)
- Generated: Yes
- Committed: No (deployed by CI)

**`backend-hormonia/htmlcov/`:**
- Purpose: pytest coverage HTML report
- Generated: Yes
- Committed: No

**`docs/stories/`:**
- Purpose: AIOS development story files (numbered per epic)
- Generated: By `@sm` agent
- Committed: Yes

**`backend-hormonia/app/templates/`:**
- Purpose: Jinja2/JSON message templates for WhatsApp flows and quizzes
- Generated: No (manually authored)
- Committed: Yes

---

*Structure analysis: 2026-02-22*
