# Pitfalls Research

**Domain:** Healthcare WhatsApp patient monitoring — oncology clinic, prototype-to-production refinement
**Researched:** 2026-02-22
**Confidence:** HIGH (all critical pitfalls grounded in codebase evidence or verified sources)

---

## Critical Pitfalls

### Pitfall 1: Sync-in-Async as a Gradual Performance Cliff, Not an Instant Bug

**What goes wrong:**
The codebase has 46 `TODO(async-migration)` annotations across 7 files where synchronous SQLAlchemy `Session` calls block the FastAPI event loop inside `async def` functions. This does not crash in development or light testing. Under real patient load — WhatsApp webhooks arriving concurrently while Celery triggers quiz flows — the event loop stalls waiting on DB I/O. Every concurrent request waits behind every blocking call. Latency spikes from milliseconds to seconds; timeouts cascade; patients stop receiving messages.

**Why it happens:**
The codebase was built synchronously and partially migrated to async. SQLAlchemy 2.0 supports both sync and async engines but requires explicit query-syntax changes to use `AsyncSession`. The partial state — async endpoint definitions calling sync sessions — is the worst possible configuration: async overhead without async benefit. Benchmark data confirms mixed sync/async in FastAPI performs ~550 req/sec vs ~1,400 req/sec for pure async (a 2.5x penalty that only manifests under concurrent load).

**How to avoid:**
Migrate in hot-path order, not file order. The highest-throughput paths are: (1) WhatsApp webhook handler (`webhooks.py` — 1,144 lines, primary inbound channel), (2) quiz response processing (`enhanced_quiz_service.py` — 8 async-migration TODOs), (3) flow advancement (`flow_core.py` — 7 TODOs). These three paths handle the majority of real patient interaction. Migrate them first using `AsyncSession` + `asyncpg` driver. The `asyncpg` driver is already in `requirements.txt` — the infrastructure exists.

Do not attempt a big-bang migration of all 46 methods simultaneously. SQLAlchemy 2.0's official migration guide explicitly supports gradual, iterative migration. Use `run_sync()` as a transitional bridge for methods that cannot be migrated in a single pass.

**Warning signs:**
- p95 latency spikes under concurrent load tests (Locust, k6) while p50 appears normal
- Uvicorn worker logs showing slow requests that don't correspond to slow DB queries in isolation
- Celery tasks using `asyncio.run()` in `flow_tasks.py` (confirmed: line 326) creating new event loops per task invocation — a memory leak pattern visible in worker memory growth over time

**Phase to address:** Phase 1 (Security and Stability) — blocking correctness issue, not just performance

---

### Pitfall 2: LangGraph Silent No-Op When Import Fails

**What goes wrong:**
All LangGraph imports in `backend-hormonia/app/ai/langgraph/` are wrapped in `try/except ImportError` blocks that assign `None` to the imported classes. This means if `langgraph` is missing, outdated, or has a dependency conflict (e.g., after a `pip install` that downgrades a transitive dependency), the humanization and consensus graph features silently no-op. The API returns 200 with unhumanized template text. There is no error, no alert, no Sentry event. Patients receive robotic messages that undermine the core value proposition.

Confirmed in codebase:
- `graphs.py:12` — `StateGraph = None` on ImportError
- `runtime.py:21-31` — `MemorySaver = None`, `BaseCheckpointSaver = None` on ImportError
- `consensus.py:15,45` — double ImportError guards

**Why it happens:**
The guards were added defensively to allow the app to start in environments where LangGraph is not installed. The intent was good but the execution is incomplete: no startup health check verifies that LangGraph is actually functional before traffic arrives.

**How to avoid:**
Add a startup lifespan check in `backend-hormonia/app/core/lifespan.py` that calls `build_flow_message_graph()` and `build_humanization_graph()` at startup. If either raises `RuntimeError` (which the existing code does when `StateGraph is None`), fail fast with a clear error log and optionally block startup in production mode. Convert the `None` fallbacks from invisible degradation to `FeatureNotAvailableError` that surfaces in Sentry.

