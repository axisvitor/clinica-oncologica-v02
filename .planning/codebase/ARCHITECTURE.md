# Architecture

**Analysis Date:** 2026-02-22

## Pattern Overview

**Overall:** Multi-application monorepo with layered backend (Domain-Driven Design) and feature-sliced frontend

**Key Characteristics:**
- Three separate application surfaces sharing one backend: clinic management frontend (`frontend-hormonia`), monthly quiz interface (`quiz-mensal-interface`), and backend API (`backend-hormonia`)
- Backend follows DDD with clear separation: API → Domain → Infrastructure layers
- Async task processing via Celery with Dragonfly (Redis-compatible) as broker; Cloud Tasks/Scheduler fully removed
- Dual patient flow systems coexist: production `flow_core/flow_service` (SQLAlchemy, day-based) and newer `services/flow/core/manager.py` (Pydantic, step-based)
- Saga orchestration pattern for distributed patient onboarding transactions

## Layers

**API Layer:**
- Purpose: HTTP request handling, input validation, response serialization
- Location: `backend-hormonia/app/api/v2/routers/`
- Contains: FastAPI routers grouped by domain (patients, physicians, auth, flows, analytics, admin, ai, tasks, etc.)
- Depends on: Domain layer, schemas, dependencies
- Used by: Frontend clients, webhook handlers

**Domain Layer:**
- Purpose: Core business logic isolated from HTTP and infrastructure concerns
- Location: `backend-hormonia/app/domain/`
- Contains: `quizzes/`, `messaging/`, `patient/`, `analytics/`, `agents/`, `errors/`
- Depends on: Models, repositories, schemas
- Used by: API layer, background tasks

**Services Layer:**
- Purpose: Cross-cutting orchestration and specialized business services
- Location: `backend-hormonia/app/services/`
- Contains: `flow/`, `alerts/`, `audit/`, `analytics/`, `webhook/`, `websocket/`, `encryption/`, `lgpd/`, `follow_up_system/`, etc.
- Depends on: Domain, repositories, core infrastructure
- Used by: API layer, background tasks, domain layer

**Orchestration Layer:**
- Purpose: Long-running multi-step transactional workflows
- Location: `backend-hormonia/app/orchestration/`
- Contains: `saga_orchestrator/` (orchestrator, steps, compensation, persistence, types)
- Depends on: Services, repositories, Redis distributed locks
- Used by: API patient creation endpoints, background retry tasks

**AI Layer:**
- Purpose: LangGraph-based AI pipelines for quiz question humanization, sentiment analysis, empathetic follow-ups
- Location: `backend-hormonia/app/ai/langgraph/`
- Contains: `graphs.py`, `nodes.py`, `nodes_ai.py`, `state.py`, `ai_state.py`, `runtime.py`, `prompts.py`, `consensus.py`
- Depends on: Google Gemini via `app/integrations/gemini_orchestrator.py`
- Used by: Quiz flow services, message services

**Infrastructure/Core Layer:**
- Purpose: Database, Redis, auth, session management, monitoring, configuration
- Location: `backend-hormonia/app/core/`
- Contains: `application_factory.py`, `lifespan.py`, `middleware_setup.py`, `router_registry.py`, `redis_manager/`, `session_manager.py`, `database_config.py`, `cors.py`, `exceptions.py`, `security.py`, etc.
- Depends on: Nothing application-specific
- Used by: All other layers

**Tasks Layer:**
- Purpose: Celery background task definitions and beat schedule
- Location: `backend-hormonia/app/tasks/`
- Contains: `messaging.py`, `flows.py`, `flow_automation.py`, `reports.py`, `alerts.py`, `quiz_link_tasks.py`, `quiz_flow/`, `saga_retry.py`, `saga_monitoring.py`, `follow_up.py`, `webhook_dlq.py`, `monitoring.py`, `audit_cleanup.py`, `lgpd_tasks.py`
- Depends on: Services, domain, core
- Used by: Celery worker processes

**Repositories Layer:**
- Purpose: Data access abstraction over SQLAlchemy models
- Location: `backend-hormonia/app/repositories/`
- Contains: `base.py`, `base_v2.py`, `patient/`, `flow.py`, `quiz.py`, `message.py`, `alert.py`, `session.py`, `user.py`, etc.
- Depends on: Models, database session
- Used by: Services, domain, orchestration

