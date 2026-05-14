# M015 Research — Runtime Security Validation

**Milestone:** M015 Runtime Security Validation  
**Date:** 2026-05-14  
**Audience:** roadmap planner and slice planners  
**Scope of research:** backend runtime harness, DB TLS/RLS, multi-process session revocation, Taskiq/Dragonfly, private artifacts, WuzAPI/Gemini stubs, and PHI-safe evidence.

## Executive summary

M015 should be planned as a runtime harness milestone, not as another in-process pytest hardening pass. The codebase already has most product-side controls that M013/M014 introduced, but the runtime validation boundary is not yet assembled: there is no committed Postgres service, no provider stub stack, no runner, and no M015 evidence artifact.

The highest-risk first proof should be a thin harness tracer bullet: start TLS-enabled Postgres + Dragonfly + API + at least one real Taskiq worker, run migrations, verify readiness, dispatch one cross-process Taskiq smoke task that touches the DB, and write a redacted evidence skeleton. This will expose the brittle parts early: Postgres TLS certificate generation, Alembic/runtime env shape, Redis/Taskiq wiring, worker task discovery, and evidence redaction.

Natural slice order should be:

1. Harness foundation + evidence/redaction skeleton.
2. DB TLS/RLS runtime proof.
3. Session revocation/cache-fallback proof across API processes/Redis/DB.
4. Private upload/report route proof plus worker artifact safety.
5. WuzAPI/Gemini network-real provider stubs and queue/worker participation.
6. Integrated runner + M015 evidence matrix closeout.

The main surprises are:

- `backend-hormonia/docker-compose.yml` has Dragonfly/API/worker/beat/WuzAPI, but no Postgres and no Gemini stub. The WuzAPI service is a live-ish provider container, not the controlled stub M015 wants.
- `taskiq worker app.taskiq_broker:broker` may not discover the repo's task modules by default because Taskiq's default pattern is `**/tasks.py` while this repo uses `app/tasks/*_taskiq.py` and `app/tasks/smoke_test.py`.
- The async DB engine strips `sslmode=require/verify*` and uses an asyncpg SSL context with hostname/certificate verification disabled. M015 can still prove TLS encryption via direct `psycopg`/server views, but it should not claim certificate verification for the async runtime unless that code is fixed.
- Gemini currently has no application config seam for a local base URL, even though `google-genai` supports `HttpOptions(baseUrl=...)`. A product config seam is likely required to prove network-real Gemini stubbing.
- Existing app logs can include synthetic emails, phone values, patient IDs, and report output paths in some flows. Evidence collection should be allowlist/redacted, or this becomes a runtime evidence-safety red signal.

## Relevant codebase map

### Runtime composition

- `backend-hormonia/docker-compose.yml`
  - Services: `dragonfly`, `api`, `worker`, `beat`, `wuzapi`.
  - Missing for M015: PostgreSQL, WuzAPI/Gemini stubs, M015 runner, generated TLS material, multi-API process topology, evidence output volume.
  - Current `worker` command is `taskiq worker app.taskiq_broker:broker`; see Taskiq discovery risk below.
- `backend-hormonia/Dockerfile`
  - Python 3.13 slim image, installs `requirements.txt`, runs `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1`.
- `backend-hormonia/app/main.py`
  - Loads local `.env` only outside pytest/prod, creates the app through `create_application()`.
- `backend-hormonia/app/core/application_factory.py`
  - Registers middleware/routers and mounts static uploads.
  - `_setup_static_files()` mounts only `get_public_upload_root()` at `/uploads`, which is the right pattern for M015 private artifact proof.

### DB and migrations

- `backend-hormonia/app/config/settings/database.py`
  - `DATABASE_URL` is required. Redis/Dragonfly configuration is also here.
- `backend-hormonia/app/database.py`
  - Sync SQLAlchemy engine uses `create_optimized_engine(settings.DATABASE_URL, connect_args=pool_config.get_connect_args())`.
  - The sync path can rely on the psycopg URL query parameters for TLS negotiation.