Additionally, LangGraph's `JsonPlusSerializer` checkpoint component had a remote code execution vulnerability (CVE affecting versions before checkpoint library 3.0 / LangGraph API 0.5). Verify the pinned version `>=1.0.7` includes the patched checkpoint library before going live.

**Warning signs:**
- LangGraph version constraint changes during `pip install` (transitive dependency conflict)
- Messages being sent with un-humanized template variable placeholders (e.g., literal `{{patient_name}}` in WhatsApp messages)
- No LangGraph-related log lines appearing in structured logs despite quiz flow activity

**Phase to address:** Phase 1 (Security and Stability) — silent degradation in the clinical communication path is unacceptable in production

---

### Pitfall 3: Dual Flow System Divergence Creates Invisible Patient State Corruption

**What goes wrong:**
Two parallel flow engines coexist: the production system (`flow_core.py`/`enhanced_flow_engine.py` — SQLAlchemy `PatientFlowState`, day-based) and the QW-021 system (`services/flow/core/manager.py` — Pydantic `FlowContext`, step-based). Both are tested independently but not together. A bug fix applied to one system but not the other creates a divergence that only surfaces when a patient's flow state becomes inconsistent — e.g., a patient appears active in the step-based system but their day-counter in the legacy system has not advanced. This is invisible until a patient misses a message or receives a duplicate.

**Why it happens:**
The QW-021 migration was started but not completed. The intended outcome was to decommission the flat-file production system, but the migration roadmap was not defined. The result is two systems running in production simultaneously with no clear seam between them, no integration test covering their interaction, and no documented ownership.

**How to avoid:**
Before consolidating, write integration tests that explicitly probe the boundary between the two systems: what state lives in each, when each is consulted, and whether a patient record can be in a state visible to one but not the other. The consolidation plan must choose a single canonical system and migrate all callers before deprecating the other — not "run both and see which wins." Use the tombstone pattern (already established in this codebase) to decommission the loser rather than leaving both active.

Do not apply bug fixes to both systems. Apply every fix only to the designated canonical system. Any fix applied to the legacy system during consolidation is wasted work.

**Warning signs:**
- The same patient appearing in both `PatientFlowState` DB rows and `FlowContext` Pydantic objects with different status values
- Flow-related tests passing in isolation but failing when run together
- Quiz triggers firing twice for a single patient (indicating both systems evaluated the same condition)

**Phase to address:** Phase 2 (Core Refactoring) — must be resolved before adding any new flow functionality

---

### Pitfall 4: asyncio.run() in Celery Tasks Causes Event Loop Memory Leaks

**What goes wrong:**
`flow_tasks.py:326` calls `asyncio.run(process_daily_flows_async(limit))` directly. `asyncio.run()` creates a new event loop, runs the coroutine, and closes the loop — every invocation. Under the 38-task Celery Beat schedule, this creates one new event loop per periodic task execution. Connection pools (SQLAlchemy async pool, asyncpg pool, Redis client pool) attached to the previous event loop become orphaned. Over hours, workers accumulate leaked resources. The symptom is gradual worker memory growth followed by OOM kill, which silently drops in-flight task execution with no patient-facing error.

Other Celery tasks in the same project have already identified and fixed this pattern: `response_tasks.py:103` and `helpers.py:69` both have explicit comments documenting the fix to `async_to_sync`. The fix exists in the codebase — it has not been applied consistently.

**Why it happens:**
`asyncio.run()` is the obvious way to call an async function from a sync context. The `async_to_sync` approach from `asgiref` is less intuitive but correct for Celery workers because it reuses the worker's event loop rather than creating a new one per invocation.

**How to avoid:**
Audit every Celery task file for `asyncio.run()` calls. Replace with `asgiref.sync.async_to_sync()` following the pattern already established in `helpers.py:69`. For tasks that create their own connection pools (like daily flow processing), use `@worker_process_init.connect` to initialize a single shared event loop per worker process rather than per task.