**Models Layer:**
- Purpose: SQLAlchemy ORM models and Pydantic schemas
- Location: `backend-hormonia/app/models/` (ORM) and `backend-hormonia/app/schemas/` (Pydantic)
- Contains: `patient.py`, `doctor.py`, `flow.py`, `quiz.py`, `message.py`, `audit_log.py`, `patient_onboarding_saga.py`, `enums.py`, etc.
- Depends on: Nothing application-specific
- Used by: Repositories, domain, services

## Data Flow

**Patient Creation (Saga Pattern):**

1. HTTP POST to `/api/v2/patients` router
2. Router validates input via Pydantic schema (`app/schemas/patient.py`)
3. `SagaOrchestrator.start_saga()` acquires distributed Redis lock (`app/core/distributed_lock.py`)
4. Steps execute sequentially: validate → create DB record → initialize WhatsApp → schedule flow → setup quiz
5. On failure, `SagaCompensator` rolls back completed steps in reverse order
6. Saga state persisted in `patient_onboarding_saga` table via `SagaPersistence`
7. Retry tasks scheduled via Celery (`app/tasks/saga_retry.py`)

**WhatsApp Message Delivery Flow:**

1. Celery task in `app/tasks/messaging.py` dequeues work from Dragonfly broker
2. `UnifiedWhatsAppService` (`app/services/unified_whatsapp_service.py`) resolves template and recipient
3. Evolution API client (`app/integrations/evolution/`) makes HTTP call to Evolution API
4. Webhook from Evolution triggers `/webhook` endpoint
5. `app/services/webhook/handlers/` processes incoming messages, updates flow state
6. Flow engine (`flow_core.py` or `services/flow/core/manager.py`) advances patient flow day

**Quiz Delivery Flow:**

1. Celery beat job triggers `quiz_link_tasks.py` on schedule
2. Quiz session created in DB, short link generated with `short_code` in metadata
3. WhatsApp message sent with link to `{BASE_URL}/q/{code}`
4. Patient accesses `quiz-mensal-interface` (Next.js) via short link
5. Short link resolver (`/q/{code}` in router_registry) validates and redirects with JWT token
6. Quiz interface calls `quiz-mensal-interface/app/api/` route handlers → Python backend
7. Responses stored and flow integration updates patient engagement data

**Real-time Dashboard Updates:**

1. Backend events published to Redis Pub/Sub channel
2. `RedisPubSubManager` (`app/services/redis_pubsub_manager.py`) distributes to all FastAPI instances
3. WebSocket manager (`app/services/websocket/connection_manager.py`) pushes to connected clients
4. Frontend `useWebSocket` hook receives events and invalidates React Query cache

**State Management (Frontend):**
- React Query (`@tanstack/react-query`) for server state caching and synchronization
- React Context for auth state (`AuthContext.tsx`, `MedicoAuthContext.tsx`)
- Feature-local state via React hooks; no global store (Redux/Zustand not used)

## Key Abstractions

**SagaOrchestrator:**
- Purpose: Manages distributed patient onboarding transaction with compensation
- Examples: `app/orchestration/saga_orchestrator/orchestrator.py`, `steps.py`, `compensation.py`
- Pattern: Saga pattern with idempotency keys and Redis distributed locks

**FlowEngine (Dual):**
- Purpose: Manages patient treatment communication flow progression
- Examples: `app/services/flow_core.py`, `app/services/flow/core/manager.py`
- Pattern: State machine; production uses `PatientFlowState` (SQLAlchemy, day-based); QW-021 uses Pydantic `FlowContext` (step-based)

**RedisManager:**
- Purpose: Singleton Redis client with SSL, connection pooling, circuit breaker across 4 databases
- Examples: `app/core/redis_manager/manager.py`
- Pattern: Singleton with lazy initialization; DB 0=broker, 1=cache, 2=sessions, 3=ratelimit

**UnifiedWhatsAppService:**
- Purpose: Canonical WhatsApp messaging abstraction over Evolution API
- Examples: `app/services/unified_whatsapp_service.py`
- Pattern: Facade; all other code uses this, not Evolution directly

**LangGraph Graphs:**
- Purpose: Multi-node AI pipelines for message humanization and sentiment
- Examples: `app/ai/langgraph/graphs.py` (`build_flow_message_graph`, `build_humanization_graph`)
- Pattern: Directed acyclic graph with typed state; compiled and cached with `@lru_cache`

