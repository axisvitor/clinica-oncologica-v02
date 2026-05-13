---
id: S01
parent: M014
milestone: M014
provides:
  - Externally reachable ingress boundaries deny missing/invalid CSRF, replay/idempotency abuse, duplicate-oracle probes, and spoofed XFF/rate-limit failures before side effects.
  - Downstream S02–S05 can assume S01 ingress controls have controlled backend pytest evidence and PHI-safe diagnostics.
  - S05 can reference gsd_exec `3b14ac02-38eb-48c5-8303-f9cf467b5d54` and `9efe8dad-808b-46fe-8c62-633744214262` in the final evidence matrix.
requires:
  []
affects:
  - S02
  - S03
  - S04
  - S05
key_files:
  - backend-hormonia/app/utils/client_ip.py
  - backend-hormonia/app/utils/rate_limiter.py
  - backend-hormonia/app/middleware/rate_limit_core.py
  - backend-hormonia/app/middleware/distributed_rate_limiter.py
  - backend-hormonia/app/utils/request_context.py
  - backend-hormonia/app/middleware/csrf.py
  - backend-hormonia/app/core/security.py
  - backend-hormonia/app/services/password_reset_service.py
  - backend-hormonia/app/api/v2/routers/auth.py
  - backend-hormonia/app/integrations/wuzapi/webhook.py
  - backend-hormonia/app/integrations/whatsapp/security/hmac_validator.py
  - backend-hormonia/app/services/webhook_service.py
  - backend-hormonia/app/services/webhook/idempotency.py
  - backend-hormonia/app/services/patient/validation_service.py
  - backend-hormonia/app/services/patient/integrity_service.py
  - backend-hormonia/app/domain/patient/onboarding/validation_service.py
  - backend-hormonia/app/api/v2/routers/patients/crud.py
  - backend-hormonia/app/core/exceptions.py
  - backend-hormonia/app/utils/db_retry.py
  - backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py
  - backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py
  - backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py
  - backend-hormonia/tests/security/test_m014_s01_webhook_replay.py
  - backend-hormonia/tests/security/test_m014_s01_duplicate_oracle.py
key_decisions:
  - D018 — shared trusted-proxy client identity and fail-closed ingress rate-limit infrastructure policy.
  - D019 — webhook replay and idempotency failures fail closed at ingress with 403/409/503 status semantics and PHI-safe diagnostics.
  - CSRF exemptions remain narrow and Authorization/X-API-Key bypass is explicit-only for true non-cookie token-auth ingress.
  - Password reset replay hardening consumes only hashed JTIs via cache SET NX EX before credential/session mutation.
  - Duplicate patient probes return generic 409 `Duplicate patient` with `details.code=duplicate_patient`, while expected validation denials do not count as DB circuit-breaker failures.
patterns_established:
  - Shared trusted-proxy client identity helper feeds rate-limit keys, request context, and PHI-safe hashed diagnostics.
  - Ingress denial tests use side-effect sentries to prove failures happen before endpoint, queue, provider, DB, or saga execution.
  - Replay/idempotency controls treat uncertainty as denial: reset cache uncertainty returns service-unavailable semantics, webhook idempotency uncertainty returns 503, and duplicates return stable 409.
  - Session-backed browser mutations require CSRF double-submit proof unless the path is explicitly classified as true non-session ingress.
  - Duplicate-oracle closure uses generic external errors plus structured internal reason codes that exclude raw PHI.
observability_surfaces:
  - Rate-limit diagnostics with reason, route/method, scope, request/correlation metadata, and hashed/redacted client identifiers.
  - CSRF denial diagnostics with event_type, reason, method/path, request_id, and hashed client identity.
  - Password reset failure diagnostics with request_id, outcome/error/status, and token-consumption reason only.
  - Webhook denial diagnostics with request/correlation IDs, route/method, event type, reason/status, and hashed identifiers.
  - Patient duplicate diagnostics with event type/reason/route/request metadata and no raw CPF/email/phone/name values.
drill_down_paths:
  - .gsd/milestones/M014/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M014/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M014/slices/S01/tasks/T03-SUMMARY.md
  - .gsd/milestones/M014/slices/S01/tasks/T04-SUMMARY.md
  - .gsd/milestones/M014/slices/S01/tasks/T05-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-05-13T14:20:16.302Z
blocker_discovered: false
---

# S01: Ingress, Replay e Rate-Limit Fail-Closed

**Hardened externally reachable ingress so CSRF failures, reset/webhook replay, duplicate-oracle probes, and spoofed rate-limit identity deny fail-closed before DB, queue, provider, saga, or route side effects.**

## What Happened

