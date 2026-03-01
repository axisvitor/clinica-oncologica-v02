---
phase: 27-test-stability
verified: 2026-02-28T06:30:36Z
status: gaps_found
score: 2/4 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 1/4
  gaps_closed:
    - "`test_import_savepoints_preserve_valid_rows` now passes"
    - "`tests/api/critical/ -x -q` now completes with zero failures"
    - "`TODO(async-migration)` markers are absent from `backend-hormonia/app/`"
  gaps_remaining:
    - "Full suite still does not run cleanly"
    - "Fresh full-suite completion with final zero `MissingGreenlet`/`UndefinedColumn` evidence is not established"
    - "Plan 27-04 must-have (`grep -r 'TODO(async-migration)' .planning/` == 0) is not met"
  regressions:
    - "First failing test shifted from patient import savepoint path to API contract pagination count"
gaps:
  - truth: "Running `pytest` against the full test suite completes cleanly (no regressions)"
    status: failed
    reason: "Fresh verifier run stops on a regression assertion failure."
    artifacts:
      - path: "/tmp/phase27-fullsuite-x.txt"
        issue: "`tests/api/test_api_contracts.py::TestUserListAPIContract::test_user_list_returns_paginated_response` fails (`assert 30 == 26`)"
    missing:
      - "Fix the failing API contract test path so full-suite execution is clean"
      - "Re-run full suite to completion and record final pass/fail totals"
  - truth: "Plan 27-04 must-have `grep -r 'TODO(async-migration)' .planning/` returns zero results"
    status: failed
    reason: "`.planning/` still contains many literal matches in phase artifacts and milestone docs."
    artifacts:
      - path: ".planning/phases/27-test-stability/27-04-PLAN.md"
        issue: "Contains multiple literal `TODO(async-migration)` references"
      - path: ".planning/STATE.md"
        issue: "Contains literal `TODO(async-migration)` reference"
    missing:
      - "Either remove remaining literal tokens from `.planning/` or narrow the must-have scope to runtime app code only"
      - "Align TEST-03 wording across plans/requirements to eliminate scope ambiguity"
---

# Phase 27: Test Stability Verification Report

**Phase Goal:** The full test suite runs cleanly — fixtures correctly override with `get_async_db`, no `MissingGreenlet` or `UndefinedColumn` errors appear, and all async-migration TODO annotations are removed from app/ code.
**Verified:** 2026-02-28T06:30:36Z
**Status:** gaps_found
**Re-verification:** Yes — after gap-closure plans 27-03 and 27-04

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Test client fixtures override `get_async_db` and provide async-compatible DB session objects | ✓ VERIFIED | `backend-hormonia/tests/conftest.py:1134` defines `_override_get_async_db`, `backend-hormonia/tests/conftest.py:1137` wires `app.dependency_overrides[get_async_db]` |
| 2 | Full `pytest` suite completes with zero `MissingGreenlet` and zero `UndefinedColumn` errors | ✗ FAILED | Fresh `python3 -m pytest tests/ -x -q --tb=short` run stops at first regression (`/tmp/phase27-fullsuite-x.txt:44`), so full-suite completion is not established |
| 3 | Async-migration TODO annotations are removed from `app/` code | ✓ VERIFIED | `grep` scan for `TODO(async-migration)` in `backend-hormonia/app/**/*.py` returns no matches |
| 4 | No previously passing tests regress; suite is clean | ✗ FAILED | `/tmp/phase27-fullsuite-x.txt:8` shows first-failure regression in `TestUserListAPIContract::test_user_list_returns_paginated_response` (`/tmp/phase27-fullsuite-x.txt:11`) |