- `backend-hormonia/app/core/database/async_engine.py`
  - Converts the configured URL to asyncpg.
  - If the URL contains `sslmode=require` or `sslmode=verify*`, it removes those URL parameters and creates an SSL context with `check_hostname=False` and `CERT_NONE`.
  - This is acceptable only for an encryption-negotiation proof. It is not enough for a certificate verification posture claim.
- `backend-hormonia/alembic/env.py` and `backend-hormonia/app/db/migrations.py`
  - Alembic resolves `DATABASE_URL` without importing runtime settings, which is useful for a harness runner.
  - When running Alembic from the repository root, the runner must ensure the script location/PYTHONPATH shape is correct; the backend container workdir `/app` should be easier.
- `backend-hormonia/alembic/versions/6f8c2d4a9b10_enable_rls_sensitive_tables.py`
  - Enables and forces RLS on sensitive tables when they exist and revokes public table access.
  - Creates a permissive policy for `current_user` with `USING (true) WITH CHECK (true)`.
  - This proves RLS is enabled/forced and PUBLIC is revoked; it does **not** prove tenant/doctor/patient row isolation by itself.
  - The revision is on the linear path to the current Alembic head.

### Auth/session runtime behavior

- `backend-hormonia/app/api/v2/routers/auth.py`
  - `/api/v2/auth/login` creates a DB `sessions` row and writes a Redis session entry.
  - `/api/v2/auth/logout` invalidates Redis first, then marks the DB session inactive/revoked.
  - `/api/v2/auth/logout-all` invalidates all user sessions in Redis and revokes all active DB sessions for that user.
  - `/api/v2/auth/verify-session` performs an additional DB re-check for current session state and active user.
- `backend-hormonia/app/dependencies/auth_session_contract.py`
  - Staff auth accepts only the canonical session cookie. Legacy `X-Session-ID`/Bearer transports are deliberately ignored/rejected.
- `backend-hormonia/app/dependencies/auth_session_cache.py`
  - Auth resolution tries Redis first.
  - On Redis timeout/error, it falls back to DB session lookup.
  - DB fallback requires `Session.is_active`, `revoked_at IS NULL`, and `expires_at > now`.
  - If Redis returns a valid-looking session payload, most protected routes do not re-check the DB session row; `verify-session` does, but generic dependencies do not.
- `backend-hormonia/app/core/redis_manager/manager.py` and `session_cache.py`
  - Session keys use `session:{session_id}` and user cache keys use canonical `user:id:{user_id}`.
  - In test mode, Redis is disabled unless `USE_TEST_REDIS=1`, so the runtime harness should avoid accidental test-mode null Redis.

Implication for M015: prove two separate contracts explicitly:

1. App-driven revocation (`logout`/`logout-all`) invalidates Redis and DB such that another API process rejects the cookie.
2. Redis outage/cache miss fallback rejects DB-revoked/expired sessions.

A stronger “DB revocation wins even if Redis is stale” contract may currently be red; if the milestone wants that guarantee, it likely needs a product change.

### Private uploads and report artifacts

- `backend-hormonia/app/api/v2/routers/upload/config.py`
  - Separates public and private upload roots.
  - Public root is mounted under `/uploads`; private root defaults to a hidden sibling directory.
  - Private URLs use `/api/v2/upload/{upload_id}/download`.
- `backend-hormonia/app/api/v2/routers/upload/__init__.py` and `handlers.py`
  - `download_upload` authorizes owner/admin before file IO.
  - Responses use `build_attachment_file_response()`.
- `backend-hormonia/app/utils/download_responses.py`
  - Central attachment helper sets `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`, and `Cache-Control: no-store`.
  - Active/unsafe MIME types are downgraded to `application/octet-stream`.
