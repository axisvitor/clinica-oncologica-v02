---
id: S03
parent: M013
milestone: M013
provides:
  - S03 → S06: focused proof artifacts for quiz token/session invariants and denial diagnostics.
  - S03 → downstream quiz work: shared public quiz validation/state seam and signed compatibility session-state contract.
  - Validated R004/R005 evidence for authenticated quiz ownership and public quiz opaque session/link enforcement.
requires:
  - slice: S02
    provides: Shared admin-or-assigned-doctor patient ownership helper and two-doctor/two-patient negative fixture pattern.
affects:
  - S06 Integrated Security Proof consumes S03 evidence.
  - S04/S05 remain independent downstream remediation for uploads/reports.
key_files:
  - backend-hormonia/app/api/v2/routers/monthly_quiz_operations/crud.py
  - backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py
  - backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public_security.py
  - backend-hormonia/app/domain/quizzes/session/token_manager.py
  - backend-hormonia/app/config/settings.py
  - backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py
  - backend-hormonia/tests/api/v2/test_monthly_quiz_compatibility.py
  - backend-hormonia/tests/api/v2/test_quiz_extensions.py
  - backend-hormonia/tests/api/v2/test_phase25_messages_quiz_async.py
  - backend-hormonia/tests/api/v2/security_boundary_helpers.py
  - backend-hormonia/app/api/v2/patients_shared_helpers.py
key_decisions:
  - Use `load_patient_with_access` as the shared admin-or-assigned-doctor gate before authenticated quiz session/token side effects.
  - Make persisted QuizSession metadata authoritative for public quiz access and submit: token_hash, link_status, patient/template/session binding, and effective expiration must all match.
  - Use signed HttpOnly `quiz_session_state` as the compatibility authorization proof; retain legacy `quiz_session_id` only as a compatibility hint that must match signed state when present.
  - Token/quiz denial diagnostics are generic and reason/resource-ID based; token material, token prefixes, PHI, quiz answers, cookies, and secrets are excluded.
patterns_established:
  - Authenticated quiz endpoints accepting `patient_id` gate through shared patient ownership before any side effect.
  - Public quiz routes share one validator that loads persisted session state and rejects mismatches before payload reads or response writes.
  - Compatibility cookies use a dual-cookie contract where signed state is authoritative and raw session ID is never sufficient.
  - Denial logging is best-effort and must not alter fail-closed authorization behavior.
observability_surfaces:
  - Safe public quiz denial logs with reason plus non-PHI resource IDs only.
  - Generic TokenManager invalid/expired token warnings that omit exception details and token-derived diagnostics.
  - Focused caplog/response assertions proving denial diagnostics exclude PHI, token material, raw cookies, signed state values, and quiz response text.
drill_down_paths:
  - .gsd/milestones/M013/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M013/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M013/slices/S03/tasks/T03-SUMMARY.md
  - .gsd/milestones/M013/slices/S03/tasks/T04-SUMMARY.md
  - .gsd/milestones/M013/slices/S03/tasks/T01-VERIFY.json
  - .gsd/milestones/M013/slices/S03/tasks/T02-VERIFY.json
  - .gsd/milestones/M013/slices/S03/tasks/T03-VERIFY.json
  - .gsd/milestones/M013/slices/S03/tasks/T04-VERIFY.json
duration: ""
verification_result: passed
completed_at: 2026-05-12T23:36:00.284Z
blocker_discovered: false
---

# S03: Quiz Link/Session Boundary

**Monthly quiz authenticated and public boundaries now fail closed for foreign ownership, forged/expired/mismatched tokens, inactive link state, raw-cookie-only sessions, and unsafe diagnostics while the legitimate fixture quiz still completes.**

## What Happened

