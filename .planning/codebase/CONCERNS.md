# Codebase Concerns

**Analysis Date:** 2026-02-22

## Tech Debt

**Sync-in-Async Pattern (42+ methods, 9+ files):**
- Issue: SQLAlchemy sync `Session` is called inside `async def` functions, which blocks the event loop and defeats FastAPI/Uvicorn's concurrency model. Previously annotated with async-migration TODO markers (all removed in v1.4).
- Files:
  - `backend-hormonia/app/services/flow/sequential_message_handler.py` (12 instances)
  - `backend-hormonia/app/services/flow_core.py` (7 instances)
  - `backend-hormonia/app/services/enhanced_quiz_service.py` (8 instances)
  - `backend-hormonia/app/orchestration/saga_orchestrator/compensation.py` (5 instances)
  - `backend-hormonia/app/orchestration/saga_orchestrator/steps.py` (3 instances)
  - `backend-hormonia/app/services/flow_dashboard.py` (4 instances)
  - `backend-hormonia/app/services/flow_alerts.py` (5 instances)
  - `backend-hormonia/app/services/firebase_user_sync_service.py` (5 instances)
  - `backend-hormonia/app/services/data_integrity_monitoring.py` (5 instances)
- Impact: Under load, blocking DB calls in async context stall the entire event loop, causing cascading timeout failures across all concurrent requests
- Fix approach: Migrate to `AsyncSession` + `asyncpg` driver throughout; Phase 2 already identified in `backend-hormonia/app/dependencies/auth_dependencies.py` docstring

**Dual Flow Systems Coexisting:**
- Issue: Two parallel, non-unified treatment-flow engines exist and are maintained in parallel, creating cognitive overhead and potential divergence.
  - Production system: flat files `flow_core.py`, `enhanced_flow_engine.py`, `flow_service.py`, `flow_management.py` (SQLAlchemy `PatientFlowState`, day-based)
  - QW-021 system: `app/services/flow/core/manager.py` (Pydantic `FlowContext`, step-based)
- Files: `backend-hormonia/app/services/flow_core.py`, `backend-hormonia/app/services/flow/core/manager.py`
- Impact: Bug fixes and feature additions may need to be applied twice; onboarding is confusing; test coverage gaps at the seam between systems
- Fix approach: Complete QW-021 migration and decommission the flat-file production system; roadmap not yet defined

**Physician Availability Logic Unimplemented:**
- Issue: `get_available_slots()` returns an empty list with a `# TODO` comment. No slot generation logic exists. The endpoint is exposed in the API.
- Files: `backend-hormonia/app/api/v2/routers/physicians/services/availability_service.py` (lines 73-77, 191)
- Impact: Any caller of the physician scheduling feature receives empty data silently, not an error
- Fix approach: Implement slot generation based on physician working-hours config; add tests

**LGPD Deletion Audit Not Persisted:**
- Issue: LGPD Art. 16/18 patient deletion audits are written only to application logs, not to a dedicated audit table. Log rotation can destroy compliance records.
- Files: `backend-hormonia/app/repositories/patient/audit.py` (lines 190-205)
- Impact: Regulatory non-compliance risk; audit trail is lossy
- Fix approach: Create `patient_deletion_audit` table; implement `record_deletion()` with persistent writes before any deletion

**Monitoring Endpoint with Placeholder Auth:**
- Issue: `get_admin_user()` in `enhanced_monitoring.py` performs a raw DB query to find any admin user without validating the request token. Auth is hardcoded as `# TODO: Replace with actual auth integration`.
- Files: `backend-hormonia/app/api/v2/routers/enhanced_monitoring.py` (lines 84-97)
- Impact: Monitoring metrics exposed without proper authentication if any admin exists in DB
- Fix approach: Replace with standard `get_current_user` + role check dependency

**Hardcoded Metric Stub in Health Endpoint:**
- Issue: `avg_task_duration_seconds` returns a hardcoded `2.5` rather than a calculated value.
- Files: `backend-hormonia/app/api/v2/routers/health/service_health.py` (line 129)
- Impact: Health dashboards show inaccurate worker performance metrics
- Fix approach: Instrument Celery task completion times and store rolling average in Redis

