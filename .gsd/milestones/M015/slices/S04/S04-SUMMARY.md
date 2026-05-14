---
id: S04
parent: M015
milestone: M015
provides:
  - A working `artifact` seam in `verify-m015-runtime-security.sh`.
  - Fresh artifact evidence and summary with correlation `m015-20260514T172743Z-2102411`.
  - Runtime upload schema migration and cached-session UUID normalization needed by artifact ownership routes.
requires:
  []
affects:
  - S05
key_files:
  - scripts/security/verify-m015-runtime-security.sh
  - scripts/security/m015-runtime/docker-compose.yml
  - scripts/security/m015-runtime/README.md
  - scripts/security/m015-runtime/artifact_seam.py
  - scripts/security/m015-runtime/redaction.py
  - backend-hormonia/alembic/versions/m015_s04_upload_runtime_contract.py
  - backend-hormonia/app/dependencies/auth_user_adapter.py
  - backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py
  - backend-hormonia/tests/security/test_m015_runtime_harness.py
  - scripts/security/m015-runtime/tests/test_runner_contract.py
  - backend-hormonia/docs/reports/security/m015/artifact-seam-evidence.json
  - backend-hormonia/docs/reports/security/m015/artifact-seam-summary.md
key_decisions:
  - Artifact upload POSTs use real CSRF double-submit material; no middleware bypasses or auth shortcuts are used.
  - Runtime upload schema gaps are fixed with Alembic migration `m015_s04_upload_runtime_contract`, not probe-local DDL.
  - Session user IDs are normalized to UUIDs in the auth adapter so owner checks compare canonical types.
  - Safe attachment headers are required for gated/download attachment routes; public `/uploads` static serving remains a public-static reachability proof and is not forced into attachment semantics.
patterns_established:
  - Runtime seam probes should fix app/schema/auth gaps surfaced by Docker proof, not seed probe-only state that hides failures.
  - Evidence records route outcomes as hashes/status classes/booleans and withholds raw cookies, session IDs, paths, bytes, IDs, DSNs, PHI, and raw download URL maps.
  - Header assertions distinguish gated attachment routes from intentionally public static assets.
observability_surfaces:
  - Artifact seam phase logs include correlation ID, seam, phase, status, failure class, evidence path, and teardown result.
  - Durable evidence records status classes, header booleans, body hashes, redaction booleans, non-goals, migration output tail, and teardown status without raw sensitive values.
  - Per-run diagnostics are stored under `scripts/security/m015-runtime/evidence/<correlation-id>/`; durable review artifacts live under `backend-hormonia/docs/reports/security/m015/`.
drill_down_paths:
  - .gsd/milestones/M015/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M015/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M015/slices/S04/tasks/T03-SUMMARY.md
  - .gsd/milestones/M015/slices/S04/tasks/T04-SUMMARY.md
  - .gsd/milestones/M015/slices/S04/tasks/T05-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-05-14T17:34:00.228Z
blocker_discovered: false
---

# S04: Private Artifact App-Route Runtime Proof

**S04 proves private upload/report/export artifact routes through the synthetic Docker runtime with real cookie sessions and redaction-safe evidence.**

## What Happened

S04 turned the artifact seam from a registered/fail-closed placeholder into a real Docker runtime proof. The probe creates synthetic staff sessions in PostgreSQL, obtains real CSRF tokens, uses cookie-backed FastAPI HTTP requests, uploads private and public files, validates private owner/admin downloads, checks anonymous/cross-owner/direct-static denial, seeds synthetic report/export fixtures, exercises base report/enhanced builder/enhanced export routes, withholds unsafe private/static download URLs, and writes redaction-validated evidence and a summary. Running the full Docker gate exposed real runtime gaps: the legacy `uploads` table did not match the model, and cached session users had string IDs that broke owner comparisons. Both were fixed in production code/migrations and covered with local contract tests. The final post-change gate passed with correlation `m015-20260514T172743Z-2102411`, 103 scoped tests, artifact seam runtime proof, redaction validation, and clean teardown.

