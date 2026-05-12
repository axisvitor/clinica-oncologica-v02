---
id: S02
parent: M013
milestone: M013
provides:
  - Shared admin-or-assigned-doctor patient ownership helper and denial diagnostics for downstream slices.
  - Two-doctor/two-patient negative authorization fixtures and tests for reuse by S03 and S05.
  - Ownership-check pattern for resource IDs resolving through patient ownership before data access or mutation.
  - Passing focused regression evidence for R003 and R009.
requires:
  []
affects:
  - S03: Quiz Link/Session Boundary can reuse the helper and two-doctor fixture pattern.
  - S05: Report Ownership Closure can reuse the resource-to-patient ownership and negative fixture pattern.
  - S06: Integrated Security Proof consumes S02's R003/R009 proof and diagnostic evidence.
key_files:
  - backend-hormonia/app/api/v2/patients_shared_helpers.py
  - backend-hormonia/app/utils/auth_helpers.py
  - backend-hormonia/app/models/patient.py
  - backend-hormonia/app/api/v2/routers/messages.py
  - backend-hormonia/app/api/v2/routers/patients/flow_responses.py
  - backend-hormonia/app/api/v2/routers/patients/flow_overrides.py
  - backend-hormonia/tests/unit/api/v2/test_patient_access_helpers.py
  - backend-hormonia/tests/api/v2/security_boundary_helpers.py
  - backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py
  - backend-hormonia/tests/api/v2/test_messages.py
  - backend-hormonia/tests/api/v2/test_patients_rbac_impl.py
  - backend-hormonia/tests/api/v2/test_phase25_messages_quiz_async.py
  - tests/unit/api/v2/test_patient_access_helpers.py
key_decisions:
  - Centralize patient ownership enforcement in `patients_shared_helpers.py` with fail-closed admin-or-assigned-doctor semantics and PHI-free ID/reason-only denial diagnostics.
  - Read patient-bound caches only after DB ownership succeeds and scope cache keys by non-PHI actor role/id so cached foreign payloads cannot be replayed across doctors.
  - Authorize all bulk-send patient IDs in one bounded query before accepting the request or scheduling/cache side effects.
  - Eager-load message patients and authorize before direct message mutation/status validation.
  - Use shared auth utilities for flow override PUT audit attribution so dict-backed sessions and `User` models behave consistently and malformed actors fail closed.
  - Keep production ownership semantics unchanged when the combined suite surfaced a fixture count issue; isolate the RBAC fixture with unique data and a scoped search instead.
patterns_established:
  - Reusable `load_patient_with_access` helper for S03/S05 patient-bound authorization.
  - Reusable two-doctor/two-patient negative authorization fixture pattern in focused API boundary tests.
  - Patient-bound cache sequencing pattern: authorize first, then read/invalidate actor-scoped cache keys; cache failures remain non-authorizing diagnostics.
  - Generic closed-denial pattern with structured diagnostics that exclude message content, response text, patient names, phones, tokens, and secrets.
observability_surfaces:
  - Patient ownership denial diagnostics containing actor id, actor role, patient/resource id, and reason only.
  - Non-critical cache failure diagnostics that do not bypass ownership checks or include PHI.
  - Focused tests asserting PHI-free denial/log behavior for helper and flow-response paths.
drill_down_paths:
  - .gsd/milestones/M013/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M013/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M013/slices/S02/tasks/T03-SUMMARY.md
  - .gsd/milestones/M013/slices/S02/tasks/T04-SUMMARY.md
  - .gsd/milestones/M013/slices/S02/tasks/T05-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-05-12T19:54:03.630Z
blocker_discovered: false
---

# S02: Patient Ownership Boundary

**Established a reusable admin-or-assigned-doctor patient ownership boundary across messages, flow responses, and flow override schedules so foreign doctors fail closed while assigned-doctor and admin flows continue to pass.**

## What Happened

S02 introduced and propagated a shared patient access pattern for patient-bound API surfaces. T01 added `load_patient_with_access`/related helper behavior that accepts admins or the assigned doctor, rejects malformed or unauthorized actors, returns generic 403/404 responses, and logs only actor/resource IDs plus reason. T02 scoped message reads, lists, conversation summaries/history, unread counts, stats, and patient-bound cache reads so ownership succeeds before patient data or cached payloads can be returned; global doctor views now use SQL-level ownership joins while admin-all behavior remains intact. T03 extended the same boundary to message mutations and read-state changes: single sends, bulk sends, direct mark-read, pending-message deletes/cancels, and conversation mark-read all authorize the patient or message's patient before side effects, scheduler/cache activity, or state mutation. T04 protected patient flow responses and flow override GET/PUT routes by loading the patient through the shared boundary before response/override queries or active-flow-state lookup, and made override audit attribution UUID-safe for dict-backed and model session users. T05 closed integration by fixing the RBAC regression fixture to be isolated under combined focused suites, rerunning the full S02 proof, and auditing focused tests/diagnostics for planning-artifact references and PHI-free denial behavior. The closeout verifier also reran the full planned backend command after the external auto gate omitted the required `cd backend-hormonia` working directory; the corrected slice-plan command passed.