**Rate Limiter Race Condition:**
- Issue: Distributed rate limiter uses a non-atomic Redis pipeline (ZREMRANGEBYSCORE + ZCARD + ZADD). Under high concurrency, all concurrent requests may read `count=0` before any increments are visible, allowing brief bursts above the limit.
- Files: `backend-hormonia/app/middleware/rate_limit_core.py` (lines 184-205)
- Impact: Rate limiting can be briefly bypassed during traffic spikes
- Fix approach: Replace pipeline with a Lua script (template already included in the comment at line 188)

**API Version Stub (v1 router):**
- Issue: `backend-hormonia/app/routers/auth_session.py` (731 lines) appears to be an older v1 router that coexists with the v2 router at `backend-hormonia/app/api/v2/routers/auth.py` (1109 lines)
- Impact: Route duplication risk; maintenance burden of keeping two auth routers in sync
- Fix approach: Validate no v1 endpoints are still needed; deprecate and remove

**Compatibility Shim Accumulation:**
- Issue: 10+ compatibility shim files re-export from canonical locations with `# noqa: F401`. These are intentional but are a long-term maintenance burden.
- Files:
  - `backend-hormonia/app/core/circuit_breaker.py` → `app.resilience.circuit_breaker.service_breaker`
  - `backend-hormonia/app/services/circuit_breaker.py` → same canonical
  - `backend-hormonia/app/core/circuit_breaker_enhanced.py` → canonical
  - Multiple `__init__.py` shims across `api/v2/routers/`
- Impact: Import confusion; shims have no test coverage themselves; stale shims are invisible failures
- Fix approach: Add an integration test that verifies every shim target still exists; schedule shim removal after full import migration

**60+ Files Exceed 500 Lines:**
- Issue: Many service/router files are large monoliths with mixed responsibilities.
  - `backend-hormonia/app/dependencies/auth_dependencies.py` — 1546 lines
  - `backend-hormonia/app/services/flow/sequential_message_handler.py` — 1161 lines
  - `backend-hormonia/app/integrations/whatsapp/api/webhooks.py` — 1144 lines
  - `backend-hormonia/app/api/v2/routers/flows.py` — 1120 lines
  - `backend-hormonia/app/tasks/messaging.py` — 1118 lines
  - `backend-hormonia/app/api/v2/routers/auth.py` — 1109 lines
  - `backend-hormonia/app/services/flow_monitoring.py` — 923 lines (1 class, 30+ methods)
- Impact: Hard to test, review, and modify; high merge-conflict rate; difficult to enforce single responsibility
- Fix approach: Apply the same package-split pattern used for `template_loader_pkg` and `automated_recovery_pkg`; each file split into models/logic/service layers

**AI Audit Event Types Not in Enum:**
- Issue: AI event types are logged as raw strings because they were not added to the `AuditEventType` enum.
- Files: `backend-hormonia/app/services/audit/reports.py` (line 70: `# TODO: Add AI event types to AuditEventType Enum in future migration`)
- Impact: Audit queries using enum filters silently miss AI-originated events; HIPAA audit trails are incomplete for AI actions
- Fix approach: Add `AI_QUERY`, `AI_SUMMARY`, `AI_RECOMMENDATION` (or similar) to `AuditEventType` enum; add Alembic migration for the enum change

## Known Bugs

**Physician Scheduling Returns Empty Silently:**
- Symptoms: GET `/physicians/{id}/availability` returns an empty list with HTTP 200 for any valid physician
- Files: `backend-hormonia/app/api/v2/routers/physicians/services/availability_service.py`
- Trigger: Any call to get physician availability
- Workaround: None — feature is effectively non-functional

**async_to_sync vs asyncio.run() Inconsistency in Celery Tasks:**
- Symptoms: Some Celery tasks use `asyncio.run()` directly (which creates a new event loop per call, leaking memory), while others correctly use `async_to_sync` from `asgiref`. Comments indicate the correct fix was applied in some places but not all.
- Files:
  - `backend-hormonia/app/tasks/flows/flow_tasks.py` (uses `asyncio.run()`)
  - `backend-hormonia/app/tasks/quiz_flow/trigger_tasks.py` (comment: "prevents asyncio.run() from running event loop error")
  - `backend-hormonia/app/tasks/quiz_flow/helpers.py` (comment: "Use async_to_sync instead of asyncio.run()")
