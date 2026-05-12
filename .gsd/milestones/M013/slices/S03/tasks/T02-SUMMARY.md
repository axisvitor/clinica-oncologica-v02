---
id: T02
parent: S03
milestone: M013
key_files:
  - backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py
  - backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public_security.py
  - backend-hormonia/app/domain/quizzes/session/token_manager.py
  - backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py
key_decisions:
  - Stored QuizSession link metadata (token_hash, link_status, expires_at) is authoritative for public quiz token access and submission after JWT signature verification.
  - Public token denial logs use generic reason plus non-PHI resource identifiers only; response bodies remain generic and exclude token material.
  - Public current/submit now accept only hash-matching `quiz_access` tokens; non-authoritative token types such as `quiz_submission` are rejected for these link flows.
duration: 
verification_result: passed
completed_at: 2026-05-12T20:47:42.732Z
blocker_discovered: false
---

# T02: Bound public monthly quiz access and submit to the persisted hash-matching active QuizSession link state before payload reads or response writes.

**Bound public monthly quiz access and submit to the persisted hash-matching active QuizSession link state before payload reads or response writes.**

## What Happened

Added a shared public quiz link validator that decodes JWTs through TokenManager, requires type/patient/template/session/exp claims, loads QuizSession by token session_id only, rejects patient/template/path mismatches, enforces started/non-expired sessions, active link metadata, stored token_hash equality, and the earliest JWT/session/metadata expiration boundary before any quiz payload or response write. Rewired tokenized public current and public submit to use the validated session/patient/template instead of fallback lookups or token-created sessions, and closes the link metadata as `used` when a valid submission completes the quiz. The compatibility `/access` token path now uses the same validator before setting the session cookie and no longer creates sessions from public tokens. TokenManager invalid/expired diagnostics no longer include token prefixes. Extended the boundary test fixture for legacy quiz_responses schema alignment and added positive/negative public-token tests for valid read+submit, missing session_id, mismatched patient/template/session/path/type, token hash mismatch, terminal link/session state, and expired JWT/session/metadata cases with no response writes on rejection.

## Verification

Verified syntax for the changed Python files, ran the T02-focused public token/link-state test selection, and ran the full quiz link/session boundary test file from `backend-hormonia` to confirm the authenticated ownership checks still pass alongside the new public-token protections.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend-hormonia && python -m py_compile app/api/v2/routers/monthly_quiz_operations/public_security.py app/api/v2/routers/monthly_quiz_operations/public.py app/domain/quizzes/session/token_manager.py tests/api/v2/test_quiz_link_session_boundary.py` | 0 | ✅ pass | 193ms |
| 2 | `cd backend-hormonia && pytest tests/api/v2/test_quiz_link_session_boundary.py -q -k "public_token or token_hash or link_state or expired"` | 0 | ✅ pass | 27993ms |
| 3 | `cd backend-hormonia && pytest tests/api/v2/test_quiz_link_session_boundary.py -q` | 0 | ✅ pass | 26862ms |

## Deviations

Also applied the stored-link validator to the compatibility `/quiz-extensions/access` token path so public token access no longer creates fallback sessions there either, and removed token-prefix logging from TokenManager to satisfy the slice-wide no-token-material observability constraint.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py`
- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public_security.py`
- `backend-hormonia/app/domain/quizzes/session/token_manager.py`
- `backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py`