**Warning signs:**
- Railway worker memory steadily increasing over the 24-hour operating period, then resetting after a restart
- Celery worker health endpoint showing increasing RSS memory without corresponding throughput increase
- OOM kills in Railway logs correlating with high-frequency periodic tasks

**Phase to address:** Phase 1 (Security and Stability) — memory leak in production workers, affects reliability

---

### Pitfall 5: LGPD Deletion Audit Gap Creates Regulatory Exposure

**What goes wrong:**
LGPD Art. 16/18 patient deletion audits are written only to application logs (`backend-hormonia/app/repositories/patient/audit.py`, lines 190-205), not to a persistent audit table. Railway log retention policies and log rotation can destroy these records. Under LGPD enforcement (ANPD has been "very active" since 2023, with BRL 98 million in fines across 2023-2025), a healthcare provider unable to demonstrate audit trails for patient data deletion faces significant penalties and reputational damage.

Separately, AI event types (`AI_QUERY`, `AI_SUMMARY`, `AI_RECOMMENDATION`) are not in the `AuditEventType` enum (`audit/reports.py:70`), meaning every Gemini/LangGraph call to process patient questionnaire data is invisible to the audit trail. For LGPD Art. 46 (security of processing of sensitive health data using automated means), this is a specific compliance gap.

**Why it happens:**
Audit logging is typically added incrementally and log-based audit is sufficient in early prototypes where logs are manually reviewed. The transition to a dedicated audit table is often deferred and then forgotten. The AI audit gap is a newer addition: LangGraph was integrated after the audit infrastructure was established, and the enum was never updated.

**How to avoid:**
Create a `patient_deletion_audit` table via Alembic migration with columns for: patient_id (hashed), deletion_timestamp, requesting_user_id, legal_basis (Art. 16 exception or consent withdrawal), and operator_id. Write to this table before any deletion, not after — if the DB write fails, do not proceed with deletion. Treat the audit record as a precondition, not a side effect.

Add `AI_QUERY`, `AI_SUMMARY`, `AI_RECOMMENDATION`, `AI_HUMANIZATION` to `AuditEventType` enum with a corresponding Alembic enum migration. Route all LangGraph node completions through the audit service.

**Warning signs:**
- Patient deletion events visible only in structured log files, not queryable via the audit API endpoint
- AI-related activity absent from audit reports despite confirmed Gemini API calls (visible in Google Cloud console)
- Gaps in audit timeline that correspond to LangGraph humanization events

**Phase to address:** Phase 1 (Security and Stability) — LGPD compliance is a precondition for going live with real patients

---

### Pitfall 6: Encryption Key Rotation Has No Batch Re-Encryption Path

**What goes wrong:**
`backend-hormonia/app/services/encryption/service.py:609` has `# TODO: Implement batch re-encryption`. This means LGPD Art. 46 encryption key rotation is only partially implemented: new data is encrypted with new keys, but existing patient records (PHI fields: names, phone numbers, medical notes) remain encrypted with the old key after rotation. If the old key is compromised and rotated, all historical data is still readable with the compromised key. In a security incident scenario, key rotation provides no actual protection for historical patient records.

**Why it happens:**
Batch re-encryption is architecturally complex. It requires reading, decrypting, re-encrypting, and writing every PHI record atomically or with idempotent resumption. The naive implementation locks the DB for the duration; the correct implementation requires chunked processing with a resumable job. This complexity is why it was deferred to a TODO.

**How to avoid:**
Implement batch re-encryption as a Celery task with chunked DB iteration (100 records per chunk using `yield_per()` or offset pagination), idempotent design (a `key_version` column on encrypted records so the task can be resumed without re-processing records already migrated), and a progress indicator via Redis. The task should run in maintenance mode or during off-peak hours with explicit progress logging. This is not a small task — plan it as a full story with a rollback strategy.

The key version column approach also provides an observable metric: the ratio of records on old vs. new key version, queryable before decommissioning old keys.