S03 closes the quiz link/session boundary for the critical/high M013 security remediation track. T01 verified the authenticated side: quiz link creation, patient status/history, and active-link reads load the target patient through the shared admin-or-assigned-doctor ownership gate before session/token side effects, and doctor active-link queries are scoped in SQL through Patient ownership before patient names can be serialized. T02 introduced the public quiz link validation seam: JWTs are decoded through TokenManager, required claims are checked, the persisted QuizSession is loaded by token session_id, patient/template/path/session claims must match, stored token_hash and active link metadata are authoritative, terminal/cancelled/used state is rejected, and the effective expiration is the earliest of token/session/link metadata before any payload read or response write. T03 completed the compatibility boundary by issuing a signed HttpOnly quiz_session_state cookie from /access, keeping legacy quiz_session_id only as a compatibility hint, and requiring signed state for /session/active, submit, and mutating logout paths; raw-only, forged, and mismatched states fail closed. T04 sanitized token/session diagnostics so invalid quiz attempts produce generic denials and safe reason/resource IDs without PHI, raw tokens, token prefixes, quiz response text, secrets, or cookie state values. The full planned regression suite exposed legacy local Postgres schema drift in quiz extension tests; that was resolved with a test-only transactional schema alignment fixture so the proof can run without weakening production validation. During closeout, stale VERIFY.json task artifacts from an earlier failed runner attempt were repaired to match the already-passed task summaries and current evidence; no backend source changes were needed in the closer.

## Verification

All task records are complete and current artifact integrity passed. Full slice proof evidence: gsd_exec 18d02e9e-58cb-4c2a-9066-34755af826ef ran `cd backend-hormonia && pytest tests/api/v2/test_quiz_link_session_boundary.py tests/api/v2/test_monthly_quiz_compatibility.py tests/api/v2/test_quiz_extensions.py tests/api/v2/test_phase25_messages_quiz_async.py -q && python - <<'PY' ... planning artifact audit ... PY` with exit code 0 in 34952ms; output reached 100% and printed `S03 planning artifact audit passed`. Supporting task evidence: T01 focused authenticated ownership selection exit 0; T02 public token/link-state selection plus full boundary file exit 0; T03 compatibility/session-state/raw/forged/logout selection exit 0; T04 denial diagnostics, quiz extensions regression, full planned proof, and static token diagnostic marker audit exit 0. Closeout artifact checks also passed: gsd_exec 4a2d0928-40d2-4a7b-b870-877b5171bdd7 confirmed all 4 task summaries and 4 VERIFY.json files are present, non-empty, passed=true, and have only passing checks; gsd_exec ac5c7c9f-3a19-476f-a5e1-8369bc6c798f confirmed T01-T04 summary frontmatter records `verification_result: passed`.

## Requirements Advanced

- R010 — Added reusable two-doctor/two-patient negative authorization tests for quiz ownership and public session boundaries.
- R011 — Added fail-closed invalid quiz diagnostics that preserve safe reason/resource identifiers without PHI, tokens, or secrets.

## Requirements Validated

- R004 — Authenticated quiz link creation, status/history, and active-link listing enforce admin-or-assigned-doctor patient ownership under focused and full pytest proof.
- R005 — Public quiz current/access/submit/session/logout routes reject foreign, expired, forged, cancelled/used, token-hash mismatched, patient/template/session mismatched, and raw-cookie-only states while a legitimate fixture quiz completes under focused and full pytest proof.

## New Requirements Surfaced

- None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

The planned full S03 proof initially surfaced legacy local Postgres schema drift in `test_quiz_extensions.py`; a test-only transactional schema alignment fixture was added so the regression suite can run locally. During closeout, stale failed VERIFY.json artifacts from a prior runner attempt were repaired from the passed task summaries and current evidence.

## Known Limitations

Existing pytest-asyncio deprecation warning about unset `asyncio_default_fixture_loop_scope` remains non-blocking. S03 does not cover private upload/report serving or report ownership, which are assigned to S04/S05.

## Follow-ups

S04 should close private upload/report serving. S05 should close direct report ownership paths. S06 should consume S03 evidence in the final F-01..F-11 matrix and list remaining medium/proof-gap work.

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/crud.py` — Authenticated ownership gates and doctor-scoped active-link query behavior.
- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py` — Public current/access/submit/session/logout routes wired to validated token/session/state contracts.
- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public_security.py` — Shared persisted public quiz link/session validator and safe denial behavior.
- `backend-hormonia/app/domain/quizzes/session/token_manager.py` — Generic token verification diagnostics without token prefixes or exception-derived details.
- `backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py` — Negative/positive ownership, public token, token hash, state mismatch, expiration, and diagnostic tests.
- `backend-hormonia/tests/api/v2/test_monthly_quiz_compatibility.py` — Signed compatibility session-state, raw cookie, forged state, mismatch, and logout tests.
- `backend-hormonia/tests/api/v2/test_quiz_extensions.py` — Regression coverage and local Postgres test schema alignment fixture used by the full proof.
