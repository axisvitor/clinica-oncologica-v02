---
id: T05
parent: S04
milestone: M015
key_files:
  - scripts/security/verify-m015-runtime-security.sh
  - scripts/security/m015-runtime/artifact_seam.py
  - scripts/security/m015-runtime/README.md
  - backend-hormonia/alembic/versions/m015_s04_upload_runtime_contract.py
  - backend-hormonia/app/dependencies/auth_user_adapter.py
  - backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py
  - backend-hormonia/docs/reports/security/m015/artifact-seam-evidence.json
  - backend-hormonia/docs/reports/security/m015/artifact-seam-summary.md
key_decisions:
  - Fix the missing upload table/model alignment with an Alembic migration instead of seeding test-only DDL in the probe.
  - Use real CSRF double-submit material for upload POSTs rather than bypassing middleware.
  - Require safe attachment headers on gated/download routes, but do not impose attachment semantics on intentionally public static `/uploads` serving.
duration: 
verification_result: passed
completed_at: 2026-05-14T17:26:23.170Z
blocker_discovered: false
---

# T05: Ran the artifact seam end to end through Docker and persisted fresh redaction-safe evidence.

**Ran the artifact seam end to end through Docker and persisted fresh redaction-safe evidence.**

## What Happened

Wired the artifact seam runner branch to execute the real `artifact-probe` service and reran the full layered T05 gate. The first runtime attempts exposed real app-route issues rather than harness-only problems: upload POST required double-submit CSRF, the Alembic head did not align the legacy `uploads` table with the `Upload` model, cached session user IDs were string values that failed UUID owner comparison, and the probe was over-strictly applying attachment-header requirements to public static assets. Fixed each root cause by adding real CSRF handling to the probe, adding an idempotent `m015_s04_upload_runtime_contract` migration, normalizing session `User.id` values to UUIDs in the auth adapter, and scoping safe attachment header requirements to gated/private/report attachment routes. The final run produced redaction-validated artifact seam evidence and summary with clean Compose teardown.

## Verification

Fresh verification passed: shell syntax, Compose config, 103 scoped static/regression tests, Docker artifact seam runtime probe, and post-teardown container/port cleanup. Final correlation ID: `m015-20260514T172059Z-2091501`; durable evidence records `result: passed`, redaction `validated: true`, and teardown `complete`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -m py_compile scripts/security/m015-runtime/artifact_seam.py backend-hormonia/app/dependencies/auth_user_adapter.py backend-hormonia/alembic/versions/m015_s04_upload_runtime_contract.py && cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_s04_artifact_runtime_contract.py tests/security/test_m015_runtime_harness.py -q` | 0 | ✅ pass | 24200ms |
| 2 | `bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && PYTHONPATH=backend-hormonia:scripts/security/m015-runtime pytest scripts/security/m015-runtime/tests/test_runner_contract.py backend-hormonia/tests/security/test_m015_runtime_harness.py backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py backend-hormonia/tests/api/v2/test_private_upload_serving.py backend-hormonia/tests/api/v2/test_report_ownership_closure.py backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py -q && ./scripts/security/verify-m015-runtime-security.sh --seam artifact && (docker ps --format '{{.Names}} {{.Ports}}' | grep -E 'm015-runtime|18080|15432' && exit 1 || true)` | 0 | ✅ pass | 155500ms |

## Deviations

Added a runtime schema migration and auth adapter UUID normalization because the Docker proof exposed production-path failures not anticipated in the original probe-only plan. Relaxed public static header assertion while keeping safe attachment headers mandatory for gated/download attachment routes.

## Known Issues

Upload quota still logs a non-fatal AsyncSession/query mismatch during upload quota lookup; the route catches it and continues, and it did not block the S04 security proof.

## Files Created/Modified

- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/artifact_seam.py`
- `scripts/security/m015-runtime/README.md`
- `backend-hormonia/alembic/versions/m015_s04_upload_runtime_contract.py`
- `backend-hormonia/app/dependencies/auth_user_adapter.py`
- `backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py`
- `backend-hormonia/docs/reports/security/m015/artifact-seam-evidence.json`
- `backend-hormonia/docs/reports/security/m015/artifact-seam-summary.md`