**Warning signs:**
- `key_version` or `encryption_version` column absent from patient PHI tables (indicating no key versioning exists)
- Inability to answer "how many records are encrypted with key version X" without a full table scan
- No integration test for `batch_reencrypt()` that verifies all records can be decrypted after rotation

**Phase to address:** Phase 2 (Core Refactoring) — must be implemented before any production key rotation event

---

### Pitfall 7: Compatibility Shim Accumulation Hides Import Failures

**What goes wrong:**
The codebase has 10+ compatibility shim files that re-export from canonical locations with `# noqa: F401`. The shims have no test coverage themselves. If the canonical module is renamed, moved, or removed during refactoring, the shim silently becomes a `ModuleNotFoundError` at the import time of any consumer — not at the shim file itself. The failure surface is invisible: the shim appears to exist (the file is present), but the import it delegates to does not. In a production deployment, this causes startup failures that manifest as 503s with no useful error message at the failed-shim level.

**Why it happens:**
The tombstone and shim patterns are established and correct as patterns. The problem is that shims are created as one-way migrations ("we'll clean this up later") and the "later" never comes. Without automated verification, stale shims accumulate and become landmines.

**How to avoid:**
Add an integration test — a single test file `tests/test_shim_integrity.py` — that imports every known shim target and asserts it is importable. Run this test in CI. When a canonical module is moved or renamed during refactoring, the shim integrity test fails immediately, before deployment.

Complement this with a scheduled shim cleanup: when a story refactors a module, the Definition of Done includes: (1) update all direct callers, (2) convert the shim to a tombstone, (3) schedule tombstone removal at a fixed future date.

**Warning signs:**
- Import errors in production logs that reference a canonical path (not a shim path) but originate from a file that should be importing the shim
- Shim files where the `# noqa: F401` import has an `ImportError` in CI but not locally (version mismatch)
- Growing list of shim files with no corresponding removal tickets

**Phase to address:** Phase 2 (Core Refactoring) — each refactoring story should validate shims as part of Definition of Done

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Sync `Session` in `async def` with `run_in_executor` wrapper | Avoids full AsyncSession migration | Threadpool overhead per DB call; masks the real issue; never fully async | Only as a documented temporary bridge for a specific path during phased migration |
| `try/except ImportError: X = None` for optional features | App starts even if dependency missing | Silent no-ops that are invisible in production monitoring | Only when the feature is truly optional AND there is a startup health check that flags missing dependencies |
| Log-only audit for compliance events | Fast to implement | Non-compliant with LGPD/HIPAA audit retention requirements; log rotation destroys records | Never for patient data deletion, PHI access, or AI-assisted clinical actions |
| Applying bug fixes to both dual-system codepaths | Immediate safety | Double maintenance burden; divergence is inevitable; wastes effort that should go into consolidation | Never — choose one system and fix only that one |
| `asyncio.run()` in Celery tasks | Simple and readable | New event loop per task invocation; connection pool leaks; memory growth | Never in production Celery workers |
| Hardcoded metric stubs (e.g., `avg_task_duration_seconds = 2.5`) | Passes type checker, no errors | Misleading health dashboards; on-call responders cannot trust metrics | Never in production health endpoints |

---

## Integration Gotchas

