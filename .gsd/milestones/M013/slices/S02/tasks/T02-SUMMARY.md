---
id: T02
parent: S02
milestone: M013
key_files:
  - backend-hormonia/app/api/v2/routers/messages.py
  - backend-hormonia/tests/api/v2/security_boundary_helpers.py
  - backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py
  - backend-hormonia/tests/api/v2/test_messages.py
  - tests/unit/api/v2/test_patient_access_helpers.py
key_decisions:
  - Patient-bound message caches are actor-scoped and are read only after DB ownership succeeds; cache failures stay non-critical and non-authorizing.
duration: 
verification_result: passed
completed_at: 2026-05-12T19:05:07.755Z
blocker_discovered: false
---

# T02: Scoped message read, list, conversation, unread-count, and patient stats routes to the shared patient ownership boundary with cache-safe actor scoping.

**Scoped message read, list, conversation, unread-count, and patient stats routes to the shared patient ownership boundary with cache-safe actor scoping.**

## What Happened

Added message ownership boundary coverage for direct message IDOR, patient_id-filter list IDOR, global conversation leakage, conversation history IDOR, unread-count side channel, cached foreign response replay, assigned-doctor positives, and admin-all positives. Updated the active v2 messages router so direct message and patient-specific conversation/list/stats/unread routes prove patient ownership through the shared helper before returning data or reading patient-bound caches. Global message list and conversation summary queries now add SQL-level patient ownership joins for doctors while preserving admin-all behavior and pagination limits. Patient-bound cache keys now include non-PHI actor role/id scope, and cache failures remain non-critical diagnostics only. Also fixed the verification failure by adding a root-cwd compatibility wrapper for the canonical patient access helper tests and aligned the legacy message API test patient fixture with the authenticated API-v2 doctor fixture now that ownership is enforced.

## Verification

Ran the authoritative focused verification command from the task plan, the previously failing root-cwd helper gate, and an existing messages API regression subset covering list, message, stats, and conversation routes. All passed. The root-cwd helper gate still emits existing Pydantic deprecation warnings but exits successfully.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend-hormonia && pytest tests/api/v2/test_patient_ownership_boundary.py -q -k "message_read or conversation"` | 0 | ✅ pass | 25514ms |
| 2 | `cd backend-hormonia && pytest tests/api/v2/test_messages.py -q -k "list_messages or conversation or stats or get_message"` | 0 | ✅ pass | 26357ms |
| 3 | `pytest tests/unit/api/v2/test_patient_access_helpers.py -q` | 0 | ✅ pass | 23060ms |

## Deviations

Added a root-level compatibility test wrapper because the auto-fix gate invoked tests/unit/api/v2/test_patient_access_helpers.py from the repository root while the canonical test file lives under backend-hormonia/tests. Also updated the legacy test_messages.py patient fixture to use the API-v2 authenticated doctor fixture so positive tests remain valid under enforced ownership.

## Known Issues

The root-cwd helper gate reports existing Pydantic v1-style validator deprecation warnings; they were not introduced or fixed here.

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/messages.py`
- `backend-hormonia/tests/api/v2/security_boundary_helpers.py`
- `backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py`
- `backend-hormonia/tests/api/v2/test_messages.py`
- `tests/unit/api/v2/test_patient_access_helpers.py`