- `backend-hormonia/app/api/v2/routers/reports.py`
  - `download_report` loads cache-backed report data, checks `assert_report_access()`, and returns attachment responses.
- `backend-hormonia/app/api/v2/routers/enhanced_reports.py`
  - Builder/export downloads also use attachment helpers for generated fallback content.
  - Unsafe export URLs are withheld or blocked; safe local redirects can still happen for non-private local paths.
- `backend-hormonia/app/tasks/reports_taskiq.py` and `app/tasks/helpers/reports_helpers.py`
  - `generate_patient_report` writes PDF bytes under the private report artifact root using an opaque `{report_id}.pdf` filename.
  - The task result currently includes `output_path`. The task logging helper omits the path on success, but any evidence collector must avoid storing raw private paths.

Implication for M015: route-level upload/report behavior can be proven through HTTP without dependency overrides. Worker-generated report artifacts can be proven through Taskiq, but the planner should be careful not to imply that the worker output path itself is a public download route unless a route actually serves that artifact by ID.

### WuzAPI and Gemini provider boundaries

- `backend-hormonia/app/integrations/wuzapi/client.py`
  - Uses aiohttp, configured `base_url`, and `Token` header.
  - Key endpoints: `/chat/send/text`, media endpoints, `/session/status`, `/session/connect`, `/session/qr`.
  - Retries 429/5xx, does not retry ordinary 4xx.
- `backend-hormonia/app/integrations/whatsapp/api/routes.py`
  - Admin-only management endpoints use `get_wuzapi_for_queue()` and `WhatsAppMessageService`.
  - `/api/v2/whatsapp/messages` queues a message; `/api/v2/whatsapp/queue/process` drains a bounded batch and can force the app to call WuzAPI.
- `backend-hormonia/app/integrations/wuzapi/webhook.py`
  - `/api/v2/webhooks/wuzapi` validates HMAC/timestamp, requires Redis idempotency, then processes inbound message/receipt events.
  - Denial diagnostics use hashed event/client identifiers, but later processing logs still include phone/patient ID fields.
- `backend-hormonia/app/ai/client.py`
  - Gemini uses the `google-genai` SDK directly.
  - There is no `AI_GEMINI_BASE_URL` or equivalent setting today.
  - The installed SDK supports `genai.Client(http_options=types.HttpOptions(baseUrl=...))`, so a low-impact config seam is feasible.
- `backend-hormonia/app/ai/pii_redaction.py`
  - Prompts are redacted before external AI calls; names become `Paciente`, and email/CPF/phone-like values are replaced or removed.

Implication for M015: WuzAPI network stubbing is straightforward with the existing base URL. Gemini network stubbing requires a new configuration seam or a dedicated runtime-only client injection path; otherwise M015 cannot honestly prove “the app used the configured Gemini stub endpoint”.

### Taskiq/Dragonfly wiring

- `backend-hormonia/app/taskiq_broker.py`
  - Broker URL comes from `TASKIQ_BROKER_URL`, then `CELERY_BROKER_URL`, then `REDIS_URL`.
  - Uses `ListQueueBroker` with Redis result backend and `SmartRetryMiddleware`.
- `backend-hormonia/app/tasks/smoke_test.py`
  - Provides `smoke_test_echo` and `smoke_test_db_query`; these are ideal for early harness proof of dispatch → worker → DB → result backend.
- `backend-hormonia/app/tasks/*_taskiq.py`
  - Real task modules are named `*_taskiq.py`, not `tasks.py`.
- Taskiq CLI inspection showed default worker discovery pattern is `**/tasks.py`.

Implication for M015: use explicit worker modules or file-system discovery, for example an M015 worker command shaped like:

```bash
taskiq worker app.taskiq_broker:broker \
  app.tasks.smoke_test \
  app.tasks.messaging_taskiq \
  app.tasks.reports_taskiq \
  --workers 2
```

or:

