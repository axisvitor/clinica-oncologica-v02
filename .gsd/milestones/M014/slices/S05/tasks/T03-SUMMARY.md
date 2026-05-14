---
id: T03
parent: S05
milestone: M014
key_files:
  - backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md
  - .gsd/REQUIREMENTS.md
key_decisions:
  - R012/R013 are validated within M014's controlled-proof boundary; live JWT multi-worker runtime, live DB TLS/RLS enforcement, production CDN/object-storage behavior, and production-like DB+queue+WuzAPI/Gemini harness remain explicitly deferred to R014/M015.
duration: 
verification_result: passed
completed_at: 2026-05-14T02:34:34.603Z
blocker_discovered: false
---

# T03: Ran integrated M014 regression closure and updated requirement validation evidence.

**Ran integrated M014 regression closure and updated requirement validation evidence.**

## What Happened

Ran the integrated M014 backend security suite covering S01-S05 security proof files, reran the dashboard React Query persistence command, and reran the quiz storage command. Updated the M014 evidence matrix closeout section with fresh T03 results and reran the matrix validator after the doc edit. Updated R012/R013 validation status and R018 validation notes through GSD tools to reflect controlled-proof closure and explicit R014/M015 runtime deferrals.

## Verification

Fresh closeout verification passed: backend integrated security suite exited 0 with 149 passed in 4.20s; frontend persistence command exited 0 with 5 passed; quiz storage command exited 0 with 8 passed; post-edit matrix validator exited 0 with 4 passed in 0.91s.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py backend-hormonia/tests/security/test_m014_s01_webhook_replay.py backend-hormonia/tests/security/test_m014_s01_duplicate_oracle.py backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py backend-hormonia/tests/security/test_m014_s03_cache_headers.py backend-hormonia/tests/security/test_m014_s04_active_content_validation.py backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py` | 0 | ✅ pass — 149 passed in 4.20s | 29600ms |
| 2 | `npm --prefix frontend-hormonia test -- tests/unit/react-query/persistencePolicy.test.ts` | 0 | ✅ pass — 1 file, 5 tests passed | 56200ms |
| 3 | `npm --prefix quiz-mensal-interface test -- tests/security/quiz-progress-storage.test.tsx tests/security/no-phi-local-storage.test.tsx` | 0 | ✅ pass — 2 suites, 8 tests passed | 92300ms |
| 4 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py` | 0 | ✅ pass — 4 passed in 0.91s | 23600ms |

## Deviations

Executed manually because headless S05 task dispatches were repeatedly crash-recovered without activity artifacts. The integrated backend command was run directly via async_bash rather than gsd_exec, so the matrix records fresh command output rather than new gsd_exec IDs for T03.

## Known Issues

Known non-fatal warnings remain: pytest-asyncio loop-scope deprecation, baseline-browser-mapping age warning, Node punycode deprecation, and Jest worker teardown warning in the quiz command. All commands exited 0.

## Files Created/Modified

- `backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md`
- `.gsd/REQUIREMENTS.md`