## Verification

Fresh post-change slice gate passed: shell syntax, Compose config, 103 scoped static/regression tests, Docker artifact seam runtime proof, redaction validation, and post-teardown cleanup. Final output includes `phase=redaction status=ready artifact seam durable artifacts passed denylist validation without raw private artifact data` and `phase=teardown status=complete`; no M015 containers/ports remained.

## Requirements Advanced

- R014 — S04 adds private artifact upload/report/export runtime proof to the synthetic production-like harness; S05 still validates the final all-seam matrix.
- R015 — S04 maintains synthetic-only proof boundaries and evidence non-goals with no production systems, real PHI, live provider credentials, CDN/object-storage, or browser/frontend claims.
- R017 — S04 writes redaction-validated diagnostics/evidence for artifact runtime proof and explicitly omits raw sensitive values.
- R018 — S04 closes an additional runtime red signal instead of documenting it away: missing upload schema alignment and UUID owner comparison were fixed before green evidence.

## Requirements Validated

None.

## New Requirements Surfaced

- Non-fatal upload quota AsyncSession/query warning may need final S05 policy treatment if runtime warnings are considered closure-blocking.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

S04 uncovered and fixed two runtime app gaps outside the original probe-only implementation plan: missing Alembic alignment for the legacy `uploads` table and string-vs-UUID session user IDs during owner comparison. The probe also added real CSRF double-submit handling and narrowed attachment-header enforcement to gated/download attachment routes while leaving intentionally public static assets as static assets.

## Known Limitations

S04 intentionally does not prove CDN/object storage, browser/frontend rendering, live providers, production data, broad DAST/fuzzing, or final all-seam matrix closure. Upload quota lookup still emits a non-fatal AsyncSession/query warning in runtime logs; route behavior and security proof pass.

## Follow-ups

S05 must fold S04 evidence into the unified M015 evidence matrix, keep the synthetic-only/non-goal boundaries explicit, and decide whether to separately address the non-fatal upload quota AsyncSession/query log if the final matrix treats runtime warnings as red signals.

## Files Created/Modified

- `scripts/security/verify-m015-runtime-security.sh` — Registered and executed the artifact seam branch through Docker Compose with evidence/summary collection and teardown.
- `scripts/security/m015-runtime/docker-compose.yml` — Added the artifact probe service and mounted runtime helper.
- `scripts/security/m015-runtime/README.md` — Documented the implemented artifact seam, command usage, evidence contract, and non-goals.
- `scripts/security/m015-runtime/artifact_seam.py` — Implemented real HTTP artifact upload/report/export runtime probe with cookie sessions, CSRF, ownership assertions, safe-header checks, redaction-safe evidence, and summary writing.
- `scripts/security/m015-runtime/redaction.py` — Extended denylist checks for private artifact paths, raw download URL mappings, and raw upload/report bytes.
- `backend-hormonia/alembic/versions/m015_s04_upload_runtime_contract.py` — Aligned the runtime `uploads` table with the `Upload` model for real upload route persistence.
- `backend-hormonia/app/dependencies/auth_user_adapter.py` — Normalized session user IDs to UUIDs so cached session users compare correctly with persisted upload owners.
- `backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py` — Covered artifact probe contracts, redaction behavior, public-static vs gated-download header expectations, and UUID owner comparison.
- `backend-hormonia/tests/security/test_m015_runtime_harness.py` — Updated runner/static harness tests for artifact seam execution and evidence contracts.
- `scripts/security/m015-runtime/tests/test_runner_contract.py` — Updated runner contract tests for real artifact probe dispatch.
- `backend-hormonia/docs/reports/security/m015/artifact-seam-evidence.json` — Fresh redaction-validated artifact seam evidence.
- `backend-hormonia/docs/reports/security/m015/artifact-seam-summary.md` — Fresh artifact seam summary.