**Score:** 2/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `backend-hormonia/tests/conftest.py` | Root `SyncToAsyncSessionAdapter` with awaitable `begin_nested()` and `get_async_db` override wiring | ✓ VERIFIED | Exists, substantive adapter implementation, wired at `backend-hormonia/tests/conftest.py:1137` |
| `backend-hormonia/tests/api/critical/conftest.py` | Critical-suite adapter parity with awaitable `begin_nested()` | ✓ VERIFIED | Exists, substantive `begin_nested()` proxy at `backend-hormonia/tests/api/critical/conftest.py:925` |
| `backend-hormonia/tests/test_phase27_async_regression.py` | Regression locks for TEST-01/02/03 | ✓ VERIFIED | Exists and passes: `python3 -m pytest tests/test_phase27_async_regression.py -q` -> `5 passed` |
| `.planning/ROADMAP.md` | Phase 27 wording avoids literal `TODO(async-migration)` token while preserving intent | ✓ VERIFIED | No literal token matches in `.planning/ROADMAP.md`; app/ scope wording present at `.planning/ROADMAP.md:180` and `.planning/ROADMAP.md:186` |
| `.planning/` grep literal-token must-have (Plan 27-04) | Zero matches for `TODO(async-migration)` in planning docs | ✗ FAILED | Literal token still appears across `.planning/` (e.g., `.planning/STATE.md:145`, `.planning/phases/27-test-stability/27-04-PLAN.md:25`) |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `backend-hormonia/tests/conftest.py` | `app.dependency_overrides[get_async_db]` | `_override_get_async_db` yields `SyncToAsyncSessionAdapter(db_session)` | WIRED | Defined at `backend-hormonia/tests/conftest.py:1134` and wired at `backend-hormonia/tests/conftest.py:1137` |
| `backend-hormonia/tests/api/critical/conftest.py` | `app/api/v2/routers/patients/import_export.py` | awaitable `begin_nested()` savepoint path | WIRED | Adapter defines `begin_nested()` at `backend-hormonia/tests/api/critical/conftest.py:925`; endpoint awaits `db.begin_nested()` at `backend-hormonia/app/api/v2/routers/patients/import_export.py:935` |
| `backend-hormonia/app/api/v2/routers/localization.py` | `backend-hormonia/app/api/v2/auth_session_shared.py` | `await get_user_data_from_session(..., db=AsyncSession, ...)` | WIRED | Import at `backend-hormonia/app/api/v2/routers/localization.py:33`; awaited call at `backend-hormonia/app/api/v2/routers/localization.py:98` |
| `backend-hormonia/app/api/v2/routers/tasks/dependencies.py` | `backend-hormonia/app/api/v2/auth_session_shared.py` | `await get_user_data_from_session(..., db=AsyncSession, ...)` | WIRED | Import at `backend-hormonia/app/api/v2/routers/tasks/dependencies.py:15`; awaited call at `backend-hormonia/app/api/v2/routers/tasks/dependencies.py:60` |
| `backend-hormonia/tests/test_phase27_async_regression.py` | `app/api/v2/routers/` | `importlib.import_module` + source inspection | WIRED | Router traversal implemented at `backend-hormonia/tests/test_phase27_async_regression.py:11` and module import at `backend-hormonia/tests/test_phase27_async_regression.py:20` |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| TEST-01 | 27-02-PLAN.md, 27-03-PLAN.md | Test fixtures support AsyncSession endpoints via `get_async_db` override | ✓ SATISFIED | Overrides wired in `backend-hormonia/tests/conftest.py:1137` and `backend-hormonia/tests/api/critical/conftest.py:975`; regression guard passes (`backend-hormonia/tests/test_phase27_async_regression.py:26`) |
| TEST-02 | 27-01-PLAN.md, 27-02-PLAN.md, 27-03-PLAN.md | Full suite runs without `MissingGreenlet` or `UndefinedColumn` errors | ✗ BLOCKED | Full-suite verifier run fails early on regression (`/tmp/phase27-fullsuite-x.txt:44`), so clean completion cannot be claimed even though target signatures are absent before failure |
| TEST-03 | 27-01-PLAN.md, 27-04-PLAN.md | Remove async-migration TODO annotations | ✗ BLOCKED | `backend-hormonia/app/` is clean, but `REQUIREMENTS.md` still states "removed from codebase" (`.planning/REQUIREMENTS.md:54`) and `.planning/` contains many literal matches |

All requirement IDs declared in Phase 27 plan frontmatter were accounted for: `TEST-01`, `TEST-02`, `TEST-03`.
No orphaned Phase 27 requirement IDs were found in `.planning/REQUIREMENTS.md` traceability.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `.planning/STATE.md` | 145 | Literal `TODO(async-migration)` token retained in planning narrative | ⚠️ Warning | Breaks Plan 27-04 must-have if interpreted as `.planning/`-wide zero-match gate |
| `.planning/phases/27-test-stability/27-04-PLAN.md` | 25 | Literal `TODO(async-migration)` token retained in plan text | ⚠️ Warning | Same literal-token gate conflict; introduces requirement-scope ambiguity |

### Human Verification Required

None. Current blockers are reproducible through automated checks.

### Gaps Summary

Phase 27 improved versus the prior verification: savepoint adapter parity is in place, the patient import savepoint regression now passes, and the critical suite (`tests/api/critical/`) completes cleanly. However, the phase goal is still not achieved because the full suite is not clean in fresh verifier evidence (`tests/api/test_api_contracts.py::TestUserListAPIContract::test_user_list_returns_paginated_response` fails), which blocks definitive full-suite completion evidence for TEST-02. Additionally, TEST-03 language remains inconsistent: runtime `app/` code is clean, but the requirement and some plan-level must-haves still use broader wording that fails against `.planning/` artifacts.

---

_Verified: 2026-02-28T06:30:36Z_
_Verifier: Claude (gsd-verifier)_