S01 closed the first M014 ingress hardening tranche with shared fail-closed controls across rate limiting, CSRF, password reset, WuzAPI/generic webhooks, and patient duplicate validation. Rate-limit identity now flows through a trusted-proxy-aware client identity helper, ignores spoofed proxy headers unless explicitly trusted, hashes/redacts identifiers in diagnostics, and denies on Redis/pipeline/timeout uncertainty before endpoint execution. CSRF exemptions were contracted to safe methods, token/documentation/health/static/public quiz paths, and non-session provider ingress; browser/session-backed mutations no longer bypass CSRF merely because Authorization or X-API-Key headers are present. Password reset confirmation now validates reset JWT claims, consumes a hashed JTI with cache SET NX EX before credential/session mutation, returns stable 409 for replay, and fails closed with service-unavailable semantics on cache uncertainty. WuzAPI and generic webhook ingress now validate HMAC/timestamp/idempotency before processing and map bad signatures/timestamps, duplicate events, and idempotency infrastructure gaps to fail-closed denial statuses without provider, DLQ, flow, or DB side effects. Patient creation duplicate checks now collapse CPF/email/phone/name-like duplicate probes into a generic 409 `duplicate_patient` conflict before saga orchestration and preserve PHI-safe logs. Supporting fixes preserved domain conflict codes, prevented expected validation denials from poisoning the DB circuit breaker, and updated fixtures/helpers so legitimate controlled flows still pass.

## Verification

Fresh closeout verification was run through `gsd_exec`, not direct shell. Focused S01 security proof passed: `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py backend-hormonia/tests/security/test_m014_s01_webhook_replay.py backend-hormonia/tests/security/test_m014_s01_duplicate_oracle.py` — exit 0, 39 passed in 1.92s, gsd_exec `3b14ac02-38eb-48c5-8303-f9cf467b5d54`. Supporting regression proof also passed: `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/unit/test_webhook_rate_limiting.py backend-hormonia/tests/unit/middleware/test_rate_limiter.py backend-hormonia/tests/auth/test_csrf_middleware.py backend-hormonia/tests/api/v2/test_auth_password_recovery.py backend-hormonia/tests/integration/test_password_reset_migration_flow.py backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py backend-hormonia/tests/services/test_webhook_service_fail_closed.py backend-hormonia/tests/api/v2/test_patients_create.py backend-hormonia/tests/integration/test_duplicate_prevention.py` — exit 0, 169 passed in 7.72s, gsd_exec `9efe8dad-808b-46fe-8c62-633744214262`. These suites prove denied paths emit 403/409/422/429/503-class responses as appropriate before route/provider/queue/DB/saga side effects while legitimate fixture flows continue to pass. Operational readiness: health signal is the two-command pytest suite; failure signal is explicit denial status plus PHI-safe structured diagnostics with reason, route/method, request/correlation IDs, event type where applicable, and hashed/redacted client identity; recovery procedure is to inspect the failing ingress domain configuration/infrastructure (trusted proxy and Redis for rate limits, CSRF cookie/header token contract, reset-token cache SET NX support, webhook HMAC/timestamp/idempotency store, or duplicate validation/DB uniqueness) and rerun the focused file; monitoring gaps are production-like live providers, real PHI/data, and deployment telemetry, which remain out of scope for S01 and are deferred to later M014/M015 proof.

## Requirements Advanced

- R012 — Closed the S01-owned controlled backend proof subset for CSRF, password-reset replay, webhook replay/idempotency, duplicate oracle, and X-Forwarded-For/rate-limit hardening.
- R013 — Provided deterministic evidence for the X-Forwarded-For/rate-limit proof gap and additional replay/oracle ingress proof for the final M014 matrix.
- R015 — All proof used controlled pytest fixtures and no production exploitation or real patient data.
- R017 — Diagnostics and proof artifacts were kept PHI/secret-safe and did not depend on treating local git-ignored files as committed secrets.
- R018 — S01 produced explicit evidence for its R012/R013-relevant rows so final M014 closure can avoid silently dropping medium/proof-gap items.

## Requirements Validated

- R012 — S01-owned ingress subset validated by closeout `gsd_exec` proof: 39 focused security tests and 169 supporting regression tests passed.
- R013 — XFF/rate-limit proof gap validated by focused and supporting rate-limit tests included in the closeout command suite.
- R015 — UAT and verification commands are controlled local pytest suites with mocked/fixture providers and no production or real PHI dependency.

## New Requirements Surfaced

- None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

S01 included small supporting fixes beyond the original file list: settings for trusted-proxy/fail-closed behavior, test cache doubles with SET NX semantics, null Redis helper support, endpoint reset failure diagnostics, domain conflict-code preservation, DB circuit-breaker exclusion for expected validation/API denials, and a real-DB duplicate integration fixture correction. These were required to make the planned fail-closed contracts reproducible.

