---
id: M015
title: "Runtime Security Validation"
status: complete
completed_at: 2026-05-14T18:24:19.761Z
key_decisions:
  - Synthetic-only Docker runtime harness is the authoritative proof path for M015.
  - No-filter runner delegates to child scoped seam runs in deterministic order (`db`, `session`, `provider`, `artifact`) to preserve mature setup/teardown behavior.
  - Final evidence matrix is executable policy: required rows and validator failure classes block false green milestone closure.
  - Runtime red signals are fixed or classified before close, not documented away as green.
key_files:
  - scripts/security/verify-m015-runtime-security.sh
  - scripts/security/m015-runtime/docker-compose.yml
  - scripts/security/m015-runtime/evidence_matrix.py
  - scripts/security/m015-runtime/db_seam.py
  - scripts/security/m015-runtime/m015_session_security_taskiq.py
  - scripts/security/m015-runtime/provider_seam.py
  - scripts/security/m015-runtime/artifact_seam.py
  - scripts/security/m015-runtime/redaction.py
  - backend-hormonia/alembic/versions/m015_s04_upload_runtime_contract.py
  - backend-hormonia/app/dependencies/auth_user_adapter.py
  - backend-hormonia/docs/reports/security/m015/db-seam-evidence.json
  - backend-hormonia/docs/reports/security/m015/session-seam-evidence.json
  - backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json
  - backend-hormonia/docs/reports/security/m015/artifact-seam-evidence.json
  - backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.json
  - backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.md
  - backend-hormonia/tests/security/test_m015_final_matrix_contract.py
  - backend-hormonia/tests/security/test_m015_runtime_harness.py
  - backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py
  - scripts/security/m015-runtime/tests/test_runner_contract.py
lessons_learned:
  - Runtime proof exposed real schema/auth issues that in-process tests did not catch; Docker seams should be trusted over shortcuts for closure.
  - Redaction validators need stable failure classes and finding names, otherwise failures are safe but slow to diagnose.
  - Final matrix rows should be machine-addressable IDs, not prose-only claims.
---

# M015: Runtime Security Validation

**M015 closes the deferred runtime security proof with a synthetic all-seam Docker runner and strict validated evidence matrix.**

## What Happened

M015 built and validated a synthetic-only, production-like runtime security harness for deferred M014 gaps. S01 established the Docker runtime substrate with TLS PostgreSQL, Dragonfly, FastAPI readiness, migrations, RLS, evidence, and teardown. S02 proved cookie-backed session behavior across API/cache/DB/Taskiq worker boundaries. S03 proved network-real WuzAPI/Gemini provider boundaries against local stubs with worker participation and redacted observations. S04 proved private upload/report/export artifact app routes with real HTTP and cookie sessions, fixing upload schema and UUID owner-comparison red signals found by the runtime proof. S05 assembled the final no-filter all-seam runner and strict evidence matrix validator. The final closeout command passed with parent correlation `m015-20260514T181125Z-2167622`; child seams `-db`, `-session`, `-provider`, and `-artifact` all completed, matrix validation passed, and cleanup left no M015 containers or bound ports.

## Success Criteria Results

- ✅ Single committed M015 runner starts synthetic backend stack, runs runtime checks, captures evidence, and tears down.
- ✅ DB/session/provider/artifact seams were exercised through real process/network/runtime boundaries.
- ✅ Final matrix maps deferred runtime items and requirements to evidence/fixed outcome/non-goals and rejects false greens.
- ✅ No live provider credentials, production systems, real PHI, browser/frontend, CDN/object-storage, broad DAST, or exploitation claims introduced.
- ✅ Runtime red signals found during M015 were fixed or classified before closure.

## Definition of Done Results

- ✅ All slices S01-S05 complete.
- ✅ Final no-filter runner executed all seams and exited 0.
- ✅ Final matrix JSON/MD generated and validated.
- ✅ Redaction checks passed for seam evidence and matrix artifacts.
- ✅ No active M015 runtime containers or `18080`/`15432` bound ports remained after teardown.
- ✅ Requirement R014 updated to validated with final matrix evidence.

## Requirement Outcomes

- R012: Covered by prior M014 proof plus M015 DB TLS/RLS runtime row in the final matrix.
- R013: Validated by S02 session/cache/worker runtime evidence and S05 matrix rows.
- R014: Updated to `validated`; final no-filter all-seam run and matrix close the runtime harness requirement.
- R015: Anti-feature boundary honored with explicit non-goals and synthetic-only evidence.
- R017: Anti-feature boundary honored with redaction-safe evidence and matrix validation.
- R018: Anti-feature boundary honored by strict validator and classified warning policy, avoiding silent dropped findings.

## Deviations

M015 fixed additional runtime red signals discovered by the proof itself: S04 added upload schema alignment and cached-session UUID normalization; S05 added matrix generation/validation and session redaction-error finding diagnostics. These were necessary to avoid false green closure.

## Follow-ups

Review the classified `upload_quota_async_session_query_warning` in a future cleanup/security-hardening pass if runtime warnings are elevated to blocking policy. Otherwise, no M015 implementation slices remain.
