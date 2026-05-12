---
id: T03
parent: S02
milestone: M013
key_files:
  - backend-hormonia/app/api/v2/routers/messages.py
  - backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py
  - backend-hormonia/tests/api/v2/test_messages.py
key_decisions:
  - Bulk message ownership checks parse and load all requested patients in one bounded query before any scheduling/cache side effects.
  - Direct message mutations eager-load `Message.patient` and enforce shared patient ownership before status validation or mutation.
  - Message mutation cache invalidation targets current actor-scoped cache key prefixes and remains non-critical on cache failures.
duration: 
verification_result: passed
completed_at: 2026-05-12T19:24:24.621Z
blocker_discovered: false
---

# T03: Enforced patient ownership on message sends, bulk sends, direct read-state updates, deletes, and conversation mark-read mutations.

**Enforced patient ownership on message sends, bulk sends, direct read-state updates, deletes, and conversation mark-read mutations.**

## What Happened

Added mutation/read-state IDOR regression coverage for foreign patient sends, mixed owned+foreign bulk sends, foreign direct mark-read, foreign pending-message delete, and foreign conversation mark-read. Updated message mutation routes to reuse the shared patient ownership boundary before any create/update/cancel side effects: single sends load the patient with access before creating outbound messages, bulk routes authorize all patient IDs in one bounded query before accepting the request, direct message mutations eager-load the patient and authorize before status validation, and conversation mark-read authorizes the patient before issuing the update. Successful mutation cache invalidation now uses actor-visible message cache prefixes so invalidation can target the current actor's scoped message/list/conversation keys; denial paths raise before cache invalidation or resource mutation.

## Verification

Ran the focused T03 verification from `backend-hormonia`, the broader modified message/boundary test files, and the slice-level read/conversation ownership gate from the correct backend directory. The focused and broad runs passed with one pre-existing rate-limit test skipped because rate limiting is disabled in the test environment; the slice-level read/conversation gate passed all selected tests.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend-hormonia && pytest tests/api/v2/test_patient_ownership_boundary.py tests/api/v2/test_messages.py -q -k "message_mutation or read_state or bulk or send_message"` | 0 | ✅ pass | 28040ms |
| 2 | `cd backend-hormonia && pytest tests/api/v2/test_patient_ownership_boundary.py tests/api/v2/test_messages.py -q` | 0 | ✅ pass | 28814ms |
| 3 | `cd backend-hormonia && pytest tests/api/v2/test_patient_ownership_boundary.py -q -k "message_read or conversation"` | 0 | ✅ pass | 26663ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/messages.py`
- `backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py`
- `backend-hormonia/tests/api/v2/test_messages.py`