- Trigger: High-frequency Celery task execution
- Workaround: Tasks work but may leak event loop resources over time

## Security Considerations

**Firebase Service Account Key in Repository Root:**
- Risk: Firebase Admin SDK service account file exists at the repository root (`clinica-oncologica-hosting-firebase-adminsdk-fbsvc-0c279a6456.json`). The file is gitignored (`firebase-adminsdk-*.json` in `.gitignore`) and does NOT appear in tracked git history, but it remains on disk in a working directory that developers may accidentally commit or expose.
- Files: `/clinica-oncologica-hosting-firebase-adminsdk-fbsvc-0c279a6456.json`
- Current mitigation: `.gitignore` rule at line 86-87 prevents accidental commit
- Recommendations: Store the credential via a secret manager (GCP Secret Manager); load at runtime via env var or mounted volume; remove the file from working directory

**Debug Endpoints Accessible in Non-Production:**
- Risk: Debug router (`/debug/environment`, `/debug/auth`, `/debug/database`) is gated by `APP_ENABLE_DEBUG` and requires admin role, but the `get_admin_user` dependency in `enhanced_monitoring.py` bypasses actual token validation.
- Files: `backend-hormonia/app/api/v2/routers/debug/environment.py`, `backend-hormonia/app/api/v2/routers/enhanced_monitoring.py`
- Current mitigation: `check_debug_enabled()` guard; admin role required in most debug routes
- Recommendations: Ensure `APP_ENABLE_DEBUG=False` is enforced in staging/production deployments; fix the placeholder `get_admin_user` in monitoring router

**Default Insecure JWT Secret Key:**
- Risk: `SECURITY_SECRET_KEY` defaults to `"dev-insecure-secret-key-must-be-changed-in-production-railway"`. Production validator raises an error if the default is used, but development environments run with a weak key.
- Files: `backend-hormonia/app/config/settings/security.py` (line 19)
- Current mitigation: Production validator (`validate_secret_key`) blocks startup with default key in `APP_ENVIRONMENT=production`
- Recommendations: Remove the default value entirely; require explicit env var even in development

**Test Token Registry Bypass:**
- Risk: `auth_dependencies.py` includes a `TEST_TOKEN_REGISTRY` that bypasses Firebase validation when `APP_ENABLE_DEBUG=True`. This mechanism is guarded against production, but the code exists in the production binary.
- Files: `backend-hormonia/app/dependencies/auth_dependencies.py` (lines 43-60)
- Current mitigation: Production env check blocks registry activation; critical log on startup
- Recommendations: Move test authentication bypass into a test-only conftest; do not ship debug-bypass code in production binary

## Performance Bottlenecks

**Sync SQLAlchemy in Async Context (Primary Bottleneck):**
- Problem: 42+ async function calls block the event loop with synchronous DB queries via `Session` (not `AsyncSession`)
- Files: See "Sync-in-Async Pattern" in Tech Debt section above
- Cause: The codebase was built primarily synchronous and partially migrated to async; `AsyncSession` requires query syntax changes throughout
- Improvement path: Phase-by-phase migration to `AsyncSession`; start with the highest-throughput paths (quiz response processing, flow advancement, webhook handling)

**Redis `keys()` Equivalent in Analytics Cache:**
- Problem: `app/core/redis_manager/utils.py` contains an in-memory mock that calls `.keys()` with pattern matching (lines 342, 495, 548, 698). While the mock is test-only, the pattern may leak into production code if the mock is inadvertently used.
- Files: `backend-hormonia/app/core/redis_manager/utils.py`
- Cause: In-memory mock implementation uses dict `.keys()` for simplicity
- Improvement path: Replace mock `.keys()` calls with `scan_iter()` equivalent; validate production Redis client never uses `.keys()`

**No Pagination on Patient Import Export:**
- Problem: `patients/import_export.py` (1027 lines) handles bulk patient operations. Large imports may hold DB sessions open for extended periods.
- Files: `backend-hormonia/app/api/v2/routers/patients/import_export.py`
- Cause: Bulk operation design
- Improvement path: Add chunked processing with progress tracking; use Celery task for large imports