Common mistakes when connecting to the external services in this project.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Evolution API webhooks | Silently dropping messages when handler throws an unhandled exception | Always route failed webhook processing to the DLQ; never let `webhooks.py` return a non-200 to Evolution API (it will retry indefinitely) |
| Firebase Auth | Testing only the happy path (valid token); missing the session hand-off seam | Write integration tests for the Firebase token → backend session exchange; the gap is confirmed in `CONCERNS.md` as a skipped test |
| Google Gemini / LangGraph | Assuming Gemini latency is negligible | LangGraph agent loops add 7-10s latency per message generation; set explicit timeouts in `LangGraph` graph config; circuit-break on Gemini unavailability with a fallback to plain template text |
| Dragonfly (Redis-compatible) | Using `keys()` pattern in any code path | Always use `scan_iter(match=pattern, count=100)`; `keys()` blocks the entire Dragonfly instance while scanning; confirmed risk in `redis_manager/utils.py` mock code |
| AWS RDS PostgreSQL | No connection pool sizing for Celery workers | Celery workers each open their own connection pool; with Railway auto-scaling, this can exhaust RDS `max_connections`; set explicit `pool_size` and `max_overflow` in worker DB config |
| Celery Beat | Running a single Beat instance with no HA | Use `redbeat` (PyPI: `celery-redbeat`, Production/Stable as of Jul 2025) to store schedule in Redis with distributed lock; allows redundant Beat instances with automatic failover |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| WebSocket connection manager using in-memory dictionaries | Only clients on the same API instance receive broadcasts; split-brain dashboard | Move connection registry to Redis pub/sub; `redis_pubsub_manager.py` exists but integration is unclear | At 2+ API instances (Railway auto-scaling) |
| Metrics collector hitting DB on every cache miss with no circuit breaker | Dashboard load causes DB CPU spike that cascades to patient-facing API | Add stale-while-revalidate caching; pre-aggregate in Celery Beat tasks; add query timeout per `CONCERNS.md` recommendation | At ~50+ concurrent dashboard users |
| Patient import/export without pagination | Long-running DB session blocks connection pool for all other requests | Chunk imports via Celery tasks with progress tracking; `import_export.py` is 1,027 lines and holds sessions open | At imports of >500 patients |
| Celery Beat as a single Railway process | 38 periodic tasks skip silently if Beat crashes and restarts | Deploy `redbeat` for HA Beat; monitor Beat heartbeat in health check | Any Beat crash during patient-critical windows (daily flow triggers at 8am) |
| Sync SQLAlchemy under async FastAPI | p95 latency degrades non-linearly as concurrency increases | Migrate high-throughput paths to `AsyncSession` first | At ~20+ concurrent active WhatsApp sessions |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Firebase service account JSON file on working directory disk | Developer accidentally commits credential to git (even with .gitignore, the file is present) | Migrate to GCP Secret Manager; load credential at runtime via env var; remove the file from all working directories |
| `TEST_TOKEN_REGISTRY` auth bypass shipped in production binary | Debug token bypass exists in production code even if gated by env check; supply chain attack could enable it | Move test auth bypass to `conftest.py` only; do not ship in production binary; confirmed as current risk in `CONCERNS.md` |
| `get_admin_user()` in `enhanced_monitoring.py` bypasses token validation | Monitoring metrics accessible to anyone with DB admin record presence | Replace with standard `get_current_user` + role check dependency; confirmed as current risk in `CONCERNS.md` |
| Default `SECURITY_SECRET_KEY` present as a fallback value | Development environments run with a known weak JWT key; key rotation requires finding all environments using the default | Remove the default value entirely; require explicit env var even in dev; production validator exists but dev is unprotected |
| AI actions not in audit enum | Gemini API calls processing oncology patient questionnaire responses are invisible to LGPD/HIPAA audit trail | Add AI event types to `AuditEventType` enum; route all LangGraph node completions through audit service |
| `python-jose` still imported in test files | CVE-2024-23342 affected package code still callable in test execution environment | Replace remaining `from jose import jwt` in `test_security_comprehensive.py:204` and `test_admin_contracts.py:211` with `import jwt` (pyjwt) |

---

## UX Pitfalls

Common user experience mistakes specific to this domain (oncology patient communication).

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Robotic template text when LangGraph silently no-ops | Oncology patients receive impersonal, clinical-sounding messages; undermines trust in the system; patients may disengage | Implement startup health check for LangGraph; if humanization fails, log error and fall back to a warmly-worded pre-approved template, not raw DB template text |
| Physician availability endpoint returning empty list silently (HTTP 200) | Medical staff get no error, no feedback — scheduling UI appears functional but no slots are available | Return HTTP 501 Not Implemented or HTTP 503 with a clear error body until `get_available_slots()` is implemented; silence is worse than an explicit error |
| Quiz flow advancing to next question before patient has time to respond | Patients feel rushed; automated follow-ups arrive before they have engaged with current message | Add configurable minimum response window (e.g., 24h) before flow advances; respect Brazilian patient communication norms |
| No WhatsApp message delivery confirmation tracked at the application layer | Message appears "sent" in system but patient never received it (Evolution API delivered to WhatsApp but not to device) | Track delivery status webhooks from Evolution API; update message delivery state in DB; surface failed deliveries in physician dashboard |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces in this specific project.