**Repository Pattern:**
- Purpose: Data access abstraction; separates query logic from services
- Examples: `app/repositories/base.py`, `app/repositories/patient/`, `app/repositories/flow.py`
- Pattern: Generic base with CRUD; specialized repositories inherit and extend

**DLQ (Dead Letter Queue):**
- Purpose: Capture and retry failed webhook/message deliveries
- Examples: `app/services/dlq/` with shared config in `base.py`
- Pattern: Redis-backed queue with configurable retry and escalation

## Entry Points

**FastAPI Application:**
- Location: `backend-hormonia/main.py`
- Triggers: uvicorn on `PORT` env var (default 8000); Railway/Railpack auto-detects
- Responsibilities: Creates app via `create_application()` factory in `app/core/application_factory.py`

**Celery Worker:**
- Location: `backend-hormonia/worker/` and `backend-hormonia/app/celery_app.py`
- Triggers: `celery worker` command; deployed on Railway
- Responsibilities: Processes 16 task modules including messaging, flows, quiz, saga, monitoring

**Celery Beat Scheduler:**
- Location: `backend-hormonia/beat/` and beat_schedule in `app/celery_app.py`
- Triggers: `celery beat` command; 38 periodic tasks defined
- Responsibilities: Time-based job triggering for flows, quizzes, alerts, reports, LGPD, audits

**Frontend SPA:**
- Location: `frontend-hormonia/src/app/routes/index.ts`
- Triggers: Browser navigation; Vite-built SPA deployed to Firebase Hosting
- Responsibilities: Role-based routing (`AdminRoutes.tsx`, `MedicoRoutes.tsx`)

**Quiz Next.js App:**
- Location: `quiz-mensal-interface/app/layout.tsx`
- Triggers: Patient accesses quiz link; deployed to Firebase Hosting (separate config)
- Responsibilities: Renders quiz interface; calls backend via dedicated `lib/api-client.ts`

## Error Handling

**Strategy:** Hierarchical exception system with domain-specific exceptions, global handler, and per-request correlation IDs

**Patterns:**
- Root exception `HormoniaException` → `APIException` (HTTP exceptions) → domain-specific (`NotFoundError`, `ValidationError`, `BusinessRuleError`, `UnauthorizedError`, etc.) in `app/core/exceptions.py`
- Global handler in `create_application()` returns `{"error": "...", "request_id": "...", "timestamp": "..."}` with 500 status
- `APIException` handler returns structured JSON with `error_code`, `message`, `details`, `request_id`
- Domain exception handlers registered via `register_exception_handlers(app)` in `app/core/exception_handlers.py`
- Saga compensation on failure rolls back completed steps; failures trigger Celery retry tasks

## Cross-Cutting Concerns

**Logging:**
- Structured JSON logging via `app/utils/structured_logger.py`; log level from `APP_ENABLE_DEBUG`
- Logger retrieved via `app/utils/logging.get_logger(__name__)` throughout codebase
- Sentry integration initialized at app startup via `app/core/setup/sentry.py`

**Validation:**
- Request bodies via Pydantic schemas in `app/schemas/` and `app/schemas/v2/`
- Phone normalization exclusively via `app/schemas/validators/phone.py`
- Enum validation middleware via `app/models/enum_validation.py` (initialized at startup)

**Authentication:**
- Firebase Auth tokens verified by `app/dependencies/auth_dependencies.py`
- Sessions stored in Dragonfly (DB 2) via `app/core/session_manager.py`
- CSRF via Double Submit Cookie pattern (`app/middleware/csrf.py`); token endpoint `/api/v2/auth/csrf-token`
- Distributed rate limiting via `app/middleware/distributed_rate_limiter.py` (Redis-backed)

**LGPD/Privacy:**
- `LGPDMiddleware` (`app/middleware/lgpd_middleware.py`) enforces Brazilian data protection
- PII/PHI redaction before Gemini AI calls via `app/ai/pii_redaction.py`
- Consent management via `app/services/lgpd/consent_service.py`
- Encryption service for PII fields via `app/services/encryption/`

**Resilience:**
- Circuit breaker: `app/resilience/circuit_breaker/` (breaker, enhanced, service_breaker)
- Retry logic: `app/resilience/retry/`; also `app/core/retry.py`
- Health checks: `app/resilience/health/` and endpoints at `/health/live`, `/health/ready`
- Prometheus metrics exported at `/metrics`

---

*Architecture analysis: 2026-02-22*