**Metrics Collector Direct DB Queries Without Caching Fallback:**
- Problem: `MetricsCollectorService` in `metrics_collector.py` (948 lines) performs direct SQL aggregations across multiple tables on every call when Redis cache misses. No circuit breaker for DB-heavy aggregation queries.
- Files: `backend-hormonia/app/services/analytics/metrics_collector.py`
- Cause: Cache miss falls through directly to full DB aggregation
- Improvement path: Add stale-while-revalidate caching; add query timeout; pre-aggregate in Celery beat tasks

## Fragile Areas

**`flow_monitoring.py` (923 lines, single class with 30+ methods):**
- Files: `backend-hormonia/app/services/flow_monitoring.py`
- Why fragile: The `FlowMonitoringService` class mixes Prometheus metrics emission, Redis alert tracking, stale-flow detection, corruption-rate monitoring, and health status aggregation. A change to any one area risks breaking others.
- Safe modification: Read the full class before any change; add unit tests for the specific method being changed before editing; each method is effectively independent so localized changes are low-risk
- Test coverage: Present in `tests/` but not systematically verified against this class

**`auth_dependencies.py` (1546 lines, dual auth systems):**
- Files: `backend-hormonia/app/dependencies/auth_dependencies.py`
- Why fragile: Contains both legacy Firebase token auth and new session-based auth, plus in-progress async migration (Phase 1 complete, Phase 2/3 pending). The migration docstring is a second header block appended at the top without removing the original header.
- Safe modification: Use only the async `get_current_user_from_session()` / `get_current_user()` paths; do not touch the deprecated sync functions without verifying all callers; any change requires running the full auth test suite
- Test coverage: `tests/auth/` has comprehensive coverage but some tests are skipped with `@pytest.mark.skip` due to Firebase Auth behavior

**Saga Orchestrator with 5 Async-Migration TODOs:**
- Files: `backend-hormonia/app/orchestration/saga_orchestrator/compensation.py`, `backend-hormonia/app/orchestration/saga_orchestrator/steps.py`
- Why fragile: Saga pattern requires all-or-nothing compensation; if a compensation step blocks the event loop it can cause compensation failure, leaving distributed state partially rolled back
- Safe modification: Do not add new DB operations without wrapping in `asyncio.get_event_loop().run_in_executor()` or migrating to `AsyncSession`; add idempotency keys to new compensation steps
- Test coverage: `tests/test_saga_refactoring.py`, `tests/test_saga_unit_of_work.py`

**Webhook Handler (1144 lines, complex routing):**
- Files: `backend-hormonia/app/integrations/whatsapp/api/webhooks.py`
- Why fragile: WhatsApp webhook processing is the primary inbound patient interaction channel. Large file with complex message routing, signature validation, and flow advancement. Any regression silently drops patient messages.
- Safe modification: Add tests for any new message type before adding routing logic; keep signature validation as the first check before any processing; use the DLQ for failed processing rather than silent drops
- Test coverage: Not visible in main test directory; DLQ tests exist at `tests/services/`

## Scaling Limits

**Celery Beat Single Point of Failure:**
- Current capacity: 38 periodic tasks scheduled via Celery Beat on a single Railway worker process
- Limit: If the Beat process crashes or restarts, no scheduled tasks run until it recovers; there is no Beat high-availability configuration
- Scaling path: Deploy Celery Beat with a distributed lock (Redis-backed via `redbeat`) to allow multiple Beat instances with leader election

**WebSocket Connection Manager (In-Memory State):**
- Current capacity: `connection_manager.py` (888 lines) stores WebSocket connections and pending pings in in-memory dictionaries
- Limit: Does not scale across multiple API server instances; a client connected to instance A will not receive broadcasts initiated from instance B
- Scaling path: Move connection registry to Redis pub/sub; `redis_pubsub_manager.py` exists but integration with WebSocket manager status is unclear

**Redis as Single Cache Layer:**
- Current capacity: All caching, sessions, rate limiting, task brokering, and pub/sub run through a single Dragonfly instance on 4 logical DBs
- Limit: If Dragonfly becomes unavailable, all of the above fail simultaneously
- Scaling path: Redis Sentinel or Cluster for HA; circuit breakers (present in `redis_manager`) already provide degraded-mode operation

## Dependencies at Risk