## Known Limitations

Closeout pytest stderr still includes an existing pytest-asyncio deprecation warning about `asyncio_default_fixture_loop_scope`; tests pass. S01 proof is deterministic backend pytest with mocks/fixtures, not a production-like live-provider or real-data harness.

## Follow-ups

S02 should consume the hardened ingress assumptions for ADK auth/session ownership. S03 should handle browser PHI cache and quiz persistence proof. S04 should handle upload stored-XSS/private artifact serving. S05 should place S01 command evidence and residual gaps into the M014 evidence matrix, including R012/R013/R018 row status.

## Files Created/Modified

- `backend-hormonia/app/utils/client_ip.py` — Added shared trusted-proxy-aware client identity and hashed/redacted identifier helpers.
- `backend-hormonia/app/utils/rate_limiter.py` — Fail-closed Redis/rate-limit handling and PHI-safe rate-limit diagnostics.
- `backend-hormonia/app/middleware/rate_limit_core.py` — Routed middleware identity and over-limit behavior through the shared fail-closed rate-limit boundary.
- `backend-hormonia/app/middleware/distributed_rate_limiter.py` — Honored trusted client identity and fail-closed acquisition behavior.
- `backend-hormonia/app/utils/request_context.py` — Aligned request audit context with the shared trusted-proxy client identity helper.
- `backend-hormonia/app/config/settings/security.py` — Added rate-limit fail-closed and trusted proxy settings.
- `backend-hormonia/app/config/settings/integrations.py` — Added WhatsApp/webhook trusted proxy and HMAC-related configuration support.
- `backend-hormonia/app/config/settings/__init__.py` — Exported/propagated new settings fields.
- `backend-hormonia/app/middleware/csrf.py` — Contracted CSRF exemptions and added PHI-safe CSRF denial diagnostics.
- `backend-hormonia/app/core/security.py` — Added reset-token claims verification for JTI/expiration replay control.
- `backend-hormonia/app/services/password_reset_service.py` — Consumed hashed reset JTIs atomically before password/session side effects and mapped replay/cache uncertainty to fail-closed errors.
- `backend-hormonia/app/api/v2/routers/auth.py` — Updated password recovery/reset endpoints and failure diagnostics for the hardened CSRF/replay contract.
- `backend-hormonia/app/core/redis_manager/utils.py` — Supported reset-token cache consumption semantics in null Redis helpers.
- `backend-hormonia/app/integrations/wuzapi/webhook.py` — Validated HMAC/timestamps/idempotency before processing WuzAPI webhook side effects.
- `backend-hormonia/app/integrations/whatsapp/security/hmac_validator.py` — Centralized webhook timestamp/signature validation behavior.
- `backend-hormonia/app/services/webhook_service.py` — Changed duplicate/idempotency-denied inbound webhooks from success-style duplicates to fail-closed HTTP errors.
- `backend-hormonia/app/services/webhook/idempotency.py` — Stopped fallback/idempotency infrastructure errors from acquiring events fail-open.
- `backend-hormonia/app/services/patient/validation_service.py` — Collapsed duplicate patient probes into generic conflict denials and PHI-safe logs.
- `backend-hormonia/app/services/patient/integrity_service.py` — Aligned duplicate detection normalization and denial behavior with the generic oracle-closed contract.
- `backend-hormonia/app/services/patient/sync_service.py` — Updated patient sync duplicate handling touched by the oracle-proof suite.
- `backend-hormonia/app/domain/patient/onboarding/validation_service.py` — Aligned onboarding validation duplicate errors with generic PHI-safe behavior.
- `backend-hormonia/app/api/v2/routers/patients/crud.py` — Mapped duplicate validation failures to generic 409 before patient saga/provider side effects.
- `backend-hormonia/app/core/exceptions.py` — Preserved domain-specific conflict detail codes while keeping HTTP conflict class generic.
- `backend-hormonia/app/utils/db_retry.py` — Excluded intentional domain/API validation denials from DB circuit-breaker failure counts.
- `backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py` — Added focused trusted-proxy and fail-closed rate-limit proof.
- `backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py` — Added focused CSRF fail-closed and side-effect sentinel proof.
- `backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py` — Added focused reset replay/cache uncertainty/no-mutation proof.
- `backend-hormonia/tests/security/test_m014_s01_webhook_replay.py` — Added focused WuzAPI/generic webhook replay/idempotency proof.
- `backend-hormonia/tests/security/test_m014_s01_duplicate_oracle.py` — Added focused duplicate-oracle closure and PHI-safe diagnostic proof.