- [ ] **LGPD compliance**: Middleware and consent management exist — but verify audit records for patient deletion are being written to a DB table (not just logs), and AI actions are in the audit enum
- [ ] **Encryption**: Fernet field encryption is implemented — but verify `batch_reencrypt()` exists and is tested before any key rotation occurs in production
- [ ] **Authentication**: Firebase Auth integration works — but verify the `TEST_TOKEN_REGISTRY` bypass is NOT present in the production binary, and `get_admin_user()` in monitoring router uses real token validation
- [ ] **LangGraph humanization**: Graphs compile and graphs are tested — but verify startup health check confirms LangGraph is functional before traffic arrives; confirm version is >=0.5 for checkpoint vulnerability fix
- [ ] **Celery periodic tasks**: 38 tasks defined and Beat running — but verify Beat has HA configuration (`redbeat`) and Beat heartbeat is monitored in the health endpoint
- [ ] **Dual flow consolidation**: Both systems are tested — but verify there is an integration test that covers the boundary between `flow_core.py` and `services/flow/core/manager.py` before any consolidation work begins
- [ ] **Shim integrity**: Canonical modules exist — but verify every shim file's import target still resolves (add `test_shim_integrity.py` to CI)
- [ ] **Celery async tasks**: Some tasks use `async_to_sync` — but verify `flow_tasks.py:326` and `tasks/flows/base.py:69` have been migrated away from `asyncio.run()`
- [ ] **Webhook reliability**: WhatsApp webhooks are processed — but verify all failure paths route to DLQ rather than returning non-200 to Evolution API

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Event loop blocking causing production timeout cascade | MEDIUM | Restart API workers immediately (clears stall); identify blocking path via Sentry slow transaction traces; apply `run_in_executor()` as emergency bridge; schedule proper AsyncSession migration |
| LangGraph silent no-op discovered in production | LOW | Restart API pod to trigger startup health check (if implemented); verify `langgraph` package in container; send corrective messages to affected patients using approved non-AI template |
| Dual flow divergence causing patient state corruption | HIGH | Identify the authoritative system for each affected patient; manually reconcile state via admin tooling; add an integration test to prevent recurrence; the longer both systems run without consolidation, the higher this recovery cost |
| LGPD audit gap discovered during ANPD inquiry | HIGH | Reconstruct audit trail from application logs and structured log archive (Sentry, Railway logs) for the period before the DB audit table was created; implement persistent audit immediately; engage LGPD compliance counsel |
| Encryption key rotation without batch re-encryption | HIGH | Keep old key available indefinitely (cannot decommission it); implement batch re-encryption before any future rotation; historical records remain encrypted with the original key permanently |
| Shim import failure in production deployment | LOW | Roll back to previous deployment; identify which canonical module was moved; update the shim; redeploy |
| Celery Beat downtime causing missed periodic tasks | MEDIUM | Restart Beat container; Beat will resume on next scheduled interval (tasks are not backfilled); manually trigger missed critical tasks (e.g., daily flow triggers) via Celery admin or Flower UI |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Sync-in-async event loop blocking | Phase 1 (high-throughput paths: webhook, quiz response, flow advancement) | Load test with 50 concurrent WhatsApp sessions; p95 latency must remain under 2s |
| LangGraph silent no-op | Phase 1 | Startup health check test; integration test verifying humanization output differs from raw template text |
| Dual flow divergence | Phase 2 (before any new flow feature) | Integration test covering `flow_core.py` ↔ `services/flow/core/manager.py` boundary passes; single canonical system designated |
| asyncio.run() event loop leak | Phase 1 | Memory stability test: run 38 periodic tasks for 24h; worker RSS must not increase monotonically |
| LGPD deletion audit gap | Phase 1 | `patient_deletion_audit` table exists; integration test writes and reads a deletion record; AI event types in `AuditEventType` enum |
| Encryption batch re-encryption | Phase 2 | `batch_reencrypt()` implemented, tested, and idempotent; `key_version` column on PHI tables; recovery drill documented |
| Shim accumulation | Phase 2 (ongoing) | `tests/test_shim_integrity.py` passes in CI; all shims created during Phase 2 refactoring have tombstone schedule |
| asyncio.run() Celery tasks | Phase 1 | Grep for `asyncio.run(` in `app/tasks/`; must return zero results in production task files |
| Firebase service account on disk | Phase 1 | Verify file absent from all deployed containers; credential loaded via env var |
| Monitoring auth bypass | Phase 1 | `enhanced_monitoring.py` uses `get_current_user` dependency; no `get_admin_user` raw DB query |