```bash
taskiq worker app.taskiq_broker:broker \
  --fs-discover \
  --tasks-pattern '**/*_taskiq.py' \
  --tasks-pattern '**/smoke_test.py'
```

The exact command should be verified in the first slice.

### Existing tests and evidence patterns

- `backend-hormonia/tests/conftest.py`
  - Defaults to SQLite unless `TEST_DATABASE_URL`/`DATABASE_URL` points to local Postgres and `USE_TEST_POSTGRES=1` or local host is detected.
  - Security tests are not part of default collection; M014 ran them by explicit path.
- `backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py`
  - Good pattern for an artifact validator: required rows/surfaces/commands/evidence IDs and unsafe sentinel rejection.
- `backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md`
  - The reviewer-facing matrix pattern is directly reusable for M015.

M015 should add a new matrix and validator rather than mutating the M014 artifact.

Recommended paths:

- `backend-hormonia/docker-compose.m015-runtime.yml`
- `backend-hormonia/scripts/security/verify-m015-runtime-security.sh`
- `backend-hormonia/scripts/security/m015_runtime/` for Python runner helpers/stub services/probe scripts.
- `backend-hormonia/tests/security/test_m015_runtime_security_evidence_matrix.py`
- `backend-hormonia/docs/reports/security/m015-runtime-security-evidence-matrix.md`
- A gitignored runtime scratch directory such as `backend-hormonia/.m015-runtime/` for generated certs, container env files, temporary evidence JSON, and logs.

## What should be proven first

The first proof should not be the whole security matrix. It should be a minimal vertical runtime proof that exercises all foundation dependencies:

1. Generate local test TLS material into a gitignored scratch directory.
2. Start M015 Postgres with TLS, Dragonfly, API, and a Taskiq worker.
3. Run Alembic migrations against the M015 DB.
4. Check app readiness and DB connectivity.
5. Dispatch `app.tasks.smoke_test.smoke_test_db_query` through Dragonfly to a worker and retrieve/verify the result.
6. Write a tiny evidence JSON/matrix row through the redaction layer.
7. Tear down with volumes removed.

This tracer bullet should be the first slice because it validates the harness shape that all later security proofs depend on.

## Boundary contracts that matter

### Harness contract

- Single committed runner command from repository root, expected shape: `./backend-hormonia/scripts/security/verify-m015-runtime-security.sh` or `./scripts/security/verify-m015-runtime-security.sh` if the project prefers root scripts.
- Does not read local gitignored `.env` secrets.
- Generates only synthetic keys, passwords, certs, users, patients, sessions, uploads, provider payloads, and AI prompts.
- Uses a deterministic compose project name and cleans up containers/volumes on success and failure.
- Fails non-zero on harness setup failure, product security failure, redaction failure, missing evidence rows, or teardown failure that risks contaminated follow-up runs.

### DB TLS/RLS contract

- TLS proof should be explicit and queryable, for example:
  - connection negotiated SSL via `pg_stat_ssl` or `ssl_is_used()` where available;
  - client used a TLS-demanding URL/config;
  - no DSN/password appears in evidence.
- RLS proof should distinguish:
  - enabled/forced/revoked posture on sensitive tables;
  - policy execution behavior for a non-owner/non-privileged role.
- Current migration is permissive for `current_user`; do not overclaim tenant isolation from that migration alone.

### Session contract

- Use real HTTP cookies from `/api/v2/auth/login`, not dependency overrides or direct helper calls.
- Use two API processes/containers rather than relying on in-process `TestClient`.
- Prove app-driven logout/log-out-all invalidates across another process.
- Prove DB fallback rejects revoked/expired sessions when Redis is unavailable or the session key is missing.
- If the selected claim includes “DB revocation always wins over stale Redis”, test it directly; expect potential product work.

### Taskiq/Dragonfly contract

- A real worker process must execute selected tasks.
- Worker discovery must explicitly load the modules under test.
- Readiness must include an actual task execution/result, not just Redis ping. Current health code treats broker reachability as worker-ish health and does not prove a worker consumed a message.