## Verification

Fresh closeout verification ran through `gsd_exec` from the repository root with the slice-plan working directory: `cd backend-hormonia && pytest tests/unit/api/v2/test_patient_access_helpers.py tests/api/v2/test_patient_ownership_boundary.py tests/api/v2/test_messages.py tests/api/v2/test_patients_rbac_impl.py tests/api/v2/test_phase25_messages_quiz_async.py -q` (exec `c5edd54e-b8d9-45e0-9cf6-dbd795db0864`, exit 0, ~29.9s). Output reached 100% with one expected skip in `tests/api/v2/test_messages.py:80` because rate limiting is disabled in the test environment; stderr contained only the existing pytest-asyncio loop-scope deprecation warning. Task-level evidence also covered helper unit tests, message read/conversation gates, message mutation/read-state/bulk/send gates, flow response/override boundary tests, the adjusted admin RBAC case, no `.gsd`/`.planning`/`.audits` references in focused tests, and PHI-free deny diagnostic assertions.

## Requirements Advanced

- R010 — Created a reusable two-doctor/two-patient negative authorization fixture pattern and focused boundary suite covering messages, flow responses, and flow overrides.
- R011 — Implemented and verified closed denial diagnostics with actor/resource IDs and reason only, plus tests/audits showing message content, response text, patient names/phones, tokens, and secrets are not emitted.

## Requirements Validated

- R003 — Message read/list/conversation/unread/read-state/send/bulk-send/delete/cancel routes are covered by the full S02 pytest proof and focused boundary tests; closeout `gsd_exec` exited 0.
- R009 — Flow response and flow override GET/PUT routes are gated by `load_patient_with_access` and covered by the full S02 pytest proof plus focused ownership boundary tests; closeout `gsd_exec` exited 0.

## New Requirements Surfaced

- None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

A root-cwd compatibility wrapper was added for the helper unit gate during task execution because an external auto gate invoked a root-level test path. No production scope deviation occurred. Closeout verification used the planned `cd backend-hormonia` command because the latest external auto gate omitted that required working directory and failed before collection.

## Known Limitations

The backend suite still emits the existing pytest-asyncio `asyncio_default_fixture_loop_scope` deprecation warning. One existing `test_messages.py` rate-limit test is skipped when rate limiting is disabled in the test environment. Runtime server/manual UAT and downstream quiz/report/file hardening remain out of scope for S02.

## Follow-ups

S03 should reuse the two-doctor/two-patient fixture and shared ownership helper for quiz link/session authorization. S05 should reuse the resource-to-patient/generated_by ownership pattern for reports. A future maintenance task can set `asyncio_default_fixture_loop_scope` explicitly to remove the pytest-asyncio warning.

## Files Created/Modified

- `backend-hormonia/app/api/v2/patients_shared_helpers.py` — Added reusable admin-or-assigned-doctor patient access helper and PHI-free denial diagnostics.
- `backend-hormonia/app/utils/auth_helpers.py` — Added/shared actor role and UUID resolution utilities used by ownership and audit attribution paths.
- `backend-hormonia/app/models/patient.py` — Supported assigned-doctor ownership checks used by the shared helper.
- `backend-hormonia/app/api/v2/routers/messages.py` — Gated message reads, lists, conversations, stats/unread, sends, bulk sends, read-state mutations, deletes/cancels, and cache access/invalidation by patient ownership.
- `backend-hormonia/app/api/v2/routers/patients/flow_responses.py` — Loaded patient through the shared access helper before patient flow response queries.
- `backend-hormonia/app/api/v2/routers/patients/flow_overrides.py` — Loaded patient through the shared access helper before override GET/PUT work and used UUID-safe actor attribution.
- `backend-hormonia/tests/unit/api/v2/test_patient_access_helpers.py` — Covered helper allow/deny/fail-closed/PHI-free diagnostic behavior.
- `backend-hormonia/tests/api/v2/security_boundary_helpers.py` — Added reusable two-doctor/two-patient API boundary fixture support.
- `backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py` — Added focused cross-doctor denial and assigned/admin positive tests for messages, flow responses, and flow overrides.
- `backend-hormonia/tests/api/v2/test_messages.py` — Aligned message regression fixtures with enforced ownership and covered existing message flows.
- `backend-hormonia/tests/api/v2/test_patients_rbac_impl.py` — Made admin RBAC count assertion fixture-isolated with unique data/scoped search for combined suites.
- `backend-hormonia/tests/api/v2/test_phase25_messages_quiz_async.py` — Included in regression proof to ensure quiz-adjacent message flows remained passing.
- `tests/unit/api/v2/test_patient_access_helpers.py` — Root-cwd compatibility wrapper for the helper unit gate.