---

## Sources

- Codebase analysis: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/.planning/codebase/CONCERNS.md` — direct evidence for pitfalls 1-7
- [FastAPI + SQLAlchemy 2.0: Modern Async Database Patterns (Dec 2025)](https://dev-faizan.medium.com/fastapi-sqlalchemy-2-0-modern-async-database-patterns-7879d39b6843) — sync/async performance benchmarks
- [Building High-Performance Async APIs with FastAPI, SQLAlchemy 2.0, and Asyncpg](https://leapcell.io/blog/building-high-performance-async-apis-with-fastapi-sqlalchemy-2-0-and-asyncpg) — async migration patterns
- [SQLAlchemy 2.0 Major Migration Guide](https://docs.sqlalchemy.org/en/21/changelog/migration_20.html) — gradual migration strategy (official)
- [LangGraph production deployment best practices 2025](https://blog.langchain.com/is-langgraph-used-in-production/) — LangGraph in production guidance
- [Critical Flaw in LangGraph — RCE via Deserialization](https://cyberpress.org/flaw-in-langgraph/) — checkpoint serialization CVE
- [Advanced Error Handling Strategies in LangGraph Applications](https://sparkco.ai/blog/advanced-error-handling-strategies-in-langgraph-applications) — graceful degradation patterns
- [Using Celery With FastAPI: The Async Inside Tasks Event Loop Problem](https://medium.com/@termtrix/using-celery-with-fastapi-the-async-inside-tasks-event-loop-problem-and-how-endpoints-save-79e33676ade9) — asyncio.run() leak in Celery
- [Distributed Scheduling Gone Wrong: The Celery Beat Trap](https://medium.com/@sudarshaana/distributed-scheduling-gone-wrong-the-celery-beat-trap-and-how-we-escaped-85c7e53828f6) — Beat SPOF
- [RedBeat: A Celery Beat Scheduler for Redis (Jul 2025)](https://pypi.org/project/celery-redbeat/) — HA Beat solution
- [LGPD Enforcement Guide: Brazil's Data Protection Fines](https://www.compliancehub.wiki/breaches-and-fines-under-brazils-lei-geral-de-protecao-de-dados-lgpd-2/) — ANPD enforcement activity
- [Data Protection Laws and Regulations Report 2025-2026 Brazil](https://iclg.com/practice-areas/data-protection-laws-and-regulations/brazil) — LGPD current status
- [Encryption Key Rotation: The Compliance Blind Spot](https://kiteworks.substack.com/p/encryption-key-rotation-the-compliance) — key rotation best practices
- [AI and LLM Data Provenance and Audit Trails for Healthcare](https://www.onhealthcare.tech/p/ai-and-llm-data-provenance-and-audit) — AI audit trail requirements
- [Martin Fowler: Parallel Change pattern](https://martinfowler.com/bliki/ParallelChange.html) — dual system consolidation strategy

---
*Pitfalls research for: Healthcare WhatsApp patient monitoring — oncology clinic*
*Researched: 2026-02-22*