### Provider stub contract

- WuzAPI stub should assert path, method, `Token` header presence without persisting token value, bounded timeout/error/replay scenarios, and synthetic payload shape.
- Gemini stub should be reached over HTTP by the app, not by an in-process fake. This likely needs `AI_GEMINI_BASE_URL`/`AI_GEMINI_USE_STUB` or equivalent.
- Stub evidence should record only counts, scenario names, and redaction verdicts; no raw provider request bodies.

### Private artifact contract

- Private upload download: owner/admin succeed; anonymous/foreign/deleted/missing/path traversal fail closed.
- Response headers: attachment, `nosniff`, `no-store`, safe content type, no redirect to `/uploads` or private paths.
- Report/download routes: prove attachment behavior and ownership checks for the routes selected. If proving worker-generated artifacts, also prove task artifacts remain under private root with opaque names and that evidence does not store raw output paths.

### Evidence contract

- Matrix rows map every M014-deferred runtime seam to fresh evidence, explicit non-goal, or fixed outcome.
- Validator rejects missing rows, placeholders, stale command references, raw DSNs, cookies, Authorization values, provider payloads, signed state, private filesystem paths, and patient/provider identifiers.
- Prefer allowlisted evidence summaries over raw service logs.

## Known failure modes that should shape slice ordering

1. **Postgres TLS setup brittleness.** Local cert generation and Postgres SSL config are the most likely setup flake. Put this early.
2. **Async DB TLS overclaim risk.** The async engine disables certificate verification. Decide whether M015 fixes this or restricts the claim to TLS encryption/negotiation.
3. **Taskiq task discovery.** Existing compose worker command is likely too weak for M015. Fix in harness before relying on worker evidence.
4. **Test-mode Redis nulling.** `TESTING=1` without `USE_TEST_REDIS=1` disables Redis through the null manager. Runtime harness should run in a non-pytest production-like env or explicitly enable test Redis.
5. **Production env validation vs local HTTP.** `APP_ENVIRONMENT=production` requires secure keys, AI key, WuzAPI token, secure cookies, and SSL redirect. A local synthetic env such as `APP_ENVIRONMENT=m015-runtime`, `APP_ENABLE_DEBUG=false`, and generated synthetic secret values may be more practical while still production-like. If true `production` is required, handle HTTPS/forwarded proto intentionally.
6. **Gemini has no stub base URL.** Add the config seam before trying to prove Gemini network wiring.
7. **Stale Redis session semantics.** DB fallback is safe, but Redis-positive auth may bypass DB revocation on generic routes. Test the exact selected claim early enough to fix product behavior if red.
8. **Raw logs are risky evidence.** Existing code logs synthetic email/phone/patient IDs in some paths and report tasks can return paths. Evidence collection must sanitize or avoid raw logs.
9. **Security tests are explicit-path only.** The M015 runner must call the new tests by path or place runtime probes in scripts; relying on default pytest discovery may skip security files.

## Recommended roadmap slices

### S01 — Harness tracer bullet and evidence skeleton

Goal: prove the harness can boot and record safe evidence before implementing deep security assertions.

Deliverables:

- M015 compose override/profile with TLS Postgres, Dragonfly, API, one worker, and placeholder stubs.
- Runner script with generate-start-wait-migrate-probe-teardown lifecycle.
- Generated synthetic env and cert handling under a gitignored scratch path.
- Taskiq smoke DB task proof using a real worker.
- Initial M015 matrix file and validator with unsafe sentinel rules.

Acceptance focus:

- Runner exits 0 for the smoke proof and non-zero on forced setup failure.
- No raw secrets/DSNs/cookies/provider bodies/private paths in evidence.

### S02 — DB TLS and RLS runtime proof

Goal: close the M014 DB TLS/RLS deferral with a real local PostgreSQL service.