**`python-jose` Removed (CVE-2024-23342):**
- Risk: The removal is correct and documented in `requirements.txt` (line 14), but any code that still imports `from jose import jwt` will fail at runtime
- Impact: Silent import errors if any module was missed during migration
- Migration plan: Search for any remaining `from jose` imports; all JWT operations should use `pyjwt` (`import jwt`)

**`langgraph` with Guarded Imports:**
- Risk: `langgraph` imports are wrapped in `try/except ImportError` with `None` fallbacks throughout `backend-hormonia/app/ai/langgraph/`. If the package is missing or incompatible, LangGraph features silently degrade rather than failing fast.
- Files: `backend-hormonia/app/ai/langgraph/runtime.py`, `backend-hormonia/app/ai/langgraph/graphs.py`, `backend-hormonia/app/ai/langgraph/consensus.py`
- Impact: LangGraph-based humanization and consensus features silently no-op rather than raising errors
- Migration plan: Add a startup health check that verifies LangGraph availability; convert `None` fallbacks to explicit `FeatureNotAvailableError`

**`pytest-asyncio<0.24.0` Pin:**
- Risk: `requirements.txt` pins `pytest-asyncio>=0.23.0,<0.24.0`. Version 0.24+ changed the default `asyncio_mode` behavior. The pin prevents upgrades but leaves the project on an older release.
- Impact: Test suite may break silently when pin is eventually removed
- Migration plan: Test with `pytest-asyncio==0.24.x`; update `asyncio_mode = "auto"` in `pyproject.toml` as needed before removing pin

## Missing Critical Features

**Batch Re-Encryption Not Implemented:**
- Problem: Encryption key rotation cannot re-encrypt existing patient data at scale.
- Files: `backend-hormonia/app/services/encryption/service.py` (line 609: `# TODO: Implement batch re-encryption`)
- Blocks: LGPD Art. 46 compliance for encryption key rotation; any security incident requiring key rotation forces manual intervention

**AI Event Types Missing from Audit Enum:**
- Problem: AI model queries and responses are not captured in the structured audit log.
- Files: `backend-hormonia/app/services/audit/reports.py` (line 70)
- Blocks: Complete HIPAA audit trail for AI-assisted clinical decisions; regulatory reporting

## Test Coverage Gaps

**Firebase Auth Integration Tests Skipped:**
- What's not tested: Token refresh flow, login endpoint (both use Firebase client-side; endpoints do not exist server-side)
- Files: `backend-hormonia/tests/api/critical/test_auth_login.py`, `backend-hormonia/tests/api/critical/test_auth_refresh.py`
- Risk: Auth regression in the Firebase → backend session hand-off is not caught by automated tests
- Priority: Medium — Firebase SDK handles the primary flow; gap is in the integration seam

**Cross-Origin Headers Not Tested:**
- What's not tested: Cross-origin response headers in `SecurityHeadersMiddleware`
- Files: `backend-hormonia/tests/security/test_security_headers.py` (line 184: skipped)
- Risk: CORS misconfiguration could go undetected
- Priority: Medium

**Physician Availability Endpoint Has No Tests:**
- What's not tested: The `get_available_slots()` and `get_next_available_slot()` methods (both return empty/None)
- Files: `backend-hormonia/app/api/v2/routers/physicians/services/availability_service.py`
- Risk: Feature is non-functional and no test exists to detect future regressions or implementation attempts
- Priority: High — directly impacts patient scheduling workflow

**Dual Flow System Integration:**
- What's not tested: Interaction between the production flat-file flow system (`flow_core.py`, `enhanced_flow_engine.py`) and the QW-021 packaged system (`services/flow/core/manager.py`). Both are tested independently but not together.
- Files: `backend-hormonia/app/services/flow_core.py`, `backend-hormonia/app/services/flow/core/manager.py`
- Risk: Data consistency divergence between the two systems is invisible until a patient's flow state becomes corrupt
- Priority: High — core clinical workflow

**Saga Compensation in Partial-Failure Scenarios:**
- What's not tested: Compensation rollback when DB is unavailable mid-saga (the async-blocking issue makes this untestable in current form)
- Files: `backend-hormonia/app/orchestration/saga_orchestrator/compensation.py`
- Risk: Patient onboarding could be left in a partially-created state with no recovery path
- Priority: High — HIPAA patient data integrity

---

*Concerns audit: 2026-02-22*
