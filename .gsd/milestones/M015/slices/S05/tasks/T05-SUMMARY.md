---
id: T05
parent: S05
milestone: M015
key_files:
  - scripts/security/verify-m015-runtime-security.sh
  - scripts/security/m015-runtime/evidence_matrix.py
  - scripts/security/m015-runtime/m015_session_security_taskiq.py
  - backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.json
  - backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.md
  - backend-hormonia/docs/reports/security/m015/db-seam-evidence.json
  - backend-hormonia/docs/reports/security/m015/session-seam-evidence.json
  - backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json
  - backend-hormonia/docs/reports/security/m015/artifact-seam-evidence.json
key_decisions:
  - All-seam closeout executes scoped seam child processes sequentially instead of refactoring shared in-process state, preserving each seam's existing teardown and diagnostics.
  - The matrix is generated and validated both inside the no-filter runner and again as an explicit post-run verification step.
  - Session probe unhandled RedactionError logs now include denylist finding names, improving future diagnosis without exposing sensitive values.
duration: 
verification_result: passed
completed_at: 2026-05-14T18:20:02.331Z
blocker_discovered: false
---

# T05: Ran final no-filter all-seam M015 closeout and persisted the validated evidence matrix.

**Ran final no-filter all-seam M015 closeout and persisted the validated evidence matrix.**

## What Happened

Ran the full S05 gate: shell syntax, Docker Compose config, 118 scoped static/regression tests, no-filter all-seam runner, matrix generation/validation, explicit matrix validation, and post-teardown container/port check. The no-filter runner executed DB, session, provider, and artifact child seams in order, each with child correlation IDs under parent correlation `m015-20260514T181125Z-2167622`. DB proved TLS/RLS/migrations/readiness; session proved cookie auth, cache fallback, revocation, explicit cache invalidation, and Taskiq worker DB re-check; provider proved WuzAPI/Gemini local stub boundaries and worker participation; artifact proved private upload/report/export app-route ownership, unsafe URL denial, safe headers, and redaction-safe evidence. The final matrix records all required runtime items and requirements R012/R013/R014/R015/R017/R018 with `result: passed`, validator `passed`, classified warnings, and non-goals.

## Verification

Fresh T05 gate passed: 118 scoped tests passed, all four Docker seams completed under parent correlation `m015-20260514T181125Z-2167622`, matrix validation printed `M015 evidence matrix validated: backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.json`, and post-teardown grep found no M015 containers or bound ports.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && PYTHONPATH=backend-hormonia:scripts/security/m015-runtime pytest scripts/security/m015-runtime/tests/test_runner_contract.py backend-hormonia/tests/security/test_m015_runtime_harness.py backend-hormonia/tests/security/test_m015_final_matrix_contract.py backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py backend-hormonia/tests/api/v2/test_private_upload_serving.py backend-hormonia/tests/api/v2/test_report_ownership_closure.py backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py -q && ./scripts/security/verify-m015-runtime-security.sh && python3 scripts/security/m015-runtime/evidence_matrix.py --input-dir backend-hormonia/docs/reports/security/m015 --output-dir backend-hormonia/docs/reports/security/m015 --validate && (docker ps --format '{{.Names}} {{.Ports}}' | grep -E 'm015-runtime|18080|15432' && exit 1 || true)` | 0 | ✅ pass | 491200ms |

## Deviations

A first all-seam attempt failed in the session child seam with a generic redaction error; a scoped rerun passed after adding finding-name diagnostics for future failures. The final all-seam rerun passed end to end.

## Known Issues

The matrix keeps `upload_quota_async_session_query_warning` classified as a known non-blocking runtime warning for milestone validation review; it did not block the security proof.

## Files Created/Modified

- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/evidence_matrix.py`
- `scripts/security/m015-runtime/m015_session_security_taskiq.py`
- `backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.json`
- `backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.md`
- `backend-hormonia/docs/reports/security/m015/db-seam-evidence.json`
- `backend-hormonia/docs/reports/security/m015/session-seam-evidence.json`
- `backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json`
- `backend-hormonia/docs/reports/security/m015/artifact-seam-evidence.json`