Deliverables:

- Postgres TLS material generation and server config.
- Alembic migration execution in harness.
- Probe script/test for SSL negotiation and RLS status/policy execution.
- Evidence rows for TLS and RLS with exact commands and sanitized output.

Important caveat:

- Decide whether certificate verification is required. If yes, fix async engine SSL handling or make the proof explicitly direct-psycopg plus product config posture.

### S03 — Multi-process session revocation and fallback

Goal: prove selected session/JWT runtime seams across process/cache/DB boundaries.

Deliverables:

- Synthetic admin/two-doctor/two-patient/session fixtures through DB/API.
- Two API processes or two API containers sharing DB/Dragonfly.
- HTTP probes for login, protected route, logout/logout-all, other-process rejection.
- Redis miss/outage fallback probes for revoked/expired DB sessions.
- If stale Redis accepts a DB-revoked session and the claim requires DB source-of-truth, fix before close.

### S04 — Private app-route artifact proof

Goal: prove deployed-style app-route behavior for private uploads and selected report routes.

Deliverables:

- Runtime fixture seeding for private/public uploads owned by synthetic users.
- Owner/admin/foreign/anonymous HTTP probes against `/api/v2/upload/{id}/download`.
- Header/content/redirect assertions.
- Report route probes for `/api/v2/reports/{id}/download` and enhanced report/export routes selected by the planner.
- Optional Taskiq report generation proof for private opaque artifact path, with path redacted from evidence.

### S05 — Provider stubs and queue/worker wiring

Goal: prove app-to-stub network wiring and controlled failure modes for WuzAPI/Gemini without live providers.

Deliverables:

- Local WuzAPI HTTP stub with success, 4xx, 5xx, timeout, duplicate/replay-style scenarios.
- Gemini HTTP stub plus app config seam for base URL/stub endpoint.
- Runtime probes that force the app to call each stub.
- Queue/worker participation for at least one selected WhatsApp/security scenario, not just direct HTTP mocks.
- Stub request redaction assertions.

### S06 — Integrated runner and matrix closeout

Goal: make the single runner reviewer-ready and enforce the final evidence contract.

Deliverables:

- Full runner invoking all selected probes.
- M015 evidence matrix with rows for all M014-deferred runtime items and non-goals.
- Validator rejecting missing/stale/unsafe evidence.
- Final teardown/diagnostic behavior documented.

## Requirements review

`.gsd/REQUIREMENTS.md` currently has no Active requirements. The relevant existing entries are:

- **R014 (deferred):** the direct M015 target. It should likely move from deferred to validated only after the integrated runner and matrix are complete.
- **R012/R013 (validated with explicit runtime deferrals):** table stakes are to close only the runtime portions M014 did not claim, not to reopen every controlled M014 proof.
- **R015 (anti-feature):** no production exploitation and no real PHI remains mandatory.
- **R017 (anti-feature/evidence-safety constraint):** all evidence/logs/diagnostics must avoid PHI, tokens, cookies, signed states, secrets, provider bodies, and private paths.
- **R018 (anti-feature/no silent drop):** every deferred runtime item needs a matrix outcome.

Candidate requirements for planner consideration, not auto-binding:

1. **Runtime harness entrypoint requirement:** a single runner must orchestrate startup, migrations, probes, evidence, and teardown without reading real secrets.
2. **Gemini stub configuration requirement:** the app must support a local Gemini base URL/stub mode for synthetic runtime validation.
3. **Worker discovery requirement:** runtime validation workers must explicitly load selected Taskiq modules and prove task consumption, not only broker reachability.
4. **TLS posture requirement:** define whether M015 requires encryption-only negotiation or certificate verification (`verify-full`-style). This decision affects whether async engine code must change.
5. **Evidence-redaction requirement:** raw service logs are not evidence unless passed through an allowlist/redaction filter.

Likely out of scope remains unchanged: browser/frontend flows, CDN/object storage, production exploitation, live WuzAPI/Gemini credentials, broad fuzzing/DAST-first validation.

## Skill discovery

Installed skills from the prompt that are generally relevant: `test`, `verify-before-complete`, `observability`, `security-review`, `api-design`, and `decompose-into-slices`. No installed skill is directly specialized for Taskiq, PostgreSQL TLS/RLS, Docker Compose, or FastAPI runtime harnesses.

External skill search was performed with `npx skills find` for core technologies. Promising options to consider, not installed:

- FastAPI:
  - `npx skills add wshobson/agents@fastapi-templates` — high install count, likely useful for FastAPI structure but may be template-heavy.
  - `npx skills add mindrally/skills@fastapi-python` — high install count, broadly relevant.
  - `npx skills add jeffallan/claude-skills@fastapi-expert` — FastAPI-focused.
- Taskiq:
  - No skills found for `Taskiq`.
- PostgreSQL RLS/TLS:
  - `npx skills add mindrally/skills@postgresql-best-practices` — broadly relevant Postgres skill.
  - `npx skills add troykelly/claude-skills@postgres-rls` — directly relevant to RLS, smaller install count.
  - `npx skills add yoanbernabeu/supabase-pentest-skills@supabase-audit-rls` — RLS-relevant but Supabase-specific; use cautiously.
- Dragonfly/Redis:
  - `npx skills add personamanagmentlayer/pcl@redis-expert` — Redis-focused; Dragonfly is Redis-compatible for this harness.
- Docker Compose:
  - `npx skills add manutej/luxor-claude-marketplace@docker-compose-orchestration` — high install count and directly relevant to multi-service harnessing.
  - `npx skills add thebushidocollective/han@docker-compose-production` — lower install count but production-like compose focus.
- pytest:
  - `npx skills add manutej/luxor-claude-marketplace@pytest-patterns` — relevant if slice planners build many focused probes.
  - `npx skills add pluginagentmarketplace/custom-plugin-python@pytest-testing` — generic pytest support.

## Open questions for planning

1. Should M015 require DB certificate verification, or is TLS encryption negotiation plus posture enough? Current async engine behavior makes this a real scope decision.
2. Should session auth treat DB revocation as source-of-truth even when Redis has a stale positive session? If yes, product code likely needs a revocation/version check.
3. Should the harness run two API containers on two ports, or one uvicorn process with multiple workers? Two containers are easier to target deterministically for cross-process proof.
4. Is Gemini base URL support acceptable as a product configuration change in M015? Without it, the Gemini stub requirement is not honestly provable.
5. Which report artifact route is selected for app-route proof? Current base/enhanced report downloads are route-served attachments, while Taskiq `generate_patient_report` writes a private file path as a task artifact.
6. Are sanitized/allowlisted service logs required as evidence, or can evidence be probe outputs only? Raw logs are likely too risky.

## Research evidence commands

Key research scans and inspections were saved under `.gsd/exec/`:

- `3d1235b7-656d-4e03-8f17-a336e6904eb4` — broad repo/runtime file map.
- `d15a6e1f-f795-4e3f-965e-2eda79262ef7` — auth/session file and symbol map.
- `782d6275-8b5e-4fa8-9a9c-2b241a0aed1c` — upload/report private artifact route map.
- `300969da-10c4-441e-a89c-1631382eb7c0` — Taskiq task definition map.
- `2e7bbdff-8e4f-4900-b2e3-955fea50d2fe` — external skill discovery.
- `960d673c-c4f7-4063-b410-716a449cc26e` — google-genai base URL support introspection.
- `e970b988-cb46-41f5-be31-82c0fa50053d` — Taskiq worker CLI discovery defaults.
- `dd1ed5bf-080e-44bd-b3be-ef1ec09c225a` and `41bf3d38-41b7-426c-9d3a-cac8ee32e686` — Alembic RLS revision presence and graph position.
